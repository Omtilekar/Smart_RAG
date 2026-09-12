"""Task 3.6 - cross-encoder reranking over the Task 3.5-selected dense-only
retrieval mode (RRF hybrid was practically tied with dense; dense-only was
preferred as the simpler architecture - see
results/phase_3_5_rrf_hybrid_fusion.json). Reranks the frozen 50-chunk Qwen
dense candidate pool with `cross-encoder/ms-marco-MiniLM-L6-v2` (the
single candidate approved for this round - PROJECT_EXECUTION.md names no
specific reranker model; see configs/phase_3_6_cross_encoder_reranking.json's
`candidate_grid_decision`).

One dense retrieval pass per question produces the base (pre-rerank) top-50;
the same 50 chunks are then rescored by the cross-encoder and resorted -
no second dense retrieval call, no embedding/index rebuild, no sparse
retrieval, no generation.

Never imports src.eval.test_access - Task 3.6 evaluation is DEV-only.

Usage:
    python -u scripts/run_phase3_reranker.py --plan
    python -u scripts/run_phase3_reranker.py --run
    python -u scripts/run_phase3_reranker.py --compare
    python -u scripts/run_phase3_reranker.py --status
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

import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.artifacts.versioning import semantic_hash  # noqa: E402
from src.embeddings import model_registry as mr  # noqa: E402
from src.index.lancedb_index import open_database as open_dense_db, open_chunk_table, exact_cosine_search  # noqa: E402
from src.retrieval.baseline import _to_results as _to_results_dense  # noqa: E402
from src.rerank import cross_encoder as ce  # noqa: E402
from src.retrieval.reranked import RerankedRetriever  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_ablation as p3a  # noqa: E402
from src.eval import phase3_rerank as p3r  # noqa: E402
from src.eval import phase3_hybrid as p3h  # noqa: E402
from src.eval.metrics import first_hit_rank, reciprocal_rank, mean_reciprocal_rank, ndcg_at_k, hit_at_k, precision_at_k  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402

from scripts.run_phase3_chunking_ablation import _p50_p95  # noqa: E402
from scripts.run_phase3_rrf_hybrid import verify_parent_reproduces  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_6_cross_encoder_reranking.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
TASK32_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"
TASK33_RESULT_PATH = REPO_ROOT / "results" / "phase_3_3_embedding_model_benchmark.json"
TASK33_QWEN_RESULT_PATH = REPO_ROOT / "results" / "phase3_3" / "qwen3_embedding.json"
TASK35_RESULT_PATH = REPO_ROOT / "results" / "phase_3_5_rrf_hybrid_fusion.json"
SPLIT_SUMMARY_PATH = REPO_ROOT / "results" / "phase_2_4_split_summary.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_6"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_6_cross_encoder_reranking.json"

ROW_ID = "ce_minilm_l6"
CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
CHUNK_SCHEMA_VERSION = 1
EXPECTED_CHUNK_COUNT = 323971

BASE_K = 50
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
        raise SystemExit(f"FATAL: frozen 89-question scope does not reproduce. STOP.")
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
        raise SystemExit(f"FATAL: Task 3.3 winner changed. STOP.")
    return _load_json(TASK33_QWEN_RESULT_PATH)


def verify_task35_selection() -> None:
    task35 = _load_json(TASK35_RESULT_PATH)
    if task35["selection"]["selected"] != "dense_only":
        raise SystemExit(
            f"FATAL: Task 3.5 selection changed to {task35['selection']['selected']!r} - "
            f"this script assumes dense-only is the inherited retrieval mode. STOP."
        )


def _doc_metrics_at(ranked_document_ids: list[str], target_id: str, k: int) -> dict:
    rank = first_hit_rank(ranked_document_ids, {target_id}, k=k)
    hit = hit_at_k(rank, k)
    relevances = p3.document_relevances_at_k(ranked_document_ids, target_id, k=k)
    return {"rank": rank, "hit": hit, "relevances": relevances}


def _doc_metrics_for(ranked_document_ids: list[str], target_id: str) -> dict:
    m5 = _doc_metrics_at(ranked_document_ids, target_id, k=5)
    m10 = _doc_metrics_at(ranked_document_ids, target_id, k=DOC_RECALL_K)
    rank50 = first_hit_rank(ranked_document_ids, {target_id}, k=len(ranked_document_ids))
    hit50 = hit_at_k(rank50, len(ranked_document_ids))
    return {
        "hit5": m5["hit"], "rank5": m5["rank"], "precision5": precision_at_k(m5["relevances"], 5),
        "hit10": m10["hit"], "rank10": m10["rank"], "rr10": reciprocal_rank(m10["rank"]),
        "ndcg10": ndcg_at_k(m10["relevances"], num_relevant=1, k=DOC_RECALL_K),
        "hit50": hit50, "rank50": rank50,
    }


# --------------------------------------------------------------- CLI actions

def cmd_plan() -> int:
    config, config_hash = load_experiment_config()
    print("[STAGE 3/10] Frozen Task 3.6 cross-encoder reranking contract")
    print(f"phase3_6_config_hash: {config_hash}")
    print(json.dumps(config, indent=2))
    return 0


def cmd_status() -> int:
    print("Task 3.6 status (read-only)")
    path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not path.is_file():
        print(f"  {ROW_ID}: not run")
        return 0
    result = _load_json(path)
    m = result.get("metrics")
    if m:
        print(f"  {ROW_ID}: recall@5={m['doc_recall_at_5']:.4f} precision@5={m['doc_precision_at_5']:.4f} "
              f"mrr={m['doc_mrr']:.4f} ndcg@10={m['doc_ndcg_at_10']:.4f}")
    return 0


def run_full() -> int:
    print("[STAGE 1/10] Task 3.6 preflight")
    frozen_scope_ids, baseline = load_frozen_scope()
    p3a.assert_dev_split("dev")
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    qwen = verify_frozen_dense_winner()
    verify_task35_selection()
    print(f"Frozen scope verified: {len(frozen_scope_ids)} questions. Chunks: {chunk_table.num_rows}. "
          f"Base retrieval: {qwen['repository']}@{qwen['revision'][:12]} (Task 3.5-selected dense-only).")

    config, config_hash = load_experiment_config()
    rr_spec = config["reranker"]
    if rr_spec["model_revision"] != ce.CROSS_ENCODER_MINILM_L6.revision:
        raise SystemExit("FATAL: frozen config reranker revision != src.rerank.cross_encoder pinned revision. STOP.")

    print("[STAGE 2/10] Verify inherited dense winner reproduces")
    dev_payload = load_dev_questions()
    questions_by_id = {q["question_id"]: q for q in dev_payload["questions"]}
    scoped_questions = [questions_by_id[qid] for qid in frozen_scope_ids]

    dense_spec = mr.CANDIDATES_BY_ID["qwen3_embedding"]
    print("[HYBRID] validating dense parent...")  # reuses verify_parent_reproduces's own log line
    dense_model = mr.load_model(dense_spec, device="cuda")
    dense_db = open_dense_db(storage.index_dir(CHUNK_CONFIG_HASH, dense_spec.repository))
    dense_table = open_chunk_table(dense_db)

    print("[STAGE 4/10] Load cross-encoder reranker (pilot)")
    reranker_spec = ce.CROSS_ENCODER_MINILM_L6
    t0 = time.perf_counter()
    reranker_model = ce.load_model(reranker_spec, device="cuda")
    print(f"[RERANK] loaded {reranker_spec.repository}@{reranker_spec.revision[:12]} in {time.perf_counter()-t0:.2f}s")

    print("[STAGE 5/10] Reranked retriever boundary ready (src/retrieval/reranked.py)")

    print("[STAGE 6/10] Validate reranker behavior (synthetic smoke)")
    pilot_scores = ce.score_pairs(reranker_model, "What is the capital of France?",
                                   ["Paris is the capital of France.", "Berlin is the capital of Germany."])
    if not (pilot_scores[0] > pilot_scores[1]):
        raise SystemExit(f"FATAL: reranker pilot sanity check failed: {pilot_scores}")
    print(f"[SMOKE] ok  relevant={pilot_scores[0]:.3f} > irrelevant={pilot_scores[1]:.3f}")

    print("[STAGE 7/10] Evaluate reranked vs no-rerank baseline "
          "(also verifies the dense parent reproduces its frozen Task 3.3 per-question metrics)")
    diagnostics_path = storage.eval_dir("phase3_6_cross_encoder_reranking") / "query_diagnostics.jsonl"
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)

    n = len(scoped_questions)
    base_per_question, reranked_per_question, dense_pq = {}, {}, {}
    dense_ms, rerank_ms, total_ms = [], [], []
    base_hit10_flags, reranked_hit10_flags = [], []

    t0 = time.perf_counter()
    with open(diagnostics_path, "w", encoding="utf-8") as diag_f:
        for i, q in enumerate(scoped_questions, start=1):
            qid = q["question_id"]
            target_id = p3.question_target_document_ids(q)[0]

            s0 = time.perf_counter()
            qvec = mr.encode_queries(dense_spec, dense_model, [q["question"]], batch_size=1)[0]
            dense_arrow = exact_cosine_search(dense_table, qvec, limit=BASE_K, expected_dimension=dense_spec.dimension)
            base_results = _to_results_dense(dense_arrow)
            s1 = time.perf_counter()

            texts = [r.text for r in base_results]
            scores = ce.score_pairs(reranker_model, q["question"], texts)
            ce.validate_scores(scores, expected_count=len(base_results))
            order = np.argsort(-scores, kind="stable")
            reranked_document_ids = [base_results[i2].document_id for i2 in order]
            s2 = time.perf_counter()

            base_document_ids = [r.document_id for r in base_results]
            base_m = _doc_metrics_for(base_document_ids, target_id)
            reranked_m = _doc_metrics_for(reranked_document_ids, target_id)

            p3r.assert_candidate_set_recall_unchanged(
                reranked_recall_at_50=1.0 if reranked_m["hit50"] else 0.0,
                base_recall_at_50=1.0 if base_m["hit50"] else 0.0,
            )

            dense_pq[qid] = {"hit10": base_m["hit10"], "rank10": base_m["rank10"], "rr10": base_m["rr10"],
                              "ndcg10": base_m["ndcg10"], "hit50": base_m["hit50"], "rank50": base_m["rank50"]}
            base_per_question[qid] = {"target_document_id": target_id, **base_m}
            reranked_per_question[qid] = {"target_document_id": target_id, **reranked_m}

            base_hit10_flags.append(base_m["hit10"])
            reranked_hit10_flags.append(reranked_m["hit10"])

            dense_ms.append((s1 - s0) * 1000)
            rerank_ms.append((s2 - s1) * 1000)
            total_ms.append((s2 - s0) * 1000)

            diag_f.write(json.dumps({
                "question_id": qid, "gold_document_ids": [target_id],
                "base_ranked_document_ids": base_document_ids, "reranked_document_ids": reranked_document_ids,
                "reranker_scores": [float(x) for x in scores],
                "base_hit10": base_m["hit10"], "reranked_hit10": reranked_m["hit10"],
                "base_rank10": base_m["rank10"], "reranked_rank10": reranked_m["rank10"],
                "dense_retrieval_ms": (s1 - s0) * 1000, "rerank_ms": (s2 - s1) * 1000,
            }) + "\n")

            if i % EVAL_PROGRESS_EVERY == 0 or i == n:
                print(f"[RERANK EVAL]  {i}/{n}  {100*i/n:5.1f}%  base_hit10={sum(base_hit10_flags)}  "
                      f"reranked_hit10={sum(reranked_hit10_flags)}  avg_ms={sum(total_ms)/len(total_ms):.1f}", flush=True)
    run_seconds = time.perf_counter() - t0

    verify_parent_reproduces(dense_pq, qwen["per_question"], label="dense", question_ids=frozen_scope_ids)
    print("[RERANK] dense parent reproduces frozen metrics")

    def _aggregate(per_question: dict) -> dict:
        hits5 = sum(1 for v in per_question.values() if v["hit5"])
        hits10 = sum(1 for v in per_question.values() if v["hit10"])
        hits50 = sum(1 for v in per_question.values() if v["hit50"])
        return {
            "doc_recall_at_5": hits5 / n, "doc_recall_at_5_hits": hits5,
            "doc_recall_at_10": hits10 / n, "doc_recall_at_10_hits": hits10,
            "doc_recall_at_50": hits50 / n, "doc_recall_at_50_hits": hits50,
            "doc_mrr": mean_reciprocal_rank([v["rr10"] for v in per_question.values()]),
            "doc_ndcg_at_10": sum(v["ndcg10"] for v in per_question.values()) / n,
            "doc_precision_at_5": sum(v["precision5"] for v in per_question.values()) / n,
        }

    base_metrics = _aggregate(base_per_question)
    reranked_metrics = _aggregate(reranked_per_question)
    p3r.assert_candidate_set_recall_unchanged(reranked_metrics["doc_recall_at_50"], base_metrics["doc_recall_at_50"])

    print(f"[RERANK EVAL] no_rerank:  R@5={base_metrics['doc_recall_at_5']:.4f} P@5={base_metrics['doc_precision_at_5']:.4f} "
          f"MRR={base_metrics['doc_mrr']:.4f} nDCG@10={base_metrics['doc_ndcg_at_10']:.4f}")
    print(f"[RERANK EVAL] reranked:   R@5={reranked_metrics['doc_recall_at_5']:.4f} P@5={reranked_metrics['doc_precision_at_5']:.4f} "
          f"MRR={reranked_metrics['doc_mrr']:.4f} nDCG@10={reranked_metrics['doc_ndcg_at_10']:.4f}")

    split_summary = _load_json(SPLIT_SUMMARY_PATH)
    identity_hash = semantic_hash(reranker_spec.reranker_identity())
    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": qwen["repository"], "model_revision": qwen["revision"],
            "embedding_dimension": qwen["dimension"], "vector_dtype": "float32",
            "normalize_embeddings": qwen["normalize_embeddings"], "identity_hash": qwen["embedding_identity_hash"],
        },
        index_identity_hash=qwen["index_identity_hash"],
        retrieval_config={"type": "dense_only_reranked", "base_k": BASE_K},
        reranker_config={"enabled": True, "model": reranker_spec.repository, "revision": reranker_spec.revision},
        generation_model=None, split="dev", eval_set_version="phase2-v1", split_version="phase2-split-v1",
        split_sha256=split_summary["dev_sha256"], metrics=reranked_metrics, evaluation_source="internal_phase2",
        experiment_name="phase3_6_cross_encoder_reranking", run_kind="phase3_cross_encoder_reranking",
        notes=f"Task 3.6 cross-encoder reranking ({reranker_spec.repository}@{reranker_spec.revision[:12]}) "
              f"over the Task 3.5-selected dense-only candidate pool ({CHUNK_CONFIG_HASH[:12]}...).",
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[RERANK EVAL] Task 2.11 run record written: {run_record_path}")

    payload = {
        "row_id": ROW_ID, "chunk_config_hash": CHUNK_CONFIG_HASH, "config_hash": config_hash,
        "run_id": run_record.run_id, "git_sha": git_sha(), "question_count": n,
        "metrics": reranked_metrics, "base_metrics": base_metrics,
        "per_question": reranked_per_question, "base_per_question": base_per_question,
        "reranker_identity": reranker_spec.reranker_identity(), "reranker_identity_hash": identity_hash,
        "latency_ms": {"dense": _p50_p95(dense_ms), "rerank": _p50_p95(rerank_ms), "total": _p50_p95(total_ms)},
        "run_seconds": round(run_seconds, 3), "diagnostics_path": str(diagnostics_path),
    }
    _write_json(CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json", payload)
    return 0


def cmd_compare() -> int:
    print("[STAGE 8/10] Analyze reranked vs no-rerank deltas")
    result_path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not result_path.is_file():
        raise SystemExit("Not run yet - run --run first.")
    result = _load_json(result_path)
    frozen_scope_ids, baseline = load_frozen_scope()

    rm, bm = result["metrics"], result["base_metrics"]
    deltas = {
        "recall10": rm["doc_recall_at_10"] - bm["doc_recall_at_10"], "recall50": rm["doc_recall_at_50"] - bm["doc_recall_at_50"],
        "mrr": rm["doc_mrr"] - bm["doc_mrr"], "ndcg10": rm["doc_ndcg_at_10"] - bm["doc_ndcg_at_10"],
        "precision5": rm["doc_precision_at_5"] - bm["doc_precision_at_5"], "recall5": rm["doc_recall_at_5"] - bm["doc_recall_at_5"],
    }

    cand_rr, base_rr = [], []
    cand_ndcg, base_ndcg = [], []
    cand_hit5, base_hit5 = [], []
    for qid in frozen_scope_ids:
        cand_rr.append(result["per_question"][qid]["rr10"]); base_rr.append(result["base_per_question"][qid]["rr10"])
        cand_ndcg.append(result["per_question"][qid]["ndcg10"]); base_ndcg.append(result["base_per_question"][qid]["ndcg10"])
        cand_hit5.append(1.0 if result["per_question"][qid]["hit5"] else 0.0)
        base_hit5.append(1.0 if result["base_per_question"][qid]["hit5"] else 0.0)

    mrr_boot = p3a.paired_bootstrap_delta_ci(cand_rr, base_rr, seed=p3a.BOOTSTRAP_SEED, iterations=p3a.BOOTSTRAP_ITERATIONS)
    ndcg_boot = p3a.paired_bootstrap_delta_ci(cand_ndcg, base_ndcg, seed=p3a.BOOTSTRAP_SEED, iterations=p3a.BOOTSTRAP_ITERATIONS)

    recall5_hit_delta = sum(1 for qid in frozen_scope_ids if result["per_question"][qid]["hit5"]) - \
                         sum(1 for qid in frozen_scope_ids if result["base_per_question"][qid]["hit5"])

    hit_gain_loss_5 = p3h.gain_loss_counts(result["base_per_question"], result["per_question"], frozen_scope_ids, hit_field="hit5")

    print(f"Reranked vs no-rerank: delta_recall5={deltas['recall5']:+.4f} delta_precision5={deltas['precision5']:+.4f} "
          f"delta_mrr={deltas['mrr']:+.4f} delta_ndcg10={deltas['ndcg10']:+.4f}")
    print(f"hit@5 vs no-rerank: gained={hit_gain_loss_5['gained']} lost={hit_gain_loss_5['lost']} "
          f"unchanged={hit_gain_loss_5['unchanged']}")
    print(f"MRR 95% CI: ({mrr_boot.ci_lo:+.4f}, {mrr_boot.ci_hi:+.4f})  nDCG@10 95% CI: ({ndcg_boot.ci_lo:+.4f}, {ndcg_boot.ci_hi:+.4f})")

    print("[STAGE 9/10] Select reranking configuration")
    selection = p3r.select_rerank_configuration(
        reranked_metrics=rm, base_metrics=bm, recall5_hit_delta=recall5_hit_delta,
        mrr_ci=(mrr_boot.ci_lo, mrr_boot.ci_hi), ndcg_ci=(ndcg_boot.ci_lo, ndcg_boot.ci_hi),
    )
    if selection.flagged_for_user_decision:
        raise SystemExit(f"STOP - Task 3.6 requires a user decision: {selection.flag_reason}")
    print(f"Selected: {selection.selected} - {selection.rationale}")

    config, config_hash = load_experiment_config()
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    corpus_doc_count = len(set(chunk_table.column("document_id").to_pylist()))
    dense_result = _load_json(TASK33_QWEN_RESULT_PATH)

    row = p3r.build_rerank_ablation_row(
        row_id=ROW_ID, config_hash=config_hash, run_id=result["run_id"], git_sha=result["git_sha"],
        eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
        question_count=result["question_count"], corpus_document_count=corpus_doc_count,
        chunk_count=EXPECTED_CHUNK_COUNT, chunk_config_hash=CHUNK_CONFIG_HASH,
        dense_repository=config["base_retrieval"]["model_repository"], dense_revision=config["base_retrieval"]["model_revision"],
        dense_embedding_identity_hash=dense_result["embedding_identity_hash"],
        dense_index_identity_hash=dense_result["index_identity_hash"],
        reranker_repository=config["reranker"]["model_repository"], reranker_revision=config["reranker"]["model_revision"],
        reranker_identity_hash=result["reranker_identity_hash"], rerank_base_k=BASE_K,
        metrics=rm, deltas=deltas, hit_gain_loss_5=hit_gain_loss_5,
        reranker_latency_p50_ms=result["latency_ms"]["rerank"]["p50"] or 0.0,
        reranker_latency_p95_ms=result["latency_ms"]["rerank"]["p95"] or 0.0,
        retrieval_latency_p50_ms=result["latency_ms"]["total"]["p50"] or 0.0,
        retrieval_latency_p95_ms=result["latency_ms"]["total"]["p95"] or 0.0,
        selected=selection.selected,
        notes=f"Task 3.6: cross-encoder rerank ({config['reranker']['model_repository']}) over Task "
              f"3.5-selected dense-only candidate pool (base_k={BASE_K}). Selection: {selection.rationale}",
    )
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    report = {
        "task": "3.6", "phase3_6_config_hash": config_hash, "phase3_6_config": config,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": baseline["phase3_config"]["phase3_dev_scope_sha256"],
        "question_count": result["question_count"], "chunk_config_hash": CHUNK_CONFIG_HASH,
        "chunk_count": EXPECTED_CHUNK_COUNT, "corpus_document_count": corpus_doc_count,
        "no_rerank_baseline": {"model_repository": config["base_retrieval"]["model_repository"], "metrics": bm},
        "reranker": {"model_repository": config["reranker"]["model_repository"],
                     "model_revision": config["reranker"]["model_revision"],
                     "reranker_identity_hash": result["reranker_identity_hash"], "metrics": rm},
        "deltas_vs_no_rerank": deltas,
        "bootstrap": {"mrr_ci": [mrr_boot.ci_lo, mrr_boot.ci_hi], "ndcg_ci": [ndcg_boot.ci_lo, ndcg_boot.ci_hi],
                      "seed": p3a.BOOTSTRAP_SEED, "iterations": p3a.BOOTSTRAP_ITERATIONS},
        "hit_gain_loss_at_5": hit_gain_loss_5, "recall5_hit_delta": recall5_hit_delta,
        "selection": selection.to_dict(), "ablation_row": row,
        "limitations": [
            "Evaluated only over the frozen Task 3.1 89-question DEV/evaluable-subset (4.9% of full DEV).",
            "N=89 is small; bootstrap CIs govern which reranked-vs-no-rerank differences are credible.",
            "Only cross-encoder/ms-marco-MiniLM-L6-v2 was benchmarked - the roadmap's optional larger "
            "quality-ceiling comparison was explicitly deferred, not attempted in this round.",
            "doc_recall@50 is mathematically identical before/after reranking (same candidate set, only "
            "reordered) - never claimed as an improvement.",
            "chunk_recall@10, chunk_mrr, faithfulness, citation_grounding, and generation metrics remain N/A.",
        ],
        "next_task_readiness": f"Selected retrieval mode for the next task: {selection.selected}. {selection.rationale}",
    }
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.6 report written: {FINAL_RESULT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.6 - Phase 3 cross-encoder reranking.")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.plan:
        return cmd_plan()
    if args.status:
        return cmd_status()
    if args.run:
        return run_full()
    if args.compare:
        return cmd_compare()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
