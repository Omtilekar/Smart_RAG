"""Task 3.4 - LanceDB-native BM25/FTS sparse-only retrieval baseline
against the frozen Task 3.2 chunking winner (fixed 256-token windows,
zero overlap; chunk_config_hash=ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06)
and evaluated over the exact frozen Task 3.1 89-question DEV/evaluable
subset used by Tasks 3.1-3.3.

Sparse-only: no dense embedding is loaded or computed here. The frozen
Task 3.3 Qwen dense winner is loaded read-only, from its already-written
`results/phase3_3/qwen3_embedding.json`, purely for Stage 8's paired
comparison and for provenance in the Task 3.4 run record - never rebuilt,
never used to score a sparse query. Never imports src.eval.test_access -
Task 3.4 evaluation is DEV-only.

Metric note: Task 1.10's `evaluate_question()`/`summarize_doc_recall()`
require exactly `k` ranked results (correct for dense exact-cosine search,
which always returns k rows). LanceDB's native FTS only returns rows with
a nonzero match score, so a sparse query can legitimately return fewer
than `candidate_k` rows. This script therefore computes doc_recall@10/
doc_recall@50/doc_mrr/doc_ndcg@10 directly from Task 2.6's granularity-
agnostic `first_hit_rank()`/`hit_at_k()`/`reciprocal_rank()`/`ndcg_at_k()`
plus Task 3.1's `document_relevances_at_k()` (the same functions Task 1.10
docstring guarantees reproduce identical semantics, and the same
functions Task 3.3 already uses for its doc_recall@50 diagnostic) rather
than through the fixed-length wrapper - never a new metric implementation.

Usage:
    python -u scripts/run_phase3_bm25_fts_baseline.py --plan
    python -u scripts/run_phase3_bm25_fts_baseline.py --build
    python -u scripts/run_phase3_bm25_fts_baseline.py --evaluate
    python -u scripts/run_phase3_bm25_fts_baseline.py --compare
    python -u scripts/run_phase3_bm25_fts_baseline.py --run
    python -u scripts/run_phase3_bm25_fts_baseline.py --status
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

import lancedb  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.artifacts.versioning import semantic_hash  # noqa: E402
from src.index import lancedb_fts as fts  # noqa: E402
from src.retrieval.sparse import SparseRetriever  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_ablation as p3a  # noqa: E402
from src.eval import phase3_sparse as p3s  # noqa: E402
from src.eval.metrics import first_hit_rank, reciprocal_rank, mean_reciprocal_rank, ndcg_at_k, hit_at_k  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402

from scripts.run_phase3_chunking_ablation import _p50_p95, directory_size_bytes, bootstrap_vs_reference  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_4_bm25_fts_baseline.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
TASK32_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"
TASK33_QWEN_RESULT_PATH = REPO_ROOT / "results" / "phase3_3" / "qwen3_embedding.json"
SPLIT_SUMMARY_PATH = REPO_ROOT / "results" / "phase_2_4_split_summary.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_4"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_4_bm25_fts_baseline.json"

ROW_ID = "bm25_fts"
CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
CHUNK_SCHEMA_VERSION = 1
EXPECTED_CHUNK_COUNT = 323971

CANDIDATE_K = 50
DOC_RECALL_K = 10
EVAL_PROGRESS_EVERY = 10


def git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_experiment_config() -> tuple[dict, str]:
    config = _load_json(CONFIG_PATH)
    return config, semantic_hash(config)


def load_frozen_scope() -> tuple[list[str], dict]:
    baseline = _load_json(BASELINE_RESULT_PATH)
    question_ids = sorted(baseline["question_ids"])
    ids_hash = p3.compute_question_ids_sha256(question_ids)
    config, _ = load_experiment_config()
    if ids_hash != config["question_ids_sha256"]:
        raise SystemExit(
            f"FATAL: frozen 89-question scope does not reproduce - recomputed {ids_hash} != "
            f"config's frozen {config['question_ids_sha256']}. STOP."
        )
    if baseline["question_count"] != config["question_count"]:
        raise SystemExit("FATAL: question_count mismatch between baseline result and frozen config.")
    return question_ids, baseline


def load_dev_questions() -> dict:
    return _load_json(REPO_ROOT / "results" / "phase_2_4_dev.json")


def verify_frozen_chunks(storage) -> "pq.Table":
    task32 = _load_json(TASK32_RESULT_PATH)
    winner_hash = task32["final_winner"]["chunk_config_hash"]
    if winner_hash != CHUNK_CONFIG_HASH:
        raise SystemExit(
            f"FATAL: Task 3.2 final_winner chunk_config_hash {winner_hash} != expected {CHUNK_CONFIG_HASH}. STOP."
        )
    path = storage.chunks_dir(CHUNK_CONFIG_HASH) / "chunks.parquet"
    if not path.is_file():
        raise SystemExit(f"FATAL: frozen Task 3.2 chunk artifact missing at {path}")
    table = pq.read_table(path)
    if table.num_rows != EXPECTED_CHUNK_COUNT:
        raise SystemExit(f"FATAL: chunk artifact has {table.num_rows} rows, expected {EXPECTED_CHUNK_COUNT}")
    if "vector" in table.schema.names:
        raise SystemExit("FATAL: frozen chunk artifact unexpectedly carries a 'vector' column - wrong source table.")
    return table


def verify_frozen_dense_winner() -> dict:
    task33 = _load_json(REPO_ROOT / "results" / "phase_3_3_embedding_model_benchmark.json")
    if task33["final_winner_candidate_id"] != "qwen3_embedding":
        raise SystemExit(
            f"FATAL: Task 3.3 final_winner_candidate_id={task33['final_winner_candidate_id']!r} != "
            f"expected 'qwen3_embedding'. Dense winner identity changed - STOP."
        )
    if not TASK33_QWEN_RESULT_PATH.is_file():
        raise SystemExit(f"FATAL: frozen Task 3.3 dense winner result missing at {TASK33_QWEN_RESULT_PATH}")
    qwen = _load_json(TASK33_QWEN_RESULT_PATH)
    config, _ = load_experiment_config()
    ref = config["dense_reference"]
    if qwen["repository"] != ref["model_repository"] or qwen["revision"] != ref["model_revision"] \
            or qwen["dimension"] != ref["embedding_dimension"]:
        raise SystemExit("FATAL: live Task 3.3 qwen3_embedding identity != frozen Task 3.4 config's dense_reference. STOP.")
    return qwen


# --------------------------------------------------------------- Stage 4: build FTS index

def build_fts_artifact(storage, chunk_table) -> dict:
    n = chunk_table.num_rows
    db_path = storage.index_dir(CHUNK_CONFIG_HASH, fts.SPARSE_ARTIFACT_KEY)
    print(f"[FTS] preparing table... ({db_path})")
    print(f"[FTS] rows={n}")

    reused_table = False
    if db_path.exists():
        db = fts.open_database(db_path)
        names = db.list_tables().tables
        if names == [fts.TABLE_NAME]:
            table = fts.open_sparse_table(db)
            if table.count_rows() == n and fts.FTS_INDEX_NAME in fts.existing_fts_index_names(table):
                print(f"[FTS] existing artifact found ({n} rows, index present) - reusing")
                reused_table = True
            elif table.count_rows() != n:
                raise SystemExit(f"FATAL: existing sparse table at {db_path} has {table.count_rows()} rows, expected {n}")
        elif names:
            raise SystemExit(f"FATAL: {db_path} contains unexpected tables {names}")
        else:
            table = fts.create_sparse_table(db, chunk_table)
    else:
        storage.ensure_dir(db_path)
        db = fts.open_database(db_path)
        table = fts.create_sparse_table(db, chunk_table)

    build_seconds = None
    if not reused_table:
        print("[FTS] creating native full-text index on text...")
        t0 = time.perf_counter()
        fts.build_fts_index(table, replace=False)
        build_seconds = time.perf_counter() - t0

    fts.validate_sparse_table(table, expected_row_count=n)
    index_size = directory_size_bytes(db_path)
    if build_seconds is not None:
        print(f"[FTS] build complete elapsed={build_seconds:.2f}s size={index_size:,} bytes")
    else:
        print(f"[FTS] validated existing index, size={index_size:,} bytes")

    # persistence-after-reopen check (Stage 4 build validation)
    db2 = fts.open_database(db_path)
    table2 = fts.open_sparse_table(db2)
    fts.validate_sparse_table(table2, expected_row_count=n)
    print("[FTS] reopened in a fresh connection - index persists, validated again.")

    return {
        "row_count": n, "fts_build_seconds": round(build_seconds, 3) if build_seconds is not None else None,
        "reused": reused_table, "index_size_bytes": index_size, "db_path": str(db_path),
    }


# --------------------------------------------------------------- Stage 6: robustness smoke

SMOKE_QUERIES: tuple[str, ...] = (
    "revenue increased significantly",
    "REVENUE Increased Significantly",
    "net income, cash flow, and total assets",
    "growth of 10.5% year-over-year",
    "$1.2 billion in fiscal 2020",
    "risk factors (cybersecurity)",
    "10-K/A amendments",
    "Item 1A Risk Factors",
    "R&D expenses",
    "café naïve — unicode dash",
)


def run_smoke_tests(retriever: SparseRetriever) -> None:
    print("[SMOKE] query robustness (real sparse artifact, not gating - correctness only)")
    for q in SMOKE_QUERIES:
        results = retriever.retrieve(q, k=5)
        print(f"[SMOKE] ok  {len(results):2d} hits  {q!r}")

    for label, fn in (
        ("empty string", lambda: retriever.retrieve("", k=5)),
        ("whitespace only", lambda: retriever.retrieve("   ", k=5)),
        ("non-string question", lambda: retriever.retrieve(12345, k=5)),
        ("k=0", lambda: retriever.retrieve("revenue", k=0)),
        ("negative k", lambda: retriever.retrieve("revenue", k=-1)),
        ("boolean k", lambda: retriever.retrieve("revenue", k=True)),
    ):
        try:
            fn()
            print(f"[SMOKE] FAIL  {label!r} did not raise")
            raise SystemExit(f"FATAL: malformed input {label!r} was not rejected.")
        except (TypeError, ValueError) as exc:
            print(f"[SMOKE] ok  {label!r} rejected: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------- Stage 7: formal evaluation

def evaluate_sparse(retriever: SparseRetriever, scoped_questions: list[dict], frozen_scope_ids: list[str],
                     diagnostics_path: Path) -> dict:
    p3a.assert_frozen_scope([q["question_id"] for q in scoped_questions], frozen_scope_ids)

    n = len(scoped_questions)
    per_question: dict[str, dict] = {}
    rr10_values, ndcg10_values = [], []
    hit10_flags, hit50_flags = [], []
    search_ms, total_ms = [], []
    underfilled: list[str] = []

    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    with open(diagnostics_path, "w", encoding="utf-8") as diag_f:
        for i, q in enumerate(scoped_questions, start=1):
            target_id = p3.question_target_document_ids(q)[0]

            s0 = time.perf_counter()
            results = retriever.retrieve(q["question"], k=CANDIDATE_K)
            s1 = time.perf_counter()

            if len(results) < CANDIDATE_K:
                underfilled.append(q["question_id"])

            ranked_chunk_ids = [r.chunk_id for r in results]
            ranked_document_ids = [r.document_id for r in results]
            native_scores = [r.sparse_score for r in results]

            rank10 = first_hit_rank(ranked_document_ids, {target_id}, k=DOC_RECALL_K)
            hit10 = hit_at_k(rank10, DOC_RECALL_K)
            rr10 = reciprocal_rank(rank10)
            relevances10 = p3.document_relevances_at_k(ranked_document_ids, target_id, k=DOC_RECALL_K)
            ndcg10 = ndcg_at_k(relevances10, num_relevant=1, k=DOC_RECALL_K)

            rank50 = first_hit_rank(ranked_document_ids, {target_id}, k=CANDIDATE_K)
            hit50 = hit_at_k(rank50, CANDIDATE_K)

            total_ms.append((s1 - s0) * 1000)
            search_ms.append((s1 - s0) * 1000)

            hit10_flags.append(hit10)
            hit50_flags.append(hit50)
            rr10_values.append(rr10)
            ndcg10_values.append(ndcg10)

            per_question[q["question_id"]] = {
                "target_document_id": target_id, "hit10": hit10, "rank10": rank10,
                "rr10": rr10, "ndcg10": ndcg10, "hit50": hit50, "rank50": rank50,
            }

            diag_f.write(json.dumps({
                "question_id": q["question_id"], "gold_document_ids": [target_id],
                "ranked_chunk_ids": ranked_chunk_ids, "ranked_document_ids": ranked_document_ids,
                "native_sparse_scores": native_scores,
                "first_gold_hit_rank": rank50, "hit_at_10": hit10, "hit_at_50": hit50,
                "reciprocal_rank": rr10, "ndcg_at_10": ndcg10,
                "fts_search_ms": (s1 - s0) * 1000, "total_retrieval_ms": (s1 - s0) * 1000,
            }) + "\n")

            if i % EVAL_PROGRESS_EVERY == 0 or i == n:
                elapsed = time.perf_counter() - t0
                p50 = _p50_p95(total_ms)["p50"] or 0.0
                print(f"[SPARSE EVAL]  {i}/{n}  {100*i/n:5.1f}%  hits@10={sum(hit10_flags)}  "
                      f"hits@50={sum(hit50_flags)}  p50_ms={p50:.1f}", flush=True)
    run_seconds = time.perf_counter() - t0

    hits10 = sum(1 for h in hit10_flags if h)
    hits50 = sum(1 for h in hit50_flags if h)

    if underfilled:
        print(f"[SPARSE EVAL] NOTE: {len(underfilled)}/{n} question(s) returned fewer than "
              f"{CANDIDATE_K} sparse hits (native FTS only returns nonzero-score matches): {underfilled}")

    return {
        "question_count": n,
        "metrics": {
            "doc_recall_at_10": hits10 / n, "doc_recall_at_10_hits": hits10,
            "doc_recall_at_50": hits50 / n, "doc_recall_at_50_hits": hits50,
            "doc_mrr": mean_reciprocal_rank(rr10_values), "doc_ndcg_at_10": sum(ndcg10_values) / len(ndcg10_values),
        },
        "per_question": per_question,
        "underfilled_question_ids": underfilled,
        "latency_ms": {"fts_search": _p50_p95(search_ms), "retrieval_total": _p50_p95(total_ms)},
        "run_seconds": round(run_seconds, 3),
        "diagnostics_path": str(diagnostics_path),
    }


# --------------------------------------------------------------- persistence

def load_candidate_result() -> dict | None:
    path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    return _load_json(path) if path.is_file() else None


def save_candidate_result(payload: dict) -> None:
    _write_json(CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json", payload)


# --------------------------------------------------------------- CLI actions

def cmd_plan() -> int:
    config, config_hash = load_experiment_config()
    print("[STAGE 3/10] Frozen Task 3.4 sparse retrieval contract")
    print(f"phase3_4_config_hash: {config_hash}")
    print(json.dumps(config, indent=2))
    return 0


def cmd_status() -> int:
    print("Task 3.4 status (read-only)")
    result = load_candidate_result()
    if result is None:
        print(f"  {ROW_ID}: not built/evaluated")
    else:
        m = result.get("metrics")
        if m:
            print(f"  {ROW_ID}: recall@10={m['doc_recall_at_10']:.4f} recall@50={m['doc_recall_at_50']:.4f} "
                  f"mrr={m['doc_mrr']:.4f} ndcg@10={m['doc_ndcg_at_10']:.4f}")
        else:
            print(f"  {ROW_ID}: built, not yet evaluated")
    return 0


def cmd_build() -> int:
    print("[STAGE 1/10] Task 3.4 preflight")
    frozen_scope_ids, baseline = load_frozen_scope()
    p3a.assert_dev_split("dev")
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    verify_frozen_dense_winner()
    print(f"Frozen scope verified: {len(frozen_scope_ids)} questions. "
          f"Frozen 256/0/fixed chunk artifact verified: {chunk_table.num_rows} chunks. "
          f"lancedb version: {lancedb.__version__}")

    config, config_hash = load_experiment_config()
    if config["lancedb_version"] != lancedb.__version__:
        raise SystemExit(
            f"FATAL: installed lancedb version {lancedb.__version__} != frozen config "
            f"{config['lancedb_version']}. Re-audit Stage 2 before proceeding. STOP."
        )

    print("[STAGE 4/10] Build LanceDB FTS index")
    build_stats = build_fts_artifact(storage, chunk_table)

    existing = load_candidate_result() or {}
    existing["build_stats"] = build_stats
    existing["chunk_config_hash"] = CHUNK_CONFIG_HASH
    save_candidate_result(existing)
    print(f"Build stats: {build_stats}")
    return 0


def cmd_evaluate() -> int:
    result = load_candidate_result()
    if result is None or "build_stats" not in result:
        raise SystemExit("Not built yet - run --build first.")

    frozen_scope_ids, baseline = load_frozen_scope()
    dev_payload = load_dev_questions()
    questions_by_id = {q["question_id"]: q for q in dev_payload["questions"]}
    scoped_questions = [questions_by_id[qid] for qid in frozen_scope_ids]

    storage = get_storage()
    db_path = storage.index_dir(CHUNK_CONFIG_HASH, fts.SPARSE_ARTIFACT_KEY)
    db = fts.open_database(db_path)
    table = fts.open_sparse_table(db)
    retriever = SparseRetriever(table)

    print("[STAGE 5/10] Sparse retriever boundary ready (src/retrieval/sparse.py)")
    print("[STAGE 6/10] Sparse-query robustness smoke")
    run_smoke_tests(retriever)

    print("[STAGE 7/10] Evaluate sparse-only baseline")
    diagnostics_path = storage.eval_dir("phase3_4_bm25_fts_baseline") / "query_diagnostics.jsonl"
    eval_result = evaluate_sparse(retriever, scoped_questions, frozen_scope_ids, diagnostics_path)

    qwen = verify_frozen_dense_winner()
    config, config_hash = load_experiment_config()
    split_summary = _load_json(SPLIT_SUMMARY_PATH)
    sha = git_sha()

    identity = fts.sparse_index_identity(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        lancedb_version=lancedb.__version__,
    )
    identity_hash = fts.sparse_index_identity_hash(identity)

    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": qwen["repository"], "model_revision": qwen["revision"],
            "embedding_dimension": qwen["dimension"], "vector_dtype": "float32",
            "normalize_embeddings": qwen["normalize_embeddings"], "identity_hash": qwen["embedding_identity_hash"],
        },
        index_identity_hash=identity_hash,
        retrieval_config={"type": "sparse_lancedb_fts", "dense_used_for_scoring": False,
                           "top_k": CANDIDATE_K, "sparse_backend": p3s.SPARSE_BACKEND},
        reranker_config={"enabled": False}, generation_model=None, split="dev",
        eval_set_version="phase2-v1", split_version="phase2-split-v1", split_sha256=split_summary["dev_sha256"],
        metrics=eval_result["metrics"], evaluation_source="internal_phase2",
        experiment_name="phase3_4_bm25_fts_sparse_baseline", run_kind="phase3_bm25_fts_sparse_baseline",
        notes=f"Task 3.4 LanceDB-native FTS sparse-only baseline over frozen 256/0/fixed chunks "
              f"({CHUNK_CONFIG_HASH[:12]}...). Dense Qwen identity recorded for provenance only "
              f"(dense_used_for_scoring=false).",
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[SPARSE EVAL] Task 2.11 run record written: {run_record_path}")

    existing = load_candidate_result()
    existing.update({
        "row_id": ROW_ID, "chunk_config_hash": CHUNK_CONFIG_HASH,
        "sparse_index_identity": identity, "sparse_index_identity_hash": identity_hash,
        "run_id": run_record.run_id, "git_sha": sha,
        "config_hash": config_hash,
        **eval_result,
    })
    save_candidate_result(existing)
    print(f"[SPARSE EVAL] doc_recall@10={eval_result['metrics']['doc_recall_at_10']:.4f} "
          f"doc_recall@50={eval_result['metrics']['doc_recall_at_50']:.4f} "
          f"doc_mrr={eval_result['metrics']['doc_mrr']:.4f} doc_ndcg@10={eval_result['metrics']['doc_ndcg_at_10']:.4f}")
    return 0


def cmd_compare() -> int:
    print("[STAGE 8/10] Dense-vs-sparse comparison")
    sparse_result = load_candidate_result()
    if sparse_result is None or "metrics" not in sparse_result:
        raise SystemExit("Not evaluated yet - run --evaluate first.")
    dense_result = _load_json(TASK33_QWEN_RESULT_PATH)
    frozen_scope_ids, baseline = load_frozen_scope()

    bootstrap = bootstrap_vs_reference(sparse_result, dense_result, frozen_scope_ids)
    comp10 = p3s.complementarity_table(dense_result["per_question"], sparse_result["per_question"],
                                        frozen_scope_ids, hit_field="hit10")
    comp50 = p3s.complementarity_table(dense_result["per_question"], sparse_result["per_question"],
                                        frozen_scope_ids, hit_field="hit50")
    rank_cmp = p3s.first_hit_rank_comparison_counts(dense_result["per_question"], sparse_result["per_question"],
                                                     frozen_scope_ids, rank_field="rank10")

    dm = dense_result["metrics"]
    sm = sparse_result["metrics"]
    deltas = {
        "recall10": sm["doc_recall_at_10"] - dm["doc_recall_at_10"],
        "recall50": sm["doc_recall_at_50"] - dm["doc_recall_at_50"],
        "mrr": sm["doc_mrr"] - dm["doc_mrr"],
        "ndcg10": sm["doc_ndcg_at_10"] - dm["doc_ndcg_at_10"],
    }

    print(f"Sparse vs Qwen dense: delta_recall10={deltas['recall10']:+.4f} delta_recall50={deltas['recall50']:+.4f} "
          f"delta_mrr={deltas['mrr']:+.4f} delta_ndcg10={deltas['ndcg10']:+.4f}")
    print(f"Complementarity @10: both={comp10['both']} dense_only={comp10['dense_only']} "
          f"sparse_only={comp10['sparse_only']} neither={comp10['neither']}")
    print(f"Complementarity @50: both={comp50['both']} dense_only={comp50['dense_only']} "
          f"sparse_only={comp50['sparse_only']} neither={comp50['neither']}")
    print(f"First-hit-rank@10 comparison: sparse_better={rank_cmp['sparse_better']} "
          f"dense_better={rank_cmp['dense_better']} same={rank_cmp['same']}")

    print("[STAGE 9/10] Record Task 3.4 result")
    config, config_hash = load_experiment_config()
    # corpus_document_count: reproduce from the live chunk artifact (never guessed)
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    corpus_doc_count = len(set(chunk_table.column("document_id").to_pylist()))

    row = p3s.build_sparse_ablation_row(
        row_id=ROW_ID, config_hash=config_hash, run_id=sparse_result["run_id"], git_sha=sparse_result["git_sha"],
        eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
        question_count=sparse_result["question_count"], corpus_document_count=corpus_doc_count,
        chunk_count=EXPECTED_CHUNK_COUNT, chunk_config_hash=CHUNK_CONFIG_HASH,
        dense_repository=config["dense_reference"]["model_repository"],
        dense_revision=config["dense_reference"]["model_revision"],
        dense_embedding_identity_hash=dense_result["embedding_identity_hash"],
        sparse_index_identity_hash_value=sparse_result["sparse_index_identity_hash"],
        candidate_k=CANDIDATE_K, metrics=sm, deltas=deltas, complementarity10=comp10, complementarity50=comp50,
        lancedb_version=lancedb.__version__, fts_indexed_column=fts.FTS_INDEXED_COLUMN,
        fts_build_seconds=sparse_result["build_stats"].get("fts_build_seconds") or 0.0,
        fts_index_size_bytes=sparse_result["build_stats"]["index_size_bytes"],
        retrieval_latency_p50_ms=sparse_result["latency_ms"]["retrieval_total"]["p50"] or 0.0,
        retrieval_latency_p95_ms=sparse_result["latency_ms"]["retrieval_total"]["p95"] or 0.0,
        notes=f"Task 3.4: LanceDB-native FTS ({fts.DEFAULT_FTS_CONFIG['base_tokenizer']} tokenizer, "
              f"stem={fts.DEFAULT_FTS_CONFIG['stem']}, stopwords_removed={fts.DEFAULT_FTS_CONFIG['remove_stop_words']}), "
              f"sparse-only (dense_used_in_this_row=false). Dense reference: qwen3_embedding "
              f"(Task 3.3 frozen winner, not rebuilt).",
    )
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    report = {
        "task": "3.4", "phase3_4_config_hash": config_hash, "phase3_4_config": config,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": baseline["phase3_config"]["phase3_dev_scope_sha256"],
        "question_count": sparse_result["question_count"],
        "chunk_config_hash": CHUNK_CONFIG_HASH, "chunk_count": EXPECTED_CHUNK_COUNT,
        "corpus_document_count": corpus_doc_count,
        "dense_reference": {
            "candidate_id": "qwen3_embedding", "model_repository": config["dense_reference"]["model_repository"],
            "model_revision": config["dense_reference"]["model_revision"],
            "embedding_dimension": config["dense_reference"]["embedding_dimension"],
            "embedding_identity_hash": dense_result["embedding_identity_hash"],
            "used_for_sparse_scoring": False, "metrics": dm,
        },
        "sparse_result": sparse_result,
        "paired_sparse_vs_dense": {
            "deltas": deltas,
            "bootstrap": {k: v for k, v in bootstrap.items() if k != "notable_rank_moves"},
            "bootstrap_notable_rank_moves": bootstrap["notable_rank_moves"],
        },
        "complementarity": {"hit_at_10": comp10, "hit_at_50": comp50},
        "first_hit_rank_comparison_at_10": rank_cmp,
        "ablation_row": row,
        "limitations": [
            "Evaluated only over the frozen Task 3.1 89-question DEV/evaluable-subset (4.9% of full DEV).",
            "N=89 is small; bootstrap CIs govern which sparse-vs-dense differences are credible.",
            "Sparse-only baseline: no RRF/hybrid fusion, no reranking, no CRAG, no router, no metadata "
            "pre-filtering, no generation - dense-vs-sparse is an analysis comparison only, not a winner selection.",
            "LanceDB native FTS returns only nonzero-score matches, so a small number of questions may "
            f"receive fewer than {CANDIDATE_K} candidates - see sparse_result.underfilled_question_ids.",
            "chunk_recall@10, chunk_mrr, precision@5, faithfulness, citation_grounding, and generation "
            "metrics remain N/A - no valid chunk-level or generation gold exists for this scope.",
        ],
        "next_task_readiness": (
            "Sparse baseline frozen and comparable to the Task 3.3 dense winner on the identical 89-question "
            "scope. Complementarity counts above are the evidence Task 3.5 (RRF hybrid fusion) needs to decide "
            "whether hybrid retrieval is likely to add value."
        ),
    }
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.4 report written: {FINAL_RESULT_PATH}")
    return 0


def run_full() -> int:
    rc = cmd_build()
    if rc:
        return rc
    rc = cmd_evaluate()
    if rc:
        return rc
    return cmd_compare()


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.4 - Phase 3 LanceDB BM25/FTS sparse baseline.")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.plan:
        return cmd_plan()
    if args.status:
        return cmd_status()
    if args.build:
        return cmd_build()
    if args.evaluate:
        return cmd_evaluate()
    if args.compare:
        return cmd_compare()
    if args.run:
        return run_full()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
