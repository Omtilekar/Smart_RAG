"""Tests for src/normalize/edgar_markdown.py (pure rendering logic) and the
deterministic helpers in scripts/normalize_development_corpus.py.

Deliberately does NOT run the real 1,500-document build against the 5.77 GB
EDGAR-CORPUS parquet - that is scripts/normalize_development_corpus.py's own
real run (Task 1.2 Step 35), not a unit test. Only pure, cheap logic is
tested here with small synthetic fixtures, per Task 1.2 Step 32.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

from src.normalize import edgar_markdown as em  # noqa: E402


def _load_orchestration_module():
    spec = importlib.util.spec_from_file_location(
        "normalize_development_corpus", REPO_ROOT / "scripts" / "normalize_development_corpus.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ndc = _load_orchestration_module()


# ---------------------------------------------------- section ordering

def test_section_columns_are_natural_sec_item_order():
    assert em.SECTION_COLUMNS[:5] == ("section_1", "section_1A", "section_1B", "section_2", "section_3")
    assert em.SECTION_COLUMNS[-1] == "section_15"


def test_section_column_to_item_label():
    assert em.section_column_to_item_label("section_1") == "Item 1"
    assert em.section_column_to_item_label("section_7A") == "Item 7A"
    assert em.section_column_to_item_label("section_15") == "Item 15"


def test_section_column_to_item_label_rejects_non_section_column():
    with pytest.raises(ValueError):
        em.section_column_to_item_label("cik")


# ---------------------------------------------------- empty-section omission

def test_render_body_omits_null_sections():
    body = em.render_body({"section_1": "Business text.", "section_1A": None})
    assert "## Item 1\n\nBusiness text." in body
    assert "Item 1A" not in body


def test_render_body_omits_empty_and_whitespace_only_sections():
    body = em.render_body({"section_1": "", "section_1A": "   \n\t  ", "section_2": "Real text"})
    assert "Item 1" not in body
    assert "Item 1A" not in body
    assert "## Item 2\n\nReal text" in body


def test_render_body_all_empty_yields_empty_string():
    body = em.render_body({col: "" for col in em.SECTION_COLUMNS})
    assert body == ""


def test_render_body_preserves_section_order_regardless_of_dict_order():
    sections = {"section_7A": "Later item.", "section_1": "First item."}
    body = em.render_body(sections)
    assert body.index("Item 1") < body.index("Item 7A")


# ---------------------------------------------------- multiline/Unicode/CRLF

def test_normalize_newlines_converts_crlf_and_cr():
    assert em.normalize_newlines("a\r\nb\rc\n") == "a\nb\nc\n"


def test_render_body_preserves_multiline_and_unicode_text():
    text = "Line one.\nLine two with “curly quotes” and ® symbol."
    body = em.render_body({"section_1": text})
    assert "Line one.\nLine two" in body
    assert "“curly quotes”" in body
    assert "®" in body


def test_render_body_strips_leading_trailing_whitespace_per_section():
    body = em.render_body({"section_1": "  \n  Text with padding.  \n  "})
    assert body == "## Item 1\n\nText with padding."


def test_render_body_normalizes_crlf_within_section_text():
    body = em.render_body({"section_1": "Line one.\r\nLine two.\r\n"})
    assert "\r" not in body
    assert "Line one.\nLine two." in body


# ---------------------------------------------------- frontmatter

VALID_FIELDS = {
    "cik": 1005817,
    "company": "TOMPKINS FINANCIAL CORP",
    "form_type": "10-K",
    "fiscal_year": 2016,
    "source": "edgar_corpus",
    "source_filename": "1005817_2016.htm",
    "document_id": "1005817_2016.htm",
    "source_split": "validation",
    "development_manifest_sha256": "d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b",
}


def test_render_frontmatter_has_delimiters():
    fm = em.render_frontmatter(VALID_FIELDS)
    assert fm.startswith("---\n")
    assert fm.endswith("\n---")


def test_render_frontmatter_integers_unquoted():
    fm = em.render_frontmatter(VALID_FIELDS)
    assert "cik: 1005817\n" in fm
    assert "fiscal_year: 2016\n" in fm


def test_render_frontmatter_strings_quoted():
    fm = em.render_frontmatter(VALID_FIELDS)
    assert 'company: "TOMPKINS FINANCIAL CORP"' in fm
    assert 'form_type: "10-K"' in fm


def test_render_frontmatter_safely_escapes_quotes_and_colons_and_hashes():
    fields = dict(VALID_FIELDS)
    fields["company"] = 'Weird: "Quoted" # Corp\nSecond line'
    fm = em.render_frontmatter(fields)
    # Must remain a single valid line (JSON string escaping), not break YAML
    company_line = next(line for line in fm.splitlines() if line.startswith("company:"))
    import json as _json
    value = _json.loads(company_line[len("company: "):])
    assert value == 'Weird: "Quoted" # Corp\nSecond line'


def test_render_frontmatter_missing_field_raises():
    incomplete = {k: v for k, v in VALID_FIELDS.items() if k != "cik"}
    with pytest.raises(ValueError):
        em.render_frontmatter(incomplete)


def test_render_frontmatter_key_order_is_fixed_regardless_of_input_order():
    reordered = dict(reversed(list(VALID_FIELDS.items())))
    fm_a = em.render_frontmatter(VALID_FIELDS)
    fm_b = em.render_frontmatter(reordered)
    assert fm_a == fm_b


# ---------------------------------------------------- full document render

def test_render_document_ends_with_exactly_one_newline():
    doc = em.render_document(VALID_FIELDS, {"section_1": "Text."})
    assert doc.endswith("\n")
    assert not doc.endswith("\n\n")


def test_render_document_empty_body_still_has_valid_frontmatter():
    doc = em.render_document(VALID_FIELDS, {col: "" for col in em.SECTION_COLUMNS})
    assert doc.startswith("---\n")
    assert "cik: 1005817" in doc
    body_after_frontmatter = doc.split("---\n", 2)[2]
    assert body_after_frontmatter.strip() == ""


def test_render_document_is_deterministic():
    a = em.render_document(VALID_FIELDS, {"section_1": "Text."})
    b = em.render_document(dict(VALID_FIELDS), {"section_1": "Text."})
    assert a == b


def test_count_item_headings():
    doc = em.render_document(VALID_FIELDS, {"section_1": "A", "section_1A": "B", "section_7": "C"})
    assert em.count_item_headings(doc) == 3


def test_count_item_headings_zero_for_empty_body():
    doc = em.render_document(VALID_FIELDS, {col: "" for col in em.SECTION_COLUMNS})
    assert em.count_item_headings(doc) == 0


# ---------------------------------------------------- output filename mapping

def test_output_filename_replaces_htm_extension():
    assert em.output_filename("1005817_2016.htm") == "1005817_2016.md"


def test_output_filename_replaces_txt_extension():
    assert em.output_filename("92116_1993.txt") == "92116_1993.md"


def test_output_filename_rejects_no_extension():
    with pytest.raises(ValueError):
        em.output_filename("no_extension")


def test_output_filename_deterministic_unique_mapping():
    ids = ["1005817_2016.htm", "1010086_2016.htm", "92116_1993.txt"]
    mapped = [em.output_filename(i) for i in ids]
    assert len(set(mapped)) == len(mapped)


# ---------------------------------------------------- normalization_build_sha256

def test_normalization_build_sha256_deterministic():
    rendered = {"a_2016.md": "content a", "b_2017.md": "content b"}
    assert ndc.normalization_build_sha256(rendered) == ndc.normalization_build_sha256(dict(rendered))


def test_normalization_build_sha256_independent_of_dict_insertion_order():
    a = {"a_2016.md": "content a", "b_2017.md": "content b"}
    b = {"b_2017.md": "content b", "a_2016.md": "content a"}
    assert ndc.normalization_build_sha256(a) == ndc.normalization_build_sha256(b)


def test_normalization_build_sha256_changes_when_content_changes():
    a = {"a_2016.md": "content a"}
    b = {"a_2016.md": "content a (edited)"}
    assert ndc.normalization_build_sha256(a) != ndc.normalization_build_sha256(b)


def test_normalization_build_sha256_changes_when_filename_changes():
    a = {"a_2016.md": "same content"}
    b = {"a_2017.md": "same content"}
    assert ndc.normalization_build_sha256(a) != ndc.normalization_build_sha256(b)
