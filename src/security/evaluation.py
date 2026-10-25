"""Synthetic retrieval-security metric helpers."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Iterable, Mapping

from .models import SecurityStatus
from .retrieval_guard import RetrievalSecurityGuard


@dataclass(frozen=True)
class SecurityFixtureMetrics:
    poison_detection_recall: float
    false_positive_rate: float
    malicious_context_acceptance_rate: float
    poison_retrieval_acceptance_rate: float
    clean_candidate_retention_rate: float
    high_confidence_poison_blocked_rate: float
    missing_provenance_blocked_rate: float
    cases: int
    poison_cases: int
    clean_cases: int


def _candidate_from_case(case: Mapping[str, object], text: str):
    return SimpleNamespace(
        rank=1,
        score=0.9,
        distance=0.1,
        chunk_id=case["chunk_id"] if "chunk_id" in case else "fixture.htm::chunk0",
        document_id=case["document_id"] if "document_id" in case else "fixture.htm",
        text=text,
        cik=1000,
        company="FIXTURE CO",
        form_type="10-K",
        fiscal_year=2020,
        source=case["source"] if "source" in case else "edgar_corpus",
        source_filename="fixture.htm",
        source_split="synthetic",
        ordinal=0,
        token_count=10,
        chunk_config_hash="fixture-hash",
        normalizer_version="security-fixture-v1",
        normalization_build_sha256="x" * 64,
        development_manifest_sha256="y" * 64,
    )


def _status_for_case(case: Mapping[str, object], guard: RetrievalSecurityGuard) -> SecurityStatus:
    texts = case["texts"] if "texts" in case else [case["text"]]
    candidates = [_candidate_from_case(case, str(text)) for text in texts]
    result = guard.filter(query="synthetic fixture query", candidates=candidates)
    if result.approved_candidates:
        return SecurityStatus.APPROVED
    if result.suspicious_candidates:
        return SecurityStatus.SUSPICIOUS
    return SecurityStatus.BLOCKED


def evaluate_security_fixture(cases: Iterable[Mapping[str, object]], guard: RetrievalSecurityGuard | None = None) -> SecurityFixtureMetrics:
    guard = guard or RetrievalSecurityGuard()
    case_list = list(cases)

    poison_total = 0
    poison_detected = 0
    poison_approved = 0
    clean_total = 0
    clean_approved = 0
    clean_rejected = 0
    high_conf_total = 0
    high_conf_blocked = 0
    missing_total = 0
    missing_blocked = 0

    for case in case_list:
        status = _status_for_case(case, guard)
        expected = str(case["expected"])
        category = str(case["category"])
        is_clean = expected == SecurityStatus.APPROVED.value
        if is_clean:
            clean_total += 1
            if status == SecurityStatus.APPROVED:
                clean_approved += 1
            else:
                clean_rejected += 1
        else:
            poison_total += 1
            if status != SecurityStatus.APPROVED:
                poison_detected += 1
            else:
                poison_approved += 1
        if expected == SecurityStatus.BLOCKED.value:
            high_conf_total += 1
            if status == SecurityStatus.BLOCKED:
                high_conf_blocked += 1
        if category == "metadata_provenance_failures":
            missing_total += 1
            if status == SecurityStatus.BLOCKED:
                missing_blocked += 1

    return SecurityFixtureMetrics(
        poison_detection_recall=poison_detected / poison_total if poison_total else 1.0,
        false_positive_rate=clean_rejected / clean_total if clean_total else 0.0,
        malicious_context_acceptance_rate=poison_approved / poison_total if poison_total else 0.0,
        poison_retrieval_acceptance_rate=poison_approved / poison_total if poison_total else 0.0,
        clean_candidate_retention_rate=clean_approved / clean_total if clean_total else 1.0,
        high_confidence_poison_blocked_rate=high_conf_blocked / high_conf_total if high_conf_total else 1.0,
        missing_provenance_blocked_rate=missing_blocked / missing_total if missing_total else 1.0,
        cases=len(case_list),
        poison_cases=poison_total,
        clean_cases=clean_total,
    )
