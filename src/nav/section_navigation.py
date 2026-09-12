"""Task 3.12 - simple tree/section navigation for queries like "Summarize
Item 7 of this filing." No retrieval, no embedding call, no generation,
no full-corpus scan. Reuses, never reimplements:

  - Task 2.8's `src.parse.primary_html` canonical-Item detection
    (`_CANONICAL_ITEMS`, Section 15) - the ONE section-boundary source
    of truth. This module never re-derives Item boundaries; it only
    looks up the already-computed `section_id` on Task 2.8's parsed
    structural nodes.
  - The already-parsed `artifacts/primary_docs/parsed/<doc_key>.json`
    corpus (Task 2.8, locally-derived/gitignored, deterministic given
    source_sha256 + parser_config_hash).
  - `data/xbrl.duckdb`'s `submissions` table (cik, adsh, fiscal_year,
    form) for filing identification - the same frozen source Task
    2.1/2.2's truth contract and Task 2.8's own document_id
    construction are built from.

`navigate_to_section()` loads exactly one document's parsed JSON file -
never scans any other document (the "avoid unnecessary global
retrieval" invariant).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.parse.primary_html import _CANONICAL_ITEMS
from src.parse.source_identity import document_id as build_document_id
from src.storage import get_storage, safe_component

OUTCOMES: tuple[str, ...] = (
    "found", "section_not_found", "filing_not_parsed", "filing_not_found", "ambiguous_filing",
)

_ITEM_REFERENCE_RE = re.compile(r"\bItem\s+(\d{1,2}[A-C]?)\b", re.IGNORECASE)


def extract_item_reference(text: str) -> str | None:
    """Extracts a canonical SEC Item id (e.g. "7", "7A") referenced in
    free text (e.g. "Summarize Item 7 of this filing"). Returns None if
    no canonical Item id is found - never guesses (mirrors Task 2.8's
    own section_id=None-over-a-wrong-guess policy, Section 15)."""
    for m in _ITEM_REFERENCE_RE.finditer(text):
        item = m.group(1).upper()
        if item in _CANONICAL_ITEMS:
            return item
    return None


@dataclass(frozen=True)
class SectionNavigationResult:
    outcome: str
    document_id: str | None
    cik: int
    fiscal_year: int
    item: str
    section_title: str | None = None
    node_texts: tuple[str, ...] = ()
    node_count: int = 0
    total_document_node_count: int = 0
    candidate_count: int = 0


def resolve_filing_document_id(con, *, cik: int, fiscal_year: int) -> tuple[str, str | None]:
    """Resolves (cik, fiscal_year) to a Task 2.8 `document_id` via the
    frozen `submissions` table, restricted to form='10-K' (Task 3.9's
    finding: form_type is constant across this corpus). Returns
    (outcome, document_id): outcome is "found" (document_id set),
    "filing_not_found" (zero matches, document_id=None), or
    "ambiguous_filing" (more than one 10-K submission for the same
    cik+fiscal_year, e.g. an amended filing - never silently picks
    one, document_id=None)."""
    rows = con.execute(
        "SELECT accession FROM (SELECT adsh AS accession FROM submissions "
        "WHERE cik = ? AND fiscal_year = ? AND form = '10-K') t",
        [cik, fiscal_year],
    ).fetchall()
    if not rows:
        return "filing_not_found", None
    if len(rows) > 1:
        return "ambiguous_filing", None
    accession = rows[0][0]
    return "found", build_document_id(cik, accession)


def _parsed_document_path(document_id: str) -> Path:
    storage = get_storage()
    doc_key = safe_component(document_id)
    return storage.artifacts_root / "primary_docs" / "parsed" / f"{doc_key}.json"


def load_document_nodes(document_id: str) -> list[dict] | None:
    """Loads exactly Task 2.8's parsed structural-node list for one
    document - never scans or loads any other document (the "avoid
    unnecessary global retrieval" invariant). Returns None if this
    document was never parsed (an honest, documented coverage gap -
    see project_plan/PHASE3_TREE_SECTION_NAVIGATION.md)."""
    path = _parsed_document_path(document_id)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def navigate_to_section(con, *, cik: int, fiscal_year: int, item: str) -> SectionNavigationResult:
    """End-to-end filing identification + section navigation. Raises
    ValueError for a non-canonical `item` (never silently accepts a
    guess). Loads at most one document's parsed nodes."""
    if item not in _CANONICAL_ITEMS:
        raise ValueError(f"not a canonical SEC Item id: {item!r}")

    filing_outcome, document_id = resolve_filing_document_id(con, cik=cik, fiscal_year=fiscal_year)
    if filing_outcome != "found":
        return SectionNavigationResult(outcome=filing_outcome, document_id=None, cik=cik, fiscal_year=fiscal_year, item=item)

    nodes = load_document_nodes(document_id)
    if nodes is None:
        return SectionNavigationResult(outcome="filing_not_parsed", document_id=document_id, cik=cik, fiscal_year=fiscal_year, item=item)

    matched = [n for n in nodes if n.get("section_id") == item]
    if not matched:
        return SectionNavigationResult(
            outcome="section_not_found", document_id=document_id, cik=cik, fiscal_year=fiscal_year, item=item,
            total_document_node_count=len(nodes),
        )

    section_title = matched[0].get("section_title")
    return SectionNavigationResult(
        outcome="found", document_id=document_id, cik=cik, fiscal_year=fiscal_year, item=item,
        section_title=section_title, node_texts=tuple(n["text"] for n in matched),
        node_count=len(matched), total_document_node_count=len(nodes),
    )


__all__ = [
    "OUTCOMES", "extract_item_reference", "SectionNavigationResult",
    "resolve_filing_document_id", "load_document_nodes", "navigate_to_section",
]
