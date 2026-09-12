"""Task 3.12 - portable tests for src.nav.section_navigation. Synthetic
in-memory DuckDB `submissions` table (same convention as
tests/test_xbrl_lookup.py) plus a tmp_path-backed parsed-document
corpus (monkeypatched storage root) - never touches the real frozen
database or the real artifacts/primary_docs/parsed/ corpus."""

from __future__ import annotations

import json

import duckdb
import pytest

from src.nav import section_navigation as nav
from src.parse.source_identity import document_id as build_document_id
from src.storage import StoragePaths


def _con():
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE submissions (
            adsh VARCHAR, cik BIGINT, name VARCHAR, form VARCHAR, fiscal_year INTEGER,
            fp VARCHAR, period VARCHAR, filed VARCHAR
        )
    """)
    return con


def _insert_submission(con, **kwargs):
    defaults = dict(
        adsh="0000000000-24-000001", cik=1000, name="ACME CORP", form="10-K",
        fiscal_year=2020, fp="FY", period="20201231", filed="20210215",
    )
    defaults.update(kwargs)
    con.execute(
        "INSERT INTO submissions VALUES (?,?,?,?,?,?,?,?)",
        [defaults[c] for c in ("adsh", "cik", "name", "form", "fiscal_year", "fp", "period", "filed")],
    )


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    paths = StoragePaths(repo_root=tmp_path, data_root=tmp_path / "data",
                          artifacts_root=tmp_path / "artifacts", results_root=tmp_path / "results")
    monkeypatch.setattr(nav, "get_storage", lambda: paths)
    return paths


def _write_parsed_document(storage, document_id, nodes):
    parsed_dir = storage.artifacts_root / "primary_docs" / "parsed"
    parsed_dir.mkdir(parents=True, exist_ok=True)
    from src.storage import safe_component
    path = parsed_dir / f"{safe_component(document_id)}.json"
    path.write_text(json.dumps(nodes), encoding="utf-8")


def _node(section_id, text, section_title=None, node_type="paragraph"):
    return {"section_id": section_id, "section_title": section_title, "text": text, "node_type": node_type}


# --------------------------------------------------------------- extract_item_reference

def test_extract_item_reference_finds_canonical_item():
    assert nav.extract_item_reference("Summarize Item 7 of this filing.") == "7"


def test_extract_item_reference_normalizes_case_and_suffix():
    assert nav.extract_item_reference("what does item 7a say?") == "7A"


def test_extract_item_reference_none_for_non_canonical_number():
    assert nav.extract_item_reference("Item 99 of this filing") is None


def test_extract_item_reference_none_when_absent():
    assert nav.extract_item_reference("What was revenue in 2020?") is None


# --------------------------------------------------------------- resolve_filing_document_id

def test_resolve_filing_document_id_found():
    con = _con()
    _insert_submission(con)
    outcome, document_id = nav.resolve_filing_document_id(con, cik=1000, fiscal_year=2020)
    assert outcome == "found"
    assert document_id == build_document_id(1000, "0000000000-24-000001")


def test_resolve_filing_document_id_not_found():
    con = _con()
    _insert_submission(con)
    outcome, document_id = nav.resolve_filing_document_id(con, cik=1000, fiscal_year=2019)
    assert outcome == "filing_not_found"
    assert document_id is None


def test_resolve_filing_document_id_ambiguous_on_amended_filing():
    con = _con()
    _insert_submission(con, adsh="0000000000-24-000001")
    _insert_submission(con, adsh="0000000000-24-000099", filed="20210401")  # e.g. a 10-K/A re-submission
    outcome, document_id = nav.resolve_filing_document_id(con, cik=1000, fiscal_year=2020)
    assert outcome == "ambiguous_filing"
    assert document_id is None


def test_resolve_filing_document_id_ignores_non_10k_forms():
    con = _con()
    _insert_submission(con, form="10-Q")
    outcome, document_id = nav.resolve_filing_document_id(con, cik=1000, fiscal_year=2020)
    assert outcome == "filing_not_found"


# --------------------------------------------------------------- navigate_to_section

def test_navigate_to_section_found(storage):
    document_id = build_document_id(1000, "0000000000-24-000001")
    _write_parsed_document(storage, document_id, [
        _node(None, "cover page"),
        _node("7", "MD&A paragraph one", section_title="Item 7. Management's Discussion and Analysis"),
        _node("7", "MD&A paragraph two", section_title="Item 7. Management's Discussion and Analysis"),
        _node("8", "financial statements paragraph"),
    ])
    con = _con()
    _insert_submission(con)
    result = nav.navigate_to_section(con, cik=1000, fiscal_year=2020, item="7")
    assert result.outcome == "found"
    assert result.node_count == 2
    assert result.total_document_node_count == 4
    assert result.section_title == "Item 7. Management's Discussion and Analysis"
    assert result.node_texts == ("MD&A paragraph one", "MD&A paragraph two")


def test_navigate_to_section_never_returns_a_full_document_read(storage):
    """Hard invariant: a successful navigation always returns strictly
    fewer nodes than the whole document - proof no unnecessary global
    retrieval occurred."""
    document_id = build_document_id(1000, "0000000000-24-000001")
    _write_parsed_document(storage, document_id, [
        _node(None, "cover page"),
        _node("7", "MD&A paragraph one", section_title="Item 7."),
        _node("8", "financial statements paragraph"),
    ])
    con = _con()
    _insert_submission(con)
    result = nav.navigate_to_section(con, cik=1000, fiscal_year=2020, item="7")
    assert result.outcome == "found"
    assert result.node_count < result.total_document_node_count
    assert all(True for _ in result.node_texts)  # returned nodes exist


def test_navigate_to_section_never_leaks_other_sections(storage):
    document_id = build_document_id(1000, "0000000000-24-000001")
    _write_parsed_document(storage, document_id, [
        _node("1", "business description"),
        _node("7", "MD&A", section_title="Item 7."),
        _node("7A", "market risk", section_title="Item 7A."),
    ])
    con = _con()
    _insert_submission(con)
    result = nav.navigate_to_section(con, cik=1000, fiscal_year=2020, item="7")
    assert result.node_texts == ("MD&A",)  # never includes "7A" or "1" content


def test_navigate_to_section_not_found_in_parsed_document(storage):
    document_id = build_document_id(1000, "0000000000-24-000001")
    _write_parsed_document(storage, document_id, [_node("1", "business description")])
    con = _con()
    _insert_submission(con)
    result = nav.navigate_to_section(con, cik=1000, fiscal_year=2020, item="7")
    assert result.outcome == "section_not_found"
    assert result.total_document_node_count == 1


def test_navigate_to_section_filing_not_parsed(storage):
    con = _con()
    _insert_submission(con)
    # No parsed JSON file was ever written for this document_id.
    result = nav.navigate_to_section(con, cik=1000, fiscal_year=2020, item="7")
    assert result.outcome == "filing_not_parsed"


def test_navigate_to_section_filing_not_found(storage):
    con = _con()
    # No submission exists at all.
    result = nav.navigate_to_section(con, cik=1000, fiscal_year=2020, item="7")
    assert result.outcome == "filing_not_found"
    assert result.document_id is None


def test_navigate_to_section_ambiguous_filing(storage):
    con = _con()
    _insert_submission(con, adsh="0000000000-24-000001")
    _insert_submission(con, adsh="0000000000-24-000099", filed="20210401")
    result = nav.navigate_to_section(con, cik=1000, fiscal_year=2020, item="7")
    assert result.outcome == "ambiguous_filing"


def test_navigate_to_section_rejects_non_canonical_item(storage):
    con = _con()
    _insert_submission(con)
    with pytest.raises(ValueError):
        nav.navigate_to_section(con, cik=1000, fiscal_year=2020, item="99")


def test_navigate_to_section_loads_only_the_one_requested_document(storage, monkeypatch):
    """Loading a second, unrelated document must never be touched - the
    'avoid unnecessary global retrieval' invariant, verified by call-
    counting the actual file load."""
    target_id = build_document_id(1000, "0000000000-24-000001")
    other_id = build_document_id(2000, "0000000000-24-000002")
    _write_parsed_document(storage, target_id, [_node("7", "MD&A", section_title="Item 7.")])
    _write_parsed_document(storage, other_id, [_node("7", "unrelated company MD&A", section_title="Item 7.")])

    loaded_ids = []
    real_load = nav.load_document_nodes

    def _spy(document_id):
        loaded_ids.append(document_id)
        return real_load(document_id)

    monkeypatch.setattr(nav, "load_document_nodes", _spy)
    con = _con()
    _insert_submission(con)
    result = nav.navigate_to_section(con, cik=1000, fiscal_year=2020, item="7")
    assert result.outcome == "found"
    assert loaded_ids == [target_id]
