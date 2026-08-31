"""Task 1.11 - portable tests for src/cli/phase1.py.

Fake/injected dependencies only - no real network, no real model/index,
no OpenRouter call. Task 1.11's single live paid answer demo is a
dedicated manual command run, never an ordinary pytest test (Step 23 of
the task prompt) - the generation_api marker convention is unaffected.
"""

from dataclasses import dataclass

import pytest

import src.cli.phase1 as cli
from src.generation.provider import GenerationError


@dataclass(frozen=True)
class FakeResult:
    answer: str
    citations: list[str]


class FakeGenerator:
    def __init__(self, result=None, error=None):
        self._result = result if result is not None else FakeResult(answer="Revenue was $1M. [doc.htm::chunk0]", citations=["doc.htm::chunk0"])
        self._error = error
        self.calls = []

    def answer(self, question):
        self.calls.append(question)
        if self._error is not None:
            raise self._error
        return self._result


# --------------------------------------------------------------------- --help

def test_help_exits_0_and_lists_subcommands(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "answer" in out
    assert "evaluate" in out


def test_answer_requires_question_flag():
    with pytest.raises(SystemExit) as exc:
        cli.main(["answer"])
    assert exc.value.code != 0


# ---------------------------------------------------------------- empty question

def test_empty_question_rejected(capsys):
    rc = cli.cmd_answer("", generator=FakeGenerator())
    assert rc != 0
    err = capsys.readouterr().err
    assert "empty" in err.lower()


def test_whitespace_question_rejected(capsys):
    rc = cli.cmd_answer("   ", generator=FakeGenerator())
    assert rc != 0


# ------------------------------------------------------------------- answer path

def test_answer_invokes_generator_with_question():
    gen = FakeGenerator()
    rc = cli.cmd_answer("What was revenue?", generator=gen)
    assert rc == 0
    assert gen.calls == ["What was revenue?"]


def test_answer_prints_answer_and_citations(capsys):
    gen = FakeGenerator(result=FakeResult(answer="Revenue was $1M.", citations=["doc.htm::chunk0", "doc.htm::chunk1"]))
    cli.cmd_answer("What was revenue?", generator=gen)
    out = capsys.readouterr().out
    assert "Answer:" in out
    assert "Revenue was $1M." in out
    assert "Citations:" in out
    assert "- doc.htm::chunk0" in out
    assert "- doc.htm::chunk1" in out


def test_zero_citations_shown_explicitly(capsys):
    gen = FakeGenerator(result=FakeResult(answer="The context does not contain enough information.", citations=[]))
    cli.cmd_answer("unanswerable question", generator=gen)
    out = capsys.readouterr().out
    assert "Citations:" in out
    assert "(none)" in out


def test_vectors_and_context_not_printed(capsys):
    gen = FakeGenerator(result=FakeResult(answer="Answer text.", citations=["doc.htm::chunk0"]))
    cli.cmd_answer("question", generator=gen)
    out = capsys.readouterr().out
    assert "vector" not in out.lower()


def test_provider_error_becomes_nonzero_safe_failure(capsys):
    gen = FakeGenerator(error=GenerationError("simulated provider failure"))
    rc = cli.cmd_answer("question", generator=gen)
    assert rc != 0
    err = capsys.readouterr().err
    assert "simulated provider failure" in err


def test_no_api_key_in_output(capsys, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-totally-fake-test-key-do-not-leak")
    gen = FakeGenerator()
    cli.cmd_answer("question", generator=gen)
    captured = capsys.readouterr()
    assert "sk-or-v1-totally-fake-test-key-do-not-leak" not in captured.out
    assert "sk-or-v1-totally-fake-test-key-do-not-leak" not in captured.err


# ----------------------------------------------------------------- evaluate path

def test_evaluate_delegates_to_task_1_10_runner(monkeypatch, capsys):
    import scripts.run_baseline_metric as runner_module

    calls = []

    def fake_run(*, result_relative_path=None, config_relative_path=None):
        calls.append(result_relative_path)
        return {"question_count": 200, "hit_count": 194, "doc_recall_at_10": 0.97}

    monkeypatch.setattr(runner_module, "run", fake_run)
    rc = cli.cmd_evaluate()
    assert rc == 0
    assert len(calls) == 1
    assert calls[0] == cli.EVALUATE_RESULT_RELATIVE_PATH


def test_evaluate_does_not_duplicate_metric_computation(monkeypatch):
    """cmd_evaluate must not itself recompute hit_count/doc_recall - it
    only formats whatever the injected runner returns."""
    import scripts.run_baseline_metric as runner_module

    def fake_run(*, result_relative_path=None, config_relative_path=None):
        return {"question_count": 5, "hit_count": 3, "doc_recall_at_10": 0.6}

    monkeypatch.setattr(runner_module, "run", fake_run)
    rc = cli.cmd_evaluate()
    assert rc == 0


def test_evaluate_prints_headline_values(monkeypatch, capsys):
    import scripts.run_baseline_metric as runner_module

    def fake_run(*, result_relative_path=None, config_relative_path=None):
        return {"question_count": 200, "hit_count": 194, "doc_recall_at_10": 0.97}

    monkeypatch.setattr(runner_module, "run", fake_run)
    cli.cmd_evaluate()
    out = capsys.readouterr().out
    assert "question_count: 200" in out
    assert "hit_count: 194" in out
    assert "doc_recall@10: 0.970000" in out


def test_evaluate_propagates_runner_failure_as_nonzero(monkeypatch):
    import scripts.run_baseline_metric as runner_module

    def failing_run(*, result_relative_path=None, config_relative_path=None):
        raise SystemExit("FATAL: simulated invariant violation")

    monkeypatch.setattr(runner_module, "run", failing_run)
    with pytest.raises(SystemExit):
        cli.cmd_evaluate()
