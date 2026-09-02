"""Task 2.12 - tests for src.eval.financebench (pure logic, synthetic
fixtures only). No download, no PDF parsing, no model load, no GPU."""

from __future__ import annotations

import pytest

from src.eval import financebench as fb


def make_row(**overrides) -> dict:
    row = {
        "financebench_id": "financebench_id_00001",
        "company": "Acme",
        "doc_name": "ACME_2020_10K",
        "question_type": "metrics-generated",
        "question_reasoning": "Information extraction",
        "question": "What was FY2020 revenue?",
        "answer": "$100.00",
        "justification": "Directly extracted from the income statement.",
        "evidence": [{"evidence_text": "Total revenue $100", "doc_name": "ACME_2020_10K", "evidence_page_num": 3,
                      "evidence_text_full_page": "..."}],
        "gics_sector": "Industrials",
        "doc_type": "10k",
        "doc_period": "2020",
        "doc_link": "https://example.com/acme.pdf",
        "dataset_subset_label": "OPEN_SOURCE",
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------- dataset validation

class TestDatasetValidation:
    def test_valid_row_passes(self):
        fb.validate_financebench_row(make_row())

    def test_missing_field_rejected(self):
        row = make_row()
        del row["answer"]
        with pytest.raises(fb.FinanceBenchError):
            fb.validate_financebench_row(row)

    def test_empty_question_rejected(self):
        with pytest.raises(fb.FinanceBenchError):
            fb.validate_financebench_row(make_row(question="   "))

    def test_empty_answer_rejected(self):
        with pytest.raises(fb.FinanceBenchError):
            fb.validate_financebench_row(make_row(answer=""))

    def test_empty_evidence_list_rejected(self):
        with pytest.raises(fb.FinanceBenchError):
            fb.validate_financebench_row(make_row(evidence=[]))

    def test_evidence_item_missing_page_num_rejected(self):
        row = make_row()
        del row["evidence"][0]["evidence_page_num"]
        with pytest.raises(fb.FinanceBenchError):
            fb.validate_financebench_row(row)

    def test_negative_page_num_rejected(self):
        row = make_row()
        row["evidence"][0]["evidence_page_num"] = -1
        with pytest.raises(fb.FinanceBenchError):
            fb.validate_financebench_row(row)

    def test_unique_ids_enforced_in_audit(self):
        rows = [make_row(), make_row()]
        with pytest.raises(fb.FinanceBenchError):
            fb.audit_financebench_dataset(rows)

    def test_audit_reports_correct_counts(self):
        rows = [
            make_row(financebench_id="id1", doc_name="A", question_type="t1"),
            make_row(financebench_id="id2", doc_name="B", question_type="t2",
                      evidence=[{"evidence_text": "x", "doc_name": "B", "evidence_page_num": 0},
                                {"evidence_text": "y", "doc_name": "B", "evidence_page_num": 1}]),
        ]
        audit = fb.audit_financebench_dataset(rows)
        assert audit.row_count == 2
        assert audit.unique_id_count == 2
        assert audit.unique_doc_name_count == 2
        assert audit.evidence_count_distribution == {1: 1, 2: 1}
        assert audit.zero_evidence_count == 0
        assert audit.null_question_count == 0
        assert audit.null_answer_count == 0


# --------------------------------------------------------------- leakage guard

class TestLeakageGuard:
    @pytest.mark.parametrize("forbidden", ["evidence_text", "justification", "answer", "question"])
    def test_forbidden_sources_rejected(self, forbidden):
        with pytest.raises(fb.LeakageError):
            fb.assert_no_gold_leakage(forbidden, make_row())

    def test_source_pdf_allowed(self):
        fb.assert_no_gold_leakage("source_pdf", make_row())

    def test_doc_name_allowed(self):
        fb.assert_no_gold_leakage("doc_name", make_row())


# --------------------------------------------------------------- normalization

class TestNormalization:
    def test_collapses_whitespace(self):
        assert fb.normalize_whitespace("a   b\n\nc") == "a b c"

    def test_strips_leading_trailing(self):
        assert fb.normalize_whitespace("  a b  ") == "a b"

    def test_em_dash_treated_as_whitespace(self):
        assert fb.normalize_whitespace("Other — net") == fb.normalize_whitespace("Other net")

    def test_en_dash_treated_as_whitespace(self):
        assert fb.normalize_whitespace("Other – net") == fb.normalize_whitespace("Other net")

    def test_minus_sign_treated_as_whitespace(self):
        assert fb.normalize_whitespace("Other − net") == fb.normalize_whitespace("Other net")

    def test_ascii_hyphen_not_touched(self):
        # A genuine hyphenated word must not be altered.
        assert fb.normalize_whitespace("non-GAAP measure") == "non-GAAP measure"

    def test_bullet_glyph_treated_as_whitespace(self):
        assert fb.normalize_whitespace("• server microprocessors") == fb.normalize_whitespace("server microprocessors")


# --------------------------------------------------------------- evidence alignment

def make_page(page_number: int, text: str) -> fb.PageNode:
    return fb.PageNode(doc_name="ACME_2020_10K", page_number=page_number, text=text, tables=())


class TestEvidenceAlignment:
    def test_exact_match_on_stated_page(self):
        pages = {3: make_page(3, "Preamble. Total revenue $100 million. Trailer.")}
        result = fb.align_evidence_item(3, "Total revenue $100 million", pages)
        assert result.status == "exact"
        assert result.page_number == 3
        assert result.matched_via == "stated_page"

    def test_normalized_exact_whitespace_case(self):
        pages = {3: make_page(3, "Total   revenue\n$100 million")}
        result = fb.align_evidence_item(3, "Total revenue $100 million", pages)
        assert result.status == "normalized_exact"
        assert result.page_number == 3

    def test_dash_glyph_case(self):
        pages = {3: make_page(3, "Adjustments — net income of $5")}
        result = fb.align_evidence_item(3, "Adjustments net income of $5", pages)
        assert result.status == "normalized_exact"

    def test_ambiguous_when_multiple_adjacent_pages_match(self):
        pages = {
            3: make_page(3, "irrelevant content"),
            2: make_page(2, "Total revenue $100 million duplicate"),
            4: make_page(4, "Total revenue $100 million duplicate"),
        }
        result = fb.align_evidence_item(3, "Total revenue $100 million duplicate", pages)
        assert result.status == "ambiguous"
        assert result.page_number is None

    def test_unmatched_when_absent_everywhere(self):
        pages = {3: make_page(3, "nothing relevant here")}
        result = fb.align_evidence_item(3, "Total revenue $100 million", pages)
        assert result.status == "unmatched"
        assert result.page_number is None

    def test_adjacent_page_off_by_one_recovered(self):
        pages = {
            3: make_page(3, "irrelevant"),
            4: make_page(4, "Total revenue $100 million"),
        }
        result = fb.align_evidence_item(3, "Total revenue $100 million", pages)
        assert result.status == "exact"
        assert result.page_number == 4
        assert result.matched_via == "adjacent_page"

    def test_no_negative_page_lookup(self):
        pages = {0: make_page(0, "Total revenue $100 million")}
        # stated page 0 doesn't match, adjacent candidates are -1 (skipped) and 1 (absent)
        result = fb.align_evidence_item(0, "something else entirely", pages)
        assert result.status == "unmatched"

    def test_no_arbitrary_first_match_selection(self):
        # Both true neighbors of the stated page match distinct pages -
        # must never silently pick the first one; must report ambiguous.
        pages = {2: make_page(2, "X"), 1: make_page(1, "Total revenue $100 million"),
                 3: make_page(3, "Total revenue $100 million")}
        result = fb.align_evidence_item(2, "Total revenue $100 million", pages)
        assert result.status == "ambiguous"


class TestGoldChunkAttribution:
    def _chunk(self, chunk_id, text):
        return fb.BenchmarkChunk(chunk_id=chunk_id, doc_name="ACME_2020_10K", page_number=3, ordinal=0,
                                  text=text, token_count=10, benchmark_config_hash="a" * 64)

    def test_exact_hit_chunk_selected(self):
        chunks = [self._chunk("c1", "Total revenue $100 million"), self._chunk("c2", "unrelated text")]
        alignment = fb.AlignmentResult(status="exact", page_number=3, matched_via="stated_page")
        ids = fb.gold_chunk_ids_for_alignment(alignment, "Total revenue $100 million", chunks)
        assert ids == ("c1",)

    def test_no_gold_chunks_for_unmatched_alignment(self):
        chunks = [self._chunk("c1", "Total revenue $100 million")]
        alignment = fb.AlignmentResult(status="unmatched", page_number=None, matched_via=None)
        ids = fb.gold_chunk_ids_for_alignment(alignment, "Total revenue $100 million", chunks)
        assert ids == ()

    def test_evidence_spanning_chunk_boundary_attributes_whole_page(self):
        chunks = [self._chunk("c1", "Total revenue"), self._chunk("c2", "$100 million")]
        alignment = fb.AlignmentResult(status="normalized_exact", page_number=3, matched_via="stated_page")
        ids = fb.gold_chunk_ids_for_alignment(alignment, "Total revenue $100 million", chunks)
        assert set(ids) == {"c1", "c2"}


# --------------------------------------------------------------- table serialization

class TestTableSerialization:
    def test_basic_rows(self):
        result = fb.serialize_table([["A", "B"], ["1", "2"]])
        assert result == "A | B\n1 | 2"

    def test_none_cell_becomes_empty_string(self):
        result = fb.serialize_table([["A", None]])
        assert result == "A | "

    def test_deterministic(self):
        rows = [["X", "Y"], ["Z", None]]
        assert fb.serialize_table(rows) == fb.serialize_table(rows)


# --------------------------------------------------------------- chunking / IDs

class TestBenchmarkChunkId:
    def test_deterministic(self):
        a = fb.build_benchmark_chunk_id("ACME_2020_10K", 3, 0)
        b = fb.build_benchmark_chunk_id("ACME_2020_10K", 3, 0)
        assert a == b

    def test_namespaced_with_benchmark_name(self):
        cid = fb.build_benchmark_chunk_id("ACME_2020_10K", 3, 0)
        assert cid.startswith("financebench:")

    def test_page_identity_retained(self):
        cid = fb.build_benchmark_chunk_id("ACME_2020_10K", 3, 0)
        assert "page00003" in cid

    def test_different_page_different_id(self):
        assert fb.build_benchmark_chunk_id("ACME_2020_10K", 3, 0) != fb.build_benchmark_chunk_id("ACME_2020_10K", 4, 0)

    def test_different_doc_different_id(self):
        assert fb.build_benchmark_chunk_id("A", 3, 0) != fb.build_benchmark_chunk_id("B", 3, 0)

    def test_never_collides_with_sec_chunk_id_shape(self):
        cid = fb.build_benchmark_chunk_id("ACME_2020_10K", 3, 0)
        assert "::chunk" not in cid  # Phase 1's SEC chunk_id pattern


class _FakeTokenizer:
    """Deterministic whitespace tokenizer standing in for the real BGE
    tokenizer - fast/portable, exercises compute_token_windows exactly."""
    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=True, truncation=False):
        offsets = []
        i = 0
        for tok in text.split(" "):
            start = text.index(tok, i)
            end = start + len(tok)
            offsets.append((start, end))
            i = end
        return {"offset_mapping": offsets}


class TestBenchmarkChunking:
    def test_short_page_single_chunk(self):
        page = make_page(0, "one two three")
        chunks = fb.build_page_chunks(page, tokenizer=_FakeTokenizer(), benchmark_config_hash="a" * 64)
        assert len(chunks) == 1
        assert chunks[0].text == "one two three"

    def test_empty_page_zero_chunks(self):
        page = make_page(0, "")
        chunks = fb.build_page_chunks(page, tokenizer=_FakeTokenizer(), benchmark_config_hash="a" * 64)
        assert chunks == []

    def test_long_page_splits_into_windows(self):
        text = " ".join(f"tok{i}" for i in range(600))
        page = make_page(0, text)
        chunks = fb.build_page_chunks(page, tokenizer=_FakeTokenizer(), benchmark_config_hash="a" * 64)
        assert len(chunks) == 2
        assert chunks[0].token_count == 512
        assert chunks[1].token_count == 88

    def test_config_hash_recorded_on_every_chunk(self):
        page = make_page(0, "one two three")
        chunks = fb.build_page_chunks(page, tokenizer=_FakeTokenizer(), benchmark_config_hash="b" * 64)
        assert all(c.benchmark_config_hash == "b" * 64 for c in chunks)

    def test_never_crosses_page_boundary(self):
        # Two adjacent pages, each independently chunked - ordinals reset
        # per page and chunk_ids are page-scoped.
        page_a = make_page(0, "one two three")
        page_b = make_page(1, "four five six")
        chunks_a = fb.build_page_chunks(page_a, tokenizer=_FakeTokenizer(), benchmark_config_hash="a" * 64)
        chunks_b = fb.build_page_chunks(page_b, tokenizer=_FakeTokenizer(), benchmark_config_hash="a" * 64)
        assert chunks_a[0].page_number == 0
        assert chunks_b[0].page_number == 1
        assert "three" in chunks_a[0].text and "four" not in chunks_a[0].text


# --------------------------------------------------------------- benchmark identity

class TestBenchmarkIdentity:
    def test_deterministic(self):
        kwargs = dict(dataset_revision="rev1", dataset_file_sha256="a" * 64,
                      document_manifest_sha256="b" * 64, evidence_alignment_version="1.0")
        a = fb.build_benchmark_identity(**kwargs)
        b = fb.build_benchmark_identity(**kwargs)
        assert fb.compute_benchmark_config_hash(a) == fb.compute_benchmark_config_hash(b)

    def test_revision_change_changes_hash(self):
        base = dict(dataset_file_sha256="a" * 64, document_manifest_sha256="b" * 64, evidence_alignment_version="1.0")
        h1 = fb.compute_benchmark_config_hash(fb.build_benchmark_identity(dataset_revision="rev1", **base))
        h2 = fb.compute_benchmark_config_hash(fb.build_benchmark_identity(dataset_revision="rev2", **base))
        assert h1 != h2

    def test_no_timestamp_or_git_sha_in_identity(self):
        identity = fb.build_benchmark_identity(dataset_revision="rev1", dataset_file_sha256="a" * 64,
                                                 document_manifest_sha256="b" * 64, evidence_alignment_version="1.0")
        assert "timestamp" not in identity
        assert "git_sha" not in identity
        assert "created_at_utc" not in identity


# --------------------------------------------------------------- retrieval metrics

class TestRetrievalMetrics:
    def test_gold_item_at_rank_1(self):
        result = fb.evaluate_financebench_question(
            financebench_id="q1", retrieved_doc_names=["A", "B", "C"], retrieved_chunk_ids=["c1", "c2", "c3"],
            gold_doc_name="A", gold_chunk_ids=("c1",), k=10,
        )
        assert result.doc_recall_hit is True
        assert result.doc_first_hit_rank == 1
        assert result.evidence_hits_in_top_k == 1
        assert result.evidence_first_hit_rank == 1

    def test_gold_item_at_rank_k(self):
        docs = ["X"] * 9 + ["A"]
        chunks = [f"c{i}" for i in range(9)] + ["cgold"]
        result = fb.evaluate_financebench_question(
            financebench_id="q1", retrieved_doc_names=docs, retrieved_chunk_ids=chunks,
            gold_doc_name="A", gold_chunk_ids=("cgold",), k=10,
        )
        assert result.doc_recall_hit is True
        assert result.doc_first_hit_rank == 10
        assert result.evidence_first_hit_rank == 10

    def test_multiple_gold_evidence_items(self):
        result = fb.evaluate_financebench_question(
            financebench_id="q1", retrieved_doc_names=["A"] * 3, retrieved_chunk_ids=["c1", "c2", "c3"],
            gold_doc_name="A", gold_chunk_ids=("c1", "c3", "cX"), k=10,
        )
        assert result.evidence_hits_in_top_k == 2  # c1 and c3 hit, cX not retrieved

    def test_no_gold_retrieved(self):
        result = fb.evaluate_financebench_question(
            financebench_id="q1", retrieved_doc_names=["B", "C"], retrieved_chunk_ids=["c2", "c3"],
            gold_doc_name="A", gold_chunk_ids=("c1",), k=10,
        )
        assert result.doc_recall_hit is False
        assert result.doc_first_hit_rank is None
        assert result.evidence_hits_in_top_k == 0
        assert result.evidence_first_hit_rank is None

    def test_beyond_k_not_counted(self):
        docs = ["X"] * 10 + ["A"]  # gold doc is at rank 11, beyond k=10
        result = fb.evaluate_financebench_question(
            financebench_id="q1", retrieved_doc_names=docs, retrieved_chunk_ids=["c"] * 11,
            gold_doc_name="A", gold_chunk_ids=("c1",), k=10,
        )
        assert result.doc_recall_hit is False
        assert result.doc_first_hit_rank is None


class TestAggregateRetrievalResult:
    def _result(self, **overrides):
        base = dict(financebench_id="q", doc_recall_hit=True, doc_first_hit_rank=1,
                    evidence_relevant_chunk_ids=("c1",), evidence_hits_in_top_k=1, evidence_first_hit_rank=1,
                    status="evaluated")
        base.update(overrides)
        return fb.QuestionRetrievalResult(**base)

    def test_infrastructure_status_excluded_from_denominator(self):
        results = [self._result(), self._result(status="blocked_document_missing", doc_recall_hit=False,
                                                  doc_first_hit_rank=None, evidence_hits_in_top_k=0, evidence_first_hit_rank=None)]
        agg = fb.aggregate_financebench_results(results, k=10)
        assert agg.evaluated_count == 1

    def test_doc_recall_math(self):
        results = [self._result(doc_recall_hit=True), self._result(doc_recall_hit=False, doc_first_hit_rank=None)]
        agg = fb.aggregate_financebench_results(results, k=10)
        assert agg.doc_recall_at_k == 0.5
        assert agg.doc_hit_count == 1

    def test_mrr_math(self):
        results = [self._result(doc_first_hit_rank=1), self._result(doc_first_hit_rank=4)]
        agg = fb.aggregate_financebench_results(results, k=10)
        assert agg.doc_mrr == pytest.approx((1.0 + 0.25) / 2)

    def test_evidence_recall_is_macro_average_not_pooled(self):
        # q1: 1/1 gold hit (recall=1.0); q2: 1/2 gold hit (recall=0.5)
        # macro mean = 0.75; pooled would be (1+1)/(1+2) = 0.667
        results = [
            self._result(financebench_id="q1", evidence_relevant_chunk_ids=("c1",), evidence_hits_in_top_k=1),
            self._result(financebench_id="q2", evidence_relevant_chunk_ids=("c1", "c2"), evidence_hits_in_top_k=1),
        ]
        agg = fb.aggregate_financebench_results(results, k=10)
        assert agg.evidence_recall_at_k == pytest.approx(0.75)

    def test_empty_evidence_question_excluded_from_evidence_metric(self):
        results = [self._result(evidence_relevant_chunk_ids=())]
        agg = fb.aggregate_financebench_results(results, k=10)
        assert agg.evidence_questions_with_gold == 0
        assert agg.evidence_recall_at_k == 0.0

    def test_zero_evaluated_questions_raises(self):
        results = [self._result(status="blocked_document_missing")]
        with pytest.raises(fb.FinanceBenchError):
            fb.aggregate_financebench_results(results, k=10)

    def test_never_silently_drops_denominator(self):
        results = [self._result(), self._result(status="blocked_parse_failure"), self._result(status="infrastructure_error")]
        agg = fb.aggregate_financebench_results(results, k=10)
        # only 1 of 3 counted in evaluated_count - the other 2 statuses must
        # be reported separately by the caller, never silently vanish.
        assert agg.evaluated_count == 1
        assert len(results) == 3
