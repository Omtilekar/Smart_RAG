"""Task 2.8 - deterministic structural parsing of primary 10-K HTML via
Docling. Docling's own output is NOT authoritative for inline-XBRL
identity (see src/parse/inline_xbrl.py's module docstring) - this module
only produces the structural/table representation (paragraphs, headings,
tables) that inline-XBRL facts are later aligned against.

Docling's HTML backend does not preserve a raw-DOM source locator (no
page/bbox provenance for HTML input, verified empirically: every
`TableItem`/`TextItem`'s `.prov` is an empty list for HTML input). This
module is honest about that (Section 14): `source_locator` is Docling's
own deterministic structural reference (`self_ref`, e.g. "#/texts/42"),
not a raw-HTML XPath or byte offset. It is still fully reproducible -
the same input file + Docling version always produces the same
`self_ref` for the same logical element - just not a literal pointer
into the original HTML source.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TABLE_ROW_GROUP_SIZE = 50  # large-table split threshold (Section 19)

# SEC Form 10-K canonical Item identifiers this module can confidently
# detect (Section 15) - anything else stays section_id=None rather than
# guessing.
_CANONICAL_ITEMS = {
    "1", "1A", "1B", "1C", "2", "3", "4", "5", "6", "7", "7A", "8",
    "9", "9A", "9B", "9C", "10", "11", "12", "13", "14", "15", "16",
}

import re

_ITEM_HEADING_RE = re.compile(r"^Item\s+(\d{1,2}[A-C]?)\.\s+(.+)", re.IGNORECASE)


@dataclass(frozen=True)
class StructuralNode:
    document_id: str
    node_id: str
    parent_node_id: str | None
    node_type: str  # "heading" | "paragraph" | "table" | "other"
    section_id: str | None
    section_title: str | None
    source_order: int
    source_locator: str
    text: str
    content_type: str  # "narrative" | "table"
    table_id: str | None = None
    table_part: int | None = None


def _detect_section_headings(text_items: list) -> dict[int, tuple[str, str]]:
    """Returns {text_item_index: (section_id, section_title)} for the
    LAST occurrence of each canonical Item heading in the document -
    real section headers occur after any table-of-contents listing, and
    (verified against real filings) TOC entries and real headers name
    Items in the same relative order, so the last occurrence of each
    canonical Item id is the real section start. A candidate whose Item
    number is not in `_CANONICAL_ITEMS` is ignored entirely (Section 15:
    prefer section_id=None to a wrong guess)."""
    last_occurrence: dict[str, tuple[int, str, str]] = {}
    for i, item in enumerate(text_items):
        m = _ITEM_HEADING_RE.match(item.text.strip())
        if not m:
            continue
        item_num = m.group(1).upper()
        if item_num not in _CANONICAL_ITEMS:
            continue
        last_occurrence[item_num] = (i, item_num, item.text.strip())

    return {i: (item_num, title) for i, item_num, title in last_occurrence.values()}


def _split_table_rows(rows: list[list[str]], header_row_count: int) -> list[list[list[str]]]:
    """Splits `rows` (including its header rows) into row-group parts of
    at most TABLE_ROW_GROUP_SIZE data rows each, repeating the header
    rows in every part (Section 19). A table small enough to fit in one
    part is returned as a single-element list."""
    header = rows[:header_row_count]
    body = rows[header_row_count:]
    if len(body) <= TABLE_ROW_GROUP_SIZE:
        return [rows]
    parts = []
    for start in range(0, len(body), TABLE_ROW_GROUP_SIZE):
        parts.append(header + body[start:start + TABLE_ROW_GROUP_SIZE])
    return parts


def _table_to_markdown(rows: list[list[str]], header_row_count: int) -> str:
    if not rows:
        return ""
    lines = []
    for i, row in enumerate(rows):
        lines.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in row) + " |")
        if i == header_row_count - 1:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return "\n".join(lines)


def build_structural_nodes(document_id: str, docling_document) -> list[StructuralNode]:
    """Pure transformation of an already-converted DoclingDocument (see
    convert_document() for the I/O step) into this project's
    StructuralNode schema. Deterministic given the same DoclingDocument -
    node_id is `{document_id}#node-{source_order:05d}`, a simple ordinal
    scheme (Section 13 requires determinism, not that the ID be a hash;
    an ordinal tied to document_id is equally deterministic and more
    directly auditable)."""
    text_items = list(docling_document.texts)
    section_map = _detect_section_headings(text_items)
    # id()-keyed lookups instead of list.index() inside the traversal
    # loop below - avoids O(n^2) behavior on large filings (some primary
    # 10-Ks have 5,000+ text items).
    text_index_by_id = {id(t): i for i, t in enumerate(text_items)}
    table_index_by_id = {id(t): i for i, t in enumerate(docling_document.tables)}

    nodes: list[StructuralNode] = []
    order = 0
    current_section_id: str | None = None
    current_section_title: str | None = None

    # interleave texts and tables by their Docling-assigned self_ref index
    # (texts/N, tables/N) is not itself an interleaved document order, so
    # we rebuild document order from doc.body's children traversal.
    body_children = list(docling_document.iterate_items())

    for item, _level in body_children:
        item_type = type(item).__name__
        if item_type == "TableItem":
            table_ordinal = table_index_by_id[id(item)]
            grid = item.data.grid
            rows = [[cell.text if cell is not None else "" for cell in row] for row in grid]
            header_row_count = 1 if rows else 0
            parts = _split_table_rows(rows, header_row_count)
            table_id = f"{document_id}#table-{table_ordinal:04d}"
            for part_idx, part_rows in enumerate(parts):
                node_id = f"{document_id}#node-{order:05d}"
                nodes.append(StructuralNode(
                    document_id=document_id, node_id=node_id, parent_node_id=None,
                    node_type="table", section_id=current_section_id, section_title=current_section_title,
                    source_order=order, source_locator=item.self_ref,
                    text=_table_to_markdown(part_rows, header_row_count),
                    content_type="table", table_id=table_id, table_part=part_idx,
                ))
                order += 1
        elif item_type == "TextItem":
            text_index = text_index_by_id[id(item)]
            if text_index in section_map:
                current_section_id, current_section_title = section_map[text_index]
            node_type = "heading" if text_index in section_map else "paragraph"
            node_id = f"{document_id}#node-{order:05d}"
            nodes.append(StructuralNode(
                document_id=document_id, node_id=node_id, parent_node_id=None,
                node_type=node_type, section_id=current_section_id, section_title=current_section_title,
                source_order=order, source_locator=item.self_ref,
                text=item.text, content_type="narrative",
            ))
            order += 1
        # other item types (pictures, etc.) are not expected in these
        # HTML filings (verified: 0 pictures in the sample filing) and
        # are intentionally not represented as evidence nodes.

    return nodes


def convert_document(html_path: str):
    """The one I/O function in this module - wraps
    docling.document_converter.DocumentConverter.convert(). Kept
    separate from build_structural_nodes() so the pure transformation
    logic above is independently testable against a hand-constructed
    DoclingDocument-shaped fixture."""
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    result = converter.convert(html_path)
    return result.document
