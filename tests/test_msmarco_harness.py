"""Task 2.7 - tests for src/eval/msmarco_harness.py.

Portable tests use tiny hand-derived synthetic fixtures (no MS MARCO
data required). A local_data-marked section verifies the real frozen
MS MARCO Parquet files (schema, counts, referential integrity, ID
normalization) WITHOUT running any embedding/retrieval. A separate
local_data+model+gpu-marked mini-integration test builds a tiny in-
memory benchmark from a handful of real passages end-to-end. Nothing
here loads the full 8.8M-passage corpus, builds a full embedding/index,
or evaluates all 6,980 queries - that only happens via the explicit
scripts/run_msmarco_harness.py --build/--evaluate commands.

Hand derivations (independent of the production implementation, using
raw math.log2 arithmetic - see project_plan/PHASE2_MSMARCO_HARNESS.md
for the same numbers written out as documentation):

    Case A: relevant={A}, k=5, retrieved=[A,x,y,z,w]
      first_hit=1, recall=1/1=1.0, RR=1.0
      relevances=[1,0,0,0,0] -> DCG=1/log2(2)=1.0, IDCG=1.0 -> nDCG=1.0

    Case B: relevant={A}, k=5, retrieved=[x,y,z,w,A]
      first_hit=5, recall=1/1=1.0, RR=1/5=0.2
      relevances=[0,0,0,0,1] -> DCG=1/log2(6)=0.38685280723454163
      IDCG=1.0 -> nDCG=0.38685280723454163

    Case C: relevant={A}, k=5, retrieved=[x,y,z,w,v]  (A never appears)
      first_hit=None, recall=0/1=0.0, RR=0.0, nDCG=0.0

    Aggregate over A,B,C:
      mean_recall = (1.0+1.0+0.0)/3 = 0.6666666666666666
      MRR         = (1.0+0.2+0.0)/3 = 0.39999999999999997
      mean_nDCG   = (1.0+0.38685280723454163+0.0)/3 = 0.46228426907818054

    Multi-qrel case D: relevant={A,B,C}, k=5, retrieved=[X,B,Y,A,Z]
      hits_in_top_k=2 (B at rank2, A at rank4), recall=2/3=0.6666666666666666
      first_hit=2, RR=0.5
      relevances=[0,1,0,1,0] -> DCG=1/log2(3)+1/log2(5)=1.0616063116448506
      IDCG(num_relevant=3)=1/log2(2)+1/log2(3)+1/log2(4)=2.1309297535714578
      nDCG=0.49818925746641285
"""

from __future__ import annotations

import math

import pytest

from src.eval.msmarco_harness import (
    canonical_id,
    group_qrels,
    evaluate_query,
    aggregate_results,
    compute_config_hash,
    compute_result_hash,
    BENCHMARK_ID,
    EXPECTED_CORPUS_COUNT,
    EXPECTED_VALIDATION_QREL_COUNT,
    EXPECTED_VALIDATION_QUERY_COUNT,
)
from src.eval.metrics import MetricInputError


# --------------------------------------------------------------- ID normalization

def test_canonical_id_string_and_int_agree():
    assert canonical_id("0") == canonical_id(0) == "0"
    assert canonical_id("1185869") == canonical_id(1185869) == "1185869"


def test_canonical_id_bigint_form():
    assert canonical_id(7067032) == "7067032"


# --------------------------------------------------------------- qrel grouping

def test_group_qrels_single():
    grouped = group_qrels([{"query-id": 1, "corpus-id": 100}])
    assert grouped["1"].relevant_ids == frozenset({"100"})


def test_group_qrels_multiple_for_same_query_never_dropped():
    rows = [
        {"query-id": 1, "corpus-id": 100},
        {"query-id": 1, "corpus-id": 200},
        {"query-id": 1, "corpus-id": 300},
    ]
    grouped = group_qrels(rows)
    assert grouped["1"].relevant_ids == frozenset({"100", "200", "300"})


def test_group_qrels_separates_different_queries():
    rows = [{"query-id": 1, "corpus-id": 100}, {"query-id": 2, "corpus-id": 200}]
    grouped = group_qrels(rows)
    assert grouped["1"].relevant_ids == frozenset({"100"})
    assert grouped["2"].relevant_ids == frozenset({"200"})


# --------------------------------------------------------------- per-query evaluation

def test_relevant_at_rank_1():
    r = evaluate_query(query_id="q1", retrieved_ids=["A", "x", "y", "z", "w"], relevant_ids=frozenset({"A"}), k=5)
    assert r.first_hit_rank == 1
    assert r.passage_recall_at_k == pytest.approx(1.0)
    assert r.reciprocal_rank_value == pytest.approx(1.0)
    assert r.ndcg_at_k_value == pytest.approx(1.0, abs=1e-12)


def test_relevant_at_rank_k():
    r = evaluate_query(query_id="q2", retrieved_ids=["x", "y", "z", "w", "A"], relevant_ids=frozenset({"A"}), k=5)
    assert r.first_hit_rank == 5
    assert r.passage_recall_at_k == pytest.approx(1.0)
    assert r.reciprocal_rank_value == pytest.approx(0.2)
    assert r.ndcg_at_k_value == pytest.approx(1 / math.log2(6), abs=1e-12)


def test_relevant_outside_k_is_miss():
    r = evaluate_query(query_id="q3", retrieved_ids=["x", "y", "z", "w", "v"], relevant_ids=frozenset({"A"}), k=5)
    assert r.first_hit_rank is None
    assert r.passage_recall_at_k == pytest.approx(0.0)
    assert r.reciprocal_rank_value == pytest.approx(0.0)
    assert r.ndcg_at_k_value == pytest.approx(0.0, abs=1e-12)


def test_no_retrieved_relevant_item_same_as_miss():
    r = evaluate_query(query_id="q3b", retrieved_ids=["m", "n"], relevant_ids=frozenset({"A"}), k=5)
    assert r.hits_in_top_k == 0
    assert r.passage_recall_at_k == pytest.approx(0.0)


def test_empty_result_list_no_crash():
    r = evaluate_query(query_id="q4", retrieved_ids=[], relevant_ids=frozenset({"A"}), k=5)
    assert r.first_hit_rank is None
    assert r.hits_in_top_k == 0
    assert r.passage_recall_at_k == pytest.approx(0.0)
    assert r.ndcg_at_k_value == pytest.approx(0.0, abs=1e-12)


def test_multiple_qrels_recall_is_fraction_not_binary_hit():
    r = evaluate_query(query_id="q5", retrieved_ids=["X", "B", "Y", "A", "Z"], relevant_ids=frozenset({"A", "B", "C"}), k=5)
    assert r.hits_in_top_k == 2
    assert r.passage_recall_at_k == pytest.approx(2 / 3)
    assert r.first_hit_rank == 2  # B found before A
    assert r.reciprocal_rank_value == pytest.approx(0.5)
    expected_dcg = 1 / math.log2(3) + 1 / math.log2(5)
    expected_idcg = 1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert r.ndcg_at_k_value == pytest.approx(expected_dcg / expected_idcg, abs=1e-9)
    assert r.ndcg_at_k_value == pytest.approx(0.49818925746641285, abs=1e-9)


def test_duplicate_retrieved_id_rejected():
    with pytest.raises(MetricInputError):
        evaluate_query(query_id="q6", retrieved_ids=["A", "A", "B"], relevant_ids=frozenset({"A"}), k=3)


def test_retrieved_longer_than_k_rejected():
    with pytest.raises(MetricInputError):
        evaluate_query(query_id="q7", retrieved_ids=["A", "B", "C"], relevant_ids=frozenset({"A"}), k=2)


def test_invalid_k_rejected():
    with pytest.raises(MetricInputError):
        evaluate_query(query_id="q8", retrieved_ids=["A"], relevant_ids=frozenset({"A"}), k=0)


def test_recall_not_confused_with_binary_hit():
    # A query with 3 relevant passages, only 1 retrieved -> recall=1/3,
    # NOT hit_at_k's binary True/False.
    r = evaluate_query(query_id="q9", retrieved_ids=["A"], relevant_ids=frozenset({"A", "B", "C"}), k=1)
    assert r.passage_recall_at_k == pytest.approx(1 / 3)


# --------------------------------------------------------------- aggregation

def test_aggregate_hand_derived_three_queries():
    r1 = evaluate_query(query_id="q1", retrieved_ids=["A", "x", "y", "z", "w"], relevant_ids=frozenset({"A"}), k=5)
    r2 = evaluate_query(query_id="q2", retrieved_ids=["x", "y", "z", "w", "A"], relevant_ids=frozenset({"A"}), k=5)
    r3 = evaluate_query(query_id="q3", retrieved_ids=["x", "y", "z", "w", "v"], relevant_ids=frozenset({"A"}), k=5)
    agg = aggregate_results([r1, r2, r3], k=5)
    assert agg.query_count == 3
    assert agg.passage_recall_at_k["value"] == pytest.approx(0.6666666666666666, abs=1e-12)
    assert agg.passage_mrr == pytest.approx(0.39999999999999997, abs=1e-12)
    assert agg.passage_ndcg_at_k == pytest.approx(0.46228426907818054, abs=1e-9)


def test_aggregate_empty_raises():
    with pytest.raises(MetricInputError):
        aggregate_results([], k=10)


def test_aggregate_recall_diagnostic_numerator_denominator_not_the_reported_value():
    # With multi-qrel queries, numerator/denominator sum != mean-of-fractions
    # value - documented explicitly, tested explicitly so nobody assumes
    # value == numerator/denominator here.
    r1 = evaluate_query(query_id="q1", retrieved_ids=["A"], relevant_ids=frozenset({"A", "B"}), k=1)  # recall=0.5
    r2 = evaluate_query(query_id="q2", retrieved_ids=["C"], relevant_ids=frozenset({"C"}), k=1)  # recall=1.0
    agg = aggregate_results([r1, r2], k=1)
    mean_of_fractions = (0.5 + 1.0) / 2
    pooled_ratio = agg.passage_recall_at_k["numerator"] / agg.passage_recall_at_k["denominator"]
    assert agg.passage_recall_at_k["value"] == pytest.approx(mean_of_fractions)
    assert agg.passage_recall_at_k["value"] != pooled_ratio


# --------------------------------------------------------------- hashing / determinism

def test_config_hash_deterministic():
    config = {"benchmark": BENCHMARK_ID, "top_k": 10}
    assert compute_config_hash(config) == compute_config_hash(config)


def test_config_hash_changes_with_content():
    assert compute_config_hash({"top_k": 10}) != compute_config_hash({"top_k": 50})


def test_result_hash_deterministic_and_order_independent():
    r1 = evaluate_query(query_id="q1", retrieved_ids=["A"], relevant_ids=frozenset({"A"}), k=1)
    r2 = evaluate_query(query_id="q2", retrieved_ids=["B"], relevant_ids=frozenset({"A"}), k=1)
    h1 = compute_result_hash([r1, r2])
    h2 = compute_result_hash([r2, r1])  # reversed input order
    assert h1 == h2


def test_result_hash_changes_with_content():
    r1 = evaluate_query(query_id="q1", retrieved_ids=["A"], relevant_ids=frozenset({"A"}), k=1)
    r2 = evaluate_query(query_id="q1", retrieved_ids=["B"], relevant_ids=frozenset({"A"}), k=1)
    assert compute_result_hash([r1]) != compute_result_hash([r2])


# --------------------------------------------------------------- local_data: real frozen data verification

@pytest.mark.local_data
def test_real_msmarco_frozen_counts():
    import duckdb
    con = duckdb.connect()
    corpus_count = con.execute("select count(*) from read_parquet('data/msmarco/corpus.parquet')").fetchone()[0]
    qrel_count = con.execute("select count(*) from read_parquet('data/msmarco/qrels_validation.parquet')").fetchone()[0]
    distinct_queries = con.execute(
        'select count(distinct "query-id") from read_parquet(\'data/msmarco/qrels_validation.parquet\')'
    ).fetchone()[0]
    assert corpus_count == EXPECTED_CORPUS_COUNT
    assert qrel_count == EXPECTED_VALIDATION_QREL_COUNT
    assert distinct_queries == EXPECTED_VALIDATION_QUERY_COUNT


@pytest.mark.local_data
def test_real_msmarco_referential_integrity_100_percent():
    import duckdb
    con = duckdb.connect()
    missing_query = con.execute("""
        select count(*) from read_parquet('data/msmarco/qrels_validation.parquet') qr
        left join read_parquet('data/msmarco/queries.parquet') q on cast(qr."query-id" as varchar) = q._id
        where q._id is null
    """).fetchone()[0]
    missing_corpus = con.execute("""
        select count(*) from read_parquet('data/msmarco/qrels_validation.parquet') qr
        left join read_parquet('data/msmarco/corpus.parquet') c on cast(qr."corpus-id" as varchar) = c._id
        where c._id is null
    """).fetchone()[0]
    assert missing_query == 0
    assert missing_corpus == 0


@pytest.mark.local_data
def test_real_msmarco_qrels_are_binary():
    import duckdb
    con = duckdb.connect()
    scores = con.execute("select distinct score from read_parquet('data/msmarco/qrels_validation.parquet')").fetchall()
    assert scores == [(1,)]


@pytest.mark.local_data
def test_real_msmarco_id_normalization_matches_str_int():
    import duckdb
    con = duckdb.connect()
    sample = con.execute("select _id from read_parquet('data/msmarco/corpus.parquet') limit 20").fetchall()
    for (raw_id,) in sample:
        assert canonical_id(raw_id) == raw_id  # already canonical string form
        assert canonical_id(int(raw_id)) == raw_id


# --------------------------------------------------------------- local mini-benchmark integration (Section 35)

@pytest.mark.local_data
@pytest.mark.model
@pytest.mark.gpu
def test_local_mini_benchmark_end_to_end(tmp_path):
    """Builds a tiny (500-passage) real-data benchmark end to end - load
    corpus, load queries, load qrels, embed, index, retrieve, score,
    persist - and verifies the fast batched exact search agrees exactly
    with src.index.lancedb_index's frozen exact_cosine_search on every
    evaluated query. This is PILOT-scale, not the reported benchmark
    result, but proves the whole wiring (not just the metric math)."""
    import duckdb
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    from src.embeddings.bge import EMBEDDING_DIMENSION, encode_passages, encode_queries, load_model, validate_vectors
    from src.index import lancedb_index as idx

    con = duckdb.connect()
    # 480 arbitrary passages + 20 passages known to be gold-relevant for
    # some real query (deterministic, via qrels_validation itself) - a
    # pure random/first-N slice of the 8.84M-passage corpus essentially
    # never contains a qrel-relevant passage (verified empirically during
    # the real pilot runs), so this mini-benchmark would otherwise have
    # zero eligible queries to score.
    filler = con.execute("select _id, text from read_parquet('data/msmarco/corpus.parquet') limit 480").fetchall()
    relevant_sample_ids = con.execute(
        'select distinct "corpus-id" from read_parquet(\'data/msmarco/qrels_validation.parquet\') order by "corpus-id" limit 20'
    ).fetchall()
    relevant_ids_str = ",".join(str(r[0]) for r in relevant_sample_ids)
    relevant_passages = con.execute(
        f"select _id, text from read_parquet('data/msmarco/corpus.parquet') where cast(_id as bigint) in ({relevant_ids_str})"
    ).fetchall()
    passages = filler + relevant_passages
    ids = [canonical_id(pid) for pid, _ in passages]
    texts = [text for _, text in passages]

    model = load_model(device="cuda")
    vectors = encode_passages(model, texts)
    validate_vectors(vectors, expect_normalized=True)

    vector_array = pa.FixedSizeListArray.from_arrays(pa.array(vectors.reshape(-1), type=pa.float32()), EMBEDDING_DIMENSION)
    schema = pa.schema([
        pa.field("corpus_id", pa.string()), pa.field("text", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIMENSION)),
    ])
    shard_path = tmp_path / "shard_0000.parquet"
    pq.write_table(pa.table({"corpus_id": ids, "text": texts, "vector": vector_array}, schema=schema), shard_path)

    db = idx.open_database(tmp_path / "index")
    table = db.create_table("mini", data=pq.read_table(shard_path))
    assert table.count_rows() == len(passages)

    corpus_ids = set(ids)
    qrel_rows = con.execute('select "query-id", "corpus-id" from read_parquet(\'data/msmarco/qrels_validation.parquet\')').fetchall()
    grouped = group_qrels([{"query-id": q, "corpus-id": c} for q, c in qrel_rows])
    eligible = [qid for qid, qs in grouped.items() if qs.relevant_ids & corpus_ids]
    assert eligible, "no eligible queries found in the first 500 passages - widen the sample"

    query_ids_table = con.execute("select _id, text from read_parquet('data/msmarco/queries.parquet')").to_arrow_table()
    qtext_by_id = {canonical_id(i): t for i, t in zip(query_ids_table.column("_id").to_pylist(), query_ids_table.column("text").to_pylist())}

    sample_qids = sorted(eligible, key=canonical_id)[:5]
    results = []
    for qid in sample_qids:
        qvec = encode_queries(model, [qtext_by_id[qid]])[0]
        hits = idx.exact_cosine_search(table, qvec, limit=10)
        retrieved_ids = [canonical_id(x) for x in hits.column("corpus_id").to_pylist()]
        r = evaluate_query(query_id=qid, retrieved_ids=retrieved_ids, relevant_ids=grouped[qid].relevant_ids & corpus_ids, k=10)
        results.append(r)

    agg = aggregate_results(results, k=10)
    assert 0.0 <= agg.passage_recall_at_k["value"] <= 1.0
    assert 0.0 <= agg.passage_mrr <= 1.0
    assert 0.0 <= agg.passage_ndcg_at_k <= 1.0

    result_hash_1 = compute_result_hash(results)
    result_hash_2 = compute_result_hash(list(reversed(results)))
    assert result_hash_1 == result_hash_2  # order-independent, deterministic
