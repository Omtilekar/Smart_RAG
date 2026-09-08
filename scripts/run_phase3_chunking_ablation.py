"""Task 3.2 - controlled DEV-only chunking ablation.

Orchestrates the staged experiment grid frozen in
configs/phase_3_2_chunking_ablation.json (src.eval.phase3_ablation):

    Round A: window size (512 baseline reused / 256 / 1024)
    Round B: overlap on the Round A winner window (0 reused / 12.5% / 25%)
    Round C: fixed vs section-aware on the Round B winner window+overlap

Reuses Task 1.3/1.4/1.5's chunking/embedding/indexing logic (via
scripts.chunk_development_corpus / scripts.embed_development_corpus /
src.index.lancedb_index), Task 1.10/2.6/3.1's metric implementations
(never reimplemented here), and Task 2.10/2.11's hashing/run-logging.

Never imports src.eval.test_access - Task 3.2 evaluation is DEV-only,
using exactly the Task 3.1 frozen 89-question scope loaded verbatim from
results/phase_3_1_trusted_baseline.json (never recomputed per candidate).

Usage:
    python -u scripts/run_phase3_chunking_ablation.py --plan
    python -u scripts/run_phase3_chunking_ablation.py --run --resume
    python -u scripts/run_phase3_chunking_ablation.py --status
    python -u scripts/run_phase3_chunking_ablation.py --compare
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.artifacts.versioning import (  # noqa: E402
    semantic_hash, embedding_identity_hash, compute_index_identity_hash,
)
from src.chunk.fixed_window import (  # noqa: E402
    CHUNK_SCHEMA_FIELDS,
    build_chunk_config,
    chunk_config_hash as compute_chunk_config_hash,
    compute_token_windows,
    make_chunk_id,
    slice_chunk_text,
    split_body_into_sections,
)
from src.embeddings.bge import (  # noqa: E402
    MODEL_REPO, MODEL_REVISION, EMBEDDING_DIMENSION, DEFAULT_BATCH_SIZE,
    load_model, encode_queries, encode_passages, validate_vectors,
    embedding_identity as bge_embedding_identity,
)
from src.index.lancedb_index import (  # noqa: E402
    TABLE_NAME, DISTANCE_METRIC, EXPECTED_COLUMNS,
    create_chunk_table, open_database, open_chunk_table, validate_chunk_table,
    exact_cosine_search, index_identity as build_index_identity_dict,
)
from src.retrieval.baseline import _to_results  # noqa: E402
from src.eval.baseline_metrics import evaluate_question, summarize_doc_recall  # noqa: E402
from src.eval.metrics import first_hit_rank, reciprocal_rank, mean_reciprocal_rank, ndcg_at_k, hit_at_k  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_ablation as p3a  # noqa: E402

import scripts.chunk_development_corpus as cdc  # noqa: E402
import scripts.embed_development_corpus as edc  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_2_chunking_ablation.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_2"
DECISIONS_PATH = REPO_ROOT / "results" / "phase_3_2_round_decisions.json"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"

ROW0_CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
ROW0_CHUNK_SCHEMA_VERSION = 1
ROW0_ROW_COUNT = 162357

CANDIDATE_K = 50
DOC_RECALL_K = 10

CHUNK_PROGRESS_EVERY = 250
EMBED_PROGRESS_EVERY_BATCHES = 50
EVAL_PROGRESS_EVERY = 10


def git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _p50_p95(values: list[float]) -> dict:
    if not values:
        return {"p50": None, "p95": None}
    s = sorted(values)
    return {"p50": round(s[len(s) // 2], 3), "p95": round(s[int(0.95 * (len(s) - 1))], 3)}


def directory_size_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, int(round(p * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


# --------------------------------------------------------------- frozen config / scope

def load_experiment_config() -> tuple[dict, str]:
    config = _load_json(CONFIG_PATH)
    return config, semantic_hash(config)


def load_frozen_scope() -> tuple[list[str], dict]:
    """Loads the exact Task 3.1 89-question scope verbatim - never
    recomputed. Verifies its sha256 against the frozen config before any
    candidate run (Stage 1 requirement)."""
    baseline = _load_json(BASELINE_RESULT_PATH)
    question_ids = sorted(baseline["question_ids"])
    ids_hash = p3.compute_question_ids_sha256(question_ids)
    config, _ = load_experiment_config()
    if ids_hash != config["question_ids_hash"]:
        raise SystemExit(
            f"FATAL: frozen 89-question scope does not reproduce - recomputed {ids_hash} != "
            f"config's frozen {config['question_ids_hash']}. STOP."
        )
    if baseline["question_count"] != config["question_count"]:
        raise SystemExit("FATAL: question_count mismatch between baseline result and frozen config.")
    return question_ids, baseline


def load_dev_questions() -> dict:
    return _load_json(REPO_ROOT / "results" / "phase_2_4_dev.json")


# --------------------------------------------------------------- candidate identity

def resolve_chunk_config(candidate: p3a.ChunkCandidate, provenance: dict) -> tuple[dict, str]:
    config = build_chunk_config(
        normalizer_version=provenance["normalizer_version"],
        normalization_build_sha256=provenance["normalization_build_sha256"],
        development_manifest_sha256=provenance["development_manifest_sha256"],
        tokenizer_repo=cdc.TOKENIZER_REPO,
        tokenizer_revision=cdc.TOKENIZER_REVISION,
        window_size_tokens=candidate.window_size_tokens,
        overlap_tokens=candidate.overlap_tokens,
        split_mode=candidate.split_mode,
    )
    return config, compute_chunk_config_hash(config)


# --------------------------------------------------------------- Stage 4/5: build chunks

def _windows_for_text(tokenizer, text: str, window_size: int, stride: int) -> list[tuple[str, int]]:
    encoding = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True, truncation=False)
    offsets = encoding["offset_mapping"]
    num_tokens = len(offsets)
    if num_tokens == 0:
        return []
    windows = compute_token_windows(num_tokens, window_size, stride)
    out = []
    for start_idx, end_idx in windows:
        chunk_text = slice_chunk_text(text, offsets, start_idx, end_idx)
        out.append((chunk_text, end_idx - start_idx))
    return out


def build_chunks_for_candidate(candidate: p3a.ChunkCandidate, provenance: dict, filings: list[dict],
                                parsed_docs: dict, tokenizer, storage) -> dict:
    if candidate.reuse_row_id == "0":
        # Row 0's frozen chunk identity was computed independently (Task
        # 1.3, before split_mode existed as a config field) - never
        # recompute it through the generalized build_chunk_config(), which
        # would silently mint a NEW, disconnected hash and try to rebuild
        # the entire trusted baseline. Verify the frozen artifact directly.
        hash_ = ROW0_CHUNK_CONFIG_HASH
        out_path = storage.chunks_dir(hash_) / "chunks.parquet"
        if not out_path.is_file():
            raise SystemExit(f"FATAL: expected frozen row 0 chunk artifact missing at {out_path}")
        table = pq.read_table(out_path)
        if table.num_rows != ROW0_ROW_COUNT:
            raise SystemExit(
                f"FATAL: row 0 chunk artifact has {table.num_rows} rows, expected {ROW0_ROW_COUNT} - "
                f"possible corruption. STOP."
            )
        print(f"[CHUNK {candidate.label}] row 0 frozen artifact verified ({table.num_rows} chunks) - reused, never rebuilt")
        return {"chunk_config_hash": hash_, "chunk_count": table.num_rows, "build_seconds": None, "reused": True}

    config, hash_ = resolve_chunk_config(candidate, provenance)
    out_dir = storage.chunks_dir(hash_)
    out_path = out_dir / "chunks.parquet"

    if out_path.is_file():
        table = pq.read_table(out_path)
        print(f"[CHUNK {candidate.label}] existing artifact found ({table.num_rows} chunks) - reusing")
        return {"chunk_config_hash": hash_, "chunk_count": table.num_rows, "build_seconds": None, "reused": True}

    t0 = time.perf_counter()
    n_docs = len(filings)
    chunks: list[dict] = []
    for i, row in enumerate(filings, start=1):
        doc_id = row["document_id"]
        fields, body = parsed_docs[doc_id]

        if not body:
            if doc_id not in cdc.EXPECTED_EMPTY_BODY_DOCUMENT_IDS:
                raise SystemExit(f"FATAL: unexpected empty body for {doc_id}")
        else:
            if candidate.split_mode == "fixed":
                spans = [(None, None, body)]
            else:
                sections = split_body_into_sections(body)
                spans = [(sid, title, body[start:end]) for sid, title, start, end in sections]

            ordinal = 0
            for _section_id, _title, span_text in spans:
                for chunk_text, token_count in _windows_for_text(
                    tokenizer, span_text, candidate.window_size_tokens, candidate.stride_tokens
                ):
                    if not chunk_text.strip():
                        raise SystemExit(f"FATAL: empty chunk text produced for {doc_id} ordinal {ordinal}")
                    chunks.append({
                        "chunk_id": make_chunk_id(doc_id, ordinal),
                        "document_id": doc_id,
                        "cik": fields["cik"],
                        "company": fields["company"],
                        "form_type": fields["form_type"],
                        "fiscal_year": fields["fiscal_year"],
                        "source": fields["source"],
                        "source_filename": fields["source_filename"],
                        "source_split": fields["source_split"],
                        "ordinal": ordinal,
                        "text": chunk_text,
                        "token_count": token_count,
                        "chunk_config_hash": hash_,
                        "normalizer_version": provenance["normalizer_version"],
                        "normalization_build_sha256": provenance["normalization_build_sha256"],
                        "development_manifest_sha256": fields["development_manifest_sha256"],
                    })
                    ordinal += 1

        if i % CHUNK_PROGRESS_EVERY == 0 or i == n_docs:
            elapsed = time.perf_counter() - t0
            rate = i / elapsed if elapsed > 0 else 0.0
            eta = (n_docs - i) / rate if rate > 0 else 0.0
            print(f"[CHUNK {candidate.label}]  {i}/{n_docs} docs  {100*i/n_docs:5.1f}%  "
                  f"chunks={len(chunks)}  ETA {eta:.1f}s", flush=True)

    ids = [c["chunk_id"] for c in chunks]
    if len(set(ids)) != len(ids):
        raise SystemExit("FATAL: duplicate chunk_id detected")

    schema = pa.schema([
        ("chunk_id", pa.string()), ("document_id", pa.string()), ("cik", pa.int64()),
        ("company", pa.string()), ("form_type", pa.string()), ("fiscal_year", pa.int32()),
        ("source", pa.string()), ("source_filename", pa.string()), ("source_split", pa.string()),
        ("ordinal", pa.int32()), ("text", pa.string()), ("token_count", pa.int32()),
        ("chunk_config_hash", pa.string()), ("normalizer_version", pa.string()),
        ("normalization_build_sha256", pa.string()), ("development_manifest_sha256", pa.string()),
    ])
    columns = {field: [c[field] for c in chunks] for field in CHUNK_SCHEMA_FIELDS}
    table = pa.table(columns, schema=schema)
    storage.ensure_dir(out_dir)
    pq.write_table(table, out_path)

    config_out = REPO_ROOT / "configs" / f"phase_3_2_chunk_{candidate.row_id}.json"
    config_out.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    build_seconds = time.perf_counter() - t0
    print(f"[CHUNK {candidate.label}] done: {len(chunks)} chunks in {build_seconds:.1f}s -> {out_path}")
    return {"chunk_config_hash": hash_, "chunk_count": len(chunks), "build_seconds": round(build_seconds, 2),
            "reused": False, "artifact_size_bytes": out_path.stat().st_size}


# --------------------------------------------------------------- Stage 5: build embeddings

def build_embeddings_for_candidate(chunk_config_hash: str, label: str, storage, model) -> dict:
    chunk_path = storage.chunks_dir(chunk_config_hash) / "chunks.parquet"
    chunk_table = pq.read_table(chunk_path)
    n = chunk_table.num_rows

    out_dir = storage.embeddings_dir(chunk_config_hash, MODEL_REPO)
    out_path = out_dir / "embeddings.parquet"
    if out_path.is_file():
        existing = pq.read_table(out_path)
        if existing.num_rows == n:
            print(f"[EMBED {label}] existing artifact found ({n} vectors) - reusing")
            return {"vector_count": n, "embed_seconds": None, "reused": True,
                    "artifact_size_bytes": out_path.stat().st_size}
        raise SystemExit(
            f"FATAL: {out_path} has {existing.num_rows} rows, chunks.parquet has {n} - "
            f"refusing to silently overwrite a conflicting build."
        )

    texts = chunk_table.column("text").to_pylist()
    t0 = time.perf_counter()

    batch = DEFAULT_BATCH_SIZE
    all_vectors = []
    n_batches = (n + batch - 1) // batch
    for bi in range(n_batches):
        chunk_slice = texts[bi * batch:(bi + 1) * batch]
        vecs, _used = edc.encode_with_oom_fallback(model, chunk_slice, batch)
        all_vectors.append(vecs)
        if (bi + 1) % EMBED_PROGRESS_EVERY_BATCHES == 0 or (bi + 1) == n_batches:
            done = min((bi + 1) * batch, n)
            elapsed = time.perf_counter() - t0
            rate = done / elapsed if elapsed > 0 else 0.0
            eta = (n - done) / rate if rate > 0 else 0.0
            print(f"[EMBED {label}]  {done}/{n} chunks  {100*done/n:5.1f}%  {rate:.1f} chunks/s  "
                  f"ETA {eta:.1f}s", flush=True)

    import numpy as np
    vectors = np.concatenate(all_vectors, axis=0)
    validate_vectors(vectors)
    if vectors.shape[0] != n:
        raise SystemExit(f"FATAL: {vectors.shape[0]} vectors for {n} chunks")

    embed_seconds = time.perf_counter() - t0

    columns = {field: chunk_table.column(field) for field in CHUNK_SCHEMA_FIELDS}
    vector_array = pa.FixedSizeListArray.from_arrays(
        pa.array(vectors.reshape(-1), type=pa.float32()), EMBEDDING_DIMENSION,
    )
    schema_fields = [chunk_table.schema.field(f) for f in CHUNK_SCHEMA_FIELDS]
    schema_fields.append(pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIMENSION)))
    out_table = pa.table({**columns, "vector": vector_array}, schema=pa.schema(schema_fields))

    storage.ensure_dir(out_dir)
    pq.write_table(out_table, out_path)
    artifact_size = out_path.stat().st_size

    print(f"[EMBED {label}] done: {n} vectors in {embed_seconds:.1f}s ({n/embed_seconds:.1f} chunks/s) -> {out_path}")
    return {"vector_count": n, "embed_seconds": round(embed_seconds, 2), "reused": False,
            "artifact_size_bytes": artifact_size}


# --------------------------------------------------------------- Stage 5: build index

def build_index_for_candidate(chunk_config_hash: str, label: str, storage) -> dict:
    emb_path = storage.embeddings_dir(chunk_config_hash, MODEL_REPO) / "embeddings.parquet"
    source_table = pq.read_table(emb_path)
    n = source_table.num_rows

    db_path = storage.index_dir(chunk_config_hash, MODEL_REPO)
    t0 = time.perf_counter()
    if db_path.exists():
        db = open_database(db_path)
        names = db.list_tables().tables
        if names == [TABLE_NAME]:
            table = open_chunk_table(db)
            if table.count_rows() == n:
                print(f"[INDEX {label}] existing table found ({n} rows) - reusing")
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
    print(f"[INDEX {label}]  building ...  done: {n} rows in {index_build_seconds:.1f}s ({index_size:,} bytes)")
    return {"row_count": n, "index_build_seconds": round(index_build_seconds, 2), "reused": False,
            "index_size_bytes": index_size}


# --------------------------------------------------------------- Stage 6: evaluate

def evaluate_candidate(chunk_config_hash: str, label: str, storage, model,
                        scoped_questions: list[dict], frozen_scope_ids: list[str]) -> dict:
    p3a.assert_frozen_scope([q["question_id"] for q in scoped_questions], frozen_scope_ids)

    db_path = storage.index_dir(chunk_config_hash, MODEL_REPO)
    db = open_database(db_path)
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
        qvec = encode_queries(model, [q["question"]], batch_size=1)[0]
        s1 = time.perf_counter()
        arrow = exact_cosine_search(table, qvec, limit=CANDIDATE_K)
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
            print(f"[EVAL {label}]  {i}/{n}  {100*i/n:5.1f}%  hits@10={hits10_far}  hits@50={hits50_far}  "
                  f"ETA {eta:.1f}s", flush=True)
    run_seconds = time.perf_counter() - t0

    aggregate = summarize_doc_recall(doc10_results, k=DOC_RECALL_K)
    doc_mrr = mean_reciprocal_rank(doc_mrr_values)
    doc_ndcg_at_10 = sum(doc_ndcg_values) / len(doc_ndcg_values)
    doc_recall_at_50 = sum(1 for h in hit50_flags if h) / len(hit50_flags)
    hits50 = sum(1 for h in hit50_flags if h)

    return {
        "chunk_config_hash": chunk_config_hash,
        "question_count": n,
        "metrics": {
            "doc_recall_at_10": aggregate.doc_recall_at_k,
            "doc_recall_at_10_hits": aggregate.hit_count,
            "doc_recall_at_50": doc_recall_at_50,
            "doc_recall_at_50_hits": hits50,
            "doc_mrr": doc_mrr,
            "doc_ndcg_at_10": doc_ndcg_at_10,
        },
        "per_question": per_question,
        "latency_ms": {
            "query_embedding": _p50_p95(embed_ms), "vector_search": _p50_p95(search_ms),
            "retrieval_total": _p50_p95(total_ms),
        },
        "run_seconds": round(run_seconds, 3),
    }


# --------------------------------------------------------------- ledger / result persistence

def load_decisions() -> dict:
    if DECISIONS_PATH.is_file():
        return _load_json(DECISIONS_PATH)
    return {"rounds": {}}


def save_decisions(decisions: dict) -> None:
    _write_json(DECISIONS_PATH, decisions)


def load_candidate_result(row_id: str) -> dict | None:
    path = CANDIDATE_RESULTS_DIR / f"{row_id}.json"
    if path.is_file():
        return _load_json(path)
    return None


def save_candidate_result(row_id: str, payload: dict) -> None:
    _write_json(CANDIDATE_RESULTS_DIR / f"{row_id}.json", payload)


# --------------------------------------------------------------- candidate processing

def process_candidate(candidate: p3a.ChunkCandidate, *, provenance, filings, parsed_docs, tokenizer,
                       storage, model, scoped_questions, frozen_scope_ids, resume: bool) -> dict:
    existing = load_candidate_result(candidate.row_id) if resume else None
    if existing is not None:
        print(f"[{candidate.row_id}] {candidate.label}: existing result found - reusing (--resume)")
        return existing

    chunk_stats = build_chunks_for_candidate(candidate, provenance, filings, parsed_docs, tokenizer, storage)
    hash_ = chunk_stats["chunk_config_hash"]
    embed_stats = build_embeddings_for_candidate(hash_, candidate.label, storage, model)
    index_stats = build_index_for_candidate(hash_, candidate.label, storage)
    eval_result = evaluate_candidate(hash_, candidate.label, storage, model, scoped_questions, frozen_scope_ids)

    build_seconds_total = sum(
        v for v in (chunk_stats.get("build_seconds"), embed_stats.get("embed_seconds"),
                    index_stats.get("index_build_seconds")) if v is not None
    ) or None

    payload = {
        "row_id": candidate.row_id, "round": candidate.round, "label": candidate.label,
        "window_size_tokens": candidate.window_size_tokens, "overlap_tokens": candidate.overlap_tokens,
        "stride_tokens": candidate.stride_tokens, "split_mode": candidate.split_mode,
        "reuse_row_id": candidate.reuse_row_id, "encoder_truncation_note": candidate.encoder_truncation_note,
        "chunk_config_hash": hash_,
        "chunk_stats": chunk_stats, "embed_stats": embed_stats, "index_stats": index_stats,
        "build_seconds_total": build_seconds_total,
        **eval_result,
    }
    save_candidate_result(candidate.row_id, payload)
    return payload


# --------------------------------------------------------------- bootstrap vs reference

def paired_arrays(candidate_pq: dict, reference_pq: dict, question_ids: list[str], field: str) -> tuple[list[float], list[float]]:
    cand = [float(candidate_pq[qid][field]) for qid in question_ids]
    ref = [float(reference_pq[qid][field]) for qid in question_ids]
    return cand, ref


def bootstrap_vs_reference(candidate_result: dict, reference_result: dict, question_ids: list[str]) -> dict:
    cand_hit50 = sum(1 for qid in question_ids if candidate_result["per_question"][qid]["hit50"])
    ref_hit50 = sum(1 for qid in question_ids if reference_result["per_question"][qid]["hit50"])

    cand_mrr, ref_mrr = paired_arrays(candidate_result["per_question"], reference_result["per_question"], question_ids, "rr10")
    mrr_boot = p3a.paired_bootstrap_delta_ci(cand_mrr, ref_mrr, seed=p3a.BOOTSTRAP_SEED, iterations=p3a.BOOTSTRAP_ITERATIONS)

    cand_ndcg, ref_ndcg = paired_arrays(candidate_result["per_question"], reference_result["per_question"], question_ids, "ndcg10")
    ndcg_boot = p3a.paired_bootstrap_delta_ci(cand_ndcg, ref_ndcg, seed=p3a.BOOTSTRAP_SEED, iterations=p3a.BOOTSTRAP_ITERATIONS)

    cand_hit10, ref_hit10 = paired_arrays(
        {k: {"h": 1.0 if v["hit10"] else 0.0} for k, v in candidate_result["per_question"].items()},
        {k: {"h": 1.0 if v["hit10"] else 0.0} for k, v in reference_result["per_question"].items()},
        question_ids, "h",
    )
    recall10_boot = p3a.paired_bootstrap_delta_ci(cand_hit10, ref_hit10, seed=p3a.BOOTSTRAP_SEED, iterations=p3a.BOOTSTRAP_ITERATIONS)

    gained10 = [qid for qid in question_ids
                if not reference_result["per_question"][qid]["hit10"] and candidate_result["per_question"][qid]["hit10"]]
    lost10 = [qid for qid in question_ids
              if reference_result["per_question"][qid]["hit10"] and not candidate_result["per_question"][qid]["hit10"]]
    gained50 = [qid for qid in question_ids
                if not reference_result["per_question"][qid]["hit50"] and candidate_result["per_question"][qid]["hit50"]]
    lost50 = [qid for qid in question_ids
              if reference_result["per_question"][qid]["hit50"] and not candidate_result["per_question"][qid]["hit50"]]

    rank_moves = []
    for qid in question_ids:
        c_rank = candidate_result["per_question"][qid]["rank10"]
        r_rank = reference_result["per_question"][qid]["rank10"]
        if c_rank is not None and r_rank is not None and c_rank != r_rank:
            rank_moves.append({"question_id": qid, "reference_rank10": r_rank, "candidate_rank10": c_rank,
                                "delta": r_rank - c_rank})
    rank_moves.sort(key=lambda m: -abs(m["delta"]))

    return {
        "recall50_hit_delta": cand_hit50 - ref_hit50,
        "recall10_hit_delta": sum(1 for qid in question_ids if candidate_result["per_question"][qid]["hit10"])
                               - sum(1 for qid in question_ids if reference_result["per_question"][qid]["hit10"]),
        "mrr_ci": (mrr_boot.ci_lo, mrr_boot.ci_hi), "mrr_point_estimate": mrr_boot.point_estimate,
        "ndcg_ci": (ndcg_boot.ci_lo, ndcg_boot.ci_hi), "ndcg_point_estimate": ndcg_boot.point_estimate,
        "recall10_ci": (recall10_boot.ci_lo, recall10_boot.ci_hi),
        "hit10_gained": gained10, "hit10_lost": lost10,
        "hit50_gained": gained50, "hit50_lost": lost50,
        "notable_rank_moves": rank_moves[:10],
    }


# --------------------------------------------------------------- ablation table rows

def candidate_to_ablation_row(candidate_result: dict, *, run_id: str, sha: str, config_hash: str,
                               eval_scope_sha256: str, corpus_document_count: int) -> dict:
    m = candidate_result["metrics"]
    lat = candidate_result["latency_ms"]
    embed_stats = candidate_result.get("embed_stats", {})
    index_stats = candidate_result.get("index_stats", {})
    return {
        "row_id": candidate_result["row_id"], "configuration": candidate_result["label"],
        "status": "phase3_2_ablation", "run_id": run_id, "git_sha": sha, "phase3_config_hash": config_hash,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND, "eval_scope_sha256": eval_scope_sha256,
        "question_count": candidate_result["question_count"], "corpus_document_count": corpus_document_count,
        "chunk_count": candidate_result["chunk_stats"]["chunk_count"],
        "chunk_config_hash": candidate_result["chunk_config_hash"],
        "embedding_model": MODEL_REPO, "embedding_revision": MODEL_REVISION,
        "embedding_identity": None, "index_identity": None,
        "retrieval": p3.RETRIEVAL_TYPE, "candidate_k": CANDIDATE_K,
        "doc_recall_at_10": m["doc_recall_at_10"], "doc_recall_at_50": m["doc_recall_at_50"],
        "doc_mrr": m["doc_mrr"], "doc_ndcg_at_10": m["doc_ndcg_at_10"],
        "precision_at_5": p3.NA, "refusal_metric": p3.NA,
        "retrieval_latency_p50_ms": lat["retrieval_total"]["p50"], "retrieval_latency_p95_ms": lat["retrieval_total"]["p95"],
        "query_embedding_latency_p50_ms": lat["query_embedding"]["p50"], "search_latency_p50_ms": lat["vector_search"]["p50"],
        "index_size_bytes": index_stats.get("index_size_bytes", p3.NA),
        "notes": (
            f"Task 3.2 {candidate_result['round']}: window={candidate_result['window_size_tokens']}, "
            f"overlap={candidate_result['overlap_tokens']}, split_mode={candidate_result['split_mode']}."
            + (f" {candidate_result['encoder_truncation_note']}" if candidate_result.get("encoder_truncation_note") else "")
        ),
    }


# --------------------------------------------------------------- round orchestration

def row0_as_candidate_result(baseline: dict) -> dict:
    """Row 0's frozen aggregate metrics, reshaped into the candidate_result
    shape used for tie-break bookkeeping (chunk_count etc come from the
    ablation table). Per-question data for row 0 is obtained separately by
    actually evaluating A0 (reuse_row_id='0') against the live frozen
    index - this function only supplies the frozen aggregate for sanity
    cross-checking against that fresh A0 evaluation."""
    m = baseline["metrics"]
    return {
        "doc_recall_at_10": m["doc_recall@10"], "doc_recall_at_50": m["doc_recall@50"],
        "doc_mrr": m["doc_mrr"], "doc_ndcg_at_10": m["doc_ndcg@10"],
    }


def run_round(round_letter: str, candidates: list[p3a.ChunkCandidate], reference_row_id: str, *,
              provenance, filings, parsed_docs, tokenizer, storage, model,
              scoped_questions, frozen_scope_ids, resume: bool, baseline_check: dict | None) -> dict:
    print()
    print(f"[STAGE] Round {round_letter}: {[c.row_id for c in candidates]}")

    results: dict[str, dict] = {}
    for candidate in candidates:
        result = process_candidate(
            candidate, provenance=provenance, filings=filings, parsed_docs=parsed_docs, tokenizer=tokenizer,
            storage=storage, model=model, scoped_questions=scoped_questions, frozen_scope_ids=frozen_scope_ids,
            resume=resume,
        )
        results[candidate.row_id] = result

        if candidate.row_id == reference_row_id and baseline_check is not None:
            for key, frozen_key in (("doc_recall_at_10", "doc_recall@10"), ("doc_recall_at_50", "doc_recall@50"),
                                     ("doc_mrr", "doc_mrr"), ("doc_ndcg_at_10", "doc_ndcg@10")):
                fresh = result["metrics"][key]
                frozen = baseline_check[frozen_key]
                if abs(fresh - frozen) > 1e-9:
                    raise SystemExit(
                        f"FATAL: reference {reference_row_id} fresh evaluation {key}={fresh} != "
                        f"frozen row 0 value {frozen} - retrieval is not reproducing row 0 exactly. STOP."
                    )
            print(f"[{reference_row_id}] fresh evaluation reproduces frozen row 0 metrics exactly - verified.")

    bootstrap = {}
    for row_id, result in results.items():
        if row_id == reference_row_id:
            continue
        bootstrap[row_id] = bootstrap_vs_reference(result, results[reference_row_id], frozen_scope_ids)

    reference = results[reference_row_id]
    quality_rows = [
        {"row_id": rid, "doc_recall_at_50": r["metrics"]["doc_recall_at_50"], "doc_mrr": r["metrics"]["doc_mrr"],
         "doc_ndcg_at_10": r["metrics"]["doc_ndcg_at_10"], "doc_recall_at_10": r["metrics"]["doc_recall_at_10"],
         "chunk_count": r["chunk_stats"]["chunk_count"],
         "embedding_artifact_size_bytes": r["embed_stats"].get("artifact_size_bytes", 0),
         "index_size_bytes": r["index_stats"].get("index_size_bytes", 0),
         "retrieval_latency_p95_ms": r["latency_ms"]["retrieval_total"]["p95"] or 0.0,
         "build_seconds_total": r.get("build_seconds_total") or 0.0,
         "split_mode": r["split_mode"]}
        for rid, r in results.items()
    ]
    selection = p3a.select_round_winner(
        reference_row_id=reference_row_id, candidates=quality_rows,
        bootstrap_vs_reference={rid: {"recall50_hit_delta": b["recall50_hit_delta"], "mrr_ci": b["mrr_ci"], "ndcg_ci": b["ndcg_ci"]}
                                 for rid, b in bootstrap.items()},
    )
    if selection.flagged_for_user_decision:
        raise SystemExit(f"STOP - Round {round_letter} requires a user decision: {selection.flag_reason}")

    print(f"Round {round_letter} winner: {selection.winner_row_id} - {selection.rationale}")

    return {
        "round": round_letter, "reference_row_id": reference_row_id,
        "results": results, "bootstrap": bootstrap, "selection": selection.to_dict(),
    }


# --------------------------------------------------------------- CLI actions

def cmd_plan() -> int:
    config, config_hash = load_experiment_config()
    print("[STAGE 3/10] Frozen Task 3.2 chunking experiment grid")
    print(f"phase3_2_config_hash: {config_hash}")
    print(json.dumps(config, indent=2))
    print()
    print("Round A:", [c["row_id"] for c in config["round_a_candidates"]])
    print("Round B policy:", config["round_b_policy"][:120], "...")
    print("Round C policy:", config["round_c_policy"][:120], "...")
    return 0


def cmd_status() -> int:
    decisions = load_decisions()
    print("Task 3.2 status (read-only)")
    print(f"Round decisions recorded: {list(decisions.get('rounds', {}).keys())}")
    for row_id in ("A0", "A1", "A2", "B0", "B1", "B2", "C0", "C1"):
        result = load_candidate_result(row_id)
        if result is None:
            print(f"  {row_id}: not built")
        else:
            m = result["metrics"]
            print(f"  {row_id} ({result['label']}): recall@10={m['doc_recall_at_10']:.4f} "
                  f"recall@50={m['doc_recall_at_50']:.4f} mrr={m['doc_mrr']:.4f} ndcg@10={m['doc_ndcg_at_10']:.4f}")
    return 0


def run_full(resume: bool) -> int:
    print("[STAGE 1/10] Task 3.2 preflight")
    frozen_scope_ids, baseline = load_frozen_scope()
    dev_payload = load_dev_questions()
    questions_by_id = {q["question_id"]: q for q in dev_payload["questions"]}
    scoped_questions = [questions_by_id[qid] for qid in frozen_scope_ids]
    p3a.assert_dev_split("dev")
    print(f"Frozen scope verified: {len(frozen_scope_ids)} questions, hash matches config.")

    storage = get_storage()
    provenance = cdc.verify_task_1_2_provenance(storage)
    manifest = cdc.load_and_verify_manifest(storage)
    filings = manifest["filings"]
    print(f"Manifest verified: {len(filings)} filings.")

    print("[STAGE 2/10] Encoder-length compatibility audit")
    print(f"Encoder max sequence length: {p3a.ENCODER_MAX_SEQ_LENGTH_TOKENS} tokens (BAAI/bge-small-en-v1.5, verified).")

    tokenizer = cdc.load_tokenizer()
    parsed_docs = cdc.resolve_and_parse_documents(provenance, filings)

    print("[STAGE 4/10] Implement experimental chunking configurations - ready")
    print("[STAGE 5/10] Build candidate artifacts")
    print("[STAGE 6/10] Evaluate chunking candidates")

    model = load_model(device="cuda")

    round_a = run_round(
        "A", p3a.round_a_candidates(), reference_row_id="A0",
        provenance=provenance, filings=filings, parsed_docs=parsed_docs, tokenizer=tokenizer,
        storage=storage, model=model, scoped_questions=scoped_questions, frozen_scope_ids=frozen_scope_ids,
        resume=resume, baseline_check=baseline["metrics"],
    )
    decisions = load_decisions()
    decisions["rounds"]["A"] = round_a["selection"]
    save_decisions(decisions)

    a_winner_id = round_a["selection"]["winner_row_id"]
    a_winner = p3a.round_a_candidates()[["A0", "A1", "A2"].index(a_winner_id)]
    winner_window = a_winner.window_size_tokens

    round_b = run_round(
        "B", p3a.round_b_candidates(winner_window, winner_row_id=a_winner_id), reference_row_id="B0",
        provenance=provenance, filings=filings, parsed_docs=parsed_docs, tokenizer=tokenizer,
        storage=storage, model=model, scoped_questions=scoped_questions, frozen_scope_ids=frozen_scope_ids,
        resume=resume, baseline_check=None,
    )
    decisions["rounds"]["B"] = round_b["selection"]
    save_decisions(decisions)

    b_candidates = p3a.round_b_candidates(winner_window, winner_row_id=a_winner_id)
    b_winner_id = round_b["selection"]["winner_row_id"]
    b_winner = b_candidates[["B0", "B1", "B2"].index(b_winner_id)]
    winner_overlap = b_winner.overlap_tokens

    round_c = run_round(
        "C", p3a.round_c_candidates(winner_window_tokens=winner_window, winner_overlap_tokens=winner_overlap,
                                    winner_row_id=b_winner_id),
        reference_row_id="C0",
        provenance=provenance, filings=filings, parsed_docs=parsed_docs, tokenizer=tokenizer,
        storage=storage, model=model, scoped_questions=scoped_questions, frozen_scope_ids=frozen_scope_ids,
        resume=resume, baseline_check=None,
    )
    decisions["rounds"]["C"] = round_c["selection"]
    save_decisions(decisions)

    c_winner_id = round_c["selection"]["winner_row_id"]

    print()
    print("[STAGE 9/10] Update Phase 3 ablation table")
    sha = git_sha()
    config, config_hash = load_experiment_config()
    corpus_doc_count = len({fl["document_id"] for fl in filings})
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    for round_data in (round_a, round_b, round_c):
        for row_id, result in round_data["results"].items():
            if result["chunk_stats"].get("reused") and result.get("reuse_row_id"):
                continue  # do not append a duplicate row for a reused prior-round artifact
            run_id_stub = f"phase3_2_{row_id}_{sha[:12]}"
            row = candidate_to_ablation_row(
                result, run_id=run_id_stub, sha=sha, config_hash=config_hash,
                eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
                corpus_document_count=corpus_doc_count,
            )
            existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    print("[STAGE 10/10] Verify and close Task 3.2 - build/eval phase complete")
    print(f"Final winner chain: Round A={a_winner_id}, Round B={b_winner_id}, Round C={c_winner_id}")
    return 0


def cmd_compare() -> int:
    decisions = load_decisions()
    if set(decisions.get("rounds", {})) != {"A", "B", "C"}:
        print("Not all rounds complete yet - run --run --resume first.")
        return 1
    print(json.dumps(decisions, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.2 - controlled Phase 3 chunking ablation.")
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
