"""Regression test for a real crash found during Task 3.3: torch 2.13
raises CUDA out-of-memory through `torch.AcceleratorError` for some code
paths - a RuntimeError subclass that is a SIBLING of
`torch.cuda.OutOfMemoryError` (both derive directly from RuntimeError),
not a parent/child of it. `except torch.cuda.OutOfMemoryError:` alone
never matches an AcceleratorError instance, so a real OOM propagated as
an uncaught traceback and killed a live multi-hour embedding build.
Portable - no GPU/model/network."""

from __future__ import annotations

import torch

from scripts.run_phase3_embedding_benchmark import _is_oom_error


def test_detects_real_accelerator_error_oom():
    try:
        raise torch.AcceleratorError("CUDA error: out of memory")
    except Exception as exc:  # noqa: BLE001
        assert _is_oom_error(exc) is True


def test_detects_legacy_cuda_out_of_memory_error():
    try:
        raise torch.cuda.OutOfMemoryError("CUDA out of memory")
    except Exception as exc:  # noqa: BLE001
        assert _is_oom_error(exc) is True


def test_does_not_flag_unrelated_runtime_error():
    try:
        raise RuntimeError("some unrelated CUDA error")
    except Exception as exc:  # noqa: BLE001
        assert _is_oom_error(exc) is False


def test_detects_oom_via_message_text_fallback():
    # Guards against a future torch version using yet another exception
    # class for the same condition - the message-text fallback must still
    # catch it.
    class SomeFutureOomError(RuntimeError):
        pass

    try:
        raise SomeFutureOomError("device ran Out Of Memory while allocating")
    except Exception as exc:  # noqa: BLE001
        assert _is_oom_error(exc) is True


def test_torch_out_of_memory_error_and_accelerator_error_are_siblings():
    # Documents the actual torch 2.13 hierarchy this bug depends on: both
    # derive directly from RuntimeError, neither is a subclass of the
    # other - which is exactly why a single `except <one-of-them>:` clause
    # misses the other, and why _is_oom_error checks both explicitly.
    assert not issubclass(torch.cuda.OutOfMemoryError, torch.AcceleratorError)
    assert not issubclass(torch.AcceleratorError, torch.cuda.OutOfMemoryError)
    assert issubclass(torch.cuda.OutOfMemoryError, RuntimeError)
    assert issubclass(torch.AcceleratorError, RuntimeError)
