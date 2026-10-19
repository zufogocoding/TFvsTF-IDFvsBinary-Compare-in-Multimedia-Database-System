"""Parse the original Cranfield archive without silently changing identifiers."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import random
import re
import tarfile
import urllib.request

from .config import DATA, DATASET_ID, SEED, sha256_file

ARCHIVE_URL = "https://ir.dcs.gla.ac.uk/resources/test_collections/cran/cran.tar.gz"
ARCHIVE_SHA256 = "8c48a8412e4a7e6e0dd5af99c959f8d75fdf88135602adc1a56aa22770652d64"

def parse_records(text):
    """Cranfield tagged records; normalize whitespace, preserve original IDs."""
    records, current, field = [], None, None
    for line in text.splitlines():
        if line.startswith(".I "):
            if current is not None:
                records.append(current)
            current, field = {"source_id": line[3:].strip()}, None
        elif re.fullmatch(r"\.[A-Z]", line.strip()):
            field = line.strip()[1:]
            if current is not None:
                current.setdefault(field, [])
        elif current is not None and field:
            current[field].append(line.strip())
    if current is not None:
        records.append(current)
    return [{k: (" ".join(v).strip() if isinstance(v, list) else v)
             for k, v in record.items()} for record in records]

def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")

def prepare(archive=None, destination=DATA):
    destination = Path(destination)
    raw = destination / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    archive_target = raw / "cran.tar.gz"
    if archive is not None:
        contents = Path(archive).read_bytes()
    elif archive_target.exists():
        contents = archive_target.read_bytes()
    else:
        with urllib.request.urlopen(ARCHIVE_URL, timeout=60) as response:
            contents = response.read(10 * 1024 * 1024)
    digest = hashlib.sha256(contents).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError("Archive SHA-256 differs from the verified Cranfield version. Do not import silently.")
    archive_target.write_bytes(contents)
    names = ("cran.all.1400", "cran.qry", "cranqrel", "cranqrel.readme")
    # Read only named regular files. Never tar.extractall on a downloaded archive.
    with tarfile.open(archive_target, "r:gz") as t:
        for name in names:
            member = t.getmember(name)
            if not member.isfile():
                raise ValueError("Archive member is not a regular file: " + name)
            data = t.extractfile(member).read()
            (raw / name).write_bytes(data)
    doc_records = parse_records((raw / names[0]).read_text(encoding="utf-8"))
    query_records = parse_records((raw / names[1]).read_text(encoding="utf-8"))
    documents = [{"doc_id": str(int(r["source_id"])), "title": r.get("T", ""),
                  "body": r.get("W", ""), "author": r.get("A", ""), "bib": r.get("B", "")}
                 for r in doc_records]
    # cran.qry .I identifiers have gaps. qrels uses POSITION (1..225), as does ir_datasets.
    queries = [{"query_id": str(i), "source_query_id": r["source_id"], "text": r.get("W", "")}
               for i, r in enumerate(query_records, start=1)]
    shuffled = [q["query_id"] for q in queries]
    random.Random(SEED).shuffle(shuffled)
    dev = set(shuffled[:45])
    for q in queries:
        q["split"] = "DEV" if q["query_id"] in dev else "TEST"
    qrels = []
    for line_number, line in enumerate((raw / names[2]).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        cols = line.split()
        if len(cols) != 3:
            raise ValueError(f"Invalid qrel at line {line_number}")
        qid, did, grade = cols
        qrels.append({"query_id": str(int(qid)), "doc_id": str(int(did)), "raw_grade": int(grade)})
    validate(documents, queries, qrels)
    if (len(documents), len(queries), len(qrels)) != (1400, 225, 1837):
        raise ValueError("The source does not match the expected Cranfield collection")
    write_jsonl(destination / "documents.jsonl", documents)
    write_jsonl(destination / "queries.jsonl", queries)
    (destination / "qrels.tsv").write_text("query_id\tdoc_id\traw_grade\n" + "".join(
        f"{r['query_id']}\t{r['doc_id']}\t{r['raw_grade']}\n" for r in qrels), encoding="utf-8")
    manifest = {
        "dataset_id": DATASET_ID, "name": "Cranfield 1400", "language": "en",
        "source_url": ARCHIVE_URL, "documentation_url": "https://ir-datasets.com/cranfield.html",
        "archive_sha256": digest,
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {"documents": len(documents), "queries": len(queries), "qrels": len(qrels), "dev": 45, "test": 180},
        "grade_counts": dict(Counter(r["raw_grade"] for r in qrels)),
        "query_id_mapping": "1-based source record order, matching qrels and ir_datasets; original .I stored separately",
        "relevance_rule": "raw_grade > 0; unlisted pairs are treated as nonrelevant",
        "ndcg_rule": "binary gains only; does not assume an orientation for positive grade levels",
        "files": {name: sha256_file(destination / name) for name in ("documents.jsonl", "queries.jsonl", "qrels.tsv")},
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest

def validate(documents, queries, qrels):
    docs = [x["doc_id"] for x in documents]
    qs = [x["query_id"] for x in queries]
    if len(set(docs)) != len(docs) or len(set(qs)) != len(qs):
        raise ValueError("Duplicate document or query identifier")
    doc_ids, query_ids, pairs = set(docs), set(qs), set()
    for r in qrels:
        pair = (r["query_id"], r["doc_id"])
        if pair in pairs:
            raise ValueError("Duplicate relevance pair: " + str(pair))
        pairs.add(pair)
        if r["query_id"] not in query_ids or r["doc_id"] not in doc_ids:
            raise ValueError("Qrel refers to a missing query or document")
        if r["raw_grade"] not in (-1, 1, 2, 3, 4):
            raise ValueError("Unknown Cranfield grade")

def load(destination=DATA):
    destination = Path(destination)
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        if sha256_file(destination / name) != digest:
            raise ValueError("Dataset hash mismatch: " + name)
    def read_jsonl(name):
        return [json.loads(line) for line in (destination / name).read_text(encoding="utf-8").splitlines() if line.strip()]
    documents, queries = read_jsonl("documents.jsonl"), read_jsonl("queries.jsonl")
    lines = (destination / "qrels.tsv").read_text(encoding="utf-8").splitlines()[1:]
    qrels = [{"query_id": q, "doc_id": d, "raw_grade": int(g)} for q, d, g in (line.split("\t") for line in lines)]
    validate(documents, queries, qrels)
    actual = (len(documents), len(queries), len(qrels))
    expected = tuple(manifest["counts"][k] for k in ("documents", "queries", "qrels"))
    if actual != expected:
        raise ValueError("Dataset counts do not match manifest")
    return documents, queries, qrels, manifest
