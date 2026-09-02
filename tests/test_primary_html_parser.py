"""Task 2.8 - tests for src/parse/source_identity.py and the pure
transformation logic in src/parse/primary_html.py. The real Docling
integration (convert_document + build_structural_nodes against actual
DoclingDocument objects) is validated in the local_data-marked section
using real primary filings - constructing a synthetic DoclingDocument
object is impractical (it is a complex third-party pydantic model), so
portable tests exercise this module's own pure helper functions
(section detection, table row splitting/serialization) directly with
hand-built inputs."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.parse.source_identity import enumerate_primary_documents, document_id
from src.parse.primary_html import _detect_section_headings, _split_table_rows, _table_to_markdown, TABLE_ROW_GROUP_SIZE


@dataclass
class _FakeTextItem:
    text: str


# --------------------------------------------------------------- source identity

def test_document_id_format():
    assert document_id(12345, "0001234567-24-000001") == "primary:12345:0001234567-24-000001"


def test_enumerate_primary_documents(tmp_path):
    (tmp_path / "100" / "acc-1.htm").parent.mkdir(parents=True)
    (tmp_path / "100" / "acc-1.htm").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "200" / "acc-2.htm").parent.mkdir(parents=True)
    (tmp_path / "200" / "acc-2.htm").write_text("<html></html>", encoding="utf-8")

    docs = enumerate_primary_documents(tmp_path)
    assert len(docs) == 2
    assert docs[0].cik == 100
    assert docs[0].accession == "acc-1"
    assert docs[0].document_id == "primary:100:acc-1"
    assert docs[0].source_sha256  # non-empty
    assert docs[0].source_size_bytes > 0
    # deterministic order: sorted by cik then accession
    assert [d.cik for d in docs] == [100, 200]


def test_enumerate_rejects_zero_byte_file(tmp_path):
    (tmp_path / "100").mkdir()
    (tmp_path / "100" / "acc-1.htm").write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        enumerate_primary_documents(tmp_path)


def test_source_sha256_deterministic(tmp_path):
    (tmp_path / "100").mkdir()
    (tmp_path / "100" / "acc-1.htm").write_text("hello world", encoding="utf-8")
    docs1 = enumerate_primary_documents(tmp_path)
    docs2 = enumerate_primary_documents(tmp_path)
    assert docs1[0].source_sha256 == docs2[0].source_sha256


# --------------------------------------------------------------- section detection

def test_section_detection_finds_canonical_items():
    items = [
        _FakeTextItem("Table of Contents"),
        _FakeTextItem("Item 1. Business"),
        _FakeTextItem("Item 1A. Risk Factors"),
        _FakeTextItem("Some narrative text"),
        _FakeTextItem("Item 1. Business"),  # real header, later occurrence
        _FakeTextItem("Actual business content here"),
        _FakeTextItem("Item 1A. Risk Factors"),  # real header
        _FakeTextItem("Actual risk factors content"),
    ]
    section_map = _detect_section_headings(items)
    # last occurrence of each canonical item wins (index 4 and 6, not 1 and 2)
    assert section_map[4] == ("1", "Item 1. Business")
    assert section_map[6] == ("1A", "Item 1A. Risk Factors")
    assert 1 not in section_map
    assert 2 not in section_map


def test_section_detection_ignores_non_canonical_items():
    items = [_FakeTextItem("Item 99. Not A Real Item")]
    section_map = _detect_section_headings(items)
    assert section_map == {}


def test_section_detection_single_occurrence_no_toc():
    items = [_FakeTextItem("intro"), _FakeTextItem("Item 7. MD&A"), _FakeTextItem("content")]
    section_map = _detect_section_headings(items)
    assert section_map[1] == ("7", "Item 7. MD&A")


def test_section_detection_empty_input():
    assert _detect_section_headings([]) == {}


# --------------------------------------------------------------- table splitting/serialization

def test_small_table_single_part():
    rows = [["A", "B"], ["1", "2"], ["3", "4"]]
    parts = _split_table_rows(rows, header_row_count=1)
    assert len(parts) == 1
    assert parts[0] == rows


def test_large_table_splits_with_repeated_header():
    header = ["Col1", "Col2"]
    body = [[str(i), str(i * 2)] for i in range(120)]
    rows = [header] + body
    parts = _split_table_rows(rows, header_row_count=1)
    assert len(parts) == 3  # 120 rows / 50 per part -> 3 parts (50, 50, 20)
    for part in parts:
        assert part[0] == header  # header repeated in every part
    assert len(parts[0]) == 1 + TABLE_ROW_GROUP_SIZE
    assert len(parts[-1]) == 1 + 20


def test_table_parts_reconstructable():
    header = ["A"]
    body = [[str(i)] for i in range(75)]
    rows = [header] + body
    parts = _split_table_rows(rows, header_row_count=1)
    reconstructed_body = []
    for part in parts:
        reconstructed_body.extend(part[1:])
    assert reconstructed_body == body


def test_table_to_markdown_has_header_separator():
    rows = [["A", "B"], ["1", "2"]]
    md = _table_to_markdown(rows, header_row_count=1)
    lines = md.splitlines()
    assert lines[0] == "| A | B |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| 1 | 2 |"


def test_table_to_markdown_escapes_pipe_and_newline():
    rows = [["A|B"], ["line1\nline2"]]
    md = _table_to_markdown(rows, header_row_count=1)
    assert "\\|" in md
    assert "\n" not in md.split("\n", 2)[-1] or "line1 line2" in md


def test_table_to_markdown_empty_rows():
    assert _table_to_markdown([], header_row_count=0) == ""


# --------------------------------------------------------------- local_data: real Docling integration

@pytest.mark.local_data
@pytest.mark.model
def test_real_primary_document_structural_parsing():
    from src.storage import get_storage
    from src.parse import primary_html as ph

    storage = get_storage()
    path = storage.primary_docs_root / "100122" / "0000100122-24-000002.htm"
    if not path.exists():
        pytest.skip("real primary filing not present")

    doc = ph.convert_document(str(path))
    nodes = ph.build_structural_nodes("primary:100122:0000100122-24-000002", doc)

    assert len(nodes) > 1000
    headings = [n for n in nodes if n.node_type == "heading"]
    assert len(headings) >= 20  # 10-K has ~23 canonical Items
    section_ids = {h.section_id for h in headings}
    assert "1" in section_ids
    assert "7" in section_ids
    assert "7A" in section_ids

    tables = [n for n in nodes if n.node_type == "table"]
    assert len(tables) > 50
    table_ids = {n.table_id for n in tables}
    assert len(table_ids) > 50

    # node IDs are unique and follow the documented deterministic scheme
    node_ids = [n.node_id for n in nodes]
    assert len(node_ids) == len(set(node_ids))
    assert all(nid.startswith("primary:100122:0000100122-24-000002#node-") for nid in node_ids)

    # re-parsing produces byte-identical node IDs/order (Section 48)
    doc2 = ph.convert_document(str(path))
    nodes2 = ph.build_structural_nodes("primary:100122:0000100122-24-000002", doc2)
    assert [n.node_id for n in nodes] == [n.node_id for n in nodes2]
    assert [n.text for n in nodes] == [n.text for n in nodes2]
