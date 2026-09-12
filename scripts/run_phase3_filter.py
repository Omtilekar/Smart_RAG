"""Task 3.9 - metadata (CIK + fiscal_year) pre-filtering over the frozen
Task 3.3 dense index. `form_type`/`section` are not implemented as real
filters (form_type is a constant '10-K' across the whole frozen chunk
artifact; there is no section column at all - see
configs/phase_3_9_metadata_prefiltering.json's `filter_dimension_decision`).

cik/fiscal_year are extracted from each question's raw TEXT ONLY via
Task 3.8's frozen `src.router.rules.classify_intent()` - never from the
question record's own hidden ground-truth fields (that would be test
leakage). A question filters only if the router resolves exactly one
distinct cik AND exactly one distinct fiscal_year; otherwise it falls
back to unfiltered dense search, recorded explicitly.

Never imports src.eval.test_access - Task 3.9 evaluation is DEV-only.

Usage:
    python -u scripts/run_phase3_filter.py --plan
    python -u scripts/run_phase3_filter.py --run
    python -u scripts/run_phase3_filter.py --compare
    python -u scripts/run_phase3_filter.py --status
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
from src.index.lancedb_index import open_database as open_dense_db, open_chunk_table  # noqa: E402
from src.retrieval.filtered import MetadataFilteredRetriever  # noqa: E402
from src.eval.tag_registry import get_registry  # noqa: E402
from src.router.rules import CompanyGazetteer, classify_intent  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_ablation as p3a  # noqa: E402
from src.eval import phase3_filter as p3f  # noqa: E402
from src.eval.metrics import first_hit_rank, reciprocal_rank, mean_reciprocal_rank, ndcg_at_k, hit_at_k  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402

from scripts.run_phase3_chunking_ablation import _p50_p95, bootstrap_vs_reference  # noqa: E402
from scripts.run_phase3_router import build_gazetteer_from_dev  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_9_metadata_prefiltering.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
TASK32_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"
TASK33_QWEN_RESULT_PATH = REPO_ROOT / "results" / "phase3_3" / "qwen3_embedding.json"
SPLIT_SUMMARY_PATH = REPO_ROOT / "results" / "phase_2_4_split_summary.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_9"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_9_metadata_prefiltering.json"

ROW_ID = "metadata_prefilter"
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
    if ids_hash != config["question_ids_sha256"]:
        raise SystemExit("FATAL: frozen 89-question scope does not reproduce. STOP.")
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


def _doc_metrics_for(ranked_document_ids: list[str], target_id: str) -> dict:
    rank10 = first_hit_rank(ranked_document_ids, {target_id}, k=DOC_RECALL_K)
    hit10 = hit_at_k(rank10, DOC_RECALL_K)
    rr10 = reciprocal_rank(rank10)
    relevances10 = p3.document_relevances_at_k(ranked_document_ids, target_id, k=DOC_RECALL_K)
    ndcg10 = ndcg_at_k(relevances10, num_relevant=1, k=DOC_RECALL_K)
    rank50 = first_hit_rank(ranked_document_ids, {target_id}, k=len(ranked_document_ids))
    hit50 = hit_at_k(rank50, len(ranked_document_ids))
    return {"hit10": hit10, "rank10": rank10, "rr10": rr10, "ndcg10": ndcg10, "hit50": hit50, "rank50": rank50}


def verify_parent_reproduces(recomputed: dict, frozen_per_question: dict, *, question_ids: list[str]) -> None:
    for qid in question_ids:
        r, f = recomputed[qid], frozen_per_question[qid]
        for field in ("hit10", "rank10", "rr10", "ndcg10", "hit50", "rank50"):
            rv, fv = r[field], f[field]
            ok = (rv is None and fv is None) or (rv is not None and fv is not None and abs(rv - fv) < 1e-9) \
                if isinstance(rv, float) or isinstance(fv, float) else rv == fv
            if not ok:
                raise SystemExit(f"FATAL: baseline drift on {qid} field {field}: recomputed={rv!r} != frozen={fv!r}. STOP.")
    print(f"[FILTER] unfiltered baseline reproduces frozen Task 3.3 metrics exactly ({len(question_ids)} questions).")


# --------------------------------------------------------------- CLI actions

def cmd_plan() -> int:
    config, config_hash = load_experiment_config()
    print("[STAGE 3/10] Frozen Task 3.9 metadata pre-filtering contract")
    print(f"phase3_9_config_hash: {config_hash}")
    print(json.dumps(config, indent=2))
    return 0


def cmd_status() -> int:
    print("Task 3.9 status (read-only)")
    path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not path.is_file():
        print(f"  {ROW_ID}: not run")
        return 0
    result = _load_json(path)
    m = result["filtered_metrics"]
    print(f"  {ROW_ID}: recall@10={m['doc_recall_at_10']:.4f} recall@50={m['doc_recall_at_50']:.4f} "
          f"mrr={m['doc_mrr']:.4f} ndcg@10={m['doc_ndcg_at_10']:.4f} "
          f"filtered={result['filtered_question_count']}/{result['question_count']}")
    return 0


def run_full() -> int:
    print("[STAGE 1/10] Task 3.9 preflight")
    frozen_scope_ids, baseline = load_frozen_scope()
    p3a.assert_dev_split("dev")
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    qwen = _load_json(TASK33_QWEN_RESULT_PATH)
    config, config_hash = load_experiment_config()
    print(f"Frozen scope verified: {len(frozen_scope_ids)} questions. Chunks: {chunk_table.num_rows}.")

    print("[STAGE 2/10] Load dense retriever + router gazetteer/registry")
    dev_payload = load_dev_questions()
    questions_by_id = {q["question_id"]: q for q in dev_payload["questions"]}
    scoped_questions = [questions_by_id[qid] for qid in frozen_scope_ids]

    dense_spec = mr.CANDIDATES_BY_ID["qwen3_embedding"]
    dense_model = mr.load_model(dense_spec, device="cuda")
    dense_db = open_dense_db(storage.index_dir(CHUNK_CONFIG_HASH, dense_spec.repository))
    dense_table = open_chunk_table(dense_db)
    retriever = MetadataFilteredRetriever(dense_spec, dense_model, dense_table)

    gazetteer = CompanyGazetteer(build_gazetteer_from_dev(dev_payload))
    registry = get_registry()

    print("[STAGE 7/10] Evaluate filtered vs unfiltered dense retrieval")
    diagnostics_path = storage.eval_dir("phase3_9_metadata_prefiltering") / "query_diagnostics.jsonl"
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)

    n = len(scoped_questions)
    baseline_pq, filtered_pq = {}, {}
    baseline_ms, filtered_ms = [], []
    filtered_count = 0

    with open(diagnostics_path, "w", encoding="utf-8") as diag_f:
        for i, q in enumerate(scoped_questions, start=1):
            qid = q["question_id"]
            target_id = p3.question_target_document_ids(q)[0]

            s0 = time.perf_counter()
            base_results = retriever.retrieve(q["question"], k=CANDIDATE_K)
            s1 = time.perf_counter()
            baseline_ms.append((s1 - s0) * 1000)
            baseline_pq[qid] = _doc_metrics_for([r.document_id for r in base_results], target_id)

            decision = classify_intent(q["question"], gazetteer=gazetteer, registry=registry)
            ciks = set(decision.resolved_ciks)
            years = set(decision.fiscal_years)
            use_cik = next(iter(ciks)) if len(ciks) == 1 else None
            use_year = next(iter(years)) if len(years) == 1 else None
            will_filter = use_cik is not None and use_year is not None

            s2 = time.perf_counter()
            filt_results = retriever.retrieve(q["question"], k=CANDIDATE_K, cik=use_cik, fiscal_year=use_year)
            s3 = time.perf_counter()
            filtered_ms.append((s3 - s2) * 1000)
            filtered_pq[qid] = _doc_metrics_for([r.document_id for r in filt_results], target_id)
            if will_filter:
                filtered_count += 1

            diag_f.write(json.dumps({
                "question_id": qid, "gold_document_id": target_id,
                "extracted_cik": use_cik, "extracted_fiscal_year": use_year, "was_filtered": will_filter,
                "predicate": retriever.last_stats.predicate,
                "baseline_hit10": baseline_pq[qid]["hit10"], "filtered_hit10": filtered_pq[qid]["hit10"],
                "baseline_ms": (s1 - s0) * 1000, "filtered_ms": (s3 - s2) * 1000,
            }) + "\n")

            if i % 20 == 0 or i == n:
                print(f"[FILTER EVAL]  {i}/{n}  filtered_so_far={filtered_count}  "
                      f"baseline_hits10={sum(1 for v in baseline_pq.values() if v['hit10'])}  "
                      f"filtered_hits10={sum(1 for v in filtered_pq.values() if v['hit10'])}", flush=True)

    verify_parent_reproduces(baseline_pq, qwen["per_question"], question_ids=frozen_scope_ids)

    def _aggregate(per_question: dict) -> dict:
        hits10 = sum(1 for v in per_question.values() if v["hit10"])
        hits50 = sum(1 for v in per_question.values() if v["hit50"])
        return {
            "doc_recall_at_10": hits10 / n, "doc_recall_at_10_hits": hits10,
            "doc_recall_at_50": hits50 / n, "doc_recall_at_50_hits": hits50,
            "doc_mrr": mean_reciprocal_rank([v["rr10"] for v in per_question.values()]),
            "doc_ndcg_at_10": sum(v["ndcg10"] for v in per_question.values()) / n,
        }

    baseline_metrics = _aggregate(baseline_pq)
    filtered_metrics = _aggregate(filtered_pq)
    print(f"[FILTER EVAL] baseline (unfiltered): {baseline_metrics}")
    print(f"[FILTER EVAL] filtered ({filtered_count}/{n} questions filtered): {filtered_metrics}")

    split_summary = _load_json(SPLIT_SUMMARY_PATH)
    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": qwen["repository"], "model_revision": qwen["revision"],
            "embedding_dimension": qwen["dimension"], "vector_dtype": "float32",
            "normalize_embeddings": qwen["normalize_embeddings"], "identity_hash": qwen["embedding_identity_hash"],
        },
        index_identity_hash=qwen["index_identity_hash"],
        retrieval_config={"type": "dense_metadata_prefiltered", "candidate_k": CANDIDATE_K,
                           "filtered_question_count": filtered_count},
        reranker_config={"enabled": False}, generation_model=None, split="dev",
        eval_set_version="phase2-v1", split_version="phase2-split-v1", split_sha256=split_summary["dev_sha256"],
        metrics=filtered_metrics, evaluation_source="internal_phase2",
        experiment_name="phase3_9_metadata_prefiltering", run_kind="phase3_metadata_prefiltering",
        notes=f"Task 3.9 CIK+fiscal_year pre-filtering (router-extracted, {filtered_count}/{n} filtered) "
              f"over dense-only ({CHUNK_CONFIG_HASH[:12]}...).",
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[FILTER EVAL] Task 2.11 run record written: {run_record_path}")

    payload = {
        "row_id": ROW_ID, "chunk_config_hash": CHUNK_CONFIG_HASH, "config_hash": config_hash,
        "run_id": run_record.run_id, "git_sha": git_sha(), "question_count": n,
        "filtered_question_count": filtered_count, "fallback_question_count": n - filtered_count,
        "baseline_metrics": baseline_metrics, "filtered_metrics": filtered_metrics,
        "baseline_per_question": baseline_pq, "filtered_per_question": filtered_pq,
        "latency_ms": {"baseline": _p50_p95(baseline_ms), "filtered": _p50_p95(filtered_ms)},
        "diagnostics_path": str(diagnostics_path),
    }
    _write_json(CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json", payload)
    return 0


def cmd_compare() -> int:
    print("[STAGE 8/10] Analyze filtered vs baseline deltas")
    result_path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not result_path.is_file():
        raise SystemExit("Not run yet - run --run first.")
    result = _load_json(result_path)
    frozen_scope_ids, baseline = load_frozen_scope()

    bm, fm = result["baseline_metrics"], result["filtered_metrics"]
    deltas = {
        "recall10": fm["doc_recall_at_10"] - bm["doc_recall_at_10"], "recall50": fm["doc_recall_at_50"] - bm["doc_recall_at_50"],
        "mrr": fm["doc_mrr"] - bm["doc_mrr"], "ndcg10": fm["doc_ndcg_at_10"] - bm["doc_ndcg_at_10"],
    }
    bootstrap = bootstrap_vs_reference(
        {"per_question": result["filtered_per_question"]}, {"per_question": result["baseline_per_question"]}, frozen_scope_ids,
    )
    print(f"Filtered vs baseline: delta_recall10={deltas['recall10']:+.4f} delta_recall50={deltas['recall50']:+.4f} "
          f"delta_mrr={deltas['mrr']:+.4f} delta_ndcg10={deltas['ndcg10']:+.4f}")

    print("[STAGE 9/10] Select filtering configuration")
    candidates = [
        {"row_id": "baseline", "doc_recall_at_50": bm["doc_recall_at_50"], "doc_mrr": bm["doc_mrr"],
         "doc_ndcg_at_10": bm["doc_ndcg_at_10"], "doc_recall_at_10": bm["doc_recall_at_10"]},
        {"row_id": "filtered", "doc_recall_at_50": fm["doc_recall_at_50"], "doc_mrr": fm["doc_mrr"],
         "doc_ndcg_at_10": fm["doc_ndcg_at_10"], "doc_recall_at_10": fm["doc_recall_at_10"]},
    ]
    selection = p3a.select_round_winner(
        reference_row_id="baseline", candidates=candidates,
        bootstrap_vs_reference={"filtered": {"recall50_hit_delta": fm["doc_recall_at_50_hits"] - bm["doc_recall_at_50_hits"],
                                              "mrr_ci": bootstrap["mrr_ci"], "ndcg_ci": bootstrap["ndcg_ci"]}},
        tiebreak_key_fn=p3f.filtered_tiebreak_key,
    )
    if selection.flagged_for_user_decision:
        raise SystemExit(f"STOP - Task 3.9 requires a user decision: {selection.flag_reason}")
    selected = "metadata_prefilter" if selection.winner_row_id == "filtered" else "no_prefilter"
    print(f"Selected: {selected} - {selection.rationale}")

    config, config_hash = load_experiment_config()
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    corpus_doc_count = len(set(chunk_table.column("document_id").to_pylist()))
    dense_result = _load_json(TASK33_QWEN_RESULT_PATH)

    row = p3f.build_filter_ablation_row(
        row_id=ROW_ID, config_hash=config_hash, run_id=result["run_id"], git_sha=result["git_sha"],
        eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
        question_count=result["question_count"], corpus_document_count=corpus_doc_count,
        chunk_count=EXPECTED_CHUNK_COUNT, chunk_config_hash=CHUNK_CONFIG_HASH,
        dense_repository=config["dense_baseline"]["model_repository"], dense_revision=config["dense_baseline"]["model_revision"],
        dense_embedding_identity_hash=dense_result["embedding_identity_hash"],
        dense_index_identity_hash=dense_result["index_identity_hash"], candidate_k=CANDIDATE_K,
        metrics=fm, deltas=deltas, filtered_question_count=result["filtered_question_count"],
        fallback_question_count=result["fallback_question_count"],
        retrieval_latency_p50_ms=result["latency_ms"]["filtered"]["p50"] or 0.0,
        retrieval_latency_p95_ms=result["latency_ms"]["filtered"]["p95"] or 0.0,
        selected=selected,
        notes=f"Task 3.9: CIK+fiscal_year pre-filter (router-extracted), "
              f"{result['filtered_question_count']}/{result['question_count']} filtered. Selection: {selection.rationale}",
    )
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    report = {
        "task": "3.9", "phase3_9_config_hash": config_hash, "phase3_9_config": config,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": baseline["phase3_config"]["phase3_dev_scope_sha256"],
        "question_count": result["question_count"], "chunk_config_hash": CHUNK_CONFIG_HASH,
        "chunk_count": EXPECTED_CHUNK_COUNT, "corpus_document_count": corpus_doc_count,
        "filtered_question_count": result["filtered_question_count"], "fallback_question_count": result["fallback_question_count"],
        "baseline_metrics": bm, "filtered_metrics": fm, "deltas": deltas,
        "bootstrap": {k: v for k, v in bootstrap.items() if k != "notable_rank_moves"},
        "selection": selection.to_dict(), "ablation_row": row,
        "limitations": [
            "Evaluated only over the frozen Task 3.1 89-question DEV/evaluable-subset (4.9% of full DEV).",
            "Only cik+fiscal_year are real filter dimensions given the frozen chunk artifact - form_type is "
            "constant and section metadata does not exist (Task 3.2 selected fixed, non-section-aware splitting).",
            "cik/fiscal_year are extracted from question text by Task 3.8's router - extraction errors would "
            "cause a wrongly-filtered (and likely missed) query; this evaluation measures that real risk "
            "honestly rather than using oracle ground-truth values.",
            "chunk_recall@10, chunk_mrr, precision@5, faithfulness, citation_grounding, and generation "
            "metrics remain N/A.",
        ],
        "next_task_readiness": f"Selected: {selected}. {selection.rationale}",
    }
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.9 report written: {FINAL_RESULT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.9 - Phase 3 metadata pre-filtering.")
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
