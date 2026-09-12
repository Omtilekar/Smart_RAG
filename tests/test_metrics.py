"""Task 2.6 - hand-verified unit tests for src/eval/metrics.py.

Every expected value below is derived BY HAND (shown in comments) using
raw arithmetic (math.log2, plain division) - never by calling the
production function under test to produce its own "expected" value. See
project_plan/PHASE2_METRIC_TESTS.md for the same derivations written out
as documentation.

Toy fixture (Section 37), k=10, single relevant document per question:

    Q1: relevant target at rank 1
    Q2: relevant target at rank 2
    Q3: relevant target at rank 10
    Q4: relevant target at rank 11   (outside k=10 - counts as a miss)
    Q5: no relevant result at all

    first_hit_rank:  Q1=1, Q2=2, Q3=10, Q4=None, Q5=None
    hit@10:          Q1=T, Q2=T, Q3=T,  Q4=F,    Q5=F
    RR:              Q1=1, Q2=0.5, Q3=0.1, Q4=0, Q5=0
    doc_ndcg@10 (num_relevant=1 each, Q5 num_relevant=0 -> N/A):
      Q1 = 1/log2(2) / (1/log2(2)) = 1.0            (perfect ranking)
      Q2 = 1/log2(3) / 1.0         = 0.6309297535714575
      Q3 = 1/log2(11) / 1.0        = 0.2890648263178879
      Q4 = 0 / 1.0                 = 0.0
      Q5 = not applicable (num_relevant=0)

    recall@10   = 3/5 = 0.6         (Q1,Q2,Q3 hit; Q4,Q5 miss)
    MRR         = (1 + 0.5 + 0.1 + 0 + 0) / 5 = 0.32
    mean nDCG@10 over applicable Q1-Q4 = (1.0+0.6309297535714575+0.2890648263178879+0.0)/4
                = 0.47999864497233635
"""

from __future__ import annotations

import math

import pytest

from src.eval.metrics import (
    MetricInputError,
    aggregate_rate,
    first_hit_rank,
    hit_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
    dcg_at_k,
    idcg_at_k,
    ndcg_at_k,
    precision_at_k,
    numeric_exact_match,
    correct_refusal,
)
from src.eval import baseline_metrics


TOY_FIXTURE = {
    "Q1": {"rank": 1, "k": 10},
    "Q2": {"rank": 2, "k": 10},
    "Q3": {"rank": 10, "k": 10},
    "Q4": {"rank": 11, "k": 10},  # outside window - built as a genuine miss below
    "Q5": {"rank": None, "k": 10},
}


def _ranked_ids_for(rank: int | None, k: int) -> list[str]:
    """Builds a k-length ranked ID list with 'TARGET' placed at `rank`
    (1-indexed) if not None, filler IDs elsewhere. rank > k means TARGET
    never appears in the returned list (genuinely outside the window)."""
    ids = [f"filler-{i}" for i in range(1, k + 1)]
    if rank is not None and rank <= k:
        ids[rank - 1] = "TARGET"
    return ids


# --------------------------------------------------------------- rate aggregation

def test_aggregate_rate_hand_example_3_of_4():
    # Q1 hit, Q2 miss, Q3 hit, Q4 hit -> numerator=3, denominator=4, value=0.75
    result = aggregate_rate([True, False, True, True])
    assert result == {"value": 0.75, "numerator": 3, "denominator": 4}


def test_aggregate_rate_numerator_denominator_value_agree():
    result = aggregate_rate([True, True, False, False, False])
    assert result["numerator"] / result["denominator"] == result["value"]


def test_aggregate_rate_empty_raises():
    with pytest.raises(MetricInputError):
        aggregate_rate([])


def test_aggregate_rate_all_true():
    assert aggregate_rate([True, True]) == {"value": 1.0, "numerator": 2, "denominator": 2}


def test_aggregate_rate_all_false():
    assert aggregate_rate([False, False, False]) == {"value": 0.0, "numerator": 0, "denominator": 3}


def test_na_is_not_zero_excluded_questions_shrink_denominator():
    # 2 applicable questions, both hits, one N/A question excluded entirely
    # (never appended as False) -> rate is 1.0, not 2/3.
    flags = [True, True]  # the N/A question was never added here
    result = aggregate_rate(flags)
    assert result["value"] == 1.0
    assert result["denominator"] == 2


# --------------------------------------------------------------- doc_recall boundary (first_hit_rank/hit_at_k)

def test_target_at_rank_1_is_hit():
    ranked = _ranked_ids_for(1, 10)
    rank = first_hit_rank(ranked, {"TARGET"}, k=10)
    assert rank == 1
    assert hit_at_k(rank, k=10) is True


def test_target_at_rank_10_is_hit():
    ranked = _ranked_ids_for(10, 10)
    rank = first_hit_rank(ranked, {"TARGET"}, k=10)
    assert rank == 10
    assert hit_at_k(rank, k=10) is True


def test_target_at_rank_11_is_miss():
    # TARGET genuinely does not appear in the top-10 list at all.
    ranked = [f"filler-{i}" for i in range(1, 11)]
    rank = first_hit_rank(ranked, {"TARGET"}, k=10)
    assert rank is None
    assert hit_at_k(rank, k=10) is False


def test_no_target_is_miss():
    ranked = [f"filler-{i}" for i in range(1, 11)]
    rank = first_hit_rank(ranked, {"TARGET"}, k=10)
    assert rank is None


def test_empty_results_is_miss_not_error():
    rank = first_hit_rank([], {"TARGET"}, k=10)
    assert rank is None


def test_fewer_than_k_results_still_works():
    rank = first_hit_rank(["a", "TARGET", "c"], {"TARGET"}, k=10)
    assert rank == 2


def test_multiple_relevant_first_one_wins():
    # relevant set has 2 members; the ranked list surfaces the later one
    # first - first_hit_rank must report the EARLIEST matching rank.
    ranked = ["x", "B", "y", "A", "z"]
    rank = first_hit_rank(ranked, {"A", "B", "C"}, k=5)
    assert rank == 2  # B at rank 2, before A at rank 4


def test_duplicate_document_chunks_first_hit_rank_is_first_occurrence():
    # rank1 -> doc X chunk1, rank2 -> doc X chunk2, rank3 -> target doc Y chunk1
    ranked_document_ids = ["X", "X", "Y"]
    rank = first_hit_rank(ranked_document_ids, {"Y"}, k=3)
    assert rank == 3  # no de-dup before cutoff - matches Task 1.10 semantics


def test_invalid_k_rejected():
    with pytest.raises(MetricInputError):
        first_hit_rank(["a"], {"a"}, k=0)


# --------------------------------------------------------------- regression vs Task 1.10 baseline_metrics

class _FakeResult:
    def __init__(self, rank, chunk_id, document_id):
        self.rank = rank
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.score = 1.0
        self.distance = 0.0


def test_agrees_with_task_1_10_baseline_metrics_hit_and_rank():
    # Same fixture fed to both the frozen Task 1.10 implementation and
    # this module's generic first_hit_rank - must agree exactly.
    retrieved = [
        _FakeResult(1, "c1", "docA"), _FakeResult(2, "c2", "docA"),
        _FakeResult(3, "c3", "docB"), _FakeResult(4, "c4", "docC"),
        _FakeResult(5, "c5", "docC"), _FakeResult(6, "c6", "docD"),
        _FakeResult(7, "c7", "docD"), _FakeResult(8, "c8", "docE"),
        _FakeResult(9, "c9", "docF"), _FakeResult(10, "c10", "docTARGET"),
    ]
    legacy = baseline_metrics.evaluate_question(
        question_id="q1", question="Q?", category="numeric",
        target_document_id="docTARGET", retrieved_results=retrieved, k=10,
    )
    document_ids = [r.document_id for r in retrieved]
    generic_rank = first_hit_rank(document_ids, {"docTARGET"}, k=10)
    assert legacy.hit is True
    assert legacy.first_hit_rank == generic_rank == 10


def test_agrees_with_task_1_10_baseline_metrics_miss():
    retrieved = [_FakeResult(i, f"c{i}", f"doc{i}") for i in range(1, 11)]
    legacy = baseline_metrics.evaluate_question(
        question_id="q1", question="Q?", category="numeric",
        target_document_id="docTARGET", retrieved_results=retrieved, k=10,
    )
    document_ids = [r.document_id for r in retrieved]
    generic_rank = first_hit_rank(document_ids, {"docTARGET"}, k=10)
    assert legacy.hit is False
    assert legacy.first_hit_rank is None
    assert generic_rank is None


# --------------------------------------------------------------- MRR

def test_mrr_relevant_at_rank_1():
    assert reciprocal_rank(1) == 1.0


def test_mrr_relevant_at_rank_2():
    assert reciprocal_rank(2) == 0.5


def test_mrr_relevant_at_later_rank():
    assert reciprocal_rank(4) == 0.25


def test_mrr_no_relevant_result_is_zero():
    assert reciprocal_rank(None) == 0.0


def test_mrr_invalid_rank_rejected():
    with pytest.raises(MetricInputError):
        reciprocal_rank(0)


def test_mrr_never_mean_rank_or_inverse_mean_rank():
    ranks = [1, 2, 4, None]
    rr = [reciprocal_rank(r) for r in ranks]
    mrr = mean_reciprocal_rank(rr)
    mean_rank_of_hits = sum(r for r in ranks if r is not None) / 3
    assert mrr != mean_rank_of_hits
    assert mrr != 1 / mean_rank_of_hits


def test_mrr_hand_derived_toy_fixture():
    # ranks = [1, 2, 4, miss] -> RR = [1, 0.5, 0.25, 0] -> MRR = 1.75/4 = 0.4375
    ranks = [1, 2, 4, None]
    rr = [reciprocal_rank(r) for r in ranks]
    assert rr == [1.0, 0.5, 0.25, 0.0]
    assert mean_reciprocal_rank(rr) == pytest.approx(0.4375, abs=1e-12)


def test_mrr_full_toy_fixture_q1_to_q5():
    ranks = [1, 2, 10, None, None]  # Q4's rank-11 hit is outside k=10 -> None
    rr = [reciprocal_rank(r) for r in ranks]
    assert rr == [1.0, 0.5, 0.1, 0.0, 0.0]
    assert mean_reciprocal_rank(rr) == pytest.approx(0.32, abs=1e-12)


def test_mrr_empty_raises():
    with pytest.raises(MetricInputError):
        mean_reciprocal_rank([])


# --------------------------------------------------------------- nDCG@k

def test_ndcg_perfect_ranking_equals_one():
    # single relevant item at rank 1, num_relevant=1
    relevances = [1, 0, 0]
    result = ndcg_at_k(relevances, num_relevant=1, k=3)
    assert result == pytest.approx(1.0, abs=1e-12)


def test_ndcg_reversed_ranking_hand_derived():
    # relevant item at the LAST position of a 3-item list, num_relevant=1
    # DCG = 1/log2(4) ; IDCG = 1/log2(2) = 1
    relevances = [0, 0, 1]
    expected_dcg = 1 / math.log2(4)
    expected_ndcg = expected_dcg / 1.0
    result = ndcg_at_k(relevances, num_relevant=1, k=3)
    assert 0 < result < 1
    assert result == pytest.approx(expected_ndcg, abs=1e-12)


def test_ndcg_zero_hit():
    relevances = [0, 0, 0]
    result = ndcg_at_k(relevances, num_relevant=1, k=3)
    assert result == pytest.approx(0.0, abs=1e-12)


def test_ndcg_no_relevant_items_in_gold_is_not_applicable():
    relevances = [0, 0, 0]
    result = ndcg_at_k(relevances, num_relevant=0, k=3)
    assert result is None  # documented N/A convention, never a fake 0.0 or 1.0


def test_ndcg_cutoff_boundary_rank_10_contributes_rank_11_does_not():
    # relevant item exactly at rank 10 contributes; the same item pushed
    # to rank 11 (outside k=10) does not.
    relevances_at_10 = [0] * 9 + [1]
    relevances_at_11 = [0] * 10 + [1]  # 11 entries, k=10 truncates the last
    r10 = ndcg_at_k(relevances_at_10, num_relevant=1, k=10)
    r11 = ndcg_at_k(relevances_at_11, num_relevant=1, k=10)
    assert r10 == pytest.approx(1 / math.log2(11), abs=1e-12)
    assert r11 == pytest.approx(0.0, abs=1e-12)


def test_ndcg_toy_fixture_hand_derived_per_question():
    # Q1 (rank1,relevant=1): DCG=1/log2(2)=1.0, IDCG=1.0 -> nDCG=1.0
    assert ndcg_at_k([1], num_relevant=1, k=1) == pytest.approx(1.0, abs=1e-12)
    # Q2 (rank2): relevances=[0,1] -> DCG=1/log2(3), IDCG=1/log2(2)=1
    q2 = ndcg_at_k([0, 1], num_relevant=1, k=2)
    assert q2 == pytest.approx(1 / math.log2(3), abs=1e-12)
    # Q3 (rank10 of 10): DCG=1/log2(11), IDCG=1
    relevances_q3 = [0] * 9 + [1]
    q3 = ndcg_at_k(relevances_q3, num_relevant=1, k=10)
    assert q3 == pytest.approx(1 / math.log2(11), abs=1e-12)
    # Q4 (miss within k window): DCG=0
    q4 = ndcg_at_k([0] * 10, num_relevant=1, k=10)
    assert q4 == pytest.approx(0.0, abs=1e-12)
    # mean over Q1-Q4 (Q5 excluded, num_relevant=0 -> N/A)
    mean_ndcg = (1.0 + 1 / math.log2(3) + 1 / math.log2(11) + 0.0) / 4
    assert mean_ndcg == pytest.approx(0.47999864497233635, abs=1e-12)


def test_ndcg_multi_relevant_fixture_hand_derived():
    # gold relevant: A, B, C (num_relevant=3); retrieved: X, B, Y, A, Z
    # relevances aligned to ranks 1..5: [0, 1, 0, 1, 0]
    relevances = [0, 1, 0, 1, 0]
    expected_dcg = 1 / math.log2(3) + 1 / math.log2(5)          # B at rank2, A at rank4
    expected_idcg = 1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)  # 3 relevant ideally at ranks 1-3
    expected_ndcg = expected_dcg / expected_idcg
    result = ndcg_at_k(relevances, num_relevant=3, k=5)
    assert result == pytest.approx(expected_ndcg, abs=1e-12)
    assert result == pytest.approx(0.49818925746641285, abs=1e-9)


def test_ndcg_binary_relevance_enforced():
    with pytest.raises(MetricInputError):
        dcg_at_k([2, 0, 1], k=3)  # graded relevance not supported


def test_ndcg_range_invariant_binary():
    for k in (1, 5, 10):
        for relevances in ([1] + [0] * (k - 1), [0] * k):
            result = ndcg_at_k(relevances, num_relevant=1, k=k)
            assert 0.0 <= result <= 1.0


def test_idcg_zero_relevant_zero_denominator_handled():
    assert idcg_at_k(0, k=5) == 0.0


# --------------------------------------------------------------- numeric exact match

def test_numeric_exact_match_same_value():
    assert numeric_exact_match(gold_value="1000000.0", gold_unit="USD", predicted_value="1000000.0", predicted_unit="USD") is True


def test_numeric_exact_match_different_value():
    assert numeric_exact_match(gold_value="1000000.0", gold_unit="USD", predicted_value="999999.0", predicted_unit="USD") is False


def test_numeric_exact_match_zero():
    assert numeric_exact_match(gold_value="0.0", gold_unit="USD", predicted_value="0.0", predicted_unit="USD") is True


def test_numeric_exact_match_negative():
    assert numeric_exact_match(gold_value="-500.0", gold_unit="USD", predicted_value="-500.0", predicted_unit="USD") is True


def test_numeric_exact_match_negative_vs_positive():
    assert numeric_exact_match(gold_value="-500.0", gold_unit="USD", predicted_value="500.0", predicted_unit="USD") is False


def test_numeric_exact_match_large_value():
    assert numeric_exact_match(gold_value="895429000000.0", gold_unit="USD", predicted_value="895429000000.0", predicted_unit="USD") is True


def test_numeric_exact_match_small_decimal():
    assert numeric_exact_match(gold_value="0.01", gold_unit="USD", predicted_value="0.01", predicted_unit="USD") is True


def test_numeric_exact_match_representation_equivalence():
    # "1000000", "1000000.0", "1e6" are the same canonical float value
    assert numeric_exact_match(gold_value="1000000.0", gold_unit="USD", predicted_value="1e6", predicted_unit="USD") is True
    assert numeric_exact_match(gold_value="1000000", gold_unit="USD", predicted_value="1000000.0", predicted_unit="USD") is True


def test_numeric_exact_match_eps_case():
    # frozen registry unit is plain "USD" for EPS tags (verified in Task
    # 2.2 - never "USD/shares") - see configs/eval_tags.yaml.
    assert numeric_exact_match(gold_value="2.31", gold_unit="USD", predicted_value="2.31", predicted_unit="USD") is True


def test_numeric_exact_match_same_value_wrong_unit():
    assert numeric_exact_match(gold_value="100.0", gold_unit="USD", predicted_value="100.0", predicted_unit="shares") is False


def test_numeric_exact_match_invalid_predicted_parse_raises():
    with pytest.raises(MetricInputError):
        numeric_exact_match(gold_value="100.0", gold_unit="USD", predicted_value="not_a_number", predicted_unit="USD")


def test_numeric_exact_match_invalid_gold_parse_raises():
    with pytest.raises(MetricInputError):
        numeric_exact_match(gold_value="not_a_number", gold_unit="USD", predicted_value="100.0", predicted_unit="USD")


# --------------------------------------------------------------- correct refusal

def test_correct_refusal_match():
    assert correct_refusal(expected_behavior="refuse_insufficient_evidence", observed_behavior="refuse_insufficient_evidence") is True


def test_correct_refusal_mismatch():
    assert correct_refusal(expected_behavior="refuse_insufficient_evidence", observed_behavior="answered_anyway") is False


def test_correct_refusal_aggregate_hand_example():
    # expected refusal cases = 4, correct refusals = 3 -> rate = 0.75
    flags = [
        correct_refusal(expected_behavior="refusal", observed_behavior="refusal"),
        correct_refusal(expected_behavior="refusal", observed_behavior="refusal"),
        correct_refusal(expected_behavior="refusal", observed_behavior="refusal"),
        correct_refusal(expected_behavior="refusal", observed_behavior="answered"),
    ]
    result = aggregate_rate(flags)
    assert result == {"value": 0.75, "numerator": 3, "denominator": 4}


# --------------------------------------------------------------- citation_format_compliance regression (aggregation only)

def test_citation_format_compliance_synthetic_regression():
    # 8 valid, 2 invalid -> 8/10 = 0.8. Does NOT call OpenRouter, does NOT
    # regenerate the historical Task 1.7a answers, does NOT claim the
    # Phase 1 8/10 warning is resolved - purely tests aggregation math.
    flags = [True] * 8 + [False] * 2
    result = aggregate_rate(flags)
    assert result == {"value": 0.8, "numerator": 8, "denominator": 10}


# --------------------------------------------------------------- determinism / property invariants

def test_recall_range_invariant():
    for flags in ([True], [False], [True, False, True]):
        result = aggregate_rate(flags)
        assert 0.0 <= result["value"] <= 1.0


def test_mrr_range_invariant():
    for ranks in ([1], [None], [1, 2, None, 5]):
        rr = [reciprocal_rank(r) for r in ranks]
        assert 0.0 <= mean_reciprocal_rank(rr) <= 1.0


def test_moving_first_relevant_result_downward_cannot_improve_rr():
    assert reciprocal_rank(2) <= reciprocal_rank(1)
    assert reciprocal_rank(5) <= reciprocal_rank(2)


def test_adding_irrelevant_result_before_first_relevant_cannot_improve_rr():
    ranked_before = ["TARGET", "x", "y"]
    ranked_after = ["z", "TARGET", "x", "y"]
    rank_before = first_hit_rank(ranked_before, {"TARGET"}, k=10)
    rank_after = first_hit_rank(ranked_after, {"TARGET"}, k=10)
    assert reciprocal_rank(rank_after) <= reciprocal_rank(rank_before)


def test_metrics_module_has_no_io_dependencies():
    import inspect
    from src.eval import metrics as mod
    source = inspect.getsource(mod)
    for forbidden in ("duckdb", "open(", "requests", "subprocess", "OpenRouter"):
        assert forbidden not in source


# --------------------------------------------------------------- eval_store round trip (Section 44)
#
# Proves metric math and Task 2.5 persistence agree on representation.
# Uses an in-memory DuckDB connection - never the real eval.duckdb, never
# TEST, never retrieval/generation.

def test_metric_round_trip_through_eval_store():
    import duckdb
    from src.eval import eval_store as es

    con = duckdb.connect(":memory:")
    es.initialize_schema(con)

    run_id = es.start_run(
        con, split="ci", eval_set_version="phase2-v1", source_dataset_sha256="s" * 64,
        split_version="phase2-split-v1", split_assignment_sha256="a" * 64,
        question_set_sha256="q" * 64, question_count=5, expected_question_count=5,
    )

    # 5-question synthetic doc-recall fixture matching the toy fixture above
    ranks = [1, 2, 10, None, None]
    hits = [hit_at_k(r, k=10) for r in ranks]
    for i, (rank, hit) in enumerate(zip(ranks, hits), start=1):
        es.record_question_result(
            con, run_id=run_id, question_id=f"synthetic-q{i}", category="numeric", status="success",
            doc_first_hit_rank=rank, latency_ms=1.0,
        )

    recall_result = aggregate_rate(hits)
    assert recall_result == {"value": 0.6, "numerator": 3, "denominator": 5}

    metric_id = es.record_metric(
        con, run_id=run_id, metric_name="doc_recall@10", metric_version="1.0", scope="overall",
        value=recall_result["value"], numerator=recall_result["numerator"], denominator=recall_result["denominator"],
    )
    assert metric_id

    row = con.execute(
        "SELECT metric_name, metric_version, value, numerator, denominator, scope FROM eval_metrics WHERE run_id = ?",
        [run_id],
    ).fetchone()
    assert row == ("doc_recall@10", "1.0", 0.6, 3, 5, "overall")

    # independently re-aggregate from the persisted per-question rows,
    # never trusting the stored eval_metrics row to prove itself
    persisted_ranks = con.execute(
        "SELECT doc_first_hit_rank FROM eval_question_results WHERE run_id = ? ORDER BY question_id",
        [run_id],
    ).fetchall()
    recomputed_hits = [hit_at_k(r[0], k=10) for r in persisted_ranks]
    recomputed = aggregate_rate(recomputed_hits)
    assert recomputed == recall_result

    es.complete_run(con, run_id=run_id)
    assert es.get_run(con, run_id)["status"] == "complete"
    con.close()


# --------------------------------------------------------------- Task 3.6: precision_at_k

def test_precision_at_k_hand_calculation():
    assert precision_at_k([1, 0, 0, 0, 0], k=5) == pytest.approx(0.2)
    assert precision_at_k([1, 1, 1, 1, 1], k=5) == pytest.approx(1.0)
    assert precision_at_k([0, 0, 0, 0, 0], k=5) == pytest.approx(0.0)


def test_precision_at_k_requires_exactly_k_values():
    with pytest.raises(MetricInputError):
        precision_at_k([1, 0], k=5)


def test_precision_at_k_rejects_non_binary_relevance():
    with pytest.raises(MetricInputError):
        precision_at_k([1, 2, 0], k=3)


def test_precision_at_k_rejects_k_below_one():
    with pytest.raises(MetricInputError):
        precision_at_k([1], k=0)
