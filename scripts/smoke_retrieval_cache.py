"""Local exact-retrieval-cache smoke benchmark.

No generation provider, paid API, AWS access, or protected TEST data is
used. This measures the current live local dense retriever directly.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.dependencies import (
    DEV_CHUNK_CONFIG_HASH,
    DEV_EMBEDDING_MODEL_REPO,
    build_live_dense_retrieval_cache_identity,
)
from src.config import get_settings, resolve_device
from src.embeddings.bge import load_model
from src.index.lancedb_index import open_chunk_table, open_database
from src.retrieval.baseline import BaselineRetriever
from src.retrieval.cache import CachedRetriever, ExactRetrievalCache
from src.storage import get_storage

QUERIES = (
    "What was the company's total revenue?",
    "What risks did the company discuss in its annual filing?",
)

OUTPUT_PATH = Path("results") / "phase_4_13_retrieval_cache_smoke.json"


def _contract(results) -> list[dict]:
    return [asdict(result) for result in results]


def _compare_contracts(left: list[dict], right: list[dict]) -> bool:
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if a.keys() != b.keys():
            return False
        for key in a:
            if isinstance(a[key], float):
                if abs(a[key] - b[key]) > 1e-9:
                    return False
            elif a[key] != b[key]:
                return False
    return True


def _time_retrieve(retriever, query: str):
    start = time.perf_counter()
    results = retriever.retrieve(query, k=5)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return results, elapsed_ms


def main() -> int:
    settings = get_settings()
    storage = get_storage()
    db_path = storage.index_dir(DEV_CHUNK_CONFIG_HASH, DEV_EMBEDDING_MODEL_REPO)
    if not db_path.is_dir():
        raise RuntimeError(f"local dev LanceDB index not found at {db_path}")

    db = open_database(db_path)
    table = open_chunk_table(db)
    model = load_model(device=resolve_device(settings.device))
    base = BaselineRetriever(model=model, table=table)
    row_count = table.count_rows()
    cache = ExactRetrievalCache(
        max_entries=settings.retrieval_cache_max_entries,
        ttl_seconds=settings.retrieval_cache_ttl_seconds,
    )
    cached = CachedRetriever(
        base,
        cache=cache,
        static_identity=build_live_dense_retrieval_cache_identity(settings, dense_row_count=row_count),
    )

    measurements = []
    all_equal = True
    for query in QUERIES:
        disabled_results, disabled_ms = _time_retrieve(base, query)
        cold_results, cold_ms = _time_retrieve(cached, query)
        warm_results, warm_ms = _time_retrieve(cached, query)
        disabled_contract = _contract(disabled_results)
        cold_contract = _contract(cold_results)
        warm_contract = _contract(warm_results)
        equivalent = (
            _compare_contracts(disabled_contract, cold_contract)
            and _compare_contracts(disabled_contract, warm_contract)
        )
        all_equal = all_equal and equivalent
        speedup = cold_ms / warm_ms if warm_ms > 0 else None
        measurements.append({
            "query_label": f"hand_written_{len(measurements) + 1}",
            "disabled_retrieval_ms": round(disabled_ms, 3),
            "cold_cache_miss_ms": round(cold_ms, 3),
            "warm_cache_hit_ms": round(warm_ms, 3),
            "cold_to_warm_speedup": round(speedup, 3) if speedup is not None else None,
            "result_count": len(warm_results),
            "retrieval_contract_equal": equivalent,
        })

    payload = {
        "task": "phase_4_13_exact_retrieval_cache",
        "protected_test_usage": "0/3",
        "paid_generation_api_calls": 0,
        "aws_access": 0,
        "queries": "hand-written non-protected smoke queries",
        "dense_index_row_count": row_count,
        "cache_backend": "memory_lru_ttl",
        "cache_stats": cache.stats(),
        "retrieval_contract_equal": all_equal,
        "measurements": measurements,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if all_equal else 1


if __name__ == "__main__":
    raise SystemExit(main())
