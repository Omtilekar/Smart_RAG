"""Task 4.10 - typed request/response models for the FastAPI service.

Pydantic models only - no business logic. "Define request/response
models" is one of PROJECT_EXECUTION.md's own three Task 4.10 bullets.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# 2026-09-16 explicit user decision: a guard rejection (input, or the
# already-existing context/output guards inside the dense pipeline) is
# represented as HTTP 200 with a typed refusal body, never a 4xx/5xx -
# the HTTP request itself is well-formed; a guard refusal is an expected
# business outcome, not a transport error. Clients always parse the same
# JSON shape regardless of outcome.
STATUS_ANSWERED = "answered"
STATUS_REJECTED = "rejected"


class QueryRequest(BaseModel):
    """The user's exact question string, preserved unchanged for Task
    4.7's input guard - this model performs no stripping/rewriting of
    `question` itself (Pydantic's own str type does not trim whitespace)."""
    question: str = Field(..., description="Natural-language question about the SEC filing corpus.")


class QueryResponse(BaseModel):
    """Uniform response shape across both the dense and structured-XBRL
    routes (`route` tells a client which one produced this answer).

    `citations` holds `[chunk_id]`-shaped strings for `route="dense"`
    (the frozen Task 1.7 citation identity) and SEC accession numbers
    (`adsh`) for `route="structured_xbrl"` - a different identity space,
    distinguishable via `route`, never silently mixed without a way to
    tell them apart. Never populated on `status="rejected"`.

    Never exposes: embeddings, raw retrieval vectors, the provider's raw
    response, the system prompt, full retrieved context, filesystem
    paths, or stack traces."""
    status: str = Field(..., description=f"'{STATUS_ANSWERED}' or '{STATUS_REJECTED}'.")
    answer: str | None = Field(None, description="Present only when status='answered'.")
    citations: list[str] = Field(default_factory=list)
    route: str | None = Field(None, description="'dense' or 'structured_xbrl'. None when status='rejected'.")
    reason_code: str | None = Field(None, description="Stable guard reason code, present only when status='rejected'.")
    request_id: str


class HealthResponse(BaseModel):
    """Liveness only - the process is running. Never performs a
    dependency check (that is /status's job)."""
    status: str = "ok"


class RetrievalSecurityTelemetryResponse(BaseModel):
    """Aggregate retrieval-security counters only. Never includes raw
    user queries or retrieved text."""
    scans: int
    candidate_count: int
    approved_candidates: int
    suspicious_candidates: int
    blocked_candidates: int
    missing_provenance_count: int
    invalid_source_count: int
    duplicate_candidates_collapsed: int
    poison_signal_count: int
    obfuscation_signal_count: int
    all_context_blocked_count: int


class RetrievalSecurityStatusResponse(BaseModel):
    """Deterministic query-time retrieval-security status."""
    enabled: bool
    mode: str
    scanner_version: str
    policy_version: str
    text_scan_scope: str
    xbrl_policy: str
    telemetry: RetrievalSecurityTelemetryResponse


class StatusResponse(BaseModel):
    """Readiness + static deployment identity. Never calls OpenRouter/
    Ollama or performs a live retrieval - only inspects already-
    initialized dependency state and frozen config identity strings."""
    ready: bool
    dependencies: dict[str, bool]
    config: dict[str, str | int | None]
    retrieval_cache: dict[str, bool | int | float | str] | None = None
    retrieval_security: RetrievalSecurityStatusResponse | None = None
    prompt_cache: dict[str, bool | int | float | str | None] | None = None
