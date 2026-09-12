"""Task 3.7 - CRAG-style confidence grading over the Task 3.5-selected,
Task 3.6-unreranked dense-only retrieval mode. Reuses the frozen Task 3.3
dense retrieval score as the confidence signal (no reranker score exists -
Task 3.6 selected no_rerank) and calibrates a refusal threshold on DEV
using two disjoint, already-defined populations: the frozen 89-question
should-answer scope, and the fixed should-refuse population (DEV questions
whose (category,subtype) is in `NOT_APPLICABLE_SHAPES`). See
configs/phase_3_7_crag_confidence_grading.json for the full frozen
contract and the population/score-source decisions.

Never imports src.eval.test_access - Task 3.7 evaluation is DEV-only.

Usage:
    python -u scripts/run_phase3_crag.py --plan
    python -u scripts/run_phase3_crag.py --run
    python -u scripts/run_phase3_crag.py --status
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

import pyarrow.parquet as pq  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.artifacts.versioning import semantic_hash  # noqa: E402
from src.embeddings import model_registry as mr  # noqa: E402
from src.index.lancedb_index import open_database as open_dense_db, open_chunk_table, exact_cosine_search  # noqa: E402
from src.retrieval.baseline import _to_results as _to_results_dense  # noqa: E402
from src.crag import confidence as crag  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_ablation as p3a  # noqa: E402
from src.eval import phase3_crag as p3c  # noqa: E402
from src.eval.metrics import first_hit_rank, reciprocal_rank, hit_at_k, ndcg_at_k  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402

from scripts.run_phase3_chunking_ablation import _p50_p95  # noqa: E402
from scripts.run_phase3_rrf_hybrid import verify_parent_reproduces  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_7_crag_confidence_grading.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
TASK32_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"
TASK33_RESULT_PATH = REPO_ROOT / "results" / "phase_3_3_embedding_model_benchmark.json"
TASK33_QWEN_RESULT_PATH = REPO_ROOT / "results" / "phase3_3" / "qwen3_embedding.json"
TASK35_RESULT_PATH = REPO_ROOT / "results" / "phase_3_5_rrf_hybrid_fusion.json"
TASK36_RESULT_PATH = REPO_ROOT / "results" / "phase_3_6_cross_encoder_reranking.json"
SPLIT_SUMMARY_PATH = REPO_ROOT / "results" / "phase_2_4_split_summary.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_7"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_7_crag_confidence_grading.json"

ROW_ID = "crag_confidence"
CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
CHUNK_SCHEMA_VERSION = 1
EXPECTED_CHUNK_COUNT = 323971
CANDIDATE_K = 50
DOC_RECALL_K = 10


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
    if ids_hash != config["should_answer_scope"]["question_ids_sha256"]:
        raise SystemExit("FATAL: frozen 89-question should-answer scope does not reproduce. STOP.")
    return question_ids, baseline


def load_dev_questions() -> dict:
    return _load_json(REPO_ROOT / "results" / "phase_2_4_dev.json")


def verify_frozen_chunks(storage) -> "pq.Table":
    task32 = _load_json(TASK32_RESULT_PATH)
    if task32["final_winner"]["chunk_config_hash"] != CHUNK_CONFIG_HASH:
        raise SystemExit("FATAL: Task 3.2 final_winner chunk_config_hash changed. STOP.")
    table = pq.read_table(storage.chunks_dir(CHUNK_CONFIG_HASH) / "chunks.parquet")
    if table.num_rows != EXPECTED_CHUNK_COUNT:
        raise SystemExit(f"FATAL: chunk artifact has {table.num_rows} rows, expected {EXPECTED_CHUNK_COUNT}")
    return table


def verify_frozen_dense_winner() -> dict:
    task33 = _load_json(TASK33_RESULT_PATH)
    if task33["final_winner_candidate_id"] != "qwen3_embedding":
        raise SystemExit("FATAL: Task 3.3 winner changed. STOP.")
    return _load_json(TASK33_QWEN_RESULT_PATH)


def verify_inherited_selections() -> None:
    task35 = _load_json(TASK35_RESULT_PATH)
    if task35["selection"]["selected"] != "dense_only":
        raise SystemExit("FATAL: Task 3.5 selection changed - this script assumes dense-only. STOP.")
    task36 = _load_json(TASK36_RESULT_PATH)
    if task36["selection"]["selected"] != "no_rerank":
        raise SystemExit("FATAL: Task 3.6 selection changed - this script assumes no_rerank. STOP.")


def load_should_refuse_questions(config: dict) -> list[dict]:
    shapes = {tuple(s) for s in config["should_refuse_scope"]["shapes"]}
    dev = load_dev_questions()
    return [q for q in dev["questions"] if p3.question_shape(q) in shapes]


# --------------------------------------------------------------- CLI actions

def cmd_plan() -> int:
    config, config_hash = load_experiment_config()
    print("[STAGE 3/10] Frozen Task 3.7 CRAG confidence-grading contract")
    print(f"phase3_7_config_hash: {config_hash}")
    should_refuse = load_should_refuse_questions(config)
    print(f"should_refuse population (live count): {len(should_refuse)} "
          f"(config note claims {config['should_refuse_scope']['note']})")
    print(json.dumps(config, indent=2))
    return 0


def cmd_status() -> int:
    print("Task 3.7 status (read-only)")
    path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not path.is_file():
        print(f"  {ROW_ID}: not run")
        return 0
    result = _load_json(path)
    rates = result.get("rates")
    if rates:
        print(f"  {ROW_ID}: true_refusal_rate={rates['true_refusal_rate']['value']:.4f} "
              f"false_refusal_rate={rates['false_refusal_rate']['value']:.4f} "
              f"missed_failure_rate={rates['missed_failure_rate']['value']:.4f} "
              f"threshold={result['threshold']:.4f}")
    return 0


def _retrieve_and_score(dense_spec, dense_model, dense_table, question: str) -> tuple[list, float]:
    s0 = time.perf_counter()
    qvec = mr.encode_queries(dense_spec, dense_model, [question], batch_size=1)[0]
    arrow = exact_cosine_search(dense_table, qvec, limit=CANDIDATE_K, expected_dimension=dense_spec.dimension)
    results = _to_results_dense(arrow)
    elapsed_ms = (time.perf_counter() - s0) * 1000
    return results, elapsed_ms


def run_full() -> int:
    print("[STAGE 1/10] Task 3.7 preflight")
    frozen_scope_ids, baseline = load_frozen_scope()
    p3a.assert_dev_split("dev")
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    qwen = verify_frozen_dense_winner()
    verify_inherited_selections()
    config, config_hash = load_experiment_config()
    should_refuse_questions = load_should_refuse_questions(config)
    print(f"Frozen should_answer scope: {len(frozen_scope_ids)} questions. "
          f"should_refuse population: {len(should_refuse_questions)} questions. Chunks: {chunk_table.num_rows}.")

    print("[STAGE 2/10] Load dense retriever (Task 3.5/3.6-selected dense-only, unreranked)")
    dense_spec = mr.CANDIDATES_BY_ID["qwen3_embedding"]
    dense_model = mr.load_model(dense_spec, device="cuda")
    dense_db = open_dense_db(storage.index_dir(CHUNK_CONFIG_HASH, dense_spec.repository))
    dense_table = open_chunk_table(dense_db)

    print("[STAGE 6/10] Validate confidence-feature computation (synthetic smoke)")
    smoke_features = crag.compute_confidence_features([0.9, 0.8, 0.7, 0.6, 0.5], candidate_count=5)
    assert smoke_features.top1_score == 0.9
    assert abs(smoke_features.top3_mean_score - 0.8) < 1e-9
    assert abs(smoke_features.top1_top5_gap - 0.4) < 1e-9
    print(f"[SMOKE] ok  {smoke_features}")

    print("[STAGE 7/10] Retrieve and compute confidence features (should-answer + should-refuse populations)")
    dev_payload = load_dev_questions()
    questions_by_id = {q["question_id"]: q for q in dev_payload["questions"]}
    should_answer_questions = [questions_by_id[qid] for qid in frozen_scope_ids]

    dense_pq = {}
    should_answer_features = {}
    latencies = []
    n_total = len(should_answer_questions) + len(should_refuse_questions)
    i = 0
    for q in should_answer_questions:
        i += 1
        results, ms = _retrieve_and_score(dense_spec, dense_model, dense_table, q["question"])
        latencies.append(ms)
        scores = [r.score for r in results]
        features = crag.compute_confidence_features(scores, candidate_count=len(results))
        should_answer_features[q["question_id"]] = features

        target_id = p3.question_target_document_ids(q)[0]
        ranked_document_ids = [r.document_id for r in results]
        rank10 = first_hit_rank(ranked_document_ids, {target_id}, k=DOC_RECALL_K)
        hit10 = hit_at_k(rank10, DOC_RECALL_K)
        rank50 = first_hit_rank(ranked_document_ids, {target_id}, k=len(ranked_document_ids))
        hit50 = hit_at_k(rank50, len(ranked_document_ids))
        relevances10 = p3.document_relevances_at_k(ranked_document_ids, target_id, k=DOC_RECALL_K)
        ndcg10 = ndcg_at_k(relevances10, num_relevant=1, k=DOC_RECALL_K)
        dense_pq[q["question_id"]] = {"hit10": hit10, "rank10": rank10, "rr10": reciprocal_rank(rank10),
                                       "ndcg10": ndcg10, "hit50": hit50, "rank50": rank50}
        if i % 20 == 0 or i == len(should_answer_questions):
            print(f"[CRAG]  should_answer {i}/{len(should_answer_questions)}", flush=True)

    should_refuse_features = {}
    for j, q in enumerate(should_refuse_questions, start=1):
        results, ms = _retrieve_and_score(dense_spec, dense_model, dense_table, q["question"])
        latencies.append(ms)
        scores = [r.score for r in results]
        features = crag.compute_confidence_features(scores, candidate_count=len(results))
        should_refuse_features[q["question_id"]] = features
        if j % 20 == 0 or j == len(should_refuse_questions):
            print(f"[CRAG]  should_refuse {j}/{len(should_refuse_questions)}", flush=True)

    verify_parent_reproduces(dense_pq, qwen["per_question"], label="dense", question_ids=frozen_scope_ids)
    print("[CRAG] dense parent reproduces frozen Task 3.3 metrics")

    print("[STAGE 9/10] Calibrate threshold and compute rates")
    should_answer_top1 = [f.top1_score for f in should_answer_features.values()]
    should_refuse_top1 = [f.top1_score for f in should_refuse_features.values()]
    calibration = crag.calibrate_threshold_youden_j(should_answer_top1, should_refuse_top1)
    threshold = calibration["threshold"]

    should_answer_outcomes = [
        crag.classify_outcome(should_have_answered=True, refused=crag.should_refuse(f, threshold))
        for f in should_answer_features.values()
    ]
    should_refuse_outcomes = [
        crag.classify_outcome(should_have_answered=False, refused=crag.should_refuse(f, threshold))
        for f in should_refuse_features.values()
    ]
    rates = p3c.crag_rates(should_answer_outcomes=should_answer_outcomes, should_refuse_outcomes=should_refuse_outcomes)

    print(f"[CRAG] threshold={threshold:.4f} (Youden's J={calibration['youden_j']:.4f}, "
          f"{calibration['candidates_evaluated']} candidates evaluated)")
    print(f"[CRAG] true_refusal_rate={rates['true_refusal_rate']['value']:.4f} "
          f"({rates['true_refusal_rate']['numerator']}/{rates['true_refusal_rate']['denominator']})")
    print(f"[CRAG] false_refusal_rate={rates['false_refusal_rate']['value']:.4f} "
          f"({rates['false_refusal_rate']['numerator']}/{rates['false_refusal_rate']['denominator']})")
    print(f"[CRAG] missed_failure_rate={rates['missed_failure_rate']['value']:.4f} "
          f"({rates['missed_failure_rate']['numerator']}/{rates['missed_failure_rate']['denominator']})")

    split_summary = _load_json(SPLIT_SUMMARY_PATH)
    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": qwen["repository"], "model_revision": qwen["revision"],
            "embedding_dimension": qwen["dimension"], "vector_dtype": "float32",
            "normalize_embeddings": qwen["normalize_embeddings"], "identity_hash": qwen["embedding_identity_hash"],
        },
        index_identity_hash=qwen["index_identity_hash"],
        retrieval_config={"type": "dense_only_crag_gated", "candidate_k": CANDIDATE_K, "threshold": threshold},
        reranker_config={"enabled": False}, generation_model=None, split="dev",
        eval_set_version="phase2-v1", split_version="phase2-split-v1", split_sha256=split_summary["dev_sha256"],
        metrics={"true_refusal_rate": rates["true_refusal_rate"]["value"],
                 "false_refusal_rate": rates["false_refusal_rate"]["value"],
                 "missed_failure_rate": rates["missed_failure_rate"]["value"]},
        evaluation_source="internal_phase2", experiment_name="phase3_7_crag_confidence_grading",
        run_kind="phase3_crag_confidence_grading",
        notes=f"Task 3.7 CRAG confidence grading (Youden's J threshold={threshold:.4f}) over dense-only "
              f"({CHUNK_CONFIG_HASH[:12]}...), should_answer={len(should_answer_questions)}, "
              f"should_refuse={len(should_refuse_questions)}.",
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[CRAG] Task 2.11 run record written: {run_record_path}")

    payload = {
        "row_id": ROW_ID, "chunk_config_hash": CHUNK_CONFIG_HASH, "config_hash": config_hash,
        "run_id": run_record.run_id, "git_sha": git_sha(),
        "should_answer_count": len(should_answer_questions), "should_refuse_count": len(should_refuse_questions),
        "threshold": threshold, "youden_j": calibration["youden_j"],
        "calibration_candidates_evaluated": calibration["candidates_evaluated"],
        "rates": rates,
        "should_answer_features": {qid: f.__dict__ for qid, f in should_answer_features.items()},
        "should_refuse_features": {qid: f.__dict__ for qid, f in should_refuse_features.items()},
        "latency_ms": _p50_p95(latencies),
    }
    _write_json(CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json", payload)

    print("[STAGE 10/10] Record ablation row and final result")
    dense_result = _load_json(TASK33_QWEN_RESULT_PATH)
    corpus_doc_count = len(set(chunk_table.column("document_id").to_pylist()))
    row = p3c.build_crag_ablation_row(
        row_id=ROW_ID, config_hash=config_hash, run_id=run_record.run_id, git_sha=payload["git_sha"],
        eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
        corpus_document_count=corpus_doc_count, chunk_count=EXPECTED_CHUNK_COUNT, chunk_config_hash=CHUNK_CONFIG_HASH,
        dense_repository=config["base_retrieval"]["model_repository"], dense_revision=config["base_retrieval"]["model_revision"],
        dense_embedding_identity_hash=dense_result["embedding_identity_hash"],
        dense_index_identity_hash=dense_result["index_identity_hash"],
        should_answer_count=len(should_answer_questions), should_refuse_count=len(should_refuse_questions),
        crag_feature="top1_score", crag_threshold=threshold, crag_youden_j=calibration["youden_j"], rates=rates,
        retrieval_latency_p50_ms=payload["latency_ms"]["p50"] or 0.0, retrieval_latency_p95_ms=payload["latency_ms"]["p95"] or 0.0,
        notes=f"Task 3.7: CRAG confidence grading, top1_score threshold={threshold:.4f} (Youden's J), "
              f"should_answer={len(should_answer_questions)}, should_refuse={len(should_refuse_questions)}. "
              f"Score source substituted for the roadmap's 'reranker score' since Task 3.6 selected no_rerank.",
    )
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    report = {
        "task": "3.7", "phase3_7_config_hash": config_hash, "phase3_7_config": config,
        "chunk_config_hash": CHUNK_CONFIG_HASH, "chunk_count": EXPECTED_CHUNK_COUNT,
        "corpus_document_count": corpus_doc_count,
        "should_answer_scope_sha256": baseline["phase3_config"]["phase3_dev_scope_sha256"],
        "should_answer_count": len(should_answer_questions), "should_refuse_count": len(should_refuse_questions),
        "crag_feature": "top1_score", "threshold": threshold, "youden_j": calibration["youden_j"],
        "rates": rates, "latency_ms": payload["latency_ms"], "ablation_row": row,
        "limitations": [
            "should_answer population is the frozen 89-question retrieval scope (4.9% of full DEV); "
            "should_refuse population is 113 fixed not-applicable-shape DEV questions - neither is a random "
            "DEV sample.",
            "Threshold calibrated and measured on the same population (no held-out split) - a known "
            "optimistic-bias limitation, consistent with how every other frozen Phase 3 threshold in this "
            "project was set with visibility into DEV behavior.",
            "Single global threshold on top1_score only - per-intent thresholds and the other three "
            "candidate features (top3_mean_score, top1_top5_gap, candidate_count) were not used to gate "
            "the decision in this round, only recorded diagnostically.",
            "DEV questions with a retrieval-applicable-but-uncovered gold document (excluded from the "
            "89-question scope since Task 3.1) were NOT used as should_refuse evidence - a deliberate scope "
            "boundary, not an oversight.",
            "No generation - this measures a pure retrieval-confidence gate, not end-to-end answer quality.",
        ],
        "next_task_readiness": (
            f"CRAG confidence gate calibrated (top1_score < {threshold:.4f} => refuse). "
            f"true_refusal_rate={rates['true_refusal_rate']['value']:.4f}, "
            f"false_refusal_rate={rates['false_refusal_rate']['value']:.4f}, "
            f"missed_failure_rate={rates['missed_failure_rate']['value']:.4f}."
        ),
    }
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.7 report written: {FINAL_RESULT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.7 - Phase 3 CRAG confidence grading.")
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
