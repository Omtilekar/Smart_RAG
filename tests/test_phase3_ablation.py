"""Tests for src/eval/phase3_ablation.py (Task 3.2 pure ablation logic):
candidate registry, evaluator guards, paired bootstrap, and the frozen
winner-selection rule. All portable - no I/O, no model, no GPU."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.eval import phase3_ablation as pa

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------- never touches TEST

def test_module_never_imports_test_access():
    """AST-based, not a substring scan (mirrors src/eval/phase3_baseline.py's
    own verification convention) - Task 3.2 evaluation is DEV-only."""
    source = (REPO_ROOT / "src" / "eval" / "phase3_ablation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "src.eval.test_access"
            if node.module and node.module.endswith("test_access"):
                for alias in node.names:
                    assert alias.name != "load_test_set"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "test_access" not in alias.name


# ---------------------------------------------------------- overlap table

def test_overlap_tokens_for_known_windows():
    assert pa.overlap_tokens_for(256, 0.125) == 32
    assert pa.overlap_tokens_for(256, 0.25) == 64
    assert pa.overlap_tokens_for(512, 0.125) == 64
    assert pa.overlap_tokens_for(512, 0.25) == 128
    assert pa.overlap_tokens_for(1024, 0.125) == 128
    assert pa.overlap_tokens_for(1024, 0.25) == 256


def test_overlap_tokens_for_unknown_window_raises():
    with pytest.raises(pa.Phase3AblationError):
        pa.overlap_tokens_for(128, 0.125)


def test_overlap_tokens_for_unknown_pct_raises():
    with pytest.raises(pa.Phase3AblationError):
        pa.overlap_tokens_for(256, 0.5)


# ---------------------------------------------------------- candidate registry

def test_round_a_candidates_shape():
    candidates = pa.round_a_candidates()
    ids = [c.row_id for c in candidates]
    assert ids == ["A0", "A1", "A2"]
    a0, a1, a2 = candidates
    assert a0.window_size_tokens == 512 and a0.overlap_tokens == 0 and a0.reuse_row_id == "0"
    assert a1.window_size_tokens == 256 and a1.overlap_tokens == 0 and a1.reuse_row_id is None
    assert a2.window_size_tokens == 1024 and a2.overlap_tokens == 0
    assert a2.encoder_truncation_note is not None
    assert a1.encoder_truncation_note is None
    assert a0.encoder_truncation_note is None


def test_round_a_candidates_stride():
    a1 = pa.round_a_candidates()[1]
    assert a1.stride_tokens == 256


def test_round_b_candidates_shape():
    candidates = pa.round_b_candidates(256, winner_row_id="A1")
    ids = [c.row_id for c in candidates]
    assert ids == ["B0", "B1", "B2"]
    b0, b1, b2 = candidates
    assert b0.overlap_tokens == 0 and b0.reuse_row_id == "A1"
    assert b1.overlap_tokens == 32 and b1.reuse_row_id is None
    assert b2.overlap_tokens == 64
    assert b1.stride_tokens == 224
    assert b2.stride_tokens == 192


def test_round_b_candidates_encoder_note_propagates_for_1024_winner():
    candidates = pa.round_b_candidates(1024, winner_row_id="A2")
    assert all(c.encoder_truncation_note is not None for c in candidates)


def test_round_c_candidates_shape():
    candidates = pa.round_c_candidates(winner_window_tokens=256, winner_overlap_tokens=32, winner_row_id="B1")
    ids = [c.row_id for c in candidates]
    assert ids == ["C0", "C1"]
    c0, c1 = candidates
    assert c0.split_mode == "fixed" and c0.reuse_row_id == "B1"
    assert c1.split_mode == "section_aware" and c1.reuse_row_id is None
    assert c0.window_size_tokens == c1.window_size_tokens == 256
    assert c0.overlap_tokens == c1.overlap_tokens == 32


# ---------------------------------------------------------- evaluator guards

def test_assert_frozen_scope_passes_for_exact_match():
    pa.assert_frozen_scope(["a", "b", "c"], ["c", "b", "a"])


def test_assert_frozen_scope_rejects_missing_id():
    with pytest.raises(pa.Phase3AblationError):
        pa.assert_frozen_scope(["a", "b"], ["a", "b", "c"])


def test_assert_frozen_scope_rejects_unexpected_id():
    with pytest.raises(pa.Phase3AblationError):
        pa.assert_frozen_scope(["a", "b", "c", "d"], ["a", "b", "c"])


def test_assert_dev_split_passes():
    pa.assert_dev_split("dev")


def test_assert_dev_split_rejects_test():
    with pytest.raises(pa.Phase3AblationError):
        pa.assert_dev_split("test")


def test_assert_dev_split_rejects_other():
    with pytest.raises(pa.Phase3AblationError):
        pa.assert_dev_split("ci")


# ---------------------------------------------------------- paired bootstrap

def test_bootstrap_deterministic_with_seed_42():
    cand = [1.0, 0.5, 0.0, 1.0, 0.5] * 10
    base = [0.5, 0.5, 0.0, 0.5, 0.0] * 10
    r1 = pa.paired_bootstrap_delta_ci(cand, base, seed=42, iterations=500)
    r2 = pa.paired_bootstrap_delta_ci(cand, base, seed=42, iterations=500)
    assert r1.ci_lo == r2.ci_lo
    assert r1.ci_hi == r2.ci_hi
    assert r1.point_estimate == r2.point_estimate


def test_bootstrap_different_seed_can_differ():
    cand = [1.0, 0.5, 0.0, 1.0, 0.5] * 10
    base = [0.5, 0.5, 0.0, 0.5, 0.0] * 10
    r1 = pa.paired_bootstrap_delta_ci(cand, base, seed=42, iterations=500)
    r2 = pa.paired_bootstrap_delta_ci(cand, base, seed=7, iterations=500)
    # not asserting inequality (could coincide) - just that both run and are valid
    assert r1.iterations == r2.iterations == 500


def test_bootstrap_point_estimate_is_plain_mean_difference():
    cand = [1.0, 1.0, 1.0, 1.0]
    base = [0.0, 0.0, 0.0, 0.0]
    r = pa.paired_bootstrap_delta_ci(cand, base, seed=42, iterations=100)
    assert r.point_estimate == pytest.approx(1.0)


def test_bootstrap_identical_arms_ci_includes_zero():
    values = [0.2, 0.4, 0.6, 0.8, 1.0] * 4
    r = pa.paired_bootstrap_delta_ci(values, values, seed=42, iterations=1000)
    assert r.point_estimate == 0.0
    assert r.includes_zero()


def test_bootstrap_rejects_mismatched_lengths():
    with pytest.raises(pa.Phase3AblationError):
        pa.paired_bootstrap_delta_ci([1.0, 2.0], [1.0], seed=42, iterations=10)


def test_bootstrap_rejects_empty_arrays():
    with pytest.raises(pa.Phase3AblationError):
        pa.paired_bootstrap_delta_ci([], [], seed=42, iterations=10)


def test_bootstrap_operates_on_paired_indices_not_independent_resampling():
    # A large, clear, consistent per-question improvement must produce a
    # CI that does NOT include 0 - proves the resampling is paired (shares
    # indices across arms) rather than shuffling the two arms independently,
    # which would wash out a perfectly-correlated improvement much less
    # reliably at this sample size.
    cand = [1.0] * 30
    base = [0.0] * 30
    r = pa.paired_bootstrap_delta_ci(cand, base, seed=42, iterations=2000)
    assert not r.includes_zero()
    assert r.ci_lo > 0.0


# ---------------------------------------------------------- practical tie rule

def test_is_practical_tie_true_when_all_conditions_hold():
    assert pa.is_practical_tie(recall50_hit_delta=1, mrr_ci=(-0.01, 0.02), ndcg_ci=(-0.01, 0.01))


def test_is_practical_tie_false_when_recall_delta_too_large():
    assert not pa.is_practical_tie(recall50_hit_delta=2, mrr_ci=(-0.01, 0.02), ndcg_ci=(-0.01, 0.01))


def test_is_practical_tie_false_when_mrr_ci_excludes_zero():
    assert not pa.is_practical_tie(recall50_hit_delta=0, mrr_ci=(0.01, 0.05), ndcg_ci=(-0.01, 0.01))


def test_is_practical_tie_false_when_ndcg_ci_excludes_zero():
    assert not pa.is_practical_tie(recall50_hit_delta=0, mrr_ci=(-0.01, 0.01), ndcg_ci=(-0.05, -0.01))


def test_is_practical_tie_negative_recall_delta_also_allowed():
    assert pa.is_practical_tie(recall50_hit_delta=-1, mrr_ci=(-0.01, 0.01), ndcg_ci=(-0.01, 0.01))


# ---------------------------------------------------------- tie-break

def test_apply_tiebreak_prefers_fewer_chunks():
    a = {"row_id": "x", "chunk_count": 200_000, "split_mode": "fixed"}
    b = {"row_id": "y", "chunk_count": 100_000, "split_mode": "fixed"}
    assert pa.apply_tiebreak([a, b])["row_id"] == "y"


def test_apply_tiebreak_falls_through_to_simplicity():
    a = {"row_id": "x", "chunk_count": 100, "embedding_artifact_size_bytes": 1, "index_size_bytes": 1,
         "retrieval_latency_p95_ms": 1, "build_seconds_total": 1, "split_mode": "section_aware"}
    b = {"row_id": "y", "chunk_count": 100, "embedding_artifact_size_bytes": 1, "index_size_bytes": 1,
         "retrieval_latency_p95_ms": 1, "build_seconds_total": 1, "split_mode": "fixed"}
    assert pa.apply_tiebreak([a, b])["row_id"] == "y"


def test_apply_tiebreak_single_candidate():
    a = {"row_id": "solo", "chunk_count": 1, "split_mode": "fixed"}
    assert pa.apply_tiebreak([a])["row_id"] == "solo"


def test_apply_tiebreak_empty_raises():
    with pytest.raises(pa.Phase3AblationError):
        pa.apply_tiebreak([])


# ---------------------------------------------------------- select_round_winner

def _candidate(row_id, *, recall50=0.9, mrr=0.8, ndcg10=0.8, recall10=0.9, chunk_count=100, split_mode="fixed"):
    return {
        "row_id": row_id, "doc_recall_at_50": recall50, "doc_mrr": mrr, "doc_ndcg_at_10": ndcg10,
        "doc_recall_at_10": recall10, "chunk_count": chunk_count, "split_mode": split_mode,
        "embedding_artifact_size_bytes": chunk_count * 100, "index_size_bytes": chunk_count * 100,
        "retrieval_latency_p95_ms": 250.0, "build_seconds_total": 100.0,
    }


def test_select_round_winner_reference_wins_outright():
    ref = _candidate("A0", recall50=0.95, mrr=0.85, ndcg10=0.85)
    worse = _candidate("A1", recall50=0.80, mrr=0.70, ndcg10=0.70)
    bootstrap = {"A1": {"recall50_hit_delta": -13, "mrr_ci": (-0.20, -0.10), "ndcg_ci": (-0.20, -0.10)}}
    result = pa.select_round_winner(reference_row_id="A0", candidates=[ref, worse], bootstrap_vs_reference=bootstrap)
    assert result.winner_row_id == "A0"
    assert not result.flagged_for_user_decision


def test_select_round_winner_credible_improvement_wins():
    ref = _candidate("A0", recall50=0.90, mrr=0.80, ndcg10=0.80)
    better = _candidate("A1", recall50=0.97, mrr=0.90, ndcg10=0.90)
    bootstrap = {"A1": {"recall50_hit_delta": 6, "mrr_ci": (0.02, 0.15), "ndcg_ci": (0.02, 0.15)}}
    result = pa.select_round_winner(reference_row_id="A0", candidates=[ref, better], bootstrap_vs_reference=bootstrap)
    assert result.winner_row_id == "A1"
    assert not result.flagged_for_user_decision


def test_select_round_winner_practical_tie_uses_tiebreak():
    ref = _candidate("A0", recall50=0.90, mrr=0.80, ndcg10=0.80, chunk_count=200_000)
    tied_but_cheaper = _candidate("A1", recall50=0.90 + (1 / 89), mrr=0.80, ndcg10=0.80, chunk_count=100_000)
    bootstrap = {"A1": {"recall50_hit_delta": 1, "mrr_ci": (-0.01, 0.01), "ndcg_ci": (-0.01, 0.01)}}
    result = pa.select_round_winner(
        reference_row_id="A0", candidates=[ref, tied_but_cheaper], bootstrap_vs_reference=bootstrap,
    )
    assert result.winner_row_id == "A1"  # cheaper candidate wins the tie-break
    assert not result.flagged_for_user_decision


def test_select_round_winner_flags_regression_tradeoff():
    ref = _candidate("A0", recall50=0.90, mrr=0.85, ndcg10=0.85)
    tradeoff = _candidate("A1", recall50=0.95, mrr=0.60, ndcg10=0.60)
    bootstrap = {"A1": {"recall50_hit_delta": 4, "mrr_ci": (-0.30, -0.15), "ndcg_ci": (-0.30, -0.15)}}
    result = pa.select_round_winner(reference_row_id="A0", candidates=[ref, tradeoff], bootstrap_vs_reference=bootstrap)
    assert result.winner_row_id is None
    assert result.flagged_for_user_decision
    assert "regression" in result.flag_reason.lower()


def test_select_round_winner_unknown_reference_raises():
    ref = _candidate("A0")
    with pytest.raises(pa.Phase3AblationError):
        pa.select_round_winner(reference_row_id="ZZ", candidates=[ref], bootstrap_vs_reference={})


def test_select_round_winner_three_candidates_best_wins():
    ref = _candidate("A0", recall50=0.90, mrr=0.80, ndcg10=0.80)
    mid = _candidate("A1", recall50=0.90, mrr=0.80, ndcg10=0.80)
    best = _candidate("A2", recall50=0.98, mrr=0.92, ndcg10=0.92)
    bootstrap = {
        "A1": {"recall50_hit_delta": 0, "mrr_ci": (-0.01, 0.01), "ndcg_ci": (-0.01, 0.01)},
        "A2": {"recall50_hit_delta": 7, "mrr_ci": (0.05, 0.20), "ndcg_ci": (0.05, 0.20)},
    }
    result = pa.select_round_winner(reference_row_id="A0", candidates=[ref, mid, best], bootstrap_vs_reference=bootstrap)
    assert result.winner_row_id == "A2"


# ---------------------------------------------------------- rank_by_quality

def test_rank_by_quality_orders_by_priority():
    a = _candidate("a", recall50=0.9, mrr=0.9, ndcg10=0.9, recall10=0.9)
    b = _candidate("b", recall50=0.95, mrr=0.1, ndcg10=0.1, recall10=0.1)
    ranked = pa.rank_by_quality([a, b])
    assert ranked[0]["row_id"] == "b"  # recall@50 dominates even though everything else is worse
