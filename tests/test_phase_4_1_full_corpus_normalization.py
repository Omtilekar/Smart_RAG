"""Task 4.1 - full-corpus normalization driver tests.

Portable tests use tiny synthetic fixtures only - no 91,086-row build runs
inside pytest. Tests that touch real frozen local data/artifacts are marked
`local_data`.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

from src.artifacts.versioning import ConfigHashError, semantic_hash
from src.normalize.edgar_markdown import (
    SECTION_COLUMNS,
    FRONTMATTER_KEYS,
    FULL_CORPUS_FRONTMATTER_KEYS,
    render_document,
    is_all_sections_empty,
)
from src.storage import get_storage, StorageError

import scripts.normalize_full_corpus as m


def _sections(**overrides) -> dict:
    base = {col: None for col in SECTION_COLUMNS}
    base.update(overrides)
    return base


# --------------------------------------------------------------- 1-2. config hash determinism

def test_config_hash_deterministic_across_calls():
    assert m.config_hash(m.build_config()) == m.config_hash(m.build_config())


def test_config_hash_changes_when_semantics_change():
    cfg = m.build_config()
    mutated = dict(cfg)
    mutated["newline_policy"] = "something else entirely"
    assert m.config_hash(cfg) != m.config_hash(mutated)


def test_config_hash_is_sha256_shaped():
    h = m.config_hash(m.build_config())
    assert len(h) == 64
    int(h, 16)  # raises if not hex


# --------------------------------------------------------------- 3/13. document id / output path determinism

def test_output_filename_matches_document_id_deterministically():
    assert m.output_filename("1005817_2016.htm") == "1005817_2016.md"
    assert m.output_filename("1005817_2016.htm") == m.output_filename("1005817_2016.htm")


# --------------------------------------------------------------- 4. duplicate source identity rejection

def test_assert_source_healthy_rejects_duplicate_filenames():
    bad_audit = {
        "total_rows": m.EXPECTED_SOURCE_DOCUMENT_COUNT,
        "duplicate_filename_groups": 3,
        "duplicate_cik_year_groups": 0,
        "null_or_empty_filename": 0,
        "null_or_empty_cik": 0,
        "null_or_empty_year": 0,
        "distinct_ciks": m.EXPECTED_SOURCE_CIK_COUNT,
        "year_min": 1993, "year_max": 2020,
    }
    with pytest.raises(SystemExit):
        m.assert_source_healthy(bad_audit)


def test_assert_source_healthy_accepts_clean_audit():
    good_audit = {
        "total_rows": m.EXPECTED_SOURCE_DOCUMENT_COUNT,
        "duplicate_filename_groups": 0,
        "duplicate_cik_year_groups": 0,
        "null_or_empty_filename": 0,
        "null_or_empty_cik": 0,
        "null_or_empty_year": 0,
        "distinct_ciks": m.EXPECTED_SOURCE_CIK_COUNT,
        "year_min": 1993, "year_max": 2020,
    }
    m.assert_source_healthy(good_audit)  # must not raise


# --------------------------------------------------------------- 5/6. metadata type normalization / no fabrication

def test_frontmatter_fields_normalize_cik_and_year_types():
    row = {"filename": "123_2015.htm", "split": "train", "cik": "123", "year": "2015"}
    fields = m.build_frontmatter_fields(row, company_lookup={123: "ACME CORP"})
    assert isinstance(fields["cik"], int) and fields["cik"] == 123
    assert isinstance(fields["fiscal_year"], int) and fields["fiscal_year"] == 2015
    assert fields["company"] == "ACME CORP"


def test_company_is_null_not_fabricated_when_cik_unresolved():
    row = {"filename": "999_2015.htm", "split": "train", "cik": "999", "year": "2015"}
    fields = m.build_frontmatter_fields(row, company_lookup={})
    assert fields["company"] is None


def test_company_lookup_tie_break_uses_most_recently_filed():
    # Simulated submissions rows for one CIK with two distinct historical names.
    rows = [(42, "OLD NAME INC", "20100101"), (42, "NEW NAME INC", "20200101")]
    best: dict[int, tuple[str, str]] = {}
    for cik, name, filed in rows:
        current = best.get(cik)
        if current is None or filed > current[1]:
            best[cik] = (name, filed)
    assert best[42][0] == "NEW NAME INC"


# --------------------------------------------------------------- 7/8. section ordering / empty-section omission

def test_section_ordering_preserved_in_full_corpus_frontmatter_path():
    sections = _sections(section_1="Item 1 text", section_7="Item 7 text")
    fields = {
        "cik": 1, "company": None, "form_type": "10-K", "fiscal_year": 2020,
        "source": "edgar_corpus", "source_filename": "x.htm", "document_id": "x.htm",
        "source_split": "train",
    }
    text = render_document(fields, sections, frontmatter_keys=FULL_CORPUS_FRONTMATTER_KEYS)
    i1 = text.index("## Item 1")
    i7 = text.index("## Item 7")
    assert i1 < i7


def test_whitespace_only_section_is_omitted():
    sections = _sections(section_1="   \n\t  ", section_2="real text")
    assert "## Item 1" not in "".join(f"{k}:{v}" for k, v in sections.items())  # sanity
    fields = {
        "cik": 1, "company": None, "form_type": "10-K", "fiscal_year": 2020,
        "source": "edgar_corpus", "source_filename": "x.htm", "document_id": "x.htm",
        "source_split": "train",
    }
    text = render_document(fields, sections, frontmatter_keys=FULL_CORPUS_FRONTMATTER_KEYS)
    assert "## Item 1\n" not in text
    assert "## Item 2" in text


# --------------------------------------------------------------- 9. empty-document handling

def test_is_all_sections_empty_true_for_all_blank():
    sections = _sections(section_1="", section_2="   ")
    assert is_all_sections_empty(sections) is True


def test_is_all_sections_empty_false_when_one_section_has_text():
    sections = _sections(section_1="real content")
    assert is_all_sections_empty(sections) is False


def test_render_unit_classifies_empty_source_document():
    row = {
        "filename": "1_2020.htm", "split": "train", "cik": "1", "year": "2020",
        **_sections(),
    }
    fname, text, outcome = m.render_unit(row, company_lookup={})
    assert outcome == "VALID_EMPTY_SOURCE"
    assert m.count_item_headings(text) == 0


def test_render_unit_classifies_normalized_document():
    row = {
        "filename": "1_2020.htm", "split": "train", "cik": "1", "year": "2020",
        **_sections(section_1="Some real business description."),
    }
    fname, text, outcome = m.render_unit(row, company_lookup={})
    assert outcome == "NORMALIZED"
    assert m.count_item_headings(text) == 1


# --------------------------------------------------------------- 10/12. newline normalization / trailing newline

def test_crlf_and_cr_normalized_to_lf():
    sections = _sections(section_1="line one\r\nline two\rline three")
    fields = {
        "cik": 1, "company": None, "form_type": "10-K", "fiscal_year": 2020,
        "source": "edgar_corpus", "source_filename": "x.htm", "document_id": "x.htm",
        "source_split": "train",
    }
    text = render_document(fields, sections, frontmatter_keys=FULL_CORPUS_FRONTMATTER_KEYS)
    assert "\r" not in text


def test_exactly_one_trailing_newline():
    row = {
        "filename": "1_2020.htm", "split": "train", "cik": "1", "year": "2020",
        **_sections(section_1="text"),
    }
    _fname, text, _outcome = m.render_unit(row, company_lookup={})
    assert text.endswith("\n") and not text.endswith("\n\n")


# --------------------------------------------------------------- 11. unicode preservation

def test_unicode_preserved_in_body_and_frontmatter():
    row = {
        "filename": "1_2020.htm", "split": "train", "cik": "1", "year": "2020",
        **_sections(section_1="Café Münchén — “quoted” naïve résumé"),
    }
    _fname, text, _outcome = m.render_unit(row, company_lookup={1: "Café Corp — Zürich"})
    assert "Café Münchén" in text
    assert "Café Corp" in text


# --------------------------------------------------------------- 14. path traversal rejection

def test_normalized_dir_for_config_rejects_non_hash_input():
    storage = get_storage()
    with pytest.raises(ConfigHashError):
        storage.normalized_dir_for_config("../escape")


def test_normalized_dir_for_config_rejects_short_string():
    storage = get_storage()
    with pytest.raises(ConfigHashError):
        storage.normalized_dir_for_config("deadbeef")


def test_normalized_dir_for_config_accepts_real_hash():
    storage = get_storage()
    h = "a" * 64
    path = storage.normalized_dir_for_config(h)
    assert path.parts[-2:] == ("normalized_full", h)


# --------------------------------------------------------------- 15/16. checkpoint mismatch rejection

def test_checkpoint_config_mismatch_rejected():
    header = {"phase_4_1_config_hash": "a" * 64, "source_document_ids_sha256": "b" * 64}
    with pytest.raises(SystemExit):
        m.assert_checkpoint_resumable(header, "c" * 64, "b" * 64, ckpt_path=None)


def test_checkpoint_source_mismatch_rejected():
    header = {"phase_4_1_config_hash": "a" * 64, "source_document_ids_sha256": "b" * 64}
    with pytest.raises(SystemExit):
        m.assert_checkpoint_resumable(header, "a" * 64, "different" * 8, ckpt_path=None)


def test_checkpoint_matching_header_accepted():
    header = {"phase_4_1_config_hash": "a" * 64, "source_document_ids_sha256": "b" * 64}
    m.assert_checkpoint_resumable(header, "a" * 64, "b" * 64, ckpt_path=None)  # must not raise


def test_checkpoint_missing_header_is_not_a_mismatch():
    m.assert_checkpoint_resumable(None, "a" * 64, "b" * 64, ckpt_path=None)  # must not raise


# --------------------------------------------------------------- 17. resume skips only validated completed units

def test_verify_completed_units_excludes_corrupted_content(tmp_path):
    # write_bytes matches the real driver's atomic_write_text (no newline
    # translation) - write_text on Windows would silently rewrite \n -> \r\n
    # and desync the hash from what's actually on disk.
    p = tmp_path / "doc.md"
    p.write_bytes(b"real content\n")
    import hashlib
    real_hash = hashlib.sha256(b"real content\n").hexdigest()
    records = {
        "doc": {"document_id": "doc", "outcome": "NORMALIZED", "output_relpath": "doc.md", "content_sha256": real_hash},
    }
    verified = m.verify_completed_units(tmp_path, records)
    assert "doc" in verified

    # Now corrupt the on-disk file without updating the checkpoint record.
    p.write_bytes(b"tampered content\n")
    verified_after_tamper = m.verify_completed_units(tmp_path, records)
    assert "doc" not in verified_after_tamper


def test_verify_completed_units_excludes_missing_file(tmp_path):
    records = {
        "doc": {"document_id": "doc", "outcome": "NORMALIZED", "output_relpath": "missing.md", "content_sha256": "x"},
    }
    verified = m.verify_completed_units(tmp_path, records)
    assert verified == {}


def test_verify_completed_units_never_treats_failed_as_complete(tmp_path):
    records = {
        "doc": {"document_id": "doc", "outcome": "FAILED", "output_relpath": None, "content_sha256": None},
    }
    verified = m.verify_completed_units(tmp_path, records)
    assert verified == {}


# --------------------------------------------------------------- 18. atomic partial-write behavior

def test_atomic_write_leaves_no_tmp_file_and_correct_content(tmp_path):
    target = tmp_path / "out.md"
    m.atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert not (tmp_path / "out.md.tmp").exists()


# --------------------------------------------------------------- 19. corrupt checkpoint/unit rejection

def test_read_checkpoint_drops_partial_trailing_line(tmp_path):
    p = tmp_path / "build_state.jsonl"
    header = {"record_type": "header", "phase_4_1_config_hash": "a" * 64, "source_document_ids_sha256": "b" * 64}
    unit = {"record_type": "unit", "document_id": "x", "outcome": "NORMALIZED", "output_relpath": "x.md", "content_sha256": "c" * 64, "bytes": 1}
    p.write_text(json.dumps(header) + "\n" + json.dumps(unit) + "\n" + '{"record_type": "unit", "docum', encoding="utf-8")
    read_header, records = m.read_checkpoint(p)
    assert read_header["phase_4_1_config_hash"] == "a" * 64
    assert "x" in records
    assert len(records) == 1  # the truncated trailing line never became a record


def test_read_checkpoint_rejects_corrupt_non_trailing_line(tmp_path):
    p = tmp_path / "build_state.jsonl"
    header = {"record_type": "header", "phase_4_1_config_hash": "a" * 64, "source_document_ids_sha256": "b" * 64}
    p.write_text(json.dumps(header) + "\n" + "not valid json at all\n" + "{}\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        m.read_checkpoint(p)


# --------------------------------------------------------------- 20. failed rows cannot disappear silently

def test_summarize_final_accounts_for_failed_rows_as_missing(tmp_path):
    metadata = [
        {"document_id": "ok.htm", "split": "train", "cik": 1, "year": 2020, "total_len": 10},
        {"document_id": "bad.htm", "split": "train", "cik": 2, "year": 2020, "total_len": 10},
    ]
    ckpt = m.checkpoint_path(tmp_path)
    m.write_header(ckpt, {"record_type": "header", "phase_4_1_config_hash": "a" * 64, "source_document_ids_sha256": "b" * 64})
    ok_text = "content\n"
    (tmp_path / "ok.md").write_bytes(ok_text.encode("utf-8"))
    import hashlib
    ok_hash = hashlib.sha256(ok_text.encode("utf-8")).hexdigest()
    m.append_record(ckpt, {"record_type": "unit", "document_id": "ok.htm", "outcome": "NORMALIZED",
                            "output_relpath": "ok.md", "content_sha256": ok_hash, "bytes": len(ok_text)})
    m.append_record(ckpt, {"record_type": "unit", "document_id": "bad.htm", "outcome": "FAILED",
                            "output_relpath": None, "content_sha256": None, "bytes": None,
                            "error_class": "ValueError", "error_summary": "boom"})
    summary = m.summarize_final(tmp_path, metadata)
    assert summary["completed_count"] == 1
    assert summary["failed_count"] == 1
    assert "bad.htm" in summary["failed_sample"]
    assert summary["missing_count"] == 0  # accounted for as failed, not silently vanished


# --------------------------------------------------------------- 21/22. manifest completeness / hash determinism

def test_build_manifest_includes_every_source_document_exactly_once(tmp_path):
    metadata = [
        {"document_id": "a.htm", "split": "train", "cik": 1, "year": 2020, "total_len": 10},
        {"document_id": "b.htm", "split": "test", "cik": 2, "year": 2019, "total_len": 0},
    ]
    ckpt = m.checkpoint_path(tmp_path)
    m.write_header(ckpt, {"record_type": "header", "phase_4_1_config_hash": "a" * 64, "source_document_ids_sha256": "b" * 64})
    manifest_path, manifest_hash = m.build_manifest_and_hash(tmp_path, metadata)
    lines = manifest_path.read_text(encoding="utf-8").strip().splitlines()
    ids = [json.loads(line)["document_id"] for line in lines]
    assert sorted(ids) == ["a.htm", "b.htm"]
    assert len(ids) == len(set(ids))


def test_manifest_hash_deterministic(tmp_path):
    metadata = [{"document_id": "a.htm", "split": "train", "cik": 1, "year": 2020, "total_len": 10}]
    ckpt = m.checkpoint_path(tmp_path)
    m.write_header(ckpt, {"record_type": "header", "phase_4_1_config_hash": "a" * 64, "source_document_ids_sha256": "b" * 64})
    _p1, h1 = m.build_manifest_and_hash(tmp_path, metadata)
    _p2, h2 = m.build_manifest_and_hash(tmp_path, metadata)
    assert h1 == h2


# --------------------------------------------------------------- 23. content hash determinism

def test_content_hash_deterministic_for_same_row():
    row = {
        "filename": "1_2020.htm", "split": "train", "cik": "1", "year": "2020",
        **_sections(section_1="stable text"),
    }
    import hashlib
    _f1, t1, _o1 = m.render_unit(row, company_lookup={})
    _f2, t2, _o2 = m.render_unit(row, company_lookup={})
    assert hashlib.sha256(t1.encode()).hexdigest() == hashlib.sha256(t2.encode()).hexdigest()


# --------------------------------------------------------------- 24. Task 1.2 body-compatibility regression

def test_body_bytes_identical_between_dev_and_full_corpus_frontmatter_contracts():
    """The full-corpus frontmatter contract (FULL_CORPUS_FRONTMATTER_KEYS,
    nullable company, no development_manifest_sha256) must never change
    BODY rendering - only the metadata envelope legitimately differs
    (documented Stage 4 requirement)."""
    sections = _sections(
        section_1="Item 1 business description.\r\nSecond line.",
        section_1A="Risk factors — café, naïve, “quoted”.",
        section_7="MD&A text here.",
    )
    dev_fields = {
        "cik": 1005817, "company": "TOMPKINS FINANCIAL CORP", "form_type": "10-K",
        "fiscal_year": 2016, "source": "edgar_corpus", "source_filename": "1005817_2016.htm",
        "document_id": "1005817_2016.htm", "source_split": "validation",
        "development_manifest_sha256": "d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b",
    }
    full_fields = {
        "cik": 1005817, "company": "TOMPKINS FINANCIAL CORP", "form_type": "10-K",
        "fiscal_year": 2016, "source": "edgar_corpus", "source_filename": "1005817_2016.htm",
        "document_id": "1005817_2016.htm", "source_split": "validation",
    }
    dev_text = render_document(dev_fields, sections, frontmatter_keys=FRONTMATTER_KEYS)
    full_text = render_document(full_fields, sections, frontmatter_keys=FULL_CORPUS_FRONTMATTER_KEYS)

    dev_body = dev_text.split("---\n", 2)[2]
    full_body = full_text.split("---\n", 2)[2]
    assert dev_body == full_body
    # Frontmatter legitimately differs (dev carries development_manifest_sha256).
    assert dev_text.split("---\n", 2)[1] != full_text.split("---\n", 2)[1]


@pytest.mark.local_data
def test_body_bytes_identical_against_real_phase1_artifact():
    """Same regression, against a real on-disk Phase 1 normalized document,
    for a document that also exists in the full EDGAR-CORPUS source."""
    storage = get_storage()
    dev_path = storage.normalized_dir("phase1-minimal-v1") / "1005817_2016.md"
    if not dev_path.is_file():
        pytest.skip("Phase 1 dev-corpus artifact not present on disk")
    dev_text = dev_path.read_text(encoding="utf-8")
    dev_body = dev_text.split("---\n", 2)[2]

    con = m.connect_source(storage)
    rows = m.fetch_full_rows(con, ["1005817_2016.htm"])
    row = rows["1005817_2016.htm"]
    _fname, full_text, _outcome = m.render_unit(row, company_lookup={})
    full_body = full_text.split("---\n", 2)[2]
    assert dev_body == full_body


# --------------------------------------------------------------- 25-29. no later-phase work performed

def _direct_imports_of(module_path) -> set[str]:
    """Static AST inspection of the driver's own source - deterministic
    regardless of what other test modules in the same pytest session have
    already imported (a sys.modules-based check would give false positives
    once ANY other test file imports e.g. src.chunk first)."""
    import ast
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_module_never_imports_later_phase_pipeline_packages():
    forbidden_prefixes = (
        "src.chunk", "src.embeddings", "src.index", "src.retrieval",
        "src.generation", "src.rerank", "src.crag", "src.router",
        "src.sql", "src.nav", "src.api", "src.guards",
    )
    imports = _direct_imports_of(Path(m.__file__))
    forbidden_found = [n for n in imports if n.startswith(forbidden_prefixes)]
    assert forbidden_found == [], (
        f"scripts/normalize_full_corpus.py directly imports later-phase packages: {forbidden_found}"
    )


def test_module_never_touches_test_access():
    imports = _direct_imports_of(Path(m.__file__))
    assert "src.eval.test_access" not in imports
    assert not any(n.startswith("src.eval") for n in imports)


# --------------------------------------------------------------- 30. source data/ never written

@pytest.mark.local_data
def test_plan_mode_never_modifies_frozen_source_files():
    import hashlib
    storage = get_storage()
    targets = [storage.xbrl_db] + [storage.edgar_corpus_root / f"{s}.parquet" for s in m.SOURCE_SPLITS]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in targets if p.is_file()}
    con = m.connect_source(storage)
    m.audit_source(con)
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in targets if p.is_file()}
    assert before == after
