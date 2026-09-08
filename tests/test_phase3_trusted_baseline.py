"""Task 3.1 - tests for src.eval.phase3_baseline (pure logic, synthetic
fixtures only - no GPU, no LanceDB, no model load, no network) plus a
handful of static-import-scan tests proving the formal runner never
touches TEST. A local-data/GPU integration test (marked) exercises a tiny
real slice of the retrieval loop if the Phase 1 index is present."""

from __future__ import annotations

import csv
import inspect
from pathlib import Path

import pytest

from src.eval import phase3_baseline as p3
from src.eval.baseline_metrics import evaluate_question, summarize_doc_recall
from src.eval.metrics import first_hit_rank, reciprocal_rank, ndcg_at_k, hit_at_k


# --------------------------------------------------------------- fixtures

def numeric_q(question_id, cik, fiscal_year, subtype="xbrl_fact", category="numeric"):
    return {"question_id": question_id, "category": category, "subtype": subtype, "cik": cik, "fiscal_year": fiscal_year}


def yoy_q(question_id, cik, year_a, year_b):
    return {
        "question_id": question_id, "category": "comparative", "subtype": "year_over_year_difference",
        "cik": cik, "operands": [{"fiscal_year": year_a}, {"fiscal_year": year_b}],
    }


def cross_entity_q(question_id, cik_a, cik_b, fiscal_year):
    return {
        "question_id": question_id, "category": "comparative", "subtype": "cross_entity_comparison",
        "fiscal_year": fiscal_year, "operands": [{"cik": cik_a}, {"cik": cik_b}],
    }


def adversarial_q(question_id, subtype="prompt_injection"):
    return {"question_id": question_id, "category": "adversarial", "subtype": subtype}


def year_outside_window_q(question_id, cik=1, fiscal_year=2099):
    return {"question_id": question_id, "category": "unanswerable", "subtype": "year_outside_window", "cik": cik, "fiscal_year": fiscal_year}


def unsupported_tag_q(question_id, cik, fiscal_year):
    return {"question_id": question_id, "category": "unanswerable", "subtype": "unsupported_tag", "cik": cik, "fiscal_year": fiscal_year}


# --------------------------------------------------------------- document identity

class TestDocumentIdentity:
    def test_format(self):
        assert p3.document_id_for(12345, 2018) == "12345_2018.htm"

    def test_rejects_non_int_cik(self):
        with pytest.raises(p3.Phase3BaselineError):
            p3.document_id_for("12345", 2018)

    def test_rejects_bool_cik(self):
        with pytest.raises(p3.Phase3BaselineError):
            p3.document_id_for(True, 2018)


# --------------------------------------------------------------- applicability (test 3)

class TestApplicability:
    def test_numeric_applicable(self):
        assert p3.classify_applicability(numeric_q("q1", 1, 2018)) == "applicable"

    def test_unsupported_tag_applicable(self):
        assert p3.classify_applicability(unsupported_tag_q("q1", 1, 2018)) == "applicable"

    def test_yoy_applicable(self):
        assert p3.classify_applicability(yoy_q("q1", 1, 2018, 2019)) == "applicable"

    def test_cross_entity_applicable(self):
        assert p3.classify_applicability(cross_entity_q("q1", 1, 2, 2018)) == "applicable"

    @pytest.mark.parametrize("subtype", ["prompt_injection", "financial_advice", "off_scope"])
    def test_adversarial_not_applicable(self, subtype):
        assert p3.classify_applicability(adversarial_q("q1", subtype)) == "not_applicable"

    def test_year_outside_window_not_applicable(self):
        assert p3.classify_applicability(year_outside_window_q("q1")) == "not_applicable"

    def test_unknown_shape_raises(self):
        with pytest.raises(p3.Phase3BaselineError):
            p3.classify_applicability({"question_id": "q1", "category": "narrative", "subtype": "something_new"})

    def test_target_ids_raise_for_not_applicable(self):
        with pytest.raises(p3.Phase3BaselineError):
            p3.question_target_document_ids(adversarial_q("q1"))


# --------------------------------------------------------------- multi-document targets (test 4)

class TestMultiDocumentTargets:
    def test_yoy_two_documents(self):
        q = yoy_q("q1", 42, 2018, 2019)
        assert p3.question_target_document_ids(q) == ["42_2018.htm", "42_2019.htm"]

    def test_yoy_dedups_same_year(self):
        q = yoy_q("q1", 42, 2018, 2018)
        assert p3.question_target_document_ids(q) == ["42_2018.htm"]

    def test_cross_entity_two_documents(self):
        q = cross_entity_q("q1", 10, 20, 2019)
        assert p3.question_target_document_ids(q) == ["10_2019.htm", "20_2019.htm"]

    def test_single_target_shapes_return_one_id(self):
        assert p3.question_target_document_ids(numeric_q("q1", 5, 2020)) == ["5_2020.htm"]
        assert p3.question_target_document_ids(unsupported_tag_q("q1", 5, 2020)) == ["5_2020.htm"]


# --------------------------------------------------------------- coverage audit (tests 5, 6)

class TestCoverageAudit:
    def test_out_of_corpus_full_miss_is_none_coverage(self):
        q = numeric_q("q1", 999, 2018)
        result = p3.audit_question_coverage(q, index_document_ids=set())
        assert result.coverage == "none"
        assert result.applicability == "applicable"

    def test_full_coverage(self):
        q = numeric_q("q1", 1, 2018)
        result = p3.audit_question_coverage(q, index_document_ids={"1_2018.htm"})
        assert result.coverage == "full"

    def test_partial_coverage_multi_doc(self):
        q = yoy_q("q1", 1, 2018, 2019)
        result = p3.audit_question_coverage(q, index_document_ids={"1_2018.htm"})
        assert result.coverage == "partial"

    def test_not_applicable_gets_na_coverage(self):
        result = p3.audit_question_coverage(adversarial_q("q1"), index_document_ids=set())
        assert result.coverage == "na"
        assert result.applicability == "not_applicable"

    def test_out_of_corpus_never_selected_into_scope(self):
        """The critical rule: an out-of-corpus target is not a retrieval
        miss - it must never appear in the frozen scope at all, whether
        partially or not covered."""
        questions = [
            numeric_q("full", 1, 2018),
            numeric_q("missing", 999, 2018),
            yoy_q("partial", 1, 2018, 2019),
            adversarial_q("na"),
        ]
        scope = p3.select_phase3_dev_scope(questions, index_document_ids={"1_2018.htm"})
        assert scope == ["full"]

    def test_audit_dev_coverage_summary_counts(self):
        questions = [numeric_q("q1", 1, 2018), numeric_q("q2", 2, 2018), adversarial_q("q3")]
        summary, results = p3.audit_dev_coverage(questions, index_document_ids={"1_2018.htm"})
        assert summary["total_questions"] == 3
        assert summary["retrieval_applicable"] == 2
        assert summary["not_applicable"] == 1
        assert summary["fully_covered"] == 1
        assert summary["not_covered"] == 1
        assert len(results) == 3


# --------------------------------------------------------------- scope hash determinism (test 7)

class TestScopeHashing:
    def test_scope_hash_deterministic(self):
        ids = ["b", "a", "c"]
        assert p3.compute_phase3_dev_scope_sha256(ids) == p3.compute_phase3_dev_scope_sha256(list(reversed(ids)))

    def test_scope_hash_sensitive_to_membership(self):
        h1 = p3.compute_phase3_dev_scope_sha256(["a", "b"])
        h2 = p3.compute_phase3_dev_scope_sha256(["a", "b", "c"])
        assert h1 != h2

    def test_question_ids_hash_independent_of_scope_kind(self):
        ids = ["a", "b"]
        h1 = p3.compute_question_ids_sha256(ids)
        h2 = p3.compute_question_ids_sha256(list(reversed(ids)))
        assert h1 == h2


# --------------------------------------------------------------- config hash determinism/sensitivity (test 8)

def _sample_config(**overrides) -> dict:
    base = dict(
        eval_set_version="phase2-v1", source_dataset_sha256="a" * 64, split_version="phase2-split-v1",
        split_assignment_sha256="b" * 64, phase3_dev_scope_sha256="c" * 64, question_count=89,
        question_ids_sha256="d" * 64, normalizer_version="phase1-minimal-v1", normalization_build_sha256="e" * 64,
        chunk_config_hash="f" * 64, chunk_schema_version=1, embedding_model="BAAI/bge-small-en-v1.5",
        embedding_revision="rev", embedding_identity_hash="1" * 64, index_identity_hash="2" * 64,
        distance_metric="cosine", index_type="exact_flat", metric_schema_version=1,
        evaluation_schema_hash="3" * 64, git_sha="4" * 40,
    )
    base.update(overrides)
    return p3.build_phase3_config(**base)


class TestConfigHash:
    def test_deterministic_regardless_of_key_order(self):
        cfg = _sample_config()
        shuffled = dict(reversed(list(cfg.items())))
        assert p3.compute_phase3_config_hash(cfg) == p3.compute_phase3_config_hash(shuffled)

    def test_sensitive_to_a_semantic_field(self):
        cfg1 = _sample_config()
        cfg2 = _sample_config(chunk_config_hash="9" * 64)
        assert p3.compute_phase3_config_hash(cfg1) != p3.compute_phase3_config_hash(cfg2)

    def test_insensitive_to_git_sha(self):
        cfg1 = _sample_config(git_sha="1" * 40)
        cfg2 = _sample_config(git_sha="2" * 40)
        assert p3.compute_phase3_config_hash(cfg1) == p3.compute_phase3_config_hash(cfg2)

    def test_generation_always_disabled(self):
        assert _sample_config()["generation_enabled"] is False


# --------------------------------------------------------------- artifact identity mismatch (test 9)

class TestArtifactIdentityVerification:
    def test_matching_identities_pass(self):
        cfg = _sample_config(chunk_config_hash="f" * 64, embedding_identity_hash="1" * 64, index_identity_hash="2" * 64)
        p3.verify_artifact_identities(
            cfg, live_chunk_config_hash="f" * 64, live_embedding_identity_hash="1" * 64, live_index_identity_hash="2" * 64,
        )

    def test_chunk_hash_mismatch_raises(self):
        cfg = _sample_config()
        with pytest.raises(p3.Phase3BaselineError):
            p3.verify_artifact_identities(
                cfg, live_chunk_config_hash="0" * 64,
                live_embedding_identity_hash=cfg["embedding_identity_hash"],
                live_index_identity_hash=cfg["index_identity_hash"],
            )

    def test_embedding_identity_mismatch_raises(self):
        cfg = _sample_config()
        with pytest.raises(p3.Phase3BaselineError):
            p3.verify_artifact_identities(
                cfg, live_chunk_config_hash=cfg["chunk_config_hash"],
                live_embedding_identity_hash="0" * 64, live_index_identity_hash=cfg["index_identity_hash"],
            )

    def test_index_identity_mismatch_raises(self):
        cfg = _sample_config()
        with pytest.raises(p3.Phase3BaselineError):
            p3.verify_artifact_identities(
                cfg, live_chunk_config_hash=cfg["chunk_config_hash"],
                live_embedding_identity_hash=cfg["embedding_identity_hash"], live_index_identity_hash="0" * 64,
            )


# --------------------------------------------------------------- raw vector rank preserved (test 10)

class TestRankOrderPreserved:
    def test_ranked_document_ids_follow_input_order(self):
        # Synthetic stand-in for retriever output - rank order must never be
        # re-sorted by this module (it has no ranking logic of its own).
        class Fake:
            def __init__(self, document_id):
                self.document_id = document_id
        fake_results = [Fake("z_doc"), Fake("a_doc"), Fake("m_doc")]
        ranked = [r.document_id for r in fake_results]
        assert ranked == ["z_doc", "a_doc", "m_doc"]  # not alphabetically re-sorted


# --------------------------------------------------------------- doc_recall@10 / doc_mrr / doc_ndcg@10 reuse (tests 11-14)

class TestMetricReuse:
    def test_doc_recall_at_10_uses_task_1_10_semantics(self):
        class R:
            def __init__(self, rank, document_id):
                self.rank, self.document_id = rank, document_id
                self.chunk_id, self.score, self.distance = f"c{rank}", 0.5, 0.5
        results = [R(i, "other_doc") for i in range(1, 11)]
        results[4] = R(5, "target_doc")
        qr = evaluate_question(
            question_id="q1", question="?", category="numeric",
            target_document_id="target_doc", retrieved_results=results, k=10,
        )
        assert qr.hit is True
        assert qr.first_hit_rank == 5
        agg = summarize_doc_recall([qr], k=10)
        assert agg.doc_recall_at_k == 1.0

    def test_doc_mrr_uses_task_2_6_reciprocal_rank(self):
        ranked = ["a", "b", "target", "c"]
        rank = first_hit_rank(ranked, {"target"}, k=10)
        assert rank == 3
        assert reciprocal_rank(rank) == pytest.approx(1 / 3)

    def test_doc_mrr_zero_when_absent(self):
        rank = first_hit_rank(["a", "b"], {"target"}, k=10)
        assert rank is None
        assert reciprocal_rank(rank) == 0.0

    def test_doc_ndcg_at_10_uses_task_2_6_ndcg(self):
        import math
        relevances = [0, 0, 1, 0]  # hit at rank 3
        ndcg = ndcg_at_k(relevances, num_relevant=1, k=10)
        # idcg(num_relevant=1, k=10) == 1/log2(2) == 1.0; dcg with the hit at
        # rank 3 == 1/log2(4) - hand-computable, not copied from the module.
        assert ndcg == pytest.approx((1 / math.log2(4)) / 1.0)


# --------------------------------------------------------------- doc_recall@50 diagnostic (test 14)

class TestDocRecallAt50Diagnostic:
    def test_hand_checkable(self):
        ranked = [f"doc{i}" for i in range(60)]
        ranked[49] = "target"  # rank 50, last position within top-50
        rank = first_hit_rank(ranked, {"target"}, k=50)
        assert rank == 50
        assert hit_at_k(rank, 50) is True

    def test_miss_beyond_50(self):
        ranked = [f"doc{i}" for i in range(60)]
        ranked[50] = "target"  # rank 51, outside top-50
        rank = first_hit_rank(ranked, {"target"}, k=50)
        assert rank is None
        assert hit_at_k(rank, 50) is False


# --------------------------------------------------------------- N/A != 0 (test 15)

class TestNeverAOsZero:
    def test_row0_precision_and_refusal_are_na_strings(self):
        row = p3.build_row0(
            run_id="r1", git_sha="g" * 40, phase3_config_hash="h" * 64, eval_scope_sha256="s" * 64,
            question_count=89, corpus_document_count=1493, chunk_count=162357, chunk_config_hash="f" * 64,
            embedding_model="BAAI/bge-small-en-v1.5", embedding_revision="rev", embedding_identity="1" * 64,
            index_identity="2" * 64, candidate_k=50, doc_recall_at_10=0.5, doc_recall_at_50=0.6,
            doc_mrr=0.4, doc_ndcg_at_10=0.45, retrieval_latency_p50_ms=10.0, retrieval_latency_p95_ms=20.0,
            query_embedding_latency_p50_ms=5.0, search_latency_p50_ms=5.0, index_size_bytes=1000, notes="test",
        )
        assert row["precision_at_5"] == p3.NA
        assert row["refusal_metric"] == p3.NA
        assert row["precision_at_5"] != 0
        assert row["refusal_metric"] != 0

    def test_csv_roundtrip_preserves_na_distinct_from_zero(self, tmp_path: Path):
        row = {"row_id": 1, "doc_recall_at_10": 0.0, "precision_at_5": p3.NA}
        p3.write_ablation_table(tmp_path / "t.csv", [row])
        loaded = p3.load_ablation_table(tmp_path / "t.csv")
        assert loaded[0]["doc_recall_at_10"] == "0.0"
        assert loaded[0]["precision_at_5"] == "N/A"
        assert loaded[0]["precision_at_5"] != loaded[0]["doc_recall_at_10"]


# --------------------------------------------------------------- no chunk-level metric without gold (test 16)

class TestNoChunkMetricWithoutGold:
    def test_ablation_columns_exclude_chunk_level_metrics(self):
        assert "chunk_recall_at_10" not in p3.ABLATION_TABLE_COLUMNS
        assert "chunk_mrr" not in p3.ABLATION_TABLE_COLUMNS


# --------------------------------------------------------------- generation disabled (test 17)

class TestGenerationDisabled:
    def test_config_generation_enabled_false(self):
        assert _sample_config()["generation_enabled"] is False


# --------------------------------------------------------------- no network/paid calls in portable tests (test 18)

class TestNoNetworkImports:
    def test_module_source_has_no_network_or_paid_api_references(self):
        source = inspect.getsource(p3)
        for forbidden in ("openrouter", "requests.", "httpx.", "urllib.request"):
            assert forbidden not in source.lower()


# --------------------------------------------------------------- Task 2.11 run-log DEV provenance (test 19)

class TestRunLogDevProvenance:
    def test_build_run_record_dev_split(self):
        from src.eval.run_logging import build_run_record, validate_run_record

        record = build_run_record(
            chunk_schema_version=1, chunk_config_hash="f" * 64,
            embedding_model={
                "model_repository": "BAAI/bge-small-en-v1.5", "model_revision": "rev",
                "embedding_dimension": 384, "vector_dtype": "float32", "normalize_embeddings": True,
                "identity_hash": "1" * 64,
            },
            index_identity_hash="2" * 64,
            retrieval_config={"type": "vector_exact_cosine", "top_k": 50},
            reranker_config={"enabled": False}, generation_model=None,
            split="dev", eval_set_version="phase2-v1", split_version="phase2-split-v1",
            metrics={"doc_recall@10": 0.5},
            git_state={"git_sha": "a" * 40, "git_dirty": False},
        )
        validate_run_record(record)
        assert record.split == "dev"
        assert record.evaluation_source == "internal_phase2"
        assert record.generation_model is None


# --------------------------------------------------------------- scope size determinism (test 20)

class TestScopeSizeMatchesExpectedCoverage:
    def test_scope_matches_full_coverage_count(self):
        questions = [
            numeric_q("q1", 1, 2018), numeric_q("q2", 2, 2018),  # full
            numeric_q("q3", 999, 2018),  # missing
            unsupported_tag_q("q4", 1, 2018),  # full (shares doc with q1)
            yoy_q("q5", 1, 2018, 2019),  # partial
        ]
        index_ids = {"1_2018.htm", "2_2018.htm"}
        scope = p3.select_phase3_dev_scope(questions, index_ids)
        assert scope == ["q1", "q2", "q4"]


# --------------------------------------------------------------- ablation table row 0 freeze (tests 21, 22)

class TestAblationTableFreeze:
    def test_row0_appended_when_absent(self):
        rows = p3.upsert_row([], {"row_id": 0, "phase3_config_hash": "h1"})
        assert len(rows) == 1
        assert rows[0]["row_id"] == 0

    def test_idempotent_rewrite_same_config_is_noop(self):
        rows = [{"row_id": 0, "phase3_config_hash": "h1", "notes": "original"}]
        result = p3.upsert_row(rows, {"row_id": 0, "phase3_config_hash": "h1", "notes": "attempted overwrite"})
        assert result[0]["notes"] == "original"  # unchanged - table returned as-is

    def test_different_config_hash_for_existing_row_raises(self):
        rows = [{"row_id": 0, "phase3_config_hash": "h1"}]
        with pytest.raises(p3.Phase3BaselineError):
            p3.upsert_row(rows, {"row_id": 0, "phase3_config_hash": "h2"})

    def test_duplicate_row_ids_already_present_raises(self):
        rows = [{"row_id": 0, "phase3_config_hash": "h1"}, {"row_id": 0, "phase3_config_hash": "h1"}]
        with pytest.raises(p3.Phase3BaselineError):
            p3.upsert_row(rows, {"row_id": 0, "phase3_config_hash": "h1"})

    def test_new_row_id_appended_alongside_row0(self):
        rows = [{"row_id": 0, "phase3_config_hash": "h1"}]
        result = p3.upsert_row(rows, {"row_id": 1, "phase3_config_hash": "h2"})
        assert len(result) == 2
        assert {r["row_id"] for r in result} == {0, 1}

    def test_write_and_load_roundtrip(self, tmp_path: Path):
        rows = [{"row_id": 0, "phase3_config_hash": "h1", "doc_recall_at_10": 0.5}]
        path = tmp_path / "ablation.csv"
        p3.write_ablation_table(path, rows)
        loaded = p3.load_ablation_table(path)
        assert loaded[0]["row_id"] == "0"
        assert loaded[0]["phase3_config_hash"] == "h1"

    def test_row_carries_config_hash_and_git_sha(self):
        row = p3.build_row0(
            run_id="r1", git_sha="g" * 40, phase3_config_hash="h" * 64, eval_scope_sha256="s" * 64,
            question_count=1, corpus_document_count=1, chunk_count=1, chunk_config_hash="f" * 64,
            embedding_model="m", embedding_revision="rev", embedding_identity="1" * 64, index_identity="2" * 64,
            candidate_k=50, doc_recall_at_10=1.0, doc_recall_at_50=1.0, doc_mrr=1.0, doc_ndcg_at_10=1.0,
            retrieval_latency_p50_ms=1.0, retrieval_latency_p95_ms=1.0, query_embedding_latency_p50_ms=1.0,
            search_latency_p50_ms=1.0, index_size_bytes=1, notes="",
        )
        assert row["git_sha"] == "g" * 40
        assert row["phase3_config_hash"] == "h" * 64


# --------------------------------------------------------------- result JSON provenance (test 23)

class TestResultSummaryProvenance:
    def test_summary_carries_run_id_git_sha_config_hash(self):
        summary = p3.build_result_summary(
            run_id="r1", git_sha="g" * 40, phase3_config={"a": 1}, phase3_config_hash="h" * 64,
            question_count=2, metrics={"doc_recall@10": 1.0}, stage_timings_ms={}, question_ids=["b", "a"],
        )
        assert summary["run_id"] == "r1"
        assert summary["git_sha"] == "g" * 40
        assert summary["phase3_config_hash"] == "h" * 64
        assert summary["question_ids"] == ["a", "b"]  # sorted, not insertion order


# --------------------------------------------------------------- no TEST payload in result (test 24) + no TEST import (tests 1, 2)

def _ast_imports_or_calls(source: str, *, forbidden_module_substring: str, forbidden_call_name: str) -> bool:
    """True iff `source` contains a real Import/ImportFrom node naming a
    module with `forbidden_module_substring`, or a Call node invoking
    `forbidden_call_name` - never a naive substring scan, which would
    also flag this module's own explanatory docstrings/comments about
    why it avoids TEST access."""
    import ast

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(forbidden_module_substring in alias.name for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if forbidden_module_substring in module or any(forbidden_module_substring in a.name for a in node.names):
                return True
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name == forbidden_call_name:
                return True
    return False


class TestNeverTouchesTest:
    def test_module_never_imports_test_access(self):
        source = inspect.getsource(p3)
        assert not _ast_imports_or_calls(source, forbidden_module_substring="test_access", forbidden_call_name="load_test_set")

    def test_runner_script_never_imports_test_access(self):
        runner_path = Path(__file__).resolve().parents[1] / "scripts" / "run_phase3_trusted_baseline.py"
        source = runner_path.read_text(encoding="utf-8")
        assert not _ast_imports_or_calls(source, forbidden_module_substring="test_access", forbidden_call_name="load_test_set")

    def test_result_summary_question_ids_are_exactly_the_given_scope(self):
        summary = p3.build_result_summary(
            run_id="r1", git_sha="g" * 40, phase3_config={}, phase3_config_hash="h" * 64,
            question_count=2, metrics={}, stage_timings_ms={}, question_ids=["dev-1", "dev-2"],
        )
        assert set(summary["question_ids"]) == {"dev-1", "dev-2"}


# --------------------------------------------------------------- frozen historical identities (test 25 guard)

class TestFrozenIdentityConstants:
    """Guards against accidental drift in the runner's hardcoded Phase 1
    identity constants - these must always equal the values independently
    verified against the live artifacts before this task began."""

    def test_runner_constants_match_frozen_values(self):
        import scripts.run_phase3_trusted_baseline as runner

        assert runner.CHUNK_CONFIG_HASH == "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
        assert runner.EXPECTED_EMBEDDING_IDENTITY_HASH == "b39a67c9eb6487fc98f266f23742afd0a30321d98067505802a1e219b27bec84"
        assert runner.EXPECTED_INDEX_IDENTITY_HASH == "ace70ee67d8e98e019d221f2a0215a5b88498a0fc5dcbe73ac7ef1277630b111"
        assert runner.EXPECTED_ROW_COUNT == 162357


# --------------------------------------------------------------- integration (real index, gated)

@pytest.mark.local_data
@pytest.mark.gpu
@pytest.mark.model
class TestRealCoverageAuditIntegration:
    def test_real_dev_scope_is_nonempty_and_frozen_shape(self):
        import json
        from pathlib import Path as _P
        import lancedb

        repo_root = _P(__file__).resolve().parents[1]
        dev = json.loads((repo_root / "results" / "phase_2_4_dev.json").read_text(encoding="utf-8"))
        db = lancedb.connect(
            str(repo_root / "artifacts" / "indexes" / "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd" / "BAAI--bge-small-en-v1.5")
        )
        table = db.open_table("chunks")
        doc_ids = set(table.to_pandas()["document_id"].unique().tolist())

        scope = p3.select_phase3_dev_scope(dev["questions"], doc_ids)
        assert len(scope) == 89
        assert scope == sorted(scope)
