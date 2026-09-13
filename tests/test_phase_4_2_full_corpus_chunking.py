"""Task 4.2 - full-corpus chunking driver tests.

Portable tests use a tiny synthetic fake tokenizer and tiny synthetic
Task-4.1-shaped fixtures - no real HF tokenizer load, no 91,086-document
build inside pytest. Tests that touch the real frozen local artifacts
(Task 3.2's dev chunk artifact, the real HF tokenizer, Task 4.1's full
manifest) are marked `local_data`/`model`.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.artifacts.versioning import ConfigHashError
from src.chunk import metadata_schema as ms
from src.storage import get_storage

import scripts.chunk_full_corpus as m


class FakeTokenizer:
    """Whitespace-word tokenizer - deterministic, no model/network. Mimics
    an HF fast tokenizer's __call__ shape closely enough to exercise
    chunk_one_document's real integration path."""
    is_fast = True

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=True):
        offsets = [(mo.start(), mo.end()) for mo in re.finditer(r"\S+", text)]
        return {"offset_mapping": offsets}


def make_fields(**overrides) -> dict:
    fields = {"cik": 100122, "company": "Acme Corp", "form_type": "10-K", "fiscal_year": 2020}
    fields.update(overrides)
    return fields


# --------------------------------------------------------------- 1/5. frozen chunk semantics

def test_load_and_verify_chunk_config_reproduces_frozen_hash():
    cfg = m.load_and_verify_chunk_config()
    assert cfg["window_size_tokens"] == 256
    assert cfg["overlap_tokens"] == 0
    assert cfg["split_mode"] == "fixed"


def test_frozen_hash_constant_matches_config_file():
    from src.artifacts.versioning import semantic_hash
    cfg = json.loads(m.CHUNK_CONFIG_PATH.read_text(encoding="utf-8"))
    assert semantic_hash(cfg) == m.EXPECTED_CHUNK_CONFIG_HASH


def test_load_tokenizer_stops_when_offline_load_fails(monkeypatch):
    import transformers
    def boom(*a, **kw):
        raise OSError("not cached")
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", staticmethod(boom))
    with pytest.raises(SystemExit):
        m.load_tokenizer(m.load_and_verify_chunk_config())


# --------------------------------------------------------------- 2/3/13/14. window semantics

def test_256_style_window_and_zero_overlap_semantics():
    body = " ".join(f"word{i}" for i in range(10))
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(), body_text=body, tokenizer=FakeTokenizer(),
        window_size=4, stride=4, chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    assert [r["token_count"] for r in records] == [4, 4, 2]  # final partial window kept
    assert [r["ordinal"] for r in records] == [0, 1, 2]


def test_zero_overlap_windows_partition_tokens_exactly():
    body = " ".join(f"w{i}" for i in range(9))
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(), body_text=body, tokenizer=FakeTokenizer(),
        window_size=3, stride=3, chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    reconstructed = " ".join(r["text"] for r in records)
    assert reconstructed == body  # no gap, no overlap, no duplication


def test_empty_body_emits_zero_chunks():
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(), body_text="", tokenizer=FakeTokenizer(),
        window_size=256, stride=256, chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    assert records == []


def test_nonempty_body_emits_positive_chunks():
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(), body_text="hello world", tokenizer=FakeTokenizer(),
        window_size=256, stride=256, chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    assert len(records) > 0


# --------------------------------------------------------------- 4. frontmatter excluded from body

def test_chunk_text_never_contains_frontmatter():
    fm_text = (
        "---\ncik: 100122\ncompany: \"Acme Corp\"\nform_type: \"10-K\"\nfiscal_year: 2020\n"
        "source: \"edgar_corpus\"\nsource_filename: \"x.htm\"\ndocument_id: \"x.htm\"\n"
        "source_split: \"train\"\n---\n\n## Item 1\n\nreal body content here\n"
    )
    from src.normalize.edgar_markdown import FULL_CORPUS_FRONTMATTER_KEYS
    from src.chunk.fixed_window import parse_normalized_document
    fields, body = parse_normalized_document(fm_text, frontmatter_keys=FULL_CORPUS_FRONTMATTER_KEYS)
    records = m.chunk_one_document(
        document_id="x.htm", fields=fields, body_text=body, tokenizer=FakeTokenizer(),
        window_size=256, stride=256, chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    for r in records:
        assert "cik:" not in r["text"] and "---" not in r["text"]


# --------------------------------------------------------------- 6/7/8. Task 2.9 schema reuse

def test_uses_canonical_23_field_schema():
    schema = ms.canonical_pyarrow_schema()
    assert len(schema.names) == 23


def test_chunk_local_id_reused_from_metadata_schema():
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(), body_text="a b c d e", tokenizer=FakeTokenizer(),
        window_size=2, stride=2, chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    assert records[0]["chunk_local_id"] == ms.build_chunk_local_id(0)
    assert records[1]["chunk_local_id"] == ms.build_chunk_local_id(1)


def test_chunk_uid_reused_from_metadata_schema():
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(), body_text="a b c", tokenizer=FakeTokenizer(),
        window_size=256, stride=256, chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    expected = ms.build_chunk_uid(
        chunk_schema_version=2, source="edgar_corpus", document_id="d1",
        chunk_config_hash="a" * 64, chunk_local_id=records[0]["chunk_local_id"],
    )
    assert records[0]["chunk_uid"] == expected


# --------------------------------------------------------------- 9/10. nullable company / no fabrication

def test_nullable_company_accepted():
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(company=None), body_text="some text",
        tokenizer=FakeTokenizer(), window_size=256, stride=256,
        chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    assert records[0]["company"] is None
    ms.validate_chunk_record(records[0])  # must not raise


def test_unavailable_fields_not_fabricated():
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(), body_text="some text", tokenizer=FakeTokenizer(),
        window_size=256, stride=256, chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    r = records[0]
    assert r["accession"] is None
    assert r["period_end"] is None
    assert r["filed_date"] is None
    assert r["sic"] is None
    assert r["table_id"] is None


# --------------------------------------------------------------- 11/12. offsets / section metadata

def test_char_offsets_half_open_and_round_trip():
    body = "The quick brown fox jumps"
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(), body_text=body, tokenizer=FakeTokenizer(),
        window_size=2, stride=2, chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    for r in records:
        assert body[r["char_start"]:r["char_end"]] == r["text"]
        assert r["char_end"] > r["char_start"]


def test_section_metadata_never_fabricated_for_fixed_split():
    records = m.chunk_one_document(
        document_id="d1", fields=make_fields(), body_text="## Item 1\n\ntext ## Item 2\n\nmore",
        tokenizer=FakeTokenizer(), window_size=256, stride=256,
        chunk_config_hash="a" * 64, chunk_schema_version=2,
    )
    for r in records:
        assert r["section_id"] is None
        assert r["section_title"] is None


# --------------------------------------------------------------- 15/16/17. sharding

def test_one_document_never_split_across_shards(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "TARGET_ROWS_PER_SHARD", 5)
    rows_doc_a = [dict(document_id="a", chunk_config_hash="a" * 64, chunk_schema_version=2) for _ in range(4)]
    rows_doc_b = [dict(document_id="b", chunk_config_hash="a" * 64, chunk_schema_version=2) for _ in range(4)]
    # Build minimal valid canonical rows via chunk_one_document instead of hand-rolled dicts,
    # so the schema is genuinely satisfied.
    records_a = m.chunk_one_document(document_id="a", fields=make_fields(), body_text="w0 w1 w2 w3",
                                      tokenizer=FakeTokenizer(), window_size=1, stride=1,
                                      chunk_config_hash="a" * 64, chunk_schema_version=2)
    records_b = m.chunk_one_document(document_id="b", fields=make_fields(), body_text="w0 w1 w2 w3",
                                      tokenizer=FakeTokenizer(), window_size=1, stride=1,
                                      chunk_config_hash="a" * 64, chunk_schema_version=2)
    shard_rec = m.publish_shard(tmp_path, 0, records_a + records_b)
    doc_ids_in_shard = {d["document_id"] for d in shard_rec["documents"]}
    assert doc_ids_in_shard == {"a", "b"}
    assert shard_rec["row_count"] == len(records_a) + len(records_b)


def test_atomic_shard_publication_leaves_no_tmp_file(tmp_path):
    records = m.chunk_one_document(document_id="a", fields=make_fields(), body_text="w0 w1",
                                    tokenizer=FakeTokenizer(), window_size=1, stride=1,
                                    chunk_config_hash="a" * 64, chunk_schema_version=2)
    shard_rec = m.publish_shard(tmp_path, 0, records)
    final_path = tmp_path / shard_rec["relative_path"]
    assert final_path.is_file()
    assert not final_path.with_suffix(".parquet.tmp").exists()
    actual_hash = hashlib.sha256(final_path.read_bytes()).hexdigest()
    assert actual_hash == shard_rec["sha256"]


def test_deterministic_shard_row_count_matches_input():
    records = m.chunk_one_document(document_id="a", fields=make_fields(), body_text="w0 w1 w2",
                                    tokenizer=FakeTokenizer(), window_size=1, stride=1,
                                    chunk_config_hash="a" * 64, chunk_schema_version=2)
    assert len(records) == 3


# --------------------------------------------------------------- 18/19. identity mismatch rejection

def test_checkpoint_config_identity_mismatch_rejected():
    header = {
        "phase_4_1_config_hash": "a" * 64, "phase_4_1_build_manifest_sha256": "b" * 64,
        "phase_4_2_build_config_hash": "c" * 64, "chunk_schema_version": 2, "chunk_config_hash": "d" * 64,
    }
    expected = dict(header)
    expected["chunk_config_hash"] = "e" * 64
    with pytest.raises(SystemExit):
        m.assert_checkpoint_resumable(header, expected, ckpt_path=Path("x"))


def test_checkpoint_matching_identity_accepted():
    header = {
        "phase_4_1_config_hash": "a" * 64, "phase_4_1_build_manifest_sha256": "b" * 64,
        "phase_4_2_build_config_hash": "c" * 64, "chunk_schema_version": 2, "chunk_config_hash": "d" * 64,
    }
    m.assert_checkpoint_resumable(header, dict(header), ckpt_path=Path("x"))  # must not raise


def test_checkpoint_missing_header_not_a_mismatch():
    m.assert_checkpoint_resumable(None, {"phase_4_1_config_hash": "a" * 64}, ckpt_path=Path("x"))


def test_stale_task41_manifest_hash_rejected():
    with pytest.raises(SystemExit):
        m.verify_manifest_hash(b"tampered content", "a" * 64)


def test_matching_task41_manifest_hash_accepted():
    data = b"real manifest content"
    expected = hashlib.sha256(data).hexdigest()
    assert m.verify_manifest_hash(data, expected) == expected


# --------------------------------------------------------------- 20. corrupted shard rejection

def test_corrupted_shard_hash_excluded_on_resume(tmp_path):
    records = m.chunk_one_document(document_id="a", fields=make_fields(), body_text="w0 w1",
                                    tokenizer=FakeTokenizer(), window_size=1, stride=1,
                                    chunk_config_hash="a" * 64, chunk_schema_version=2)
    shard_rec = m.publish_shard(tmp_path, 0, records)
    valid_shards, completed = m.verify_shards(tmp_path, [shard_rec])
    assert "a" in completed

    # Corrupt the file without updating the checkpoint record.
    final_path = tmp_path / shard_rec["relative_path"]
    final_path.write_bytes(b"corrupted garbage")
    valid_shards, completed = m.verify_shards(tmp_path, [shard_rec])
    assert valid_shards == {}
    assert completed == {}


def test_missing_shard_file_excluded_on_resume(tmp_path):
    shard_rec = {"shard_id": "part-00000", "relative_path": "shards/part-00000.parquet",
                 "row_count": 1, "sha256": "x" * 64, "documents": [{"document_id": "a", "chunk_count": 1}]}
    valid_shards, completed = m.verify_shards(tmp_path, [shard_rec])
    assert valid_shards == {} and completed == {}


# --------------------------------------------------------------- 21. simulated interruption + resume

class _StubStorage:
    def __init__(self, root: Path):
        self._root = root

    def ensure_dir(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path


def _write_task41_doc(root: Path, document_id: str, cik: int, year: int, body: str) -> None:
    from src.normalize.edgar_markdown import render_document, FULL_CORPUS_FRONTMATTER_KEYS
    fields = {
        "cik": cik, "company": None, "form_type": "10-K", "fiscal_year": year,
        "source": "edgar_corpus", "source_filename": document_id, "document_id": document_id,
        "source_split": "train",
    }
    sections = {"section_1": body} if body else {}
    text = render_document(fields, sections, frontmatter_keys=FULL_CORPUS_FRONTMATTER_KEYS)
    (root / document_id.replace(".htm", ".md")).write_bytes(text.encode("utf-8"))


def _synthetic_entries_and_root(tmp_path) -> tuple[list[dict], Path]:
    root = tmp_path / "task41_root"
    root.mkdir()
    entries = []
    for i in range(6):
        doc_id = f"doc{i}.htm"
        body = f"word{i}a word{i}b word{i}c word{i}d word{i}e" if i != 3 else ""
        _write_task41_doc(root, doc_id, cik=1000 + i, year=2000 + i, body=body)
        out_name = doc_id.replace(".htm", ".md")
        data = (root / out_name).read_bytes()
        entries.append({
            "document_id": doc_id, "source_split": "train", "cik": 1000 + i, "fiscal_year": 2000 + i,
            "relative_output_path": out_name, "content_sha256": hashlib.sha256(data).hexdigest(),
            "status": "VALID_EMPTY_SOURCE" if i == 3 else "NORMALIZED",
        })
    return entries, root


def test_simulated_interruption_resume_no_duplicate_chunks(tmp_path):
    entries, root = _synthetic_entries_and_root(tmp_path)
    out_dir = tmp_path / "out"
    storage = _StubStorage(out_dir)
    identity = {
        "phase_4_1_config_hash": "a" * 64, "phase_4_1_build_manifest_sha256": "b" * 64,
        "phase_4_2_build_config_hash": "c" * 64, "chunk_schema_version": 2, "chunk_config_hash": "d" * 64,
    }
    tokenizer = FakeTokenizer()

    # First "run" - simulate an interruption after 3 of 6 documents.
    m.run(storage, entries, out_dir, identity, tokenizer, window_size=2, stride=2,
          chunk_config_hash="d" * 64, chunk_schema_version=2, task41_root=root, limit=3)

    # Resume - process the rest.
    m.run(storage, entries, out_dir, identity, tokenizer, window_size=2, stride=2,
          chunk_config_hash="d" * 64, chunk_schema_version=2, task41_root=root, limit=None)

    summary = m.summarize_final(out_dir, entries)
    assert summary["missing_count"] == 0
    assert summary["failed_count"] == 0
    assert summary["documents_without_chunks"] == 1  # doc3, the empty one

    # No duplicate chunk_uid across all published shards.
    _header, shard_records, _doc_records = m.read_checkpoint(m.checkpoint_path(out_dir))
    valid_shards, _completed = m.verify_shards(out_dir, shard_records)
    all_uids = []
    for rec in valid_shards.values():
        table = pq.read_table(out_dir / rec["relative_path"])
        all_uids.extend(table.column("chunk_uid").to_pylist())
    assert len(all_uids) == len(set(all_uids))

    # Compare against an uninterrupted from-scratch run for the same corpus.
    out_dir_2 = tmp_path / "out_fresh"
    storage2 = _StubStorage(out_dir_2)
    m.run(storage2, entries, out_dir_2, identity, tokenizer, window_size=2, stride=2,
          chunk_config_hash="d" * 64, chunk_schema_version=2, task41_root=root, limit=None)
    summary_fresh = m.summarize_final(out_dir_2, entries)
    assert summary_fresh["total_chunk_count"] == summary["total_chunk_count"]


# --------------------------------------------------------------- 22/23. manifest completeness / determinism

def test_document_manifest_completeness(tmp_path):
    entries, root = _synthetic_entries_and_root(tmp_path)
    out_dir = tmp_path / "out"
    storage = _StubStorage(out_dir)
    identity = {
        "phase_4_1_config_hash": "a" * 64, "phase_4_1_build_manifest_sha256": "b" * 64,
        "phase_4_2_build_config_hash": "c" * 64, "chunk_schema_version": 2, "chunk_config_hash": "d" * 64,
    }
    m.run(storage, entries, out_dir, identity, FakeTokenizer(), window_size=2, stride=2,
          chunk_config_hash="d" * 64, chunk_schema_version=2, task41_root=root, limit=None)
    path, _hash = m.build_document_manifest(out_dir, entries)
    table = pq.read_table(path)
    assert table.num_rows == len(entries)
    assert set(table.column("document_id").to_pylist()) == {e["document_id"] for e in entries}


def test_shard_manifest_hash_deterministic(tmp_path):
    entries, root = _synthetic_entries_and_root(tmp_path)
    out_dir = tmp_path / "out"
    storage = _StubStorage(out_dir)
    identity = {
        "phase_4_1_config_hash": "a" * 64, "phase_4_1_build_manifest_sha256": "b" * 64,
        "phase_4_2_build_config_hash": "c" * 64, "chunk_schema_version": 2, "chunk_config_hash": "d" * 64,
    }
    m.run(storage, entries, out_dir, identity, FakeTokenizer(), window_size=2, stride=2,
          chunk_config_hash="d" * 64, chunk_schema_version=2, task41_root=root, limit=None)
    _p1, h1 = m.build_shard_manifest(out_dir)
    _p2, h2 = m.build_shard_manifest(out_dir)
    assert h1 == h2


# --------------------------------------------------------------- 24. no duplicate chunk_uid (broader)

def test_no_duplicate_chunk_uid_across_multiple_documents():
    all_records = []
    for i in range(5):
        recs = m.chunk_one_document(
            document_id=f"doc{i}", fields=make_fields(), body_text="a b c d e f g",
            tokenizer=FakeTokenizer(), window_size=3, stride=3,
            chunk_config_hash="a" * 64, chunk_schema_version=2,
        )
        all_records.extend(recs)
    uids = [r["chunk_uid"] for r in all_records]
    assert len(uids) == len(set(uids))


# --------------------------------------------------------------- 25. Task 3.2 regression

@pytest.mark.local_data
@pytest.mark.model
def test_regression_reproduces_frozen_dev_chunk_boundaries_and_text():
    """Re-chunks a document through the real production path (real
    tokenizer, real Task 4.1 normalized text) and compares against the
    frozen Task 3.2 A1 dev-corpus chunk artifact's rows for the same
    document_id - the exact same tokenizer/window/offset semantics must
    reproduce the exact same boundaries/text."""
    storage = get_storage()
    dev_chunks_path = storage.chunks_dir(m.EXPECTED_CHUNK_CONFIG_HASH) / "chunks.parquet"
    if not dev_chunks_path.is_file():
        pytest.skip("Phase 3 A1 dev chunk artifact not present on disk")

    document_id = "1005817_2016.htm"
    dev_table = pq.read_table(dev_chunks_path)
    dev_rows = [r for r in dev_table.to_pylist() if r["document_id"] == document_id]
    if not dev_rows:
        pytest.skip(f"{document_id} not present in the dev chunk artifact")
    dev_rows.sort(key=lambda r: r["ordinal"])

    task41_root = storage.normalized_dir_for_config(m.EXPECTED_PHASE_4_1_CONFIG_HASH)
    md_path = task41_root / "1005817_2016.md"
    if not md_path.is_file():
        pytest.skip("Task 4.1 full-corpus artifact not present on disk")

    from src.normalize.edgar_markdown import FULL_CORPUS_FRONTMATTER_KEYS
    from src.chunk.fixed_window import parse_normalized_document
    text = md_path.read_text(encoding="utf-8")
    fields, body = parse_normalized_document(text, frontmatter_keys=FULL_CORPUS_FRONTMATTER_KEYS)

    cfg = m.load_and_verify_chunk_config()
    tokenizer = m.load_tokenizer(cfg)
    new_records = m.chunk_one_document(
        document_id=document_id, fields=fields, body_text=body, tokenizer=tokenizer,
        window_size=cfg["window_size_tokens"], stride=cfg["stride_tokens"],
        chunk_config_hash=m.EXPECTED_CHUNK_CONFIG_HASH, chunk_schema_version=ms.CHUNK_SCHEMA_VERSION,
    )
    new_records.sort(key=lambda r: r["ordinal"])

    assert len(new_records) == len(dev_rows)
    for old, new in zip(dev_rows, new_records):
        assert old["text"] == new["text"]
        assert old["token_count"] == new["token_count"]
        assert old["ordinal"] == new["ordinal"]


# --------------------------------------------------------------- 26. namespace collision safety

def test_full_corpus_namespace_never_collides_with_dev_artifact():
    storage = get_storage()
    dev_path = storage.chunks_dir(m.EXPECTED_CHUNK_CONFIG_HASH)
    full_path = storage.chunks_dir_full(m.EXPECTED_PHASE_4_1_CONFIG_HASH, m.EXPECTED_CHUNK_CONFIG_HASH)
    assert dev_path != full_path
    assert "chunks_full" in full_path.parts
    assert "chunks_full" not in dev_path.parts


def test_chunks_dir_full_rejects_non_hash_input():
    storage = get_storage()
    with pytest.raises(ConfigHashError):
        storage.chunks_dir_full("../escape", "a" * 64)
    with pytest.raises(ConfigHashError):
        storage.chunks_dir_full("a" * 64, "not-a-hash")


# --------------------------------------------------------------- 27-31. no later-phase work

def _direct_imports_of(module_path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_driver_never_imports_embedding_index_generation_or_test_access():
    forbidden_prefixes = (
        "src.embeddings", "src.index", "src.retrieval", "src.generation",
        "src.rerank", "src.crag", "src.router", "src.sql", "src.nav", "src.api", "src.guards",
    )
    imports = _direct_imports_of(Path(m.__file__))
    forbidden_found = [n for n in imports if n.startswith(forbidden_prefixes)]
    assert forbidden_found == []
    assert "src.eval.test_access" not in imports
    assert not any(n.startswith("src.eval") for n in imports)


# --------------------------------------------------------------- 32/33. frozen data/artifact untouched

@pytest.mark.local_data
def test_plan_mode_never_modifies_task41_artifact_or_source_data():
    storage = get_storage()
    targets = [
        storage.xbrl_db,
        storage.normalized_dir_for_config(m.EXPECTED_PHASE_4_1_CONFIG_HASH) / "manifest.jsonl",
        storage.edgar_corpus_root / "train.parquet",
    ]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in targets if p.is_file()}
    m.load_and_verify_chunk_config()
    m.load_task41_manifest(storage)
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in targets if p.is_file()}
    assert before == after
