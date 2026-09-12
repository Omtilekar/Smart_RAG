"""Task 3.7 - CRAG-style confidence grading, reusing existing retrieval
signals rather than adding an LLM grader (PROJECT_EXECUTION.md Task 3.7's
own framing). Pure feature extraction, threshold calibration, and
refusal-decision logic - no I/O, no model, no LanceDB, no network.

Score-source adaptation (documented, not silently guessed): the roadmap
names "top-1 reranker score" as a candidate feature, but Task 3.6
evaluated cross-encoder reranking and selected `no_rerank` (reranking
credibly REGRESSED quality) - there is no reranker score to use. Every
feature below is computed from the frozen Task 3.3 dense retrieval
score instead (cosine similarity, higher is better) - the same
candidate pool, just without a reranker stage. This is a feature-source
substitution forced by Task 3.6's own result, not a reopening of that
decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


class CragError(ValueError):
    """Raised for malformed confidence-feature input or an invalid
    threshold-calibration request - never silently worked around."""


@dataclass(frozen=True)
class ConfidenceFeatures:
    """One question's confidence-signal snapshot. `scores` are the
    dense-retrieval `.score` values (cosine similarity, higher=better)
    for the top candidates, in rank order (rank 1 first)."""
    top1_score: float
    top3_mean_score: float
    top1_top5_gap: float
    candidate_count: int


def compute_confidence_features(scores: Sequence[float], candidate_count: int) -> ConfidenceFeatures:
    """`scores` must be non-empty and rank-ordered (rank 1 first) - the
    caller passes the real retrieval order, never a resorted copy.
    `candidate_count` is the number of candidates remaining after any
    metadata pre-filtering (always equal to `len(scores)` while Task 3.9's
    metadata pre-filter remains disabled - carried as its own field so a
    later task's pre-filter naturally starts changing it without an API
    change here)."""
    if not scores:
        raise CragError("scores must be non-empty")
    if candidate_count < 1:
        raise CragError(f"candidate_count must be >= 1, got {candidate_count}")

    top1 = scores[0]
    top3 = scores[:3]
    top3_mean = sum(top3) / len(top3)
    top5 = scores[:5]
    gap = top5[0] - top5[-1] if len(top5) >= 2 else 0.0

    return ConfidenceFeatures(
        top1_score=top1, top3_mean_score=top3_mean, top1_top5_gap=gap, candidate_count=candidate_count,
    )


# --------------------------------------------------------------- refusal decision

def should_refuse(features: ConfidenceFeatures, threshold: float) -> bool:
    """The frozen Task 3.7 decision rule: refuse iff `top1_score` is
    below `threshold`. The single-feature rule keeps the calibration
    step (`calibrate_threshold_youden_j`) simple and reproducible; the
    other three features are recorded for diagnostic/future-task use but
    do not gate the decision in this round (never silently expanded into
    a multi-feature rule the roadmap did not ask for)."""
    return features.top1_score < threshold


# --------------------------------------------------------------- outcome classification

def classify_outcome(*, should_have_answered: bool, refused: bool) -> str:
    """One of `"correct_answer"` (should answer, did not refuse),
    `"false_refusal"` (should answer, refused - a real capability lost),
    `"missed_failure"` (should refuse, did not - a real failure that
    should have been caught), `"true_refusal"` (should refuse, refused -
    correct)."""
    if should_have_answered:
        return "false_refusal" if refused else "correct_answer"
    return "true_refusal" if refused else "missed_failure"


# --------------------------------------------------------------- threshold calibration

def calibrate_threshold_youden_j(should_answer_top1: Sequence[float], should_refuse_top1: Sequence[float]) -> dict:
    """Deterministic, non-parametric threshold sweep over every observed
    `top1_score` value as a candidate cutoff, maximizing Youden's J
    statistic (`true_refusal_rate - false_refusal_rate`, equivalently
    TPR - FPR treating "should refuse" as the positive class) - the
    standard, simple, well-known balanced-accuracy-optimal threshold
    rule, not a hand-tuned pick. Ties broken by the LOWEST candidate
    threshold (fewer false refusals at equal J - conservative default
    for a "should the system speak" gate, never silently the opposite)."""
    if not should_answer_top1 or not should_refuse_top1:
        raise CragError("calibration requires at least one should-answer and one should-refuse example")

    candidates = sorted(set(should_answer_top1) | set(should_refuse_top1))
    best_threshold, best_j = candidates[0], float("-inf")
    for t in candidates:
        true_refusal_rate = sum(1 for s in should_refuse_top1 if s < t) / len(should_refuse_top1)
        false_refusal_rate = sum(1 for s in should_answer_top1 if s < t) / len(should_answer_top1)
        j = true_refusal_rate - false_refusal_rate
        if j > best_j:
            best_j, best_threshold = j, t

    return {"threshold": best_threshold, "youden_j": best_j, "candidates_evaluated": len(candidates)}


__all__ = [
    "CragError", "ConfidenceFeatures", "compute_confidence_features",
    "should_refuse", "classify_outcome", "calibrate_threshold_youden_j",
]
