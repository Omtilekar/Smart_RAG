"""Task 1.10 - portable tests for src/eval/baseline_metrics.py.

Pure-logic tests only: synthetic retrieval-result fixtures (duck-typed,
no real retriever/index/model). Real-data integration coverage lives in
test_baseline_metric_real_smoke (local_data+model+gpu-marked), below.
"""

from dataclasses import dataclass

import pytest

from src.eval.baseline_metrics import (
    evaluate_question,
    summarize_doc_recall,
    canonical_json,
    compute_config_hash,
    compute_result_hash,
)


@dataclass(frozen=True)
class FakeChunk:
    rank: int
    chunk_id: str
    document_id: str
    score: float = 0.5
    distance: float = 0.5


def _chunks(document_ids: list[str]) -> list[FakeChunk]:
    """One fake chunk per rank, 1-based, from a list of document_ids."""
    return [FakeChunk(rank=i + 1, chunk_id=f"{doc}::chunk0", document_id=doc) for i, doc in enumerate(document_ids)]


# ------------------------------------------------------------------------- hit logic

def test_target_at_rank_1_is_hit():
    results = _chunks(["target.htm"] + [f"other{i}.htm" for i in range(9)])
    r = evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target.htm", retrieved_results=results, k=10)
    assert r.hit is True
    assert r.first_hit_rank == 1


def test_target_at_rank_10_is_hit():
    results = _chunks([f"other{i}.htm" for i in range(9)] + ["target.htm"])
    r = evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target.htm", retrieved_results=results, k=10)
    assert r.hit is True
    assert r.first_hit_rank == 10


def test_target_absent_is_miss():
    results = _chunks([f"other{i}.htm" for i in range(10)])
    r = evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target.htm", retrieved_results=results, k=10)
    assert r.hit is False
    assert r.first_hit_rank is None


def test_target_appears_multiple_times_one_hit_first_rank_retained():
    docs = [f"other{i}.htm" for i in range(3)] + ["target.htm"] + [f"other{i}.htm" for i in range(3, 5)] + ["target.htm"] + [f"other{i}.htm" for i in range(5, 8)]
    results = _chunks(docs)
    r = evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target.htm", retrieved_results=results, k=10)
    assert r.hit is True
    assert r.first_hit_rank == 4  # first occurrence is 1-based index 4


def test_same_cik_company_but_wrong_document_id_is_miss():
    # exact string equality only - a document with a different filename never matches
    results = _chunks(["target_2018.htm"] + [f"other{i}.htm" for i in range(9)])
    r = evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target_2019.htm", retrieved_results=results, k=10)
    assert r.hit is False
    assert r.first_hit_rank is None


def test_target_would_appear_at_rank_11_is_miss_when_k_10():
    # simulate: only the first 10 results are ever passed in - rank 11 is never considered
    results = _chunks([f"other{i}.htm" for i in range(10)])
    r = evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target.htm", retrieved_results=results, k=10)
    assert r.hit is False


def test_exact_string_equality_not_substring():
    results = _chunks(["target.htm.extra"] + [f"other{i}.htm" for i in range(9)])
    r = evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target.htm", retrieved_results=results, k=10)
    assert r.hit is False


# --------------------------------------------------------------------- invariants

def test_empty_retrieval_rejected_when_10_expected():
    with pytest.raises(ValueError):
        evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target.htm", retrieved_results=[], k=10)


def test_wrong_result_count_rejected():
    results = _chunks([f"other{i}.htm" for i in range(5)])
    with pytest.raises(ValueError):
        evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target.htm", retrieved_results=results, k=10)


def test_non_sequential_ranks_rejected():
    results = [FakeChunk(rank=1, chunk_id="a::chunk0", document_id="a.htm"),
               FakeChunk(rank=3, chunk_id="b::chunk0", document_id="b.htm")]
    with pytest.raises(ValueError):
        evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="target.htm", retrieved_results=results, k=2)


def test_retrieved_ids_recorded_in_rank_order():
    docs = [f"doc{i}.htm" for i in range(10)]
    results = _chunks(docs)
    r = evaluate_question(question_id="q1", question="Q", category="business",
                           target_document_id="doc5.htm", retrieved_results=results, k=10)
    assert r.retrieved_document_ids == docs
    assert r.retrieved_chunk_ids == [f"{d}::chunk0" for d in docs]


# -------------------------------------------------------------------- aggregation

def _result(qid, category, hit, first_hit_rank):
    return evaluate_question(
        question_id=qid, question="Q", category=category,
        target_document_id="target.htm" if hit else "absent.htm",
        retrieved_results=_chunks(
            [f"other{i}.htm" for i in range(first_hit_rank - 1)] + ["target.htm"] + [f"other{i}.htm" for i in range(10 - first_hit_rank)]
        ) if hit else _chunks([f"other{i}.htm" for i in range(10)]),
        k=10,
    )


def test_aggregate_hit_count_and_recall():
    results = [_result(f"q{i}", "business", True, 1) for i in range(3)] + [_result(f"q{i}", "business", False, None) for i in range(7)]
    agg = summarize_doc_recall(results, k=10)
    assert agg.question_count == 10
    assert agg.hit_count == 3
    assert agg.doc_recall_at_k == pytest.approx(0.3)


def test_category_aggregation():
    biz = [_result(f"b{i}", "business", True, 1) for i in range(2)] + [_result(f"b{i}", "business", False, None) for i in range(2)]
    risk = [_result(f"r{i}", "risk_factors", True, 5) for i in range(1)] + [_result(f"r{i}", "risk_factors", False, None) for i in range(3)]
    agg = summarize_doc_recall(biz + risk, k=10)
    assert agg.category_results["business"].question_count == 4
    assert agg.category_results["business"].hit_count == 2
    assert agg.category_results["business"].doc_recall_at_k == pytest.approx(0.5)
    assert agg.category_results["risk_factors"].question_count == 4
    assert agg.category_results["risk_factors"].hit_count == 1
    assert agg.category_results["risk_factors"].doc_recall_at_k == pytest.approx(0.25)


def test_first_hit_rank_counts():
    results = [_result("a", "business", True, 1), _result("b", "business", True, 1), _result("c", "business", True, 5), _result("d", "business", False, None)]
    agg = summarize_doc_recall(results, k=10)
    assert agg.first_hit_rank_counts[1] == 2
    assert agg.first_hit_rank_counts[5] == 1
    assert agg.first_hit_rank_counts[2] == 0
    assert sum(agg.first_hit_rank_counts.values()) == 3  # only hits counted
    assert set(agg.first_hit_rank_counts.keys()) == set(range(1, 11))


# ---------------------------------------------------------------------- hashing

def test_config_hash_determinism():
    config = {"metric_name": "doc_recall@10", "k": 10}
    h1 = compute_config_hash(config)
    h2 = compute_config_hash(config)
    assert h1 == h2
    assert len(h1) == 64


def test_config_hash_key_order_independent():
    assert compute_config_hash({"a": 1, "b": 2}) == compute_config_hash({"b": 2, "a": 1})


def test_canonical_json_sorted_keys_stable_separators():
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_result_hash_ignores_runtime_and_timestamp_fields():
    results = [_result("q1", "business", True, 1)]
    h1 = compute_result_hash(results)
    # question/category/scores/distances differ but stable fields identical -> same hash
    modified = [evaluate_question(
        question_id="q1", question="A COMPLETELY DIFFERENT QUESTION TEXT", category="different_category",
        target_document_id=results[0].target_document_id,
        retrieved_results=_chunks(results[0].retrieved_document_ids),
        k=10,
    )]
    h2 = compute_result_hash(modified)
    assert h1 == h2


def test_result_hash_changes_when_retrieval_identity_changes():
    results_a = [_result("q1", "business", True, 1)]
    results_b = [_result("q1", "business", False, None)]
    assert compute_result_hash(results_a) != compute_result_hash(results_b)


# ----------------------------------------------------- real-data integration

CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
DATASET_RELATIVE_PATH = "results/phase_1_9_smoke_evaluation.json"


@pytest.mark.local_data
@pytest.mark.model
@pytest.mark.gpu
def test_baseline_metric_real_smoke():
    """Proves the real Task 1.9 dataset loads, Task 1.6's real retriever
    accepts k=10 and returns 10 results, and evaluate_question() evaluates
    exact document membership correctly - on a SMALL 3-question subset, not
    the full 200 (the full run is scripts/run_baseline_metric.py's job, not
    ordinary pytest)."""
    import json
    from src.storage import get_storage
    from src.embeddings.bge import load_model
    from src.index.lancedb_index import open_database, open_chunk_table
    from src.retrieval.baseline import BaselineRetriever

    storage = get_storage()
    dataset_path = storage.repo_root / DATASET_RELATIVE_PATH
    if not dataset_path.is_file():
        pytest.skip(f"Task 1.9 dataset not present at {dataset_path}")
    db_path = storage.index_dir(CHUNK_CONFIG_HASH, MODEL_NAME)
    if not db_path.is_dir():
        pytest.skip(f"Task 1.5 index not present at {db_path}")

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    sample_questions = dataset["questions"][:3]

    db = open_database(db_path)
    table = open_chunk_table(db)
    model = load_model(device="cuda")
    retriever = BaselineRetriever(model=model, table=table)

    for q in sample_questions:
        results = retriever.retrieve(q["question"], k=10)
        assert len(results) == 10
        metric_result = evaluate_question(
            question_id=q["question_id"], question=q["question"], category=q["category"],
            target_document_id=q["target_document_id"], retrieved_results=results, k=10,
        )
        assert metric_result.hit == (q["target_document_id"] in [r.document_id for r in results])
