"""Task 1.3 - minimal fixed-window chunker: pure, deterministic logic only.

No filesystem, tokenizer-loading, or DuckDB access lives here - see
scripts/chunk_development_corpus.py for orchestration (loading the offline
tokenizer, enumerating normalized documents, writing Parquet).

Frozen Phase 1 chunking contract (all user-approved - see
project_plan/PHASE1_CHUNKING.md for the full rationale of each decision):

- tokenizer: BAAI/bge-small-en-v1.5 (offline, cached, fixed revision)
- window_size_tokens = 512, stride_tokens = 512 (zero overlap)
- partial final window: kept, never dropped
- special-token counting: content tokens only (add_special_tokens=False)
- what gets chunked: Markdown body only; YAML frontmatter is parsed into
  chunk metadata, never tokenized/windowed
- text preservation: offset-mapping slicing (exact substrings of the
  original normalized body), not token-id decode()
- empty body (7 known-empty-source documents from Task 1.2): 0 chunks,
  an explicit approved exception - not an error
- chunk_id = "{document_id}::chunk{ordinal}", ordinal zero-based
"""

from __future__ import annotations

import json
import re

# Must match src/normalize/edgar_markdown.py's FRONTMATTER_KEYS exactly -
# Task 1.3 reads Task 1.2's own frontmatter contract, not a redefinition.
FRONTMATTER_KEYS: tuple[str, ...] = (
    "cik", "company", "form_type", "fiscal_year", "source",
    "source_filename", "document_id", "source_split",
    "development_manifest_sha256",
)

CHUNK_SCHEMA_VERSION = "1.0"
CHUNK_SCHEMA_FIELDS: tuple[str, ...] = (
    "chunk_id", "document_id", "cik", "company", "form_type", "fiscal_year",
    "source", "source_filename", "source_split", "ordinal", "text",
    "token_count", "chunk_config_hash", "normalizer_version",
    "normalization_build_sha256", "development_manifest_sha256",
)

WINDOW_SIZE_TOKENS = 512
STRIDE_TOKENS = 512  # window_size - overlap; overlap_tokens = 0 (approved)

_DOC_RE = re.compile(r"^---\n(?P<fm>.*?)\n---\n(?P<rest>.*)\Z", re.DOTALL)


def parse_normalized_document(markdown_text: str) -> tuple[dict, str]:
    """Splits a Task 1.2 normalized Markdown document into (frontmatter
    fields, body text). Exact inverse of edgar_markdown.render_document():
    body is recovered byte-for-byte, not re-derived or re-stripped.

    Raises ValueError on any structural mismatch - malformed Markdown is
    never silently chunked as raw text (Task 1.3 Step 23)."""
    m = _DOC_RE.match(markdown_text)
    if not m:
        raise ValueError("malformed normalized document: frontmatter delimiters not found")
    fm_block = m.group("fm")
    rest = m.group("rest")
    body = rest[1:-1] if rest else ""

    fields: dict = {}
    for line in fm_block.split("\n"):
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"malformed frontmatter line: {line!r}")
        key, _, raw_value = line.partition(":")
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value.startswith('"'):
            fields[key] = json.loads(raw_value)
        else:
            fields[key] = int(raw_value)

    missing = set(FRONTMATTER_KEYS) - set(fields)
    if missing:
        raise ValueError(f"missing frontmatter fields: {sorted(missing)}")
    extra = set(fields) - set(FRONTMATTER_KEYS)
    if extra:
        raise ValueError(f"unexpected frontmatter fields: {sorted(extra)}")
    return fields, body


def compute_token_windows(num_tokens: int, window_size: int = WINDOW_SIZE_TOKENS,
                           stride: int = STRIDE_TOKENS) -> list[tuple[int, int]]:
    """[start, end) token-index ranges covering all `num_tokens` tokens.
    Zero overlap when stride == window_size. Final partial window is always
    kept (never dropped, never merged). Returns [] for num_tokens == 0 -
    this is how the 7 known-empty-source documents naturally produce 0
    chunks, with no special-casing required."""
    if window_size <= 0:
        raise ValueError(f"window_size must be positive, got {window_size}")
    if stride <= 0:
        raise ValueError(f"stride must be positive, got {stride}")
    if num_tokens < 0:
        raise ValueError(f"num_tokens must be non-negative, got {num_tokens}")
    if num_tokens == 0:
        return []

    windows: list[tuple[int, int]] = []
    start = 0
    while start < num_tokens:
        end = min(start + window_size, num_tokens)
        windows.append((start, end))
        if end == num_tokens:
            break
        start += stride
    return windows


def slice_chunk_text(body_text: str, offsets: list[tuple[int, int]],
                      start_idx: int, end_idx: int) -> str:
    """Exact substring of `body_text` spanned by tokens [start_idx, end_idx).
    Preserves original characters exactly (no decode/re-encode artifacts).
    Known limitation: pure-whitespace gaps between tokens (e.g. a run of
    whitespace the tokenizer's pre-tokenizer does not attach to any token)
    are not captured by this slice - never real content, only whitespace."""
    if end_idx <= start_idx:
        raise ValueError(f"empty or invalid token range: [{start_idx}, {end_idx})")
    char_start = offsets[start_idx][0]
    char_end = offsets[end_idx - 1][1]
    return body_text[char_start:char_end]


def make_chunk_id(document_id: str, ordinal: int) -> str:
    """'{document_id}::chunk{ordinal}', zero-based ordinal. Deterministic,
    globally unique (document_id is already unique per Task 1.1's manifest),
    human-readable."""
    return f"{document_id}::chunk{ordinal}"


def build_chunk_config(*, normalizer_version: str, normalization_build_sha256: str,
                        development_manifest_sha256: str, tokenizer_repo: str,
                        tokenizer_revision: str) -> dict:
    """Every decision that affects chunk identity or text, in one place.
    No timestamps - this dict is hashed verbatim by chunk_config_hash()."""
    return {
        "schema_version": "1.0",
        "input_normalizer_version": normalizer_version,
        "input_normalization_build_sha256": normalization_build_sha256,
        "development_manifest_sha256": development_manifest_sha256,
        "tokenizer": {
            "repo": tokenizer_repo,
            "revision": tokenizer_revision,
            "local_files_only": True,
        },
        "window_size_tokens": WINDOW_SIZE_TOKENS,
        "overlap_tokens": 0,
        "stride_tokens": STRIDE_TOKENS,
        "special_token_policy": "content_tokens_only (add_special_tokens=False)",
        "partial_window_policy": "keep",
        "frontmatter_body_policy": "body_only_frontmatter_to_metadata",
        "decode_offset_policy": "offset_mapping_slicing",
        "chunk_schema_version": CHUNK_SCHEMA_VERSION,
        "chunk_id_policy": "document_id + '::chunk{ordinal}', zero-based ordinal",
    }


def chunk_config_hash(config: dict) -> str:
    """SHA-256 over canonical JSON (sort_keys, no whitespace) - the same
    convention already established by Task 1.1's development_manifest_sha256
    and Task 1.2's normalization_build_sha256, reused deliberately rather
    than inventing a new one.

    Task 2.10 - delegates to the one centralized canonical-hashing
    primitive (src.artifacts.versioning.compute_chunk_config_hash) rather
    than maintaining a second independent json.dumps+hashlib.sha256
    implementation. Verified byte-identical to the original inline
    implementation for the real frozen Phase 1 config (legacy
    compatibility: PASS) - this function's return value is unchanged."""
    from src.artifacts.versioning import compute_chunk_config_hash
    return compute_chunk_config_hash(config)
