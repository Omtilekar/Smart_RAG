#!/usr/bin/env python
"""
FEASIBILITY / BENCHMARK CODE - NOT PRODUCTION PIPELINE IMPLEMENTATION

Phase 0 Task 0.10 serving feasibility spike (project_plan/PROJECT_EXECUTION.md,
"### 0.10 Serving feasibility spike"). Answers one question with measurement
instead of estimation: is a serverless (Lambda-shaped, CPU-only) retrieval
serving path plausible, or should the project plan around a continuously
warm service (Fargate) instead?

This is a throwaway. It builds a disposable ~100k-chunk benchmark corpus
from EDGAR-CORPUS (NOT the Phase 1 development corpus), a disposable
LanceDB index under artifacts/serving_spike/, and measures warm and
process-cold latency for two paths (vector-only, vector+rerank) plus a
flat-vs-quantized index comparison. It does not implement, and must not be
mistaken for, src/normalize, src/chunk, src/embeddings, src/index, or
src/retrieval.

Usage:
    python scripts/serving_spike.py [--target-chunks N] [--rebuild]
    python scripts/serving_spike.py --cold-run --index-dir <path>   (internal - spawned as a subprocess)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import get_settings  # noqa: E402
from src.logging_utils import configure_logging, get_logger, log_event  # noqa: E402
from src.storage import get_storage  # noqa: E402

log = get_logger("serving_spike")

RERANKER_REPO = "Xenova/ms-marco-MiniLM-L-6-v2"
RERANKER_ONNX_FILE = "onnx/model_int8.onnx"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
CHUNK_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 0
TARGET_CHUNKS_DEFAULT = 100_000
TOP_K = 50
WARMUP_QUERIES = 10
WARM_QUERY_TARGET = 180
COLD_SAMPLES = 10
CPU_THREADS = 2  # documented plausible small-Lambda-like allocation, not tuned further
SECTIONS_FOR_CORPUS = ["section_1", "section_1A", "section_7", "section_7A", "section_8"]
LANCEDB_QUANT = {"index_type": "IVF_PQ", "num_partitions": 100, "num_sub_vectors": 48, "num_bits": 8}


def esc(path) -> str:
    return str(path).replace("'", "''")


def spike_config_hash(config: dict) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def percentile_stats(samples_ms: list[float]) -> dict:
    if not samples_ms:
        return {"count": 0}
    s = sorted(samples_ms)
    n = len(s)

    def pct(p):
        idx = min(n - 1, max(0, round(p / 100 * (n - 1))))
        return s[idx]

    return {
        "count": n,
        "mean": round(statistics.fmean(s), 3),
        "median": round(statistics.median(s), 3),
        "p50": round(pct(50), 3),
        "p90": round(pct(90), 3),
        "p95": round(pct(95), 3),
        "p99": round(pct(99), 3) if n >= 20 else None,
        "min": round(s[0], 3),
        "max": round(s[-1], 3),
    }


def rss_mb() -> float:
    import psutil
    return psutil.Process().memory_info().rss / 1e6


def default_config(target_chunks: int) -> dict:
    return {
        "schema_version": 1,
        "corpus": {
            "source": "EDGAR-CORPUS (data/edgar_corpus/*.parquet)",
            "selection_method": "deterministic ORDER BY hash(filename)",
            "sections": SECTIONS_FOR_CORPUS,
            "target_chunk_count": target_chunks,
            "label": "DISPOSABLE SERVING-SPIKE CORPUS - NOT PHASE 1 DEVELOPMENT CORPUS",
        },
        "chunking": {
            "tokenizer": EMBEDDING_MODEL,
            "chunk_tokens": CHUNK_TOKENS,
            "overlap_tokens": CHUNK_OVERLAP_TOKENS,
            "note": "benchmark-local chunking only - not src/chunk/ production code",
        },
        "embedding": {"model": EMBEDDING_MODEL, "corpus_build_device": "cuda", "serving_device": "cpu"},
        "lancedb": {
            "flat": {"index": "none (brute-force exact search)"},
            "quantized": LANCEDB_QUANT,
        },
        "retrieval": {"top_k": TOP_K},
        "reranker": {
            "repo": RERANKER_REPO,
            "onnx_file": RERANKER_ONNX_FILE,
            "runtime": "onnxruntime",
            "provider": "CPUExecutionProvider",
            "quantization": "int8 (pre-quantized, published by Xenova)",
        },
        "queries": {
            "count_target": WARM_QUERY_TARGET,
            "label": "SERVING LATENCY PROBES ONLY - not a Phase 1/2 eval set, not LLM-generated",
        },
        "warmup": {"count": WARMUP_QUERIES},
        "measurement": {"warm_query_count_target": WARM_QUERY_TARGET, "cold_process_samples": COLD_SAMPLES},
        "resource_controls": {
            "cpu_threads": CPU_THREADS,
            "note": "torch/onnxruntime intra-op threads constrained for serving-like realism; "
            "this laptop's full core count is not used for the primary benchmark",
        },
    }


# =============================================================== corpus


def select_and_chunk_corpus(target_chunks: int) -> list[dict]:
    import duckdb
    from transformers import AutoTokenizer

    storage = get_storage()
    edgar_dir = storage.edgar_corpus_root
    splits = [edgar_dir / f"{s}.parquet" for s in ("train", "test", "validation")]
    splits = [p for p in splits if p.is_file()]
    if not splits:
        raise SystemExit("EDGAR-CORPUS parquet files not found under data/edgar_corpus/")
    union_sql = " UNION ALL ".join(f"SELECT * FROM read_parquet('{esc(p)}')" for p in splits)

    con = duckdb.connect()
    con.execute("SET enable_progress_bar=false")
    section_cols = ", ".join(SECTIONS_FOR_CORPUS)
    # Deterministic oversample - enough filings to plausibly reach target_chunks;
    # select_and_chunk_corpus stops early once the target is hit.
    n_filings = max(500, target_chunks // 15)
    rows = con.execute(
        f"SELECT filename, cik, year, {section_cols} FROM ({union_sql}) "
        f"ORDER BY hash(filename) LIMIT {n_filings}"
    ).fetchall()
    colnames = ["filename", "cik", "year"] + SECTIONS_FOR_CORPUS

    tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)

    chunks: list[dict] = []
    for row in rows:
        rec = dict(zip(colnames, row))
        for section in SECTIONS_FOR_CORPUS:
            text = rec.get(section)
            if not text or not text.strip():
                continue
            ids = tokenizer.encode(text, add_special_tokens=False)
            if not ids:
                continue
            for start in range(0, len(ids), CHUNK_TOKENS):
                window = ids[start:start + CHUNK_TOKENS]
                if len(window) < 20:
                    continue
                chunk_text = tokenizer.decode(window, skip_special_tokens=True)
                chunk_id = hashlib.sha1(f"{rec['filename']}|{section}|{start}".encode()).hexdigest()[:16]
                chunks.append({
                    "chunk_id": chunk_id,
                    "cik": str(rec["cik"]),
                    "year": str(rec["year"]),
                    "section": section,
                    "filename": rec["filename"],
                    "text": chunk_text,
                    "token_count": len(window),
                })
                if len(chunks) >= target_chunks:
                    con.close()
                    return chunks
    con.close()
    return chunks


# ============================================================= embedding


def build_corpus_embeddings(chunks: list[dict]):
    import torch
    from sentence_transformers import SentenceTransformer

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    model = SentenceTransformer(EMBEDDING_MODEL, device="cuda")
    texts = [c["text"] for c in chunks]

    t0 = time.perf_counter()
    embeddings = model.encode(texts, device="cuda", batch_size=256, show_progress_bar=False, convert_to_numpy=True)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0
    peak_vram_mb = torch.cuda.max_memory_allocated() / 1e6
    dim = int(embeddings.shape[1])
    del model
    torch.cuda.empty_cache()

    return embeddings, {
        "device": "cuda",
        "note": "offline corpus-build step, GPU used deliberately to save time - NOT the serving latency path",
        "dimension": dim,
        "chunk_count": len(chunks),
        "elapsed_s": round(elapsed, 3),
        "peak_vram_mb": round(peak_vram_mb, 1),
    }


# =============================================================== lancedb


def build_lancedb_indexes(chunks: list[dict], embeddings, spike_dir: Path, rebuild: bool):
    import lancedb
    import pyarrow as pa

    flat_dir = spike_dir / "lancedb_flat"
    quant_dir = spike_dir / "lancedb_quantized"

    table_data = pa.table({
        "chunk_id": [c["chunk_id"] for c in chunks],
        "cik": [c["cik"] for c in chunks],
        "year": [c["year"] for c in chunks],
        "section": [c["section"] for c in chunks],
        "text": [c["text"] for c in chunks],
        "vector": embeddings.tolist(),
    })

    results = {}
    for name, path, quantized in (("flat", flat_dir, False), ("quantized", quant_dir, True)):
        if rebuild and path.exists():
            shutil.rmtree(path)
        if path.exists():
            db = lancedb.connect(str(path))
            table = db.open_table("spike")
            build_time = None
        else:
            db = lancedb.connect(str(path))
            t0 = time.perf_counter()
            table = db.create_table("spike", data=table_data)
            if quantized:
                table.create_index(metric="cosine", **LANCEDB_QUANT)
            build_time = round(time.perf_counter() - t0, 3)
        size_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        results[name] = {
            "table": table,
            "build_time_s": build_time,
            "vector_count": table.count_rows(),
            "dimension": int(embeddings.shape[1]),
            "on_disk_size_mb": round(size_bytes / 1e6, 2),
            "quantized": quantized,
            "path": str(path.relative_to(REPO_ROOT)),
        }
    return results


def verify_index(table, query_vector) -> bool:
    results = table.search(query_vector).limit(5).to_arrow()
    return results.num_rows > 0 and "text" in results.column_names


# ============================================================== queries


def build_query_set() -> list[str]:
    """Deterministic, hand-written SEC-style latency probes. NOT an LLM-generated
    set, NOT the Phase 1/2 evaluation set - see label in default_config()."""
    templates = [
        "What was the company's total revenue?",
        "What are the material risk factors described in the filing?",
        "Describe the company's principal business operations.",
        "What was operating income for the period?",
        "How did net income change compared with the prior fiscal year?",
        "What are the primary risks related to competition?",
        "Summarize the company's research and development expenses.",
        "What legal proceedings is the company involved in?",
        "Describe the company's properties and facilities.",
        "What is the company's dividend policy?",
        "What were total operating expenses?",
        "How does the company describe its market risk exposure?",
        "What is discussed in the management discussion and analysis section?",
        "What risks does the company face from regulatory changes?",
        "Describe the company's employees and human capital resources.",
        "What was gross profit for the period?",
        "What risks are associated with the company's supply chain?",
        "How did cash and cash equivalents change year over year?",
        "What does the company say about cybersecurity risks?",
        "Describe the company's competitive landscape.",
        "What was the increase or decrease in cost of revenue?",
        "What risks are disclosed related to international operations?",
        "Summarize the company's critical accounting policies.",
        "What capital expenditures did the company make?",
        "Describe changes in stockholders' equity during the period.",
        "What risks does the company disclose about intellectual property?",
        "How does the company describe its liquidity and capital resources?",
        "What was research and development expense as a percentage of revenue?",
        "Describe the company's risk factors related to indebtedness.",
        "What does Item 7A disclose about quantitative market risk?",
    ]
    years = [2016, 2017, 2018, 2019, 2020, 2021]
    return [f"{t} (fiscal year {y})" for t in templates for y in years]


# ============================================================= reranker


def resolve_reranker_onnx_path() -> Path:
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(RERANKER_REPO, RERANKER_ONNX_FILE))


def load_reranker():
    import onnxruntime as ort
    from transformers import AutoTokenizer

    onnx_path = resolve_reranker_onnx_path()
    so = ort.SessionOptions()
    so.intra_op_num_threads = CPU_THREADS
    session = ort.InferenceSession(str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"])
    tokenizer = AutoTokenizer.from_pretrained(RERANKER_REPO)
    info = {
        "model": RERANKER_REPO,
        "onnx_file": RERANKER_ONNX_FILE,
        "runtime": "onnxruntime " + ort.__version__,
        "execution_provider": session.get_providers()[0],
        "quantization": "int8",
        "model_file_size_mb": round(onnx_path.stat().st_size / 1e6, 2),
    }
    return session, tokenizer, info


def score_rerank(session, tokenizer, query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    enc = tokenizer([query] * len(passages), passages, padding=True, truncation=True,
                     max_length=512, return_tensors="np")
    inputs = {
        "input_ids": enc["input_ids"].astype("int64"),
        "attention_mask": enc["attention_mask"].astype("int64"),
        "token_type_ids": enc["token_type_ids"].astype("int64"),
    }
    outputs = session.run(["logits"], inputs)
    return outputs[0].reshape(-1).tolist()


# =============================================================== warm bench


def run_single_query(query, embed_model_cpu, table_flat, table_quant, reranker_session, reranker_tokenizer, top_k):
    t0 = time.perf_counter()
    qvec = embed_model_cpu.encode([query], device="cpu", convert_to_numpy=True)[0]
    t1 = time.perf_counter()
    results_flat = table_flat.search(qvec).limit(top_k).to_arrow()
    t2 = time.perf_counter()
    passages = results_flat.column("text").to_pylist()
    _ = score_rerank(reranker_session, reranker_tokenizer, query, passages)
    t3 = time.perf_counter()
    results_quant = table_quant.search(qvec).limit(top_k).to_arrow()
    t4 = time.perf_counter()
    assert results_quant.num_rows >= 0

    return {
        "embedding_ms": (t1 - t0) * 1000,
        "retrieval_flat_ms": (t2 - t1) * 1000,
        "rerank_ms": (t3 - t2) * 1000,
        "retrieval_quantized_ms": (t4 - t3) * 1000,
        "vector_only_flat_total_ms": (t2 - t0) * 1000,
        "vector_rerank_total_ms": (t3 - t0) * 1000,
        "vector_only_quantized_total_ms": (t1 - t0) * 1000 + (t4 - t3) * 1000,
    }


def benchmark_warm(queries, embed_model_cpu, table_flat, table_quant, reranker_session, reranker_tokenizer, top_k):
    warm_queries = queries[:WARMUP_QUERIES]
    measured_queries = queries[WARMUP_QUERIES:]

    for q in warm_queries:
        run_single_query(q, embed_model_cpu, table_flat, table_quant, reranker_session, reranker_tokenizer, top_k)

    samples = []
    peak_rss = rss_mb()
    for i, q in enumerate(measured_queries):
        samples.append(run_single_query(q, embed_model_cpu, table_flat, table_quant,
                                          reranker_session, reranker_tokenizer, top_k))
        if i % 20 == 0:
            peak_rss = max(peak_rss, rss_mb())
    peak_rss = max(peak_rss, rss_mb())
    return samples, peak_rss


# =============================================================== cold proxy


def cold_run_once(index_dir: Path) -> None:
    """Invoked as a fresh subprocess by run_cold_benchmark(). Prints one line
    to stdout; everything else is process start + imports + model init +
    LanceDB open + one query, all included in the timed interval."""
    t_start = time.perf_counter()
    import lancedb
    import onnxruntime as ort
    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer

    embed_model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    db = lancedb.connect(str(index_dir / "lancedb_flat"))
    table = db.open_table("spike")
    onnx_path = resolve_reranker_onnx_path()
    so = ort.SessionOptions()
    so.intra_op_num_threads = CPU_THREADS
    session = ort.InferenceSession(str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"])
    tokenizer = AutoTokenizer.from_pretrained(RERANKER_REPO)

    query = "What was the company's total revenue? (fiscal year 2020)"
    qvec = embed_model.encode([query], device="cpu", convert_to_numpy=True)[0]
    results = table.search(qvec).limit(TOP_K).to_arrow()
    passages = results.column("text").to_pylist()
    score_rerank(session, tokenizer, query, passages)

    elapsed_ms = (time.perf_counter() - t_start) * 1000
    print(f"COLD_ELAPSED_MS={elapsed_ms:.2f}")


def run_cold_benchmark(spike_dir: Path, n_samples: int) -> list[float]:
    samples = []
    for i in range(n_samples):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--cold-run", "--index-dir", str(spike_dir)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
        )
        line = next((l for l in result.stdout.splitlines() if l.startswith("COLD_ELAPSED_MS=")), None)
        if line is None:
            log.warning("cold sample %d produced no timing line (stderr: %s)", i, result.stderr[-500:])
            continue
        samples.append(float(line.split("=")[1]))
        log_event(log, logging.INFO, "cold_sample_completed", sample=i, elapsed_ms=round(samples[-1], 1))
    return samples


# ============================================================= memory footprint


def measure_memory_stages(spike_dir: Path) -> dict:
    """Fresh, single-purpose measurement pass (separate from the warm-benchmark
    process) so each stage's RSS reflects only what's been loaded so far."""
    stages = {}
    stages["baseline"] = rss_mb()

    import lancedb  # noqa: F401
    import onnxruntime  # noqa: F401
    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer
    stages["after_imports"] = rss_mb()

    db = lancedb.connect(str(spike_dir / "lancedb_flat"))
    table = db.open_table("spike")
    stages["after_lancedb_open"] = rss_mb()

    embed_model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    stages["after_embedding_model_load"] = rss_mb()

    onnx_path = resolve_reranker_onnx_path()
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = CPU_THREADS
    session = ort.InferenceSession(str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"])
    tokenizer = AutoTokenizer.from_pretrained(RERANKER_REPO)
    stages["after_reranker_load"] = rss_mb()

    query = "What was the company's total revenue? (fiscal year 2020)"
    qvec = embed_model.encode([query], device="cpu", convert_to_numpy=True)[0]
    results = table.search(qvec).limit(TOP_K).to_arrow()
    passages = results.column("text").to_pylist()
    score_rerank(session, tokenizer, query, passages)
    stages["after_one_query"] = rss_mb()

    return {k: round(v, 1) for k, v in stages.items()}


# =============================================================== decision


def apply_decision(warm_p95_ms: float, cold_p95_s: float) -> dict:
    """Frozen thresholds from PROJECT_EXECUTION.md ### 0.10, applied without
    modification after seeing the results."""
    if warm_p95_ms < 500:
        warm_action = "Proceed with the serverless design"
    elif warm_p95_ms <= 2000:
        warm_action = "Proceed, but constrain reranker size and candidate pool in Phase 3"
    else:
        warm_action = "Change serving target to warm compute; revisit Phase 3 assumptions"

    cold_flag = cold_p95_s > 10
    if cold_flag:
        decision = "Fargate / continuously warm service preferred (cold-start proxy exceeds 10s)"
    elif warm_p95_ms > 2000:
        decision = "Fargate / continuously warm service preferred (warm p95 exceeds 2s)"
    elif warm_p95_ms > 500:
        decision = "Lambda conditionally preferred - feasible only with Phase 3 optimization; Fargate is the safer default"
    else:
        decision = "Lambda remains the preferred Phase 4 target"

    return {
        "warm_p95_ms": round(warm_p95_ms, 1),
        "warm_action_per_threshold_table": warm_action,
        "cold_p95_s": round(cold_p95_s, 2),
        "cold_exceeds_10s": cold_flag,
        "serving_target_decision": decision,
    }


# =================================================================== main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-chunks", type=int, default=TARGET_CHUNKS_DEFAULT)
    parser.add_argument("--rebuild", action="store_true", help="rebuild corpus/embeddings/index even if a matching spike_config_hash artifact exists")
    parser.add_argument("--cold-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--index-dir", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.cold_run:
        cold_run_once(args.index_dir)
        return 0

    configure_logging()
    import torch
    torch.set_num_threads(CPU_THREADS)

    t_task_start = time.perf_counter()
    storage = get_storage()
    config = default_config(args.target_chunks)
    cfg_hash = spike_config_hash(config)
    spike_dir = storage.artifacts_root / "serving_spike" / cfg_hash
    storage.ensure_dir(spike_dir)

    log_event(log, logging.INFO, "spike_started", spike_config_hash=cfg_hash, target_chunks=args.target_chunks)

    # --- hardware/software context ---
    import sentence_transformers
    import lancedb as _lancedb
    context = {
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_model": platform.processor(),
        "logical_cpu_count": __import__("os").cpu_count(),
        "torch_version": torch.__version__,
        "torch_version_cuda": torch.version.cuda,
        "gpu_model": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "lancedb_version": _lancedb.__version__,
        "sentence_transformers_version": sentence_transformers.__version__,
    }
    try:
        import psutil
        vm = psutil.virtual_memory()
        context["system_ram_gb"] = round(vm.total / 1e9, 1)
        context["gpu_vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2) if torch.cuda.is_available() else None
    except Exception:  # noqa: BLE001
        pass

    # --- corpus + chunking (reuse if config hash matches and not --rebuild) ---
    chunks_path = spike_dir / "chunks_meta.json"
    if chunks_path.is_file() and not args.rebuild:
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        log.info("reusing existing chunk metadata (%d chunks) for config %s", len(chunks), cfg_hash)
    else:
        t0 = time.perf_counter()
        chunks = select_and_chunk_corpus(args.target_chunks)
        corpus_time = time.perf_counter() - t0
        chunks_path.write_text(json.dumps(chunks), encoding="utf-8")
        log_event(log, logging.INFO, "chunks_created", count=len(chunks), elapsed_s=round(corpus_time, 1))

    token_counts = [c["token_count"] for c in chunks]
    corpus_stats = {
        "chunk_count": len(chunks),
        "unique_filings": len(set(c["filename"] for c in chunks)),
        "mean_token_count": round(statistics.fmean(token_counts), 1),
        "p50_token_count": statistics.median(token_counts),
        "p95_token_count": sorted(token_counts)[int(len(token_counts) * 0.95)],
    }

    # --- embeddings (reuse if present) ---
    emb_path = spike_dir / "embeddings.npy"
    import numpy as np
    if emb_path.is_file() and not args.rebuild:
        embeddings = np.load(emb_path)
        embedding_info = {"reused_from": str(emb_path.relative_to(REPO_ROOT)), "dimension": int(embeddings.shape[1]), "chunk_count": int(embeddings.shape[0])}
        log.info("reusing existing embeddings %s", embeddings.shape)
    else:
        embeddings, embedding_info = build_corpus_embeddings(chunks)
        np.save(emb_path, embeddings)
        log_event(log, logging.INFO, "embeddings_completed", chunk_count=embedding_info["chunk_count"],
                   dimension=embedding_info["dimension"], elapsed_s=embedding_info["elapsed_s"])

    # --- lancedb indexes ---
    indexes = build_lancedb_indexes(chunks, embeddings, spike_dir, args.rebuild)
    log_event(log, logging.INFO, "index_ready", flat_size_mb=indexes["flat"]["on_disk_size_mb"],
              quantized_size_mb=indexes["quantized"]["on_disk_size_mb"])

    ok_flat = verify_index(indexes["flat"]["table"], embeddings[0])
    ok_quant = verify_index(indexes["quantized"]["table"], embeddings[0])
    if not (ok_flat and ok_quant):
        raise SystemExit("index sanity check failed - aborting before benchmarking")

    # --- reranker ---
    reranker_session, reranker_tokenizer, reranker_info = load_reranker()

    # --- queries ---
    queries = build_query_set()

    # --- warm benchmark (CPU serving path) ---
    from sentence_transformers import SentenceTransformer
    embed_model_cpu = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    warm_samples, peak_rss_warm = benchmark_warm(
        queries, embed_model_cpu, indexes["flat"]["table"], indexes["quantized"]["table"],
        reranker_session, reranker_tokenizer, TOP_K,
    )
    log_event(log, logging.INFO, "warm_benchmark_completed", measured=len(warm_samples))

    # reproducibility check - second warm pass
    warm_samples_2, _ = benchmark_warm(
        queries, embed_model_cpu, indexes["flat"]["table"], indexes["quantized"]["table"],
        reranker_session, reranker_tokenizer, TOP_K,
    )

    # --- cold proxy benchmark ---
    cold_samples = run_cold_benchmark(spike_dir, COLD_SAMPLES)
    log_event(log, logging.INFO, "cold_benchmark_completed", samples=len(cold_samples))

    # --- memory stages (separate fresh pass) ---
    memory_stages = measure_memory_stages(spike_dir)

    # --- aggregate stats ---
    def col(samples, key):
        return [s[key] for s in samples]

    component_stats = {
        "embedding_ms": percentile_stats(col(warm_samples, "embedding_ms")),
        "retrieval_flat_ms": percentile_stats(col(warm_samples, "retrieval_flat_ms")),
        "retrieval_quantized_ms": percentile_stats(col(warm_samples, "retrieval_quantized_ms")),
        "rerank_ms": percentile_stats(col(warm_samples, "rerank_ms")),
    }
    path_stats = {
        "vector_only_flat": percentile_stats(col(warm_samples, "vector_only_flat_total_ms")),
        "vector_only_quantized": percentile_stats(col(warm_samples, "vector_only_quantized_total_ms")),
        "vector_plus_rerank": percentile_stats(col(warm_samples, "vector_rerank_total_ms")),
    }
    path_stats_run2 = {
        "vector_only_flat": percentile_stats(col(warm_samples_2, "vector_only_flat_total_ms")),
        "vector_plus_rerank": percentile_stats(col(warm_samples_2, "vector_rerank_total_ms")),
    }
    cold_stats_ms = percentile_stats(cold_samples)
    cold_stats_s = {k: (v / 1000 if isinstance(v, (int, float)) else v) for k, v in cold_stats_ms.items()}

    decision = apply_decision(
        warm_p95_ms=path_stats["vector_plus_rerank"]["p95"],
        cold_p95_s=cold_stats_s["p95"] if cold_stats_s.get("p95") is not None else float("inf"),
    )

    artifact_sizes = {
        "lancedb_flat_mb": indexes["flat"]["on_disk_size_mb"],
        "lancedb_quantized_mb": indexes["quantized"]["on_disk_size_mb"],
        "reranker_onnx_mb": reranker_info["model_file_size_mb"],
        "note_venv_size": "DEVELOPMENT ENVIRONMENT SIZE - NOT DEPLOYMENT PACKAGE SIZE - not measured here, .venv includes GPU-specific packages not representative of a CPU deployment package",
    }

    limitations = [
        f"{len(chunks)} chunks - a representative subset, not the full ~14M-chunk projected production corpus",
        "local process-cold proxy, NOT a real AWS Lambda cold start (no container init, no cold ENI/VPC attach, "
        "no Lambda runtime bootstrap; OS filesystem page cache may also remain warm across subprocesses on this machine)",
        "no generation/LLM latency included - retrieval/reranking serving path only",
        "no relevance-quality evaluation performed or claimed - Phase 2 establishes trustworthy measurement, Phase 3 does scientific ablations",
        "provisional components (bge-small, MiniLM, 512-token/no-overlap chunking, top-50) - not final Phase 3 selections",
        "cloud memory-tier scaling (e.g. distinct Lambda 1GB/2GB/4GB allocations) was NOT reproduced - Docker Desktop "
        "is installed on this machine but its daemon was not running, and starting it was out of scope for this benchmark; "
        "only single-configuration process RSS was measured",
        "single development machine, single measurement session - laptop thermal/background-load variance is possible",
    ]

    result = {
        "spike_config_hash": cfg_hash,
        "timestamp_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "config": config,
        "environment": context,
        "corpus": corpus_stats,
        "embedding_build": embedding_info,
        "lancedb": {
            "flat": {k: v for k, v in indexes["flat"].items() if k != "table"},
            "quantized": {k: v for k, v in indexes["quantized"].items() if k != "table"},
        },
        "reranker": reranker_info,
        "component_timing_ms": component_stats,
        "path_timing_ms": path_stats,
        "path_timing_ms_reproducibility_run2": path_stats_run2,
        "cold_process_proxy": {
            "raw_samples_ms": [round(s, 1) for s in cold_samples],
            "stats_ms": cold_stats_ms,
            "stats_s": cold_stats_s,
            "label": "local process-cold proxy - NOT real Lambda cold-start measurement",
        },
        "memory_rss_mb": {**memory_stages, "peak_during_warm_benchmark": round(peak_rss_warm, 1)},
        "artifact_sizes_mb": artifact_sizes,
        "decision_thresholds": {
            "warm_p95_lt_500ms": "Proceed with the serverless design",
            "warm_p95_500ms_to_2s": "Proceed, but constrain reranker size and candidate pool in Phase 3",
            "warm_p95_gt_2s": "Change serving target to warm compute; revisit Phase 3 assumptions",
            "cold_proxy_gt_10s": "Serverless target unsuitable regardless of warm performance",
        },
        "decision": decision,
        "limitations": limitations,
        "phase3_recheck_required": True,
        "total_task_elapsed_s": round(time.perf_counter() - t_task_start, 1),
    }

    results_path = REPO_ROOT / "results" / "phase_0_10_serving_spike.json"
    results_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    csv_path = REPO_ROOT / "results" / "phase_0_10_serving_spike.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("query_index,embedding_ms,retrieval_flat_ms,retrieval_quantized_ms,rerank_ms,vector_only_total_ms,vector_rerank_total_ms\n")
        for i, s in enumerate(warm_samples):
            f.write(f"{i},{s['embedding_ms']:.2f},{s['retrieval_flat_ms']:.2f},{s['retrieval_quantized_ms']:.2f},"
                     f"{s['rerank_ms']:.2f},{s['vector_only_flat_total_ms']:.2f},{s['vector_rerank_total_ms']:.2f}\n")

    print(json.dumps(decision, indent=2))
    print(f"\nResults written: {results_path.relative_to(REPO_ROOT)}")
    print(f"Per-query CSV:   {csv_path.relative_to(REPO_ROOT)}")
    print(f"spike_config_hash: {cfg_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
