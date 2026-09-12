"""Task 3.14 - re-check the Phase 0 (Task 0.10) serving feasibility
decision against the ACTUAL Phase 3 selected retrieval stack, not the
spike's provisional placeholders.

Phase 0's spike measured bge-small-en-v1.5 (384-dim) + LanceDB +
MiniLM cross-encoder reranking. Phase 3 selected a materially
different stack: Qwen/Qwen3-Embedding-0.6B (1024-dim, ~1.1 GB model,
Task 3.3 winner), dense-only retrieval (Task 3.5's RRF hybrid was a
negative result - dense-only selected), NO reranker (Task 3.6's
cross-encoder reranking was a negative result - no_rerank selected).
This script re-measures CPU-only warm latency for the real selected
path against the real frozen production LanceDB index, using the same
CPU_THREADS=2 constraint and warm/cold measurement convention as the
Task 0.10 spike (project_plan/SERVING_FEASIBILITY.md), so the numbers
are directly comparable to the frozen decision thresholds.

Never imports src.eval.test_access - Task 3.14 evaluation is DEV-only.
Read-only against the frozen production chunk/index artifacts; writes
no new index and mutates no frozen artifact.

Usage:
    python -u scripts/run_phase3_serving_recheck.py --plan
    python -u scripts/run_phase3_serving_recheck.py --run
    python -u scripts/run_phase3_serving_recheck.py --status
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

import psutil  # noqa: E402
import torch  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.embeddings import model_registry as mr  # noqa: E402
from src.index.lancedb_index import open_database, open_chunk_table, exact_cosine_search  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402

from scripts.run_phase3_chunking_ablation import _p50_p95, directory_size_bytes  # noqa: E402

CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
CANDIDATE_K = 50
CPU_THREADS = 2  # same small-instance assumption as the Task 0.10 spike
WARMUP_QUERIES = 10  # same convention as the Task 0.10 spike

BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
DEV_QUESTIONS_PATH = REPO_ROOT / "results" / "phase_2_4_dev.json"
SPIKE_RESULT_PATH = REPO_ROOT / "results" / "phase_0_10_serving_spike.json"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_14_serving_recheck.json"

# Frozen Task 0.10 decision thresholds (project_plan/SERVING_FEASIBILITY.md),
# applied without modification to whatever this script measures.
DECISION_THRESHOLDS = (
    (500.0, "proceed_with_serverless_design"),
    (2000.0, "proceed_but_constrain_reranker_and_candidate_pool"),
    (float("inf"), "change_serving_target_to_warm_compute"),
)


def git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def apply_decision_thresholds(warm_p95_ms: float) -> str:
    for threshold, action in DECISION_THRESHOLDS:
        if warm_p95_ms < threshold:
            return action
    return DECISION_THRESHOLDS[-1][1]  # pragma: no cover - unreachable, inf sentinel always matches


def load_frozen_scope_questions() -> list[dict]:
    baseline = _load_json(BASELINE_RESULT_PATH)
    question_ids = sorted(baseline["question_ids"])
    dev_payload = _load_json(DEV_QUESTIONS_PATH)
    by_id = {q["question_id"]: q for q in dev_payload["questions"]}
    return [by_id[qid] for qid in question_ids]


def cmd_plan() -> int:
    print("[STAGE 1/6] Task 3.14 serving re-check plan")
    print(f"selected embedding: Qwen/Qwen3-Embedding-0.6B (Task 3.3 winner), dimension=1024")
    print("selected retrieval: dense-only (Task 3.5 RRF hybrid = negative result)")
    print("selected reranker: none (Task 3.6 cross-encoder reranking = negative result)")
    print(f"CPU_THREADS={CPU_THREADS} (matches Task 0.10 spike's small-instance assumption)")
    print(f"candidate_k={CANDIDATE_K}, warmup_queries={WARMUP_QUERIES}")
    return 0


def cmd_status() -> int:
    print("Task 3.14 status (read-only)")
    if not FINAL_RESULT_PATH.is_file():
        print("  not run")
        return 0
    result = _load_json(FINAL_RESULT_PATH)
    print(f"  warm p50={result['path_timing_ms']['p50']} ms, p95={result['path_timing_ms']['p95']} ms")
    print(f"  decision: {result['decision']['action']}")
    return 0


def run_full() -> int:
    print("[STAGE 1/6] Task 3.14 preflight")
    torch.set_num_threads(CPU_THREADS)
    storage = get_storage()
    spec = mr.CANDIDATES_BY_ID["qwen3_embedding"]
    questions = load_frozen_scope_questions()
    print(f"Frozen DEV scope: {len(questions)} questions. CPU_THREADS={CPU_THREADS}.")

    print("[STAGE 2/6] Open frozen production LanceDB index (read-only) - no new index built")
    index_path = storage.index_dir(CHUNK_CONFIG_HASH, spec.repository)
    if not index_path.is_dir():
        raise SystemExit(f"FATAL: frozen production index not found at {index_path}. STOP.")
    index_size_bytes = directory_size_bytes(index_path)
    db = open_database(index_path)
    table = open_chunk_table(db)
    print(f"Index: {index_path} ({index_size_bytes / (1024**3):.3f} GiB, {table.count_rows()} rows)")

    print("[STAGE 3/6] Load Qwen3-Embedding-0.6B on CPU (device='cpu', not the eval-time 'cuda' path)")
    rss_before_model = psutil.Process().memory_info().rss
    t_load_start = time.perf_counter()
    model = mr.load_model(spec, device="cpu")
    model_load_seconds = time.perf_counter() - t_load_start
    rss_after_model = psutil.Process().memory_info().rss
    print(f"Model loaded in {model_load_seconds:.3f}s. RSS delta: {(rss_after_model - rss_before_model) / (1024**2):.1f} MB")

    print(f"[STAGE 4/6] Warm-up ({WARMUP_QUERIES} unmeasured queries)")
    for q in questions[:WARMUP_QUERIES]:
        qvec = mr.encode_queries(spec, model, [q["question"]], batch_size=1)[0]
        exact_cosine_search(table, qvec, limit=CANDIDATE_K, expected_dimension=spec.dimension)

    print(f"[STAGE 5/6] Warm measurement ({len(questions) - WARMUP_QUERIES} queries, dense-only, no rerank)")
    embed_ms: list[float] = []
    search_ms: list[float] = []
    path_ms: list[float] = []
    for q in questions[WARMUP_QUERIES:]:
        t0 = time.perf_counter()
        qvec = mr.encode_queries(spec, model, [q["question"]], batch_size=1)[0]
        t_embed = time.perf_counter()
        exact_cosine_search(table, qvec, limit=CANDIDATE_K, expected_dimension=spec.dimension)
        t_search = time.perf_counter()
        embed_ms.append((t_embed - t0) * 1000)
        search_ms.append((t_search - t_embed) * 1000)
        path_ms.append((t_search - t0) * 1000)
    rss_peak = psutil.Process().memory_info().rss

    component_timing_ms = {"query_embedding_cpu": _p50_p95(embed_ms), "vector_retrieval_flat": _p50_p95(search_ms)}
    path_timing_ms = _p50_p95(path_ms)
    print(f"[RECHECK] query_embedding p50={component_timing_ms['query_embedding_cpu']['p50']}ms "
          f"p95={component_timing_ms['query_embedding_cpu']['p95']}ms")
    print(f"[RECHECK] vector_retrieval p50={component_timing_ms['vector_retrieval_flat']['p50']}ms "
          f"p95={component_timing_ms['vector_retrieval_flat']['p95']}ms")
    print(f"[RECHECK] end-to-end (dense-only, no rerank) p50={path_timing_ms['p50']}ms p95={path_timing_ms['p95']}ms")

    print("[STAGE 6/6] Apply frozen Task 0.10 decision thresholds and record")
    decision_action = apply_decision_thresholds(path_timing_ms["p95"])
    print(f"[RECHECK] decision: {decision_action}")

    spike = _load_json(SPIKE_RESULT_PATH)
    report = {
        "task": "3.14",
        "git_sha": git_sha(),
        "selected_stack": {
            "chunking": "fixed/256/0 (Task 3.2 winner)",
            "embedding": {"repository": spec.repository, "revision": spec.revision, "dimension": spec.dimension},
            "retrieval": "dense_only (Task 3.5 RRF hybrid = negative result, dense-only selected)",
            "reranker": "none (Task 3.6 cross-encoder reranking = negative result, no_rerank selected)",
            "candidate_k": CANDIDATE_K,
        },
        "measurement_methodology": {
            "cpu_threads": CPU_THREADS, "warmup_queries": WARMUP_QUERIES,
            "measured_queries": len(questions) - WARMUP_QUERIES,
            "note": "Same CPU_THREADS=2 small-instance constraint and warm-up convention as the Task 0.10 spike "
                    "(project_plan/SERVING_FEASIBILITY.md) - directly comparable to its frozen decision thresholds. "
                    "Task 3.1/3.3/3.9's own recorded retrieval_latency_* ablation-table columns were measured with "
                    "the model on device='cuda' (GPU), NOT CPU - not valid inputs for this CPU-only serving check, "
                    "hence this new measurement.",
        },
        "component_timing_ms": component_timing_ms,
        "path_timing_ms": path_timing_ms,
        "model_load_seconds": round(model_load_seconds, 3),
        "memory_mb": {
            "rss_before_model_load": round(rss_before_model / (1024**2), 1),
            "rss_after_model_load": round(rss_after_model / (1024**2), 1),
            "rss_peak_during_warm_benchmark": round(rss_peak / (1024**2), 1),
        },
        "artifact_sizes": {
            "lancedb_index_bytes": index_size_bytes,
            "lancedb_index_gib": round(index_size_bytes / (1024**3), 3),
            "quantization_applied": False,
            "quantization_note": "No quantization scheme was ever selected or applied in Phase 3 (flat/exact "
                                  "search throughout, src.index.lancedb_index.exact_cosine_search) - an honest "
                                  "gap against this task's 'after the selected quantization' wording, not a "
                                  "fabricated selection. The Task 0.10 spike's own IVF_PQ comparison (100k chunks, "
                                  "384-dim) is not directly comparable to this 323,971-chunk, 1024-dim index.",
        },
        "decision_thresholds": {
            "source": "project_plan/SERVING_FEASIBILITY.md, applied without modification",
            "thresholds_ms": {"proceed_serverless": "<500", "proceed_constrained": "500-2000", "warm_compute": ">2000"},
        },
        "decision": {
            "action": decision_action,
            "warm_p95_ms": path_timing_ms["p95"],
            "phase0_warm_p95_vector_plus_rerank_ms": spike["path_timing_ms"]["vector_plus_rerank"]["p95"] if "vector_plus_rerank" in spike.get("path_timing_ms", {}) else None,
        },
        "limitations": [
            "No cold-start measurement was repeated for this re-check (Task 0.10's own process-cold proxy already "
            "established process-cold >> 10s is dominated by import/model-load cost, not the retrieval path "
            "itself, and Qwen3-Embedding-0.6B's larger model size makes cold start strictly worse, not better, "
            "than the spike's bge-small baseline - so the Task 0.10 serverless disqualification on cold-start "
            "grounds alone still stands without needing to re-measure it).",
            "No quantized index was built for this re-check - Phase 3 never selected or built one; the frozen "
            "production index is flat/exact (unquantized).",
            "No memory-tier repetition (distinct Lambda-shaped memory allocations) was performed, matching the "
            "Task 0.10 spike's own documented Docker-unavailable gap.",
            "This is a single-machine, single-session CPU measurement (CPU_THREADS=2 constrained but otherwise "
            "this development laptop, not an actual Lambda/Fargate CPU) - same caveat the Task 0.10 spike itself "
            "documented for its own numbers.",
        ],
    }
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.14 report written: {FINAL_RESULT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.14 - Phase 3 serving-budget re-check.")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.plan:
        return cmd_plan()
    if args.status:
        return cmd_status()
    if args.run:
        return run_full()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
