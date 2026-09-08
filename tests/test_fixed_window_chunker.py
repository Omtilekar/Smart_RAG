"""Tests for src/chunk/fixed_window.py (pure, deterministic chunking logic)
and scripts/chunk_development_corpus.py's helper functions.

Deliberately does NOT load the real bge-small-en-v1.5 tokenizer or run the
full 1,500-document build against the frozen normalized corpus - that is
scripts/chunk_development_corpus.py's own real run (Task 1.3), not a unit
test. All tests here use small synthetic offset-mapping fixtures instead of
a live tokenizer, per Task 1.3 Step 33 ("do not rebuild the full corpus
inside every ordinary pytest run").
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

from src.chunk import fixed_window as fw  # noqa: E402
from src.normalize import edgar_markdown as em  # noqa: E402


def _load_orchestration_module():
    spec = importlib.util.spec_from_file_location(
        "chunk_development_corpus", REPO_ROOT / "scripts" / "chunk_development_corpus.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cdc = _load_orchestration_module()


# ---------------------------------------------------- compute_token_windows

def test_exact_full_window_single_chunk():
    windows = fw.compute_token_windows(512, window_size=512, stride=512)
    assert windows == [(0, 512)]


def test_multiple_full_windows_no_overlap():
    windows = fw.compute_token_windows(1024, window_size=512, stride=512)
    assert windows == [(0, 512), (512, 1024)]


def test_partial_final_window_kept():
    windows = fw.compute_token_windows(1000, window_size=512, stride=512)
    assert windows == [(0, 512), (512, 1000)]
    # partial window is 488 tokens, not dropped
    assert windows[-1][1] - windows[-1][0] == 488


def test_windows_cover_every_token_exactly_once_with_zero_overlap():
    windows = fw.compute_token_windows(1300, window_size=512, stride=512)
    covered = []
    for start, end in windows:
        covered.extend(range(start, end))
    assert covered == list(range(1300))  # exhaustive, no gaps, no overlap


def test_zero_tokens_yields_zero_windows():
    assert fw.compute_token_windows(0, window_size=512, stride=512) == []


def test_overlap_produces_repeated_token_coverage():
    # stride < window_size => overlap, exercised even though Phase 1 itself
    # uses stride=window_size=512 (zero overlap) - the function must still
    # behave correctly for a nonzero-overlap config if ever reused.
    windows = fw.compute_token_windows(20, window_size=10, stride=5)
    assert windows == [(0, 10), (5, 15), (10, 20)]


def test_invalid_window_size_raises():
    with pytest.raises(ValueError):
        fw.compute_token_windows(100, window_size=0, stride=512)


def test_invalid_stride_raises():
    with pytest.raises(ValueError):
        fw.compute_token_windows(100, window_size=512, stride=0)


def test_negative_num_tokens_raises():
    with pytest.raises(ValueError):
        fw.compute_token_windows(-1, window_size=512, stride=512)


# ---------------------------------------------------------- slice_chunk_text

def test_slice_chunk_text_exact_substring():
    body = "Item 1. Business\nSome long prose here."
    offsets = [(0, 4), (5, 6), (6, 7), (8, 16), (17, 21), (22, 26), (27, 32), (33, 37), (37, 38)]
    text = fw.slice_chunk_text(body, offsets, 0, 3)
    assert text == body[offsets[0][0]:offsets[2][1]]


def test_slice_chunk_text_preserves_unicode():
    body = "café naïve “curly quotes” ® symbol"
    offsets = [(0, 4), (5, 10), (11, 26), (27, 35)]
    text = fw.slice_chunk_text(body, offsets, 0, 4)
    assert text == body


def test_slice_chunk_text_invalid_range_raises():
    with pytest.raises(ValueError):
        fw.slice_chunk_text("text", [(0, 4)], 1, 1)


# ------------------------------------------------------------- make_chunk_id

def test_make_chunk_id_format():
    assert fw.make_chunk_id("1005817_2016.htm", 0) == "1005817_2016.htm::chunk0"
    assert fw.make_chunk_id("1005817_2016.htm", 7) == "1005817_2016.htm::chunk7"


def test_make_chunk_id_deterministic_and_unique():
    ids = [fw.make_chunk_id("doc.htm", i) for i in range(5)]
    assert len(set(ids)) == 5


# ------------------------------------------------------- parse_normalized_document

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


def test_parse_roundtrip_non_empty_body():
    body = "## Item 1\n\nSome business text.\n\n## Item 1A\n\nRisk factors here."
    doc = em.render_document(VALID_FIELDS, {"section_1": "Some business text.", "section_1A": "Risk factors here."})
    fields, parsed_body = fw.parse_normalized_document(doc)
    assert fields == VALID_FIELDS
    assert parsed_body == body


def test_parse_roundtrip_empty_body():
    doc = em.render_document(VALID_FIELDS, {col: "" for col in em.SECTION_COLUMNS})
    fields, parsed_body = fw.parse_normalized_document(doc)
    assert fields == VALID_FIELDS
    assert parsed_body == ""


def test_parse_preserves_unicode_and_multiline_body():
    text = "Line one.\nLine two with “curly quotes” and ® symbol.\nLine three."
    doc = em.render_document(VALID_FIELDS, {"section_1": text})
    _, parsed_body = fw.parse_normalized_document(doc)
    assert "## Item 1\n\n" + text == parsed_body


def test_parse_missing_open_delimiter_raises():
    with pytest.raises(ValueError):
        fw.parse_normalized_document("cik: 123\n---\nbody")


def test_parse_missing_close_delimiter_raises():
    with pytest.raises(ValueError):
        fw.parse_normalized_document("---\ncik: 123\nno closing delimiter here")


def test_parse_missing_required_field_raises():
    doc = em.render_document(VALID_FIELDS, {"section_1": "text"})
    broken = doc.replace('cik: 1005817\n', '')
    with pytest.raises(ValueError):
        fw.parse_normalized_document(broken)


# ----------------------------------------------------------- chunk config / hash

def _sample_config():
    return fw.build_chunk_config(
        normalizer_version="phase1-minimal-v1",
        normalization_build_sha256="a" * 64,
        development_manifest_sha256="b" * 64,
        tokenizer_repo="BAAI/bge-small-en-v1.5",
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    )


def test_chunk_config_hash_deterministic():
    config = _sample_config()
    assert fw.chunk_config_hash(config) == fw.chunk_config_hash(dict(config))


def test_chunk_config_hash_stable_under_key_reordering():
    config = _sample_config()
    reordered = dict(reversed(list(config.items())))
    assert fw.chunk_config_hash(config) == fw.chunk_config_hash(reordered)


def test_chunk_config_hash_changes_when_window_size_changes():
    a = _sample_config()
    b = _sample_config()
    b["window_size_tokens"] = 256
    assert fw.chunk_config_hash(a) != fw.chunk_config_hash(b)


def test_chunk_config_hash_changes_when_manifest_checksum_changes():
    a = _sample_config()
    b = _sample_config()
    b["development_manifest_sha256"] = "c" * 64
    assert fw.chunk_config_hash(a) != fw.chunk_config_hash(b)


def test_chunk_config_has_no_timestamp_field():
    config = _sample_config()
    assert not any("time" in k.lower() or "date" in k.lower() for k in config)


# -------------------------------------------- orchestration helper: normalization_build_sha256

def test_normalization_build_sha256_matches_manual_computation(tmp_path):
    (tmp_path / "a_2016.md").write_text("content a", encoding="utf-8")
    (tmp_path / "b_2017.md").write_text("content b", encoding="utf-8")
    result = cdc.normalization_build_sha256(tmp_path)

    import hashlib
    expected_lines = []
    for name, content in sorted([("a_2016.md", "content a"), ("b_2017.md", "content b")]):
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        expected_lines.append(f"{name}:{h}\n")
    expected = hashlib.sha256("".join(expected_lines).encode("utf-8")).hexdigest()
    assert result == expected


def test_normalization_build_sha256_independent_of_filesystem_iteration_order(tmp_path):
    (tmp_path / "z_2020.md").write_text("z content", encoding="utf-8")
    (tmp_path / "a_2016.md").write_text("a content", encoding="utf-8")
    result1 = cdc.normalization_build_sha256(tmp_path)
    result2 = cdc.normalization_build_sha256(tmp_path)
    assert result1 == result2


# ============================================================ Task 3.2 generalization

# -------------------------------------------------- generalized build_chunk_config

def _gen_config(**overrides):
    kwargs = dict(
        normalizer_version="phase1-minimal-v1",
        normalization_build_sha256="a" * 64,
        development_manifest_sha256="b" * 64,
        tokenizer_repo="BAAI/bge-small-en-v1.5",
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    )
    kwargs.update(overrides)
    return fw.build_chunk_config(**kwargs)


def test_generalized_config_defaults_match_frozen_phase1_values():
    config = _gen_config()
    assert config["window_size_tokens"] == 512
    assert config["overlap_tokens"] == 0
    assert config["stride_tokens"] == 512
    assert config["split_mode"] == "fixed"


def test_generalized_config_256_window():
    config = _gen_config(window_size_tokens=256)
    assert config["window_size_tokens"] == 256
    assert config["stride_tokens"] == 256


def test_generalized_config_1024_window():
    config = _gen_config(window_size_tokens=1024)
    assert config["window_size_tokens"] == 1024
    assert config["stride_tokens"] == 1024


def test_generalized_config_stride_derived_from_overlap():
    config = _gen_config(window_size_tokens=256, overlap_tokens=32)
    assert config["stride_tokens"] == 224


def test_generalized_config_section_aware_split_mode():
    config = _gen_config(split_mode="section_aware")
    assert config["split_mode"] == "section_aware"


def test_generalized_config_rejects_unknown_split_mode():
    with pytest.raises(ValueError):
        _gen_config(split_mode="semantic")


def test_generalized_config_rejects_overlap_ge_window():
    with pytest.raises(ValueError):
        _gen_config(window_size_tokens=256, overlap_tokens=256)


def test_generalized_config_rejects_negative_overlap():
    with pytest.raises(ValueError):
        _gen_config(overlap_tokens=-1)


def test_generalized_config_rejects_nonpositive_window():
    with pytest.raises(ValueError):
        _gen_config(window_size_tokens=0)


def test_hash_changes_with_window_size():
    a = fw.chunk_config_hash(_gen_config(window_size_tokens=256))
    b = fw.chunk_config_hash(_gen_config(window_size_tokens=512))
    assert a != b


def test_hash_changes_with_overlap():
    a = fw.chunk_config_hash(_gen_config(window_size_tokens=256, overlap_tokens=0))
    b = fw.chunk_config_hash(_gen_config(window_size_tokens=256, overlap_tokens=32))
    assert a != b


def test_hash_changes_with_split_mode():
    a = fw.chunk_config_hash(_gen_config(split_mode="fixed"))
    b = fw.chunk_config_hash(_gen_config(split_mode="section_aware"))
    assert a != b


def test_default_call_still_deterministic_and_matches_original_shape():
    # Baseline 512/0 output compatibility regression (Stage 10 #16): the
    # generalized function called with no window/overlap/split_mode
    # arguments reproduces the exact Phase 1 semantic values.
    config = _gen_config()
    assert config["window_size_tokens"] == fw.WINDOW_SIZE_TOKENS
    assert config["overlap_tokens"] == 0
    assert config["stride_tokens"] == fw.STRIDE_TOKENS


# ------------------------------------------------------- overlap/stride window coverage

def test_no_token_gaps_for_overlap_zero():
    windows = fw.compute_token_windows(2000, window_size=256, stride=256)
    covered = []
    for start, end in windows:
        covered.extend(range(start, end))
    assert covered == list(range(2000))


def test_expected_token_overlap_for_nonzero_overlap():
    # window=256, overlap=32 => stride=224
    windows = fw.compute_token_windows(1000, window_size=256, stride=224)
    for (s0, e0), (s1, e1) in zip(windows, windows[1:]):
        assert s1 < e0  # consecutive windows overlap
        assert (e0 - s1) == 32  # exact overlap amount matches config


def test_no_duplicate_final_window():
    windows = fw.compute_token_windows(600, window_size=256, stride=224)
    assert len(windows) == len(set(windows))
    # last window's end is exactly num_tokens, and no earlier window repeats it
    assert windows[-1][1] == 600
    assert windows.count(windows[-1]) == 1


def test_partial_final_window_retained_with_overlap():
    windows = fw.compute_token_windows(500, window_size=256, stride=224)
    assert windows[-1][1] == 500
    assert (windows[-1][1] - windows[-1][0]) < 256


# ---------------------------------------------------------- section splitting

def _section_body():
    return em.render_body({
        "section_1": "Business overview text.",
        "section_1A": "Risk factors text.",
        "section_7": "MD&A discussion text.",
    })


def test_section_label_to_id():
    assert fw.section_label_to_id("Item 1") == "item_1"
    assert fw.section_label_to_id("Item 1A") == "item_1a"
    assert fw.section_label_to_id("Item 7") == "item_7"


def test_split_body_into_sections_count_and_order():
    body = _section_body()
    spans = fw.split_body_into_sections(body)
    ids = [s[0] for s in spans]
    assert ids == ["item_1", "item_1a", "item_7"]


def test_split_body_into_sections_titles():
    body = _section_body()
    spans = fw.split_body_into_sections(body)
    titles = [s[1] for s in spans]
    assert titles == ["Item 1", "Item 1A", "Item 7"]


def test_split_body_into_sections_never_crosses_boundary():
    body = _section_body()
    spans = fw.split_body_into_sections(body)
    for section_id, title, start, end in spans:
        span_text = body[start:end]
        assert span_text.startswith(f"## {title}")
        # no other section's heading LINE appears inside this span (exact
        # line match - "## Item 1" is a substring of "## Item 1A", which
        # is not a boundary violation)
        other_heading_lines = {f"## {t}" for (_, t, _, _) in spans if t != title}
        span_lines = set(span_text.splitlines())
        assert not (other_heading_lines & span_lines)


def test_split_body_into_sections_covers_full_body_no_gaps():
    body = _section_body()
    spans = fw.split_body_into_sections(body)
    reconstructed = "".join(body[start:end] for _, _, start, end in spans)
    assert reconstructed == body


def test_split_body_into_sections_empty_body_yields_no_sections():
    assert fw.split_body_into_sections("") == []


def test_split_body_into_sections_single_section():
    body = em.render_body({"section_1": "Only one section here."})
    spans = fw.split_body_into_sections(body)
    assert len(spans) == 1
    assert spans[0][0] == "item_1"
    assert spans[0][2] == 0
    assert spans[0][3] == len(body)


def test_split_body_into_sections_malformed_body_raises():
    with pytest.raises(ValueError):
        fw.split_body_into_sections("plain prose with no heading at all")


def test_split_body_into_sections_no_source_section_disappears():
    body = em.render_body({
        "section_1": "A",
        "section_2": "B",
        "section_9A": "C",
    })
    spans = fw.split_body_into_sections(body)
    assert {s[0] for s in spans} == {"item_1", "item_2", "item_9a"}
