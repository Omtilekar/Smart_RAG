"""Typed retrieval-security decisions.

These models intentionally carry metadata and counters, not raw retrieved
text or raw user queries. The candidate object itself is retained only in
process so the generator can continue with the original evidence object
when it is approved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SecurityStatus(str, Enum):
    APPROVED = "approved"
    SUSPICIOUS = "suspicious"
    BLOCKED = "blocked"


class SecurityFlag(str, Enum):
    MISSING_PROVENANCE = "missing_provenance"
    INVALID_SOURCE = "invalid_source"
    DUPLICATE_CONTENT = "duplicate_content"
    INSTRUCTION_OVERRIDE = "instruction_override"
    ROLE_IMPERSONATION = "role_impersonation"
    PROMPT_EXFILTRATION = "prompt_exfiltration"
    TOOL_INSTRUCTION = "tool_instruction"
    CONTEXT_BOUNDARY_ESCAPE = "context_boundary_escape"
    HIDDEN_MARKUP = "hidden_markup"
    ZERO_WIDTH_OBFUSCATION = "zero_width_obfuscation"
    CONTROL_CHARACTER = "control_character"
    OBFUSCATED_INSTRUCTION = "obfuscated_instruction"


@dataclass(frozen=True)
class SecurityAssessment:
    status: SecurityStatus
    risk_score: float
    flags: tuple[SecurityFlag, ...]
    scanner_version: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateSecurityRecord:
    candidate: Any
    assessment: SecurityAssessment
    duplicate_of: str | None = None


@dataclass(frozen=True)
class RetrievalSecuritySummary:
    total_candidates: int
    approved_candidates: int
    suspicious_candidates: int
    blocked_candidates: int
    duplicate_candidates_collapsed: int = 0
    missing_provenance_count: int = 0
    invalid_source_count: int = 0
    poison_signal_count: int = 0
    obfuscation_signal_count: int = 0
    all_context_blocked: bool = False


@dataclass(frozen=True)
class RetrievalSecurityResult:
    approved_candidates: list[Any]
    suspicious_candidates: list[CandidateSecurityRecord]
    blocked_candidates: list[CandidateSecurityRecord]
    summary: RetrievalSecuritySummary
