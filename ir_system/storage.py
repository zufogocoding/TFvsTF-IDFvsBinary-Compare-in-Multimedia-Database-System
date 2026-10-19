from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import uuid
from .config import ROOT, RUNTIME, canonical_json, config_hash, source_hash

TABLES = ("datasets", "documents", "queries", "qrels", "experiments", "query_runs", "ranked_results", "query_metrics", "timing_samples")

def utcnow():
    return datetime.now(timezone.utc).isoformat()

class Database:
    def __init__(self, path=None):
        self.path = Path(path or RUNTIME / "ir_compare.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            # A single-file rollback journal is portable across local filesystems
            # and makes the delivered SQLite file independent of WAL sidecars.
            db.execute("PRAGMA journal_mode=DELETE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("Unsupported database schema version")
            db.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
            integrity = [row[0] for row in db.execute("PRAGMA integrity_check")]
            if integrity != ["ok"]:
                raise ValueError("SQLite integrity check failed. Preserve the file and rebuild from the supplied dataset: " + "; ".join(integrity[:3]))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=60)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_dataset(self, documents, queries, qrels, manifest):
        dataset_id = manifest["dataset_id"]
        with self.connect() as db:
            existing = db.execute("SELECT manifest_json FROM datasets WHERE dataset_id=?", (dataset_id,)).fetchone()
            if existing:
                if json.loads(existing[0])["files"] != manifest["files"]:
                    raise ValueError("Existing dataset ID has different content; create a new version")
                for table, expected in (("documents", len(documents)), ("queries", len(queries)), ("qrels", len(qrels))):
                    actual = db.execute(f"SELECT COUNT(*) FROM {table} WHERE dataset_id=?", (dataset_id,)).fetchone()[0]
                    if actual != expected:
                        raise ValueError("Database dataset is incomplete: " + table)
                return
            db.execute("INSERT INTO datasets VALUES(?,?,?,?,?,?)", (dataset_id, manifest["name"], manifest["language"], manifest["source_url"], canonical_json(manifest), utcnow()))
            db.executemany("INSERT INTO documents VALUES(?,?,?,?,?,?,?)", [
                (dataset_id, d["doc_id"], d["title"], d["body"], d.get("author", ""), d.get("bib", ""),
                 hashlib.sha256((d["title"] + " " + d["body"]).encode()).hexdigest()) for d in documents])
            db.executemany("INSERT INTO queries VALUES(?,?,?,?,?)", [
                (dataset_id, q["query_id"], q["source_query_id"], q["text"], q["split"]) for q in queries])
            db.executemany("INSERT INTO qrels VALUES(?,?,?,?)", [
                (dataset_id, r["query_id"], r["doc_id"], r["raw_grade"]) for r in qrels])

    def begin_experiment(self, dataset_id, split, config, environment, artifacts):
        experiment_id = utcnow()[:19].replace(":", "").replace("-", "") + "_" + uuid.uuid4().hex[:8]
        with self.connect() as db:
            db.execute("INSERT INTO experiments(experiment_id,dataset_id,created_at,split,config_json,config_hash,code_hash,environment_json,artifact_manifest_json,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (experiment_id, dataset_id, utcnow(), split, canonical_json(config), config_hash(config), source_hash(), canonical_json(environment), canonical_json(artifacts), "RUNNING"))
        return experiment_id

    def save_query(self, experiment_id, dataset_id, query_id, method, result, metrics):
        run_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO query_runs VALUES(?,?,?,?,?,?,?,?)", (run_id, experiment_id, dataset_id, query_id, method, "COMPLETED", len(result["ranking"]), int(result["zero_vector"])))
            db.executemany("INSERT INTO ranked_results VALUES(?,?,?,?,?)", [
                (run_id, rank, dataset_id, doc_id, score) for rank, (doc_id, score) in enumerate(result["ranking"], 1)])
            db.executemany("INSERT INTO query_metrics VALUES(?,?,?,?)", [(run_id, name, k, float(v)) for (name, k), v in metrics.items()])
        return run_id

    def save_timings(self, rows):
        with self.connect() as db:
            db.executemany("INSERT INTO timing_samples VALUES(?,?,?,?,?)", rows)

    def finish(self, experiment_id, expected_queries, repeats):
        with self.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM query_runs WHERE experiment_id=?", (experiment_id,)).fetchone()[0]
            metrics = db.execute("SELECT COUNT(*) FROM query_metrics m JOIN query_runs r USING(run_id) WHERE experiment_id=?", (experiment_id,)).fetchone()[0]
            timings = db.execute("SELECT COUNT(*) FROM timing_samples t JOIN query_runs r USING(run_id) WHERE experiment_id=?", (experiment_id,)).fetchone()[0]
            if count != expected_queries * 3 or metrics != count * 6 or timings != count * repeats:
                raise ValueError("Incomplete experimental records")
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Database foreign-key check failed")
            integrity = [row[0] for row in db.execute("PRAGMA integrity_check")]
            if integrity != ["ok"]:
                raise ValueError("Database integrity check failed: " + "; ".join(integrity[:3]))
            db.execute("UPDATE experiments SET status='COMPLETED',completed_at=? WHERE experiment_id=?", (utcnow(), experiment_id))

    def fail(self, experiment_id, error):
        with self.connect() as db:
            db.execute("UPDATE experiments SET status='FAILED',completed_at=?,error_text=? WHERE experiment_id=?", (utcnow(), str(error), experiment_id))

    def overview(self):
        with self.connect() as db:
            return [{"table": t, "rows": db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]} for t in TABLES]

    def history(self, limit=20):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT experiment_id,created_at,completed_at,split,status,config_hash,code_hash FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,))]
