"""Task 2.2 - tests for src/eval/tag_registry.py.

Portable tests use temp YAML files (pytest's tmp_path) plus in-memory
parse_registry() calls - no dependency on the real configs/eval_tags.yaml
except where explicitly noted (those checks are still portable: it's a
small tracked config file, not frozen local data).
"""

from __future__ import annotations

import pytest
import yaml

from src.eval.tag_registry import (
    TagRegistryError,
    load_registry,
    parse_registry,
    compute_registry_hash,
    get_registry,
)

MINIMAL_VALID = {
    "version": 1,
    "tags": {
        "Assets": {"enabled": True, "period_type": "instant", "qtrs": 0, "unit": "USD"},
        "Revenues": {"enabled": True, "period_type": "duration", "qtrs": 4, "unit": "USD"},
    },
}


def _write_yaml(tmp_path, data) -> str:
    path = tmp_path / "eval_tags.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------- config loading

def test_valid_registry_loads(tmp_path):
    path = _write_yaml(tmp_path, MINIMAL_VALID)
    reg = load_registry(path)
    assert reg.version == 1
    assert set(reg.supported_tags()) == {"Assets", "Revenues"}


def test_missing_file_fails_clearly(tmp_path):
    with pytest.raises(TagRegistryError):
        load_registry(tmp_path / "does_not_exist.yaml")


def test_invalid_yaml_fails_clearly(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("tags: [this is not: valid: yaml: at all:", encoding="utf-8")
    with pytest.raises(TagRegistryError):
        load_registry(str(path))


def test_empty_registry_rejected():
    with pytest.raises(TagRegistryError):
        parse_registry({"version": 1, "tags": {}})


def test_missing_tags_key_rejected():
    with pytest.raises(TagRegistryError):
        parse_registry({"version": 1})


def test_root_not_a_mapping_rejected():
    with pytest.raises(TagRegistryError):
        parse_registry(["not", "a", "mapping"])


def test_missing_version_rejected():
    with pytest.raises(TagRegistryError):
        parse_registry({"tags": MINIMAL_VALID["tags"]})


def test_unsupported_schema_version_rejected():
    with pytest.raises(TagRegistryError):
        parse_registry({"version": 999, "tags": MINIMAL_VALID["tags"]})


# ------------------------------------------------------------------------ schema

def test_duplicate_tag_rejected(tmp_path):
    # Plain PyYAML (yaml.safe_load) silently keeps the LAST value when a
    # mapping key repeats - load_registry() uses a duplicate-key-checking
    # loader specifically so a copy-pasted "Assets:" block doesn't silently
    # disappear. Written as raw text since a Python dict literal can't
    # itself contain a duplicate key.
    path = tmp_path / "dup.yaml"
    path.write_text(
        "version: 1\n"
        "tags:\n"
        "  Assets:\n"
        "    enabled: true\n"
        "    period_type: instant\n"
        "    qtrs: 0\n"
        "    unit: USD\n"
        "  Assets:\n"
        "    enabled: true\n"
        "    period_type: instant\n"
        "    qtrs: 0\n"
        "    unit: CAD\n",
        encoding="utf-8",
    )
    with pytest.raises(TagRegistryError):
        load_registry(str(path))


def test_missing_qtrs_rejected():
    bad = {"version": 1, "tags": {"Assets": {"enabled": True, "period_type": "instant", "unit": "USD"}}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_invalid_qtrs_type_rejected():
    bad = {"version": 1, "tags": {"Assets": {"enabled": True, "period_type": "instant", "qtrs": "zero", "unit": "USD"}}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_qtrs_inconsistent_with_period_type_rejected():
    bad = {"version": 1, "tags": {"Assets": {"enabled": True, "period_type": "instant", "qtrs": 4, "unit": "USD"}}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_arbitrary_qtrs_value_rejected():
    bad = {"version": 1, "tags": {"Revenues": {"enabled": True, "period_type": "duration", "qtrs": 2, "unit": "USD"}}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_missing_unit_rejected():
    bad = {"version": 1, "tags": {"Assets": {"enabled": True, "period_type": "instant", "qtrs": 0}}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_empty_unit_rejected():
    bad = {"version": 1, "tags": {"Assets": {"enabled": True, "period_type": "instant", "qtrs": 0, "unit": ""}}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_invalid_period_type_rejected():
    bad = {"version": 1, "tags": {"Assets": {"enabled": True, "period_type": "sometimes", "qtrs": 0, "unit": "USD"}}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_missing_enabled_rejected():
    bad = {"version": 1, "tags": {"Assets": {"period_type": "instant", "qtrs": 0, "unit": "USD"}}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_invalid_enabled_value_rejected():
    bad = {"version": 1, "tags": {"Assets": {"enabled": "yes", "period_type": "instant", "qtrs": 0, "unit": "USD"}}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_entry_not_a_mapping_rejected():
    bad = {"version": 1, "tags": {"Assets": "not a mapping"}}
    with pytest.raises(TagRegistryError):
        parse_registry(bad)


def test_invalid_entries_never_silently_skipped():
    """A registry with one valid and one invalid tag must raise entirely -
    never silently drop the bad entry and load only the good one."""
    mixed = {
        "version": 1,
        "tags": {
            "Assets": {"enabled": True, "period_type": "instant", "qtrs": 0, "unit": "USD"},
            "BadTag": {"enabled": True, "period_type": "instant", "qtrs": 4, "unit": "USD"},
        },
    }
    with pytest.raises(TagRegistryError):
        parse_registry(mixed)


# ---------------------------------------------------------------- semantic consistency

def test_disabled_tag_excluded_from_supported():
    data = {
        "version": 1,
        "tags": {
            "Assets": {"enabled": True, "period_type": "instant", "qtrs": 0, "unit": "USD"},
            "SomeExcludedTag": {"enabled": False, "period_type": "duration", "qtrs": 4, "unit": "USD"},
        },
    }
    reg = parse_registry(data)
    assert reg.supported_tags() == ["Assets"]
    assert reg.excluded_tags() == ["SomeExcludedTag"]


def test_get_unknown_tag_raises():
    reg = parse_registry(MINIMAL_VALID)
    with pytest.raises(TagRegistryError):
        reg.get("NotInRegistry")


def test_instant_maps_to_qtrs_0():
    reg = parse_registry(MINIMAL_VALID)
    assert reg.get("Assets").qtrs == 0


def test_duration_maps_to_qtrs_4():
    reg = parse_registry(MINIMAL_VALID)
    assert reg.get("Revenues").qtrs == 4


def test_every_supported_tag_has_explicit_unit():
    reg = get_registry()
    for tag in reg.supported_tags():
        assert reg.get(tag).unit


# --------------------------------------------------------------------- determinism

def test_same_registry_same_hash():
    reg1 = parse_registry(MINIMAL_VALID)
    reg2 = parse_registry(MINIMAL_VALID)
    assert compute_registry_hash(reg1) == compute_registry_hash(reg2)


def test_hash_is_64_hex_chars():
    h = compute_registry_hash(parse_registry(MINIMAL_VALID))
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_comment_and_key_order_do_not_affect_hash(tmp_path):
    a = tmp_path / "a.yaml"
    a.write_text(
        "version: 1\ntags:\n  Assets:\n    enabled: true\n    period_type: instant\n    qtrs: 0\n    unit: USD\n",
        encoding="utf-8",
    )
    b = tmp_path / "b.yaml"
    b.write_text(
        "# a comment\nversion: 1\ntags:\n  Assets:\n    unit: USD\n    qtrs: 0\n    period_type: instant\n    enabled: true\n",
        encoding="utf-8",
    )
    h_a = compute_registry_hash(load_registry(str(a)))
    h_b = compute_registry_hash(load_registry(str(b)))
    assert h_a == h_b


def test_label_or_notes_change_does_not_affect_hash():
    with_notes = dict(MINIMAL_VALID)
    with_notes["tags"] = dict(MINIMAL_VALID["tags"])
    with_notes["tags"]["Assets"] = {**MINIMAL_VALID["tags"]["Assets"], "label": "Total assets", "notes": "some note"}
    assert compute_registry_hash(parse_registry(MINIMAL_VALID)) == compute_registry_hash(parse_registry(with_notes))


def test_semantic_change_changes_hash():
    changed = {
        "version": 1,
        "tags": {
            "Assets": {"enabled": False, "period_type": "instant", "qtrs": 0, "unit": "USD"},
            "Revenues": {"enabled": True, "period_type": "duration", "qtrs": 4, "unit": "USD"},
        },
    }
    h1 = compute_registry_hash(parse_registry(MINIMAL_VALID))
    h2 = compute_registry_hash(parse_registry(changed))
    assert h1 != h2


def test_tag_set_change_changes_hash():
    fewer = {"version": 1, "tags": {"Assets": MINIMAL_VALID["tags"]["Assets"]}}
    h1 = compute_registry_hash(parse_registry(MINIMAL_VALID))
    h2 = compute_registry_hash(parse_registry(fewer))
    assert h1 != h2


# ------------------------------------------------------------- real frozen registry

def test_real_registry_has_15_candidates_all_resolved():
    reg = get_registry()
    assert len(reg.tags) == 15
    assert len(reg.supported_tags()) + len(reg.excluded_tags()) == 15


def test_real_registry_no_unresolved_status_values():
    reg = get_registry()
    for spec in reg.tags.values():
        assert isinstance(spec.enabled, bool)
        assert spec.reason is not None and spec.reason.strip()
        lowered = (spec.reason or "").lower()
        for banned in ("todo", "maybe", "probably", "unresolved"):
            assert banned not in lowered


def test_real_registry_get_cached_singleton_stable():
    assert get_registry() is get_registry()
