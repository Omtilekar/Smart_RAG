"""Task 2.9 - tests for the canonical chunk metadata schema."""

from __future__ import annotations

import copy
import hashlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.chunk import metadata_schema as ms

VALID_HASH_A = "a" * 64
VALID_HASH_B = "b" * 64


def make_record(**overrides) -> dict:
    record = {
        "chunk_schema_version": ms.CHUNK_SCHEMA_VERSION,
        "chunk_local_id": "chunk000000",
        "document_id": "edgar_corpus:doc-1",
        "accession": None,
        "cik": 100122,
        "company": "Acme Corp",
        "form_type": "10-K",
        "fiscal_year": 2023,
        "period_end": None,
        "filed_date": None,
        "sic": None,
        "section_id": None,
        "section_title": None,
        "ordinal": 0,
        "char_start": None,
        "char_end": None,
        "content_type": "prose",
        "table_id": None,
        "source": "edgar_corpus",
        "text": "Some chunk text.",
        "token_count": 4,
        "chunk_config_hash": VALID_HASH_A,
    }
    record.update(overrides)
    if "chunk_uid" not in record:
        record["chunk_uid"] = ms.build_chunk_uid(
            chunk_schema_version=record["chunk_schema_version"], source=record["source"],
            document_id=record["document_id"], chunk_config_hash=record["chunk_config_hash"],
            chunk_local_id=record["chunk_local_id"],
        )
    return record


# --------------------------------------------------------------- canonical schema shape

class TestCanonicalSchema:
    def test_field_count(self):
        assert len(ms.CANONICAL_FIELDS) == 23

    def test_no_duplicate_field_names(self):
        names = [f.name for f in ms.CANONICAL_FIELDS]
        assert len(names) == len(set(names))

    def test_pyarrow_schema_matches_field_specs(self):
        schema = ms.canonical_pyarrow_schema()
        assert schema.names == [f.name for f in ms.CANONICAL_FIELDS]
        for f in ms.CANONICAL_FIELDS:
            pa_field = schema.field(f.name)
            assert pa_field.type == f.pa_type
            assert pa_field.nullable == f.nullable

    @pytest.mark.parametrize("name,nullable", [
        ("chunk_schema_version", False), ("chunk_uid", False), ("chunk_local_id", False),
        ("document_id", False), ("accession", True), ("cik", False), ("company", False),
        ("form_type", False), ("fiscal_year", False), ("period_end", True), ("filed_date", True),
        ("sic", True), ("section_id", True), ("section_title", True), ("ordinal", False),
        ("char_start", True), ("char_end", True), ("content_type", False), ("table_id", True),
        ("source", False), ("text", False), ("token_count", False), ("chunk_config_hash", False),
    ])
    def test_nullability_contract(self, name, nullable):
        field = next(f for f in ms.CANONICAL_FIELDS if f.name == name)
        assert field.nullable is nullable

    def test_content_types_frozen(self):
        assert ms.CONTENT_TYPES == ("prose", "table", "table_summary")

    def test_source_values_frozen(self):
        assert ms.SOURCE_VALUES == ("edgar_corpus", "primary")

    def test_msmarco_not_a_source_value(self):
        assert "msmarco" not in ms.SOURCE_VALUES
        assert "msmarco-dev-small-v1" not in ms.SOURCE_VALUES


# --------------------------------------------------------------- chunk_local_id

class TestChunkLocalId:
    def test_basic_format(self):
        assert ms.build_chunk_local_id(0) == "chunk000000"
        assert ms.build_chunk_local_id(7) == "chunk000007"
        assert ms.build_chunk_local_id(123456) == "chunk123456"

    def test_section_prefixed_format(self):
        assert ms.build_chunk_local_id(3, section_id="item_7") == "item_7:chunk000003"

    def test_no_section_id_omits_prefix(self):
        assert ms.build_chunk_local_id(3, section_id=None) == "chunk000003"
        assert ms.build_chunk_local_id(3, section_id="") == "chunk000003"

    def test_negative_ordinal_rejected(self):
        with pytest.raises(ms.ChunkMetadataError):
            ms.build_chunk_local_id(-1)

    def test_deterministic(self):
        assert ms.build_chunk_local_id(5, section_id="x") == ms.build_chunk_local_id(5, section_id="x")

    def test_is_document_local_not_global(self):
        # Section 12: must NOT embed document_id (Phase 1's pattern did)
        local_id = ms.build_chunk_local_id(0)
        assert "document_id" not in local_id
        assert "::" not in local_id


# --------------------------------------------------------------- chunk_uid

class TestChunkUid:
    def _uid(self, **kw):
        base = dict(chunk_schema_version=1, source="edgar_corpus", document_id="doc-1",
                    chunk_config_hash=VALID_HASH_A, chunk_local_id="chunk000000")
        base.update(kw)
        return ms.build_chunk_uid(**base)

    def test_is_64_hex_sha256(self):
        uid = self._uid()
        assert len(uid) == 64
        assert ms.SHA256_RE.match(uid)

    def test_deterministic(self):
        assert self._uid() == self._uid()

    def test_never_python_hash_builtin(self):
        # A real SHA-256 is stable across process restarts; Python's
        # hash() of a str is salted per-process and would differ here
        # only if PYTHONHASHSEED varies - assert it matches a
        # hand-computed digest instead, which pins the real algorithm.
        import hashlib as _h
        import json as _j
        payload = _j.dumps({
            "chunk_schema_version": 1, "source": "edgar_corpus", "document_id": "doc-1",
            "chunk_config_hash": VALID_HASH_A, "chunk_local_id": "chunk000000",
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        assert self._uid() == _h.sha256(payload).hexdigest()

    def test_sensitive_to_schema_version(self):
        assert self._uid(chunk_schema_version=1) != self._uid(chunk_schema_version=2)

    def test_sensitive_to_source(self):
        assert self._uid(source="edgar_corpus") != self._uid(source="primary")

    def test_sensitive_to_document_id(self):
        assert self._uid(document_id="doc-1") != self._uid(document_id="doc-2")

    def test_sensitive_to_config_hash(self):
        assert self._uid(chunk_config_hash=VALID_HASH_A) != self._uid(chunk_config_hash=VALID_HASH_B)

    def test_sensitive_to_local_id(self):
        assert self._uid(chunk_local_id="chunk000000") != self._uid(chunk_local_id="chunk000001")

    def test_cross_source_isolation_same_document_id(self):
        # Section 51: the same document_id string reused across two
        # different sources must never collide.
        assert self._uid(source="edgar_corpus", document_id="X") != self._uid(source="primary", document_id="X")

    def test_validate_chunk_uid_accepts_matching(self):
        uid = self._uid()
        ms.validate_chunk_uid(uid, chunk_schema_version=1, source="edgar_corpus", document_id="doc-1",
                               chunk_config_hash=VALID_HASH_A, chunk_local_id="chunk000000")

    def test_validate_chunk_uid_rejects_tampered(self):
        uid = self._uid()
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_uid(uid, chunk_schema_version=1, source="edgar_corpus", document_id="doc-1",
                                   chunk_config_hash=VALID_HASH_B, chunk_local_id="chunk000000")


# --------------------------------------------------------------- accession validation

class TestAccessionValidation:
    def test_valid_accession_accepted(self):
        ms.validate_accession("0000100122-24-000002")

    def test_none_allowed(self):
        ms.validate_accession(None)

    @pytest.mark.parametrize("bad", [
        "0000100122-24-00002",   # too short final group
        "000100122-24-000002",   # too short first group
        "0000100122-2-000002",   # too short middle group
        "0000100122240000002",   # no hyphens
        "0000100122-24-0000021", # too long
        "abcdefghij-24-000002",  # non-numeric
        "",
    ])
    def test_malformed_accession_rejected(self, bad):
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_accession(bad)


# --------------------------------------------------------------- offsets

class TestOffsetValidation:
    def test_both_none_allowed(self):
        ms.validate_offsets(None, None)

    def test_both_populated_valid_range(self):
        ms.validate_offsets(0, 5)

    def test_start_without_end_rejected(self):
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_offsets(0, None)

    def test_end_without_start_rejected(self):
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_offsets(None, 5)

    def test_negative_start_rejected(self):
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_offsets(-1, 5)

    def test_end_equal_start_rejected_half_open(self):
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_offsets(5, 5)

    def test_end_before_start_rejected(self):
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_offsets(10, 5)

    def test_end_exceeds_source_length_rejected(self):
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_offsets(0, 100, source_text="short text")

    def test_round_trip_match_passes(self):
        source = "The quick brown fox"
        ms.validate_offsets(4, 9, source_text=source, chunk_text="quick")

    def test_round_trip_mismatch_rejected(self):
        source = "The quick brown fox"
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_offsets(4, 9, source_text=source, chunk_text="WRONG")


# --------------------------------------------------------------- ISO dates

class TestIsoDateValidation:
    def test_valid_date_accepted(self):
        ms.validate_iso_date("2023-12-31", "period_end")

    def test_none_allowed(self):
        ms.validate_iso_date(None, "period_end")

    @pytest.mark.parametrize("bad", ["2023-13-01", "2023/12/31", "12-31-2023", "not-a-date", "2023-02-30"])
    def test_malformed_date_rejected(self, bad):
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_iso_date(bad, "period_end")


# --------------------------------------------------------------- record validation

class TestValidateChunkRecord:
    def test_valid_record_passes(self):
        ms.validate_chunk_record(make_record())

    def test_missing_field_rejected(self):
        record = make_record()
        del record["cik"]
        with pytest.raises(ms.ChunkMetadataError, match="cik"):
            ms.validate_chunk_record(record)

    def test_unknown_extra_key_permitted(self):
        record = make_record(some_extension_field="anything")
        ms.validate_chunk_record(record)

    def test_non_nullable_field_none_rejected(self):
        record = make_record(company=None)
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_wrong_type_rejected(self):
        record = make_record(cik="100122")
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_negative_ordinal_rejected(self):
        record = make_record(ordinal=-1)
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_zero_token_count_rejected(self):
        record = make_record(token_count=0)
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_negative_token_count_rejected(self):
        record = make_record(token_count=-3)
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_empty_text_rejected(self):
        record = make_record(text="")
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_unknown_content_type_rejected(self):
        record = make_record(content_type="chart")
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    @pytest.mark.parametrize("content_type", ["table", "table_summary"])
    def test_table_content_type_requires_table_id(self, content_type):
        record = make_record(content_type=content_type, table_id=None)
        with pytest.raises(ms.ChunkMetadataError, match="table_id"):
            ms.validate_chunk_record(record)

    @pytest.mark.parametrize("content_type", ["table", "table_summary"])
    def test_table_content_type_with_table_id_passes(self, content_type):
        record = make_record(content_type=content_type, table_id="doc-1#table-0001")
        ms.validate_chunk_record(record)

    def test_prose_without_table_id_passes(self):
        ms.validate_chunk_record(make_record(content_type="prose", table_id=None))

    def test_unknown_source_rejected(self):
        record = make_record(source="msmarco")
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_malformed_chunk_config_hash_rejected(self):
        record = make_record(chunk_config_hash="not-a-hash")
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_uppercase_chunk_config_hash_rejected(self):
        record = make_record(chunk_config_hash="A" * 64)
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_tampered_chunk_uid_rejected_when_verify_uid_true(self):
        record = make_record()
        record["chunk_uid"] = "0" * 64
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record, verify_uid=True)

    def test_tampered_chunk_uid_allowed_when_verify_uid_false(self):
        record = make_record()
        record["chunk_uid"] = "0" * 64
        ms.validate_chunk_record(record, verify_uid=False)

    def test_malformed_accession_rejected_via_record(self):
        record = make_record(accession="bad-accession")
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_valid_accession_via_record_passes(self):
        record = make_record(accession="0000100122-24-000002", source="primary")
        ms.validate_chunk_record(record)

    def test_malformed_period_end_rejected_via_record(self):
        record = make_record(period_end="2023/12/31")
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)

    def test_bad_offsets_rejected_via_record(self):
        record = make_record(char_start=10, char_end=5)
        with pytest.raises(ms.ChunkMetadataError):
            ms.validate_chunk_record(record)


# --------------------------------------------------------------- table validation

class TestValidateChunkTable:
    def test_single_record_table(self):
        result = ms.validate_chunk_table([make_record()])
        assert result.row_count == 1
        assert result.unique_chunk_uids == 1
        assert result.unique_local_ids_per_document_config == 1

    def test_multiple_distinct_records(self):
        records = [make_record(ordinal=i, chunk_local_id=ms.build_chunk_local_id(i)) for i in range(5)]
        for r in records:
            r["chunk_uid"] = ms.build_chunk_uid(
                chunk_schema_version=r["chunk_schema_version"], source=r["source"],
                document_id=r["document_id"], chunk_config_hash=r["chunk_config_hash"],
                chunk_local_id=r["chunk_local_id"],
            )
        result = ms.validate_chunk_table(records)
        assert result.row_count == 5
        assert result.unique_chunk_uids == 5

    def test_duplicate_chunk_uid_rejected(self):
        record = make_record()
        with pytest.raises(ms.ChunkMetadataError, match="duplicate chunk_uid"):
            ms.validate_chunk_table([record, copy.deepcopy(record)])

    def test_duplicate_local_id_within_document_config_rejected(self):
        r1 = make_record(document_id="doc-1", chunk_config_hash=VALID_HASH_A, chunk_local_id="chunk000000")
        r2 = make_record(document_id="doc-1", chunk_config_hash=VALID_HASH_A, chunk_local_id="chunk000000",
                          source="edgar_corpus")
        r2["chunk_uid"] = "f" * 64  # distinct chunk_uid, but same local identity triple
        with pytest.raises(ms.ChunkMetadataError, match="duplicate"):
            ms.validate_chunk_table([r1, r2], verify_uid=False)

    def test_same_local_id_different_config_hash_allowed(self):
        r1 = make_record(chunk_config_hash=VALID_HASH_A, chunk_local_id="chunk000000")
        r2 = make_record(chunk_config_hash=VALID_HASH_B, chunk_local_id="chunk000000")
        result = ms.validate_chunk_table([r1, r2])
        assert result.row_count == 2
        assert result.unique_local_ids_per_document_config == 2

    def test_field_coverage_reports_full_population(self):
        result = ms.validate_chunk_table([make_record()])
        assert result.field_coverage["company"]["populated"] == 1
        assert result.field_coverage["company"]["population_pct"] == 100.0

    def test_field_coverage_reports_null_population(self):
        result = ms.validate_chunk_table([make_record(accession=None)])
        assert result.field_coverage["accession"]["null"] == 1
        assert result.field_coverage["accession"]["population_pct"] == 0.0

    def test_empty_table(self):
        result = ms.validate_chunk_table([])
        assert result.row_count == 0
        assert result.unique_chunk_uids == 0


# --------------------------------------------------------------- real-artifact compatibility (local_data)

PHASE1_CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"


@pytest.mark.local_data
class TestPhase1RealArtifactCompatibility:
    def test_all_phase1_rows_map_to_unique_chunk_uids(self):
        from pathlib import Path
        path = Path("artifacts") / "chunks" / PHASE1_CHUNK_CONFIG_HASH / "chunks.parquet"
        table = pq.read_table(path)
        rows = table.to_pylist()
        records = []
        for row in rows:
            local_id = ms.build_chunk_local_id(row["ordinal"])
            uid = ms.build_chunk_uid(
                chunk_schema_version=ms.CHUNK_SCHEMA_VERSION, source="edgar_corpus",
                document_id=row["document_id"], chunk_config_hash=row["chunk_config_hash"],
                chunk_local_id=local_id,
            )
            records.append({
                "chunk_schema_version": ms.CHUNK_SCHEMA_VERSION, "chunk_uid": uid, "chunk_local_id": local_id,
                "document_id": row["document_id"], "accession": None, "cik": row["cik"], "company": row["company"],
                "form_type": row["form_type"], "fiscal_year": row["fiscal_year"], "period_end": None,
                "filed_date": None, "sic": None, "section_id": None, "section_title": None,
                "ordinal": row["ordinal"], "char_start": None, "char_end": None, "content_type": "prose",
                "table_id": None, "source": "edgar_corpus", "text": row["text"], "token_count": row["token_count"],
                "chunk_config_hash": row["chunk_config_hash"],
            })
        result = ms.validate_chunk_table(records)
        assert result.row_count == 162_357
        assert result.unique_chunk_uids == 162_357


@pytest.mark.local_data
class TestTask28RealArtifactCompatibility:
    def test_primary_sample_maps_to_unique_chunk_uids(self):
        import json
        from pathlib import Path

        from src.storage import safe_component

        document_id = "primary:100122:0000100122-24-000002"
        path = Path("artifacts") / "primary_docs" / "parsed" / f"{safe_component(document_id)}.json"
        with open(path, encoding="utf-8") as f:
            nodes = json.load(f)

        demo_config_hash = hashlib.sha256(b"test-primary-compat").hexdigest()
        records = []
        for node in nodes[:20]:
            canonical_content_type = "prose" if node["content_type"] == "narrative" else "table"
            local_id = ms.build_chunk_local_id(node["source_order"], section_id=node["section_id"])
            uid = ms.build_chunk_uid(
                chunk_schema_version=ms.CHUNK_SCHEMA_VERSION, source="primary", document_id=document_id,
                chunk_config_hash=demo_config_hash, chunk_local_id=local_id,
            )
            records.append({
                "chunk_schema_version": ms.CHUNK_SCHEMA_VERSION, "chunk_uid": uid, "chunk_local_id": local_id,
                "document_id": document_id, "accession": "0000100122-24-000002", "cik": 100122,
                "company": "Placeholder Co", "form_type": "10-K", "fiscal_year": 2023,
                "period_end": None, "filed_date": None, "sic": None,
                "section_id": node["section_id"], "section_title": node["section_title"],
                "ordinal": node["source_order"], "char_start": None, "char_end": None,
                "content_type": canonical_content_type, "table_id": node["table_id"], "source": "primary",
                "text": node["text"] if node["text"] else "(empty)", "token_count": max(1, len((node["text"] or "").split())),
                "chunk_config_hash": demo_config_hash,
            })
        result = ms.validate_chunk_table(records)
        assert result.row_count == len(records)
        assert result.unique_chunk_uids == len(records)
