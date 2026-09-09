"""Task 3.3 - generalized embedding-model adapter boundary.

Generalizes Task 1.4's BGE-only pipeline (src/embeddings/bge.py, left
completely untouched) into a small model-spec / adapter pattern so a new
candidate embedding model does not require a new hand-written pipeline.
`EmbeddingModelSpec` for the BGE-small control reproduces
src.embeddings.bge's exact frozen identity fields
(embedding_identity_hash: b39a67c9eb6487fc98f266f23742afd0a30321d98067505802a1e219b27bec84,
verified byte-identical - see tests/test_model_registry.py) - Task 1.4/3.2's
BGE artifacts are reused unmodified, never rebuilt through this module.

Every model-specific detail (query/passage prefix, normalization,
trust_remote_code, similarity metric) lives on the frozen `EmbeddingModelSpec`
for that candidate, never guessed generically or borrowed from another
model - see project_plan/PHASE3_EMBEDDING_MODEL_BENCHMARK.md for the
verified source of every field (model card / config.json / empirical
check, never assumed from a different model in the same "family").
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

VECTOR_DTYPE = np.float32


@dataclass(frozen=True)
class EmbeddingModelSpec:
    candidate_id: str
    repository: str
    revision: str
    dimension: int
    max_seq_length: int
    pooling: str
    query_prefix: str
    passage_prefix: str
    normalize_embeddings: bool
    similarity_metric: str
    trust_remote_code: bool
    license: str
    model_size_bytes: int | None
    is_control: bool = False

    @property
    def passage_convention(self) -> str:
        return "raw_text_no_instruction" if not self.passage_prefix else f"prepend:{self.passage_prefix}"

    @property
    def query_convention(self) -> str:
        return "raw_text_no_instruction" if not self.query_prefix else f"prepend:{self.query_prefix}"

    def embedding_identity(self) -> dict:
        from src.artifacts.versioning import compute_embedding_identity
        return compute_embedding_identity(
            model_repository=self.repository, model_revision=self.revision,
            embedding_dimension=self.dimension, vector_dtype=str(np.dtype(VECTOR_DTYPE)),
            normalize_embeddings=self.normalize_embeddings,
            passage_convention=self.passage_convention, query_convention=self.query_convention,
        )


# --------------------------------------------------------------- frozen candidate registry

# BGE-small control: reproduces src.embeddings.bge's exact frozen identity
# fields (MODEL_REPO/MODEL_REVISION/QUERY_INSTRUCTION unchanged there) -
# never a second, independently-drifting definition of the control model.
BGE_SMALL = EmbeddingModelSpec(
    candidate_id="bge_small", repository="BAAI/bge-small-en-v1.5",
    revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    dimension=384, max_seq_length=512, pooling="cls",
    query_prefix="Represent this sentence for searching relevant passages: ", passage_prefix="",
    normalize_embeddings=True, similarity_metric="cosine", trust_remote_code=False,
    license="mit", model_size_bytes=133_000_000, is_control=True,
)

BGE_BASE = EmbeddingModelSpec(
    candidate_id="bge_base", repository="BAAI/bge-base-en-v1.5",
    revision="a5beb1e3e68b9ab74eb54cfd186867f64f240e1a",
    dimension=768, max_seq_length=512, pooling="cls",
    query_prefix="Represent this sentence for searching relevant passages: ", passage_prefix="",
    normalize_embeddings=True, similarity_metric="cosine", trust_remote_code=False,
    license="mit", model_size_bytes=438_000_000,
)

NOMIC_EMBED = EmbeddingModelSpec(
    candidate_id="nomic_embed", repository="nomic-ai/nomic-embed-text-v1.5",
    revision="e9b6763023c676ca8431644204f50c2b100d9aab",
    dimension=768, max_seq_length=8192, pooling="mean",
    query_prefix="search_query: ", passage_prefix="search_document: ",
    # No built-in Normalize module in this repo's modules.json - normalize
    # must be requested explicitly at encode() time (verified empirically:
    # raw output norm ~22, not 1.0).
    normalize_embeddings=True, similarity_metric="cosine",
    # Verified empirically against the installed transformers 5.16.1 /
    # sentence-transformers 6.0.0 (see project_plan/PHASE3_EMBEDDING_MODEL_BENCHMARK.md):
    # loads natively via AutoModel, trust_remote_code=True is NOT required
    # with these library versions (the model card's own note: "From
    # transformers v5.5.0 and sentence transformers v5.3.0, trust_remote_code=True
    # will no longer be necessary" - both installed versions clear that bar).
    trust_remote_code=False,
    license="apache-2.0", model_size_bytes=547_000_000,
)

QWEN3_EMBEDDING = EmbeddingModelSpec(
    candidate_id="qwen3_embedding", repository="Qwen/Qwen3-Embedding-0.6B",
    revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
    dimension=1024, max_seq_length=32768, pooling="last_token",
    # Exact registered prompt from the repo's own config_sentence_transformers.json
    # ("prompts"."query") - verified bit-identical (max abs diff 0.0) between
    # SentenceTransformer's built-in prompt_name="query" mechanism and this
    # manual prefix-concatenation, so the same uniform encode path used for
    # every other candidate is safe here too.
    query_prefix="Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:",
    passage_prefix="",  # repo's own "document" prompt is "" (empty)
    normalize_embeddings=True, similarity_metric="cosine", trust_remote_code=False,
    license="apache-2.0", model_size_bytes=1_192_000_000,
)

ALL_CANDIDATES: tuple[EmbeddingModelSpec, ...] = (BGE_SMALL, BGE_BASE, NOMIC_EMBED, QWEN3_EMBEDDING)
CANDIDATES_BY_ID: dict[str, EmbeddingModelSpec] = {c.candidate_id: c for c in ALL_CANDIDATES}


# --------------------------------------------------------------- generic model loading/encoding

def load_model(spec: EmbeddingModelSpec, device: str = "cuda"):
    """Loads any SentenceTransformer-compatible model by its frozen spec.
    Unlike Task 1.4's offline-only src.embeddings.bge.load_model(), this
    may download from the Hub (Task 3.3 candidates are not pre-cached) -
    huggingface_hub's own cache makes a second load a no-op download.
    Never uses `revision="main"` - always the frozen pinned commit SHA.

    Explicitly forces float32 weights (`model_kwargs={"torch_dtype":
    torch.float32}`) - Qwen/Qwen3-Embedding-0.6B's own config declares
    bfloat16 and sentence-transformers honors that by default, which
    silently degraded normalized-vector precision enough to fail the
    frozen normalization check (measured: unit-norm deviation ~0.3% in
    bf16 vs exact 1.0 in fp32). Every candidate is forced to the same
    fp32 policy explicitly rather than three of four happening to already
    default there."""
    import torch
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        spec.repository, revision=spec.revision, trust_remote_code=spec.trust_remote_code, device=device,
        model_kwargs={"torch_dtype": torch.float32},
    )
    actual_device = str(next(model.parameters()).device)
    if device == "cuda" and "cuda" not in actual_device:
        raise RuntimeError(f"requested cuda but model resolved to device {actual_device!r}")
    actual_dtype = next(model.parameters()).dtype
    if actual_dtype != torch.float32:
        raise RuntimeError(f"{spec.candidate_id}: expected float32 weights, model loaded as {actual_dtype}")

    dim = model.get_embedding_dimension() if hasattr(model, "get_embedding_dimension") \
        else model.get_sentence_embedding_dimension()
    if dim != spec.dimension:
        raise RuntimeError(f"{spec.candidate_id}: unexpected embedding dimension {dim} != {spec.dimension}")
    return model


def encode_passages(spec: EmbeddingModelSpec, model, texts: list[str], batch_size: int) -> np.ndarray:
    prefixed = [spec.passage_prefix + t for t in texts] if spec.passage_prefix else texts
    vectors = model.encode(
        prefixed, batch_size=batch_size, normalize_embeddings=spec.normalize_embeddings,
        convert_to_numpy=True, show_progress_bar=False,
    )
    return vectors.astype(VECTOR_DTYPE, copy=False)


def encode_queries(spec: EmbeddingModelSpec, model, texts: list[str], batch_size: int) -> np.ndarray:
    prefixed = [spec.query_prefix + t for t in texts] if spec.query_prefix else texts
    vectors = model.encode(
        prefixed, batch_size=batch_size, normalize_embeddings=spec.normalize_embeddings,
        convert_to_numpy=True, show_progress_bar=False,
    )
    return vectors.astype(VECTOR_DTYPE, copy=False)


def validate_vectors(vectors: np.ndarray, *, expected_dimension: int,
                      expect_normalized: bool = True, norm_tolerance: float = 1e-3) -> None:
    """Generic version of src.embeddings.bge.validate_vectors(), parameterized
    by expected_dimension instead of the BGE-only hardcoded 384."""
    if vectors.ndim != 2 or vectors.shape[1] != expected_dimension:
        raise ValueError(f"expected shape (N, {expected_dimension}), got {vectors.shape}")
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


__all__ = [
    "VECTOR_DTYPE", "EmbeddingModelSpec",
    "BGE_SMALL", "BGE_BASE", "NOMIC_EMBED", "QWEN3_EMBEDDING",
    "ALL_CANDIDATES", "CANDIDATES_BY_ID",
    "load_model", "encode_passages", "encode_queries", "validate_vectors",
]
