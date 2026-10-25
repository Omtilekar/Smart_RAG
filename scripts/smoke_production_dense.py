"""Task 4.A real local smoke: live Qwen3 encoder + the frozen 10,487,096-row
production LanceDB artifact. Retriever-first (no generation, no network);
then one /query + /status round trip through the real FastAPI app with a
deterministic FAKE provider. Never touches protected TEST, OpenRouter or AWS.

Writes results/phase_4a_production_dense_smoke.json.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "results" / "phase_4a_production_dense_smoke.json"

# Hand-written, non-protected probes (no TEST questions).
UNSCOPED = [
    "What risks do technology research companies describe in their annual reports?",
    "How do companies describe competition in their business sections?",
]
SCOPED = {"cik": 1000015, "fiscal_year": 1996}   # first document in the artifact
SCOPED_QUESTION = "What does the company say about its subscribers and products?"


def _rss_mb() -> float | None:
    try:
        import psutil
        return round(psutil.Process(os.getpid()).memory_info().rss / 1e6, 1)
    except Exception:  # noqa: BLE001
        return None


def _gpu_mb() -> float | None:
    try:
        import torch
        return round(torch.cuda.memory_allocated() / 1e6, 1) if torch.cuda.is_available() else None
    except Exception:  # noqa: BLE001
        return None


def _summ(results):
    return [{"rank": r.rank, "chunk_id": r.chunk_id, "chunk_uid": r.chunk_uid[:12], "cik": r.cik,
             "fiscal_year": r.fiscal_year, "distance": round(r.distance, 5), "score": round(r.score, 5)}
            for r in results]


def _timed(retriever, question, **filters):
    t0 = time.perf_counter()
    results = retriever.retrieve(question, k=5, **filters)
    return round((time.perf_counter() - t0) * 1000, 1), results


def main() -> None:
    from src.config import get_settings, resolve_device
    from src.embeddings.model_registry import QWEN3_EMBEDDING, encode_queries, load_model
    from src.index.lancedb_index_full import open_chunk_table, open_database
    from src.retrieval.production import (
        ProductionDenseRetriever, load_production_contract, smoke_lookup, validate_production_table,
    )
    from src.storage import get_storage

    settings = get_settings()
    report: dict = {"created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "safety": {"openrouter_calls": 0, "aws_access": 0, "protected_test_opened": False}}
    report["rss_mb_before"] = _rss_mb()

    contract = load_production_contract()
    db_path = get_storage().index_dir_full(
        contract.phase_4_1_config_hash, contract.chunk_config_hash,
        contract.embedding_model, contract.embedding_model_revision)

    t0 = time.perf_counter()
    table = open_chunk_table(open_database(db_path))
    report["index_open_s"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    validate_production_table(table, contract)
    report["table_validation_s"] = round(time.perf_counter() - t0, 3)
    t0 = time.perf_counter()
    report["startup_smoke_lookup"] = smoke_lookup(table)
    report["startup_smoke_lookup_s"] = round(time.perf_counter() - t0, 3)
    report["row_count"] = table.count_rows()

    device = resolve_device(settings.device)
    t0 = time.perf_counter()
    model = load_model(QWEN3_EMBEDDING, device=device)
    report["model_load_s"] = round(time.perf_counter() - t0, 2)
    report["device"] = device

    query_vec = encode_queries(QWEN3_EMBEDDING, model, [UNSCOPED[0]], batch_size=1)[0]
    report["query_vector"] = {"dimension": int(len(query_vec)), "dtype": str(query_vec.dtype),
                              "l2_norm": round(float((query_vec ** 2).sum() ** 0.5), 6)}
    t0 = time.perf_counter()
    encode_queries(QWEN3_EMBEDDING, model, [UNSCOPED[1]], batch_size=1)
    report["query_embedding_warm_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    retriever = ProductionDenseRetriever(QWEN3_EMBEDDING, model, table)
    probes = {}
    # company + year scoped (BTree pre-filter) - first call is "first query", repeat is warm.
    first_ms, scoped = _timed(retriever, SCOPED_QUESTION, **SCOPED)
    warm_ms, scoped_again = _timed(retriever, SCOPED_QUESTION, **SCOPED)
    probes["company_year_scoped"] = {"filters": SCOPED, "first_ms": first_ms, "warm_ms": warm_ms,
                                     "deterministic": _summ(scoped) == _summ(scoped_again), "results": _summ(scoped)}
    cik_ms, cik_only = _timed(retriever, SCOPED_QUESTION, cik=SCOPED["cik"])
    probes["company_scoped"] = {"filters": {"cik": SCOPED["cik"]}, "ms": cik_ms, "results": _summ(cik_only)}
    for i, question in enumerate(UNSCOPED):
        ms, results = _timed(retriever, question)
        probes[f"unscoped_{i}"] = {"question": question, "ms": ms, "result_count": len(results),
                                   "results": _summ(results)}
    report["probes"] = probes
    report["rss_mb_after"] = _rss_mb()
    report["gpu_allocated_mb_after"] = _gpu_mb()

    # ---- real FastAPI app, real production deps, FAKE provider ----
    import src.api.dependencies as deps_module
    from fastapi.testclient import TestClient
    from src.api.app import create_app
    from src.generation.provider import ProviderResponse

    class _FakeProvider:
        def generate(self, request):
            return ProviderResponse(
                text="Deterministic fake answer for the Task 4.A smoke.", requested_model="fake/model",
                response_model="fake/model", provider_name="fake", response_provider=None, prompt_tokens=1,
                completion_tokens=1, total_tokens=2, temperature_requested=request.temperature, latency_ms=0.1)

    deps_module.get_generation_provider = lambda settings: _FakeProvider()
    del model, retriever, table  # the app below builds its own single production stack
    t0 = time.perf_counter()
    deps = deps_module.build_production_dependencies(settings)
    report["app_startup_s"] = round(time.perf_counter() - t0, 2)
    with TestClient(create_app(dependencies=deps)) as client:
        status = client.get("/status").json()
        t0 = time.perf_counter()
        resp = client.post("/query", json={"question": UNSCOPED[0]})
        report["api_query_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        report["api_status_config"] = status["config"]
        report["api_query"] = {"http": resp.status_code, "status": resp.json().get("status"),
                               "route": resp.json().get("route")}
        report["api_cache_after_query"] = client.get("/status").json().get("retrieval_cache")
    report["rss_mb_after_app"] = _rss_mb()

    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "index_open_s", "table_validation_s", "startup_smoke_lookup_s", "model_load_s", "app_startup_s",
        "query_embedding_warm_ms", "api_query_ms", "rss_mb_after_app", "gpu_allocated_mb_after")}, indent=2))
    for name, probe in probes.items():
        print(name, {k: v for k, v in probe.items() if k in ("first_ms", "warm_ms", "ms")})


if __name__ == "__main__":
    main()
