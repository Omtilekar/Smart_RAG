# Task 0.6 — Logging

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.6 — Logging
```

Current Phase 0 status:

```text
0.0 Git Safety Preflight       — COMPLETE
0.1 Python Environment         — COMPLETE
0.2 CUDA/GPU Validation        — COMPLETE
0.3 Repository Structure       — COMPLETE
0.4 Dependency Management      — COMPLETE
0.5 Configuration System       — COMPLETE
0.6 Logging                    — CURRENT
```

Task 0.5 established:

```text
src/config.py
get_settings()
load_settings()
LOG_LEVEL
APP_ENV
portable repository/storage roots
.env support
```

The purpose of Task 0.6 is to establish **one consistent application logging convention** before Phase 1 starts producing normalization, chunking, embedding, indexing, retrieval, evaluation, and generation logs.

This task should build a small production-friendly logging foundation using Python's standard library.

It must NOT become an observability-platform project.

---

# OBJECTIVES

Complete only these goals:

1. inspect all current logging behavior,
2. establish one centralized logging utility,
3. integrate it with `LOG_LEVEL` from `src.config`,
4. produce consistent timestamped application logs,
5. support lightweight structured context,
6. make configuration idempotent,
7. prevent duplicate handlers,
8. establish secret-safe logging rules,
9. preserve existing ingestion behavior,
10. document the logging contract,
11. update `Progress.md`.

Do NOT begin:

```text
0.7 Storage Abstraction
0.8 Basic Automated Tests
0.9 Developer Commands
0.10 Serving Feasibility Spike
```

---

# CORE DESIGN PRINCIPLE

The logging system should answer this question:

> If any Phase 1 component emits a log message, will every developer know what fields mean, where the log came from, and how to control verbosity?

Keep the system simple.

Preferred stack:

```text
Python stdlib logging
+
src.config LOG_LEVEL
+
one small project logging utility
```

Do NOT add a logging dependency unless the standard library proves insufficient.

Do not add:

```text
structlog
loguru
OpenTelemetry
Sentry
Datadog
CloudWatch SDK
ELK clients
```

during this task.

---

# STEP 1 — VERIFY PROJECT ENVIRONMENT

Activate:

```text
.venv/
```

and verify:

```bash
python --version
python -c "import sys; print(sys.executable)"
```

Expected:

```text
Python 3.11.9
interpreter inside .venv
```

Also verify:

```python
from src.config import get_settings

print(get_settings().log_level)
```

Do not install any new package unless absolutely necessary.

---

# STEP 2 — INSPECT EXISTING LOGGING

Search the repository for:

```text
import logging
logging.
getLogger
basicConfig
setup_logging
print(
```

Pay particular attention to:

```text
src/ingest/common.py
src/ingest/fetch_msmarco.py
src/ingest/fetch_edgar_corpus.py
src/ingest/fetch_xbrl.py
src/ingest/fetch_primary_docs.py
src/ingest/validate.py
src/ingest/audit_data.py
```

Determine:

```text
how loggers are currently created
whether basicConfig is used
whether handlers are created manually
whether modules log directly
whether acquisition code uses print()
whether logs are written to files
```

Summarize the existing behavior before changing anything.

---

# STEP 3 — PRESERVE WORKING INGESTION CODE

Data Preparation is frozen.

Do not perform a broad logging refactor across:

```text
src/ingest/
```

merely to make old code match the new style.

If existing ingestion logging works independently, it may remain as:

```text
legacy acquisition logging
```

while all new Phase 0/1+ application code uses the centralized logging utility.

Only make a tiny compatibility change to ingestion code if it is clearly necessary and behavior-preserving.

If no change is necessary, leave `src/ingest/` untouched.

Document the distinction.

---

# STEP 4 — CREATE THE CENTRAL LOGGING MODULE

Create:

```text
src/logging_utils.py
```

Do NOT create:

```text
src/logging.py
```

because that name is unnecessarily easy to confuse with Python's standard-library `logging` module.

The module should remain small.

Preferred public API:

```python
configure_logging(...)
get_logger(...)
log_event(...)
```

Adapt names only if there is a clear reason.

---

# STEP 5 — `configure_logging()`

Implement a function conceptually similar to:

```python
def configure_logging(
    level: str | None = None,
) -> None:
    ...
```

If `level` is omitted:

```text
use get_settings().log_level
```

Do not separately read:

```text
os.environ["LOG_LEVEL"]
```

inside the logging module.

The configuration layer already owns that.

---

# STEP 6 — OUTPUT DESTINATION

For Phase 0, application logging should be:

```text
console / stderr
```

only.

Do NOT automatically create:

```text
logs/
```

Do NOT add:

```text
RotatingFileHandler
TimedRotatingFileHandler
file sinks
CloudWatch sinks
```

yet.

Reasons:

```text
local development works naturally
Docker/Fargate/Lambda capture stdout/stderr
no filesystem assumption
no collision with Task 0.7 storage semantics
```

File/cloud observability comes later if justified.

---

# STEP 7 — LOG FORMAT

Use a consistent, machine-readable-enough but human-readable format.

Preferred conceptual output:

```text
2026-08-26T20:14:31.482Z level=INFO logger=src.embeddings event=batch_completed stage=embedding batch=72 processed=23040 elapsed_ms=184
```

Minimum required fields:

```text
UTC timestamp
level
logger/module name
message or event
```

For structured events also support context such as:

```text
stage
run_id
batch
processed
elapsed_ms
count
model
device
```

Do NOT require every possible field.

---

# STEP 8 — USE UTC TIMESTAMPS

Use timezone-aware UTC timestamps.

Preferred representation:

```text
YYYY-MM-DDTHH:MM:SS.sssZ
```

For example:

```text
2026-08-26T20:14:31.482Z
```

Do not emit naive timestamps whose timezone is ambiguous.

Do not rely on local machine timezone for application logs.

---

# STEP 9 — LOG LEVELS

Support standard Python levels:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

Task 0.5 already validates `LOG_LEVEL`.

Expected behavior:

```text
LOG_LEVEL=INFO
    DEBUG suppressed

LOG_LEVEL=DEBUG
    DEBUG visible
```

Do not invent custom log levels.

---

# STEP 10 — LOGGER NAMES

Use:

```python
get_logger(__name__)
```

or equivalent.

Logger names should preserve module provenance, for example:

```text
src.normalize
src.chunk
src.embeddings
src.retrieval
src.eval
```

Do not use one anonymous global logger for the whole application.

---

# STEP 11 — LIGHTWEIGHT STRUCTURED EVENT API

Provide a small helper for structured events.

Conceptually:

```python
log_event(
    logger,
    logging.INFO,
    "embedding_batch_completed",
    stage="embedding",
    batch=72,
    processed=23040,
    elapsed_ms=184,
)
```

Expected output conceptually:

```text
... level=INFO logger=src.embeddings event=embedding_batch_completed stage=embedding batch=72 processed=23040 elapsed_ms=184
```

The exact implementation may differ.

Keep it small.

Do NOT build a generalized schema framework.

---

# STEP 12 — FIELD VALUE SERIALIZATION

Structured values should render predictably.

Support ordinary values such as:

```text
str
int
float
bool
None
Path
```

If a value contains whitespace or special characters, serialize/quote it unambiguously.

Using:

```python
json.dumps(...)
```

for individual structured values is acceptable.

Avoid output where this:

```text
model=some model name
```

becomes ambiguous.

Prefer something like:

```text
model="some model name"
```

---

# STEP 13 — RESERVED / INVALID FIELD NAMES

Prevent structured event keys from accidentally colliding with internal `LogRecord` fields.

Examples include:

```text
name
msg
args
levelname
pathname
filename
module
exc_info
```

Either:

```text
reject reserved structured keys clearly
```

or keep context in a dedicated internal dictionary so collisions cannot occur.

Choose the simpler robust design.

---

# STEP 14 — SECRET-SAFE STRUCTURED FIELDS

The logging utility must never encourage credential logging.

At minimum identify structured field names containing concepts such as:

```text
password
secret
api_key
apikey
token
authorization
credential
```

and replace their values with:

```text
[REDACTED]
```

before formatting.

For example:

```python
log_event(
    logger,
    logging.INFO,
    "provider_initialized",
    api_key="abc123",
)
```

must NOT output:

```text
abc123
```

It should output something conceptually like:

```text
api_key="[REDACTED]"
```

Keep this mechanism lightweight.

---

# STEP 15 — DOCUMENT THE LIMIT OF REDACTION

Do not make a false security claim.

Structured-field redaction cannot reliably sanitize arbitrary secrets embedded inside free-form messages.

Document:

> Never put secrets into log messages. Structured sensitive fields receive defensive redaction, but free-form text is the caller's responsibility.

Do not implement a huge regex-based secret scanner inside the formatter.

---

# STEP 16 — EXCEPTION LOGGING

Standard usage such as:

```python
try:
    ...
except Exception:
    logger.exception("operation failed")
```

must continue to produce a useful traceback.

Your formatter must not break:

```text
exc_info
stack traces
```

Verify this behavior.

---

# STEP 17 — IDEMPOTENT CONFIGURATION

Calling:

```python
configure_logging()
configure_logging()
configure_logging()
```

must NOT produce three copies of every message.

Verify that the application handler is created only once.

If reconfiguration occurs with a different level:

```text
INFO -> DEBUG
```

the existing project handler should update rather than duplicate.

Do not blindly delete unrelated handlers that may have been installed by another application/library.

Manage only handlers owned by this project.

---

# STEP 18 — THIRD-PARTY LOGGER BEHAVIOR

Do not globally silence third-party libraries.

Do not build a large package-by-package noise suppression list.

If one dependency is demonstrably noisy during verification, document it first.

The foundation should default to standard logging behavior.

Later phases may tune:

```text
urllib3
transformers
huggingface
lancedb
```

only if actual noise warrants it.

---

# STEP 19 — IMPORT-TIME SIDE EFFECTS

This must be true:

```python
import src.logging_utils
```

does NOT automatically configure global logging.

Explicit configuration should be required:

```python
configure_logging()
```

Importing the module must not:

```text
create handlers
create directories
open files
load torch
load models
connect to databases
call APIs
```

This makes the module safe to use in libraries/tests.

---

# STEP 20 — CONFIGURATION INTEGRATION

Verify:

```text
LOG_LEVEL=DEBUG
```

through `src.config` changes logging behavior.

Do NOT bypass the centralized settings system.

The desired dependency direction is:

```text
src.config
    ↓
src.logging_utils
    ↓
future application modules
```

not:

```text
every module -> os.environ
```

---

# STEP 21 — CREATE DEMONSTRATION LOG EVENTS

Use a small temporary verification script/process to emit examples such as:

```text
startup
embedding_batch_completed
retrieval_completed
warning example
exception example
```

These are verification examples only.

Do not implement embeddings or retrieval logic.

For example:

```python
logger = get_logger("src.embeddings")

log_event(
    logger,
    logging.INFO,
    "embedding_batch_completed",
    batch=3,
    processed=96,
    elapsed_ms=122,
)
```

is enough.

---

# STEP 22 — VERIFY LEVEL FILTERING

Test at least:

```text
INFO configuration
DEBUG configuration
```

Expected:

At INFO:

```text
DEBUG hidden
INFO visible
WARNING visible
```

At DEBUG:

```text
DEBUG visible
INFO visible
```

Record PASS/FAIL.

---

# STEP 23 — VERIFY DUPLICATE-HANDLER SAFETY

Call:

```python
configure_logging()
```

multiple times.

Emit exactly one known event.

Verify the event appears exactly once.

Then change log level and configure again.

Verify:

```text
handler count remains stable
new level takes effect
```

Record PASS/FAIL.

---

# STEP 24 — VERIFY STRUCTURED CONTEXT

Test fields including:

```text
stage="embedding"
batch=7
processed=224
elapsed_ms=83.4
success=True
model="BAAI/bge-small-en-v1.5"
```

Verify values are represented clearly.

Also test:

```text
None
Path
string with spaces
```

Do not require nested arbitrary objects.

If unsupported types are provided, safely convert with a clear representation rather than throwing an obscure formatter exception.

---

# STEP 25 — VERIFY SECRET REDACTION

Use fake values only.

Test keys such as:

```text
api_key
token
password
authorization
```

Example fake value:

```text
SHOULD_NOT_APPEAR_12345
```

Capture logging output.

Verify the fake secret string does not appear.

Record:

```text
structured-field redaction: PASS
```

Do not use any real secret for this test.

---

# STEP 26 — VERIFY TRACEBACK OUTPUT

Trigger a harmless intentional exception such as:

```python
1 / 0
```

inside a try/except block and log it via:

```python
logger.exception(...)
```

Verify:

```text
error message appears
exception type appears
traceback is preserved
formatter does not crash
```

---

# STEP 27 — VERIFY NO FILE/DIRECTORY SIDE EFFECTS

Before configuring logging, note whether:

```text
logs/
```

exists.

Run logging configuration and emit messages.

Verify no new:

```text
logs/
*.log
```

file was created by the new logging system.

Existing historical root stage logs from Data Preparation are not part of this test.

---

# STEP 28 — VERIFY LIGHTWEIGHT IMPORT

In a fresh process:

```python
import src.logging_utils
```

Inspect whether heavy modules such as:

```text
torch
sentence_transformers
duckdb
lancedb
```

were imported as a side effect.

Expected:

```text
NO
```

Logging infrastructure must remain lightweight.

---

# STEP 29 — DO NOT CREATE LOG FILES

Task 0.6 should NOT create:

```text
logs/app.log
logs/debug.log
logs/rag.log
```

The project's `.gitignore` already reserves:

```text
logs/
```

for runtime-generated content, but no file sink is necessary yet.

Later deployment will capture console logs.

---

# STEP 30 — DO NOT ADD RUN IDs AUTOMATICALLY YET

Do not invent lifecycle concepts before they exist.

Examples:

```text
request_id
query_id
run_id
trace_id
```

may be supplied as structured fields by future code, but Task 0.6 does not need a global context manager for them.

We will introduce request/run correlation when real workflows exist.

---

# STEP 31 — DO NOT IMPLEMENT METRICS

Do not confuse:

```text
logging
```

with:

```text
metrics
```

Do not build:

```text
Prometheus counters
histograms
latency aggregators
OpenTelemetry metrics
dashboard exporters
```

during Task 0.6.

Logging records events.

Evaluation/observability metrics come later.

---

# STEP 32 — DO NOT IMPLEMENT STORAGE

Do not create:

```text
src/storage.py
```

Do not add path helpers.

Do not write logs under `settings.logs_root`.

Task 0.7 owns storage semantics.

This task intentionally remains console-only.

---

# STEP 33 — DOCUMENT THE LOGGING CONTRACT

Create:

```text
project_plan/LOGGING.md
```

Recommended contents:

```markdown
# Logging

## Goals

Consistent, lightweight logs for all application components.

## Configuration

LOG_LEVEL comes from src.config.

## Usage

from src.logging_utils import configure_logging, get_logger, log_event

configure_logging()

logger = get_logger(__name__)

logger.info("service started")

log_event(
    logger,
    logging.INFO,
    "embedding_batch_completed",
    batch=4,
    processed=128,
    elapsed_ms=95,
)

## Format

<example>

## Levels

DEBUG
INFO
WARNING
ERROR
CRITICAL

## Structured fields

Guidelines...

## Secret safety

Never put secrets in messages.
Sensitive structured field names are redacted defensively.

## Exceptions

Use logger.exception(...) inside exception handlers.

## Output

stderr / console only in Phase 0.

## Future work

Request correlation, metrics, cloud log aggregation, tracing are later concerns.
```

Use the actual finalized API.

---

# STEP 34 — UPDATE REPOSITORY DOCUMENTATION IF NECESSARY

Review:

```text
project_plan/REPOSITORY_STRUCTURE.md
project_plan/CONFIGURATION.md
```

Make only small consistency edits if necessary.

For example, `REPOSITORY_STRUCTURE.md` may now note:

```text
src/logging_utils.py — implemented in Phase 0.6
```

and cross-link:

```text
LOGGING.md
```

Do not duplicate the complete logging documentation into multiple files.

---

# STEP 35 — DO NOT MODIFY REQUIREMENTS UNLESS NECESSARY

This task should use Python's standard-library logging.

Expected dependency additions:

```text
none
```

Do not modify:

```text
requirements.txt
requirements-dev.txt
requirements-gpu.txt
```

unless a real technical blocker proves the stdlib insufficient.

If you believe a new dependency is required, stop and explain why before adding it.

---

# STEP 36 — GIT SAFETY CHECK

Run:

```bash
git status --short
git status --ignored --short
git add -n .
git count-objects -vH
```

Do not stage or commit.

Verify:

```text
src/logging_utils.py        trackable
project_plan/LOGGING.md     trackable
Progress.md                 trackable

.venv                       ignored
data                        ignored
.tmp                        ignored
logs/                       ignored
model cache                 ignored
.env                        ignored
```

Ensure no new:

```text
*.log
secret
credential
large binary
```

is unintentionally stageable.

---

# STEP 37 — SECRET SCAN NEW/MODIFIED FILES

Inspect all files created or modified during this task for:

```text
api key values
tokens
passwords
authorization headers
real email addresses
personal absolute filesystem paths
```

Do not print real secret values during inspection or in the final response.

The fake redaction-test value must not be persisted into tracked documentation unless clearly marked as fake and necessary; preferably keep it only in temporary verification code/output.

---

# STEP 38 — UPDATE `Progress.md`

Preserve every existing entry.

Append:

```markdown
## YYYY-MM-DD — Phase 0.6 Logging
```

using the current local date.

Include:

## Objective

Explain why the project established logging before Phase 1 pipeline work.

## Initial State

Summarize:

```text
existing ingestion logging behavior
no centralized future-application logging utility
LOG_LEVEL already centralized by Task 0.5
```

## Design

Record:

```text
module name
public API
console/stderr behavior
UTC timestamp format
logger naming
structured event behavior
secret-redaction behavior
```

## Example

Include one short representative output line.

Do not include secrets or huge traces.

## Verification

Report PASS/FAIL for:

```text
INFO filtering
DEBUG filtering
reconfiguration
duplicate-handler prevention
structured fields
secret redaction
exception traceback
no file creation
lightweight import
config integration
```

## Existing Ingestion Behavior

State clearly whether:

```text
src/ingest/
```

was modified.

If left unchanged:

```text
Existing acquisition logging retained as legacy working behavior; all new application modules use src.logging_utils.
```

## Files Created / Modified

Likely:

```text
src/logging_utils.py
project_plan/LOGGING.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Only list files actually changed.

## Result

Use exactly one:

```text
PASS — centralized logging foundation established

WARN — logging works but one non-blocking issue remains

BLOCKED — logging foundation cannot be established reliably
```

## Phase Status

If PASS:

```text
Data Preparation                  — COMPLETE
Phase 0                           — IN PROGRESS
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — NEXT
```

---

# ACCEPTANCE CRITERIA

Task 0.6 is complete only if:

```text
[ ] existing logging behavior inspected

[ ] src/logging_utils.py exists
[ ] stdlib logging used
[ ] no new logging dependency added

[ ] configure_logging() exists or equivalent
[ ] get_logger() exists or equivalent
[ ] lightweight structured-event helper exists

[ ] LOG_LEVEL comes from src.config
[ ] module does not read LOG_LEVEL directly from os.environ

[ ] UTC timestamp emitted
[ ] level emitted
[ ] logger/module emitted
[ ] structured event/context supported

[ ] DEBUG filtering verified
[ ] INFO filtering verified

[ ] configuration is idempotent
[ ] repeated setup does not duplicate messages
[ ] level can be reconfigured without handler duplication

[ ] exception tracebacks remain usable

[ ] common structured secret-field names are redacted
[ ] fake secret value absent from captured output
[ ] documentation clearly states free-form messages must never contain secrets

[ ] logging writes to console/stderr only
[ ] no logs directory created
[ ] no log files created

[ ] import src.logging_utils has no heavy side effects
[ ] torch not imported by logging module
[ ] database/vector/model systems not initialized

[ ] working ingestion code not unnecessarily refactored

[ ] project_plan/LOGGING.md exists
[ ] documentation consistent with actual API

[ ] Git dry run safe
[ ] Progress.md updated

[ ] no storage abstraction implemented
[ ] no metrics system implemented
[ ] no tracing implemented
[ ] no cloud logging implemented

[ ] no Git commit created
[ ] no Git push performed
[ ] Phase 0.7 work not started
```

---

# STOP CONDITIONS

Stop and report instead of forcing a design if:

```text
existing logging infrastructure already provides a materially different but functional centralized solution

standard-library logging cannot meet a demonstrated project requirement

centralized configuration introduces duplicate output that cannot be resolved without modifying unrelated code

the proposed handler setup interferes materially with existing ingestion logging
```

If existing ingestion logging conflicts with the new system:

1. preserve the exact conflict,
2. identify why it occurs,
3. choose the smallest compatibility fix,
4. avoid broad refactoring.

---

# IMPORTANT NON-GOALS

Task 0.6 does NOT implement:

```text
file logging
log rotation
distributed tracing
OpenTelemetry
metrics
Prometheus
CloudWatch integration
Sentry
request correlation
FastAPI middleware
storage abstraction
RAG features
retrieval
generation
evaluation
deployment
```

The desired output is simply:

```text
one predictable logging convention
```

for future application code.

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.6_logging.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Logging API

Report the actual public interface, for example:

```text
configure_logging()
get_logger()
log_event()
```

## Format

Show one representative log line.

## Output

Confirm:

```text
console/stderr only
no log files created
```

## Configuration

Confirm:

```text
LOG_LEVEL sourced through src.config
```

## Verification

Report PASS/FAIL for:

```text
INFO filtering
DEBUG filtering
duplicate-handler prevention
reconfiguration
structured fields
secret redaction
exception traceback
lightweight import
no filesystem side effects
```

## Existing Ingestion Logging

State whether `src/ingest/` was modified and why.

## Documentation

Confirm:

```text
project_plan/LOGGING.md
```

exists.

## Files Modified

List tracked/project files only.

## Git Safety

Confirm:

```text
no data staged
no .env staged
no logs staged
no secrets staged
no large binaries staged
```

## Progress.md

Confirm the Phase 0.6 entry was appended.

## Next Task

If PASS:

```text
task_0.7_storage_abstraction.md
```

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 0.7 work started.
```

Stop and wait for my approval.