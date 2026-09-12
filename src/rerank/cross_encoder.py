"""Task 3.6 - cross-encoder reranker model adapter.

Mirrors `src.embeddings.model_registry`'s spec/adapter pattern (frozen
dataclass spec + generic load/score functions) but for reranking, never
duplicating that module's embedding-specific logic.

Verified empirically (Stage/pilot, before any formal code was written)
against the installed sentence-transformers 6.0.0:

    - `sentence_transformers.CrossEncoder` predicts one raw, UNBOUNDED
      logit per (question, passage) pair - no sigmoid/softmax is applied
      by default (`activation_fn=None`). Higher is more relevant; scores
      are NOT probabilities and are never treated as such here (verified:
      a strongly relevant pair scored ~9.1, a mismatched pair ~-7.3).
    - `num_labels=1` (single relevance score per pair, not a
      classification head).
    - the frozen `max_length`/`max_seq_length` (0.25.0+ renamed the
      constructor kwarg's exposed property) is 512.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SCORE_DTYPE = np.float32


@dataclass(frozen=True)
class RerankerModelSpec:
    candidate_id: str
    repository: str
    revision: str
    max_seq_length: int
    num_labels: int
    score_activation: str  # "raw_logit" - never a probability
    trust_remote_code: bool
    license: str
    model_size_bytes: int | None

    def reranker_identity(self) -> dict:
        """A reranker's own semantic identity - deliberately NOT
        `src.artifacts.versioning.compute_embedding_identity()` (a
        reranker has no embedding dimension/passage-query convention of
        that shape). Reuses Task 2.10's canonical `semantic_hash()`
        primitive on a new, honestly-shaped payload - same pattern as
        `src.index.lancedb_fts.sparse_index_identity()` (Task 3.4)."""
        return {
            "reranker_identity_version": 1,
            "model_repository": self.repository, "model_revision": self.revision,
            "max_seq_length": self.max_seq_length, "num_labels": self.num_labels,
            "score_activation": self.score_activation,
        }


# --------------------------------------------------------------- frozen candidate registry

# Pinned to the exact commit resolved from the installed sentence-transformers'
# own cache (huggingface_hub refs/main) at pilot time - never "main"/"latest".
CROSS_ENCODER_MINILM_L6 = RerankerModelSpec(
    candidate_id="ce_minilm_l6", repository="cross-encoder/ms-marco-MiniLM-L6-v2",
    revision="233902d25c440f23af6f7d6e94d2946bac0bee0a",
    max_seq_length=512, num_labels=1, score_activation="raw_logit",
    trust_remote_code=False, license="apache-2.0", model_size_bytes=91_815_758,
)

ALL_CANDIDATES: tuple[RerankerModelSpec, ...] = (CROSS_ENCODER_MINILM_L6,)
CANDIDATES_BY_ID: dict[str, RerankerModelSpec] = {c.candidate_id: c for c in ALL_CANDIDATES}


# --------------------------------------------------------------- generic model loading/scoring

def load_model(spec: RerankerModelSpec, device: str = "cuda"):
    """Loads any CrossEncoder-compatible reranker by its frozen spec.
    Never `revision="main"` - always the frozen pinned commit SHA."""
    import torch
    from sentence_transformers import CrossEncoder

    model = CrossEncoder(
        spec.repository, revision=spec.revision, trust_remote_code=spec.trust_remote_code,
        device=device, max_length=spec.max_seq_length, model_kwargs={"torch_dtype": torch.float32},
    )
    actual_device = str(next(model.model.parameters()).device)
    if device == "cuda" and "cuda" not in actual_device:
        raise RuntimeError(f"requested cuda but model resolved to device {actual_device!r}")
    actual_dtype = next(model.model.parameters()).dtype
    if actual_dtype != torch.float32:
        raise RuntimeError(f"{spec.candidate_id}: expected float32 weights, model loaded as {actual_dtype}")
    if model.config.num_labels != spec.num_labels:
        raise RuntimeError(f"{spec.candidate_id}: unexpected num_labels {model.config.num_labels} != {spec.num_labels}")
    return model


def score_pairs(model, question: str, texts: list[str], batch_size: int = 32) -> np.ndarray:
    """Scores every (question, text) pair. Returns raw logits - higher is
    more relevant, never normalized/clamped into [0, 1]."""
    pairs = [[question, t] for t in texts]
    scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False)
    return np.asarray(scores, dtype=SCORE_DTYPE)


def validate_scores(scores: np.ndarray, *, expected_count: int) -> None:
    if scores.ndim != 1 or scores.shape[0] != expected_count:
        raise ValueError(f"expected shape ({expected_count},), got {scores.shape}")
    if not np.isfinite(scores).all():
        raise ValueError("reranker scores contain NaN or +-Inf")


__all__ = [
    "SCORE_DTYPE", "RerankerModelSpec", "CROSS_ENCODER_MINILM_L6", "ALL_CANDIDATES", "CANDIDATES_BY_ID",
    "load_model", "score_pairs", "validate_scores",
]
