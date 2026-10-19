from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RUNTIME = ROOT / "runtime"
RESULTS = ROOT / "results"
METHODS = ("BINARY", "TF", "TFIDF")
DATASET_ID = "cranfield-1400-v1"
SEED = 42

CONFIG = {
    "dataset": DATASET_ID,
    "fields": ["title", "body"],
    "unicode": "NFKC",
    "lowercase": True,
    "token_pattern": "[a-z]+",
    "stopwords": None,
    "stemming": False,
    "ngram_range": [1, 1],
    "min_df": 1,
    "max_df": 1.0,
    "max_features": None,
    "tf": "raw_count",
    "idf": "ln(N/df)",
    "query_weights": "same_as_document_using_corpus_idf",
    "normalization": "l2",
    "similarity": "cosine",
    "dtype": "float64",
    "retrieve": "strictly_positive_scores_only",
    "tie_break": "doc_id_lexicographic_ascending",
    "relevance": "raw_grade > 0",
    "ndcg_gain": "binary_relevance_0_or_1",
    "metric_cutoffs": [5, 10, 20],
    "development_queries": 45,
    "test_queries": 180,
    "split_algorithm": "random.Random(42).shuffle on source query order",
    "seed": SEED,
    "warmup_per_method": 3,
    "timing_repeats": 30,
    "bootstrap_resamples": 10000,
    "threads": 1,
}

def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def config_hash(value=CONFIG):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def source_hash():
    h = hashlib.sha256()
    paths = list((ROOT / "ir_system").glob("*.py"))
    paths += list(ROOT.glob("*.py"))
    paths += list((ROOT / "web").glob("*"))
    paths += [ROOT / "schema.sql", ROOT / "requirements.txt"]
    for path in sorted(p for p in paths if p.is_file()):
        h.update(str(path.relative_to(ROOT)).replace("\\", "/").encode())
        h.update(path.read_bytes())
    return h.hexdigest()
