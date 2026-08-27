"""Tests for src.storage: deterministic generated paths, safe_component
normalization/rejection, explicit-creation semantics, frozen-root
protection, and STORAGE_ROOT override behavior. Never touches real frozen
data; the one directory-creation test uses a disposable child under the
real artifacts_root, removed in a finally block (also swept by
conftest.py's session cleanup as a backstop)."""

import pytest

from src.config import get_settings
from src.storage import StorageError, get_storage, safe_component


def test_chunks_dir_deterministic_for_same_input():
    storage = get_storage()
    assert storage.chunks_dir("abc123") == storage.chunks_dir("abc123")


def test_chunks_dir_differs_for_different_hash():
    storage = get_storage()
    assert storage.chunks_dir("abc123") != storage.chunks_dir("def456")


def test_chunks_dir_is_under_artifacts_root():
    storage = get_storage()
    assert storage.artifacts_root in storage.chunks_dir("abc123").parents


def test_index_dir_identity_requires_both_hash_and_model():
    storage = get_storage()
    a = storage.index_dir("hash1", "BAAI/bge-small-en-v1.5")
    b = storage.index_dir("hash1", "BAAI/bge-base-en-v1.5")
    c = storage.index_dir("hash2", "BAAI/bge-small-en-v1.5")
    assert a != b, "different embedding model must produce a different path"
    assert a != c, "different chunk_config_hash must produce a different path"


def test_normalized_and_eval_dirs_are_deterministic():
    storage = get_storage()
    assert storage.normalized_dir("v1") == storage.normalized_dir("v1")
    assert storage.eval_dir("2026-01-01") != storage.eval_dir("2026-02-01")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("BAAI/bge-small-en-v1.5", "BAAI--bge-small-en-v1.5"),
        ("simple-model", "simple-model"),
        ("model with spaces", "model-with-spaces"),
        ("ns:model", "ns-model"),
    ],
)
def test_safe_component_normalizes_legitimate_identifiers(value, expected):
    assert safe_component(value) == expected


@pytest.mark.parametrize(
    "value",
    ["../escape", "..\\escape", "/path", "C:\\escape", "..", ".", ""],
)
def test_safe_component_rejects_dangerous_values(value):
    with pytest.raises(StorageError):
        safe_component(value)


def test_chunks_dir_rejects_traversal_component():
    storage = get_storage()
    with pytest.raises(StorageError):
        storage.chunks_dir("../escape")


def test_ensure_dir_explicit_creation_and_idempotency():
    storage = get_storage()
    target = storage.chunks_dir("pytest_ensure_dir_smoke")
    assert not target.exists(), "target must not pre-exist"
    try:
        created_once = storage.ensure_dir(target)
        assert created_once.is_dir()
        created_again = storage.ensure_dir(target)  # idempotent, no error
        assert created_again == created_once
        assert created_again.is_dir()
    finally:
        if target.exists():
            target.rmdir()


def test_ensure_dir_refuses_frozen_data_root():
    storage = get_storage()
    forbidden = storage.data_root / "should_never_be_created_by_tests"
    with pytest.raises(StorageError):
        storage.ensure_dir(forbidden)
    assert not forbidden.exists()


def test_ensure_dir_refuses_repo_root():
    storage = get_storage()
    forbidden = storage.repo_root / "should_never_be_created_by_tests"
    with pytest.raises(StorageError):
        storage.ensure_dir(forbidden)
    assert not forbidden.exists()


def test_storage_root_override_moves_data_root_only(monkeypatch, tmp_path):
    alt = tmp_path / "alt_storage_root"
    monkeypatch.setenv("STORAGE_ROOT", str(alt))
    get_settings.cache_clear()
    get_storage.cache_clear()

    storage = get_storage()
    assert storage.data_root == alt.resolve()
    assert storage.msmarco_root == alt.resolve() / "msmarco"
    # generated-output roots stay repo-relative regardless of where data/ lives
    assert "alt_storage_root" not in str(storage.artifacts_root)
    assert "alt_storage_root" not in str(storage.results_root)
    # loading config/storage never creates the override path
    assert not alt.exists()
