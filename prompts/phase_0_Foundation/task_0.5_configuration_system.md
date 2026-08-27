# Task 0.5 — Configuration System

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.5 — Configuration System
```

Previous Phase 0 status:

```text
0.0 Git Safety Preflight       — COMPLETE
0.1 Python Environment         — COMPLETE
0.2 CUDA/GPU Validation        — COMPLETE
0.3 Repository Structure       — COMPLETE
0.4 Dependency Management      — COMPLETE
0.5 Configuration System       — CURRENT
```

Current environment is already reproducible:

```text
Python:                 3.11.9
Virtual environment:    .venv/
PyTorch:                2.13.0+cu130
CUDA runtime:           13.0
GPU:                    NVIDIA GeForce RTX 5060 Laptop GPU
Dependencies:           reproduced successfully from requirements files
```

The purpose of this task is to establish a **single, typed, environment-aware configuration system** so future modules do not scatter:

```text
hardcoded paths
model names
API keys
storage roots
device settings
log levels
environment-specific values
```

throughout the codebase.

This task owns:

```text
src/config.py
.env.example
configuration documentation
configuration validation
Progress.md update
```

This task does NOT own:

```text
src/storage.py
logging implementation
retrieval configuration files
chunking configuration
FastAPI
LLM provider implementation
API calls
deployment
```

Do not begin Task 0.6 or later work.

---

# CORE PRINCIPLES

The configuration layer must follow these rules:

```text
1. Secrets come from environment variables.
2. Public defaults may live in code.
3. Paths are resolved from one project/storage root.
4. Configuration is typed and validated.
5. Importing config must not perform expensive work.
6. Importing config must not create directories automatically.
7. No API key may be committed.
8. No personal absolute filesystem path may be committed.
9. Configuration must be usable locally now and adaptable to S3 later.
10. Future modules should consume config instead of reading os.environ directly.
```

Keep it deliberately small.

Do not create an enterprise configuration framework.

---

# STEP 1 — VERIFY CURRENT STATE

From repository root inspect:

```text
src/
project_plan/
configs/
.env
.env.example
src/config.py
requirements.txt
.gitignore
Progress.md
```

Determine whether any configuration implementation already exists.

Do not overwrite an existing functional configuration module blindly.

Expected state from prior tasks:

```text
src/config.py     absent
.env              absent
.env.example      absent
python-dotenv     installed
```

Verify rather than assume.

---

# STEP 2 — ACTIVATE THE PROJECT ENVIRONMENT

Activate:

```text
.venv/
```

and verify:

```bash
python --version
python -c "import sys; print(sys.executable)"
python -c "import dotenv; print('python-dotenv import: OK')"
```

Expected:

```text
Python 3.11.9
interpreter inside .venv
python-dotenv import succeeds
```

Do not install additional packages unless the configuration implementation genuinely requires one.

Prefer using:

```text
standard library
+
python-dotenv
+
dataclasses
```

or similarly lightweight tools already available.

Do not add Pydantic Settings merely because FastAPI uses Pydantic later unless there is a clear need.

---

# STEP 3 — INSPECT CURRENT PATH USAGE

Search current source code for:

```text
data/
data/xbrl.duckdb
absolute filesystem paths
os.environ
Path(...)
SEC_USER_AGENT
model names
API-related environment variables
```

Identify existing hardcoded values.

Do not refactor all ingestion code during this task.

The purpose is to understand what configuration needs to support going forward.

Record any historical code that still reads environment variables directly, but do not rewrite working acquisition modules unless the change is tiny and clearly necessary.

---

# STEP 4 — DEFINE THE CONFIGURATION CONTRACT

Create one authoritative configuration object in:

```text
src/config.py
```

Prefer a simple immutable/frozen dataclass or similarly small typed structure.

Conceptually:

```python
@dataclass(frozen=True)
class Settings:
    environment: str
    storage_root: Path
    data_root: Path
    artifacts_root: Path
    logs_root: Path

    embedding_model: str
    device: str

    generation_provider: str | None
    generation_model: str | None

    log_level: str

    sec_user_agent: str | None
```

Adapt this carefully to the actual project needs.

Do not include fields merely because they might be useful someday.

---

# STEP 5 — DEFINE ONLY PHASE-0 / PHASE-1 SETTINGS

At minimum consider:

```text
APP_ENV
STORAGE_ROOT

EMBEDDING_MODEL
DEVICE

GENERATION_PROVIDER
GENERATION_MODEL

LOG_LEVEL

SEC_USER_AGENT
```

Potential future API keys may be represented by environment variable names in `.env.example`, but do not force them to exist before they are actually needed.

For example, depending on the intended provider:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
```

should only be included if the project plan currently expects those providers.

Do not fill them with fake-looking secret strings that could be mistaken for real credentials.

Use blank values.

---

# STEP 6 — ESTABLISH `STORAGE_ROOT`

The most important path setting is:

```text
STORAGE_ROOT
```

Default behavior should be repository-relative and portable.

For local development, a reasonable default is conceptually:

```text
<repo>/data
```

or the exact existing project convention.

Do NOT encode:

```text
C:\Users\<name>\...
```

or another machine-specific absolute path.

Derive repository root programmatically from the location of the source tree where practical.

The configuration layer should expose clear paths such as:

```text
repo_root
storage_root
data_root
artifacts_root
logs_root
```

but do not implement the full path catalog owned by:

```text
task_0.7_storage_abstraction.md
```

Task 0.5 determines the roots.

Task 0.7 determines detailed artifact locations.

---

# STEP 7 — PATH OVERRIDE BEHAVIOR

Support overriding:

```text
STORAGE_ROOT
```

through the environment.

Verify both:

```text
default repository-relative behavior
custom environment-variable behavior
```

Paths should be normalized/resolved consistently.

Do not require the path to already contain every future artifact.

Do not create directories merely by loading settings.

---

# STEP 8 — DEVICE CONFIGURATION

The current machine has a validated CUDA GPU, but configuration must not assume every clone does.

Support:

```text
DEVICE=auto
DEVICE=cuda
DEVICE=cpu
```

or an equivalently simple contract.

Recommended semantics:

```text
auto
    choose CUDA if available, otherwise CPU

cuda
    explicitly request CUDA

cpu
    explicitly request CPU
```

However, avoid importing torch at module import time solely to decide this if doing so makes configuration heavy.

A reasonable design is:

```text
configuration stores requested_device
```

and runtime code resolves it later.

If you do provide a helper such as:

```python
resolve_device()
```

keep it lightweight and testable.

Do not silently turn:

```text
DEVICE=cuda
```

into CPU.

Explicit CUDA should fail clearly later if unavailable.

---

# STEP 9 — MODEL DEFAULTS

Current Phase 1 baseline uses:

```text
BAAI/bge-small-en-v1.5
```

So expose an embedding-model setting with that as the current default.

Example conceptually:

```text
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

Do not encode this model name independently in several future modules.

Do not decide the final Phase 3 embedding model here.

This is a baseline default, not a production architecture freeze.

---

# STEP 10 — GENERATION CONFIGURATION

Phase 1 will eventually use an API LLM.

Create configuration fields that can represent:

```text
provider
model
API key environment variable
```

without implementing a provider client.

For example:

```text
GENERATION_PROVIDER=
GENERATION_MODEL=
```

Keep these optional until Phase 1 generation actually needs them.

Do not raise an error on application configuration load merely because no LLM API key exists yet.

Configuration validation should distinguish:

```text
required now
vs
required only when a feature is invoked
```

---

# STEP 11 — SEC USER AGENT

The existing ingestion code historically used:

```text
SEC_USER_AGENT
```

Treat it as environment configuration.

Do not commit a personal value.

`.env.example` should use either:

```text
SEC_USER_AGENT=
```

or a clearly generic explanatory placeholder such as:

```text
SEC_USER_AGENT="Your Name your.email@example.com"
```

Do not put my real name/email into tracked files.

Do not require `SEC_USER_AGENT` merely to import the config module.

It should only become required when code attempts SEC network access.

---

# STEP 12 — LOG LEVEL

Expose:

```text
LOG_LEVEL
```

with a sane default such as:

```text
INFO
```

Validate acceptable common values:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

Do not implement logging itself.

That belongs to:

```text
task_0.6_logging.md
```

The configuration system only supplies the setting.

---

# STEP 13 — ENVIRONMENT NAME

Support a simple application environment field such as:

```text
APP_ENV=development
```

Allowed values may be something small like:

```text
development
test
production
```

Do not build separate YAML stacks for each environment.

Environment variables are sufficient for Phase 0.

---

# STEP 14 — LOAD `.env` SAFELY

Use:

```text
python-dotenv
```

to load a repository-root:

```text
.env
```

when present.

Important behavior:

```text
real process environment variables should take precedence over .env
```

Do not override explicitly supplied shell/environment values.

No `.env` file needs to exist for configuration to load with public defaults.

---

# STEP 15 — CREATE `.env.example`

Create root:

```text
.env.example
```

This file must be tracked by Git.

Include variable names and safe example/default values only.

A reasonable shape may be:

```dotenv
# Application
APP_ENV=development
LOG_LEVEL=INFO

# Storage
STORAGE_ROOT=

# Models
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
DEVICE=auto

# Generation
GENERATION_PROVIDER=
GENERATION_MODEL=

# Credentials / external services
SEC_USER_AGENT="Your Name your.email@example.com"

# Add provider API-key variable names only if the project currently uses them.
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
```

Adapt to actual current provider plans.

Do not put real credentials into this file.

---

# STEP 16 — VERIFY `.env` IGNORE RULES

Run:

```bash
git check-ignore -v .env
git check-ignore -v .env.example
```

Expected:

```text
.env          ignored
.env.example  NOT ignored
```

If `.env.example` is incorrectly ignored because of an existing broad pattern:

fix `.gitignore` minimally.

Do not weaken secret protection.

---

# STEP 17 — CONFIGURATION API DESIGN

The public API of `src/config.py` should be obvious.

A reasonable design is:

```python
settings = load_settings()
```

or:

```python
get_settings()
```

Avoid surprising global side effects.

If caching is used, keep it explicit and easy to reset for tests later.

Potential pattern:

```python
@lru_cache
def get_settings() -> Settings:
    ...
```

If you use caching, provide a documented way for future tests to clear it:

```python
get_settings.cache_clear()
```

Do not overengineer dependency injection.

---

# STEP 18 — VALIDATION RULES

Implement lightweight validation for things configuration can reasonably reject now.

Examples:

```text
invalid APP_ENV
invalid LOG_LEVEL
empty EMBEDDING_MODEL
unsupported DEVICE value
malformed path value
```

Do not validate external connectivity.

Do not call APIs.

Do not attempt to verify model availability.

Do not require the XBRL DB to exist merely to load configuration.

Configuration validation should be deterministic and cheap.

---

# STEP 19 — SECRET-SAFE REPRESENTATION

Be careful with:

```python
repr(settings)
print(settings)
logging settings
```

If the settings object later carries secrets, those values must not be accidentally exposed.

If API keys are included directly as fields now, use a mechanism that prevents their values from appearing in representations.

An even cleaner Phase 0 design is to keep only:

```text
provider/model configuration
```

in the main settings object and retrieve provider credentials from environment variables when the corresponding integration is implemented.

Choose the simpler secure option.

Document the decision.

---

# STEP 20 — DO NOT CREATE `.env` WITH SECRETS

Do not create a real:

```text
.env
```

unless needed strictly for a test.

If a temporary `.env` is necessary to verify dotenv behavior:

1. use fake non-secret values,
2. verify it is ignored,
3. remove it afterward.

Prefer testing via temporary environment variables instead.

---

# STEP 21 — VERIFY DEFAULT CONFIGURATION

With no relevant environment overrides, run something equivalent to:

```python
from src.config import get_settings

settings = get_settings()

print(settings.app_env)
print(settings.storage_root)
print(settings.embedding_model)
print(settings.device)
print(settings.log_level)
```

Verify:

```text
defaults load
paths resolve
no secret required
no directory created unexpectedly
```

Do not print any secret-bearing values.

---

# STEP 22 — VERIFY ENVIRONMENT OVERRIDES

In a child process or controlled environment, set temporary values such as:

```text
APP_ENV=test
LOG_LEVEL=DEBUG
DEVICE=cpu
EMBEDDING_MODEL=test-model
STORAGE_ROOT=<temporary safe path>
```

Then load settings.

Verify every override is respected.

Do not mutate the developer's permanent system environment.

---

# STEP 23 — VERIFY ENVIRONMENT PRECEDENCE OVER `.env`

If practical, verify:

```text
shell/process env
>
.env
>
code default
```

Use safe fake values.

For example:

```text
.env says LOG_LEVEL=INFO
process says LOG_LEVEL=DEBUG
```

Expected:

```text
DEBUG
```

Delete the temporary `.env` afterward if one was created.

---

# STEP 24 — VERIFY INVALID CONFIGURATION FAILS CLEARLY

Test representative invalid values:

```text
APP_ENV=banana
LOG_LEVEL=LOUD
DEVICE=tpu
```

Each should fail with an understandable exception/message.

Do not expose internal stack noise as the only explanation.

Do not silently coerce arbitrary invalid values.

---

# STEP 25 — VERIFY IMPORTS ARE LIGHTWEIGHT

Importing:

```python
import src.config
```

must not:

```text
load a model
connect to DuckDB
connect to LanceDB
create directories
call the network
initialize CUDA
```

Verify this by inspecting the implementation and behavior.

The configuration module should remain near-instant.

---

# STEP 26 — DOCUMENT CONFIGURATION

Create:

```text
project_plan/CONFIGURATION.md
```

Explain:

```text
why configuration is centralized
which settings exist
which have defaults
which come from environment variables
how .env works
environment precedence
how paths are resolved
how secrets are handled
how future modules should consume settings
```

Include a compact table such as:

| Variable | Default | Required | Purpose |
|---|---|---|---|
| APP_ENV | development | No | runtime environment |
| STORAGE_ROOT | repo-relative | No | local storage root |
| EMBEDDING_MODEL | BAAI/... | No | Phase 1 baseline |
| DEVICE | auto | No | requested compute device |
| LOG_LEVEL | INFO | No | logging verbosity |
| SEC_USER_AGENT | none | only for SEC access | SEC request identity |

Adapt to actual final settings.

Explain clearly:

> `.env.example` is safe to commit; `.env` is not.

---

# STEP 27 — UPDATE OTHER DOCUMENTATION ONLY IF NECESSARY

Review:

```text
project_plan/ENVIRONMENT.md
project_plan/DEPENDENCIES.md
project_plan/REPOSITORY_STRUCTURE.md
```

Update only tiny references where necessary.

Do not duplicate `CONFIGURATION.md` inside each file.

Cross-linking is better than copying.

---

# STEP 28 — DO NOT IMPLEMENT STORAGE

Do not create:

```text
src/storage.py
```

or detailed path helpers such as:

```text
chunks_path()
index_path()
eval_path()
```

Those belong to:

```text
task_0.7_storage_abstraction.md
```

Task 0.5 owns:

```text
configuration roots
```

Task 0.7 owns:

```text
artifact path semantics
```

Keep that boundary clean.

---

# STEP 29 — DO NOT IMPLEMENT LOGGING

Do not create logging formatters, file handlers, JSON logs, or pipeline logger utilities.

Only expose:

```text
LOG_LEVEL
```

and perhaps environment configuration needed by Task 0.6.

Logging implementation is:

```text
task_0.6_logging.md
```

---

# STEP 30 — DO NOT WRITE THE FULL TEST SUITE

Task 0.8 owns formal tests.

For this task, small direct verification scripts/commands are allowed.

Do not populate:

```text
tests/
```

with the full automated test suite yet.

If a tiny temporary script is needed during implementation, remove it afterward unless it is genuinely part of the future developer tooling.

---

# STEP 31 — GIT SAFETY CHECK

Run:

```bash
git status --short
git status --ignored --short
git add -n .
git count-objects -vH
```

Do not actually stage.

Verify:

```text
src/config.py           trackable
.env.example            trackable
CONFIGURATION.md        trackable
Progress.md             trackable

.env                    ignored
.venv                   ignored
data                    ignored
.tmp                    ignored
model cache             ignored
```

Search the dry-run stage list for anything resembling:

```text
API keys
credentials
personal filesystem paths
real SEC contact
model weights
data files
```

There must be none.

---

# STEP 32 — SECRET SCAN OF NEW FILES

Before finishing, inspect all files created/modified in this task for:

```text
sk-
api_key
secret
password
token
Bearer
real email addresses
AWS credentials
absolute personal paths
```

Do not print potential secrets to the final response.

If a real secret is found in a new tracked file:

remove it immediately and report that a secret-safety correction was made.

If the secret appears in old project history/content outside this task, do not silently rewrite history; report it for review unless it is the already-authorized placeholder sanitization case.

---

# STEP 33 — UPDATE `Progress.md`

Preserve all previous content.

Append:

```markdown
## YYYY-MM-DD — Phase 0.5 Configuration System
```

using the current local date.

Include:

## Objective

Explain that this task established the centralized configuration boundary for future modules.

## Initial State

Record:

```text
no src/config.py
no .env.example
python-dotenv already installed
paths/model settings otherwise not centralized
```

Use actual observed state.

## Configuration Design

Record:

```text
configuration object/API
environment precedence
default behavior
validation strategy
secret-handling strategy
```

## Settings

Include a compact table of actual final fields/defaults.

## Path Behavior

Record:

```text
repository-root detection
default STORAGE_ROOT
override behavior
directory creation behavior
```

Make clear that detailed storage paths remain Task 0.7.

## Verification

Record PASS/FAIL for:

```text
default load
environment override
dotenv precedence
invalid value rejection
.env ignored
.env.example trackable
import side effects absent
```

## Files Created / Modified

Likely:

```text
src/config.py
.env.example
project_plan/CONFIGURATION.md
Progress.md
```

and possibly a small documentation cross-link or `.gitignore` correction.

List only actual changes.

## Result

Use exactly one:

```text
PASS — centralized configuration system established

WARN — configuration works but one non-blocking issue remains

BLOCKED — configuration contract cannot be established reliably
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
  0.6 Logging                     — NEXT
```

---

# ACCEPTANCE CRITERIA

Task 0.5 is complete only if:

```text
[ ] src/config.py exists
[ ] configuration is typed
[ ] configuration has no expensive import-time side effects

[ ] repository root is determined portably
[ ] STORAGE_ROOT has a portable default
[ ] STORAGE_ROOT can be overridden
[ ] loading settings does not create directories

[ ] APP_ENV supported and validated
[ ] LOG_LEVEL supported and validated
[ ] DEVICE supported and validated
[ ] EMBEDDING_MODEL centralized
[ ] generation provider/model represented without forcing credentials
[ ] SEC_USER_AGENT represented safely

[ ] .env loading works
[ ] process environment overrides .env
[ ] .env overrides code defaults
[ ] .env is ignored
[ ] .env.example is trackable
[ ] no real secrets exist in .env.example

[ ] invalid configuration fails clearly
[ ] configuration can load without an API key
[ ] configuration can load without SEC_USER_AGENT
[ ] secrets are not printed accidentally

[ ] project_plan/CONFIGURATION.md exists

[ ] no src/storage.py created
[ ] no logging implementation created
[ ] no API client implemented
[ ] no tests suite implemented
[ ] no RAG functionality implemented

[ ] Git dry-run contains no secrets/data/models
[ ] Progress.md updated

[ ] no Git commit created
[ ] no Git push performed
[ ] Phase 0.6 work not started
```

---

# STOP CONDITIONS

Stop and report rather than hiding the problem if:

```text
configuration requires machine-specific paths
.env.example would need real credentials
environment precedence behaves incorrectly
configuration import performs expensive work
an existing configuration implementation conflicts materially with this design
a dependency addition would be required solely to create an overcomplicated settings framework
```

Choose the smallest reliable design.

---

# IMPORTANT NON-GOALS

This task does NOT:

```text
implement storage paths beyond root settings
implement logging
implement model loading
implement generation clients
call an LLM API
connect to SEC
connect to DuckDB
connect to LanceDB
create chunks
create indexes
write automated test suite
build FastAPI
deploy anything
```

The primary output is:

```text
one trustworthy configuration boundary
```

that later modules can depend on.

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.5_configuration_system.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Configuration API

Report the public interface, for example:

```text
Settings
get_settings()
```

Use the actual implementation.

## Settings

Summarize the finalized settings and defaults.

## Environment Precedence

Confirm:

```text
process environment > .env > code defaults
```

or report the actual tested behavior.

## Path Configuration

Report:

```text
default STORAGE_ROOT
override tested: yes/no
directory creation on config load: yes/no
```

Do not expose personal absolute paths.

## Secret Safety

Confirm:

```text
.env ignored
.env.example tracked
no real credentials added
configuration loads without secrets
```

## Verification

Report PASS/FAIL for:

```text
default load
environment override
dotenv precedence
invalid-value rejection
lightweight import
Git safety
```

## Files Modified

List tracked/project files only.

## Progress.md

Confirm the Phase 0.5 entry was appended.

## Next Task

If PASS:

```text
task_0.6_logging.md
```

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 0.6 work started.
```

Stop and wait for my approval.