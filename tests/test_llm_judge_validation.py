"""Task 2.13 - portable tests for scripts/run_llm_judge_validation.py's
progress/resume/checkpoint logic. No Ollama, no GPU, no network."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "run_llm_judge_validation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_llm_judge_validation", MODULE_PATH)
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


# --------------------------------------------------------------- format_hms

class TestFormatHms:
    def test_zero(self, rlv):
        assert rlv.format_hms(0) == "00:00:00"

    def test_minutes_seconds(self, rlv):
        assert rlv.format_hms(125) == "00:02:05"

    def test_hours(self, rlv):
        assert rlv.format_hms(3661) == "01:01:01"

    def test_negative_clamped_to_zero(self, rlv):
        assert rlv.format_hms(-5) == "00:00:00"


# --------------------------------------------------------------- case_input_hash

class TestCaseInputHash:
    def test_deterministic(self, rlv):
        case = make_case()
        assert rlv.case_input_hash(case) == rlv.case_input_hash(dict(case))

    def test_changes_with_question(self, rlv):
        a = rlv.case_input_hash(make_case(question="Q1"))
        b = rlv.case_input_hash(make_case(question="Q2"))
        assert a != b

    def test_changes_with_candidate_answer(self, rlv):
        a = rlv.case_input_hash(make_case(candidate_answer="C1"))
        b = rlv.case_input_hash(make_case(candidate_answer="C2"))
        assert a != b

    def test_ignores_case_id(self, rlv):
        # Same semantic content under a different case_id must still hash
        # identically - case_id is an identifier, not semantic content.
        a = rlv.case_input_hash(make_case(case_id="c1"))
        b = rlv.case_input_hash(make_case(case_id="c2"))
        assert a == b


# --------------------------------------------------------------- progress persistence

class TestProgressPersistence:
    def test_write_read_round_trip(self, rlv, tmp_path):
        state = {"stage": "judge_validation", "total": 10, "completed": 3}
        rlv.write_progress(tmp_path, state)
        loaded = rlv.read_progress(tmp_path)
        assert loaded == state

    def test_read_missing_returns_none(self, rlv, tmp_path):
        assert rlv.read_progress(tmp_path / "does_not_exist") is None

    def test_write_is_atomic_no_leftover_tmp(self, rlv, tmp_path):
        rlv.write_progress(tmp_path, {"a": 1})
        assert not (tmp_path / "progress.json.tmp").exists()
        assert (tmp_path / "progress.json").exists()

    def test_overwrite_replaces_content(self, rlv, tmp_path):
        rlv.write_progress(tmp_path, {"completed": 1})
        rlv.write_progress(tmp_path, {"completed": 2})
        assert rlv.read_progress(tmp_path)["completed"] == 2


# --------------------------------------------------------------- judgment persistence / resume

class TestJudgmentPersistenceAndResume:
    def test_write_then_load_matches(self, rlv, tmp_path):
        import src.eval.llm_judge as lj
        case = make_case()
        verdict = lj.JudgeVerdict(faithfulness="supported", reason_codes=("fully_supported",),
                                   explanation="ok", latency_ms=100.0, attempt_count=1, response_model="qwen3.5:9b")
        rlv.write_judgment(tmp_path, case, "hash123", verdict)
        loaded = rlv.load_existing_judgment(tmp_path, case, "hash123")
        assert loaded is not None
        assert loaded["faithfulness"] == "supported"

    def test_stale_judgment_rejected_on_case_content_change(self, rlv, tmp_path):
        import src.eval.llm_judge as lj
        case = make_case(question="original question")
        verdict = lj.JudgeVerdict(faithfulness="supported", reason_codes=(), explanation="ok",
                                   latency_ms=1.0, attempt_count=1, response_model=None)
        rlv.write_judgment(tmp_path, case, "hash123", verdict)

        changed_case = make_case(question="a materially different question")
        assert rlv.load_existing_judgment(tmp_path, changed_case, "hash123") is None

    def test_stale_judgment_rejected_on_config_hash_change(self, rlv, tmp_path):
        import src.eval.llm_judge as lj
        case = make_case()
        verdict = lj.JudgeVerdict(faithfulness="supported", reason_codes=(), explanation="ok",
                                   latency_ms=1.0, attempt_count=1, response_model=None)
        rlv.write_judgment(tmp_path, case, "hash123", verdict)
        assert rlv.load_existing_judgment(tmp_path, case, "different_hash") is None

    def test_interrupted_run_recovery_first_n_not_recalled(self, rlv, tmp_path, monkeypatch):
        """Simulates completing the first 5 of 10 cases, then resuming -
        the first 5 must not be re-judged, and totals must be correct."""
        import src.eval.llm_judge as lj

        cases = [make_case(case_id=f"c{i}") for i in range(10)]
        config_hash = "fixedhash"

        call_log = []

        class _StubJudge:
            def __init__(self, config, on_retry=None):
                pass

            def judge(self, item):
                call_log.append(item.case_id)
                return lj.JudgeVerdict(faithfulness="supported", reason_codes=(), explanation="ok",
                                        latency_ms=1.0, attempt_count=1, response_model=None)

        monkeypatch.setattr(rlv.lj, "OllamaJudge", _StubJudge)

        # Pre-populate the first 5 as already-judged (simulating a completed partial run).
        for case in cases[:5]:
            verdict = lj.JudgeVerdict(faithfulness="supported", reason_codes=(), explanation="ok",
                                       latency_ms=1.0, attempt_count=1, response_model=None)
            rlv.write_judgment(tmp_path, case, config_hash, verdict)

        config = None  # unused by the stub judge
        result = rlv._run_judgments(cases, config, config_hash, tmp_path, "judge_validation")

        assert call_log == [f"c{i}" for i in range(5, 10)]
        assert result["success_count"] == 10
        assert result["failure_count"] == 0

    def test_no_duplicate_judgment_files(self, rlv, tmp_path, monkeypatch):
        import src.eval.llm_judge as lj

        cases = [make_case(case_id="only")]
        config_hash = "h"

        class _StubJudge:
            def __init__(self, config, on_retry=None):
                pass

            def judge(self, item):
                return lj.JudgeVerdict(faithfulness="supported", reason_codes=(), explanation="ok",
                                        latency_ms=1.0, attempt_count=1, response_model=None)

        monkeypatch.setattr(rlv.lj, "OllamaJudge", _StubJudge)
        rlv._run_judgments(cases, None, config_hash, tmp_path, "judge_validation")
        rlv._run_judgments(cases, None, config_hash, tmp_path, "judge_validation")
        assert len(list((tmp_path / "judgments").glob("*.json"))) == 1

    def test_judge_execution_error_recorded_as_failure_not_score(self, rlv, tmp_path, monkeypatch):
        import src.eval.llm_judge as lj

        cases = [make_case(case_id="bad")]

        class _StubJudge:
            def __init__(self, config, on_retry=None):
                pass

            def judge(self, item):
                raise lj.JudgeTransportError("simulated failure")

        monkeypatch.setattr(rlv.lj, "OllamaJudge", _StubJudge)
        result = rlv._run_judgments(cases, None, "h", tmp_path, "judge_validation")
        assert result["failure_count"] == 1
        assert result["success_count"] == 0
        failure_files = list((tmp_path / "failures").glob("*.json"))
        assert len(failure_files) == 1


# --------------------------------------------------------------- human label loading

LABEL_MODULE_PATH = REPO_ROOT / "scripts" / "label_llm_judge_calibration.py"


def _load_label_module():
    spec = importlib.util.spec_from_file_location("label_llm_judge_calibration", LABEL_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lbl():
    return _load_label_module()


class _FakeStorage:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root


def _write_calibration(lbl, storage, cases):
    path = storage.repo_root / lbl.CALIBRATION_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"case_count": len(cases), "cases": cases}), encoding="utf-8")


def _min_case(case_id):
    return {"case_id": case_id, "question": "Q", "reference_answer": "R",
            "candidate_answer": "C", "evidence": "E"}


class TestWriteLabelRejectsInvalidFaithfulness:
    @pytest.mark.parametrize("bad_value", ["maybe", "SUPPORTED", "", None, 4, True])
    def test_non_enum_faithfulness_rejected(self, lbl, tmp_path, bad_value):
        storage = _FakeStorage(tmp_path)
        with pytest.raises(ValueError):
            lbl.write_label(storage, "case1", bad_value, "")


class TestHumanLabelLoading:
    def test_write_then_load_round_trip(self, lbl, tmp_path):
        storage = _FakeStorage(tmp_path)
        lbl.write_label(storage, "case1", "supported", "looks fine")
        labels = lbl.load_existing_labels(storage)
        assert labels["case1"]["faithfulness"] == "supported"
        assert labels["case1"]["reviewer"] == lbl.REVIEWER_LABEL

    def test_missing_directory_returns_empty(self, lbl, tmp_path):
        storage = _FakeStorage(tmp_path)
        assert lbl.load_existing_labels(storage) == {}

    def test_multiple_labels_all_loaded(self, lbl, tmp_path):
        storage = _FakeStorage(tmp_path)
        lbl.write_label(storage, "a", "supported", "")
        lbl.write_label(storage, "b", "unsupported", "")
        labels = lbl.load_existing_labels(storage)
        assert set(labels.keys()) == {"a", "b"}

    def test_label_write_is_atomic_no_leftover_tmp(self, lbl, tmp_path):
        storage = _FakeStorage(tmp_path)
        lbl.write_label(storage, "case1", "supported", "")
        target_dir = tmp_path / lbl.HUMAN_LABELS_DIR
        assert not any(p.suffix == ".tmp" for p in target_dir.glob("*"))

    def test_dual_ordinal_remnant_label_file_rejected_loudly(self, lbl, tmp_path):
        """A label file from the reverted dual-ordinal (correctness+
        faithfulness 0-4) design must never be silently treated as valid
        or converted - it must be quarantined by a human before labeling
        can continue under the authoritative binary schema."""
        storage = _FakeStorage(tmp_path)
        labels_dir = tmp_path / lbl.HUMAN_LABELS_DIR
        labels_dir.mkdir(parents=True)
        (labels_dir / "case1.json").write_text(
            json.dumps({"case_id": "case1", "correctness": 4, "faithfulness": 3,
                        "derived_verdict": "pass", "reviewer": "reviewer_1"}),
            encoding="utf-8",
        )
        with pytest.raises(SystemExit):
            lbl.load_existing_labels(storage)

    def test_unrelated_malformed_label_file_rejected_loudly(self, lbl, tmp_path):
        storage = _FakeStorage(tmp_path)
        labels_dir = tmp_path / lbl.HUMAN_LABELS_DIR
        labels_dir.mkdir(parents=True)
        (labels_dir / "case1.json").write_text(
            json.dumps({"case_id": "case1", "faithfulness": "maybe", "reviewer": "reviewer_1"}),
            encoding="utf-8",
        )
        with pytest.raises(SystemExit):
            lbl.load_existing_labels(storage)


class TestInteractiveLabelingSingleBinaryDimension:
    def test_quit_saves_nothing(self, lbl, tmp_path, monkeypatch):
        storage = _FakeStorage(tmp_path)
        _write_calibration(lbl, storage, [_min_case("c1")])
        inputs = iter(["q"])
        monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
        lbl.run_labeling(storage)
        assert lbl.load_existing_labels(storage) == {}

    def test_skip_saves_nothing_and_advances(self, lbl, tmp_path, monkeypatch):
        storage = _FakeStorage(tmp_path)
        _write_calibration(lbl, storage, [_min_case("c1"), _min_case("c2")])
        inputs = iter(["s", "supported", ""])
        monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
        lbl.run_labeling(storage)
        labels = lbl.load_existing_labels(storage)
        assert "c1" not in labels
        assert labels["c2"]["faithfulness"] == "supported"

    def test_invalid_input_reprompts_until_valid(self, lbl, tmp_path, monkeypatch):
        storage = _FakeStorage(tmp_path)
        _write_calibration(lbl, storage, [_min_case("c1")])
        inputs = iter(["maybe", "4", "unsupported", ""])
        monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
        lbl.run_labeling(storage)
        labels = lbl.load_existing_labels(storage)
        assert labels["c1"]["faithfulness"] == "unsupported"

    def test_full_session_two_cases_labeled(self, lbl, tmp_path, monkeypatch):
        storage = _FakeStorage(tmp_path)
        _write_calibration(lbl, storage, [_min_case("c1"), _min_case("c2")])
        inputs = iter(["supported", "", "unsupported", "note here"])
        monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
        lbl.run_labeling(storage)
        labels = lbl.load_existing_labels(storage)
        assert len(labels) == 2
        assert labels["c1"]["faithfulness"] == "supported"
        assert labels["c2"]["faithfulness"] == "unsupported"
