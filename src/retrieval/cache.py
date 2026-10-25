"""Exact dense-retrieval cache for the serving path.

This module deliberately caches only retriever output, never generated
answers, prompts, provider responses, guard decisions, or embeddings. The
cache key is a SHA-256 digest over a deterministic JSON identity that
includes the canonical query, retrieval parameters, and artifact/config
identity. Raw query text is never stored as the cache key or exposed in
statistics.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Mapping


JSON_PRIMITIVE = str | int | float | bool | None
JSON_VALUE = JSON_PRIMITIVE | list["JSON_VALUE"] | dict[str, "JSON_VALUE"]

BACKEND_NAME = "memory_lru_ttl"


@dataclass(frozen=True)
class _CacheEntry:
    expires_at: float
    value: tuple[Any, ...]


@dataclass
class _Counters:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    stores: int = 0
    bypasses: int = 0


def canonicalize_query_for_cache(question: str) -> str:
    """Normalize only formatting differences that should not change
    retrieval intent: Unicode NFC, trim, and collapse whitespace runs.
    Case, punctuation, years, company names, and metric names are kept
    byte-for-byte after that harmless formatting pass."""
    if not isinstance(question, str):
        raise TypeError(f"question must be a str, got {type(question).__name__}")
    normalized = unicodedata.normalize("NFC", question)
    return " ".join(normalized.strip().split())


def _jsonable(value: Any) -> JSON_VALUE:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        result: dict[str, JSON_VALUE] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"cache identity mapping keys must be str, got {type(key).__name__}")
            result[key] = _jsonable(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    raise TypeError(f"cache identity value is not JSON-serializable: {type(value).__name__}")


def _canonical_json(payload: Mapping[str, Any]) -> str:
    jsonable = _jsonable(payload)
    return json.dumps(jsonable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_retrieval_cache_key(*, static_identity: Mapping[str, Any], canonical_query: str,
                              k: int, metadata_filters: Mapping[str, Any] | None = None) -> str:
    """Return the storage key digest for one exact retrieval request.

    `static_identity` must name the retriever/index/model/config identity.
    Per-call values (`canonical_query`, `k`, filters) are layered on top
    here so future dev-index -> production-index migrations naturally
    produce unrelated keys.
    """
    payload = dict(static_identity)
    payload.update({
        "canonical_query": canonical_query,
        "top_k": k,
        "metadata_filters": _jsonable(metadata_filters or {}),
    })
    encoded = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ExactRetrievalCache:
    """Bounded, process-local LRU cache with TTL expiration.

    Thread safety covers all internal state. It is intentionally not a
    cross-process cache; each Python worker owns an independent instance.
    """

    def __init__(self, *, enabled: bool = True, max_entries: int = 512,
                 ttl_seconds: int = 900, clock=time.monotonic):
        if max_entries <= 0:
            raise ValueError(f"max_entries must be positive, got {max_entries}")
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds}")
        self.enabled = bool(enabled)
        self.max_entries = int(max_entries)
        self.ttl_seconds = int(ttl_seconds)
        self._clock = clock
        self._lock = threading.RLock()
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._counters = _Counters()

    def get(self, key: str) -> tuple[bool, list[Any]]:
        if not self.enabled:
            with self._lock:
                self._counters.bypasses += 1
            return False, []

        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._counters.misses += 1
                return False, []
            if entry.expires_at <= now:
                del self._entries[key]
                self._counters.expirations += 1
                self._counters.misses += 1
                return False, []
            self._entries.move_to_end(key)
            self._counters.hits += 1
            return True, copy.deepcopy(list(entry.value))

    def set(self, key: str, results: list[Any] | tuple[Any, ...]) -> None:
        if not self.enabled:
            with self._lock:
                self._counters.bypasses += 1
            return
        if not isinstance(results, (list, tuple)):
            return

        entry = _CacheEntry(
            expires_at=self._clock() + self.ttl_seconds,
            value=tuple(copy.deepcopy(list(results))),
        )
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            self._counters.stores += 1
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
                self._counters.evictions += 1

    def clear(self, *, reset_stats: bool = False) -> None:
        with self._lock:
            self._entries.clear()
            if reset_stats:
                self._counters = _Counters()

    def stats(self) -> dict[str, bool | int | float | str]:
        with self._lock:
            lookups = self._counters.hits + self._counters.misses
            hit_rate = self._counters.hits / lookups if lookups else 0.0
            return {
                "enabled": self.enabled,
                "backend": BACKEND_NAME,
                "entries": len(self._entries),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "hits": self._counters.hits,
                "misses": self._counters.misses,
                "evictions": self._counters.evictions,
                "expirations": self._counters.expirations,
                "stores": self._counters.stores,
                "bypasses": self._counters.bypasses,
                "hit_rate": round(hit_rate, 4),
            }


class CachedRetriever:
    """Decorator exposing the same retrieve() shape as dense retrievers.

    Cache misses delegate to the wrapped retriever. Cache hits return a
    defensive copy of previously retrieved evidence and then the caller's
    normal downstream pipeline continues unchanged.
    """

    def __init__(self, retriever, *, cache: ExactRetrievalCache,
                 static_identity: Mapping[str, Any]):
        self._retriever = retriever
        self._cache = cache
        self._static_identity = _jsonable(dict(static_identity))

    @property
    def cache(self) -> ExactRetrievalCache:
        return self._cache

    def retrieve(self, question: str, k: int = 5, **metadata_filters):
        if not self._cache.enabled:
            self._cache.get("__disabled__")
            return self._retriever.retrieve(question, k=k, **metadata_filters)

        canonical_query = canonicalize_query_for_cache(question)
        key = build_retrieval_cache_key(
            static_identity=self._static_identity,
            canonical_query=canonical_query,
            k=k,
            metadata_filters=metadata_filters,
        )
        found, cached_results = self._cache.get(key)
        if found:
            return cached_results

        results = self._retriever.retrieve(question, k=k, **metadata_filters)
        self._cache.set(key, results)
        return results


__all__ = [
    "BACKEND_NAME",
    "CachedRetriever",
    "ExactRetrievalCache",
    "build_retrieval_cache_key",
    "canonicalize_query_for_cache",
]
