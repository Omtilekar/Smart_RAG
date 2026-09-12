"""Task 3.5 - Reciprocal Rank Fusion (RRF) hybrid retrieval over the two
already-frozen Phase 3 retrieval components: the Task 3.3 dense winner
(Qwen/Qwen3-Embedding-0.6B) and the Task 3.4 sparse LanceDB-native FTS
baseline. Fusion only - chunking, the dense model/index, and the sparse
index are never rebuilt, retrained, or retuned here.

Neither parent's full top-50 ranked chunk list was persisted with self-
verifying provenance in a form suitable for direct reuse (see
configs/phase_3_5_rrf_hybrid_fusion.json's `parent_stream_reuse_policy`),
so this script reruns RETRIEVAL ONLY for both parents against their
already-frozen, unmodified artifacts - no embeddings are recomputed, no
index is rebuilt. Every rerun per-question metric is verified to
reproduce the frozen Task 3.3/3.4 values exactly before fusion proceeds.

Never imports src.eval.test_access - Task 3.5 evaluation is DEV-only.

Usage:
    python -u scripts/run_phase3_rrf_hybrid.py --plan
    python -u scripts/run_phase3_rrf_hybrid.py --run
    python -u scripts/run_phase3_rrf_hybrid.py --compare
    python -u scripts/run_phase3_rrf_hybrid.py --status
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
from src.index import lancedb_fts as fts  # noqa: E402
from src.retrieval.baseline import _to_results as _to_results_dense  # noqa: E402
from src.retrieval.sparse import SparseRetriever  # noqa: E402
from src.retrieval.fusion import rrf_fuse, FusionError  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_ablation as p3a  # noqa: E402
from src.eval import phase3_hybrid as p3h  # noqa: E402
from src.eval.metrics import first_hit_rank, reciprocal_rank, mean_reciprocal_rank, ndcg_at_k, hit_at_k  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402

from scripts.run_phase3_chunking_ablation import _p50_p95, bootstrap_vs_reference  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_5_rrf_hybrid_fusion.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
TASK32_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"
TASK33_RESULT_PATH = REPO_ROOT / "results" / "phase_3_3_embedding_model_benchmark.json"
TASK33_QWEN_RESULT_PATH = REPO_ROOT / "results" / "phase3_3" / "qwen3_embedding.json"
TASK34_RESULT_PATH = REPO_ROOT / "results" / "phase_3_4_bm25_fts_baseline.json"
TASK34_SPARSE_RESULT_PATH = REPO_ROOT / "results" / "phase3_4" / "bm25_fts.json"
SPLIT_SUMMARY_PATH = REPO_ROOT / "results" / "phase_2_4_split_summary.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_5"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_5_rrf_hybrid_fusion.json"

ROW_ID = "hybrid_rrf"
CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
CHUNK_SCHEMA_VERSION = 1
EXPECTED_CHUNK_COUNT = 323971

RRF_K = 60
DENSE_K = 50
SPARSE_K = 50
FINAL_K = 50
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
    return question_ids, baseline


def load_dev_questions() -> dict:
    return _load_json(REPO_ROOT / "results" / "phase_2_4_dev.json")


def verify_frozen_chunks(storage) -> "pq.Table":
    task32 = _load_json(TASK32_RESULT_PATH)
    winner_hash = task32["final_winner"]["chunk_config_hash"]
    if winner_hash != CHUNK_CONFIG_HASH:
        raise SystemExit(f"FATAL: Task 3.2 final_winner chunk_config_hash {winner_hash} != expected. STOP.")
    path = storage.chunks_dir(CHUNK_CONFIG_HASH) / "chunks.parquet"
    table = pq.read_table(path)
    if table.num_rows != EXPECTED_CHUNK_COUNT:
        raise SystemExit(f"FATAL: chunk artifact has {table.num_rows} rows, expected {EXPECTED_CHUNK_COUNT}")
    return table


def verify_frozen_dense_winner() -> dict:
    task33 = _load_json(TASK33_RESULT_PATH)
    if task33["final_winner_candidate_id"] != "qwen3_embedding":
        raise SystemExit(f"FATAL: Task 3.3 winner changed to {task33['final_winner_candidate_id']!r}. STOP.")
    return _load_json(TASK33_QWEN_RESULT_PATH)


def verify_frozen_sparse_baseline() -> dict:
    if not TASK34_SPARSE_RESULT_PATH.is_file():
        raise SystemExit(f"FATAL: Task 3.4 sparse result missing at {TASK34_SPARSE_RESULT_PATH}")
    sparse = _load_json(TASK34_SPARSE_RESULT_PATH)
    task34 = _load_json(TASK34_RESULT_PATH)
    if task34["sparse_result"]["metrics"] != sparse["metrics"]:
        raise SystemExit("FATAL: Task 3.4 final result and per-candidate result metrics disagree. STOP.")
    return sparse


def _current_ablation_rows_have(row_id: str) -> bool:
    rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    return any(str(r["row_id"]) == row_id for r in rows)


# --------------------------------------------------------------- Stage 6: synthetic RRF smoke

def run_synthetic_rrf_smoke() -> None:
    print("[SMOKE] synthetic RRF correctness (rrf_k=60)")

    class _R:
        def __init__(self, chunk_id, rank, **extra):
            self.chunk_id, self.rank = chunk_id, rank
            for k, v in extra.items():
                setattr(self, k, v)

    common = dict(document_id="d1", text="t", cik=1, company="C", form_type="10-K", fiscal_year=2020,
                  source="s", source_filename="f", source_split="dev", ordinal=0, token_count=1,
                  chunk_config_hash="h" * 64)

    dense = [_R("A", 1, distance=0.1, score=0.9, **common), _R("B", 2, distance=0.2, score=0.8, **common)]
    sparse = [_R("B", 1, sparse_score=5.0, **common), _R("C", 2, sparse_score=3.0, **common)]
    fused = rrf_fuse(dense, sparse, rrf_k=60, limit=10)
    by_id = {f.chunk_id: f.rrf_score for f in fused}
    expected_a = 1 / 61
    expected_b = 1 / 62 + 1 / 61
    expected_c = 1 / 62
    assert abs(by_id["A"] - expected_a) < 1e-12, by_id
    assert abs(by_id["B"] - expected_b) < 1e-12, by_id
    assert abs(by_id["C"] - expected_c) < 1e-12, by_id
    assert [f.chunk_id for f in fused] == ["B", "A", "C"], [f.chunk_id for f in fused]
    print(f"[SMOKE] ok  A={by_id['A']:.6f} B={by_id['B']:.6f} C={by_id['C']:.6f}  order=B>A>C")

    try:
        rrf_fuse([_R("A", 1, **common), _R("A", 2, **common)], [], rrf_k=60, limit=10)
        raise SystemExit("FATAL: duplicate chunk_id within one stream was not rejected.")
    except FusionError as exc:
        print(f"[SMOKE] ok  duplicate chunk_id rejected: {exc}")


# --------------------------------------------------------------- parent retrieval (rerun, no rebuild)

def _doc_metrics_for(ranked_document_ids: list[str], target_id: str) -> dict:
    rank10 = first_hit_rank(ranked_document_ids, {target_id}, k=DOC_RECALL_K)
    hit10 = hit_at_k(rank10, DOC_RECALL_K)
    rr10 = reciprocal_rank(rank10)
    relevances10 = p3.document_relevances_at_k(ranked_document_ids, target_id, k=DOC_RECALL_K)
    ndcg10 = ndcg_at_k(relevances10, num_relevant=1, k=DOC_RECALL_K)
    rank50 = first_hit_rank(ranked_document_ids, {target_id}, k=len(ranked_document_ids))
    hit50 = hit_at_k(rank50, len(ranked_document_ids))
    return {"hit10": hit10, "rank10": rank10, "rr10": rr10, "ndcg10": ndcg10, "hit50": hit50, "rank50": rank50}


def verify_parent_reproduces(recomputed: dict, frozen_per_question: dict, *, label: str, question_ids: list[str]) -> None:
    for qid in question_ids:
        r, f = recomputed[qid], frozen_per_question[qid]
        for field in ("hit10", "rank10", "rr10", "ndcg10", "hit50", "rank50"):
            rv, fv = r[field], f[field]
            if isinstance(rv, float) or isinstance(fv, float):
                ok = (rv is None and fv is None) or (rv is not None and fv is not None and abs(rv - fv) < 1e-9)
            else:
                ok = rv == fv
            if not ok:
                raise SystemExit(
                    f"FATAL: {label} parent drift on {qid} field {field}: recomputed={rv!r} != frozen={fv!r}. STOP."
                )
    print(f"[HYBRID] {label} parent reproduces frozen metrics exactly ({len(question_ids)} questions).")


# --------------------------------------------------------------- CLI actions

def cmd_plan() -> int:
    config, config_hash = load_experiment_config()
    print("[STAGE 3/10] Frozen Task 3.5 RRF hybrid contract")
    print(f"phase3_5_config_hash: {config_hash}")
    print(json.dumps(config, indent=2))
    return 0


def cmd_status() -> int:
    print("Task 3.5 status (read-only)")
    path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not path.is_file():
        print(f"  {ROW_ID}: not run")
        return 0
    result = _load_json(path)
    m = result.get("metrics")
    if m:
        print(f"  {ROW_ID}: recall@10={m['doc_recall_at_10']:.4f} recall@50={m['doc_recall_at_50']:.4f} "
              f"mrr={m['doc_mrr']:.4f} ndcg@10={m['doc_ndcg_at_10']:.4f}")
    return 0


def run_full() -> int:
    print("[STAGE 1/10] Task 3.5 preflight")
    frozen_scope_ids, baseline = load_frozen_scope()
    p3a.assert_dev_split("dev")
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    qwen = verify_frozen_dense_winner()
    sparse_frozen = verify_frozen_sparse_baseline()
    if not _current_ablation_rows_have("qwen3_embedding") or not _current_ablation_rows_have("bm25_fts"):
        raise SystemExit("FATAL: Task 3.3/3.4 ablation rows missing from results/phase_3_ablation_table.csv. STOP.")
    print(f"Frozen scope verified: {len(frozen_scope_ids)} questions. Chunks: {chunk_table.num_rows}. "
          f"Dense: {qwen['repository']}@{qwen['revision'][:12]}. Sparse: bm25_fts (Task 3.4).")

    config, config_hash = load_experiment_config()

    print("[STAGE 2/10] Verify dense and sparse parent streams")
    dev_payload = load_dev_questions()
    questions_by_id = {q["question_id"]: q for q in dev_payload["questions"]}
    scoped_questions = [questions_by_id[qid] for qid in frozen_scope_ids]

    spec = mr.CANDIDATES_BY_ID["qwen3_embedding"]
    print("[HYBRID] validating dense parent...")
    model = mr.load_model(spec, device="cuda")
    dense_db = open_dense_db(storage.index_dir(CHUNK_CONFIG_HASH, spec.repository))
    dense_table = open_chunk_table(dense_db)

    print("[HYBRID] validating sparse parent...")
    sparse_db = fts.open_database(storage.index_dir(CHUNK_CONFIG_HASH, fts.SPARSE_ARTIFACT_KEY))
    sparse_table = fts.open_sparse_table(sparse_db)
    sparse_retriever = SparseRetriever(sparse_table)

    print("[STAGE 4/10] RRF fusion primitive ready (src/retrieval/fusion.py)")
    print("[STAGE 5/10] Hybrid retriever boundary ready (src/retrieval/hybrid.py)")

    print("[STAGE 6/10] Validate RRF behavior")
    run_synthetic_rrf_smoke()
    for q in scoped_questions[:3]:
        qvec = mr.encode_queries(spec, model, [q["question"]], batch_size=1)[0]
        dense_preview = _to_results_dense(exact_cosine_search(dense_table, qvec, limit=5, expected_dimension=spec.dimension))
        sparse_preview = sparse_retriever.retrieve(q["question"], k=5)
        fused_preview = rrf_fuse(dense_preview, sparse_preview, rrf_k=RRF_K, limit=5)
        print(f"[SMOKE] {q['question_id']}: dense_top3={[r.chunk_id for r in dense_preview[:3]]} "
              f"sparse_top3={[r.chunk_id for r in sparse_preview[:3]]} "
              f"fused_top3={[(r.chunk_id, round(r.rrf_score, 5)) for r in fused_preview[:3]]}")

    print("[STAGE 7/10] Evaluate RRF hybrid retrieval "
          "(also verifies each parent reproduces its frozen Task 3.3/3.4 per-question metrics)")
    diagnostics_path = storage.eval_dir("phase3_5_rrf_hybrid_fusion") / "query_diagnostics.jsonl"
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)

    n = len(scoped_questions)
    per_question: dict[str, dict] = {}
    dense_pq, sparse_pq = {}, {}
    rr10_values, ndcg10_values, hit10_flags, hit50_flags = [], [], [], []
    dense_ms, sparse_ms, fusion_ms_list, total_ms = [], [], [], []
    top10_entries, top50_entries = [], []

    t0 = time.perf_counter()
    with open(diagnostics_path, "w", encoding="utf-8") as diag_f:
        for i, q in enumerate(scoped_questions, start=1):
            qid = q["question_id"]
            target_id = p3.question_target_document_ids(q)[0]

            s0 = time.perf_counter()
            qvec = mr.encode_queries(spec, model, [q["question"]], batch_size=1)[0]
            dense_arrow = exact_cosine_search(dense_table, qvec, limit=DENSE_K, expected_dimension=spec.dimension)
            dense_results = _to_results_dense(dense_arrow)
            s1 = time.perf_counter()
            sparse_results = sparse_retriever.retrieve(q["question"], k=SPARSE_K)
            s2 = time.perf_counter()
            fused = rrf_fuse(dense_results, sparse_results, rrf_k=RRF_K, limit=FINAL_K)
            s3 = time.perf_counter()

            dense_pq[qid] = _doc_metrics_for([r.document_id for r in dense_results], target_id)
            sparse_pq[qid] = _doc_metrics_for([r.document_id for r in sparse_results], target_id)

            if len(fused) != FINAL_K:
                raise SystemExit(f"FATAL: {qid}: hybrid returned {len(fused)} results, expected {FINAL_K}")

            ranked_document_ids = [r.document_id for r in fused]
            m = _doc_metrics_for(ranked_document_ids, target_id)
            per_question[qid] = {"target_document_id": target_id, **m}

            hit10_flags.append(m["hit10"])
            hit50_flags.append(m["hit50"])
            rr10_values.append(m["rr10"])
            ndcg10_values.append(m["ndcg10"])

            dense_ms.append((s1 - s0) * 1000)
            sparse_ms.append((s2 - s1) * 1000)
            fusion_ms_list.append((s3 - s2) * 1000)
            total_ms.append((s3 - s0) * 1000)

            top10_entries.extend({"in_dense": r.in_dense, "in_sparse": r.in_sparse} for r in fused[:10])
            top50_entries.extend({"in_dense": r.in_dense, "in_sparse": r.in_sparse} for r in fused[:50])

            diag_f.write(json.dumps({
                "question_id": qid, "gold_document_ids": [target_id],
                "dense_ranked_chunk_ids": [r.chunk_id for r in dense_results],
                "sparse_ranked_chunk_ids": [r.chunk_id for r in sparse_results],
                "hybrid_ranked_chunk_ids": [r.chunk_id for r in fused],
                "hybrid_ranked_document_ids": ranked_document_ids,
                "fused": [{"chunk_id": r.chunk_id, "rrf_score": r.rrf_score, "dense_rank": r.dense_rank,
                           "sparse_rank": r.sparse_rank, "in_dense": r.in_dense, "in_sparse": r.in_sparse}
                          for r in fused],
                "first_gold_hit_rank": m["rank50"], "hit_at_10": m["hit10"], "hit_at_50": m["hit50"],
                "reciprocal_rank": m["rr10"], "ndcg_at_10": m["ndcg10"],
                "dense_retrieval_ms": (s1 - s0) * 1000, "sparse_retrieval_ms": (s2 - s1) * 1000,
                "fusion_ms": (s3 - s2) * 1000, "total_hybrid_retrieval_ms": (s3 - s0) * 1000,
            }) + "\n")

            if i % EVAL_PROGRESS_EVERY == 0 or i == n:
                avg_ms = sum(total_ms) / len(total_ms)
                print(f"[HYBRID EVAL]  {i}/{n}  {100*i/n:5.1f}%  R10_hits={sum(hit10_flags)}  "
                      f"R50_hits={sum(hit50_flags)}  avg_ms={avg_ms:.1f}", flush=True)
    run_seconds = time.perf_counter() - t0

    verify_parent_reproduces(dense_pq, qwen["per_question"], label="dense", question_ids=frozen_scope_ids)
    verify_parent_reproduces(sparse_pq, sparse_frozen["per_question"], label="sparse", question_ids=frozen_scope_ids)
    print("[HYBRID] parents reproduce frozen metrics")

    hits10, hits50 = sum(hit10_flags), sum(hit50_flags)
    metrics = {
        "doc_recall_at_10": hits10 / n, "doc_recall_at_10_hits": hits10,
        "doc_recall_at_50": hits50 / n, "doc_recall_at_50_hits": hits50,
        "doc_mrr": mean_reciprocal_rank(rr10_values), "doc_ndcg_at_10": sum(ndcg10_values) / len(ndcg10_values),
    }
    print(f"[HYBRID EVAL] doc_recall@10={metrics['doc_recall_at_10']:.4f} doc_recall@50={metrics['doc_recall_at_50']:.4f} "
          f"doc_mrr={metrics['doc_mrr']:.4f} doc_ndcg@10={metrics['doc_ndcg_at_10']:.4f}")

    composition_top10 = p3h.fusion_composition_counts(top10_entries)
    composition_top50 = p3h.fusion_composition_counts(top50_entries)
    print(f"Fusion composition top10: {composition_top10}  top50: {composition_top50}")

    split_summary = _load_json(SPLIT_SUMMARY_PATH)
    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": qwen["repository"], "model_revision": qwen["revision"],
            "embedding_dimension": qwen["dimension"], "vector_dtype": "float32",
            "normalize_embeddings": qwen["normalize_embeddings"], "identity_hash": qwen["embedding_identity_hash"],
        },
        index_identity_hash=qwen["index_identity_hash"],
        retrieval_config={"type": "rrf_hybrid", "rrf_k": RRF_K, "dense_k": DENSE_K, "sparse_k": SPARSE_K,
                           "final_k": FINAL_K, "sparse_index_identity_hash": sparse_frozen["sparse_index_identity_hash"]},
        reranker_config={"enabled": False}, generation_model=None, split="dev",
        eval_set_version="phase2-v1", split_version="phase2-split-v1", split_sha256=split_summary["dev_sha256"],
        metrics=metrics, evaluation_source="internal_phase2",
        experiment_name="phase3_5_rrf_hybrid_fusion", run_kind="phase3_rrf_hybrid_retrieval",
        notes=f"Task 3.5 RRF hybrid fusion (rrf_k={RRF_K}) of frozen Qwen dense + Task 3.4 sparse over "
              f"chunks ({CHUNK_CONFIG_HASH[:12]}...).",
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[HYBRID EVAL] Task 2.11 run record written: {run_record_path}")

    payload = {
        "row_id": ROW_ID, "chunk_config_hash": CHUNK_CONFIG_HASH, "config_hash": config_hash,
        "run_id": run_record.run_id, "git_sha": git_sha(),
        "question_count": n, "metrics": metrics, "per_question": per_question,
        "composition_top10": composition_top10, "composition_top50": composition_top50,
        "latency_ms": {"dense": _p50_p95(dense_ms), "sparse": _p50_p95(sparse_ms),
                       "fusion": _p50_p95(fusion_ms_list), "total": _p50_p95(total_ms)},
        "run_seconds": round(run_seconds, 3), "diagnostics_path": str(diagnostics_path),
    }
    _write_json(CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json", payload)
    return 0


def cmd_compare() -> int:
    print("[STAGE 8/10] Analyze hybrid deltas")
    hybrid_path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not hybrid_path.is_file():
        raise SystemExit("Not run yet - run --run first.")
    hybrid_result = _load_json(hybrid_path)
    frozen_scope_ids, baseline = load_frozen_scope()

    dense_result = _load_json(TASK33_QWEN_RESULT_PATH)
    sparse_result = _load_json(TASK34_SPARSE_RESULT_PATH)

    bootstrap_vs_dense = bootstrap_vs_reference(hybrid_result, dense_result, frozen_scope_ids)
    bootstrap_vs_sparse = bootstrap_vs_reference(hybrid_result, sparse_result, frozen_scope_ids)

    hm, dm, sm = hybrid_result["metrics"], dense_result["metrics"], sparse_result["metrics"]
    deltas_vs_dense = {
        "recall10": hm["doc_recall_at_10"] - dm["doc_recall_at_10"], "recall50": hm["doc_recall_at_50"] - dm["doc_recall_at_50"],
        "mrr": hm["doc_mrr"] - dm["doc_mrr"], "ndcg10": hm["doc_ndcg_at_10"] - dm["doc_ndcg_at_10"],
    }
    deltas_vs_sparse = {
        "recall10": hm["doc_recall_at_10"] - sm["doc_recall_at_10"], "recall50": hm["doc_recall_at_50"] - sm["doc_recall_at_50"],
        "mrr": hm["doc_mrr"] - sm["doc_mrr"], "ndcg10": hm["doc_ndcg_at_10"] - sm["doc_ndcg_at_10"],
    }

    hit_gain_loss_10 = p3h.gain_loss_counts(dense_result["per_question"], hybrid_result["per_question"], frozen_scope_ids, hit_field="hit10")
    hit_gain_loss_50 = p3h.gain_loss_counts(dense_result["per_question"], hybrid_result["per_question"], frozen_scope_ids, hit_field="hit50")
    rank_moves = p3h.rank_movement_counts(dense_result["per_question"], hybrid_result["per_question"], frozen_scope_ids, rank_field="rank10")

    print(f"Hybrid vs Qwen dense: delta_recall10={deltas_vs_dense['recall10']:+.4f} "
          f"delta_recall50={deltas_vs_dense['recall50']:+.4f} delta_mrr={deltas_vs_dense['mrr']:+.4f} "
          f"delta_ndcg10={deltas_vs_dense['ndcg10']:+.4f}")
    print(f"Hybrid vs sparse: delta_recall10={deltas_vs_sparse['recall10']:+.4f} "
          f"delta_recall50={deltas_vs_sparse['recall50']:+.4f} delta_mrr={deltas_vs_sparse['mrr']:+.4f} "
          f"delta_ndcg10={deltas_vs_sparse['ndcg10']:+.4f}")
    print(f"hit@10 vs dense: gained={hit_gain_loss_10['gained']} lost={hit_gain_loss_10['lost']} "
          f"unchanged={hit_gain_loss_10['unchanged']}")
    print(f"hit@50 vs dense: gained={hit_gain_loss_50['gained']} lost={hit_gain_loss_50['lost']} "
          f"unchanged={hit_gain_loss_50['unchanged']}")
    print(f"rank10 movement vs dense: {rank_moves}")
    print(f"Fusion composition top10: {hybrid_result['composition_top10']}")
    print(f"Fusion composition top50: {hybrid_result['composition_top50']}")

    print("[STAGE 9/10] Select hybrid retrieval configuration")
    selection = p3h.select_hybrid_configuration(
        hybrid_metrics=hm, dense_metrics=dm, question_count=hybrid_result["question_count"],
        recall10_hit_delta=bootstrap_vs_dense["recall10_hit_delta"],
        mrr_ci=bootstrap_vs_dense["mrr_ci"], ndcg_ci=bootstrap_vs_dense["ndcg_ci"],
    )
    if selection.flagged_for_user_decision:
        raise SystemExit(f"STOP - Task 3.5 requires a user decision: {selection.flag_reason}")
    print(f"Selected: {selection.selected} - {selection.rationale}")

    config, config_hash = load_experiment_config()
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    corpus_doc_count = len(set(chunk_table.column("document_id").to_pylist()))

    row = p3h.build_hybrid_ablation_row(
        row_id=ROW_ID, config_hash=config_hash, run_id=hybrid_result["run_id"], git_sha=hybrid_result["git_sha"],
        eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
        question_count=hybrid_result["question_count"], corpus_document_count=corpus_doc_count,
        chunk_count=EXPECTED_CHUNK_COUNT, chunk_config_hash=CHUNK_CONFIG_HASH,
        dense_repository=config["dense_parent"]["model_repository"], dense_revision=config["dense_parent"]["model_revision"],
        dense_embedding_identity_hash=dense_result["embedding_identity_hash"],
        dense_index_identity_hash=dense_result["index_identity_hash"],
        sparse_index_identity_hash_value=sparse_result["sparse_index_identity_hash"],
        rrf_k=RRF_K, dense_candidate_k=DENSE_K, sparse_candidate_k=SPARSE_K, final_candidate_k=FINAL_K,
        metrics=hm, deltas_vs_dense=deltas_vs_dense, deltas_vs_sparse=deltas_vs_sparse,
        hit_gain_loss_10=hit_gain_loss_10, hit_gain_loss_50=hit_gain_loss_50,
        composition_top10=hybrid_result["composition_top10"], composition_top50=hybrid_result["composition_top50"],
        dense_latency_p50_ms=hybrid_result["latency_ms"]["dense"]["p50"] or 0.0,
        sparse_latency_p50_ms=hybrid_result["latency_ms"]["sparse"]["p50"] or 0.0,
        fusion_latency_p50_ms=hybrid_result["latency_ms"]["fusion"]["p50"] or 0.0,
        hybrid_latency_p50_ms=hybrid_result["latency_ms"]["total"]["p50"] or 0.0,
        hybrid_latency_p95_ms=hybrid_result["latency_ms"]["total"]["p95"] or 0.0,
        selected=selection.selected,
        notes=f"Task 3.5: RRF (rrf_k={RRF_K}) fusion of qwen3_embedding dense + bm25_fts sparse. "
              f"Gate 1 (R@50 preservation): {'PASS' if hm['doc_recall_at_50_hits'] == hybrid_result['question_count'] else 'FAIL'}. "
              f"Selection: {selection.rationale}",
    )
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    report = {
        "task": "3.5", "phase3_5_config_hash": config_hash, "phase3_5_config": config,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": baseline["phase3_config"]["phase3_dev_scope_sha256"],
        "question_count": hybrid_result["question_count"], "chunk_config_hash": CHUNK_CONFIG_HASH,
        "chunk_count": EXPECTED_CHUNK_COUNT, "corpus_document_count": corpus_doc_count,
        "dense_parent": {"model_repository": config["dense_parent"]["model_repository"],
                          "model_revision": config["dense_parent"]["model_revision"],
                          "embedding_identity_hash": dense_result["embedding_identity_hash"],
                          "index_identity_hash": dense_result["index_identity_hash"], "metrics": dm},
        "sparse_parent": {"row_id": "bm25_fts", "sparse_index_identity_hash": sparse_result["sparse_index_identity_hash"],
                           "metrics": sm},
        "rrf": {"rrf_k": RRF_K, "dense_candidate_k": DENSE_K, "sparse_candidate_k": SPARSE_K, "final_candidate_k": FINAL_K,
                "fusion_union_key": "chunk_id", "tie_break": config["fusion"]["tie_break"]},
        "hybrid_result": hybrid_result,
        "paired_hybrid_vs_dense": {"deltas": deltas_vs_dense,
                                    "bootstrap": {k: v for k, v in bootstrap_vs_dense.items() if k != "notable_rank_moves"}},
        "paired_hybrid_vs_sparse": {"deltas": deltas_vs_sparse,
                                     "bootstrap": {k: v for k, v in bootstrap_vs_sparse.items() if k != "notable_rank_moves"}},
        "hit_gain_loss_vs_dense": {"hit_at_10": hit_gain_loss_10, "hit_at_50": hit_gain_loss_50},
        "rank10_movement_vs_dense": rank_moves,
        "fusion_composition": {"top10": hybrid_result["composition_top10"], "top50": hybrid_result["composition_top50"]},
        "selection": selection.to_dict(),
        "ablation_row": row,
        "limitations": [
            "Evaluated only over the frozen Task 3.1 89-question DEV/evaluable-subset (4.9% of full DEV).",
            "N=89 is small; bootstrap CIs govern which hybrid-vs-dense/sparse differences are credible.",
            "doc_recall@50 was already at ceiling (89/89) for the dense parent, so hybrid cannot improve it - "
            "Gate 1 in the selection rule treats exact preservation as the bar, not improvement.",
            "No reranking, CRAG, router, or metadata pre-filtering - RRF fusion only.",
            "chunk_recall@10, chunk_mrr, precision@5, faithfulness, citation_grounding, and generation "
            "metrics remain N/A.",
        ],
        "next_task_readiness": (
            f"Selected retrieval mode for the next task: {selection.selected}. {selection.rationale}"
        ),
    }
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.5 report written: {FINAL_RESULT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.5 - Phase 3 RRF hybrid fusion.")
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
