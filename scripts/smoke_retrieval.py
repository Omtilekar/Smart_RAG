"""Task 1.6 - real-corpus smoke retrieval over the Task 1.5 vector index.

Validates Task 1.5 provenance, loads BAAI/bge-small-en-v1.5 offline,
constructs a BaselineRetriever over the real 162,357-row `chunks` table,
runs a small deterministic set of SEC-style smoke questions, verifies
default-k/k=10 behavior, checks determinism on a repeated query, and
records a lightweight timing diagnostic. Read-only throughout - no index
rebuild, no re-embedding, no network access, no generation.
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
from src.embeddings.bge import load_model, encode_queries  # noqa: E402
from src.index.lancedb_index import open_database, open_chunk_table, exact_cosine_search  # noqa: E402
from src.retrieval.baseline import BaselineRetriever, DEFAULT_K  # noqa: E402

CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
MODEL_REPO = "BAAI/bge-small-en-v1.5"
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
EXPECTED_ROW_COUNT = 162357

# Smoke questions only - not a trusted evaluation set (Task 1.9 owns that).
SMOKE_QUESTIONS = [
    "What was the company's total revenue?",
    "What are the main risk factors described in this filing?",
    "What was net income for the fiscal year?",
    "How much did the company spend on research and development?",
    "What is the company's total outstanding debt?",
    "Did the company pay dividends to shareholders?",
]

DIAGNOSTIC_WARMUP = 3
SUMMARY_RELATIVE_PATH = Path("results") / "phase_1_6_retriever_summary.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


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


def main() -> int:
    storage = get_storage()
    db_path, table = verify_index(storage)

    model = load_model(device="cuda")
    retriever = BaselineRetriever(model=model, table=table)

    # --- default-k and k=10 behavior ---
    default_results = retriever.retrieve(SMOKE_QUESTIONS[0], k=DEFAULT_K)
    if len(default_results) != DEFAULT_K:
        raise SystemExit(f"FATAL: default k retrieve returned {len(default_results)}, expected {DEFAULT_K}")
    k10_results = retriever.retrieve(SMOKE_QUESTIONS[0], k=10)
    if len(k10_results) != 10:
        raise SystemExit(f"FATAL: k=10 retrieve returned {len(k10_results)}, expected 10")

    for r in default_results + k10_results:
        if r.rank < 1:
            raise SystemExit(f"FATAL: invalid rank {r.rank}")
        if not (r.score == r.score) or not (r.distance == r.distance):  # NaN check
            raise SystemExit("FATAL: non-finite score/distance")
        if not r.chunk_id or not r.document_id or not r.text:
            raise SystemExit(f"FATAL: empty identity/text field: {r}")
        if r.form_type != "10-K":
            raise SystemExit(f"FATAL: unexpected form_type {r.form_type!r}")
        if r.chunk_config_hash != CHUNK_CONFIG_HASH:
            raise SystemExit(f"FATAL: chunk_config_hash mismatch: {r.chunk_config_hash}")
        if r.normalizer_version != "phase1-minimal-v1":
            raise SystemExit(f"FATAL: unexpected normalizer_version {r.normalizer_version!r}")

    # --- smoke questions, concise metadata only ---
    smoke_results = []
    for q in SMOKE_QUESTIONS:
        results = retriever.retrieve(q, k=DEFAULT_K)
        top = results[0]
        smoke_results.append({
            "question": q,
            "top_chunk_id": top.chunk_id,
            "top_document_id": top.document_id,
            "top_company": top.company,
            "top_fiscal_year": top.fiscal_year,
            "top_score": top.score,
            "top_distance": top.distance,
        })

    # --- Unicode query ---
    unicode_question = "What were café operations' “net income” — 2020?"
    unicode_results = retriever.retrieve(unicode_question, k=DEFAULT_K)
    if len(unicode_results) != DEFAULT_K:
        raise SystemExit("FATAL: Unicode query did not return expected result count")

    # --- determinism: repeat one question with same k ---
    repeat_q = SMOKE_QUESTIONS[1]
    run_a = retriever.retrieve(repeat_q, k=DEFAULT_K)
    run_b = retriever.retrieve(repeat_q, k=DEFAULT_K)
    ids_a = [r.chunk_id for r in run_a]
    ids_b = [r.chunk_id for r in run_b]
    determinism_ok = ids_a == ids_b
    max_score_diff = max((abs(a.score - b.score) for a, b in zip(run_a, run_b)), default=0.0)
    if not determinism_ok:
        raise SystemExit(f"FATAL: repeated query returned different chunk IDs/order: {ids_a} vs {ids_b}")
    if max_score_diff > 1e-5:
        raise SystemExit(f"FATAL: repeated query scores differ beyond tolerance: {max_score_diff}")

    # --- timing diagnostics (separate embedding / search / total) ---
    diag_questions = (SMOKE_QUESTIONS * 10)[:DIAGNOSTIC_WARMUP + 30]
    for q in diag_questions[:DIAGNOSTIC_WARMUP]:
        retriever.retrieve(q, k=DEFAULT_K)

    embed_times_ms, search_times_ms, total_times_ms = [], [], []
    for q in diag_questions[DIAGNOSTIC_WARMUP:]:
        t0 = time.perf_counter()
        vectors = encode_queries(model, [q], batch_size=1)
        t1 = time.perf_counter()
        exact_cosine_search(table, vectors[0], limit=DEFAULT_K)
        t2 = time.perf_counter()
        embed_times_ms.append((t1 - t0) * 1000)
        search_times_ms.append((t2 - t1) * 1000)
        total_times_ms.append((t2 - t0) * 1000)

    def p50_p95(values):
        s = sorted(values)
        return {
            "p50": round(statistics.median(s), 3),
            "p95": round(s[int(0.95 * (len(s) - 1))], 3),
        }

    timing = {
        "label": "Phase 1 smoke diagnostic - NOT a production benchmark",
        "query_count": len(total_times_ms),
        "k": DEFAULT_K,
        "query_embedding_ms": p50_p95(embed_times_ms),
        "exact_search_ms": p50_p95(search_times_ms),
        "total_retrieve_ms": p50_p95(total_times_ms),
    }

    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "chunk_config_hash": CHUNK_CONFIG_HASH,
        "embedding_model": MODEL_REPO,
        "embedding_model_revision": MODEL_REVISION,
        "index_path": str((Path("artifacts") / "indexes" / CHUNK_CONFIG_HASH
                            / MODEL_REPO.replace("/", "--")).as_posix()),
        "table_name": "chunks",
        "search_mode": "exact",
        "distance_metric": "cosine",
        "default_k": DEFAULT_K,
        "score_transform": "1 - distance (no clamping)",
        "vector_omitted": True,
        "smoke_query_count": len(SMOKE_QUESTIONS),
        "k_values_tested": [DEFAULT_K, 10],
        "smoke_results": smoke_results,
        "unicode_query_tested": True,
        "determinism": {
            "repeated_question": repeat_q,
            "same_chunk_ids_and_order": determinism_ok,
            "max_score_diff": max_score_diff,
        },
        "timing_diagnostic": timing,
    }
    summary_path = storage.repo_root / SUMMARY_RELATIVE_PATH
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Index verified: {db_path}, 162,357 rows, 0 ANN indexes")
    print(f"Default k={DEFAULT_K}: {len(default_results)} results; k=10: {len(k10_results)} results")
    print("Smoke questions:")
    for sr in smoke_results:
        print(f"  {sr['question'][:50]!r:52s} -> {sr['top_chunk_id']} "
              f"({sr['top_company']}, FY{sr['top_fiscal_year']}) score={sr['top_score']:.4f}")
    print(f"Unicode query: {len(unicode_results)} results")
    print(f"Determinism: same IDs/order = {determinism_ok}, max score diff = {max_score_diff:.2e}")
    print(f"Timing (n={timing['query_count']}, k={DEFAULT_K}): "
          f"embed p50={timing['query_embedding_ms']['p50']}ms "
          f"search p50={timing['exact_search_ms']['p50']}ms "
          f"total p50={timing['total_retrieve_ms']['p50']}ms / "
          f"p95={timing['total_retrieve_ms']['p95']}ms")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
