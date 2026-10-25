import threading
from collections import Counter

import pytest

from src.retrieval.cache import (
    CachedRetriever,
    ExactRetrievalCache,
    build_retrieval_cache_key,
    canonicalize_query_for_cache,
)


def _identity(name="dev-index"):
    return {
        "cache_schema_version": "v1",
        "route": "dense",
        "retriever_kind": "baseline_dev_exact_cosine",
        "embedding_model_identity": "BAAI/bge-small-en-v1.5",
        "embedding_model_revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        "embedding_dimension": 384,
        "chunk_config_hash": "chunk-hash",
        "dense_index_table": "chunks",
        "dense_index_schema": "phase1_dev_17_column_chunk_id",
        "dense_index_artifact_identity": name,
        "dense_index_row_count": 162357,
        "retrieval_algorithm": "exact_flat",
        "similarity_metric": "cosine",
        "crag_threshold": None,
    }


class FakeRetriever:
    def __init__(self, *, results_factory=None, fail=False):
        self.calls = []
        self._results_factory = results_factory or (
            lambda question, k, filters: [
                {"rank": 1, "chunk_id": f"{question}-{k}-{filters}", "score": 0.9}
            ]
        )
        self._fail = fail

    def retrieve(self, question, k=5, **filters):
        self.calls.append((question, k, dict(filters)))
        if self._fail:
            raise RuntimeError("boom")
        return self._results_factory(question, k, filters)


def _cached(fake=None, *, cache=None, identity=None):
    cache = cache or ExactRetrievalCache(max_entries=8, ttl_seconds=60)
    return CachedRetriever(fake or FakeRetriever(), cache=cache, static_identity=identity or _identity())


def test_basic_hit_miss_reuses_identical_result():
    fake = FakeRetriever()
    retriever = _cached(fake)

    first = retriever.retrieve("What was revenue?", k=5)
    second = retriever.retrieve("What was revenue?", k=5)

    assert first == second
    assert len(fake.calls) == 1
    stats = retriever.cache.stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 1
    assert stats["stores"] == 1


def test_canonical_whitespace_hits_same_entry():
    fake = FakeRetriever()
    retriever = _cached(fake)

    retriever.retrieve("  What   was Apple's revenue in 2020?  ", k=5)
    retriever.retrieve("What was Apple's revenue in 2020?", k=5)

    assert len(fake.calls) == 1
    assert retriever.cache.stats()["hits"] == 1


def test_canonicalization_preserves_case_punctuation_and_years():
    assert canonicalize_query_for_cache(" Apple revenue, 2020? ") == "Apple revenue, 2020?"
    assert canonicalize_query_for_cache("Apple revenue, 2021?") != "Apple revenue, 2020?"
    assert canonicalize_query_for_cache("apple revenue, 2020?") != "Apple revenue, 2020?"


def test_retrieval_k_isolated():
    fake = FakeRetriever()
    retriever = _cached(fake)

    retriever.retrieve("What was revenue?", k=5)
    retriever.retrieve("What was revenue?", k=10)

    assert len(fake.calls) == 2
    assert Counter(call[1] for call in fake.calls) == Counter({5: 1, 10: 1})


def test_metadata_filters_are_isolated():
    fake = FakeRetriever()
    retriever = _cached(fake)

    retriever.retrieve("What was revenue?", k=5, cik=1000, fiscal_year=2020)
    retriever.retrieve("What was revenue?", k=5, cik=2000, fiscal_year=2020)

    assert len(fake.calls) == 2
    assert fake.calls[0][2]["cik"] == 1000
    assert fake.calls[1][2]["cik"] == 2000


def test_artifact_identity_isolated_even_with_shared_cache():
    cache = ExactRetrievalCache(max_entries=8, ttl_seconds=60)
    fake_a = FakeRetriever()
    fake_b = FakeRetriever()
    retriever_a = _cached(fake_a, cache=cache, identity=_identity("dev-index"))
    retriever_b = _cached(fake_b, cache=cache, identity=_identity("prod-index"))

    retriever_a.retrieve("What was revenue?", k=5)
    retriever_b.retrieve("What was revenue?", k=5)

    assert len(fake_a.calls) == 1
    assert len(fake_b.calls) == 1
    assert cache.stats()["misses"] == 2


def test_cache_key_is_hash_not_raw_query():
    key = build_retrieval_cache_key(
        static_identity=_identity(),
        canonical_query="My private exact query",
        k=5,
        metadata_filters={},
    )
    assert len(key) == 64
    assert "My private exact query" not in key


def test_ttl_expiration_uses_injected_clock():
    now = [100.0]
    cache = ExactRetrievalCache(max_entries=8, ttl_seconds=10, clock=lambda: now[0])
    fake = FakeRetriever()
    retriever = _cached(fake, cache=cache)

    retriever.retrieve("What was revenue?", k=5)
    now[0] = 111.0
    retriever.retrieve("What was revenue?", k=5)

    assert len(fake.calls) == 2
    stats = cache.stats()
    assert stats["expirations"] == 1
    assert stats["misses"] == 2


def test_lru_eviction_discards_oldest_and_preserves_recently_used():
    cache = ExactRetrievalCache(max_entries=2, ttl_seconds=60)
    fake = FakeRetriever()
    retriever = _cached(fake, cache=cache)

    retriever.retrieve("q1", k=5)
    retriever.retrieve("q2", k=5)
    retriever.retrieve("q1", k=5)
    retriever.retrieve("q3", k=5)

    assert cache.stats()["evictions"] == 1
    retriever.retrieve("q1", k=5)
    retriever.retrieve("q2", k=5)

    assert Counter(call[0] for call in fake.calls) == Counter({"q1": 1, "q2": 2, "q3": 1})
    assert cache.stats()["evictions"] == 2


def test_disabled_cache_always_delegates():
    cache = ExactRetrievalCache(enabled=False, max_entries=8, ttl_seconds=60)
    fake = FakeRetriever()
    retriever = _cached(fake, cache=cache)

    first = retriever.retrieve("What was revenue?", k=5)
    second = retriever.retrieve("What was revenue?", k=5)

    assert first == second
    assert len(fake.calls) == 2
    assert cache.stats()["bypasses"] == 2
    assert cache.stats()["entries"] == 0


def test_underlying_exception_is_not_cached():
    cache = ExactRetrievalCache(max_entries=8, ttl_seconds=60)
    fake = FakeRetriever(fail=True)
    retriever = _cached(fake, cache=cache)

    for _ in range(2):
        with pytest.raises(RuntimeError):
            retriever.retrieve("What was revenue?", k=5)

    assert len(fake.calls) == 2
    assert cache.stats()["stores"] == 0
    assert cache.stats()["entries"] == 0


def test_empty_valid_result_is_cached():
    fake = FakeRetriever(results_factory=lambda question, k, filters: [])
    retriever = _cached(fake)

    assert retriever.retrieve("No matching evidence?", k=5) == []
    assert retriever.retrieve("No matching evidence?", k=5) == []

    assert len(fake.calls) == 1
    assert retriever.cache.stats()["hits"] == 1


def test_returned_result_mutation_does_not_corrupt_cache():
    fake = FakeRetriever(results_factory=lambda question, k, filters: [{"chunk_id": "c1", "meta": {"rank": 1}}])
    retriever = _cached(fake)

    first = retriever.retrieve("What was revenue?", k=5)
    first[0]["meta"]["rank"] = 99
    second = retriever.retrieve("What was revenue?", k=5)

    assert second[0]["meta"]["rank"] == 1


def test_cache_clear_can_reset_entries_and_stats():
    retriever = _cached()
    retriever.retrieve("q1", k=5)
    retriever.retrieve("q1", k=5)

    retriever.cache.clear(reset_stats=True)

    assert retriever.cache.stats()["entries"] == 0
    assert retriever.cache.stats()["hits"] == 0
    assert retriever.cache.stats()["misses"] == 0


def test_thread_safety_for_parallel_access():
    cache = ExactRetrievalCache(max_entries=16, ttl_seconds=60)
    fake = FakeRetriever()
    retriever = _cached(fake, cache=cache)
    errors = []

    def worker(i):
        try:
            retriever.retrieve(f"question {i % 5}", k=5)
        except Exception as exc:  # pragma: no cover - assertion below reports it
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert cache.stats()["entries"] <= 5
