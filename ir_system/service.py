from collections import defaultdict
import json
import threading
import traceback

from .config import CONFIG, METHODS, RESULTS
from .dataset import load
from .engine import RetrievalEngine
from .experiment import run_experiment
from .metrics import evaluate_ranking, metric_key
from .storage import Database

class Service:
    def __init__(self, database_path=None):
        self.documents, self.queries, self.qrels, self.manifest = load()
        self.engine = RetrievalEngine(self.documents)
        self.database = Database(database_path)
        self.database.import_dataset(self.documents, self.queries, self.qrels, self.manifest)
        self.queries_by_id = {q["query_id"]: q for q in self.queries}
        self.judgments = defaultdict(dict)
        for r in self.qrels:
            self.judgments[r["query_id"]][r["doc_id"]] = r["raw_grade"]
        self._lock = threading.Lock()
        self._state = {"running": False, "stage": "idle", "done": 0, "total": 0, "error": None}

    def status(self):
        return {"dataset": self.manifest, "config": CONFIG, "index": self.engine.index_stats,
                "experiment": self.experiment_status(), "history": self.database.history()}

    def search(self, text, query_id=None, top_k=10):
        if self.experiment_status()["running"]:
            raise RuntimeError("Đang đo thực nghiệm. Vui lòng chờ để tránh ảnh hưởng số đo.")
        if query_id is not None:
            if str(query_id) not in self.queries_by_id:
                raise ValueError("Không có mã truy vấn này")
            query = self.queries_by_id[str(query_id)]
            text = query["text"]
        else:
            query = None
        if not isinstance(text, str) or len(text) > 5000:
            raise ValueError("Truy vấn phải là chuỗi tối đa 5.000 ký tự")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 50:
            raise ValueError("Số kết quả phải từ 1 đến 50")
        methods = {}
        for method in METHODS:
            result = self.engine.search(text, method)
            items = []
            for rank, (doc_id, score) in enumerate(result["ranking"][:top_k], 1):
                doc = self.engine.doc_lookup[doc_id]
                items.append({"rank": rank, "doc_id": doc_id, "title": doc["title"],
                              "snippet": doc["body"][:350], "score": score,
                              "raw_grade": self.judgments[query["query_id"]].get(doc_id) if query else None,
                              "relevant": (self.judgments[query["query_id"]].get(doc_id, 0) > 0) if query else None})
            scores = evaluate_ranking(result["ranking"], self.judgments[query["query_id"]]) if query else None
            methods[method] = {"items": items, "returned_count": len(result["ranking"]),
                               "zero_vector": result["zero_vector"], "timing": result["timing"],
                               "metrics": {metric_key(name, k): v for (name, k), v in scores.items()} if scores else None}
        return {"text": text, "query": query, "inspection": self.engine.inspect(text), "methods": methods}

    def latest_summary(self, experiment_id=None):
        completed = [row for row in self.database.history(1000) if row["status"] == "COMPLETED"]
        if experiment_id is not None:
            completed = [row for row in completed if row["experiment_id"] == experiment_id]
        for row in completed:
            path = RESULTS / row["experiment_id"] / "summary.json"
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    def experiment_status(self):
        with self._lock:
            return dict(self._state)

    def start_experiment(self, split="TEST", repeats=30):
        if split not in ("DEV", "TEST") or isinstance(repeats, bool) or not isinstance(repeats, int) or not 1 <= repeats <= 30:
            raise ValueError("Tập truy vấn hoặc số lượt đo không hợp lệ")
        with self._lock:
            if self._state["running"]:
                raise RuntimeError("Đã có một thực nghiệm đang chạy")
            self._state = {"running": True, "stage": "starting", "done": 0, "total": 0, "error": None}
        def update(values):
            with self._lock:
                self._state.update(values)
        def task():
            try:
                summary = run_experiment(self.engine, self.database, self.queries, self.qrels, self.manifest,
                                         split=split, repeats=repeats, progress=update)
                update({"stage": "completed", "experiment_id": summary["experiment_id"]})
            except Exception as exc:
                traceback.print_exc()
                update({"stage": "failed", "error": str(exc)})
            finally:
                update({"running": False})
        threading.Thread(target=task, daemon=True).start()
        return self.experiment_status()
