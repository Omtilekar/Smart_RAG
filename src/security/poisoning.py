"""Deterministic scanner for RAG poisoning and indirect prompt injection."""

from __future__ import annotations

import re

from .models import SecurityAssessment, SecurityFlag, SecurityStatus
from .normalization import normalize_for_security

SCANNER_VERSION = "rag-poison-v1"

INSTRUCTION_OVERRIDE_PATTERNS = (
    re.compile(r"\bignore (?:all )?(?:previous|prior|above|earlier|system|developer) instructions\b", re.IGNORECASE),
    re.compile(r"\bdisregard (?:all )?(?:previous|prior|above|earlier|system|developer|grounding) (?:instructions|rules)\b", re.IGNORECASE),
    re.compile(r"\bdisregard (?:all )?(?:previous|prior|above|earlier) (?:grounding|system|developer) (?:instructions|rules)\b", re.IGNORECASE),
    re.compile(r"\boverride (?:the )?(?:system|developer|previous|prior) (?:instructions|rules|message)\b", re.IGNORECASE),
    re.compile(r"\bforget (?:your|all|the) (?:instructions|rules)\b", re.IGNORECASE),
    re.compile(r"\bdo not (?:follow|obey) (?:the )?(?:system|developer|previous|prior) (?:instructions|rules)\b", re.IGNORECASE),
)

ROLE_IMPERSONATION_PATTERNS = (
    re.compile(r"(?m)^\s*(?:system|developer|assistant)\s*(?:message|prompt|instruction)?\s*:", re.IGNORECASE),
    re.compile(r"\byou are now (?:in )?(?:developer|system|admin) mode\b", re.IGNORECASE),
    re.compile(r"\bnew instructions from (?:the )?(?:developer|system)\b", re.IGNORECASE),
    re.compile(r"\byou are (?:chatgpt|an ai assistant|the assistant)\b", re.IGNORECASE),
)

PROMPT_EXFILTRATION_PATTERNS = (
    re.compile(r"\b(?:reveal|print|show|display|dump|return|leak)\b.{0,80}\b(?:system prompt|developer message|hidden prompt|instructions)\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\b(?:system prompt|developer message|hidden prompt)\b.{0,80}\b(?:reveal|print|show|display|dump|return|leak)\b", re.IGNORECASE | re.DOTALL),
)

TOOL_INSTRUCTION_PATTERNS = (
    re.compile(r"\b(?:call|invoke|use) (?:the )?(?:tool|browser|web|python|shell|api)\b", re.IGNORECASE),
    re.compile(r"\b(?:execute|run) (?:this|the following|a) (?:command|shell|powershell|python|script)\b", re.IGNORECASE),
    re.compile(r"\bsend (?:the|this|all) (?:context|prompt|data|answer) to\b", re.IGNORECASE),
)

CLEAN_DISCUSSION_MARKERS = (
    "security training",
    "cybersecurity",
    "prompt injection",
    "quoted example",
    "training example",
    "audit committee",
    "policy",
    "risk disclosure",
    "discussed",
    "warned",
    "avoid",
    "prohibit",
)

COMPACT_POISON_PATTERNS = (
    "ignorepreviousinstructions",
    "ignoresysteminstructions",
    "disregardpreviousinstructions",
    "revealyoursystemprompt",
    "showyoursystemprompt",
    "developerinstructions",
)

POISON_FLAGS = {
    SecurityFlag.INSTRUCTION_OVERRIDE,
    SecurityFlag.ROLE_IMPERSONATION,
    SecurityFlag.PROMPT_EXFILTRATION,
    SecurityFlag.TOOL_INSTRUCTION,
    SecurityFlag.CONTEXT_BOUNDARY_ESCAPE,
    SecurityFlag.OBFUSCATED_INSTRUCTION,
}

OBFUSCATION_FLAGS = {
    SecurityFlag.HIDDEN_MARKUP,
    SecurityFlag.ZERO_WIDTH_OBFUSCATION,
    SecurityFlag.CONTROL_CHARACTER,
    SecurityFlag.OBFUSCATED_INSTRUCTION,
}


def _matches_any(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _clean_discussion_context(lowered: str) -> bool:
    if not any(marker in lowered for marker in CLEAN_DISCUSSION_MARKERS):
        return False
    discussion_verbs = ("example", "training", "warned", "avoid", "prohibit", "described", "discussed")
    return any(verb in lowered for verb in discussion_verbs)


def _append_flag(flags: list[SecurityFlag], flag: SecurityFlag) -> None:
    if flag not in flags:
        flags.append(flag)


class DeterministicPoisoningScanner:
    """Small rule scanner for retrieved text.

    The scanner is intentionally conservative about clean quoted examples:
    financial/security prose that discusses prompt injection as a risk is
    allowed unless it combines that prose with active role, tool, exfiltration,
    boundary-escape, or obfuscation signals.
    """

    version = SCANNER_VERSION

    def scan_text(self, text: str) -> SecurityAssessment:
        normalized = normalize_for_security(text)
        inspection = normalized.normalized_text
        lowered = inspection.lower()
        compact = re.sub(r"[^a-z0-9]+", "", lowered)

        flags: list[SecurityFlag] = []
        if normalized.hidden_markup_count:
            _append_flag(flags, SecurityFlag.HIDDEN_MARKUP)
        if normalized.zero_width_count:
            _append_flag(flags, SecurityFlag.ZERO_WIDTH_OBFUSCATION)
        if normalized.control_character_count:
            _append_flag(flags, SecurityFlag.CONTROL_CHARACTER)
        if _matches_any(INSTRUCTION_OVERRIDE_PATTERNS, inspection):
            _append_flag(flags, SecurityFlag.INSTRUCTION_OVERRIDE)
        if _matches_any(ROLE_IMPERSONATION_PATTERNS, inspection):
            _append_flag(flags, SecurityFlag.ROLE_IMPERSONATION)
        if _matches_any(PROMPT_EXFILTRATION_PATTERNS, inspection):
            _append_flag(flags, SecurityFlag.PROMPT_EXFILTRATION)
        if _matches_any(TOOL_INSTRUCTION_PATTERNS, inspection):
            _append_flag(flags, SecurityFlag.TOOL_INSTRUCTION)
        if "<<<end_retrieved_evidence>>>" in lowered or "<<<begin_retrieved_evidence>>>" in lowered:
            _append_flag(flags, SecurityFlag.CONTEXT_BOUNDARY_ESCAPE)
        normalization_changed = normalized.original_text != normalized.normalized_text
        if normalization_changed and any(pattern in compact for pattern in COMPACT_POISON_PATTERNS):
            _append_flag(flags, SecurityFlag.OBFUSCATED_INSTRUCTION)

        poison_flags = [flag for flag in flags if flag in POISON_FLAGS]
        obfuscation_flags = [flag for flag in flags if flag in OBFUSCATION_FLAGS]
        clean_discussion = _clean_discussion_context(lowered)
        active_clean_discussion = (
            clean_discussion
            and not any(flag in flags for flag in (
                SecurityFlag.ROLE_IMPERSONATION,
                SecurityFlag.PROMPT_EXFILTRATION,
                SecurityFlag.TOOL_INSTRUCTION,
                SecurityFlag.CONTEXT_BOUNDARY_ESCAPE,
                SecurityFlag.HIDDEN_MARKUP,
                SecurityFlag.ZERO_WIDTH_OBFUSCATION,
                SecurityFlag.CONTROL_CHARACTER,
                SecurityFlag.OBFUSCATED_INSTRUCTION,
            ))
        )
        if active_clean_discussion:
            return SecurityAssessment(
                status=SecurityStatus.APPROVED,
                risk_score=0.10,
                flags=tuple(flags),
                scanner_version=self.version,
                details=("clean_security_discussion",),
            )

        risk_score = 0.0
        if SecurityFlag.INSTRUCTION_OVERRIDE in flags:
            risk_score += 0.55
        if SecurityFlag.ROLE_IMPERSONATION in flags:
            risk_score += 0.50
        if SecurityFlag.PROMPT_EXFILTRATION in flags:
            risk_score += 0.50
        if SecurityFlag.TOOL_INSTRUCTION in flags:
            risk_score += 0.45
        if SecurityFlag.CONTEXT_BOUNDARY_ESCAPE in flags:
            risk_score += 0.45
        if SecurityFlag.OBFUSCATED_INSTRUCTION in flags:
            risk_score += 0.35
        if SecurityFlag.HIDDEN_MARKUP in flags:
            risk_score += 0.25
        if SecurityFlag.ZERO_WIDTH_OBFUSCATION in flags:
            risk_score += 0.25
        if SecurityFlag.CONTROL_CHARACTER in flags:
            risk_score += 0.20
        risk_score = min(risk_score, 1.0)

        if poison_flags and (
            SecurityFlag.INSTRUCTION_OVERRIDE in flags
            or SecurityFlag.ROLE_IMPERSONATION in flags
            or SecurityFlag.PROMPT_EXFILTRATION in flags
            or SecurityFlag.TOOL_INSTRUCTION in flags
            or SecurityFlag.CONTEXT_BOUNDARY_ESCAPE in flags
            or risk_score >= 0.75
        ):
            status = SecurityStatus.BLOCKED
        elif flags:
            status = SecurityStatus.SUSPICIOUS
        else:
            status = SecurityStatus.APPROVED

        details = []
        if poison_flags:
            details.append("poison_signal")
        if obfuscation_flags:
            details.append("obfuscation_signal")
        return SecurityAssessment(
            status=status,
            risk_score=risk_score,
            flags=tuple(flags),
            scanner_version=self.version,
            details=tuple(details),
        )
