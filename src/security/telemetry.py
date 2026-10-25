"""Safe aggregate telemetry for retrieval-security decisions."""

from __future__ import annotations

from threading import Lock

from .models import RetrievalSecuritySummary


class RetrievalSecurityTelemetry:
    """Thread-safe in-memory counters with no raw text or query storage."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters = {
            "scans": 0,
            "candidate_count": 0,
            "approved_candidates": 0,
            "suspicious_candidates": 0,
            "blocked_candidates": 0,
            "missing_provenance_count": 0,
            "invalid_source_count": 0,
            "duplicate_candidates_collapsed": 0,
            "poison_signal_count": 0,
            "obfuscation_signal_count": 0,
            "all_context_blocked_count": 0,
        }

    def record(self, summary: RetrievalSecuritySummary) -> None:
        with self._lock:
            self._counters["scans"] += 1
            self._counters["candidate_count"] += summary.total_candidates
            self._counters["approved_candidates"] += summary.approved_candidates
            self._counters["suspicious_candidates"] += summary.suspicious_candidates
            self._counters["blocked_candidates"] += summary.blocked_candidates
            self._counters["missing_provenance_count"] += summary.missing_provenance_count
            self._counters["invalid_source_count"] += summary.invalid_source_count
            self._counters["duplicate_candidates_collapsed"] += summary.duplicate_candidates_collapsed
            self._counters["poison_signal_count"] += summary.poison_signal_count
            self._counters["obfuscation_signal_count"] += summary.obfuscation_signal_count
            if summary.all_context_blocked:
                self._counters["all_context_blocked_count"] += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)
