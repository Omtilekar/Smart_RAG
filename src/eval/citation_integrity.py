"""Task 1.8 - mechanical citation-integrity smoke check.

`PROJECT_EXECUTION.md`'s Task 1.8 requirements: confirm every cited chunk
ID exists, confirm citations refer only to chunks supplied to the
generator, fail clearly on an unknown citation, store source metadata
needed to inspect citations manually. This is NOT an answer-quality
evaluator, NOT an entailment/support grader, and NOT the Task 1.9
~200-question evaluation - purely structural integrity.

Reuses Task 1.7's actual strict citation grammar
(src.generation.citations.parse_citations) rather than defining a second,
possibly-incompatible one.

## A real discrepancy from this task's own framing (documented per Step 8's
instruction to follow actual code, not silently rewrite history)

Empirically verified against the live-committed Task 1.7 parser: of the
three malformed forms Task 1.7's live smoke observed, two
(fullwidth `【...】`, truncated `[chunk63]`) are correctly rejected by the
strict parser outright - they never appear in `GenerationResult.citations`
at all. The third, `[chunk_id: 1158114_2016.htm::chunk106]`, is NOT
rejected by the strict parser: its regex (`\\[([^\\[\\]]+::chunk\\d+)\\]`)
happily matches the whole bracket interior, including the literal
"chunk_id: " prefix, producing a citation string of
`"chunk_id: 1158114_2016.htm::chunk106"` - syntactically "valid" by the
strict grammar, but not a real chunk_id. This case therefore surfaces
here as `unknown_chunk_id` at the existence-check stage, not as
`malformed_citation_attempt` at the attempt-detection stage. Both are
still hard failures; only the specific reason code differs from what the
task prompt's framing assumed. Verified directly, not assumed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.generation.citations import parse_citations

_ASCII_BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")
_FULLWIDTH_BRACKET_RE = re.compile(r"【([^【】]*)】")
_CHUNK_LIKE_RE = re.compile(r"chunk\d+")


def _looks_citation_like(content: str) -> bool:
    """Narrow trigger so ordinary markdown brackets ([see note], [2024],
    [revenue]) are never treated as citation attempts."""
    return bool(_CHUNK_LIKE_RE.search(content)) or "chunk_id" in content


def _is_strict_valid_token(token: str) -> bool:
    """Reuses parse_citations() itself (not a re-derived regex) to test
    whether `token`, wrapped in ASCII brackets, is exactly what the real
    Task 1.7 parser would accept as one citation."""
    return parse_citations(f"[{token}]") == [token]


@dataclass(frozen=True)
class CitationAttempt:
    raw: str            # exact marker as emitted, e.g. "[chunk63]" or "【...】"
    token: str            # bracket-interior content
    bracket_style: str      # "ascii" | "fullwidth"
    strict_valid: bool        # would this exact marker be accepted by src.generation.citations.parse_citations


@dataclass(frozen=True)
class CitationCheck:
    chunk_id: str
    exists_in_index: bool
    was_supplied: bool
    source_metadata: dict | None  # None only when exists_in_index is False


@dataclass(frozen=True)
class CaseResult:
    status: str  # "PASS" | "FAIL"
    failure_reasons: list[str]
    citation_attempts: list[CitationAttempt]
    malformed_attempts: list[CitationAttempt]
    reparsed_citations: list[str]
    parsed_citation_mismatch: bool
    citation_checks: list[CitationCheck]


def detect_citation_attempts(answer_text: str) -> list[CitationAttempt]:
    """Broader-than-strict detector: finds every ASCII- or fullwidth-
    bracketed marker whose content looks chunk-like, then classifies each
    individually as strict-valid or not. Never normalizes/repairs a
    malformed marker - only detects and classifies."""
    attempts: list[CitationAttempt] = []
    for m in _ASCII_BRACKET_RE.finditer(answer_text):
        content = m.group(1)
        if _looks_citation_like(content):
            attempts.append(CitationAttempt(
                raw=f"[{content}]", token=content, bracket_style="ascii",
                strict_valid=_is_strict_valid_token(content),
            ))
    for m in _FULLWIDTH_BRACKET_RE.finditer(answer_text):
        content = m.group(1)
        if _looks_citation_like(content):
            # The strict grammar only ever matches ASCII [...] - a fullwidth
            # marker is never strict-valid regardless of its inner content.
            attempts.append(CitationAttempt(
                raw=f"【{content}】", token=content, bracket_style="fullwidth",
                strict_valid=False,
            ))
    return attempts


def evaluate_citation_integrity(
    *,
    answer: str,
    generation_citations: list[str],
    supplied_chunk_ids: set[str],
    exists_fn,
    metadata_fn,
    abstention_expected: bool,
) -> CaseResult:
    """Mechanical structural check only - no semantic support/entailment
    judgment, no answer-correctness judgment.

    `exists_fn(chunk_id) -> bool` and `metadata_fn(chunk_id) -> dict | None`
    are injected so this function is testable with fakes and does not
    itself know about LanceDB (see src.eval.citation_integrity.LanceDBResolvers
    for the real, index-backed implementation).

    `abstention_expected` is a caller-supplied fact (from the smoke
    question's own pre-configured expected_behavior, e.g. an abstention
    control case), never inferred here from the answer text - this
    function never runs a phrase classifier over `answer`.
    """
    attempts = detect_citation_attempts(answer)
    malformed = [a for a in attempts if not a.strict_valid]
    reparsed = parse_citations(answer)
    mismatch = reparsed != generation_citations

    reasons: list[str] = []
    if mismatch:
        reasons.append("parsed_citation_mismatch")
    if malformed:
        reasons.append("malformed_citation_attempt")

    checks: list[CitationCheck] = []
    for chunk_id in reparsed:
        exists = exists_fn(chunk_id)
        supplied = chunk_id in supplied_chunk_ids
        metadata = metadata_fn(chunk_id) if exists else None
        checks.append(CitationCheck(
            chunk_id=chunk_id, exists_in_index=exists, was_supplied=supplied,
            source_metadata=metadata,
        ))
        if not exists:
            reasons.append("unknown_chunk_id")
        elif not supplied:
            reasons.append("citation_not_in_supplied_context")

    if not reparsed and not abstention_expected:
        reasons.append("missing_required_citation")

    return CaseResult(
        status="PASS" if not reasons else "FAIL",
        failure_reasons=reasons,
        citation_attempts=attempts,
        malformed_attempts=malformed,
        reparsed_citations=reparsed,
        parsed_citation_mismatch=mismatch,
        citation_checks=checks,
    )


class RecordingRetriever:
    """Wraps a real Task 1.6 retriever and records the exact
    `RetrievalResult` objects returned by its most recent call - the same
    objects then passed through to MinimalGenerator. This is how Task 1.8
    observes the exact supplied top-5 for a generation call without a
    second retrieval and without modifying Task 1.6/1.7's public
    contracts (MinimalGenerator only requires a duck-typed
    `.retrieve(question, k)`)."""

    def __init__(self, retriever):
        self._retriever = retriever
        self.last_results = None

    def retrieve(self, question: str, k: int = 5):
        results = self._retriever.retrieve(question, k=k)
        self.last_results = results
        return results


STATIC_METADATA_FIELDS: tuple[str, ...] = (
    "chunk_id", "document_id", "company", "form_type", "fiscal_year",
    "source", "source_filename", "source_split", "ordinal", "token_count",
    "chunk_config_hash", "normalizer_version", "normalization_build_sha256",
    "development_manifest_sha256",
)


class LanceDBResolvers:
    """Real, index-backed `exists_fn`/`metadata_fn` for
    evaluate_citation_integrity(), built on
    src.index.lancedb_index.get_chunk_by_id() - an exact scalar-filter
    lookup, never a vector search, never fuzzy matching."""

    def __init__(self, table):
        self._table = table

    def exists(self, chunk_id: str) -> bool:
        from src.index.lancedb_index import get_chunk_by_id
        return get_chunk_by_id(self._table, chunk_id).num_rows > 0

    def metadata(self, chunk_id: str) -> dict | None:
        from src.index.lancedb_index import get_chunk_by_id
        rows = get_chunk_by_id(self._table, chunk_id)
        if rows.num_rows == 0:
            return None
        row = {f: rows.column(f)[0].as_py() for f in STATIC_METADATA_FIELDS}
        return row
