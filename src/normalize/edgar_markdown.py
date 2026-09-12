"""Task 1.2 - minimal EDGAR-CORPUS -> Markdown normalization.

Deliberately crude, per PROJECT_EXECUTION.md: fixed SEC-item ordering,
whitespace/newline normalization only, deterministic YAML frontmatter, no
semantic cleaning, no invented text. Pure/deterministic logic only - no
filesystem or database access lives in this module (see
scripts/normalize_development_corpus.py for orchestration).
"""

from __future__ import annotations

import json

# Exact source column order in data/edgar_corpus/*.parquet, which is
# already natural SEC 10-K Item order (verified directly via DuckDB schema
# inspection - not assumed from the column names).
SECTION_COLUMNS: tuple[str, ...] = (
    "section_1", "section_1A", "section_1B", "section_2", "section_3",
    "section_4", "section_5", "section_6", "section_7", "section_7A",
    "section_8", "section_9", "section_9A", "section_9B", "section_10",
    "section_11", "section_12", "section_13", "section_14", "section_15",
)

# Frontmatter key order - fixed, matches Task 1.2's documented minimum
# frontmatter contract exactly (no additional keys, nothing invented).
FRONTMATTER_KEYS: tuple[str, ...] = (
    "cik", "company", "form_type", "fiscal_year", "source",
    "source_filename", "document_id", "source_split",
    "development_manifest_sha256",
)

# Task 4.1 full-corpus frontmatter contract. Drops development_manifest_sha256
# (no per-filing dev manifest exists at full-corpus scale - Task 1.1's manifest
# covered only the 1,500-filing dev subset). `company` is deliberately in this
# key list too, but - unlike Task 1.2's dev-corpus contract, where every row
# resolved via the XBRL-aligned manifest - it is a genuinely nullable field
# here: only 26.51% of full EDGAR-CORPUS CIKs (6,877/25,937; 34.09% of rows,
# 31,047/91,086 - measured directly against data/xbrl.duckdb) have any XBRL
# submissions record to look a company name up from. See
# project_plan/PHASE4_FULL_CORPUS_NORMALIZATION.md.
FULL_CORPUS_FRONTMATTER_KEYS: tuple[str, ...] = (
    "cik", "company", "form_type", "fiscal_year", "source",
    "source_filename", "document_id", "source_split",
)


def section_column_to_item_label(column: str) -> str:
    """'section_1A' -> 'Item 1A'. No invented titles - the label is exactly
    the SEC item number/letter encoded in the source column name."""
    if not column.startswith("section_"):
        raise ValueError(f"not a section column: {column!r}")
    suffix = column[len("section_"):]
    return f"Item {suffix}"


def normalize_newlines(text: str) -> str:
    """CRLF/CR -> LF only. No other content transformation."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def render_body(sections: dict[str, str | None]) -> str:
    """Render the Markdown body from raw section text. Only non-empty
    (after strip) sections produce a heading + text block. No heading is
    emitted for a null/empty/whitespace-only section - never fabricated.

    Each block: '## Item {label}\\n\\n{stripped, newline-normalized text}'.
    Blocks are joined with a single blank line between them. The overall
    body has no leading/trailing blank lines; the caller is responsible for
    the file's single final trailing newline.
    """
    blocks: list[str] = []
    for column in SECTION_COLUMNS:
        raw = sections.get(column)
        if raw is None:
            continue
        normalized = normalize_newlines(raw).strip()
        if not normalized:
            continue
        label = section_column_to_item_label(column)
        blocks.append(f"## {label}\n\n{normalized}")
    return "\n\n".join(blocks)


def render_frontmatter(fields: dict, keys: tuple[str, ...] = FRONTMATTER_KEYS) -> str:
    """Deterministic YAML frontmatter. String values are JSON-quoted via
    stdlib json.dumps (a valid, safely-escaped YAML double-quoted scalar) -
    no hand-rolled quoting, no new dependency. Integer values are emitted
    unquoted. `None` is emitted as the bare YAML `null` literal - a
    legitimate, explicit "not authoritatively available" value, never a
    fabricated placeholder (Task 4.1's `company` field on
    FULL_CORPUS_FRONTMATTER_KEYS is the first caller to use this). Key order
    is fixed by `keys` (defaults to FRONTMATTER_KEYS, Task 1.2's original
    contract - unchanged, so every existing call site keeps its exact prior
    behavior), not dict insertion order, so output is stable regardless of
    how the caller built `fields`.
    """
    missing = [k for k in keys if k not in fields]
    if missing:
        raise ValueError(f"missing required frontmatter fields: {missing}")
    lines = ["---"]
    for key in keys:
        value = fields[key]
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            raise TypeError(f"unexpected bool for frontmatter field {key!r}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        elif isinstance(value, str):
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            raise TypeError(f"unsupported frontmatter value type for {key!r}: {type(value).__name__}")
    lines.append("---")
    return "\n".join(lines)


def render_document(
    fields: dict,
    sections: dict[str, str | None],
    frontmatter_keys: tuple[str, ...] = FRONTMATTER_KEYS,
) -> str:
    """Full Markdown document: frontmatter, blank line, body (possibly
    empty - see the known zero-text-section filings documented in
    PHASE1_NORMALIZATION.md / PHASE4_FULL_CORPUS_NORMALIZATION.md), exactly
    one trailing newline. `frontmatter_keys` defaults to Task 1.2's original
    FRONTMATTER_KEYS; Task 4.1 passes FULL_CORPUS_FRONTMATTER_KEYS instead.
    Body rendering (`render_body`) is completely untouched by this
    parameter - textual normalization semantics never change with the
    caller's frontmatter contract."""
    frontmatter = render_frontmatter(fields, keys=frontmatter_keys)
    body = render_body(sections)
    if body:
        return f"{frontmatter}\n\n{body}\n"
    return f"{frontmatter}\n"


def is_all_sections_empty(sections: dict[str, str | None]) -> bool:
    """True when every SECTION_COLUMNS value is null/empty/whitespace-only -
    the general, full-corpus form of Task 1.2's hand-curated
    KNOWN_EMPTY_BODY_DOCUMENT_IDS allowlist. Pure predicate, no I/O."""
    for column in SECTION_COLUMNS:
        raw = sections.get(column)
        if raw is not None and normalize_newlines(raw).strip():
            return False
    return True


def output_filename(document_id: str) -> str:
    """Deterministic one-to-one mapping: '1005817_2016.htm' ->
    '1005817_2016.md'. Replaces only the final extension."""
    if "." not in document_id:
        raise ValueError(f"document_id has no extension: {document_id!r}")
    stem = document_id.rsplit(".", 1)[0]
    return f"{stem}.md"


def count_item_headings(markdown_text: str) -> int:
    """Count '## Item ' headings actually rendered - used by output
    validation, not by rendering itself."""
    return sum(1 for line in markdown_text.splitlines() if line.startswith("## Item "))
