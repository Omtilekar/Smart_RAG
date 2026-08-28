"""Task 1.4 - baseline BGE embedding pipeline for BAAI/bge-small-en-v1.5.

Frozen Phase 1 embedding contract (all user-approved or sourced directly
from the cached model's own README - see project_plan/PHASE1_EMBEDDINGS.md
for the full rationale of each):

- model: BAAI/bge-small-en-v1.5, fixed revision, loaded offline only
- passage convention: raw text, NO instruction prefix (per the model card:
  "no instruction needs to be added to passages")
- query convention: prepend QUERY_INSTRUCTION (per the model card's own
  documented query instruction for this exact model)
- normalize_embeddings=True for both (the model card's own documented
  usage for computing cosine similarity via dot product) - not a silently
  accepted library default
- persisted dtype: float32 (matches the model's native output)
- GPU batch size: 128, full FP32 precision (no autocast)

No filesystem/Parquet-writing logic lives here - see
scripts/embed_development_corpus.py for orchestration.
"""

from __future__ import annotations

import numpy as np

MODEL_REPO = "BAAI/bge-small-en-v1.5"
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
EMBEDDING_DIMENSION = 384
VECTOR_DTYPE = np.float32
DEFAULT_BATCH_SIZE = 128

# Sourced directly from the cached model's own README (query instruction
# table row for BAAI/bge-small-en-v1.5): "no instruction needs to be added
# to passages" and this exact instruction string for queries.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

REQUIRED_MODEL_ASSET_FILES: tuple[str, ...] = (
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "sentence_bert_config.json",
    "model.safetensors",
    "1_Pooling/config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "special_tokens_map.json",
)


def verify_cached_model_assets() -> None:
    """Raises RuntimeError naming the first missing asset - never silently
    downloads. Call before constructing the model."""
    from huggingface_hub import try_to_load_from_cache

    for fname in REQUIRED_MODEL_ASSET_FILES:
        cached = try_to_load_from_cache(MODEL_REPO, fname, revision=MODEL_REVISION)
        if cached is None or not isinstance(cached, str):
            raise RuntimeError(
                f"required cached model asset missing: {MODEL_REPO}/{fname} "
                f"(revision {MODEL_REVISION}). Refusing to download - offline only."
            )


def load_model(device: str = "cuda"):
    """Loads BAAI/bge-small-en-v1.5 offline, on the given device. Raises if
    required cache assets are missing (verify_cached_model_assets()) or if
    the resolved embedding dimension is not 384."""
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    verify_cached_model_assets()

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(
        MODEL_REPO, revision=MODEL_REVISION, local_files_only=True, device=device,
    )
    actual_device = str(next(model.parameters()).device)
    if device == "cuda" and "cuda" not in actual_device:
        raise RuntimeError(f"requested cuda but model resolved to device {actual_device!r}")

    dim = model.get_embedding_dimension()
    if dim != EMBEDDING_DIMENSION:
        raise RuntimeError(f"unexpected embedding dimension: {dim} != {EMBEDDING_DIMENSION}")

    return model


def encode_passages(model, texts: list[str], batch_size: int = DEFAULT_BATCH_SIZE) -> np.ndarray:
    """Passage convention: raw text, no instruction, normalize_embeddings=True.
    Returns a (len(texts), 384) float32 array."""
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.astype(VECTOR_DTYPE, copy=False)


def encode_queries(model, texts: list[str], batch_size: int = DEFAULT_BATCH_SIZE) -> np.ndarray:
    """Query convention: QUERY_INSTRUCTION prepended exactly once per query,
    normalize_embeddings=True. Returns a (len(texts), 384) float32 array."""
    instructed = [QUERY_INSTRUCTION + t for t in texts]
    vectors = model.encode(
        instructed,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.astype(VECTOR_DTYPE, copy=False)


def validate_vectors(vectors: np.ndarray, *, expect_normalized: bool = True,
                      norm_tolerance: float = 1e-3) -> None:
    """Raises ValueError on the first violated invariant:
    - 2D array, second dim == EMBEDDING_DIMENSION
    - dtype == VECTOR_DTYPE
    - no NaN, no +-Inf
    - if expect_normalized: every row's L2 norm is 1.0 within norm_tolerance
    """
    if vectors.ndim != 2 or vectors.shape[1] != EMBEDDING_DIMENSION:
        raise ValueError(f"expected shape (N, {EMBEDDING_DIMENSION}), got {vectors.shape}")
    if vectors.dtype != VECTOR_DTYPE:
        raise ValueError(f"expected dtype {VECTOR_DTYPE}, got {vectors.dtype}")
    if not np.isfinite(vectors).all():
        raise ValueError("vectors contain NaN or +-Inf")
    if expect_normalized:
        norms = np.linalg.norm(vectors, axis=1)
        bad = np.abs(norms - 1.0) > norm_tolerance
        if bad.any():
            worst = np.abs(norms - 1.0).max()
            raise ValueError(
                f"{bad.sum()} vector(s) not unit-normalized within tolerance "
                f"{norm_tolerance} (worst deviation: {worst})"
            )
