"""Task 2.7 - MS MARCO benchmark harness CLI.

Validates this repository's retrieval + evaluation harness against the
standard MS MARCO dev-small benchmark (6,980 queries) before trusting
future SEC retrieval scores. Entirely isolated from the SEC corpus - all
derived artifacts live under artifacts/benchmark/msmarco/ (gitignored).

Modes:
    --dry-run   verify paths/schemas/counts/config/model availability/
                disk estimate - no GPU load, no embedding, fast.
    --pilot     embed+index a small deterministic passage subsample and
                evaluate a small query subsample end to end. PILOT ONLY -
                never the reported benchmark result.
    --build     embed+index the full 8,841,823-passage corpus, in
                resumable row-range shards under
                artifacts/benchmark/msmarco/embeddings/.
    --evaluate  run all 6,980 dev-small queries against the full index,
                compute passage_recall@10 / passage_mrr / passage_ndcg@10,
                write results/phase_2_7_msmarco_harness.json.

Reuses src/embeddings/bge.py's frozen BAAI/bge-small-en-v1.5 contract
(same model/revision/query-instruction/normalization as Phase 1) and
src/index/lancedb_index.py's frozen exact-cosine search contract
(no ANN) - never a new model, never a new similarity definition.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.embeddings.bge import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    EMBEDDING_DIMENSION,
    MODEL_REPO,
    MODEL_REVISION,
    VECTOR_DTYPE,
    encode_passages,
    encode_queries,
    load_model,
    validate_vectors,
)
from src.index import lancedb_index as idx  # noqa: E402
from src.eval import msmarco_harness as mh  # noqa: E402

CORPUS_PATH = Path("data") / "msmarco" / "corpus.parquet"
QUERIES_PATH = Path("data") / "msmarco" / "queries.parquet"
QRELS_VALIDATION_PATH = Path("data") / "msmarco" / "qrels_validation.parquet"

BENCHMARK_ROOT = Path("artifacts") / "benchmark" / "msmarco"
EMBEDDINGS_DIR = BENCHMARK_ROOT / "embeddings"
INDEX_DIR = BENCHMARK_ROOT / "index"
RETRIEVAL_DIR = BENCHMARK_ROOT / "retrieval"
PILOT_ROOT = BENCHMARK_ROOT / "pilot"

CONFIG_PATH = Path("configs") / "phase_2_7_msmarco_harness.json"
SUMMARY_PATH = Path("results") / "phase_2_7_msmarco_harness.json"

SHARD_SIZE = 200_000
TOP_K = 10

REFERENCE = {
    "source": (
        "BAAI/bge-small-en-v1.5 self-reported BEIR benchmark table "
        "(cross-confirmed via two independent web searches on 2026-09-01; "
        "the exact primary-source table cell could not be directly "
        "rendered via automated fetch in this session - value corroborated "
        "from two independent search-engine result summaries, not read "
        "directly off a table)"
    ),
    "benchmark": "BEIR/MTEB MSMARCO retrieval task (standard MS MARCO passage dev-small, 6,980 queries)",
    "model": "BAAI/bge-small-en-v1.5",
    "metric": "nDCG@10",
    "value": 0.408,
    "caveats": (
        "The MTEB community has documented reproducibility discrepancies "
        "between self-reported and independently-reproduced BGE scores "
        "(github.com/embeddings-benchmark/mteb issue #1912). Treated as an "
        "approximate reference, not a strict pass/fail threshold - see "
        "project_plan/PHASE2_MSMARCO_HARNESS.md."
    ),
    "apples_to_apples": "PARTIAL",
}


def git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def build_config(*, top_k: int = TOP_K) -> dict:
    return {
        "benchmark": mh.BENCHMARK_ID,
        "benchmark_config_version": mh.BENCHMARK_CONFIG_VERSION,
        "split": "validation",
        "corpus_path": str(CORPUS_PATH),
        "queries_path": str(QUERIES_PATH),
        "qrels_path": str(QRELS_VALIDATION_PATH),
        "model": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "passage_prefix": "",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "normalize_embeddings": True,
        "similarity": "cosine",
        "search_mode": "exact",
        "top_k": top_k,
        "metrics": ["passage_recall@10", "passage_mrr", "passage_ndcg@10"],
        "metric_versions": {"passage_recall@10": "1.0", "passage_mrr": "1.0", "passage_ndcg@10": "1.0"},
        "batch_size": DEFAULT_BATCH_SIZE,
        "dtype": str(VECTOR_DTYPE),
        "shard_size": SHARD_SIZE,
    }


def dataset_hashes() -> dict:
    """Semantic identity hashes over the frozen MS MARCO inputs - counts
    plus a stable content fingerprint, not the raw file bytes (Parquet
    metadata/compression can differ without a semantic change)."""
    con = duckdb.connect()
    corpus_count = con.execute(f"select count(*) from read_parquet('{CORPUS_PATH.as_posix()}')").fetchone()[0]
    queries_count = con.execute(f"select count(*) from read_parquet('{QUERIES_PATH.as_posix()}')").fetchone()[0]
    qrel_count = con.execute(f"select count(*) from read_parquet('{QRELS_VALIDATION_PATH.as_posix()}')").fetchone()[0]
    qrel_rows = con.execute(f'select "query-id", "corpus-id", score from read_parquet(\'{QRELS_VALIDATION_PATH.as_posix()}\') order by "query-id", "corpus-id"').fetchall()
    import hashlib
    qrels_payload = json.dumps(qrel_rows, sort_keys=False, separators=(",", ":")).encode("utf-8")
    qrels_sha256 = hashlib.sha256(qrels_payload).hexdigest()
    return {
        "corpus_count": corpus_count,
        "queries_count": queries_count,
        "validation_qrel_count": qrel_count,
        "validation_qrels_sha256": qrels_sha256,
    }


def resource_preflight(corpus_count: int, top_k: int) -> dict:
    vector_bytes = corpus_count * EMBEDDING_DIMENSION * 4  # float32
    con = duckdb.connect()
    avg_text_len = con.execute(f"select avg(length(text)) from read_parquet('{CORPUS_PATH.as_posix()}')").fetchone()[0]
    text_bytes = int(corpus_count * (avg_text_len or 0))
    estimated_total_bytes = vector_bytes + text_bytes
    free_bytes = shutil.disk_usage(REPO_ROOT.anchor or "/").free
    shard_count = (corpus_count + SHARD_SIZE - 1) // SHARD_SIZE

    gpu_info = {"cuda_available": False}
    try:
        import torch
        gpu_info["cuda_available"] = torch.cuda.is_available()
        if gpu_info["cuda_available"]:
            gpu_info["gpu_name"] = torch.cuda.get_device_name(0)
            gpu_info["gpu_vram_bytes"] = torch.cuda.get_device_properties(0).total_memory
    except Exception:
        pass

    return {
        "corpus_rows": corpus_count,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "dtype": str(VECTOR_DTYPE),
        "estimated_vector_bytes": vector_bytes,
        "estimated_text_bytes": text_bytes,
        "estimated_total_artifact_bytes": estimated_total_bytes,
        "free_disk_bytes": free_bytes,
        "shard_size": SHARD_SIZE,
        "estimated_shard_count": shard_count,
        "top_k": top_k,
        "gpu": gpu_info,
    }


def print_preflight(preflight: dict) -> None:
    gb = 1024 ** 3
    print("Resource preflight:")
    print(f"  corpus rows:                 {preflight['corpus_rows']:,}")
    print(f"  embedding dimension:         {preflight['embedding_dimension']}")
    print(f"  dtype:                       {preflight['dtype']}")
    print(f"  estimated vector bytes:      {preflight['estimated_vector_bytes'] / gb:.2f} GB")
    print(f"  estimated text bytes:        {preflight['estimated_text_bytes'] / gb:.2f} GB")
    print(f"  estimated total artifact:    {preflight['estimated_total_artifact_bytes'] / gb:.2f} GB")
    print(f"  free disk:                   {preflight['free_disk_bytes'] / gb:.2f} GB")
    print(f"  shard size / count:          {preflight['shard_size']:,} / {preflight['estimated_shard_count']}")
    print(f"  GPU:                         {preflight['gpu']}")


def cmd_dry_run() -> None:
    print("=== MS MARCO harness dry run ===")
    for p in (CORPUS_PATH, QUERIES_PATH, QRELS_VALIDATION_PATH):
        if not p.exists():
            print(f"MISSING: {p}", file=sys.stderr)
            raise SystemExit(1)
    hashes = dataset_hashes()
    print("dataset counts:", hashes)
    if hashes["corpus_count"] != mh.EXPECTED_CORPUS_COUNT:
        print(f"STOP: corpus count {hashes['corpus_count']} != expected {mh.EXPECTED_CORPUS_COUNT}", file=sys.stderr)
        raise SystemExit(1)
    if hashes["validation_qrel_count"] != mh.EXPECTED_VALIDATION_QREL_COUNT:
        print(f"STOP: qrel count {hashes['validation_qrel_count']} != expected {mh.EXPECTED_VALIDATION_QREL_COUNT}", file=sys.stderr)
        raise SystemExit(1)

    config = build_config()
    config_hash = mh.compute_config_hash(config)
    print("config_hash:", config_hash)

    preflight = resource_preflight(hashes["corpus_count"], TOP_K)
    print_preflight(preflight)

    try:
        model = load_model(device="cuda")
        print("model loaded OK on", next(model.parameters()).device)
        del model
    except Exception as exc:
        print(f"model load check FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print("DRY RUN OK")


def _shard_path(prefix: Path, shard_index: int) -> Path:
    return prefix / f"shard_{shard_index:04d}.parquet"


def _embed_shards(*, out_dir: Path, corpus_query: str, total_rows: int, shard_size: int, model, config_hash: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = {"config_hash": config_hash, "shards": []}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            existing = json.load(f)
        if existing.get("config_hash") == config_hash:
            manifest = existing
        else:
            print(f"WARNING: stale manifest at {manifest_path} (config_hash mismatch) - rebuilding from scratch")

    completed_shards = {s["shard_index"] for s in manifest["shards"]}
    con = duckdb.connect()
    shard_count = (total_rows + shard_size - 1) // shard_size
    total_embedded = 0
    t0 = time.time()

    for shard_index in range(shard_count):
        offset = shard_index * shard_size
        limit = min(shard_size, total_rows - offset)
        shard_path = _shard_path(out_dir, shard_index)

        if shard_index in completed_shards and shard_path.exists():
            total_embedded += limit
            continue

        rows = con.execute(f"{corpus_query} LIMIT {limit} OFFSET {offset}").to_arrow_table()
        ids = [mh.canonical_id(x) for x in rows.column("_id").to_pylist()]
        texts = rows.column("text").to_pylist()

        vectors = encode_passages(model, texts)
        validate_vectors(vectors, expect_normalized=True)

        tmp_path = shard_path.with_suffix(".parquet.tmp")
        vector_array = pa.FixedSizeListArray.from_arrays(
            pa.array(vectors.reshape(-1), type=pa.float32()), EMBEDDING_DIMENSION,
        )
        schema = pa.schema([
            pa.field("corpus_id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIMENSION)),
        ])
        table = pa.table({"corpus_id": ids, "text": texts, "vector": vector_array}, schema=schema)
        pq.write_table(table, tmp_path)
        tmp_path.replace(shard_path)

        total_embedded += limit
        manifest["shards"] = [s for s in manifest["shards"] if s["shard_index"] != shard_index]
        manifest["shards"].append({"shard_index": shard_index, "row_count": limit, "offset": offset})
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        elapsed = time.time() - t0
        rate = total_embedded / elapsed if elapsed > 0 else 0.0
        print(f"shard {shard_index + 1}/{shard_count}: {total_embedded:,}/{total_rows:,} rows embedded ({rate:.1f} rows/sec)")

    return {"total_embedded": total_embedded, "elapsed_sec": time.time() - t0, "shard_count": shard_count}


def cmd_pilot(pilot_size: int = 20_000, query_sample: int = 200) -> None:
    print(f"=== MS MARCO PILOT (PILOT ONLY - not the benchmark result): {pilot_size} passages, {query_sample} queries ===")
    config = build_config()
    config_hash = mh.compute_config_hash(config)

    model = load_model(device="cuda")
    print(f"model device: {next(model.parameters()).device}")

    emb_dir = PILOT_ROOT / "embeddings"
    if emb_dir.exists():
        shutil.rmtree(emb_dir)  # pilot artifacts are always rebuilt fresh - never resumed, never the real build
    stats = _embed_shards(
        out_dir=emb_dir,
        corpus_query=f"select _id, text from read_parquet('{CORPUS_PATH.as_posix()}')",
        total_rows=pilot_size, shard_size=pilot_size, model=model, config_hash=config_hash,
    )
    print("pilot embedding stats:", stats)

    con = duckdb.connect()
    # Read directly via pyarrow (not duckdb's read_parquet) - preserves the
    # exact fixed_size_list<float32,384> vector schema LanceDB expects;
    # DuckDB's parquet reader renames the list child field, which breaks
    # LanceDB's schema alignment on create_table.
    table = pq.read_table(emb_dir / "shard_0000.parquet")

    index_dir = PILOT_ROOT / "index"
    if index_dir.exists():
        shutil.rmtree(index_dir)
    db = idx.open_database(index_dir)
    pilot_table = db.create_table("msmarco_pilot", data=table)

    qrels_rows = con.execute(f'select "query-id", "corpus-id", score from read_parquet(\'{QRELS_VALIDATION_PATH.as_posix()}\')').fetchall()
    qrel_rows_dicts = [{"query-id": r[0], "corpus-id": r[1], "score": r[2]} for r in qrels_rows]
    grouped = mh.group_qrels(qrel_rows_dicts)

    pilot_corpus_ids = set(table.column("corpus_id").to_pylist())
    eligible_qids = [qid for qid, qs in grouped.items() if qs.relevant_ids & pilot_corpus_ids]
    print(f"queries with >=1 relevant passage inside the pilot subsample: {len(eligible_qids)}")
    sample_qids = sorted(eligible_qids, key=lambda q: mh.canonical_id(q))[:query_sample]

    queries_table = con.execute(f"select _id, text from read_parquet('{QUERIES_PATH.as_posix()}')").to_arrow_table()
    query_text_by_id = {mh.canonical_id(i): t for i, t in zip(queries_table.column("_id").to_pylist(), queries_table.column("text").to_pylist())}

    results = []
    for qid in sample_qids:
        qtext = query_text_by_id.get(qid)
        if qtext is None:
            continue
        qvec = encode_queries(model, [qtext])[0]
        hits = idx.exact_cosine_search(pilot_table, qvec, limit=TOP_K)
        retrieved_ids = hits.column("corpus_id").to_pylist()
        r = mh.evaluate_query(query_id=qid, retrieved_ids=retrieved_ids, relevant_ids=grouped[qid].relevant_ids & pilot_corpus_ids, k=TOP_K)
        results.append(r)

    if results:
        agg = mh.aggregate_results(results, k=TOP_K)
        print(f"PILOT ONLY result - query_count={agg.query_count} recall@10={agg.passage_recall_at_k['value']:.4f} "
              f"mrr={agg.passage_mrr:.4f} ndcg@10={agg.passage_ndcg_at_k:.4f}")
    else:
        print("PILOT ONLY - no eligible queries found in the pilot subsample (expected for a small random subsample)")
    print("PILOT COMPLETE (PILOT ONLY - discard before trusting any number above)")


def cmd_build() -> None:
    print("=== MS MARCO full corpus embedding build ===")
    config = build_config()
    config_hash = mh.compute_config_hash(config)
    print("config_hash:", config_hash)

    con = duckdb.connect()
    total_rows = con.execute(f"select count(*) from read_parquet('{CORPUS_PATH.as_posix()}')").fetchone()[0]
    if total_rows != mh.EXPECTED_CORPUS_COUNT:
        raise SystemExit(f"STOP: corpus count {total_rows} != expected {mh.EXPECTED_CORPUS_COUNT}")

    model = load_model(device="cuda")
    print(f"model device: {next(model.parameters()).device}")

    stats = _embed_shards(
        out_dir=EMBEDDINGS_DIR,
        corpus_query=f"select _id, text from read_parquet('{CORPUS_PATH.as_posix()}')",
        total_rows=total_rows, shard_size=SHARD_SIZE, model=model, config_hash=config_hash,
    )
    print("build stats:", stats)

    print("building LanceDB index from shards...")
    if INDEX_DIR.exists():
        existing_meta = INDEX_DIR / "build_config_hash.txt"
        if existing_meta.exists() and existing_meta.read_text().strip() == config_hash:
            print("index already built with matching config_hash - skipping rebuild")
            return
        print("stale index (config_hash mismatch or missing marker) - rebuilding")
        shutil.rmtree(INDEX_DIR)

    shard_files = sorted(EMBEDDINGS_DIR.glob("shard_*.parquet"))
    db = idx.open_database(INDEX_DIR)
    first = pq.read_table(shard_files[0])
    table = db.create_table("msmarco_corpus", data=first)
    for shard_file in shard_files[1:]:
        table.add(pq.read_table(shard_file))
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / "build_config_hash.txt").write_text(config_hash)
    print(f"index built: {table.count_rows():,} rows")


def _verify_batched_search_matches_lancedb(*, table, shard_files: list[Path], query_ids: list[str], query_vectors, k: int, sample: int = 5) -> None:
    """Section 31: verify a small sample of the fast batched exact search
    against LanceDB's own exact_cosine_search - proves both compute the
    IDENTICAL exact cosine top-k (same distance definition), not an
    approximation. Raises AssertionError on any mismatch beyond
    float32 precision noise."""
    import numpy as np

    for i in range(min(sample, len(query_ids))):
        qvec = np.asarray(query_vectors[i], dtype=np.float32)
        lance_hits = idx.exact_cosine_search(table, qvec, limit=k)
        lance_ids = [mh.canonical_id(x) for x in lance_hits.column("corpus_id").to_pylist()]

        sims_all = []
        for shard_file in shard_files:
            shard = pq.read_table(shard_file, columns=["corpus_id", "vector"])
            vecs = np.array(shard.column("vector").to_pylist(), dtype=np.float32)
            sims = vecs @ qvec
            for cid, s in zip(shard.column("corpus_id").to_pylist(), sims):
                sims_all.append((float(s), cid))
        sims_all.sort(key=lambda t: -t[0])
        manual_ids = [cid for _, cid in sims_all[:k]]

        if manual_ids != lance_ids:
            raise AssertionError(
                f"batched exact search disagrees with LanceDB for query {query_ids[i]!r}: "
                f"{manual_ids} != {lance_ids}"
            )
    print(f"batched-search vs LanceDB equivalence check PASSED on {min(sample, len(query_ids))} sample queries")


def _batched_exact_search(*, shard_files: list[Path], query_vectors, top_k: int, query_batch: int = 500) -> list[list[str]]:
    """Exact (never approximate) cosine top-k search via blocked GPU
    matmul against every corpus shard - mathematically identical to
    LanceDB's per-query exact_cosine_search (verified above), just fast
    enough to evaluate 6,980 queries against 8.8M passages in minutes
    instead of the ~14 hours a naive per-query LanceDB loop would take.
    Returns retrieved_ids[i] = rank-ordered top_k canonical corpus IDs
    for query i."""
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    n_queries = len(query_vectors)
    q_all = torch.from_numpy(np.asarray(query_vectors, dtype=np.float32)).to(device)

    candidates: list[list[tuple[float, str]]] = [[] for _ in range(n_queries)]

    for shard_idx, shard_file in enumerate(shard_files):
        shard = pq.read_table(shard_file, columns=["corpus_id", "vector"])
        shard_ids = shard.column("corpus_id").to_pylist()
        shard_vecs = np.array(shard.column("vector").to_pylist(), dtype=np.float32)
        v = torch.from_numpy(shard_vecs).to(device)  # (shard_rows, dim)
        k_this = min(top_k, v.shape[0])

        for start in range(0, n_queries, query_batch):
            end = min(start + query_batch, n_queries)
            sims = q_all[start:end] @ v.T  # (batch, shard_rows) cosine similarity (both normalized)
            vals, idxs = torch.topk(sims, k_this, dim=1)
            vals_cpu = vals.cpu().numpy()
            idxs_cpu = idxs.cpu().numpy()
            for row in range(end - start):
                for col in range(k_this):
                    candidates[start + row].append((float(vals_cpu[row, col]), shard_ids[idxs_cpu[row, col]]))
        print(f"  batched search: shard {shard_idx + 1}/{len(shard_files)} done")

    results = []
    for cand in candidates:
        cand.sort(key=lambda t: -t[0])
        results.append([cid for _, cid in cand[:top_k]])
    return results


def cmd_evaluate() -> None:
    print("=== MS MARCO dev-small evaluation (all queries) ===")
    started = datetime.now(timezone.utc)
    config = build_config()
    config_hash = mh.compute_config_hash(config)

    if not INDEX_DIR.exists():
        raise SystemExit("STOP: no full index found - run --build first")
    marker = INDEX_DIR / "build_config_hash.txt"
    if not marker.exists() or marker.read_text().strip() != config_hash:
        raise SystemExit("STOP: index config_hash does not match current config - rebuild required")

    db = idx.open_database(INDEX_DIR)
    table = db.open_table("msmarco_corpus")
    row_count = table.count_rows()
    print(f"index row count: {row_count:,}")
    if row_count != mh.EXPECTED_CORPUS_COUNT:
        raise SystemExit(f"STOP: index has {row_count} rows, expected {mh.EXPECTED_CORPUS_COUNT}")

    shard_files = sorted(EMBEDDINGS_DIR.glob("shard_*.parquet"))

    model = load_model(device="cuda")

    con = duckdb.connect()
    qrels_rows = con.execute(f'select "query-id", "corpus-id", score from read_parquet(\'{QRELS_VALIDATION_PATH.as_posix()}\')').fetchall()
    qrel_dicts = [{"query-id": r[0], "corpus-id": r[1], "score": r[2]} for r in qrels_rows]
    grouped = mh.group_qrels(qrel_dicts)
    if len(grouped) != mh.EXPECTED_VALIDATION_QUERY_COUNT:
        raise SystemExit(f"STOP: {len(grouped)} distinct queries, expected {mh.EXPECTED_VALIDATION_QUERY_COUNT}")

    queries_table = con.execute(f"select _id, text from read_parquet('{QUERIES_PATH.as_posix()}')").to_arrow_table()
    query_text_by_id = {mh.canonical_id(i): t for i, t in zip(queries_table.column("_id").to_pylist(), queries_table.column("text").to_pylist())}

    ordered_qids = sorted(grouped, key=mh.canonical_id)
    query_texts = []
    for qid in ordered_qids:
        qtext = query_text_by_id.get(qid)
        if qtext is None:
            raise SystemExit(f"STOP: query_id {qid} has qrels but no query text - silent drop not allowed")
        query_texts.append(qtext)

    t0 = time.time()
    print(f"encoding {len(query_texts):,} queries...")
    query_vectors = encode_queries(model, query_texts)
    validate_vectors(query_vectors, expect_normalized=True)
    print(f"query encoding done in {time.time() - t0:.1f}s")

    _verify_batched_search_matches_lancedb(
        table=table, shard_files=shard_files, query_ids=ordered_qids, query_vectors=query_vectors, k=TOP_K, sample=5,
    )

    t1 = time.time()
    retrieved_by_query = _batched_exact_search(shard_files=shard_files, query_vectors=query_vectors, top_k=TOP_K)
    print(f"batched exact search over {row_count:,} passages x {len(ordered_qids):,} queries done in {time.time() - t1:.1f}s")

    RETRIEVAL_DIR.mkdir(parents=True, exist_ok=True)
    per_query_rows = []
    results = []
    for qid, retrieved_ids in zip(ordered_qids, retrieved_by_query):
        r = mh.evaluate_query(query_id=qid, retrieved_ids=retrieved_ids, relevant_ids=grouped[qid].relevant_ids, k=TOP_K)
        results.append(r)
        for rank, rid in enumerate(retrieved_ids, start=1):
            per_query_rows.append({"query_id": qid, "rank": rank, "corpus_id": rid})

    elapsed = time.time() - t0
    print(f"evaluation complete: {len(results)} queries in {elapsed:.1f}s")

    pq.write_table(pa.table({
        "query_id": [r["query_id"] for r in per_query_rows],
        "rank": [r["rank"] for r in per_query_rows],
        "corpus_id": [r["corpus_id"] for r in per_query_rows],
    }), RETRIEVAL_DIR / "query_results.parquet")

    agg = mh.aggregate_results(results, k=TOP_K)
    result_hash = mh.compute_result_hash(results)

    import hashlib
    with open(RETRIEVAL_DIR / "query_results.parquet", "rb") as f:
        retrieval_artifact_sha256 = hashlib.sha256(f.read()).hexdigest()

    measured = {
        "passage_recall@10": agg.passage_recall_at_k,
        "passage_mrr": agg.passage_mrr,
        "passage_ndcg@10": agg.passage_ndcg_at_k,
    }

    ndcg_diff = agg.passage_ndcg_at_k - REFERENCE["value"]
    if abs(ndcg_diff) <= 0.03:
        interpretation = "CONSISTENT"
    elif ndcg_diff < 0:
        interpretation = "LOWER THAN EXPECTED"
    else:
        interpretation = "HIGHER THAN EXPECTED"

    summary = {
        "schema_version": "1.0",
        "benchmark": mh.BENCHMARK_ID,
        "split": "validation",
        "created_at_utc": started.isoformat(),
        "git_sha": git_sha(),
        "query_count": len(results),
        "qrel_count": len(qrel_dicts),
        "corpus_count": row_count,
        "configuration": config,
        "config_hash": config_hash,
        "measured_metrics": measured,
        "reference": REFERENCE,
        "comparison": {
            "reference_metric": REFERENCE["metric"],
            "reference_value": REFERENCE["value"],
            "measured_value": agg.passage_ndcg_at_k,
            "absolute_difference": ndcg_diff,
            "interpretation": interpretation,
        },
        "run_duration_sec": elapsed,
        "result_hash": result_hash,
        "retrieval_artifact_path": str(RETRIEVAL_DIR / "query_results.parquet"),
        "retrieval_artifact_sha256": retrieval_artifact_sha256,
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, indent=2) + "\n")

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps({**config, "config_hash": config_hash}, indent=2) + "\n")

    print(json.dumps(measured, indent=2))
    print(f"interpretation: {interpretation}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        cmd_dry_run()
    elif args.pilot:
        cmd_pilot()
    elif args.build:
        cmd_build()
    elif args.evaluate:
        cmd_evaluate()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
