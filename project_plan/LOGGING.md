# Logging

## Goals

One consistent, lightweight logging convention for all Phase 1+ application
code — so any component (normalize, chunk, embeddings, index, retrieval,
eval, generation) produces logs every developer can read the same way,
without each module inventing its own format or reading `LOG_LEVEL`
directly.

## Configuration

`LOG_LEVEL` comes from `src.config` (`get_settings().log_level`) —
`src/logging_utils.py` never reads `os.environ` itself. Dependency
direction: `src.config` → `src.logging_utils` → application modules.

## Usage

```python
import logging
from src.logging_utils import configure_logging, get_logger, log_event

configure_logging()                 # call once, e.g. at process/CLI entry point

logger = get_logger(__name__)       # preserves module provenance, e.g. "src.embeddings"

logger.info("service started")

log_event(
    logger,
    logging.INFO,
    "embedding_batch_completed",
    stage="embedding",
    batch=4,
    processed=128,
    elapsed_ms=95,
)
```

`configure_logging(level=...)` accepts an explicit level string
(`"DEBUG"`/`"INFO"`/...) for tests/tooling; omit it in normal application
code so `src.config`'s `LOG_LEVEL` governs.

## Format

```text
2026-08-27T00:07:24.250Z level=INFO logger=src.embeddings event=embedding_batch_completed stage=embedding batch=3 processed=96 elapsed_ms=122
```

Minimum fields on every line: UTC timestamp (`YYYY-MM-DDTHH:MM:SS.sssZ`,
always timezone-aware, never local/naive), `level`, `logger` (module
provenance). A plain `logger.info("message")` call omits `event=...`;
`log_event(...)` calls add it plus whatever structured fields were passed.

## Levels

Standard Python levels only — `DEBUG`, `INFO`, `WARNING`, `ERROR`,
`CRITICAL`. No custom levels.

## Structured fields

`log_event(logger, level, event, **fields)` renders each field as
`key=value`. Values are serialized predictably:

- `str`/`int`/`float`/`bool`/`None` render directly (`bool` as
  `true`/`false`, matching common structured-log convention)
- a string containing whitespace, `"`, or `=` is JSON-quoted
  (`spaced_value="hello world"`) so it can't be misread as two fields
- `Path` renders as its string form
- anything else falls back to `json.dumps(...)`, or `json.dumps(str(...))`
  if that itself isn't JSON-serializable — so an unsupported type never
  raises inside the formatter, it just degrades to a readable string

Context is assembled into the message text itself, **never** passed via
logging's `extra=` dict — this means a structured field name can never
collide with a reserved `LogRecord` attribute (`name`, `msg`, `args`,
`levelname`, `pathname`, `filename`, `module`, `exc_info`, ...); there is
nothing to collide with.

## Secret safety

Structured field *names* matching a secret-looking pattern (`password`,
`secret`, `api_key`/`apikey`, `token`, `authoriz...`, `credential`) have
their *value* replaced with `[REDACTED]` before formatting — verified
directly: a fake test value passed under `api_key`, `token`, `password`,
`authorization`, and `apikey` never appeared in the rendered output.

**This is a narrow, defensive check on recognized field names only.**
**Never put secrets into log messages.** Structured sensitive fields
receive defensive redaction; free-form text is the caller's responsibility
and this module cannot inspect it for embedded secrets. `src/config.py`'s
own design choice (Task 0.5) — no API-key field exists on `Settings` at
all — is the stronger guarantee; this redaction is a second, independent
layer, not a substitute for keeping credentials out of `Settings` and out
of message text in the first place.

## Exceptions

```python
try:
    ...
except Exception:
    logger.exception("operation failed")
```

works exactly as with stdlib `logging` — the custom formatter delegates
traceback rendering to `logging.Formatter`'s base implementation, so
`exc_info` and the full traceback are preserved. Verified directly with an
intentional `ZeroDivisionError`.

## Idempotency and reconfiguration

`configure_logging()` is safe to call more than once. It looks for its own
named handler (`sec_rag_console_handler`) on the root logger; if found, it
only updates that handler's level, it never adds a second one. Calling it
repeatedly does not duplicate messages, and changing the level between
calls (e.g. `INFO` → `DEBUG`) takes effect immediately without creating a
new handler. Verified directly: 3 repeated calls left exactly 1 project
handler, one logged event appeared exactly once, and a level change from
`INFO` to `DEBUG` was picked up by the existing handler.

Handlers installed by other libraries are left untouched — this module
only ever looks for and manages the one handler it created itself.

## Output

Console/stderr only in Phase 0 — no file handlers, no `logs/` directory
creation, no rotation, no cloud sinks. `import src.logging_utils` alone
performs zero configuration and zero side effects (no handlers attached,
no directories created, no heavy libraries imported — verified: the import
took ~45ms and left `torch`/`duckdb`/`lancedb`/`sentence_transformers`/
`transformers` all absent from `sys.modules`). `configure_logging()` must
be called explicitly.

Local development sees logs directly in the terminal; Docker/Fargate/Lambda
capture stdout/stderr natively, so no filesystem assumption is needed here.
File/cloud log aggregation is a later concern if actually justified.

## Existing acquisition logging (`src/ingest/`)

Left unmodified. `src/ingest/common.py`'s `setup_logging()` +
`logging.basicConfig(...)` (called once per CLI script's `main()`) and each
acquisition script's extensive `print()`-based report output predate this
module and are self-contained, working CLI tooling — not touched, per the
"data preparation is frozen, don't refactor working ingestion code" rule.
`src/ingest/audit_data.py` additionally writes its own log file
(`phase1_data_audit.log`) as a deliberate, first-class output of that
specific tool — also unrelated to and unaffected by this module. New
application code (Phase 1+) should use `src.logging_utils`; existing
ingestion code is legacy acquisition logging and stays as it is.

## Future work

Request/run correlation (`run_id`, `query_id`, `trace_id`), metrics
(counters, histograms, latency aggregation), distributed tracing, and cloud
log aggregation are all later concerns — none of them exist yet, by design.
`log_event`'s `**fields` already accepts a `run_id`/`stage`/etc. as an
ordinary structured field whenever a caller wants to supply one; no global
context-manager plumbing was built ahead of an actual need.
