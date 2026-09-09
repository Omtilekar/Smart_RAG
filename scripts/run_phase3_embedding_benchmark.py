"""Task 3.3 - embedding-model-only benchmark against the frozen Task 3.2
chunking winner (fixed 256-token windows, zero overlap;
chunk_config_hash=ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06).

Only the embedding model varies across candidates - chunks, retrieval
backend, distance metric, candidate depth (50), and every metric
implementation are frozen identically to Task 3.2. Reuses Task 1.10/2.6/
3.1 metric code and Task 3.2's chunking-ablation infrastructure
(paired bootstrap, practical-tie rule, winner selection, embedding
checkpointing) unmodified where the logic is generic.

Never imports src.eval.test_access - Task 3.3 evaluation is DEV-only,
using exactly the Task 3.1 frozen 89-question scope loaded verbatim.

Usage:
    python -u scripts/run_phase3_embedding_benchmark.py --plan
    python -u scripts/run_phase3_embedding_benchmark.py --run --resume
    python -u scripts/run_phase3_embedding_benchmark.py --status
    python -u scripts/run_phase3_embedding_benchmark.py --compare
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
import torch  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.artifacts.versioning import semantic_hash, embedding_identity_hash, compute_index_identity_hash  # noqa: E402
from src.embeddings import model_registry as mr  # noqa: E402
from src.index.lancedb_index import (  # noqa: E402
    TABLE_NAME, DISTANCE_METRIC,
    create_chunk_table, open_database, open_chunk_table, validate_chunk_table,
    exact_cosine_search, index_identity as build_index_identity_dict,
)
from src.retrieval.baseline import _to_results  # noqa: E402
from src.eval.baseline_metrics import evaluate_question, summarize_doc_recall  # noqa: E402
from src.eval.metrics import first_hit_rank, reciprocal_rank, mean_reciprocal_rank, ndcg_at_k, hit_at_k  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_ablation as p3a  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402

from scripts.run_phase3_chunking_ablation import (  # noqa: E402
    _embed_checkpoint_paths, _load_embed_checkpoint, _save_embed_checkpoint, _clear_embed_checkpoint,
    directory_size_bytes, _p50_p95, bootstrap_vs_reference,
)

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_3_embedding_model_benchmark.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
TASK32_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"
SPLIT_SUMMARY_PATH = REPO_ROOT / "results" / "phase_2_4_split_summary.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_3"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_3_embedding_model_benchmark.json"

CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
CHUNK_SCHEMA_VERSION = 1
EXPECTED_CHUNK_COUNT = 323971

CANDIDATE_K = 50
DOC_RECALL_K = 10

EMBED_PROGRESS_EVERY_BATCHES = 2  # qwen3_embedding's throughput (~15 chunks/s) means even a 10-batch
# (1280-chunk, ~85s) interval was never reached before the next memory-contention kill - checkpoint
# every 2 batches (~256 chunks, ~17s) instead so slow candidates still bank real progress
EVAL_PROGRESS_EVERY = 10
PILOT_PASSAGE_SAMPLE = 10
PILOT_QUERY_SAMPLE = 5
DEFAULT_BATCH_SIZE = 128  # bge_base/nomic_embed measured fast and stable at this batch size
# qwen3_embedding's pilot (a single 40-text batch) badly overestimated real-corpus throughput -
# the full build stalled near the 8.5GB VRAM ceiling (7.8GB used, 92%) for minutes with zero
# progress at batch=128, most likely memory-pressure-induced allocator thrashing rather than a
# hang (process stayed alive, GPU stayed near 100% util) - a materially smaller batch avoids
# operating this close to the ceiling.
BATCH_SIZE_OVERRIDES: dict[str, int] = {"qwen3_embedding": 16}


def _batch_size_for(spec: "mr.EmbeddingModelSpec") -> int:
    return BATCH_SIZE_OVERRIDES.get(spec.candidate_id, DEFAULT_BATCH_SIZE)


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
    return table


# --------------------------------------------------------------- generic OOM-fallback encode

def _is_oom_error(exc: BaseException) -> bool:
    """torch 2.13 raises real CUDA OOM through `torch.AcceleratorError`
    for some code paths - a RuntimeError subclass that is a SIBLING of
    `torch.cuda.OutOfMemoryError` (both derive directly from RuntimeError,
    neither is a subclass of the other) - so catching only
    torch.cuda.OutOfMemoryError never triggers for this path, and a real
    OOM crashes the whole run (verified: this exact bug killed a live
    qwen3_embedding build with an uncaught traceback). Detect by checking
    both exception types explicitly, falling back to message text so this
    keeps working if the class hierarchy changes again."""
    accelerator_error = getattr(torch, "AcceleratorError", ())
    if isinstance(exc, (torch.cuda.OutOfMemoryError, accelerator_error) if accelerator_error else torch.cuda.OutOfMemoryError):
        return True
    return "out of memory" in str(exc).lower()


def encode_with_oom_fallback(encode_fn, spec, model, texts: list[str], initial_batch_size: int):
    batch_sizes_used: list[int] = []
    batch_size = initial_batch_size
    while True:
        try:
            torch.cuda.empty_cache()
            vectors = encode_fn(spec, model, texts, batch_size)
            batch_sizes_used.append(batch_size)
            return vectors, batch_sizes_used
        except RuntimeError as exc:
            if not _is_oom_error(exc):
                raise
            torch.cuda.empty_cache()
            if batch_size <= 1:
                raise
            batch_size = max(1, batch_size // 2)
            print(f"[MODEL {spec.candidate_id}] CUDA OOM - retrying with batch_size={batch_size}", file=sys.stderr)


# --------------------------------------------------------------- Stage 6: pilot

def pilot_candidate(spec: mr.EmbeddingModelSpec, passage_sample: list[str], query_sample: list[str]) -> dict:
    print(f"[MODEL {spec.candidate_id}] loading...")
    t0 = time.perf_counter()
    model = mr.load_model(spec, device="cuda")
    load_seconds = time.perf_counter() - t0

    torch.cuda.reset_peak_memory_stats()

    batch_size = _batch_size_for(spec)
    p_vecs, batches_p = encode_with_oom_fallback(mr.encode_passages, spec, model, passage_sample, batch_size)
    q_vecs, batches_q = encode_with_oom_fallback(mr.encode_queries, spec, model, query_sample, batch_size)

    mr.validate_vectors(p_vecs, expected_dimension=spec.dimension, expect_normalized=spec.normalize_embeddings)
    mr.validate_vectors(q_vecs, expected_dimension=spec.dimension, expect_normalized=spec.normalize_embeddings)

    # query/passage encodings must differ when the model's own contract
    # expects that (i.e. the prefixes differ)
    if spec.query_prefix != spec.passage_prefix:
        same_text_as_query = mr.encode_queries(spec, model, [passage_sample[0]], batch_size=1)[0]
        same_text_as_passage = mr.encode_passages(spec, model, [passage_sample[0]], batch_size=1)[0]
        if np.allclose(same_text_as_query, same_text_as_passage):
            raise SystemExit(
                f"FATAL: {spec.candidate_id} query/passage conventions differ but produced identical "
                f"embeddings for the same text - pilot check failed."
            )

    # tiny exact-cosine retrieval smoke: self-similarity ~1.0, cross-similarity < 1.0
    sims = p_vecs @ p_vecs.T
    diag_ok = np.allclose(np.diag(sims), 1.0, atol=1e-2) if spec.normalize_embeddings else True
    distinct_ok = bool((sims - np.eye(len(p_vecs))).max() < 1.0 - 1e-6)
    if not (diag_ok and distinct_ok):
        raise SystemExit(f"FATAL: {spec.candidate_id} tiny retrieval smoke failed (diag_ok={diag_ok}, distinct_ok={distinct_ok})")

    peak_allocated = torch.cuda.max_memory_allocated()
    peak_reserved = torch.cuda.max_memory_reserved()

    t1 = time.perf_counter()
    throughput_bench, _ = encode_with_oom_fallback(mr.encode_passages, spec, model, passage_sample * 4, batch_size)
    pilot_seconds = time.perf_counter() - t1
    pilot_throughput = len(passage_sample) * 4 / pilot_seconds if pilot_seconds > 0 else 0.0

    estimated_full_build_seconds = EXPECTED_CHUNK_COUNT / pilot_throughput if pilot_throughput > 0 else None
    estimated_artifact_bytes = int(EXPECTED_CHUNK_COUNT * spec.dimension * 4 * 1.4)  # +40% for the 16 metadata cols

    result = {
        "candidate_id": spec.candidate_id, "load_seconds": round(load_seconds, 3),
        "dimension_verified": p_vecs.shape[1], "dtype_verified": str(p_vecs.dtype),
        "normalized_verified": bool(spec.normalize_embeddings),
        "batch_sizes_used_pilot": sorted(set(batches_p + batches_q)),
        "peak_gpu_allocated_bytes": int(peak_allocated), "peak_gpu_reserved_bytes": int(peak_reserved),
        "pilot_throughput_chunks_per_s": round(pilot_throughput, 2),
        "estimated_full_build_seconds": round(estimated_full_build_seconds, 1) if estimated_full_build_seconds else None,
        "estimated_artifact_bytes": estimated_artifact_bytes,
    }
    print(f"[MODEL {spec.candidate_id}] pilot PASS dim={p_vecs.shape[1]} batch={result['batch_sizes_used_pilot']} "
          f"peak_vram={peak_allocated/1e9:.2f}GB throughput~{pilot_throughput:.1f} chunks/s "
          f"ETA~{estimated_full_build_seconds:.0f}s" if estimated_full_build_seconds else "")
    return result, model


# --------------------------------------------------------------- Stage 7: build embeddings/index

def build_embeddings_for_model(spec: mr.EmbeddingModelSpec, storage, model, chunk_table) -> dict:
    n = chunk_table.num_rows
    out_dir = storage.embeddings_dir(CHUNK_CONFIG_HASH, spec.repository)
    out_path = out_dir / "embeddings.parquet"
    if out_path.is_file():
        existing = pq.read_table(out_path)
        if existing.num_rows == n:
            print(f"[EMBED {spec.candidate_id}] existing artifact found ({n} vectors) - reusing")
            return {"vector_count": n, "embed_seconds": None, "reused": True,
                    "artifact_size_bytes": out_path.stat().st_size, "batch_sizes_used": []}
        raise SystemExit(f"FATAL: {out_path} has {existing.num_rows} rows, chunks.parquet has {n}")

    from src.chunk.fixed_window import CHUNK_SCHEMA_FIELDS
    import pyarrow as pa

    texts = chunk_table.column("text").to_pylist()
    t0 = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()

    batch = _batch_size_for(spec)
    vectors = np.empty((n, spec.dimension), dtype=mr.VECTOR_DTYPE)
    n_batches = (n + batch - 1) // batch
    all_batch_sizes: set[int] = set()

    checkpoint, done_rows = _load_embed_checkpoint(out_dir, n, dimension=spec.dimension)
    start_bi = 0
    if checkpoint is not None and checkpoint.shape[1] == spec.dimension:
        vectors[:done_rows] = checkpoint
        del checkpoint
        start_bi = done_rows // batch
        print(f"[EMBED {spec.candidate_id}] resuming from checkpoint: {done_rows}/{n} chunks already embedded")
    elif checkpoint is not None:
        print(f"[EMBED {spec.candidate_id}] checkpoint dimension mismatch - discarding, starting fresh")

    for bi in range(start_bi, n_batches):
        start = bi * batch
        end = min(start + batch, n)
        chunk_slice = texts[start:end]
        vecs, used = encode_with_oom_fallback(mr.encode_passages, spec, model, chunk_slice, batch)
        all_batch_sizes.update(used)
        vectors[start:end] = vecs
        del vecs
        if (bi + 1) % EMBED_PROGRESS_EVERY_BATCHES == 0 or (bi + 1) == n_batches:
            done = end
            elapsed = time.perf_counter() - t0
            rate = (done - done_rows) / elapsed if elapsed > 0 else 0.0
            eta = (n - done) / rate if rate > 0 else 0.0
            print(f"[EMBED {spec.candidate_id}]  {done}/{n} chunks  {100*done/n:5.1f}%  {rate:.1f} chunks/s  "
                  f"ETA {eta:.1f}s", flush=True)
            _save_embed_checkpoint(out_dir, vectors, done)

    mr.validate_vectors(vectors, expected_dimension=spec.dimension, expect_normalized=spec.normalize_embeddings)
    embed_seconds = time.perf_counter() - t0
    peak_allocated = torch.cuda.max_memory_allocated()

    columns = {field: chunk_table.column(field) for field in CHUNK_SCHEMA_FIELDS}
    vector_array = pa.FixedSizeListArray.from_arrays(pa.array(vectors.reshape(-1), type=pa.float32()), spec.dimension)
    schema_fields = [chunk_table.schema.field(f) for f in CHUNK_SCHEMA_FIELDS]
    schema_fields.append(pa.field("vector", pa.list_(pa.float32(), spec.dimension)))
    out_table = pa.table({**columns, "vector": vector_array}, schema=pa.schema(schema_fields))

    storage.ensure_dir(out_dir)
    pq.write_table(out_table, out_path)
    artifact_size = out_path.stat().st_size
    _clear_embed_checkpoint(out_dir)

    print(f"[EMBED {spec.candidate_id}] done: {n} vectors in {embed_seconds:.1f}s -> {out_path}")
    return {"vector_count": n, "embed_seconds": round(embed_seconds, 2), "reused": False,
            "artifact_size_bytes": artifact_size, "batch_sizes_used": sorted(all_batch_sizes),
            "peak_gpu_allocated_bytes": int(peak_allocated)}


def build_index_for_model(spec: mr.EmbeddingModelSpec, storage) -> dict:
    emb_path = storage.embeddings_dir(CHUNK_CONFIG_HASH, spec.repository) / "embeddings.parquet"
    source_table = pq.read_table(emb_path)
    n = source_table.num_rows

    db_path = storage.index_dir(CHUNK_CONFIG_HASH, spec.repository)
    t0 = time.perf_counter()
    if db_path.exists():
        db = open_database(db_path)
        names = db.list_tables().tables
        if names == [TABLE_NAME]:
            table = open_chunk_table(db)
            if table.count_rows() == n:
                print(f"[INDEX {spec.candidate_id}] existing table found ({n} rows) - reusing")
                return {"row_count": n, "index_build_seconds": None, "reused": True,
                        "index_size_bytes": directory_size_bytes(db_path)}
            raise SystemExit(f"FATAL: existing index at {db_path} has {table.count_rows()} rows, expected {n}")
        elif names:
            raise SystemExit(f"FATAL: {db_path} contains unexpected tables {names}")
        else:
            table = create_chunk_table(db, source_table)
    else:
        storage.ensure_dir(db_path)
        db = open_database(db_path)
        table = create_chunk_table(db, source_table)

    validate_chunk_table(table, expected_row_count=n)
    index_build_seconds = time.perf_counter() - t0
    index_size = directory_size_bytes(db_path)
    print(f"[INDEX {spec.candidate_id}]  building ...  done: {n} rows in {index_build_seconds:.1f}s ({index_size:,} bytes)")
    return {"row_count": n, "index_build_seconds": round(index_build_seconds, 2), "reused": False,
            "index_size_bytes": index_size}


# --------------------------------------------------------------- Stage 8: evaluate

def evaluate_model(spec: mr.EmbeddingModelSpec, storage, model, scoped_questions: list[dict],
                    frozen_scope_ids: list[str]) -> dict:
    p3a.assert_frozen_scope([q["question_id"] for q in scoped_questions], frozen_scope_ids)

    db = open_database(storage.index_dir(CHUNK_CONFIG_HASH, spec.repository))
    table = open_chunk_table(db)

    n = len(scoped_questions)
    per_question: dict[str, dict] = {}
    doc10_results = []
    doc_mrr_values, doc_ndcg_values = [], []
    hit50_flags = []
    embed_ms, search_ms, total_ms = [], [], []

    t0 = time.perf_counter()
    for i, q in enumerate(scoped_questions, start=1):
        target_id = p3.question_target_document_ids(q)[0]

        s0 = time.perf_counter()
        qvec = mr.encode_queries(spec, model, [q["question"]], batch_size=1)[0]
        s1 = time.perf_counter()
        arrow = exact_cosine_search(table, qvec, limit=CANDIDATE_K, expected_dimension=spec.dimension)
        s2 = time.perf_counter()
        results = _to_results(arrow)
        s3 = time.perf_counter()

        embed_ms.append((s1 - s0) * 1000)
        search_ms.append((s2 - s1) * 1000)
        total_ms.append((s3 - s0) * 1000)

        if len(results) != CANDIDATE_K:
            raise SystemExit(f"FATAL: {q['question_id']}: got {len(results)} results, expected {CANDIDATE_K}")

        ranked_document_ids = [r.document_id for r in results]

        qr = evaluate_question(
            question_id=q["question_id"], question=q["question"], category=q["category"],
            target_document_id=target_id, retrieved_results=results[:DOC_RECALL_K], k=DOC_RECALL_K,
        )
        doc10_results.append(qr)

        rank10 = first_hit_rank(ranked_document_ids, {target_id}, k=DOC_RECALL_K)
        rr10 = reciprocal_rank(rank10)
        doc_mrr_values.append(rr10)
        relevances10 = p3.document_relevances_at_k(ranked_document_ids, target_id, k=DOC_RECALL_K)
        ndcg10 = ndcg_at_k(relevances10, num_relevant=1, k=DOC_RECALL_K)
        doc_ndcg_values.append(ndcg10)

        rank50 = first_hit_rank(ranked_document_ids, {target_id}, k=CANDIDATE_K)
        hit50 = hit_at_k(rank50, CANDIDATE_K)
        hit50_flags.append(hit50)

        per_question[q["question_id"]] = {
            "target_document_id": target_id, "hit10": qr.hit, "rank10": rank10,
            "rr10": rr10, "ndcg10": ndcg10, "hit50": hit50, "rank50": rank50,
        }

        if i % EVAL_PROGRESS_EVERY == 0 or i == n:
            elapsed = time.perf_counter() - t0
            rate = i / elapsed if elapsed > 0 else 0.0
            eta = (n - i) / rate if rate > 0 else 0.0
            hits10_far = sum(1 for r in doc10_results if r.hit)
            hits50_far = sum(1 for h in hit50_flags if h)
            print(f"[EVAL {spec.candidate_id}]  {i}/{n}  {100*i/n:5.1f}%  hits@10={hits10_far}  hits@50={hits50_far}  "
                  f"ETA {eta:.1f}s", flush=True)
    run_seconds = time.perf_counter() - t0

    aggregate = summarize_doc_recall(doc10_results, k=DOC_RECALL_K)
    doc_mrr = mean_reciprocal_rank(doc_mrr_values)
    doc_ndcg_at_10 = sum(doc_ndcg_values) / len(doc_ndcg_values)
    doc_recall_at_50 = sum(1 for h in hit50_flags if h) / len(hit50_flags)
    hits50 = sum(1 for h in hit50_flags if h)

    return {
        "question_count": n,
        "metrics": {
            "doc_recall_at_10": aggregate.doc_recall_at_k, "doc_recall_at_10_hits": aggregate.hit_count,
            "doc_recall_at_50": doc_recall_at_50, "doc_recall_at_50_hits": hits50,
            "doc_mrr": doc_mrr, "doc_ndcg_at_10": doc_ndcg_at_10,
        },
        "per_question": per_question,
        "latency_ms": {
            "query_embedding": _p50_p95(embed_ms), "vector_search": _p50_p95(search_ms),
            "retrieval_total": _p50_p95(total_ms),
        },
        "run_seconds": round(run_seconds, 3),
    }


# --------------------------------------------------------------- persistence

def load_candidate_result(candidate_id: str) -> dict | None:
    path = CANDIDATE_RESULTS_DIR / f"{candidate_id}.json"
    return _load_json(path) if path.is_file() else None


def save_candidate_result(candidate_id: str, payload: dict) -> None:
    _write_json(CANDIDATE_RESULTS_DIR / f"{candidate_id}.json", payload)


def process_candidate(spec: mr.EmbeddingModelSpec, *, storage, chunk_table, scoped_questions,
                       frozen_scope_ids, config, split_summary, resume: bool) -> dict:
    existing = load_candidate_result(spec.candidate_id) if resume else None
    if existing is not None:
        print(f"[MODEL {spec.candidate_id}] existing result found - reusing (--resume)")
        return existing

    identity_hash = embedding_identity_hash(spec.embedding_identity())
    idx_identity = build_index_identity_dict(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_identity_hash_value=identity_hash,
    )
    idx_identity_hash = compute_index_identity_hash(idx_identity)

    pilot = None
    if spec.is_control:
        print(f"[MODEL {spec.candidate_id}] REUSE verified Task 3.2 control artifacts")
        model = mr.load_model(spec, device="cuda")
        embed_stats = build_embeddings_for_model(spec, storage, model, chunk_table)  # no-op reuse path
        index_stats = build_index_for_model(spec, storage)
        load_seconds = None
    else:
        passage_sample = chunk_table.column("text").to_pylist()[:PILOT_PASSAGE_SAMPLE]
        query_sample = [q["question"] for q in scoped_questions[:PILOT_QUERY_SAMPLE]]
        pilot, model = pilot_candidate(spec, passage_sample, query_sample)
        load_seconds = pilot["load_seconds"]
        embed_stats = build_embeddings_for_model(spec, storage, model, chunk_table)
        index_stats = build_index_for_model(spec, storage)

    eval_result = evaluate_model(spec, storage, model, scoped_questions, frozen_scope_ids)

    sha = git_sha()
    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": spec.repository, "model_revision": spec.revision,
            "embedding_dimension": spec.dimension, "vector_dtype": "float32",
            "normalize_embeddings": spec.normalize_embeddings, "identity_hash": identity_hash,
        },
        index_identity_hash=idx_identity_hash,
        retrieval_config={"type": p3.RETRIEVAL_TYPE, "top_k": CANDIDATE_K, "distance_metric": DISTANCE_METRIC},
        reranker_config={"enabled": False}, generation_model=None, split="dev",
        eval_set_version="phase2-v1",
        split_version="phase2-split-v1", split_sha256=split_summary["dev_sha256"],
        metrics=eval_result["metrics"], evaluation_source="internal_phase2",
        experiment_name="phase3_3_embedding_benchmark", run_kind="phase3_3_embedding_benchmark",
        notes=f"Task 3.3 candidate {spec.candidate_id} ({spec.repository}@{spec.revision[:12]}) "
              f"over frozen 256/0/fixed chunks ({CHUNK_CONFIG_HASH[:12]}...).",
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[MODEL {spec.candidate_id}] Task 2.11 run record written: {run_record_path}")

    payload = {
        "candidate_id": spec.candidate_id, "repository": spec.repository, "revision": spec.revision,
        "dimension": spec.dimension, "is_control": spec.is_control,
        "query_convention": spec.query_convention, "passage_convention": spec.passage_convention,
        "normalize_embeddings": spec.normalize_embeddings, "similarity_metric": spec.similarity_metric,
        "trust_remote_code": spec.trust_remote_code, "license": spec.license,
        "model_size_bytes": spec.model_size_bytes, "embedding_identity_hash": identity_hash,
        "index_identity_hash": idx_identity_hash,
        "chunk_config_hash": CHUNK_CONFIG_HASH,
        "run_id": run_record.run_id, "git_sha": sha,
        "model_load_seconds": load_seconds, "pilot": pilot,
        "embed_stats": embed_stats, "index_stats": index_stats,
        **eval_result,
    }
    save_candidate_result(spec.candidate_id, payload)
    return payload


# --------------------------------------------------------------- winner selection

def _embedding_tiebreak_key(candidate: dict) -> tuple:
    """Stage 9's frozen embedding-model tie-break order: lower dimension/
    smaller index -> faster passage throughput -> lower query-embedding
    latency -> lower retrieval p95 -> lower peak VRAM -> smaller model
    artifact -> simpler/more standard integration (CLS/mean pooling ranked
    simpler than last-token pooling for this project's purposes)."""
    integration_rank = 0 if candidate.get("pooling") in ("cls", "mean") else 1
    return (
        candidate.get("dimension", 0),
        candidate.get("index_size_bytes", 0),
        -(candidate.get("embed_throughput_chunks_per_s") or 0.0),
        candidate.get("query_embedding_latency_p50_ms", 0.0),
        candidate.get("retrieval_latency_p95_ms", 0.0),
        candidate.get("peak_gpu_allocated_bytes", 0),
        candidate.get("model_size_bytes", 0) or 0,
        integration_rank,
    )


def _candidate_quality_row(spec: mr.EmbeddingModelSpec, result: dict) -> dict:
    m = result["metrics"]
    embed_stats = result.get("embed_stats", {})
    index_stats = result.get("index_stats", {})
    throughput = None
    if embed_stats.get("embed_seconds") and embed_stats.get("vector_count"):
        throughput = embed_stats["vector_count"] / embed_stats["embed_seconds"]
    return {
        "row_id": spec.candidate_id, "doc_recall_at_50": m["doc_recall_at_50"], "doc_mrr": m["doc_mrr"],
        "doc_ndcg_at_10": m["doc_ndcg_at_10"], "doc_recall_at_10": m["doc_recall_at_10"],
        "dimension": spec.dimension, "pooling": spec.pooling,
        "index_size_bytes": index_stats.get("index_size_bytes", 0),
        "embed_throughput_chunks_per_s": throughput,
        "query_embedding_latency_p50_ms": result["latency_ms"]["query_embedding"]["p50"] or 0.0,
        "retrieval_latency_p95_ms": result["latency_ms"]["retrieval_total"]["p95"] or 0.0,
        "peak_gpu_allocated_bytes": embed_stats.get("peak_gpu_allocated_bytes", 0) or 0,
        "model_size_bytes": spec.model_size_bytes,
    }


# --------------------------------------------------------------- ablation table row

def candidate_to_ablation_row(spec: mr.EmbeddingModelSpec, result: dict, *, config_hash: str,
                               eval_scope_sha256: str, corpus_document_count: int) -> dict:
    m = result["metrics"]
    lat = result["latency_ms"]
    index_stats = result.get("index_stats", {})
    return {
        "row_id": spec.candidate_id, "configuration": f"embedding_{spec.candidate_id}",
        "status": "phase3_3_embedding_benchmark", "run_id": result["run_id"], "git_sha": result["git_sha"],
        "phase3_config_hash": config_hash, "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": eval_scope_sha256, "question_count": result["question_count"],
        "corpus_document_count": corpus_document_count, "chunk_count": EXPECTED_CHUNK_COUNT,
        "chunk_config_hash": CHUNK_CONFIG_HASH, "embedding_model": spec.repository,
        "embedding_revision": spec.revision, "embedding_identity": result["embedding_identity_hash"],
        "index_identity": result["index_identity_hash"], "retrieval": p3.RETRIEVAL_TYPE,
        "candidate_k": CANDIDATE_K, "doc_recall_at_10": m["doc_recall_at_10"],
        "doc_recall_at_50": m["doc_recall_at_50"], "doc_mrr": m["doc_mrr"], "doc_ndcg_at_10": m["doc_ndcg_at_10"],
        "precision_at_5": p3.NA, "refusal_metric": p3.NA,
        "retrieval_latency_p50_ms": lat["retrieval_total"]["p50"], "retrieval_latency_p95_ms": lat["retrieval_total"]["p95"],
        "query_embedding_latency_p50_ms": lat["query_embedding"]["p50"], "search_latency_p50_ms": lat["vector_search"]["p50"],
        "index_size_bytes": index_stats.get("index_size_bytes", p3.NA),
        "notes": (
            f"Task 3.3: dim={spec.dimension}, normalize={spec.normalize_embeddings}, "
            f"query_convention={spec.query_convention!r}, passage_convention={spec.passage_convention!r}, "
            f"pooling={spec.pooling}, trust_remote_code={spec.trust_remote_code}, license={spec.license}."
            + (" CONTROL (reused Task 3.2 artifacts, not rebuilt)." if spec.is_control else "")
        ),
    }


# --------------------------------------------------------------- CLI actions

def cmd_plan() -> int:
    config, config_hash = load_experiment_config()
    print("[STAGE 4/10] Frozen Task 3.3 embedding benchmark config")
    print(f"phase3_3_config_hash: {config_hash}")
    print(json.dumps(config, indent=2))
    return 0


def cmd_status() -> int:
    print("Task 3.3 status (read-only)")
    for spec in mr.ALL_CANDIDATES:
        result = load_candidate_result(spec.candidate_id)
        if result is None:
            print(f"  {spec.candidate_id}: not built")
        else:
            m = result["metrics"]
            print(f"  {spec.candidate_id} ({spec.repository}): recall@10={m['doc_recall_at_10']:.4f} "
                  f"recall@50={m['doc_recall_at_50']:.4f} mrr={m['doc_mrr']:.4f} ndcg@10={m['doc_ndcg_at_10']:.4f}")
    return 0


def run_full(resume: bool) -> int:
    print("[STAGE 1/10] Task 3.3 preflight")
    frozen_scope_ids, baseline = load_frozen_scope()
    dev_payload = load_dev_questions()
    questions_by_id = {q["question_id"]: q for q in dev_payload["questions"]}
    scoped_questions = [questions_by_id[qid] for qid in frozen_scope_ids]
    p3a.assert_dev_split("dev")
    print(f"Frozen scope verified: {len(frozen_scope_ids)} questions, hash matches config.")

    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    print(f"Frozen 256/0/fixed chunk artifact verified: {chunk_table.num_rows} chunks.")

    print("[STAGE 2/10] Freeze embedding candidate grid")
    for spec in mr.ALL_CANDIDATES:
        print(f"  {spec.candidate_id:16s} {spec.repository:35s} dim={spec.dimension:5d} "
              f"max_seq={spec.max_seq_length:6d} trust_remote_code={spec.trust_remote_code}")

    print("[STAGE 3/10] Audit embedding contracts - see configs/phase_3_3_embedding_model_benchmark.json")

    config, config_hash = load_experiment_config()
    split_summary = _load_json(SPLIT_SUMMARY_PATH)

    print("[STAGE 5/10] Generalize embedding model adapter - ready (src/embeddings/model_registry.py)")
    print("[STAGE 6/10] Candidate pilot")
    print("[STAGE 7/10] Build candidate embeddings and indexes")
    print("[STAGE 8/10] Evaluate embedding candidates")

    results: dict[str, dict] = {}
    for spec in mr.ALL_CANDIDATES:
        results[spec.candidate_id] = process_candidate(
            spec, storage=storage, chunk_table=chunk_table, scoped_questions=scoped_questions,
            frozen_scope_ids=frozen_scope_ids, config=config, split_summary=split_summary, resume=resume,
        )

    control_id = "bge_small"
    control_result = results[control_id]
    task32 = _load_json(TASK32_RESULT_PATH)
    frozen_control_metrics = task32["final_winner"]["metrics"]
    for key in ("doc_recall_at_10", "doc_recall_at_50", "doc_mrr", "doc_ndcg_at_10"):
        fresh = control_result["metrics"][key]
        frozen = frozen_control_metrics[key]
        if abs(fresh - frozen) > 1e-9:
            raise SystemExit(
                f"FATAL: control (bge_small) fresh evaluation {key}={fresh} != Task 3.2 frozen winner "
                f"value {frozen} - retrieval is not reproducing the Task 3.2 control exactly. STOP."
            )
    print("[bge_small] fresh evaluation reproduces Task 3.2 frozen control metrics exactly - verified.")
    print("[STAGE 9/10] Compare and select embedding model")

    quality_rows = [_candidate_quality_row(spec, results[spec.candidate_id]) for spec in mr.ALL_CANDIDATES]
    bootstrap = {
        spec.candidate_id: bootstrap_vs_reference(results[spec.candidate_id], control_result, frozen_scope_ids)
        for spec in mr.ALL_CANDIDATES if spec.candidate_id != control_id
    }
    selection = p3a.select_round_winner(
        reference_row_id=control_id, candidates=quality_rows,
        bootstrap_vs_reference={cid: {"recall50_hit_delta": b["recall50_hit_delta"], "mrr_ci": b["mrr_ci"], "ndcg_ci": b["ndcg_ci"]}
                                 for cid, b in bootstrap.items()},
        tiebreak_key_fn=_embedding_tiebreak_key,
    )
    if selection.flagged_for_user_decision:
        raise SystemExit(f"STOP - Task 3.3 requires a user decision: {selection.flag_reason}")
    print(f"Winner: {selection.winner_row_id} - {selection.rationale}")

    print("[STAGE 10/10] Verify and close Task 3.3")
    sha = git_sha()
    corpus_doc_count = len(set(chunk_table.column("document_id").to_pylist()))
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    for spec in mr.ALL_CANDIDATES:
        row = candidate_to_ablation_row(
            spec, results[spec.candidate_id], config_hash=config_hash,
            eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
            corpus_document_count=corpus_doc_count,
        )
        existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    decisions = {"winner_candidate_id": selection.winner_row_id, "rationale": selection.rationale,
                 "bootstrap": {cid: {k: v for k, v in b.items() if k != "notable_rank_moves"} for cid, b in bootstrap.items()}}
    _write_json(REPO_ROOT / "results" / "phase_3_3_round_decision.json", decisions)

    print(f"Final winner: {selection.winner_row_id}")
    return 0


def assemble_final_report() -> dict:
    decisions_path = REPO_ROOT / "results" / "phase_3_3_round_decision.json"
    if not decisions_path.is_file():
        raise SystemExit("Not complete yet - run --run --resume first.")
    decisions = _load_json(decisions_path)

    frozen_scope_ids, baseline = load_frozen_scope()
    config, config_hash = load_experiment_config()

    results = {spec.candidate_id: load_candidate_result(spec.candidate_id) for spec in mr.ALL_CANDIDATES}
    missing = [cid for cid, r in results.items() if r is None]
    if missing:
        raise SystemExit(f"Missing candidate result(s): {missing} - run --run --resume first.")

    control_id = "bge_small"
    control_result = results[control_id]
    vs_control = {
        cid: bootstrap_vs_reference(r, control_result, frozen_scope_ids)
        for cid, r in results.items() if cid != control_id
    }

    report = {
        "task": "3.3", "phase3_3_config_hash": config_hash, "phase3_3_config": config,
        "task32_result_identity": config["task32_result_identity"],
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": baseline["phase3_config"]["phase3_dev_scope_sha256"],
        "question_count": len(frozen_scope_ids),
        "chunk_config_hash": CHUNK_CONFIG_HASH,
        "candidates": results,
        "paired_comparisons_vs_control": vs_control,
        "final_winner_candidate_id": decisions["winner_candidate_id"],
        "rationale": decisions["rationale"],
        "limitations": [
            "Evaluated only over the frozen Task 3.1 89-question DEV/evaluable-subset (4.9% of full DEV).",
            "N=89 is small; practical-tie handling and bootstrap CIs govern which differences are credible.",
            "Only the four models explicitly named in PROJECT_EXECUTION.md's Task 3.3 section were "
            "benchmarked; the optional commercial reference model was not run (paid API, not approved).",
            "No BM25/hybrid/reranking/CRAG/router/metadata-prefiltering - vector-only exact cosine throughout.",
            "chunk_recall@10, chunk_mrr, precision@5, faithfulness, citation_grounding, and generation "
            "metrics remain N/A - no valid chunk-level or generation gold exists for this scope.",
        ],
    }
    return report


def cmd_compare() -> int:
    report = assemble_final_report()
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.3 report written: {FINAL_RESULT_PATH}")
    print(f"Final winner: {report['final_winner_candidate_id']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.3 - Phase 3 embedding model benchmark.")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    if args.plan:
        return cmd_plan()
    if args.status:
        return cmd_status()
    if args.compare:
        return cmd_compare()
    if args.run:
        return run_full(resume=args.resume)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
