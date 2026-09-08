"""Task 3.1 - capture the trusted Phase 3 DEV baseline (ablation row 0).

Reuses the frozen Phase 1 retrieval architecture completely unmodified
(Task 1.4 BGE encoder, Task 1.5 exact-cosine LanceDB index, Task 1.6
retriever composition) and the frozen Task 1.10/2.6 metric implementations
(never reimplemented here). Evaluates over the frozen Option A DEV/
evaluable-subset selected by `src.eval.phase3_baseline` - the 89 DEV
questions whose gold target document(s) are fully present in the current
1,500-filing Phase 1 index (2026-09-08 user decision - see
project_plan/PHASE3_TRUSTED_BASELINE.md).

Never imports `src.eval.test_access` / `load_test_set()` - this script
reads DEV only (`results/phase_2_4_dev.json`); TEST is never opened here
and no official TEST run budget is consumed.

Usage:
    python -u scripts/run_phase3_trusted_baseline.py --run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.storage import get_storage  # noqa: E402
from src.embeddings.bge import (  # noqa: E402
    MODEL_REPO, MODEL_REVISION, load_model, encode_queries,
    embedding_identity as bge_embedding_identity,
)
from src.artifacts.versioning import embedding_identity_hash, compute_index_identity_hash  # noqa: E402
from src.index.lancedb_index import (  # noqa: E402
    open_database, open_chunk_table, exact_cosine_search,
    index_identity as build_index_identity_dict,
)
from src.retrieval.baseline import _to_results  # noqa: E402
from src.eval.baseline_metrics import evaluate_question, summarize_doc_recall  # noqa: E402
from src.eval.metrics import first_hit_rank, reciprocal_rank, mean_reciprocal_rank, ndcg_at_k, hit_at_k  # noqa: E402
from src.eval.evaluation_schema import EVALUATION_SCHEMA_VERSION, compute_evaluation_schema_hash  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402

CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
CHUNK_SCHEMA_VERSION = 1
EXPECTED_ROW_COUNT = 162357
EXPECTED_EMBEDDING_IDENTITY_HASH = "b39a67c9eb6487fc98f266f23742afd0a30321d98067505802a1e219b27bec84"
EXPECTED_INDEX_IDENTITY_HASH = "ace70ee67d8e98e019d221f2a0215a5b88498a0fc5dcbe73ac7ef1277630b111"

DEV_PATH = Path("results") / "phase_2_4_dev.json"
SPLIT_SUMMARY_PATH = Path("results") / "phase_2_4_split_summary.json"
NORMALIZATION_SUMMARY_PATH = Path("results") / "phase_1_2_normalization_summary.json"
CONFIG_PATH = Path("configs") / "phase_3_1_trusted_baseline.json"
RESULT_PATH = Path("results") / "phase_3_1_trusted_baseline.json"
ABLATION_TABLE_PATH = Path("results") / "phase_3_ablation_table.csv"

PROGRESS_EVERY = 10


def git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _load_json(relative_path: Path) -> dict:
    return json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def load_dev_questions() -> dict:
    return _load_json(DEV_PATH)


def verify_index(storage):
    db_path = storage.index_dir(CHUNK_CONFIG_HASH, MODEL_REPO)
    storage.require_dir(db_path)
    db = open_database(db_path)
    table = open_chunk_table(db)
    row_count = table.count_rows()
    if row_count != EXPECTED_ROW_COUNT:
        raise SystemExit(f"FATAL: index row count {row_count} != expected {EXPECTED_ROW_COUNT}")
    if len(table.list_indices()) != 0:
        raise SystemExit(f"FATAL: expected 0 ANN indexes on Phase 1 index, found {len(table.list_indices())}")
    return db_path, table, row_count


def index_document_ids(table) -> set[str]:
    return set(table.to_pandas()["document_id"].unique().tolist())


def directory_size_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


def build_or_verify_config(*, dev_payload: dict, doc_ids: set[str], git_sha_value: str) -> tuple[dict, str, list[str]]:
    dev_questions = dev_payload["questions"]
    split_summary = _load_json(SPLIT_SUMMARY_PATH)
    norm_summary = _load_json(NORMALIZATION_SUMMARY_PATH)

    scope_ids = p3.select_phase3_dev_scope(dev_questions, doc_ids)
    if not scope_ids:
        raise SystemExit("FATAL: frozen Phase 3 DEV scope is empty - refusing to proceed")

    scope_sha = p3.compute_phase3_dev_scope_sha256(scope_ids)
    ids_sha = p3.compute_question_ids_sha256(scope_ids)

    emb_identity = bge_embedding_identity()
    emb_hash = embedding_identity_hash(emb_identity)
    if emb_hash != EXPECTED_EMBEDDING_IDENTITY_HASH:
        raise SystemExit(f"FATAL: live embedding_identity_hash {emb_hash} != expected {EXPECTED_EMBEDDING_IDENTITY_HASH}")

    idx_identity = build_index_identity_dict(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_identity_hash_value=emb_hash,
    )
    idx_hash = compute_index_identity_hash(idx_identity)
    if idx_hash != EXPECTED_INDEX_IDENTITY_HASH:
        raise SystemExit(f"FATAL: live index_identity_hash {idx_hash} != expected {EXPECTED_INDEX_IDENTITY_HASH}")

    config = p3.build_phase3_config(
        eval_set_version=dev_payload["eval_set_version"],
        source_dataset_sha256=dev_payload["source_dataset_sha256"],
        split_version=dev_payload["split_version"],
        split_assignment_sha256=split_summary["split_assignment_sha256"],
        phase3_dev_scope_sha256=scope_sha,
        question_count=len(scope_ids),
        question_ids_sha256=ids_sha,
        normalizer_version=norm_summary["normalizer_version"],
        normalization_build_sha256=norm_summary["normalization_build_sha256"],
        chunk_config_hash=CHUNK_CONFIG_HASH,
        chunk_schema_version=CHUNK_SCHEMA_VERSION,
        embedding_model=MODEL_REPO,
        embedding_revision=MODEL_REVISION,
        embedding_identity_hash=emb_hash,
        index_identity_hash=idx_hash,
        distance_metric=idx_identity["distance_metric"],
        index_type=idx_identity["index_type"],
        metric_schema_version=EVALUATION_SCHEMA_VERSION,
        evaluation_schema_hash=compute_evaluation_schema_hash(),
        git_sha=git_sha_value,
    )
    config_hash = p3.compute_phase3_config_hash(config)

    config_path = REPO_ROOT / CONFIG_PATH
    if config_path.exists():
        existing = json.loads(config_path.read_text(encoding="utf-8"))
        existing_hash = p3.compute_phase3_config_hash(existing)
        if existing_hash != config_hash:
            raise SystemExit(
                f"FATAL: {config_path} already exists with a different semantic config "
                f"({existing_hash} != {config_hash}) - refusing to silently overwrite. STOP AND ASK."
            )
        config = existing  # identical - reuse the on-disk copy (preserves its original freeze provenance)
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(f"[BASELINE] froze new config: {config_path}")

    return config, config_hash, scope_ids, split_summary


def _p50_p95(values: list[float]) -> dict:
    if not values:
        return {"p50": None, "p95": None}
    s = sorted(values)
    return {"p50": round(s[len(s) // 2], 3), "p95": round(s[int(0.95 * (len(s) - 1))], 3)}


def run(*, top_k: int = p3.RETRIEVAL_TOP_K) -> dict:
    storage = get_storage()
    dev_payload = load_dev_questions()
    dev_questions = dev_payload["questions"]
    db_path, table, row_count = verify_index(storage)
    doc_ids = index_document_ids(table)

    sha = git_sha()
    config, config_hash, scope_ids, split_summary = build_or_verify_config(
        dev_payload=dev_payload, doc_ids=doc_ids, git_sha_value=sha,
    )

    questions_by_id = {q["question_id"]: q for q in dev_questions}
    scoped_questions = [questions_by_id[qid] for qid in scope_ids]
    n = len(scoped_questions)

    print(f"[BASELINE] frozen Phase 3 DEV scope (Option A evaluable subset): {n} questions")
    print(f"[BASELINE] phase3_config_hash={config_hash}")
    print(f"[BASELINE] loading BGE model on cuda ...")

    model = load_model(device="cuda")

    doc10_results = []
    doc_mrr_values: list[float] = []
    doc_ndcg_values: list[float] = []
    hit50_flags: list[bool] = []
    embed_latencies_ms: list[float] = []
    search_latencies_ms: list[float] = []
    total_latencies_ms: list[float] = []

    t_run_start = time.perf_counter()
    for i, q in enumerate(scoped_questions, start=1):
        target_ids = p3.question_target_document_ids(q)
        target_id = target_ids[0]  # frozen scope contains single-target shapes only

        t0 = time.perf_counter()
        qvec = encode_queries(model, [q["question"]], batch_size=1)[0]
        t_embed = time.perf_counter()
        arrow = exact_cosine_search(table, qvec, limit=top_k)
        t_search = time.perf_counter()
        results = _to_results(arrow)
        t1 = time.perf_counter()

        embed_latencies_ms.append((t_embed - t0) * 1000)
        search_latencies_ms.append((t_search - t_embed) * 1000)
        total_latencies_ms.append((t1 - t0) * 1000)

        if len(results) != top_k:
            raise SystemExit(
                f"FATAL: retrieval invariant violated for {q['question_id']}: got {len(results)}, expected {top_k}"
            )

        ranked_document_ids = [r.document_id for r in results]

        qr = evaluate_question(
            question_id=q["question_id"], question=q["question"], category=q["category"],
            target_document_id=target_id, retrieved_results=results[:10], k=10,
        )
        doc10_results.append(qr)

        rank10 = first_hit_rank(ranked_document_ids, {target_id}, k=10)
        doc_mrr_values.append(reciprocal_rank(rank10))
        relevances10 = [1 if did == target_id else 0 for did in ranked_document_ids[:10]]
        ndcg10 = ndcg_at_k(relevances10, num_relevant=1, k=10)
        assert ndcg10 is not None  # num_relevant is always 1 for this frozen single-target scope
        doc_ndcg_values.append(ndcg10)

        rank50 = first_hit_rank(ranked_document_ids, {target_id}, k=top_k)
        hit50_flags.append(hit_at_k(rank50, top_k))

        if i % PROGRESS_EVERY == 0 or i == n:
            elapsed = time.perf_counter() - t_run_start
            rate = i / elapsed if elapsed > 0 else 0.0
            eta = (n - i) / rate if rate > 0 else 0.0
            hits_so_far = sum(1 for r in doc10_results if r.hit)
            avg_ms = sum(total_latencies_ms) / len(total_latencies_ms)
            print(
                f"[BASELINE] {i:4d}/{n} {100 * i / n:5.1f}%  hits@10={hits_so_far}/{i}  "
                f"avg_ms={avg_ms:.1f}  ETA {eta:.1f}s",
                flush=True,
            )
    run_seconds = time.perf_counter() - t_run_start

    aggregate = summarize_doc_recall(doc10_results, k=10)
    doc_mrr = mean_reciprocal_rank(doc_mrr_values)
    doc_ndcg_at_10 = sum(doc_ndcg_values) / len(doc_ndcg_values)
    doc_recall_at_50 = sum(1 for h in hit50_flags if h) / len(hit50_flags)

    embed_stats = _p50_p95(embed_latencies_ms)
    search_stats = _p50_p95(search_latencies_ms)
    total_stats = _p50_p95(total_latencies_ms)

    index_bytes = directory_size_bytes(db_path)

    metrics = {
        "doc_recall@10": aggregate.doc_recall_at_k,
        "doc_recall@50": doc_recall_at_50,
        "doc_mrr": doc_mrr,
        "doc_ndcg@10": doc_ndcg_at_10,
    }

    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION,
        chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": MODEL_REPO, "model_revision": MODEL_REVISION,
            "embedding_dimension": 384, "vector_dtype": "float32", "normalize_embeddings": True,
            "identity_hash": EXPECTED_EMBEDDING_IDENTITY_HASH,
        },
        index_identity_hash=EXPECTED_INDEX_IDENTITY_HASH,
        retrieval_config={"type": p3.RETRIEVAL_TYPE, "top_k": top_k, "distance_metric": "cosine"},
        reranker_config={"enabled": False},
        generation_model=None,
        split="dev",
        eval_set_version=config["eval_set_version"],
        split_version=config["split_version"],
        split_sha256=split_summary["dev_sha256"],
        metrics=metrics,
        evaluation_source="internal_phase2",
        experiment_name="phase3_trusted_baseline",
        run_kind="phase3_trusted_baseline",
        notes=(
            "Task 3.1 row 0: unmodified Phase 1 vector-only architecture, evaluated over the frozen "
            f"DEV/evaluable-subset ({n} questions, Option A - see project_plan/PHASE3_TRUSTED_BASELINE.md). "
            "Generation disabled."
        ),
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[BASELINE] Task 2.11 run record written: {run_record_path}")

    summary = p3.build_result_summary(
        run_id=run_record.run_id, git_sha=sha, phase3_config=config, phase3_config_hash=config_hash,
        question_count=n, metrics=metrics,
        stage_timings_ms={
            "query_embedding": embed_stats, "vector_search": search_stats, "retrieval_total": total_stats,
            "run_seconds": round(run_seconds, 3),
        },
        question_ids=scope_ids,
    )

    result_path = REPO_ROOT / RESULT_PATH
    if result_path.exists():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing.get("phase3_config_hash") == config_hash and existing.get("run_id") != run_record.run_id:
            print(
                f"[BASELINE] NOTE: {result_path} already holds a result for this exact config "
                f"(different run_id) - overwriting with this run's fresh result."
            )
    result_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    row0 = p3.build_row0(
        run_id=run_record.run_id, git_sha=sha, phase3_config_hash=config_hash,
        eval_scope_sha256=config["phase3_dev_scope_sha256"], question_count=n,
        corpus_document_count=len(doc_ids), chunk_count=row_count, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model=MODEL_REPO, embedding_revision=MODEL_REVISION,
        embedding_identity=EXPECTED_EMBEDDING_IDENTITY_HASH, index_identity=EXPECTED_INDEX_IDENTITY_HASH,
        candidate_k=top_k, doc_recall_at_10=aggregate.doc_recall_at_k, doc_recall_at_50=doc_recall_at_50,
        doc_mrr=doc_mrr, doc_ndcg_at_10=doc_ndcg_at_10,
        retrieval_latency_p50_ms=total_stats["p50"], retrieval_latency_p95_ms=total_stats["p95"],
        query_embedding_latency_p50_ms=embed_stats["p50"], search_latency_p50_ms=search_stats["p50"],
        index_size_bytes=index_bytes,
        notes="Pre-optimization Phase 1 architecture; DEV/evaluable-subset (Option A, 89q); generation disabled.",
    )
    existing_rows = p3.load_ablation_table(REPO_ROOT / ABLATION_TABLE_PATH)
    updated_rows = p3.upsert_row(existing_rows, row0)
    p3.write_ablation_table(REPO_ROOT / ABLATION_TABLE_PATH, updated_rows)
    print(f"[BASELINE] ablation row 0 frozen: {REPO_ROOT / ABLATION_TABLE_PATH}")

    print()
    print("PHASE 3 - TASK 3.1 TRUSTED BASELINE")
    print("===================================")
    print()
    print("Evaluation:")
    print("  source:                    internal Phase 2 evaluation set")
    print("  split:                     DEV")
    print("  scope:                     DEV/evaluable-subset (Option A)")
    print(f"  questions evaluated:       {n}")
    print(f"  scope_sha256:              {config['phase3_dev_scope_sha256']}")
    print()
    print("Architecture:")
    print("  chunking:                  fixed 512, zero overlap")
    print("  embedding:                 BAAI/bge-small-en-v1.5")
    print("  retrieval:                 vector-only exact cosine")
    print("  BM25:                      NO")
    print("  reranker:                  NO")
    print("  CRAG:                      NO")
    print("  router:                    NO")
    print("  metadata prefilter:        NO / new features")
    print("  generation formal run:     NO")
    print()
    print("Metrics:")
    print(f"  doc_recall@10:             {aggregate.doc_recall_at_k:.6f}")
    print(f"  doc_recall@50:             {doc_recall_at_50:.6f}")
    print(f"  doc_mrr:                   {doc_mrr:.6f}")
    print(f"  doc_ndcg@10:               {doc_ndcg_at_10:.6f}")
    print("  chunk_recall@10:           N/A - no internal chunk gold")
    print("  chunk_mrr:                 N/A - no internal chunk gold")
    print("  precision@5:               N/A - not yet frozen/implemented")
    print("  refusal metric:            N/A - generation disabled")
    print()
    print("Latency:")
    print(f"  retrieval p50:             {total_stats['p50']} ms")
    print(f"  retrieval p95:             {total_stats['p95']} ms")
    print(f"  query embedding p50:       {embed_stats['p50']} ms")
    print(f"  vector search p50:         {search_stats['p50']} ms")
    print()
    print("Ablation table:")
    print("  row 0:                     FROZEN")
    print()
    print("Run provenance:")
    print(f"  run_id:                    {run_record.run_id}")
    print(f"  git_sha:                   {sha}")
    print(f"  phase3_config_hash:        {config_hash}")
    print()
    print("Protected TEST:")
    print("  opened:                    NO")
    print("  official runs used:        0/3")
    print()
    print("FinanceBench:")
    print("  rerun:                     NO")
    print("  historical Task 2.12 result unchanged")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.1 - capture the trusted Phase 3 DEV baseline.")
    parser.add_argument("--run", action="store_true", help="execute the formal baseline run")
    args = parser.parse_args()
    if not args.run:
        parser.print_help()
        return 1
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
