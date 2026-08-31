"""Task 2.2 - loader/validator for configs/eval_tags.yaml, the single
authoritative Phase 2 evaluation tag registry.

`src/eval/truth_contract.py`'s `eligible_facts()` consumes this registry
for per-tag `qtrs`/`unit`/`enabled` semantics - it does not maintain a
second, independently-decided mapping. This module owns:

- parsing and strict-validating `configs/eval_tags.yaml`,
- failing loudly (never silently skipping) on any malformed entry,
- a deterministic, timestamp-free semantic hash of the registry.

See `project_plan/PHASE2_TAG_REGISTRY.md` for the real-data evidence
behind every tag's frozen `qtrs`/`period_type`/`unit`/`enabled` values.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

REGISTRY_RELATIVE_PATH = Path("configs") / "eval_tags.yaml"


class _DuplicateKeyCheckingLoader(yaml.SafeLoader):
    """PyYAML's default SafeLoader silently keeps the last value when a
    YAML mapping repeats a key (e.g. two `Assets:` entries in the same
    file) - a copy-paste error would otherwise disappear without warning.
    This loader raises immediately instead."""


def _construct_mapping_no_duplicates(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key in YAML mapping: {key!r}", node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_DuplicateKeyCheckingLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping_no_duplicates,
)

# "For current annual 10-K evaluation: instant -> 0, annual duration -> 4."
# No other qtrs value is permitted without explicit roadmap justification -
# this project's truth contract never consumes 10-Q quarterly data.
PERIOD_TYPE_QTRS: dict[str, int] = {"instant": 0, "duration": 4}


class TagRegistryError(ValueError):
    """Raised for any malformed configs/eval_tags.yaml - missing/invalid
    field, duplicate tag, empty registry, unsupported schema version, or
    an internally inconsistent qtrs/period_type pair. Never raised for an
    ordinary "tag not supported" situation encountered by a caller asking
    the registry about a tag - that is TagRegistry.get()'s KeyError-style
    TagRegistryError, a separate, expected condition."""


@dataclass(frozen=True)
class TagSpec:
    tag: str
    enabled: bool
    period_type: str  # "instant" | "duration"
    qtrs: int
    unit: str
    category: str | None = None
    label: str | None = None
    reason: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class TagRegistry:
    version: int
    tags: dict[str, TagSpec]  # insertion order == YAML file order

    def supported_tags(self) -> list[str]:
        return [t for t, spec in self.tags.items() if spec.enabled]

    def excluded_tags(self) -> list[str]:
        return [t for t, spec in self.tags.items() if not spec.enabled]

    def get(self, tag: str) -> TagSpec:
        try:
            return self.tags[tag]
        except KeyError:
            raise TagRegistryError(
                f"unknown tag: {tag!r} - not present in the registry at all "
                f"(known tags: {sorted(self.tags)})"
            ) from None


def _validate_entry(tag: str, raw) -> TagSpec:
    if not isinstance(tag, str) or not tag.strip():
        raise TagRegistryError(f"invalid tag name: {tag!r}")
    if not isinstance(raw, dict):
        raise TagRegistryError(f"tag {tag!r}: entry must be a mapping, got {type(raw).__name__}")

    if "enabled" not in raw or not isinstance(raw["enabled"], bool):
        raise TagRegistryError(f"tag {tag!r}: 'enabled' must be an explicit boolean")
    enabled = raw["enabled"]

    period_type = raw.get("period_type")
    if period_type not in PERIOD_TYPE_QTRS:
        raise TagRegistryError(
            f"tag {tag!r}: 'period_type' must be one of {sorted(PERIOD_TYPE_QTRS)}, got {period_type!r}"
        )

    if "qtrs" not in raw or not isinstance(raw["qtrs"], int) or isinstance(raw["qtrs"], bool):
        raise TagRegistryError(f"tag {tag!r}: 'qtrs' must be an explicit integer")
    qtrs = raw["qtrs"]
    expected_qtrs = PERIOD_TYPE_QTRS[period_type]
    if qtrs != expected_qtrs:
        raise TagRegistryError(
            f"tag {tag!r}: qtrs={qtrs} is inconsistent with period_type={period_type!r} "
            f"(expected qtrs={expected_qtrs}) - arbitrary qtrs values are not permitted without "
            f"explicit roadmap justification"
        )

    unit = raw.get("unit")
    if not isinstance(unit, str) or not unit.strip():
        raise TagRegistryError(f"tag {tag!r}: 'unit' must be a non-empty string")

    return TagSpec(
        tag=tag, enabled=enabled, period_type=period_type, qtrs=qtrs, unit=unit,
        category=raw.get("category"), label=raw.get("label"),
        reason=raw.get("reason"), notes=raw.get("notes"),
    )


def parse_registry(raw: dict) -> TagRegistry:
    """Parses and validates an already-loaded YAML dict. Split from
    load_registry() so tests can exercise validation without a real file."""
    if not isinstance(raw, dict):
        raise TagRegistryError(f"registry root must be a mapping, got {type(raw).__name__}")

    if "version" not in raw or not isinstance(raw["version"], int) or isinstance(raw["version"], bool):
        raise TagRegistryError("registry must declare an explicit integer 'version'")
    version = raw["version"]
    if version != 1:
        raise TagRegistryError(f"unsupported schema version: {version} (only version 1 is known)")

    raw_tags = raw.get("tags")
    if not isinstance(raw_tags, dict) or not raw_tags:
        raise TagRegistryError("registry must contain a non-empty 'tags' mapping")

    # A Python dict cannot itself contain a duplicate key, so duplicate-tag
    # detection happens earlier, at YAML-parse time, in
    # _DuplicateKeyCheckingLoader - by the time `raw_tags` reaches this
    # point any duplicate has already raised.
    tags: dict[str, TagSpec] = {
        tag: _validate_entry(tag, entry) for tag, entry in raw_tags.items()
    }

    return TagRegistry(version=version, tags=tags)


def load_registry(path: Path | str | None = None) -> TagRegistry:
    """Loads and strictly validates configs/eval_tags.yaml. Raises
    TagRegistryError on any malformed configuration - never silently
    skips an invalid entry or accepts an inconsistent qtrs/period_type
    combination. `path` defaults to the repo's configs/eval_tags.yaml
    (resolved via src.storage, the existing Task 0.7 convention) - pass
    an explicit path only for tests."""
    if path is None:
        from src.storage import get_storage
        path = get_storage().repo_root / REGISTRY_RELATIVE_PATH
    path = Path(path)
    if not path.is_file():
        raise TagRegistryError(f"registry file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            raw = yaml.load(f, Loader=_DuplicateKeyCheckingLoader)
        except yaml.YAMLError as e:
            raise TagRegistryError(f"invalid YAML in {path}: {e}") from None

    return parse_registry(raw)


@lru_cache(maxsize=1)
def get_registry() -> TagRegistry:
    """Cached singleton, mirroring src.config.get_settings()/
    src.storage.get_storage()'s existing caching convention. Tests that
    need a different registry should call load_registry()/parse_registry()
    directly rather than mutating this cache."""
    return load_registry()


def compute_registry_hash(registry: TagRegistry) -> str:
    """Deterministic, timestamp-free SHA-256 over only the semantic
    fields (enabled/period_type/qtrs/unit per tag) - never changes
    because of comments, YAML formatting, key order, or a `label`/
    `reason`/`notes` edit in the source file."""
    payload = {
        "version": registry.version,
        "tags": {
            tag: {
                "enabled": spec.enabled,
                "period_type": spec.period_type,
                "qtrs": spec.qtrs,
                "unit": spec.unit,
            }
            for tag, spec in sorted(registry.tags.items())
        },
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
