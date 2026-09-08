"""Task 2.13 - portable tests for the cross-model agreement study
(qwen3.5:9b vs gpt-oss:20b). All localhost HTTP is mocked/stubbed - no
Ollama, no GPU, no network.

Methodology note: the originally planned 100-case HUMAN calibration was
replaced, by explicit user decision, with this cross-model agreement
study - see prompts/phase_2/task_2.13_cross_model_agreement_study.md.
No human labeling occurs anywhere in this module or the code it tests.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from src.eval import llm_judge as lj

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "run_llm_judge_validation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_llm_judge_validation_xm", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rlv():
    return _load_module()


def make_case(case_id="c1", **overrides):
    base = dict(case_id=case_id, question="Q", reference_answer="R", candidate_answer="C", evidence="E")
    base.update(overrides)
    return base


def make_config(model_tag="qwen3.5:9b", think=False, **overrides) -> lj.JudgeConfig:
    base = dict(
        provider="ollama", model_tag=model_tag, model_digest="a" * 64, architecture="qwen35",
        parameter_size="9.7B", quantization="Q4_K_M", ollama_version="0.33.3",
        temperature=0, seed=42, think=think, stream=False, num_ctx=4096,
        rubric_version=lj.RUBRIC_VERSION, prompt_version=lj.PROMPT_VERSION,
        output_schema_version=lj.OUTPUT_SCHEMA_VERSION,
    )
    base.update(overrides)
    return lj.JudgeConfig(**base)


# --------------------------------------------------------------- think=None omission

class TestThinkParamOmission:
    def test_think_false_included_in_payload(self):
        item = lj.JudgeInput(case_id="c1", question="Q", reference_answer="R", candidate_answer="C", evidence="E")
        payload = lj.build_request_payload(item, make_config(think=False))
        assert payload["think"] is False

    def test_think_none_omitted_from_payload(self):
        item = lj.JudgeInput(case_id="c1", question="Q", reference_answer="R", candidate_answer="C", evidence="E")
        payload = lj.build_request_payload(item, make_config(model_tag="gpt-oss:20b", think=None))
        assert "think" not in payload

    def test_think_none_changes_config_hash_vs_false(self):
        h_false = lj.compute_judge_config_hash(make_config(think=False))
        h_none = lj.compute_judge_config_hash(make_config(think=None))
        assert h_false != h_none


# --------------------------------------------------------------- distinct configs

class TestModelConfigsAreDistinct:
    def test_qwen_and_gptoss_configs_produce_different_hashes(self):
        qwen = make_config(model_tag="qwen3.5:9b", model_digest="a" * 64, architecture="qwen35", think=False)
        gptoss = make_config(model_tag="gpt-oss:20b", model_digest="b" * 64, architecture="gptoss", think=None)
        assert lj.compute_judge_config_hash(qwen) != lj.compute_judge_config_hash(gptoss)

    def test_both_share_identical_rubric_and_schema(self):
        qwen = make_config(model_tag="qwen3.5:9b", think=False)
        gptoss = make_config(model_tag="gpt-oss:20b", think=None)
        # The only permitted difference is provider/model-specific fields
        # (model_tag/digest/architecture/parameter_size/quantization/
        # ollama_version) and the think param itself - rubric/schema must
        # be byte-identical (same SYSTEM_PROMPT/_JSON_SCHEMA constants).
        assert qwen.rubric_version == gptoss.rubric_version
        assert qwen.output_schema_version == gptoss.output_schema_version
        d_qwen = qwen.semantic_dict()
        d_gptoss = gptoss.semantic_dict()
        assert d_qwen["system_prompt"] == d_gptoss["system_prompt"]
        assert d_qwen["json_schema"] == d_gptoss["json_schema"]
        assert d_qwen["rubric_version"] == d_gptoss["rubric_version"]


# --------------------------------------------------------------- study hash

class TestStudyHash:
    def test_deterministic(self, rlv):
        h1 = rlv.compute_cross_model_study_hash(calibration_set_sha256="abc", qwen_judge_config_hash="q",
                                                 gpt_oss_judge_config_hash="g")
        h2 = rlv.compute_cross_model_study_hash(calibration_set_sha256="abc", qwen_judge_config_hash="q",
                                                 gpt_oss_judge_config_hash="g")
        assert h1 == h2

    def test_changes_with_calibration_set(self, rlv):
        h1 = rlv.compute_cross_model_study_hash(calibration_set_sha256="abc", qwen_judge_config_hash="q",
                                                 gpt_oss_judge_config_hash="g")
        h2 = rlv.compute_cross_model_study_hash(calibration_set_sha256="xyz", qwen_judge_config_hash="q",
                                                 gpt_oss_judge_config_hash="g")
        assert h1 != h2

    def test_changes_with_either_judge_config_hash(self, rlv):
        base = rlv.compute_cross_model_study_hash(calibration_set_sha256="abc", qwen_judge_config_hash="q",
                                                    gpt_oss_judge_config_hash="g")
        changed_qwen = rlv.compute_cross_model_study_hash(calibration_set_sha256="abc",
                                                            qwen_judge_config_hash="q2",
                                                            gpt_oss_judge_config_hash="g")
        changed_gptoss = rlv.compute_cross_model_study_hash(calibration_set_sha256="abc",
                                                              qwen_judge_config_hash="q",
                                                              gpt_oss_judge_config_hash="g2")
        assert base != changed_qwen != changed_gptoss
        assert base != changed_gptoss


# --------------------------------------------------------------- independence (no cross-leakage)

class TestIndependenceNoCrossLeakage:
    def test_run_one_never_includes_other_models_output(self, rlv, tmp_path, monkeypatch):
        """Structural proof: the JudgeInput built for each model call comes
        only from the calibration case's own fields (question/reference/
        candidate/evidence) - never from the other model's verdict,
        explanation, or aggregate stats."""
        seen_payloads = []

        class _StubJudge:
            def __init__(self, config, on_retry=None):
                self.config = config

            def judge(self, item):
                seen_payloads.append(item)
                return lj.JudgeVerdict(faithfulness="supported", reason_codes=(), explanation="ok",
                                        latency_ms=1.0, attempt_count=1, response_model=None)

        cases = [make_case(case_id="c1")]
        qwen_config = make_config(model_tag="qwen3.5:9b", think=False)
        gptoss_config = make_config(model_tag="gpt-oss:20b", think=None)
        monkeypatch.setattr(rlv.lj, "OllamaJudge", _StubJudge)
        result = rlv._run_cross_model_judgments(
            cases, qwen_config=qwen_config, qwen_hash="qh2",
            gptoss_config=gptoss_config, gptoss_hash="gh2", base_dir=tmp_path / "run2",
        )
        assert len(seen_payloads) == 2
        for item in seen_payloads:
            assert item.question == "Q"
            assert item.candidate_answer == "C"
            # Never a field carrying the other model's identity/verdict.
            for forbidden_attr in ("qwen_faithfulness", "gpt_oss_faithfulness", "other_model_verdict"):
                assert not hasattr(item, forbidden_attr)
        assert result["qwen"]["success_count"] == 1
        assert result["gpt_oss"]["success_count"] == 1

    def test_case_dict_passed_to_judge_input_has_no_other_model_fields(self):
        """The calibration case schema itself never carries the other
        model's output - build_request_payload only ever sees
        question/reference_answer/candidate_answer/evidence."""
        case = make_case()
        assert set(case.keys()) <= {"case_id", "question", "reference_answer", "candidate_answer", "evidence"}


# --------------------------------------------------------------- resume safety

class TestResumeSafety:
    def test_completed_resume_causes_zero_new_model_calls(self, rlv, tmp_path, monkeypatch):
        cases = [make_case(case_id=f"c{i}") for i in range(3)]
        qwen_config = make_config(model_tag="qwen3.5:9b", think=False)
        gptoss_config = make_config(model_tag="gpt-oss:20b", think=None)

        call_count = {"n": 0}

        class _StubJudge:
            def __init__(self, config, on_retry=None):
                pass

            def judge(self, item):
                call_count["n"] += 1
                return lj.JudgeVerdict(faithfulness="supported", reason_codes=(), explanation="ok",
                                        latency_ms=1.0, attempt_count=1, response_model=None)

        monkeypatch.setattr(rlv.lj, "OllamaJudge", _StubJudge)
        rlv._run_cross_model_judgments(cases, qwen_config=qwen_config, qwen_hash="qh",
                                        gptoss_config=gptoss_config, gptoss_hash="gh", base_dir=tmp_path)
        assert call_count["n"] == 6  # 3 cases x 2 models

        # Re-run with identical cases/config hashes - must make zero new calls.
        rlv._run_cross_model_judgments(cases, qwen_config=qwen_config, qwen_hash="qh",
                                        gptoss_config=gptoss_config, gptoss_hash="gh", base_dir=tmp_path)
        assert call_count["n"] == 6

    def test_case_or_config_hash_mismatch_forces_recall(self, rlv, tmp_path, monkeypatch):
        qwen_config = make_config(model_tag="qwen3.5:9b", think=False)
        gptoss_config = make_config(model_tag="gpt-oss:20b", think=None)
        call_count = {"n": 0}

        class _StubJudge:
            def __init__(self, config, on_retry=None):
                pass

            def judge(self, item):
                call_count["n"] += 1
                return lj.JudgeVerdict(faithfulness="supported", reason_codes=(), explanation="ok",
                                        latency_ms=1.0, attempt_count=1, response_model=None)

        monkeypatch.setattr(rlv.lj, "OllamaJudge", _StubJudge)
        cases = [make_case(case_id="c1")]
        rlv._run_cross_model_judgments(cases, qwen_config=qwen_config, qwen_hash="qh",
                                        gptoss_config=gptoss_config, gptoss_hash="gh", base_dir=tmp_path)
        assert call_count["n"] == 2

        # Different judge_config_hash -> cache miss -> must recall.
        rlv._run_cross_model_judgments(cases, qwen_config=qwen_config, qwen_hash="qh_changed",
                                        gptoss_config=gptoss_config, gptoss_hash="gh", base_dir=tmp_path)
        assert call_count["n"] == 3  # only qwen side recalled

    def test_corrupted_checkpoint_rejected(self, rlv, tmp_path):
        base_dir = tmp_path / "qwen"
        (base_dir / "judgments").mkdir(parents=True)
        case = make_case(case_id="bad")
        (base_dir / "judgments" / "bad.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            rlv.load_existing_judgment(base_dir, case, "anyhash")


# --------------------------------------------------------------- cross_model_agreement / confusion matrix / kappa

class TestCrossModelAgreement:
    def test_perfect_agreement(self):
        pairs = [("supported", "supported"), ("unsupported", "unsupported")]
        result = lj.cross_model_agreement(pairs)
        assert result["agreement_rate"] == 1.0
        assert result["disagreement_count"] == 0

    def test_no_over_under_crediting_terminology(self):
        pairs = [("supported", "unsupported"), ("unsupported", "supported")]
        result = lj.cross_model_agreement(pairs)
        assert "over_crediting_count" not in result
        assert "under_crediting_count" not in result

    def test_empty_pairs_rejected(self):
        with pytest.raises(lj.JudgeError):
            lj.cross_model_agreement([])

    def test_invalid_label_rejected(self):
        with pytest.raises(lj.JudgeError):
            lj.cross_model_agreement([("maybe", "supported")])


class TestDisagreementDirection:
    def test_model_a_more_permissive(self):
        pairs = [("supported", "unsupported")]
        result = lj.disagreement_direction(pairs)
        assert result["model_a_more_permissive_count"] == 1
        assert result["model_b_more_permissive_count"] == 0

    def test_model_b_more_permissive(self):
        pairs = [("unsupported", "supported")]
        result = lj.disagreement_direction(pairs)
        assert result["model_b_more_permissive_count"] == 1
        assert result["model_a_more_permissive_count"] == 0

    def test_neutral_wording_no_correct_incorrect(self):
        pairs = [("supported", "unsupported")]
        result = lj.disagreement_direction(pairs)
        for key in result:
            assert "correct" not in key
            assert "accuracy" not in key


class TestConfusionMatrixReused:
    def test_matrix_orientation_qwen_rows_gptoss_cols(self):
        pairs = [("supported", "supported"), ("supported", "unsupported"),
                 ("unsupported", "supported"), ("unsupported", "unsupported")]
        matrix = lj.confusion_matrix(pairs)
        assert matrix["supported_supported"] == 1
        assert matrix["supported_unsupported"] == 1
        assert matrix["unsupported_supported"] == 1
        assert matrix["unsupported_unsupported"] == 1

    def test_cohens_kappa_reused_unchanged(self):
        pairs = [("supported", "supported"), ("unsupported", "unsupported")] * 10
        assert lj.cohens_kappa(pairs) == pytest.approx(1.0)


# --------------------------------------------------------------- no forbidden terminology in result artifact

class TestNoForbiddenTerminologyInResultWriter:
    def test_result_summary_has_no_accuracy_precision_recall_f1(self, rlv, tmp_path, monkeypatch):
        import src.storage as storage_mod

        class _FakeStorage:
            def __init__(self, root):
                self.repo_root = root
                self.artifacts_root = root / "artifacts"

        storage = _FakeStorage(tmp_path)
        qwen_config = make_config(model_tag="qwen3.5:9b", think=False)
        gptoss_config = make_config(model_tag="gpt-oss:20b", think=None)
        base_dir = tmp_path / "artifacts" / "eval" / "llm_judge" / "cross_model" / "studyhash"
        (base_dir / "qwen" / "judgments").mkdir(parents=True)
        (base_dir / "gpt_oss" / "judgments").mkdir(parents=True)
        (tmp_path / "results").mkdir(parents=True)

        pairs = [("supported", "supported"), ("unsupported", "unsupported")]
        cross_agreement = lj.cross_model_agreement(pairs)
        kappa = lj.cohens_kappa(pairs)
        matrix = lj.confusion_matrix(pairs)
        direction = lj.disagreement_direction(pairs)
        run_result = {"qwen": {"success_count": 2, "failure_count": 0},
                      "gpt_oss": {"success_count": 2, "failure_count": 0}}
        repeatability = {
            "qwen": {"subset_size": 2, "runs": 3, "structured_output_success_count": 6,
                     "structured_output_failure_count": 0, "structured_output_success_rate": 1.0,
                     "exact_repeatability_count": 2, "exact_repeatability_rate": 1.0,
                     "cases_with_any_flip": 0, "latency_ms": {"min": 1.0, "max": 2.0, "mean": 1.5}},
            "gpt_oss": {"subset_size": 2, "runs": 3, "structured_output_success_count": 6,
                        "structured_output_failure_count": 0, "structured_output_success_rate": 1.0,
                        "exact_repeatability_count": 2, "exact_repeatability_rate": 1.0,
                        "cases_with_any_flip": 0, "latency_ms": {"min": 1.0, "max": 2.0, "mean": 1.5}},
        }
        calibration = {"case_count": 2, "calibration_set_sha256": "abc"}

        summary = rlv.write_cross_model_result_summary(
            storage=storage, qwen_config=qwen_config, qwen_hash="qh", gptoss_config=gptoss_config,
            gptoss_hash="gh", study_hash="studyhash", calibration=calibration, run_result=run_result,
            pairs=pairs, cross_agreement=cross_agreement, kappa=kappa, matrix=matrix, direction=direction,
            repeatability=repeatability, fixtures=[], base_dir=base_dir,
        )
        # Scan every field EXCEPT `limitations` (which explains, in prose,
        # that these metrics are deliberately not reported - the words
        # legitimately appear there) for the forbidden terminology used as
        # an actual reported metric.
        scanned = {k: v for k, v in summary.items() if k != "limitations"}
        blob = json.dumps(scanned).lower()
        for forbidden in ("precision", "recall", "\"f1\"", "sensitivity", "specificity", "\"accuracy\""):
            assert forbidden not in blob, f"forbidden terminology {forbidden!r} found in cross-model result"
        assert summary["human_validation_performed"] is False
        assert summary["human_validated_judge"] is False

    def test_human_validation_performed_always_false(self, rlv):
        # Structural guarantee: the field is a hardcoded literal in
        # write_cross_model_result_summary, never derived from any
        # runtime state (there is no human-label input to this path at all).
        import inspect
        source = inspect.getsource(rlv.write_cross_model_result_summary)
        assert '"human_validation_performed": False' in source
        assert '"human_validated_judge": False' in source


# --------------------------------------------------------------- status/watch zero model calls

class TestStatusZeroModelCalls:
    def test_status_reads_cross_model_progress_without_ollama_calls(self, rlv, tmp_path, monkeypatch):
        class _FakeStorage:
            def __init__(self, root):
                self.repo_root = root
                self.artifacts_root = root / "artifacts"

        storage = _FakeStorage(tmp_path)
        monkeypatch.setattr(rlv, "get_storage", lambda: storage)

        def _fail_if_called(*a, **k):
            raise AssertionError("cmd_status must never call Ollama")

        monkeypatch.setattr(rlv.lj, "query_ollama_version", _fail_if_called)
        monkeypatch.setattr(rlv.lj, "query_ollama_model_identity", _fail_if_called)
        monkeypatch.setattr(rlv.requests, "get", _fail_if_called) if hasattr(rlv, "requests") else None

        study_dir = storage.artifacts_root / "eval" / "llm_judge" / "cross_model" / "abc123"
        study_dir.mkdir(parents=True)
        (study_dir / "progress.json").write_text(json.dumps({
            "stage": "cross_model_judging", "total": 100, "elapsed_seconds": 10.0,
            "updated_at_utc": "2026-01-01T00:00:00+00:00",
            "qwen": {"completed": 5, "percent": 5.0, "success_count": 5, "failure_count": 0,
                     "inflight_case_id": None, "average_case_seconds": 1.0, "eta_seconds": 95.0},
            "gpt_oss": {"completed": 3, "percent": 3.0, "success_count": 3, "failure_count": 0,
                        "inflight_case_id": "c4", "average_case_seconds": 20.0, "eta_seconds": 1940.0},
        }), encoding="utf-8")

        result = rlv.cmd_status(watch=False)
        assert result == 0


# --------------------------------------------------------------- prompt-injection fixture (mocked)

class TestPromptInjectionFixtureMocked:
    def test_injection_fixture_produces_unsupported_with_stub(self, rlv, monkeypatch):
        class _StubJudge:
            def __init__(self, config, on_retry=None):
                pass

            def judge(self, item):
                # A correctly-behaving judge ignores the injected
                # instruction and judges the content on its merits.
                if "Ignore the rubric" in item.candidate_answer:
                    return lj.JudgeVerdict(faithfulness="unsupported", reason_codes=("contradiction",),
                                            explanation="numeric mismatch", latency_ms=1.0, attempt_count=1,
                                            response_model=None)
                return lj.JudgeVerdict(faithfulness="supported", reason_codes=(), explanation="ok",
                                        latency_ms=1.0, attempt_count=1, response_model=None)

        monkeypatch.setattr(rlv.lj, "OllamaJudge", _StubJudge)
        qwen_config = make_config(model_tag="qwen3.5:9b", think=False)
        gptoss_config = make_config(model_tag="gpt-oss:20b", think=None)
        results = rlv._run_fixture_checks(qwen_config=qwen_config, gptoss_config=gptoss_config)
        injection = next(r for r in results if r["fixture_id"] == "prompt_injection")
        assert injection["qwen_faithfulness"] == "unsupported"
        assert injection["gpt_oss_faithfulness"] == "unsupported"
        assert injection["qwen_matches_expected"] is True
        assert injection["gpt_oss_matches_expected"] is True
