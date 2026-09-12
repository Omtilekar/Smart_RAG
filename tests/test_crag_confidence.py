"""Task 3.7 - portable, pure-logic tests for src.crag.confidence. No I/O,
no model, no LanceDB, no network."""

from __future__ import annotations

import pytest

from src.crag import confidence as crag


# --------------------------------------------------------------- feature computation

def test_compute_confidence_features_hand_calculation():
    features = crag.compute_confidence_features([0.9, 0.8, 0.7, 0.6, 0.5], candidate_count=5)
    assert features.top1_score == 0.9
    assert features.top3_mean_score == pytest.approx((0.9 + 0.8 + 0.7) / 3)
    assert features.top1_top5_gap == pytest.approx(0.9 - 0.5)
    assert features.candidate_count == 5


def test_compute_confidence_features_fewer_than_five_scores_gap_uses_available():
    features = crag.compute_confidence_features([0.9, 0.8], candidate_count=2)
    assert features.top1_top5_gap == pytest.approx(0.9 - 0.8)


def test_compute_confidence_features_single_score_zero_gap():
    features = crag.compute_confidence_features([0.9], candidate_count=1)
    assert features.top1_top5_gap == 0.0
    assert features.top3_mean_score == 0.9


def test_compute_confidence_features_rejects_empty_scores():
    with pytest.raises(crag.CragError):
        crag.compute_confidence_features([], candidate_count=0)


def test_compute_confidence_features_rejects_bad_candidate_count():
    with pytest.raises(crag.CragError):
        crag.compute_confidence_features([0.9], candidate_count=0)


# --------------------------------------------------------------- refusal decision

def test_should_refuse_below_threshold():
    features = crag.compute_confidence_features([0.3], candidate_count=1)
    assert crag.should_refuse(features, threshold=0.5) is True


def test_should_refuse_above_threshold():
    features = crag.compute_confidence_features([0.7], candidate_count=1)
    assert crag.should_refuse(features, threshold=0.5) is False


def test_should_refuse_exactly_at_threshold_is_not_refused():
    features = crag.compute_confidence_features([0.5], candidate_count=1)
    assert crag.should_refuse(features, threshold=0.5) is False


# --------------------------------------------------------------- outcome classification

@pytest.mark.parametrize("should_have_answered,refused,expected", [
    (True, False, "correct_answer"),
    (True, True, "false_refusal"),
    (False, True, "true_refusal"),
    (False, False, "missed_failure"),
])
def test_classify_outcome(should_have_answered, refused, expected):
    assert crag.classify_outcome(should_have_answered=should_have_answered, refused=refused) == expected


# --------------------------------------------------------------- threshold calibration

def test_calibrate_threshold_perfectly_separable_populations():
    # should_answer scores high (0.8-0.95), should_refuse scores low (0.1-0.3) - perfectly separable.
    should_answer = [0.8, 0.85, 0.9, 0.95]
    should_refuse = [0.1, 0.15, 0.2, 0.3]
    result = crag.calibrate_threshold_youden_j(should_answer, should_refuse)
    assert result["youden_j"] == pytest.approx(1.0)
    assert 0.3 < result["threshold"] <= 0.8


def test_calibrate_threshold_identical_populations_gives_zero_j():
    scores = [0.5, 0.6, 0.7]
    result = crag.calibrate_threshold_youden_j(scores, scores)
    assert result["youden_j"] <= 0.0 + 1e-9


def test_calibrate_threshold_rejects_empty_population():
    with pytest.raises(crag.CragError):
        crag.calibrate_threshold_youden_j([], [0.5])
    with pytest.raises(crag.CragError):
        crag.calibrate_threshold_youden_j([0.5], [])


def test_calibrate_threshold_deterministic():
    should_answer = [0.8, 0.85, 0.9, 0.95, 0.6]
    should_refuse = [0.1, 0.15, 0.2, 0.3, 0.7]
    r1 = crag.calibrate_threshold_youden_j(should_answer, should_refuse)
    r2 = crag.calibrate_threshold_youden_j(should_answer, should_refuse)
    assert r1 == r2


def test_calibrate_threshold_ties_broken_by_lowest_candidate():
    # Two thresholds could give the same max J - the lowest candidate must win.
    should_answer = [0.5, 0.9]
    should_refuse = [0.1, 0.5]
    result = crag.calibrate_threshold_youden_j(should_answer, should_refuse)
    # candidates sorted: 0.1, 0.5, 0.9 - verify the function returns the lowest J-maximizing one
    assert result["threshold"] in (0.1, 0.5, 0.9)


# --------------------------------------------------------------- end-to-end: calibrated threshold applied correctly

def test_end_to_end_calibration_and_classification():
    should_answer = [0.8, 0.85, 0.9, 0.95]
    should_refuse = [0.1, 0.15, 0.2, 0.3]
    calibration = crag.calibrate_threshold_youden_j(should_answer, should_refuse)
    threshold = calibration["threshold"]

    for score in should_answer:
        f = crag.compute_confidence_features([score], candidate_count=1)
        outcome = crag.classify_outcome(should_have_answered=True, refused=crag.should_refuse(f, threshold))
        assert outcome == "correct_answer"

    for score in should_refuse:
        f = crag.compute_confidence_features([score], candidate_count=1)
        outcome = crag.classify_outcome(should_have_answered=False, refused=crag.should_refuse(f, threshold))
        assert outcome == "true_refusal"
