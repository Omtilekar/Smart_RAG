"""Task 1.10 - run the frozen doc_recall@10 baseline metric over the real
Task 1.9 200-question smoke set, using the real Task 1.6 retriever at
k=10.

question -> Task 1.6 BaselineRetriever.retrieve(question, k=10)
         -> exactly 10 ranked chunk results
         -> hit if any result.document_id == target_document_id
         -> hit_count / 200 -> doc_recall@10

No generation, no citation check, no BM25/reranking/filtering - retrieval
evaluation only. Does not modify the Task 1.6 retriever, the Task 1.5
index, or the Task 1.9 dataset - read-only throughout.

Phase 1 smoke baseline. NOT the final benchmark. NOT a trustworthy
research result - see project_plan/PHASE1_BASELINE_METRICS.md.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.storage import get_storage  # noqa: E402
from src.embeddings.bge import load_model  # noqa: E402
from src.index.lancedb_index import open_database, open_chunk_table  # noqa: E402
from src.retrieval.baseline import BaselineRetriever  # noqa: E402
from src.eval.baseline_metrics import (  # noqa: E402
    evaluate_question,
    summarize_doc_recall,
    canonical_json,
    compute_config_hash,
    compute_result_hash,
)

SCHEMA_VERSION = "1.0"
METRIC_NAME = "doc_recall@10"
K = 10

CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
MODEL_REPO = "BAAI/bge-small-en-v1.5"
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
EXPECTED_ROW_COUNT = 162357
EXPECTED_QUESTION_COUNT = 200
EXPECTED_QUESTIONS_PER_CATEGORY = 40
EXPECTED_SMOKE_EVAL_SHA256 = "0b2c25dcbde141cafb5694ae748c5131d556d543195158aa3794dec325657a27"
CATEGORY_ORDER = ("business", "risk_factors", "mdna", "market_risk", "financial_statements")

DATASET_RELATIVE_PATH = Path("results") / "phase_1_9_smoke_evaluation.json"
CONFIG_RELATIVE_PATH = Path("configs") / "phase_1_10_baseline_metric.json"
RESULT_RELATIVE_PATH = Path("results") / "phase_1_10_baseline_metric.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def load_and_verify_dataset(storage) -> list[dict]:
    path = storage.repo_root / DATASET_RELATIVE_PATH
    storage.require_file(path)
    dataset = json.loads(path.read_text(encoding="utf-8"))
    questions = dataset["questions"]

    if len(questions) != EXPECTED_QUESTION_COUNT:
        raise SystemExit(f"BLOCKED - expected {EXPECTED_QUESTION_COUNT} questions, found {len(questions)}")
    if len({q["question_id"] for q in questions}) != EXPECTED_QUESTION_COUNT:
        raise SystemExit("BLOCKED - duplicate question_id in Task 1.9 dataset")
    if len({q["target_document_id"] for q in questions}) != EXPECTED_QUESTION_COUNT:
        raise SystemExit("BLOCKED - duplicate target_document_id in Task 1.9 dataset")
    if not all(q["label_granularity"] == "document" for q in questions):
        raise SystemExit("BLOCKED - not all questions are document-level")
    if not all(q["retrieval_metric"] == "doc_recall@10" for q in questions):
        raise SystemExit("BLOCKED - not all questions specify doc_recall@10")

    counts: dict[str, int] = {}
    for q in questions:
        counts[q["category"]] = counts.get(q["category"], 0) + 1
    for category in CATEGORY_ORDER:
        if counts.get(category) != EXPECTED_QUESTIONS_PER_CATEGORY:
            raise SystemExit(
                f"BLOCKED - category {category!r} has {counts.get(category)} questions, "
                f"expected {EXPECTED_QUESTIONS_PER_CATEGORY}"
            )

    recomputed = canonical_json_sha256(questions)
    if recomputed != EXPECTED_SMOKE_EVAL_SHA256:
        raise SystemExit(
            f"BLOCKED - Task 1.9 dataset changed unexpectedly: recomputed smoke_eval_sha256="
            f"{recomputed} != expected {EXPECTED_SMOKE_EVAL_SHA256}"
        )
    if dataset.get("smoke_eval_sha256") != EXPECTED_SMOKE_EVAL_SHA256:
        raise SystemExit("BLOCKED - Task 1.9 dataset's own stored smoke_eval_sha256 does not match expected")

    return questions


def canonical_json_sha256(questions: list[dict]) -> str:
    import hashlib
    return hashlib.sha256(canonical_json(questions)).hexdigest()


def verify_index(storage):
    db_path = storage.index_dir(CHUNK_CONFIG_HASH, MODEL_REPO)
    storage.require_dir(db_path)
    db = open_database(db_path)
    names = db.list_tables().tables
    if names != ["chunks"]:
        raise SystemExit(f"FATAL: expected table ['chunks'], found {names}")
    table = open_chunk_table(db)
    if table.count_rows() != EXPECTED_ROW_COUNT:
        raise SystemExit(f"FATAL: table has {table.count_rows()} rows, expected {EXPECTED_ROW_COUNT}")
    if len(table.list_indices()) != 0:
        raise SystemExit(f"FATAL: expected 0 ANN indexes, found {len(table.list_indices())}")
    return db_path, table


def build_stable_config() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "metric_name": METRIC_NAME,
        "k": K,
        "dataset_path": str(DATASET_RELATIVE_PATH.as_posix()),
        "expected_smoke_eval_sha256": EXPECTED_SMOKE_EVAL_SHA256,
        "retriever": "baseline_vector",
        "embedding_model": MODEL_REPO,
        "embedding_revision": MODEL_REVISION,
        "chunk_config_hash": CHUNK_CONFIG_HASH,
        "index_table": "chunks",
        "distance_metric": "cosine",
        "search_mode": "exact",
        "document_hit_definition": (
            "hit(q) = 1 if any of the first k retrieved CHUNK results has "
            "result.document_id == q.target_document_id (exact string equality, "
            "no dedup before the cutoff, no CIK/company/year matching), else 0"
        ),
    }


def main() -> int:
    storage = get_storage()
    questions = load_and_verify_dataset(storage)
    db_path, table = verify_index(storage)

    model = load_model(device="cuda")
    retriever = BaselineRetriever(model=model, table=table)

    stable_config = build_stable_config()
    metric_run_config_hash = compute_config_hash(stable_config)

    question_results = []
    latencies_ms = []
    run_start = time.perf_counter()
    for q in questions:
        t0 = time.perf_counter()
        results = retriever.retrieve(q["question"], k=K)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000)

        if len(results) != K:
            raise SystemExit(
                f"FATAL: retrieval invariant violated for {q['question_id']}: "
                f"got {len(results)} results, expected exactly {K}"
            )

        qr = evaluate_question(
            question_id=q["question_id"], question=q["question"], category=q["category"],
            target_document_id=q["target_document_id"], retrieved_results=results, k=K,
        )
        question_results.append(qr)
    run_seconds = time.perf_counter() - run_start

    aggregate = summarize_doc_recall(question_results, k=K)
    if not (0 <= aggregate.hit_count <= EXPECTED_QUESTION_COUNT):
        raise SystemExit(f"FATAL: hit_count out of range: {aggregate.hit_count}")
    if not (0.0 <= aggregate.doc_recall_at_k <= 1.0):
        raise SystemExit(f"FATAL: doc_recall@10 out of range: {aggregate.doc_recall_at_k}")

    metric_result_sha256 = compute_result_hash(question_results)

    def p50_p95(values):
        s = sorted(values)
        return {"p50": round(statistics.median(s), 3), "p95": round(s[int(0.95 * (len(s) - 1))], 3)}

    category_results_json = {
        cat: {
            "question_count": cr.question_count,
            "hit_count": cr.hit_count,
            "doc_recall_at_10": cr.doc_recall_at_k,
        }
        for cat, cr in aggregate.category_results.items()
    }
    first_hit_rank_counts_json = {str(rank): count for rank, count in aggregate.first_hit_rank_counts.items()}

    questions_json = [
        {
            "question_id": qr.question_id,
            "question": qr.question,
            "category": qr.category,
            "target_document_id": qr.target_document_id,
            "k": qr.k,
            "hit": qr.hit,
            "first_hit_rank": qr.first_hit_rank,
            "retrieved_chunk_ids": qr.retrieved_chunk_ids,
            "retrieved_document_ids": qr.retrieved_document_ids,
            "retrieved_scores": qr.retrieved_scores,
            "retrieved_distances": qr.retrieved_distances,
        }
        for qr in question_results
    ]

    result = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "metric_name": METRIC_NAME,
        "k": K,
        "question_count": aggregate.question_count,
        "hit_count": aggregate.hit_count,
        "doc_recall_at_10": aggregate.doc_recall_at_k,
        "category_results": category_results_json,
        "first_hit_rank_counts": first_hit_rank_counts_json,
        "dataset_path": str(DATASET_RELATIVE_PATH.as_posix()),
        "smoke_eval_sha256": EXPECTED_SMOKE_EVAL_SHA256,
        "metric_run_config_hash": metric_run_config_hash,
        "metric_result_sha256": metric_result_sha256,
        "retriever_provenance": {
            "embedding_model": MODEL_REPO,
            "embedding_revision": MODEL_REVISION,
            "chunk_config_hash": CHUNK_CONFIG_HASH,
            "index_relative_path": str(
                (Path("artifacts") / "indexes" / CHUNK_CONFIG_HASH / MODEL_REPO.replace("/", "--")).as_posix()
            ),
            "table_name": "chunks",
            "search_mode": "exact",
            "distance_metric": "cosine",
        },
        "runtime": {
            "label": "Phase 1 evaluation-run diagnostic - NOT a production benchmark",
            "run_seconds": round(run_seconds, 3),
            "retrieval_latency_ms": p50_p95(latencies_ms),
        },
        "questions": questions_json,
    }

    result_path = storage.repo_root / RESULT_RELATIVE_PATH
    if result_path.exists():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing.get("metric_result_sha256") != metric_result_sha256:
            raise SystemExit(
                f"FATAL: {result_path} already exists with a different metric_result_sha256 "
                f"({existing.get('metric_result_sha256')} != {metric_result_sha256}) - refusing to "
                f"silently overwrite a conflicting Task 1.10 result. STOP AND ASK before proceeding."
            )
    storage.ensure_dir(result_path.parent)
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    config_path = storage.repo_root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(stable_config, indent=2) + "\n", encoding="utf-8")

    print(f"question_count: {aggregate.question_count}")
    print(f"hit_count: {aggregate.hit_count}")
    print(f"doc_recall@10: {aggregate.doc_recall_at_k:.6f}")
    print(f"questions={aggregate.question_count} hits={aggregate.hit_count} doc_recall@10={aggregate.doc_recall_at_k:.6f}")
    print("Category results:")
    for cat in CATEGORY_ORDER:
        cr = category_results_json[cat]
        print(f"  {cat}: questions={cr['question_count']} hits={cr['hit_count']} doc_recall@10={cr['doc_recall_at_10']:.6f}")
    print(f"metric_run_config_hash: {metric_run_config_hash}")
    print(f"metric_result_sha256: {metric_result_sha256}")
    print(f"Result written to: {result_path}")
    print(f"Config written to: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
