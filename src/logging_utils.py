"""One consistent application logging convention for Phase 1+ code.

    from src.logging_utils import configure_logging, get_logger, log_event

    configure_logging()                      # reads LOG_LEVEL from src.config
    logger = get_logger(__name__)
    logger.info("service started")
    log_event(logger, logging.INFO, "embedding_batch_completed",
              batch=4, processed=128, elapsed_ms=95)

Console/stderr only in Phase 0 - no file handlers, no log directories.
Importing this module performs no configuration and no side effects;
`configure_logging()` must be called explicitly.

`src/ingest/` predates this module and is left as-is (legacy acquisition
logging via `logging.basicConfig` + `print()`) - see
project_plan/LOGGING.md for the distinction. New application code should
use this module instead.

Security note: structured field values whose *key* looks like a secret
(password, api_key, token, authorization, credential, ...) are replaced
with "[REDACTED]" before formatting. This is a narrow, defensive check on
recognized field names only - it cannot detect or sanitize a secret
embedded inside a free-form log message. Never put secrets in messages.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from src.config import get_settings

_HANDLER_NAME = "sec_rag_console_handler"

_SECRET_KEY_RE = re.compile(
    r"(password|secret|api[_-]?key|apikey|token|authoriz|credential)", re.IGNORECASE
)

_NEEDS_QUOTING_RE = re.compile(r'[\s"=]')


class _UtcEventFormatter(logging.Formatter):
    """Timezone-aware UTC timestamp + level + logger name + message.
    Leaves exception formatting to the base class (exc_info/traceback intact)."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"

    def format(self, record: logging.LogRecord) -> str:
        prefix = f"{self.formatTime(record)} level={record.levelname} logger={record.name} "
        return prefix + super().format(record)


def configure_logging(level: str | None = None) -> None:
    """Attach (or update) this project's single console handler on the root
    logger. Idempotent: calling this repeatedly never adds a second handler -
    it updates the level on the existing one. Does not touch handlers this
    module didn't create (other libraries' handlers are left alone).

    level defaults to get_settings().log_level - never read LOG_LEVEL from
    os.environ directly here; src.config owns that.
    """
    if level is None:
        level = get_settings().log_level
    level_value = getattr(logging, level.upper())

    root = logging.getLogger()
    existing = next((h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME), None)
    if existing is not None:
        existing.setLevel(level_value)
    else:
        handler = logging.StreamHandler()  # stderr, console-only per Phase 0
        handler.name = _HANDLER_NAME
        handler.setFormatter(_UtcEventFormatter())
        handler.setLevel(level_value)
        root.addHandler(handler)
    root.setLevel(level_value)


def get_logger(name: str) -> logging.Logger:
    """Module-provenance logger, e.g. get_logger(__name__) -> "src.embeddings"."""
    return logging.getLogger(name)


def _serialize_value(value: object) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        if value == "" or _NEEDS_QUOTING_RE.search(value):
            return json.dumps(value)
        return value
    try:
        return json.dumps(value)
    except TypeError:
        return json.dumps(str(value))


def log_event(logger: logging.Logger, level: int, event: str, **fields: object) -> None:
    """Emit one structured log line: `event=<name> key=value key=value ...`.

    Context is assembled entirely into the message string - never passed via
    logging's `extra=` dict - so a field name can never collide with a
    reserved LogRecord attribute (name, msg, args, levelname, pathname,
    filename, module, exc_info, ...).

    Field values whose key matches a secret-looking pattern (password,
    api_key, token, authorization, credential, ...) are replaced with
    "[REDACTED]" before formatting. This only protects structured fields
    passed here - it cannot inspect free-form text in `event` or elsewhere.
    """
    parts = [f"event={_serialize_value(event)}"]
    for key, value in fields.items():
        if _SECRET_KEY_RE.search(key):
            value = "[REDACTED]"
        parts.append(f"{key}={_serialize_value(value)}")
    logger.log(level, " ".join(parts))
