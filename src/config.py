"""Single, typed, environment-aware configuration boundary.

Future modules should call `get_settings()` instead of reading `os.environ`
directly. Historical `src/ingest/common.py` still reads `STORAGE_ROOT` and
`SEC_USER_AGENT` from the environment on its own (it predates this module) -
left as-is deliberately; not rewritten here.

Precedence: process environment > `.env` > code default. `load_dotenv()`'s
default behavior already implements this - it never overrides a variable
that's already set in `os.environ`, so a real shell/CI value always wins
over `.env`.

Importing this module must stay cheap: no directory creation, no network
calls, no CUDA initialization, no DB connections. `get_settings()` only
reads environment variables and validates them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_VALID_APP_ENVS = {"development", "test", "production"}
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_VALID_DEVICES = {"auto", "cuda", "cpu"}

# Task 4.7 - input-guardrail request-length hard limit. PROJECT_SPEC.md's
# "## 8. Guardrails" table names "Length cap | Hard limit" but no concrete
# number anywhere in the repository - 2000 was an explicit user decision
# (2026-09-16), not invented silently: generous for a real financial
# question, far under Qwen3-Embedding-0.6B's 32,768-token max_seq_length
# (src.embeddings.model_registry.QWEN3_EMBEDDING), small enough to bound
# abuse/spam input.
DEFAULT_INPUT_GUARD_MAX_LENGTH = 2000

# Repo root = parent of src/ (this file lives at src/config.py).
_REPO_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(ValueError):
    """Raised when an environment variable holds an invalid configuration value."""


@dataclass(frozen=True)
class Settings:
    app_env: str
    repo_root: Path
    storage_root: Path

    embedding_model: str
    device: str

    generation_provider: str | None
    generation_model: str | None

    log_level: str

    sec_user_agent: str | None

    input_guard_max_length: int


def _require_choice(name: str, value: str, choices: set[str]) -> str:
    if value not in choices:
        raise ConfigError(
            f"{name}={value!r} is invalid. Expected one of: {sorted(choices)}"
        )
    return value


def load_settings() -> Settings:
    """Build Settings from the current environment (+ .env if present).

    Does not cache - see get_settings() for the cached entry point future
    code should actually use.
    """
    # override=False (the default): a value already in os.environ always
    # wins over .env, so process/shell env has the final say.
    load_dotenv(_REPO_ROOT / ".env", override=False)

    app_env = _require_choice("APP_ENV", os.getenv("APP_ENV", "development"), _VALID_APP_ENVS)
    log_level = _require_choice("LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO").upper(), _VALID_LOG_LEVELS)
    device = _require_choice("DEVICE", os.getenv("DEVICE", "auto"), _VALID_DEVICES)

    storage_root_raw = os.getenv("STORAGE_ROOT", "").strip()
    storage_root = Path(storage_root_raw) if storage_root_raw else (_REPO_ROOT / "data")
    storage_root = storage_root.expanduser().resolve()

    embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5").strip()
    if not embedding_model:
        raise ConfigError("EMBEDDING_MODEL must not be empty")

    generation_provider = os.getenv("GENERATION_PROVIDER", "").strip() or None
    generation_model = os.getenv("GENERATION_MODEL", "").strip() or None

    sec_user_agent = os.getenv("SEC_USER_AGENT", "").strip() or None

    input_guard_max_length_raw = os.getenv("INPUT_GUARD_MAX_LENGTH", "").strip()
    if input_guard_max_length_raw:
        try:
            input_guard_max_length = int(input_guard_max_length_raw)
        except ValueError:
            raise ConfigError(
                f"INPUT_GUARD_MAX_LENGTH={input_guard_max_length_raw!r} is invalid. Expected a positive integer."
            ) from None
        if input_guard_max_length <= 0:
            raise ConfigError(
                f"INPUT_GUARD_MAX_LENGTH={input_guard_max_length} is invalid. Expected a positive integer."
            )
    else:
        input_guard_max_length = DEFAULT_INPUT_GUARD_MAX_LENGTH

    return Settings(
        app_env=app_env,
        repo_root=_REPO_ROOT,
        storage_root=storage_root,
        embedding_model=embedding_model,
        device=device,
        generation_provider=generation_provider,
        generation_model=generation_model,
        log_level=log_level,
        sec_user_agent=sec_user_agent,
        input_guard_max_length=input_guard_max_length,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Tests that need a fresh read after changing
    the environment should call get_settings.cache_clear() first."""
    return load_settings()


def resolve_device(requested: str) -> str:
    """Translate a requested device ("auto"/"cuda"/"cpu") into an actual
    torch device string. Imports torch lazily so importing src.config never
    pulls in torch/CUDA initialization.

    "cuda" is returned as-is even if CUDA turns out to be unavailable - the
    resulting torch call fails loudly and specifically at that point, rather
    than this function silently downgrading an explicit request to CPU.
    """
    if requested == "cpu":
        return "cpu"
    if requested == "cuda":
        return "cuda"
    if requested == "auto":
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    raise ConfigError(f"DEVICE={requested!r} is invalid. Expected one of: {sorted(_VALID_DEVICES)}")
