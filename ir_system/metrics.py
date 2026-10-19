"""Rank-based metrics; every positive Cranfield grade counts as relevant."""
import math

METRICS = (("AP", 0), ("nDCG_binary", 10), ("P", 5), ("P", 10), ("R", 10), ("R", 20))

def evaluate_ranking(ranking, judgments):
    relevant = {doc_id for doc_id, grade in judgments.items() if grade > 0}
    if not relevant:
        raise ValueError("Query has no positive qrels; diagnose and exclude consistently before comparison")
    doc_ids = [row[0] for row in ranking]
    if len(doc_ids) != len(set(doc_ids)):
        raise ValueError("A ranked document must not appear twice")
    hits, ap_sum = 0, 0.0
    for rank, doc_id in enumerate(doc_ids, 1):
        if doc_id in relevant:
            hits += 1
            ap_sum += hits / rank
    values = {("AP", 0): ap_sum / len(relevant)}
    for k in (5, 10, 20):
        h = sum(d in relevant for d in doc_ids[:k])
        if k in (5, 10):
            values[("P", k)] = h / k
        if k in (10, 20):
            values[("R", k)] = h / len(relevant)
    dcg = sum(1 / math.log2(rank + 1) for rank, doc_id in enumerate(doc_ids[:10], 1) if doc_id in relevant)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(10, len(relevant)) + 1))
    values[("nDCG_binary", 10)] = dcg / ideal
    return values

def metric_key(name, cutoff):
    return name if cutoff == 0 else f"{name}@{cutoff}"
