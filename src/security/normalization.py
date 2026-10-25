"""Normalization helpers used only for security inspection.

The original retrieved evidence is never rewritten. Callers inspect the
normalized view, then pass the untouched candidate forward only if it is
approved.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass


ZERO_WIDTH_CHARACTERS = (
    "\u200b", "\u200c", "\u200d", "\ufeff", "\u2060", "\u180e",
)

HIDDEN_MARKUP_RE = re.compile(
    r"<!--.*?-->|<\s*(script|style|template)\b.*?</\s*\1\s*>|"
    r"display\s*:\s*none|visibility\s*:\s*hidden|\bhidden\s*=",
    re.IGNORECASE | re.DOTALL,
)

WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SecurityNormalizedText:
    original_text: str
    normalized_text: str
    zero_width_count: int
    control_character_count: int
    hidden_markup_count: int


def normalize_for_security(text: str) -> SecurityNormalizedText:
    """Return a normalized inspection view without mutating evidence."""
    if not isinstance(text, str):
        text = "" if text is None else str(text)

    normalized = unicodedata.normalize("NFKC", text)

    zero_width_count = 0
    for char in ZERO_WIDTH_CHARACTERS:
        count = normalized.count(char)
        if count:
            zero_width_count += count
            normalized = normalized.replace(char, "")

    control_character_count = 0
    cleaned_chars: list[str] = []
    for char in normalized:
        codepoint = ord(char)
        if (codepoint < 32 and char not in ("\n", "\r", "\t")) or codepoint == 127:
            control_character_count += 1
            cleaned_chars.append(" ")
        else:
            cleaned_chars.append(char)

    normalized = "".join(cleaned_chars)
    hidden_markup_count = len(HIDDEN_MARKUP_RE.findall(normalized))
    normalized = WHITESPACE_RE.sub(" ", normalized).strip()

    return SecurityNormalizedText(
        original_text=text,
        normalized_text=normalized,
        zero_width_count=zero_width_count,
        control_character_count=control_character_count,
        hidden_markup_count=hidden_markup_count,
    )


def security_fingerprint(text: str) -> str:
    normalized = normalize_for_security(text).normalized_text
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
