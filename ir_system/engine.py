"""One count matrix, three weighting rules, the same cosine ranking."""
from collections import Counter
from pathlib import Path
from time import perf_counter_ns
import json
import platform
import unicodedata
import re
import os

import numpy as np
import scipy
from scipy.sparse import save_npz
import sklearn
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_info, threadpool_limits

from .config import CONFIG, METHODS, RUNTIME, sha256_file

_THREAD_LIMITER = threadpool_limits(limits=1)

def preprocess(text):
    return unicodedata.normalize("NFKC", text).lower()

def tokenize(text):
    return re.findall(r"[a-z]+", preprocess(text))

def environment():
    cpu_model = platform.processor()
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding='utf-8').splitlines():
            if line.startswith('model name'):
                cpu_model = line.split(':', 1)[1].strip()
                break
    try:
        memory_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    except (AttributeError, ValueError, OSError):
        memory_bytes = None
    return {
        "python": platform.python_version(), "platform": platform.platform(),
        "processor": platform.processor(), "machine": platform.machine(),
        "cpu_model": cpu_model, "logical_cpus": os.cpu_count(), "ram_total_bytes": memory_bytes,
        "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
        "threadpools": [{k: p.get(k) for k in ("internal_api", "num_threads", "version", "architecture")}
                        for p in threadpool_info()],
        "timing_clock": "time.perf_counter_ns", "timing_unit": "ms",
    }

class RetrievalEngine:
    def __init__(self, documents):
        if not documents:
            raise ValueError("The corpus must contain documents")
        self.documents = documents
        self.doc_ids = np.asarray([str(d["doc_id"]) for d in documents])
        if len(set(self.doc_ids)) != len(self.doc_ids):
            raise ValueError("Duplicate document identifiers")
        self.doc_lookup = {d["doc_id"]: d for d in documents}
        self.vectorizer = CountVectorizer(
            preprocessor=preprocess, lowercase=False, token_pattern=r"[a-z]+",
            stop_words=None, ngram_range=(1, 1), min_df=1, max_df=1.0,
            max_features=None, dtype=np.float64,
        )
        texts = [d.get("title", "") + " " + d.get("body", "") for d in documents]
        t0 = perf_counter_ns()
        self.counts = self.vectorizer.fit_transform(texts).tocsr()
        self.counts.sort_indices()
        t1 = perf_counter_ns()
        self.vocabulary = self.vectorizer.vocabulary_
        self.feature_names = self.vectorizer.get_feature_names_out()
        self.df = np.asarray((self.counts > 0).sum(axis=0)).ravel().astype(np.float64)
        self.idf = np.log(len(documents) / self.df)
        self.matrices, self.stats = {}, {}
        for method in METHODS:
            start = perf_counter_ns()
            matrix = self._weight(self.counts, method)
            matrix = normalize(matrix, norm="l2", copy=False).tocsr()
            matrix.eliminate_zeros()
            matrix.sort_indices()
            self.matrices[method] = matrix
            self.stats[method] = {
                "build_ms": (perf_counter_ns() - start) / 1e6,
                "nnz": int(matrix.nnz), "dtype": str(matrix.dtype),
                "csr_bytes": int(matrix.data.nbytes + matrix.indices.nbytes + matrix.indptr.nbytes),
                "zero_documents": int(np.count_nonzero(np.diff(matrix.indptr) == 0)),
            }
        self.index_stats = {
            "documents": len(documents), "vocabulary_size": len(self.vocabulary),
            "common_preprocessing_and_count_ms": (t1 - t0) / 1e6,
            "idf_bytes": int(self.idf.nbytes),
            "vocabulary_utf8_json_bytes": len(json.dumps(self.vocabulary, ensure_ascii=False).encode()),
            "methods": self.stats,
        }

    def _weight(self, counts, method):
        if method not in METHODS:
            raise ValueError("Unknown method: " + str(method))
        matrix = counts.astype(np.float64, copy=True)
        if method == "BINARY":
            matrix.data[:] = 1.0
        elif method == "TFIDF":
            matrix = matrix.multiply(self.idf).tocsr()
        matrix.eliminate_zeros()
        return matrix

    def query_vector(self, text, method):
        counts = self.vectorizer.transform([text]).tocsr()
        weighted = self._weight(counts, method)
        return normalize(weighted, norm="l2", copy=False).tocsr()

    def search(self, text, method):
        t0 = perf_counter_ns()
        q = self.query_vector(text, method)
        t1 = perf_counter_ns()
        if q.nnz == 0:
            return {"ranking": [], "zero_vector": True,
                    "timing": {"encode_ms": (t1-t0)/1e6, "score_ms": 0.0, "sort_ms": 0.0}}
        scores = (self.matrices[method] @ q.T).toarray().ravel()
        t2 = perf_counter_ns()
        positions = np.flatnonzero(scores > 0)
        order = np.lexsort((self.doc_ids[positions], -scores[positions]))
        ranking = [(str(self.doc_ids[i]), float(scores[i])) for i in positions[order]]
        t3 = perf_counter_ns()
        return {"ranking": ranking, "zero_vector": False,
                "timing": {"encode_ms": (t1-t0)/1e6, "score_ms": (t2-t1)/1e6, "sort_ms": (t3-t2)/1e6}}

    def inspect(self, text):
        tokens = tokenize(text)
        counts = Counter(tokens)
        present = [t for t in counts if t in self.vocabulary]
        return {
            "tokens": tokens, "unique_count": len(counts),
            "oov_tokens": [t for t in counts if t not in self.vocabulary],
            "weights": [{"term": t, "count": counts[t], "binary": 1,
                         "idf": float(self.idf[self.vocabulary[t]]),
                         "tfidf": float(counts[t] * self.idf[self.vocabulary[t]])} for t in present],
        }

    def write_artifacts(self, directory=None):
        directory = Path(directory or RUNTIME / "index")
        directory.mkdir(parents=True, exist_ok=True)
        files = []
        for method, matrix in self.matrices.items():
            path = directory / (method.lower() + ".npz")
            save_npz(path, matrix, compressed=True)
            self.stats[method]["index_file_bytes"] = path.stat().st_size
            files.append(path)
        path = directory / "vocabulary.json"
        path.write_text(json.dumps(self.vocabulary, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        files.append(path)
        path = directory / "doc_ids.json"
        path.write_text(json.dumps(self.doc_ids.tolist()), encoding="utf-8")
        files.append(path)
        path = directory / "idf.npy"
        np.save(path, self.idf, allow_pickle=False)
        files.append(path)
        manifest = {"stats": self.index_stats,
                    "files": {p.name: {"sha256": sha256_file(p), "size_bytes": p.stat().st_size} for p in files}}
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return manifest
