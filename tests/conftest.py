"""Shared fixtures for the Phase 0 foundation test suite.

Test isolation notes:
  - src.config.get_settings and src.storage.get_storage are both
    functools.lru_cache-cached singletons. Any test that changes an
    environment variable affecting them must call the relevant
    .cache_clear() itself after monkeypatching - the autouse fixture below
    only guarantees a clean cache *between* tests, not mid-test.
  - Python's logging module is process-global. The autouse logging fixture
    snapshots and restores the root logger's handler list and level around
    every test, so tests may freely call configure_logging() without
    leaking state into unrelated tests or files.
"""

from __future__ import annotations

import io
import logging
import shutil

import pytest

from src.config import get_settings
from src.logging_utils import _HANDLER_NAME, configure_logging
from src.storage import get_storage


@pytest.fixture(autouse=True)
def _reset_config_and_storage_caches():
    get_settings.cache_clear()
    get_storage.cache_clear()
    yield
    get_settings.cache_clear()
    get_storage.cache_clear()


@pytest.fixture(autouse=True)
def _reset_logging_state():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)


@pytest.fixture
def log_capture():
    """configure_logging(level) then redirect the project's console handler
    to an in-memory buffer, returned for the test to inspect. A fresh
    handler is created per test (see _reset_logging_state above), so this
    never bleeds output between tests."""

    def _capture(level: str = "INFO") -> io.StringIO:
        configure_logging(level)
        root = logging.getLogger()
        handler = next(h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME)
        buf = io.StringIO()
        handler.stream = buf
        return buf

    return _capture


@pytest.fixture(scope="session", autouse=True)
def _cleanup_artifacts_dir_if_created_by_tests():
    """artifacts/ should not exist before this suite runs (Task 0.7:
    nothing creates it implicitly). If storage tests create it via explicit
    ensure_dir() calls, remove it again at the end of the session so the
    repository returns to its pre-test state - mirroring the manual
    cleanup discipline used during Task 0.7's own verification."""
    storage = get_storage()
    pre_existing = storage.artifacts_root.exists()
    yield
    if not pre_existing and storage.artifacts_root.exists():
        shutil.rmtree(storage.artifacts_root, ignore_errors=True)
