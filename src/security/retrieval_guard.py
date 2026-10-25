"""Query-time retrieval security guard for dense RAG candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import (
    CandidateSecurityRecord,
    RetrievalSecurityResult,
    RetrievalSecuritySummary,
    SecurityAssessment,
    SecurityFlag,
    SecurityStatus,
)
from .normalization import security_fingerprint
from .poisoning import OBFUSCATION_FLAGS, POISON_FLAGS, DeterministicPoisoningScanner
from .telemetry import RetrievalSecurityTelemetry

POLICY_VERSION = "retrieval-security-v1"
DEFAULT_ALLOWED_SOURCES = frozenset({"edgar_corpus"})
REQUIRED_PROVENANCE_FIELDS = ("chunk_id", "document_id", "text", "source")
OPTIONAL_ARTIFACT_FIELDS = (
    "chunk_config_hash",
    "normalization_build_sha256",
    "development_manifest_sha256",
)


@dataclass(frozen=True)
class _ProvenanceDecision:
    assessment: SecurityAssessment | None
    missing_count: int = 0
    invalid_source_count: int = 0


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _candidate_attr(candidate, field: str):
    return getattr(candidate, field, None)


class RetrievalSecurityGuard:
    """Filters retrieved dense candidates before context construction.

    It validates provenance, collapses exact duplicate text, runs the
    deterministic poisoning scanner, and records aggregate counters only.
    Suspicious candidates are not passed to generation.
    """

    def __init__(
        self,
        *,
        allowed_sources: Iterable[str] = DEFAULT_ALLOWED_SOURCES,
        scanner: DeterministicPoisoningScanner | None = None,
        telemetry: RetrievalSecurityTelemetry | None = None,
    ) -> None:
        self.allowed_sources = frozenset(allowed_sources)
        self.scanner = scanner or DeterministicPoisoningScanner()
        self.telemetry = telemetry or RetrievalSecurityTelemetry()

    def filter(self, *, query: str, candidates: Iterable) -> RetrievalSecurityResult:
        # The query is accepted to make the query-time boundary explicit,
        # but it is never stored or logged by this layer.
        del query

        candidate_list = list(candidates)
        approved: list = []
        suspicious: list[CandidateSecurityRecord] = []
        blocked: list[CandidateSecurityRecord] = []
        seen_fingerprints: dict[str, str] = {}

        duplicate_count = 0
        missing_count = 0
        invalid_source_count = 0
        poison_signal_count = 0
        obfuscation_signal_count = 0

        for candidate in candidate_list:
            provenance = self._validate_provenance(candidate)
            if provenance.assessment is not None:
                blocked.append(CandidateSecurityRecord(candidate=candidate, assessment=provenance.assessment))
                missing_count += provenance.missing_count
                invalid_source_count += provenance.invalid_source_count
                continue

            text = _candidate_attr(candidate, "text")
            assessment = self.scanner.scan_text(text)
            if any(flag in POISON_FLAGS for flag in assessment.flags):
                poison_signal_count += 1
            if any(flag in OBFUSCATION_FLAGS for flag in assessment.flags):
                obfuscation_signal_count += 1

            fingerprint = security_fingerprint(text)
            duplicate_of = seen_fingerprints.get(fingerprint)
            if duplicate_of is not None:
                duplicate_count += 1
                duplicate_assessment = SecurityAssessment(
                    status=SecurityStatus.BLOCKED,
                    risk_score=assessment.risk_score,
                    flags=tuple(dict.fromkeys((*assessment.flags, SecurityFlag.DUPLICATE_CONTENT))),
                    scanner_version=assessment.scanner_version,
                    details=tuple(dict.fromkeys((*assessment.details, "duplicate_collapse"))),
                )
                blocked.append(CandidateSecurityRecord(
                    candidate=candidate,
                    assessment=duplicate_assessment,
                    duplicate_of=duplicate_of,
                ))
                continue

            seen_fingerprints[fingerprint] = str(_candidate_attr(candidate, "chunk_id"))
            if assessment.status == SecurityStatus.APPROVED:
                approved.append(candidate)
            elif assessment.status == SecurityStatus.SUSPICIOUS:
                suspicious.append(CandidateSecurityRecord(candidate=candidate, assessment=assessment))
            else:
                blocked.append(CandidateSecurityRecord(candidate=candidate, assessment=assessment))

        summary = RetrievalSecuritySummary(
            total_candidates=len(candidate_list),
            approved_candidates=len(approved),
            suspicious_candidates=len(suspicious),
            blocked_candidates=len(blocked),
            duplicate_candidates_collapsed=duplicate_count,
            missing_provenance_count=missing_count,
            invalid_source_count=invalid_source_count,
            poison_signal_count=poison_signal_count,
            obfuscation_signal_count=obfuscation_signal_count,
            all_context_blocked=bool(candidate_list) and not approved,
        )
        self.telemetry.record(summary)
        return RetrievalSecurityResult(
            approved_candidates=approved,
            suspicious_candidates=suspicious,
            blocked_candidates=blocked,
            summary=summary,
        )

    def status_snapshot(self) -> dict:
        return {
            "enabled": True,
            "mode": "deterministic",
            "scanner_version": self.scanner.version,
            "policy_version": POLICY_VERSION,
            "text_scan_scope": "dense_retrieval_candidates",
            "xbrl_policy": "structured_provenance_only",
            "telemetry": self.telemetry.snapshot(),
        }

    def _validate_provenance(self, candidate) -> _ProvenanceDecision:
        missing_fields = [
            field for field in REQUIRED_PROVENANCE_FIELDS
            if _is_blank(_candidate_attr(candidate, field))
        ]
        optional_missing = [
            field for field in OPTIONAL_ARTIFACT_FIELDS
            if hasattr(candidate, field) and _is_blank(_candidate_attr(candidate, field))
        ]
        missing_fields.extend(optional_missing)
        if missing_fields:
            return _ProvenanceDecision(
                assessment=SecurityAssessment(
                    status=SecurityStatus.BLOCKED,
                    risk_score=1.0,
                    flags=(SecurityFlag.MISSING_PROVENANCE,),
                    scanner_version=self.scanner.version,
                    details=tuple(f"missing:{field}" for field in missing_fields),
                ),
                missing_count=len(missing_fields),
            )

        source = str(_candidate_attr(candidate, "source"))
        if source not in self.allowed_sources:
            return _ProvenanceDecision(
                assessment=SecurityAssessment(
                    status=SecurityStatus.BLOCKED,
                    risk_score=1.0,
                    flags=(SecurityFlag.INVALID_SOURCE,),
                    scanner_version=self.scanner.version,
                    details=("source_not_allowed",),
                ),
                invalid_source_count=1,
            )

        return _ProvenanceDecision(assessment=None)
