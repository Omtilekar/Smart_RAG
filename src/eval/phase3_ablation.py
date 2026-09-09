"""Task 3.2 - pure logic for the controlled Phase 3 chunking ablation:
candidate registry, paired bootstrap analysis, and the frozen winner-
selection rule. No I/O, no DuckDB, no LanceDB, no model loading, no
network, and - like src.eval.phase3_baseline - no dependency on
src.eval.test_access / load_test_set() anywhere in this module.

Reuses src.eval.baseline_metrics/src.eval.metrics/src.eval.phase3_baseline
for the metrics themselves (never reimplemented here). This module only
answers three questions:

    1. What is the frozen candidate grid (Rounds A/B/C)?
    2. Given paired per-question results for a candidate vs a reference,
       what is the bootstrap-uncertainty delta (paired_bootstrap_delta_ci)?
    3. Given a round's candidates and their bootstrap deltas vs the round's
       reference, which candidate wins (select_round_winner), per the
       pre-frozen Stage 8 rule?
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

BOOTSTRAP_SEED = 42
BOOTSTRAP_ITERATIONS = 10_000

ENCODER_MAX_SEQ_LENGTH_TOKENS = 512  # BAAI/bge-small-en-v1.5 - verified, see Stage 2 audit

WINDOW_SIZES: tuple[int, ...] = (256, 512, 1024)

# Fixed, deterministic overlap-percentage -> token-count table (Stage 3 -
# "Convert percentages deterministically to token counts"). Never computed
# by rounding at runtime - looked up here so every run reproduces the exact
# same overlap_tokens for a given window size.
OVERLAP_TOKEN_TABLE: dict[int, dict[float, int]] = {
    256: {0.125: 32, 0.25: 64},
    512: {0.125: 64, 0.25: 128},
    1024: {0.125: 128, 0.25: 256},
}


class Phase3AblationError(ValueError):
    """Raised for a malformed candidate grid, an evaluator scope mismatch,
    or an ambiguous winner-selection outcome that requires a user
    decision - never silently resolved."""


def overlap_tokens_for(window_size_tokens: int, overlap_pct: float) -> int:
    table = OVERLAP_TOKEN_TABLE.get(window_size_tokens)
    if table is None:
        raise Phase3AblationError(f"no frozen overlap table entry for window_size_tokens={window_size_tokens}")
    tokens = table.get(overlap_pct)
    if tokens is None:
        raise Phase3AblationError(f"no frozen overlap table entry for window={window_size_tokens}, pct={overlap_pct}")
    return tokens


# --------------------------------------------------------------- candidate registry

@dataclass(frozen=True)
class ChunkCandidate:
    row_id: str
    round: str  # "A" | "B" | "C"
    label: str
    window_size_tokens: int
    overlap_tokens: int
    split_mode: str  # "fixed" | "section_aware"
    reuse_row_id: str | None = None  # non-None => do not rebuild, reuse this row's artifacts
    encoder_truncation_note: str | None = None

    @property
    def stride_tokens(self) -> int:
        return self.window_size_tokens - self.overlap_tokens


def _encoder_note_for(window_size_tokens: int) -> str | None:
    if window_size_tokens <= ENCODER_MAX_SEQ_LENGTH_TOKENS:
        return None
    return (
        f"BAAI/bge-small-en-v1.5 has a {ENCODER_MAX_SEQ_LENGTH_TOKENS}-token effective passage-embedding "
        f"limit (sentence_bert_config.json max_seq_length=512, tokenizer_config.json model_max_length=512, "
        f"BertModel max_position_embeddings=512 - all verified against the cached model, not assumed). "
        f"Verified empirically: SentenceTransformer.encode() silently truncates to the first "
        f"{ENCODER_MAX_SEQ_LENGTH_TOKENS} tokens (including [CLS]/[SEP]); the embedding of a chunk longer "
        f"than that is bit-identical to the embedding of its first ~510-content-token prefix. This "
        f"{window_size_tokens}-token chunk configuration is therefore NOT a lossless "
        f"{window_size_tokens}-token embedding experiment - only the truncated prefix contributes to the "
        f"vector, though the full chunk text is preserved in the chunk artifact for inspection."
    )


def round_a_candidates() -> list[ChunkCandidate]:
    """A0 (row 0, reused unmodified) + A1 (256/0) + A2 (1024/0, encoder-truncated)."""
    return [
        ChunkCandidate(
            row_id="A0", round="A", label="fixed_512_overlap_0",
            window_size_tokens=512, overlap_tokens=0, split_mode="fixed", reuse_row_id="0",
        ),
        ChunkCandidate(
            row_id="A1", round="A", label="fixed_256_overlap_0",
            window_size_tokens=256, overlap_tokens=0, split_mode="fixed",
        ),
        ChunkCandidate(
            row_id="A2", round="A",
            label="fixed_1024_overlap_0_encoder_truncates_at_512",
            window_size_tokens=1024, overlap_tokens=0, split_mode="fixed",
            encoder_truncation_note=_encoder_note_for(1024),
        ),
    ]


def round_b_candidates(winner_window_tokens: int, *, winner_row_id: str) -> list[ChunkCandidate]:
    """B0 (winner window, overlap 0 - reused from Round A, never rebuilt) +
    B1 (12.5% overlap) + B2 (25% overlap)."""
    overlap_125 = overlap_tokens_for(winner_window_tokens, 0.125)
    overlap_25 = overlap_tokens_for(winner_window_tokens, 0.25)
    note = _encoder_note_for(winner_window_tokens)
    return [
        ChunkCandidate(
            row_id="B0", round="B", label=f"fixed_{winner_window_tokens}_overlap_0",
            window_size_tokens=winner_window_tokens, overlap_tokens=0, split_mode="fixed",
            reuse_row_id=winner_row_id, encoder_truncation_note=note,
        ),
        ChunkCandidate(
            row_id="B1", round="B", label=f"fixed_{winner_window_tokens}_overlap_{overlap_125}",
            window_size_tokens=winner_window_tokens, overlap_tokens=overlap_125, split_mode="fixed",
            encoder_truncation_note=note,
        ),
        ChunkCandidate(
            row_id="B2", round="B", label=f"fixed_{winner_window_tokens}_overlap_{overlap_25}",
            window_size_tokens=winner_window_tokens, overlap_tokens=overlap_25, split_mode="fixed",
            encoder_truncation_note=note,
        ),
    ]


def round_c_candidates(*, winner_window_tokens: int, winner_overlap_tokens: int, winner_row_id: str) -> list[ChunkCandidate]:
    """C0 (fixed-window winner, reused from Round B) + C1 (same window/
    overlap, section-aware split)."""
    note = _encoder_note_for(winner_window_tokens)
    return [
        ChunkCandidate(
            row_id="C0", round="C",
            label=f"fixed_{winner_window_tokens}_overlap_{winner_overlap_tokens}",
            window_size_tokens=winner_window_tokens, overlap_tokens=winner_overlap_tokens, split_mode="fixed",
            reuse_row_id=winner_row_id, encoder_truncation_note=note,
        ),
        ChunkCandidate(
            row_id="C1", round="C",
            label=f"section_aware_{winner_window_tokens}_overlap_{winner_overlap_tokens}",
            window_size_tokens=winner_window_tokens, overlap_tokens=winner_overlap_tokens, split_mode="section_aware",
            encoder_truncation_note=note,
        ),
    ]


# --------------------------------------------------------------- evaluator guards

def assert_frozen_scope(question_ids: Sequence[str], frozen_scope_ids: Sequence[str]) -> None:
    """Refuses (Phase3AblationError) an evaluator call whose question_ids
    do not exactly match the frozen Task 3.1 89-question scope - neither
    an unexpected extra ID nor a missing expected one is ever silently
    tolerated (Section: "the exact same 89 frozen question IDs")."""
    got = set(question_ids)
    expected = set(frozen_scope_ids)
    unexpected = got - expected
    missing = expected - got
    if unexpected or missing:
        raise Phase3AblationError(
            f"question scope mismatch - unexpected: {sorted(unexpected)}, missing: {sorted(missing)}"
        )


def assert_dev_split(split: str) -> None:
    """Refuses anything other than the literal 'dev' split - Task 3.2 is
    DEV-only routine optimization; TEST must never reach this evaluator."""
    if split != "dev":
        raise Phase3AblationError(f"Task 3.2 evaluation is DEV-only, refusing split={split!r}")


# --------------------------------------------------------------- paired bootstrap

@dataclass(frozen=True)
class BootstrapResult:
    point_estimate: float
    ci_lo: float
    ci_hi: float
    seed: int
    iterations: int

    def includes_zero(self) -> bool:
        return self.ci_lo <= 0.0 <= self.ci_hi

    def to_dict(self) -> dict:
        return {
            "point_estimate": self.point_estimate, "ci_lo": self.ci_lo, "ci_hi": self.ci_hi,
            "seed": self.seed, "iterations": self.iterations,
        }


def paired_bootstrap_delta_ci(
    candidate_values: Sequence[float], baseline_values: Sequence[float],
    *, seed: int = BOOTSTRAP_SEED, iterations: int = BOOTSTRAP_ITERATIONS,
) -> BootstrapResult:
    """95% bootstrap interval for mean(candidate) - mean(baseline), over
    paired-by-question_id per-question values (e.g. per-question
    reciprocal rank or nDCG@10 - the caller aligns both sequences to the
    identical question order before calling). Resamples QUESTION INDICES
    (not the two value arrays independently) with replacement - this is
    what makes it a PAIRED bootstrap: a resample draws the same set of
    questions for both arms every iteration, deterministic under `seed`
    (`random.Random(seed)`, never the global `random` module state)."""
    n = len(candidate_values)
    if n == 0 or n != len(baseline_values):
        raise Phase3AblationError(
            f"paired_bootstrap_delta_ci requires equal-length, non-empty paired arrays, "
            f"got {n} vs {len(baseline_values)}"
        )
    cand = list(candidate_values)
    base = list(baseline_values)
    point_estimate = (sum(cand) / n) - (sum(base) / n)

    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(iterations):
        idx = [rng.randrange(n) for _ in range(n)]
        c_mean = sum(cand[i] for i in idx) / n
        b_mean = sum(base[i] for i in idx) / n
        deltas.append(c_mean - b_mean)
    deltas.sort()
    lo_pos = int(round(0.025 * (iterations - 1)))
    hi_pos = int(round(0.975 * (iterations - 1)))
    return BootstrapResult(
        point_estimate=point_estimate, ci_lo=deltas[lo_pos], ci_hi=deltas[hi_pos],
        seed=seed, iterations=iterations,
    )


# --------------------------------------------------------------- small-N tie handling

def is_practical_tie(*, recall50_hit_delta: int, mrr_ci: tuple[float, float], ndcg_ci: tuple[float, float]) -> bool:
    """Stage 8's frozen small-N tie rule: candidates are practically tied
    iff Recall@50 differs by at most 1 question out of 89 AND both the
    paired MRR delta's and paired nDCG@10 delta's 95% bootstrap intervals
    include 0."""
    return (
        abs(recall50_hit_delta) <= 1
        and mrr_ci[0] <= 0.0 <= mrr_ci[1]
        and ndcg_ci[0] <= 0.0 <= ndcg_ci[1]
    )


def _tiebreak_key(candidate: Mapping[str, Any]) -> tuple:
    """Pre-frozen engineering tie-break order: fewer chunks/duplication ->
    smaller embedding artifact -> smaller index -> lower retrieval p95 ->
    lower build cost -> simpler chunking policy (fixed before
    section_aware)."""
    simplicity_rank = 0 if candidate.get("split_mode", "fixed") == "fixed" else 1
    return (
        candidate["chunk_count"],
        candidate.get("embedding_artifact_size_bytes", 0),
        candidate.get("index_size_bytes", 0),
        candidate.get("retrieval_latency_p95_ms", 0.0),
        candidate.get("build_seconds_total", 0.0),
        simplicity_rank,
    )


def apply_tiebreak(
    tied_candidates: Sequence[Mapping[str, Any]], *, key_fn: "Any" = None,
) -> Mapping[str, Any]:
    """`key_fn` defaults to the chunking-ablation tie-break order
    (`_tiebreak_key`) - Task 3.3's embedding-model tie-break order is a
    different priority list, passed in by its own caller rather than
    duplicating this function."""
    if not tied_candidates:
        raise Phase3AblationError("apply_tiebreak requires at least one candidate")
    return sorted(tied_candidates, key=key_fn or _tiebreak_key)[0]


# --------------------------------------------------------------- winner selection

QUALITY_PRIORITY_KEYS: tuple[str, ...] = (
    "doc_recall_at_50", "doc_mrr", "doc_ndcg_at_10", "doc_recall_at_10",
)


def rank_by_quality(candidates: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Sorted best-first by the frozen priority order: doc_recall@50 >
    doc_mrr > doc_ndcg@10 > doc_recall@10, all descending."""
    return sorted(candidates, key=lambda c: tuple(-c[k] for k in QUALITY_PRIORITY_KEYS))


@dataclass(frozen=True)
class RoundSelectionResult:
    winner_row_id: str | None
    rationale: str
    flagged_for_user_decision: bool
    flag_reason: str | None

    def to_dict(self) -> dict:
        return {
            "winner_row_id": self.winner_row_id, "rationale": self.rationale,
            "flagged_for_user_decision": self.flagged_for_user_decision, "flag_reason": self.flag_reason,
        }


def select_round_winner(
    *, reference_row_id: str, candidates: Sequence[Mapping[str, Any]],
    bootstrap_vs_reference: Mapping[str, Mapping[str, Any]],
    tiebreak_key_fn: "Any" = None,
) -> RoundSelectionResult:
    """Applies the frozen Stage 8 rule to one round.

    `candidates`: every candidate in the round (including the reference
    itself), each a mapping with at least `row_id`, `split_mode`,
    `chunk_count`, and the four QUALITY_PRIORITY_KEYS metrics.
    `bootstrap_vs_reference`: for every non-reference row_id, a mapping
    with `recall50_hit_delta` (int, candidate hits - reference hits, out
    of 89), `mrr_ci` (lo, hi), `ndcg_ci` (lo, hi) - paired bootstrap
    results of that candidate against the reference.

    Never resolves a raised-Recall@50-but-regressed-MRR/nDCG trade-off on
    its own (Stage 8 "Regression protection") - returns
    flagged_for_user_decision=True instead, with `winner_row_id=None`."""
    by_id = {c["row_id"]: c for c in candidates}
    if reference_row_id not in by_id:
        raise Phase3AblationError(f"reference_row_id {reference_row_id!r} is not among the round's candidates")

    def _tied_with_reference() -> list[Mapping[str, Any]]:
        tied = [by_id[reference_row_id]]
        for row_id, bs in bootstrap_vs_reference.items():
            if row_id == reference_row_id:
                continue
            if is_practical_tie(recall50_hit_delta=bs["recall50_hit_delta"], mrr_ci=bs["mrr_ci"], ndcg_ci=bs["ndcg_ci"]):
                tied.append(by_id[row_id])
        return tied

    ranked = rank_by_quality(candidates)
    raw_best = ranked[0]
    reference = by_id[reference_row_id]

    if raw_best["row_id"] == reference_row_id:
        tied = _tied_with_reference()
        winner = apply_tiebreak(tied, key_fn=tiebreak_key_fn) if len(tied) > 1 else reference
        return RoundSelectionResult(
            winner_row_id=winner["row_id"],
            rationale=(
                f"{reference_row_id} ranks best on the frozen priority order "
                f"({', '.join(QUALITY_PRIORITY_KEYS)}); "
                + (f"engineering tie-break selected {winner['row_id']} among {len(tied)} practically-tied candidates."
                   if len(tied) > 1 else "no other candidate is even practically tied.")
            ),
            flagged_for_user_decision=False, flag_reason=None,
        )

    bs = bootstrap_vs_reference[raw_best["row_id"]]
    tie = is_practical_tie(recall50_hit_delta=bs["recall50_hit_delta"], mrr_ci=bs["mrr_ci"], ndcg_ci=bs["ndcg_ci"])
    if tie:
        tied = _tied_with_reference()
        winner = apply_tiebreak(tied, key_fn=tiebreak_key_fn)
        return RoundSelectionResult(
            winner_row_id=winner["row_id"],
            rationale=(
                f"{raw_best['row_id']} ranks best by raw metrics but is practically tied with reference "
                f"{reference_row_id} (Recall@50 hit delta={bs['recall50_hit_delta']}, MRR/nDCG@10 95% CIs "
                f"include 0); engineering tie-break selected {winner['row_id']} among {len(tied)} tied candidates."
            ),
            flagged_for_user_decision=False, flag_reason=None,
        )

    improves_top_metric = raw_best["doc_recall_at_50"] > reference["doc_recall_at_50"]
    credible_mrr_regression = bs["mrr_ci"][1] < 0.0
    credible_ndcg_regression = bs["ndcg_ci"][1] < 0.0
    if improves_top_metric and (credible_mrr_regression or credible_ndcg_regression):
        which = "doc_mrr" if credible_mrr_regression else "doc_ndcg@10"
        return RoundSelectionResult(
            winner_row_id=None,
            rationale="",
            flagged_for_user_decision=True,
            flag_reason=(
                f"{raw_best['row_id']} raises doc_recall@50 over {reference_row_id} but shows a credible "
                f"{which} regression (95% CI entirely below 0) - Stage 8 regression protection requires a "
                f"user decision rather than an automatic pick."
            ),
        )

    return RoundSelectionResult(
        winner_row_id=raw_best["row_id"],
        rationale=(
            f"{raw_best['row_id']} is a credible improvement over reference {reference_row_id} on the "
            f"frozen priority order with no regression-protection violation."
        ),
        flagged_for_user_decision=False, flag_reason=None,
    )


__all__ = [
    "BOOTSTRAP_SEED", "BOOTSTRAP_ITERATIONS", "ENCODER_MAX_SEQ_LENGTH_TOKENS",
    "WINDOW_SIZES", "OVERLAP_TOKEN_TABLE", "Phase3AblationError",
    "overlap_tokens_for", "ChunkCandidate",
    "round_a_candidates", "round_b_candidates", "round_c_candidates",
    "assert_frozen_scope", "assert_dev_split",
    "BootstrapResult", "paired_bootstrap_delta_ci",
    "is_practical_tie", "apply_tiebreak",
    "QUALITY_PRIORITY_KEYS", "rank_by_quality", "RoundSelectionResult", "select_round_winner",
]
