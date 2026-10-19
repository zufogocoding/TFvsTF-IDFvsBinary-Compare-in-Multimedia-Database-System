from collections import defaultdict
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import csv
import json
import random

import numpy as np

from .config import CONFIG, METHODS, RESULTS, SEED, canonical_json, config_hash, source_hash
from .engine import environment
from .metrics import METRICS, evaluate_ranking, metric_key
from .storage import utcnow

EXPORT_FILES = ("summary.json", "summary.csv", "per_query_metrics.csv", "rankings.tsv",
                "timing_samples.csv", "config.json", "environment.json", "manifest.json", "paired_comparisons.json")

def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

def paired_bootstrap(per_query, query_ids, resamples=10000, seed=SEED):
    if resamples < 1:
        raise ValueError("At least one bootstrap resample is required")
    index = np.random.default_rng(seed).integers(0, len(query_ids), size=(resamples, len(query_ids)))
    pairs = []
    for a, b in combinations(METHODS, 2):
        differences = np.asarray([per_query[(q, a)][("AP", 0)] - per_query[(q, b)][("AP", 0)] for q in query_ids])
        means = differences[index].mean(axis=1)
        low, high = np.percentile(means, [2.5, 97.5])
        pairs.append({"a": a, "b": b, "mean_ap_difference_a_minus_b": float(differences.mean()),
                      "ci95_percentile": [float(low), float(high)],
                      "a_wins": int(np.count_nonzero(differences > 0)),
                      "b_wins": int(np.count_nonzero(differences < 0)),
                      "ties": int(np.count_nonzero(differences == 0)),
                      "query_count": len(query_ids), "resamples": resamples, "seed": seed,
                      "interpretation": "exploratory paired query bootstrap; no simultaneous multiple-testing claim"})
    return pairs

def run_experiment(engine, database, queries, qrels, manifest, split="TEST", repeats=30, bootstrap=10000, progress=None, results_root=RESULTS, artifact_directory=None):
    if split not in ("DEV", "TEST") or not 1 <= repeats <= 100:
        raise ValueError("Invalid split or repeat count")
    selected = [q for q in queries if q["split"] == split]
    judgments = defaultdict(dict)
    for r in qrels:
        judgments[r["query_id"]][r["doc_id"]] = r["raw_grade"]
    excluded = [q["query_id"] for q in selected if not any(g > 0 for g in judgments[q["query_id"]].values())]
    selected = [q for q in selected if q["query_id"] not in excluded]
    if not selected:
        raise ValueError("No evaluable queries")
    ids = [q["query_id"] for q in selected]
    config = deepcopy(CONFIG)
    config.update({"split": split, "query_ids": ids, "timing_repeats": repeats, "bootstrap_resamples": bootstrap})
    env = environment()
    artifacts = engine.write_artifacts(artifact_directory)
    experiment_id = database.begin_experiment(manifest["dataset_id"], split, config, env, artifacts)
    target = Path(results_root) / experiment_id
    target.mkdir(parents=True, exist_ok=False)
    def notify(stage, done, total):
        if progress:
            progress({"experiment_id": experiment_id, "stage": stage, "done": done, "total": total})
    try:
        notify("quality", 0, len(selected))
        per_query, run_ids, query_rows = {}, {}, []
        with (target / "rankings.tsv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(["query_id", "method", "rank", "doc_id", "score"])
            for n, query in enumerate(selected, 1):
                qid = query["query_id"]
                for method in METHODS:
                    result = engine.search(query["text"], method)
                    scores = evaluate_ranking(result["ranking"], judgments[qid])
                    per_query[(qid, method)] = scores
                    run_ids[(qid, method)] = database.save_query(experiment_id, manifest["dataset_id"], qid, method, result, scores)
                    row = {"query_id": qid, "method": method, "zero_vector": int(result["zero_vector"]), "returned_count": len(result["ranking"])}
                    row.update({metric_key(name, k): value for (name, k), value in scores.items()})
                    query_rows.append(row)
                    writer.writerows((qid, method, rank, did, score) for rank, (did, score) in enumerate(result["ranking"], 1))
                notify("quality", n, len(selected))
        for method in METHODS:
            for _ in range(CONFIG["warmup_per_method"]):
                engine.search(selected[0]["text"], method)
        randomizer, timing_values = random.Random(SEED), defaultdict(list)
        with (target / "timing_samples.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["query_id", "method", "repeat_no", "encode_ms", "score_ms", "sort_ms", "total_ms"])
            for n, query in enumerate(selected, 1):
                qid, db_rows = query["query_id"], []
                for repeat in range(1, repeats + 1):
                    order = list(METHODS)
                    randomizer.shuffle(order)
                    for method in order:
                        measured = engine.search(query["text"], method)["timing"]
                        values = [measured[name] for name in ("encode_ms", "score_ms", "sort_ms")]
                        total_ms = sum(values)
                        timing_values[method].append(total_ms)
                        db_rows.append((run_ids[(qid, method)], repeat, *values))
                        writer.writerow([qid, method, repeat, *values, total_ms])
                database.save_timings(db_rows)
                notify("timing", n, len(selected))
        paired = paired_bootstrap(per_query, ids, resamples=bootstrap)
        summary_methods = {}
        for method in METHODS:
            scores = {metric_key(name, k): float(np.mean([per_query[(qid, method)][(name, k)] for qid in ids])) for name, k in METRICS}
            scores["MAP"] = scores.pop("AP")
            scores["timing"] = {"p50_ms": float(np.percentile(timing_values[method], 50)),
                                "p95_ms": float(np.percentile(timing_values[method], 95)),
                                "samples": len(timing_values[method])}
            scores["zero_queries"] = sum(row["zero_vector"] for row in query_rows if row["method"] == method)
            scores["index"] = deepcopy(engine.stats[method])
            summary_methods[method] = scores
        summary = {"experiment_id": experiment_id, "completed_at_utc": utcnow(),
                   "dataset_id": manifest["dataset_id"], "split": split, "query_count": len(ids),
                   "excluded_no_positive_qrels": excluded, "config_hash": config_hash(config),
                   "code_hash": source_hash(), "methods": summary_methods, "paired_comparisons": paired,
                   "environment": env, "index": deepcopy(engine.index_stats),
                   "ndcg_gain": "binary (raw_grade > 0)", "timing_repeats": repeats,
                   "notes": ["All quality metrics use binary relevance; raw positive grade order is not assumed.",
                             "AP includes every strictly positive-scoring retrieved document; missing relevant documents contribute zero.",
                             "Latency is warm-index query encoding + score computation + complete positive-result sort, excluding HTTP, SQLite and UI."]}
        fields = ["query_id", "method", "zero_vector", "returned_count", "AP", "nDCG_binary@10", "P@5", "P@10", "R@10", "R@20"]
        with (target / "per_query_metrics.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields);writer.writeheader();writer.writerows(query_rows)
        with (target / "summary.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["method", "MAP", "nDCG_binary@10", "P@5", "P@10", "R@10", "R@20", "p50_ms", "p95_ms", "csr_bytes", "nnz"])
            for method in METHODS:
                s = summary_methods[method]
                writer.writerow([method, s["MAP"], s["nDCG_binary@10"], s["P@5"], s["P@10"], s["R@10"], s["R@20"], s["timing"]["p50_ms"], s["timing"]["p95_ms"], s["index"]["csr_bytes"], s["index"]["nnz"]])
        for name, value in (("summary.json", summary), ("config.json", config), ("environment.json", env), ("manifest.json", {"dataset": manifest, "artifacts": artifacts}), ("paired_comparisons.json", paired)):
            write_json(target / name, value)
        database.finish(experiment_id, len(ids), repeats)
        notify("completed", len(selected), len(selected))
        return summary
    except BaseException as error:
        database.fail(experiment_id, error)
        raise
