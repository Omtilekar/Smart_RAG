"""Task 3.5 - portable, pure-logic tests for src.retrieval.fusion.rrf_fuse.
No I/O, no LanceDB, no model, no network - tiny synthetic parent-ranking
fixtures only."""

from __future__ import annotations

import pytest

from src.retrieval.fusion import DEFAULT_RRF_K, FusedRetrievalResult, FusionError, rrf_fuse


class R:
    """Minimal fake parent result - duck-types whatever rrf_fuse reads
    off dense/sparse results (`.chunk_id`, `.rank`, plus optional
    `.distance`/`.score`/`.sparse_score` and shared metadata fields)."""

    def __init__(self, chunk_id, rank, **extra):
        self.chunk_id = chunk_id
        self.rank = rank
        for k, v in extra.items():
            setattr(self, k, v)


COMMON = dict(document_id="d1", text="hello", cik=1, company="Acme", form_type="10-K", fiscal_year=2020,
              source="edgar_corpus", source_filename="f.htm", source_split="dev", ordinal=0, token_count=5,
              chunk_config_hash="h" * 64)


# --------------------------------------------------------------- exact formula / ranks

def test_rrf_formula_matches_hand_calculation():
    # dense: A rank1, B rank2. sparse: B rank1, C rank2. rrf_k=60.
    d = [R("A", 1, **COMMON), R("B", 2, **COMMON)]
    s = [R("B", 1, sparse_score=5.0, **COMMON), R("C", 2, sparse_score=3.0, **COMMON)]
    fused = rrf_fuse(d, s, rrf_k=60, limit=10)
    by_id = {f.chunk_id: f.rrf_score for f in fused}
    assert by_id["A"] == pytest.approx(1 / 61)
    assert by_id["B"] == pytest.approx(1 / 62 + 1 / 61)
    assert by_id["C"] == pytest.approx(1 / 62)
    assert [f.chunk_id for f in fused] == ["B", "A", "C"]  # B > A > C


def test_ranks_are_one_based():
    d = [R("A", 1, **COMMON)]
    with pytest.raises(FusionError):
        rrf_fuse([R("A", 0, **COMMON)], [], rrf_k=60, limit=10)


def test_missing_dense_candidate_contributes_zero():
    d = []
    s = [R("C", 1, sparse_score=1.0, **COMMON)]
    fused = rrf_fuse(d, s, rrf_k=60, limit=10)
    assert fused[0].dense_rank is None
    assert fused[0].rrf_score == pytest.approx(1 / 61)


def test_missing_sparse_candidate_contributes_zero():
    d = [R("A", 1, **COMMON)]
    s = []
    fused = rrf_fuse(d, s, rrf_k=60, limit=10)
    assert fused[0].sparse_rank is None
    assert fused[0].rrf_score == pytest.approx(1 / 61)


def test_same_chunk_in_both_streams_receives_both_contributions():
    d = [R("A", 3, **COMMON)]
    s = [R("A", 5, sparse_score=1.0, **COMMON)]
    fused = rrf_fuse(d, s, rrf_k=60, limit=10)
    assert fused[0].in_dense and fused[0].in_sparse
    assert fused[0].rrf_score == pytest.approx(1 / 63 + 1 / 65)


# --------------------------------------------------------------- fusion key / duplicates

def test_fusion_key_is_chunk_id_not_document_id():
    d = [R("c1", 1, document_id="docA", **{k: v for k, v in COMMON.items() if k != "document_id"})]
    s = [R("c2", 1, sparse_score=1.0, document_id="docA", **{k: v for k, v in COMMON.items() if k != "document_id"})]
    fused = rrf_fuse(d, s, rrf_k=60, limit=10)
    assert {f.chunk_id for f in fused} == {"c1", "c2"}  # not merged despite same document_id


def test_duplicate_chunk_id_in_dense_stream_rejected():
    d = [R("A", 1, **COMMON), R("A", 2, **COMMON)]
    with pytest.raises(FusionError):
        rrf_fuse(d, [], rrf_k=60, limit=10)


def test_duplicate_chunk_id_in_sparse_stream_rejected():
    s = [R("A", 1, sparse_score=1.0, **COMMON), R("A", 2, sparse_score=1.0, **COMMON)]
    with pytest.raises(FusionError):
        rrf_fuse([], s, rrf_k=60, limit=10)


# --------------------------------------------------------------- validation

@pytest.mark.parametrize("bad_rrf_k", [0, -1, True, 1.5, "60"])
def test_rrf_k_validation(bad_rrf_k):
    with pytest.raises(FusionError):
        rrf_fuse([], [R("A", 1, sparse_score=1.0, **COMMON)], rrf_k=bad_rrf_k, limit=10)


@pytest.mark.parametrize("bad_limit", [0, -1, True, 1.5, "10"])
def test_limit_validation(bad_limit):
    with pytest.raises(FusionError):
        rrf_fuse([R("A", 1, **COMMON)], [], rrf_k=60, limit=bad_limit)


# --------------------------------------------------------------- determinism / tie-break

def test_deterministic_tie_break_exact_score_tie():
    # A: dense rank1 only. B: sparse rank1 only. rrf_k=60 -> both score 1/61 (exact tie).
    # Tie-break: lower best_parent_rank (both=1, tie) -> lower dense_rank (A=1, B=inf) -> A wins.
    d = [R("A", 1, **COMMON)]
    s = [R("B", 1, sparse_score=1.0, **COMMON)]
    fused = rrf_fuse(d, s, rrf_k=60, limit=10)
    assert fused[0].rrf_score == pytest.approx(fused[1].rrf_score)
    assert [f.chunk_id for f in fused] == ["A", "B"]


def test_deterministic_tie_break_falls_back_to_chunk_id():
    # Two distinct chunk_ids sharing the same dense rank (legal - only a duplicate
    # chunk_id WITHIN one stream is an error) produce an exact rrf_score tie;
    # the tie-break falls through best_parent_rank/dense_rank/sparse_rank (all
    # equal) down to lexical chunk_id ascending.
    d = [R("Y", 2, **COMMON), R("X", 2, **{**COMMON, "document_id": "d2"})]
    fused = rrf_fuse(d, [], rrf_k=60, limit=10)
    assert fused[0].rrf_score == pytest.approx(fused[1].rrf_score)
    assert [f.chunk_id for f in fused] == ["X", "Y"]


def test_parent_input_order_does_not_change_fused_result():
    d = [R("A", 1, **COMMON), R("B", 2, **COMMON)]
    s = [R("B", 1, sparse_score=5.0, **COMMON), R("C", 2, sparse_score=3.0, **COMMON)]
    fused1 = rrf_fuse(d, s, rrf_k=60, limit=10)
    fused2 = rrf_fuse(list(reversed(d)), list(reversed(s)), rrf_k=60, limit=10)
    assert [f.chunk_id for f in fused1] == [f.chunk_id for f in fused2]
    assert [f.rrf_score for f in fused1] == [f.rrf_score for f in fused2]


def test_fusion_is_deterministic_across_repeated_calls():
    d = [R("A", 1, **COMMON), R("B", 2, **COMMON)]
    s = [R("B", 1, sparse_score=5.0, **COMMON), R("C", 2, sparse_score=3.0, **COMMON)]
    r1 = rrf_fuse(d, s, rrf_k=60, limit=10)
    r2 = rrf_fuse(d, s, rrf_k=60, limit=10)
    assert [f.chunk_id for f in r1] == [f.chunk_id for f in r2]


# --------------------------------------------------------------- no mutation / provenance / honesty

def test_parent_result_objects_are_not_mutated():
    d = [R("A", 1, **COMMON)]
    s = [R("A", 1, sparse_score=1.0, **COMMON)]
    d_rank_before, s_rank_before = d[0].rank, s[0].rank
    rrf_fuse(d, s, rrf_k=60, limit=10)
    assert d[0].rank == d_rank_before
    assert s[0].rank == s_rank_before


def test_full_provenance_metadata_is_preserved():
    d = [R("A", 1, **COMMON)]
    fused = rrf_fuse(d, [], rrf_k=60, limit=10)
    r = fused[0]
    for field in ("document_id", "text", "cik", "company", "form_type", "fiscal_year", "source",
                  "source_filename", "source_split", "ordinal", "token_count", "chunk_config_hash"):
        assert getattr(r, field) == COMMON[field]


def test_fused_result_never_exposes_a_fake_similarity_score():
    d = [R("A", 1, **COMMON)]
    fused = rrf_fuse(d, [], rrf_k=60, limit=10)
    assert isinstance(fused[0], FusedRetrievalResult)
    assert not hasattr(fused[0], "cosine_score")
    assert not hasattr(fused[0], "bm25_probability")


def test_rrf_score_never_equals_a_raw_dense_or_sparse_score_added_directly():
    # dense distance/score and sparse_score are preserved separately, never summed into rrf_score.
    d = [R("A", 1, distance=0.1, score=0.9, **COMMON)]
    s = [R("A", 1, sparse_score=1000.0, **COMMON)]
    fused = rrf_fuse(d, s, rrf_k=DEFAULT_RRF_K, limit=10)
    r = fused[0]
    assert r.dense_distance == 0.1 and r.dense_score == 0.9 and r.sparse_score == 1000.0
    assert r.rrf_score != r.dense_score + r.sparse_score
    assert r.rrf_score == pytest.approx(1 / (DEFAULT_RRF_K + 1) + 1 / (DEFAULT_RRF_K + 1))
