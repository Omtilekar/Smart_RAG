# Configuration

`src/config.py` is the single, typed, environment-aware configuration
boundary for this project. Future modules should call `get_settings()`
instead of reading `os.environ` directly — that's how hardcoded paths,
model names, and environment-specific values stay out of the codebase as
implementation spreads across `src/normalize/`, `src/chunk/`,
`src/embeddings/`, `src/retrieval/`, etc.

## Why centralized

Before this task, only `src/ingest/common.py` read environment variables
directly (`STORAGE_ROOT`, `SEC_USER_AGENT`, `SEC_RPS`) — fine for one
module, not scalable once a dozen modules each need paths, a device
setting, and a model name. `common.py` was deliberately **not** rewritten
to use `src.config` in this task (Task 0.5's scope is establishing the
boundary, not refactoring working acquisition code for a change that isn't
tiny) — new code should consume `get_settings()`; `common.py`'s direct
`os.getenv()` calls remain as a known, harmless legacy path.

## Settings

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `APP_ENV` | `development` | No | `development` \| `test` \| `production` |
| `STORAGE_ROOT` | `<repo>/data` | No | Local storage root; portable/repo-relative by default |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | No | Phase 1 baseline embedding model |
| `DEVICE` | `auto` | No | `auto` \| `cuda` \| `cpu` — see below |
| `GENERATION_PROVIDER` | (none) | No | Optional until Phase 1 generation is implemented |
| `GENERATION_MODEL` | (none) | No | Optional until Phase 1 generation is implemented |
| `LOG_LEVEL` | `INFO` | No | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` \| `CRITICAL` — consumed by `src/logging_utils.py`, see `project_plan/LOGGING.md` |
| `SEC_USER_AGENT` | (none) | Only for SEC network access | Public contact identity SEC requires in the User-Agent header — not a secret, but keep your real one out of tracked files |

Nothing is required just to import `src.config` or call `get_settings()` —
every field has a safe default or resolves to `None`. A field becomes
"required" only when the code path that actually needs it runs (e.g.
`SEC_USER_AGENT` is read by `src/ingest/common.py` only when a request is
about to be made, not at import time).

## `.env` handling

`.env.example` is committed and safe — variable names and non-secret
placeholders/defaults only. **`.env` is git-ignored and must never be
committed.** Copy `.env.example` to `.env` locally and fill in real values.

### Precedence

```text
process/shell environment  >  .env  >  code default
```

Implemented via `python-dotenv`'s `load_dotenv(..., override=False)` —
its default behavior already never overrides a variable already present in
`os.environ`, so a real shell/CI-supplied value always wins over `.env`
without any extra logic. Verified directly (Task 0.5): a process env
`LOG_LEVEL` beat a conflicting `.env` value, and an `.env`-only `APP_ENV`
beat the code default when no process value was set.

## Path resolution

`repo_root` is derived from `src/config.py`'s own file location
(`Path(__file__).resolve().parent.parent`) — never hardcoded, portable
across machines and clone locations. `storage_root` defaults to
`<repo_root>/data` (matching the existing `src/ingest/` convention) and can
be overridden via `STORAGE_ROOT`; either way it is resolved to an absolute
path but **never created** — loading settings performs no filesystem
writes. Verified directly: pointing `STORAGE_ROOT` at a path that does not
exist and loading settings leaves that path un-created.

This task determines the roots only. Detailed artifact paths (`chunks/`,
`index/`, `eval.duckdb`, etc.) are `src/storage.py`'s job (Task 0.7,
implemented — see `project_plan/STORAGE.md`), not this file's.

## Device

`DEVICE` is stored as the raw requested string (`auto`/`cuda`/`cpu`) on
`Settings` — resolving it doesn't happen at config-load time, to keep
`import src.config` free of any CUDA initialization. Call
`resolve_device(settings.device)` when you actually need a concrete torch
device string:

- `"cpu"` → `"cpu"`
- `"cuda"` → `"cuda"` (returned as-is, even if CUDA turns out to be
  unavailable — the next real torch call then fails loudly and
  specifically, rather than this function silently downgrading an explicit
  request to CPU)
- `"auto"` → `"cuda"` if `torch.cuda.is_available()`, else `"cpu"` (`torch`
  is imported lazily, inside this function only)

Verified: `import src.config` alone never puts `torch` in `sys.modules`
(35 ms import); `resolve_device()` correctly resolved `auto`→`cuda` on this
machine's validated GPU, and `cuda`/`cpu` passed through literally.

## Secrets

No API-key field exists on `Settings` at all — this is a deliberate design
choice (Task 0.5, Step 19's "simpler secure option"), not an oversight.
`GENERATION_PROVIDER`/`GENERATION_MODEL` describe *which* provider/model to
use; the credential itself (e.g. `OPENAI_API_KEY`) will be read directly
from the environment by whatever provider-client module implements that
integration later, only when it's actually needed. This means `Settings`
can never leak a credential through `repr()`, logging, or accidental
printing, because it never holds one. `.env.example` documents this pattern
with commented-out example variable names rather than active ones, since no
generation provider is committed to yet.

`SEC_USER_AGENT` is on `Settings` because it is not a secret — it's a
public contact string SEC requires in request headers, not an
authentication credential — but it should still never be a real value in a
tracked file (see `.env.example`'s placeholder and `Progress.md`'s
Task 0.1 entry, where a historical real value was sanitized out).

## Validation

`load_settings()` rejects invalid values immediately and specifically via
`ConfigError` (a `ValueError` subclass) — invalid `APP_ENV`, `LOG_LEVEL`, or
`DEVICE` each raise a clear message naming the variable, the bad value, and
the allowed set. No external connectivity, API calls, or model-availability
checks are performed — validation is deterministic and cheap, matching
`import src.config`'s lightweight-import requirement.

## API

```python
from src.config import get_settings

settings = get_settings()          # cached (functools.lru_cache)
settings.storage_root              # -> Path
settings.embedding_model           # -> str
```

`get_settings()` caches after the first successful load. Code (tests, or
anything that mutates `os.environ` at runtime) that needs a fresh read
after changing the environment should call `get_settings.cache_clear()`
first — this is the documented, supported reset mechanism, verified
directly in Task 0.5.

For a one-off uncached read (rarely needed), `load_settings()` is available
directly.
