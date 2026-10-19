"""Local JSON API and static UI, using Python's standard HTTP server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import json
import mimetypes
import re

from .config import ROOT, DATA, RESULTS
from .experiment import EXPORT_FILES

def make_server(service, host="127.0.0.1", port=8000):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def send_bytes(self, value, content_type, status=200, filename=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(value)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(value)

        def json(self, value, status=200):
            self.send_bytes(json.dumps(value, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8", status)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            params = parse_qs(parsed.query)
            try:
                if path == "/api/status":
                    return self.json(service.status())
                if path == "/api/queries":
                    split = params.get("split", [None])[0]
                    return self.json([q for q in service.queries if split is None or q["split"] == split])
                if path.startswith("/api/documents/"):
                    doc_id = path.removeprefix("/api/documents/")
                    doc = service.engine.doc_lookup.get(doc_id)
                    return self.json(doc or {"error": "Không tìm thấy văn bản"}, 200 if doc else 404)
                if path == "/api/summary":
                    return self.json(service.latest_summary(params.get("experiment_id", [None])[0]))
                if path == "/api/experiment-status":
                    return self.json(service.experiment_status())
                if path == "/api/database":
                    return self.json(service.database.overview())
                if path.startswith("/api/exports/"):
                    parts = path.split("/")
                    if len(parts) != 5:
                        raise ValueError("Đường dẫn xuất không hợp lệ")
                    experiment_id, name = parts[3:]
                    if not re.fullmatch(r"[A-Za-z0-9_]+", experiment_id) or name not in EXPORT_FILES:
                        raise ValueError("Tệp xuất không hợp lệ")
                    history = service.database.history(1000)
                    if not any(r["experiment_id"] == experiment_id and r["status"] == "COMPLETED" for r in history):
                        return self.json({"error": "Thực nghiệm chưa hoàn tất"}, 404)
                    file = RESULTS / experiment_id / name
                    if not file.is_file():
                        return self.json({"error": "Không tìm thấy tệp"}, 404)
                    return self.send_bytes(file.read_bytes(), "application/octet-stream", filename=name)
                if path.startswith("/api/dataset/"):
                    name = path.removeprefix("/api/dataset/")
                    if name not in ("manifest.json", "documents.jsonl", "queries.jsonl", "qrels.tsv"):
                        raise ValueError("Tệp dữ liệu không hợp lệ")
                    return self.send_bytes((DATA / name).read_bytes(), "application/octet-stream", filename=name)
                static = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
                if path in static:
                    file = ROOT / "web" / static[path]
                    content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
                    return self.send_bytes(file.read_bytes(), content_type + "; charset=utf-8")
                return self.json({"error": "Không tìm thấy đường dẫn"}, 404)
            except ValueError as exc:
                self.json({"error": str(exc)}, 400)
            except Exception:
                import traceback
                traceback.print_exc()
                self.json({"error": "Lỗi xử lý. Xem cửa sổ chạy Python để biết chi tiết."}, 500)

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                if origin and urlparse(origin).netloc != self.headers.get("Host"):
                    return self.json({"error": "Yêu cầu khác nguồn bị từ chối"}, 403)
                if self.headers.get_content_type() != "application/json":
                    return self.json({"error": "Cần gửi JSON"}, 415)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 32768:
                    return self.json({"error": "Kích thước yêu cầu không hợp lệ"}, 400)
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Nội dung phải là một đối tượng JSON")
                path = urlparse(self.path).path
                if path == "/api/search":
                    return self.json(service.search(payload.get("query", ""), payload.get("query_id"), payload.get("top_k", 10)))
                if path == "/api/evaluate":
                    return self.json(service.start_experiment(payload.get("split", "TEST"), payload.get("repeats", 30)), 202)
                return self.json({"error": "Không tìm thấy đường dẫn"}, 404)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self.json({"error": str(exc)}, 400)
            except RuntimeError as exc:
                self.json({"error": str(exc)}, 409)
            except Exception:
                import traceback
                traceback.print_exc()
                self.json({"error": "Lỗi xử lý. Xem cửa sổ chạy Python."}, 500)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
