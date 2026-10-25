"""Deterministic retrieval-security layer for dense RAG evidence.

The package is deliberately local and non-LLM: no provider calls, no
network moderation, and no artifact rebuilds. It inspects retrieved text
after retrieval/cache and before prompt construction.
"""

from .models import (
    CandidateSecurityRecord,
    RetrievalSecurityResult,
    RetrievalSecuritySummary,
    SecurityAssessment,
    SecurityFlag,
    SecurityStatus,
)
from .poisoning import DeterministicPoisoningScanner
from .retrieval_guard import RetrievalSecurityGuard
from .telemetry import RetrievalSecurityTelemetry

__all__ = [
    "CandidateSecurityRecord",
    "DeterministicPoisoningScanner",
    "RetrievalSecurityGuard",
    "RetrievalSecurityResult",
    "RetrievalSecuritySummary",
    "RetrievalSecurityTelemetry",
    "SecurityAssessment",
    "SecurityFlag",
    "SecurityStatus",
]
