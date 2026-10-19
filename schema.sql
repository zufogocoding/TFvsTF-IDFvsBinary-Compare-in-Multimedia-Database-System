PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS datasets (
 dataset_id TEXT PRIMARY KEY, name TEXT NOT NULL, language TEXT NOT NULL,
 source_url TEXT NOT NULL, manifest_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
 dataset_id TEXT NOT NULL, doc_id TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
 author TEXT NOT NULL, bib TEXT NOT NULL, content_hash TEXT NOT NULL,
 PRIMARY KEY(dataset_id,doc_id), FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
);
CREATE TABLE IF NOT EXISTS queries (
 dataset_id TEXT NOT NULL, query_id TEXT NOT NULL, source_query_id TEXT NOT NULL,
 text TEXT NOT NULL, split TEXT NOT NULL CHECK(split IN ('DEV','TEST')),
 PRIMARY KEY(dataset_id,query_id), FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
);
CREATE TABLE IF NOT EXISTS qrels (
 dataset_id TEXT NOT NULL, query_id TEXT NOT NULL, doc_id TEXT NOT NULL,
 raw_grade INTEGER NOT NULL CHECK(raw_grade IN (-1,1,2,3,4)),
 PRIMARY KEY(dataset_id,query_id,doc_id),
 FOREIGN KEY(dataset_id,query_id) REFERENCES queries(dataset_id,query_id),
 FOREIGN KEY(dataset_id,doc_id) REFERENCES documents(dataset_id,doc_id)
);
CREATE TABLE IF NOT EXISTS experiments (
 experiment_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, created_at TEXT NOT NULL,
 completed_at TEXT, split TEXT NOT NULL CHECK(split IN ('DEV','TEST')),
 config_json TEXT NOT NULL, config_hash TEXT NOT NULL, code_hash TEXT NOT NULL,
 environment_json TEXT NOT NULL, artifact_manifest_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('CREATED','RUNNING','COMPLETED','FAILED')),
 error_text TEXT, UNIQUE(experiment_id,dataset_id),
 FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
);
CREATE TABLE IF NOT EXISTS query_runs (
 run_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
 query_id TEXT NOT NULL, method TEXT NOT NULL CHECK(method IN ('BINARY','TF','TFIDF')),
 status TEXT NOT NULL CHECK(status IN ('COMPLETED','FAILED')),
 returned_count INTEGER NOT NULL CHECK(returned_count>=0),
 zero_vector_flag INTEGER NOT NULL CHECK(zero_vector_flag IN (0,1)),
 UNIQUE(experiment_id,query_id,method), UNIQUE(run_id,dataset_id),
 FOREIGN KEY(experiment_id,dataset_id) REFERENCES experiments(experiment_id,dataset_id),
 FOREIGN KEY(dataset_id,query_id) REFERENCES queries(dataset_id,query_id)
);
CREATE TABLE IF NOT EXISTS ranked_results (
 run_id TEXT NOT NULL, rank INTEGER NOT NULL CHECK(rank>=1), dataset_id TEXT NOT NULL,
 doc_id TEXT NOT NULL, score REAL NOT NULL CHECK(score>0),
 PRIMARY KEY(run_id,rank), UNIQUE(run_id,doc_id),
 FOREIGN KEY(run_id,dataset_id) REFERENCES query_runs(run_id,dataset_id),
 FOREIGN KEY(dataset_id,doc_id) REFERENCES documents(dataset_id,doc_id)
);
CREATE TABLE IF NOT EXISTS query_metrics (
 run_id TEXT NOT NULL, metric_name TEXT NOT NULL, cutoff INTEGER NOT NULL CHECK(cutoff>=0),
 value REAL NOT NULL CHECK(value>=0 AND value<=1.000000000001),
 PRIMARY KEY(run_id,metric_name,cutoff), FOREIGN KEY(run_id) REFERENCES query_runs(run_id)
);
CREATE TABLE IF NOT EXISTS timing_samples (
 run_id TEXT NOT NULL, repeat_no INTEGER NOT NULL CHECK(repeat_no>=1),
 encode_ms REAL NOT NULL CHECK(encode_ms>=0), score_ms REAL NOT NULL CHECK(score_ms>=0),
 sort_ms REAL NOT NULL CHECK(sort_ms>=0),
 PRIMARY KEY(run_id,repeat_no), FOREIGN KEY(run_id) REFERENCES query_runs(run_id)
);
CREATE INDEX IF NOT EXISTS ix_query_runs_experiment ON query_runs(experiment_id,method);
CREATE INDEX IF NOT EXISTS ix_queries_split ON queries(dataset_id,split);
PRAGMA user_version = 1;
