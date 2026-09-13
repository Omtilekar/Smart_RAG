"""Task 2.9 - the canonical chunk metadata schema every future SEC
chunker/index/retrieval/evidence-labeling component must use.

This is the ONE authoritative schema definition (Section 8) - the
PyArrow schema, the documentation table in
`project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md`, and the tracked
`results/phase_2_9_chunk_metadata_schema.json` snapshot are all derived
from `CANONICAL_FIELDS` below, never maintained independently.

Task 2.9 freezes SCHEMA SEMANTICS (what a chunk record means). It does
NOT implement Task 2.10's config-hashing/artifact-versioning system -
`chunk_config_hash` is validated here only as an opaque, non-null,
SHA-256-shaped string identifying "how a chunk was generated"; Task 2.10
owns how that identity is computed/matched across artifacts.

Central invariant (Final Principle): same source + same chunking
semantics -> same `chunk_uid`; different chunking semantics -> different
`chunk_uid`. Missing metadata stays honestly `None` - this module never
fabricates an accession, a date, a SIC code, or a character offset.

Schema v2 (Task 4.2, 2026-09-13): `company` is now nullable. Task 4.1's
approved full-corpus normalization policy leaves `company` genuinely NULL
for 65.91% of EDGAR-CORPUS rows (no XBRL CIK->name match exists) - the
v1 schema's `company` non-nullable constraint was only ever satisfiable
because Task 1.1's 1,500-filing dev corpus was pre-filtered to the
XBRL-aligned population (100% company coverage there, by construction).
This is a schema-SEMANTICS change (a nullability rule changed), so
CHUNK_SCHEMA_VERSION increments 1 -> 2 per this module's own evolution
policy (project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md) - never a silent
reinterpretation. Historical v1 chunk_uids (the frozen 162,357-row Task
1.2/2.9 dev-corpus audit, and every Phase 3 ablation-table chunk built
from it) are unaffected: every one of those call sites pins
`chunk_schema_version=1` as its own literal, independent of this
module's "current" default, and none of them ever had a NULL `company`
value in the first place. No other field's nullability changed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Sequence

import pyarrow as pa

CHUNK_SCHEMA_VERSION = 2  # v1 -> v2 (Task 4.2): company became nullable

# Deliberately small (Section 21) - do not add chart/image/pdf/other
# without an actual current requirement.
CONTENT_TYPES: tuple[str, ...] = ("prose", "table", "table_summary")

# Deliberately SEC-only (Section 24) - MS MARCO stays a separate
# benchmark track and never enters this schema.
SOURCE_VALUES: tuple[str, ...] = ("edgar_corpus", "primary")

# Canonical hyphenated SEC accession format, used consistently
# throughout this project (e.g. "0000100122-24-000002").
ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")

# Project-wide convention (Task 1.9/2.1/2.3/2.4/2.8): a lowercase 64-hex-
# character SHA-256 digest.
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ChunkMetadataError(ValueError):
    """Raised for any violation of the canonical chunk schema - never
    silently coerced or repaired."""


# --------------------------------------------------------------- field specification

@dataclass(frozen=True)
class FieldSpec:
    name: str
    pa_type: pa.DataType
    nullable: bool
    description: str
    # Python-level type(s) accepted by validate_chunk_record for a
    # non-null value of this field (PyArrow types don't map 1:1 onto
    # plain-dict validation).
    py_types: tuple[type, ...]


CANONICAL_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("chunk_schema_version", pa.int32(), False,
              "Identifies what the chunk record's fields MEAN (this module's version) - distinct from chunk_config_hash, which identifies HOW the chunk was generated.",
              (int,)),
    FieldSpec("chunk_uid", pa.string(), False,
              "Globally unique, deterministic chunk identity across all supported SEC sources - SHA-256 over canonical JSON of {chunk_schema_version, source, document_id, chunk_config_hash, chunk_local_id}. Changes iff any of those five inputs changes.",
              (str,)),
    FieldSpec("chunk_local_id", pa.string(), False,
              "Deterministic identity of the chunk inside its source document, for one chunking configuration - computable from purely local information (no cross-document lookup).",
              (str,)),
    FieldSpec("document_id", pa.string(), False,
              "Canonical source-document identity. Source-specific format (see project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md) - `source` + `document_id` together unambiguously identify the source document.",
              (str,)),
    FieldSpec("accession", pa.string(), True,
              "SEC accession (hyphenated NNNNNNNNNN-NN-NNNNNN) where authoritatively known. NULL for EDGAR-CORPUS (no reliable accession linkage exists) - never fabricated from filename/CIK/year.",
              (str,)),
    FieldSpec("cik", pa.int64(), False,
              "SEC Central Index Key - canonical integer, never a zero-padded string.",
              (int,)),
    FieldSpec("company", pa.string(), True,
              "Display company name. Never used as identity (names change/vary) - identity is cik/document_id/accession. "
              "NULL (schema v2+) where no authoritative name source exists - e.g. an EDGAR-CORPUS CIK with no XBRL "
              "submissions match (Task 4.1's approved policy) - never fabricated/guessed.",
              (str,)),
    FieldSpec("form_type", pa.string(), False,
              "SEC filing type (e.g. \"10-K\") - never silently normalized from an amendment or other form.",
              (str,)),
    FieldSpec("fiscal_year", pa.int32(), False,
              "Fiscal year, never conflated with filing year.",
              (int,)),
    FieldSpec("period_end", pa.date32(), True,
              "Reporting-period end date, where authoritatively known (e.g. from a submission's `period` field). NULL, never a manufactured \"Dec 31 of fiscal_year\".",
              (str,)),
    FieldSpec("filed_date", pa.date32(), True,
              "Actual SEC filing date, where authoritatively known. NULL, never inferred from fiscal_year + an offset.",
              (str,)),
    FieldSpec("sic", pa.int32(), True,
              "SEC Standard Industrial Classification code, where available from frozen raw SEC metadata. NULL, never guessed from company name.",
              (int,)),
    FieldSpec("section_id", pa.string(), True,
              "Stable machine-readable section identity (e.g. \"item_7\"). NULL when a chunk spans/crosses sections or section identity is genuinely ambiguous - never the first heading seen.",
              (str,)),
    FieldSpec("section_title", pa.string(), True,
              "Human-readable section title, where confidently available. NULL rather than synthesized.",
              (str,)),
    FieldSpec("ordinal", pa.int32(), False,
              "Zero-based canonical chunk order within the document - never a Parquet/LanceDB physical row number.",
              (int,)),
    FieldSpec("char_start", pa.int64(), True,
              "Zero-based, half-open [char_start, char_end) start offset into the canonical document text consumed by the chunker. NULL (with char_end) when no defensible contiguous span exists.",
              (int,)),
    FieldSpec("char_end", pa.int64(), True,
              "Half-open interval end (exclusive). NULL (with char_start) when no defensible contiguous span exists - never an approximate/source-dependent offset.",
              (int,)),
    FieldSpec("content_type", pa.string(), False,
              "One of CONTENT_TYPES: prose | table | table_summary.",
              (str,)),
    FieldSpec("table_id", pa.string(), True,
              "Deterministic table identity (Task 2.8's table-identity contract, reused where available). Required when content_type is table/table_summary; NULL is normal for prose.",
              (str,)),
    FieldSpec("source", pa.string(), False,
              "One of SOURCE_VALUES: edgar_corpus | primary. MS MARCO is never a value here - it is a separate benchmark track.",
              (str,)),
    FieldSpec("text", pa.string(), False,
              "The actual retrieval text - never the embedding vector, never the full source document, never metadata appended into the string.",
              (str,)),
    FieldSpec("token_count", pa.int32(), False,
              "Token count per the chunking configuration's own tokenizer - never recomputed with an unrelated tokenizer during validation.",
              (int,)),
    FieldSpec("chunk_config_hash", pa.string(), False,
              "Opaque semantic identity of the chunking configuration (SHA-256 hex, this project's convention). Task 2.9 validates format/presence only - Task 2.10 owns how it is computed/matched across artifacts.",
              (str,)),
)

_FIELDS_BY_NAME: dict[str, FieldSpec] = {f.name: f for f in CANONICAL_FIELDS}


def canonical_pyarrow_schema() -> pa.Schema:
    return pa.schema([pa.field(f.name, f.pa_type, nullable=f.nullable) for f in CANONICAL_FIELDS])


# --------------------------------------------------------------- chunk_local_id / chunk_uid

def build_chunk_local_id(ordinal: int, section_id: str | None = None) -> str:
    """Deterministic, document-local chunk identity - needs no
    cross-document information. Deliberately NOT `{document_id}::chunk{ordinal}`
    (Section 12 - that embeds global information, defeating the point of
    a *local* identifier)."""
    if ordinal < 0:
        raise ChunkMetadataError(f"ordinal must be >= 0, got {ordinal}")
    if section_id:
        return f"{section_id}:chunk{ordinal:06d}"
    return f"chunk{ordinal:06d}"


def _chunk_uid_payload(*, chunk_schema_version: int, source: str, document_id: str,
                        chunk_config_hash: str, chunk_local_id: str) -> bytes:
    payload = {
        "chunk_schema_version": chunk_schema_version,
        "source": source,
        "document_id": document_id,
        "chunk_config_hash": chunk_config_hash,
        "chunk_local_id": chunk_local_id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_chunk_uid(*, chunk_schema_version: int, source: str, document_id: str,
                     chunk_config_hash: str, chunk_local_id: str) -> str:
    """Globally unique, deterministic - SHA-256 over canonical JSON of
    the five identity-bearing ingredients (Section 13). Never Python's
    built-in hash(), never a random UUID."""
    return hashlib.sha256(
        _chunk_uid_payload(
            chunk_schema_version=chunk_schema_version, source=source, document_id=document_id,
            chunk_config_hash=chunk_config_hash, chunk_local_id=chunk_local_id,
        )
    ).hexdigest()


def validate_chunk_uid(chunk_uid: str, *, chunk_schema_version: int, source: str, document_id: str,
                        chunk_config_hash: str, chunk_local_id: str) -> None:
    expected = build_chunk_uid(
        chunk_schema_version=chunk_schema_version, source=source, document_id=document_id,
        chunk_config_hash=chunk_config_hash, chunk_local_id=chunk_local_id,
    )
    if chunk_uid != expected:
        raise ChunkMetadataError(f"chunk_uid {chunk_uid!r} does not match its declared identity inputs (expected {expected!r})")


# --------------------------------------------------------------- accession / offsets

def validate_iso_date(value: str | None, field_name: str) -> None:
    """`period_end`/`filed_date` are carried as ISO "YYYY-MM-DD" strings
    at the plain-dict record level (converted to PyArrow date32 only at
    table-construction time). Rejects a malformed date string rather
    than silently accepting garbage."""
    if value is None:
        return
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ChunkMetadataError(f"{field_name} {value!r} is not a valid ISO YYYY-MM-DD date") from exc


def validate_accession(accession: str | None) -> None:
    if accession is None:
        return
    if not ACCESSION_RE.match(accession):
        raise ChunkMetadataError(f"malformed accession {accession!r} - expected NNNNNNNNNN-NN-NNNNNN")


def validate_offsets(char_start: int | None, char_end: int | None, *, source_text: str | None = None, chunk_text: str | None = None) -> None:
    """Half-open [char_start, char_end) contract (Section 16-18). Both
    None or both populated - never one-sided. If `source_text` and
    `chunk_text` are both given, verifies the round-trip slice exactly."""
    if (char_start is None) != (char_end is None):
        raise ChunkMetadataError(f"char_start/char_end must both be NULL or both populated, got start={char_start!r} end={char_end!r}")
    if char_start is None:
        return
    if char_start < 0:
        raise ChunkMetadataError(f"char_start must be >= 0, got {char_start}")
    if char_end <= char_start:
        raise ChunkMetadataError(f"char_end must be > char_start (half-open interval), got start={char_start} end={char_end}")
    if source_text is not None:
        if char_end > len(source_text):
            raise ChunkMetadataError(f"char_end {char_end} exceeds source text length {len(source_text)}")
        if chunk_text is not None and source_text[char_start:char_end] != chunk_text:
            raise ChunkMetadataError("source_text[char_start:char_end] does not match the supplied chunk_text - offsets do not round-trip")


# --------------------------------------------------------------- record/table validation

def validate_chunk_record(record: dict, *, verify_uid: bool = True) -> None:
    """Validates one chunk record (a plain dict) against every canonical
    field's type/nullability plus the cross-field invariants (Section
    40). Raises ChunkMetadataError with a specific, actionable message on
    the first violation found - never silently coerces or skips a
    malformed value. Unknown extra keys (source-specific extension
    metadata, Section 37) are permitted and ignored."""
    for field in CANONICAL_FIELDS:
        if field.name not in record:
            raise ChunkMetadataError(f"missing required field {field.name!r}")
        value = record[field.name]
        if value is None:
            if not field.nullable:
                raise ChunkMetadataError(f"field {field.name!r} is not nullable but got None")
            continue
        if not isinstance(value, field.py_types):
            raise ChunkMetadataError(f"field {field.name!r} expected type {field.py_types}, got {type(value)}")

    if record["ordinal"] < 0:
        raise ChunkMetadataError(f"ordinal must be >= 0, got {record['ordinal']}")
    if record["token_count"] <= 0:
        raise ChunkMetadataError(f"token_count must be > 0, got {record['token_count']}")
    if record["text"] == "":
        raise ChunkMetadataError("text must be non-empty")

    validate_offsets(record.get("char_start"), record.get("char_end"))
    validate_accession(record.get("accession"))
    validate_iso_date(record.get("period_end"), "period_end")
    validate_iso_date(record.get("filed_date"), "filed_date")

    if record["content_type"] not in CONTENT_TYPES:
        raise ChunkMetadataError(f"content_type {record['content_type']!r} not in {CONTENT_TYPES}")
    if record["content_type"] in ("table", "table_summary") and record.get("table_id") is None:
        raise ChunkMetadataError(f"content_type={record['content_type']!r} requires a non-null table_id")

    if record["source"] not in SOURCE_VALUES:
        raise ChunkMetadataError(f"source {record['source']!r} not in {SOURCE_VALUES}")

    if not SHA256_RE.match(record["chunk_config_hash"]):
        raise ChunkMetadataError(f"chunk_config_hash {record['chunk_config_hash']!r} is not a lowercase 64-hex-character SHA-256 digest")

    if verify_uid:
        validate_chunk_uid(
            record["chunk_uid"],
            chunk_schema_version=record["chunk_schema_version"], source=record["source"],
            document_id=record["document_id"], chunk_config_hash=record["chunk_config_hash"],
            chunk_local_id=record["chunk_local_id"],
        )


@dataclass(frozen=True)
class TableValidationResult:
    row_count: int
    unique_chunk_uids: int
    unique_local_ids_per_document_config: int
    field_coverage: dict  # field_name -> {"populated": int, "null": int, "population_pct": float}


def validate_chunk_table(records: Sequence[dict], *, verify_uid: bool = True) -> TableValidationResult:
    """Validates every record, then the table-wide invariants (Section
    40/49/50): global chunk_uid uniqueness, and (chunk_local_id,
    chunk_config_hash, document_id) uniqueness within each document.
    Accepts a sequence of plain dicts (a PyArrow table's
    `.to_pylist()`) rather than a `pa.Table` directly, so it works
    identically for real Parquet-backed tables and small synthetic
    fixtures."""
    seen_uids: dict[str, int] = {}
    seen_local: dict[tuple, int] = {}
    field_coverage = {f.name: {"populated": 0, "null": 0} for f in CANONICAL_FIELDS}

    for i, record in enumerate(records):
        validate_chunk_record(record, verify_uid=verify_uid)
        for f in CANONICAL_FIELDS:
            if record.get(f.name) is None:
                field_coverage[f.name]["null"] += 1
            else:
                field_coverage[f.name]["populated"] += 1

        uid = record["chunk_uid"]
        if uid in seen_uids:
            raise ChunkMetadataError(f"duplicate chunk_uid {uid!r} at rows {seen_uids[uid]} and {i}")
        seen_uids[uid] = i

        local_key = (record["document_id"], record["chunk_config_hash"], record["chunk_local_id"])
        if local_key in seen_local:
            raise ChunkMetadataError(f"duplicate (document_id, chunk_config_hash, chunk_local_id) {local_key!r} at rows {seen_local[local_key]} and {i}")
        seen_local[local_key] = i

    total = len(records)
    coverage_pct = {
        name: {**counts, "population_pct": round(100.0 * counts["populated"] / total, 2) if total else 0.0}
        for name, counts in field_coverage.items()
    }

    return TableValidationResult(
        row_count=total,
        unique_chunk_uids=len(seen_uids),
        unique_local_ids_per_document_config=len(seen_local),
        field_coverage=coverage_pct,
    )
