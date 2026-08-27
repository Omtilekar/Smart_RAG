"""Tests for scripts/dev.py, the developer command interface. Runs the
script as a real subprocess (matching how a developer actually invokes
it), but never launches `test`/`smoke` recursively - that would start a
second, nested pytest run of this same suite."""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_SCRIPT = REPO_ROOT / "scripts" / "dev.py"


def _run(args, env=None):
    return subprocess.run(
        [sys.executable, str(DEV_SCRIPT), *args],
        cwd=REPO_ROOT, capture_output=True, text=True, env=env,
    )


def test_help_returns_zero_and_lists_commands():
    result = _run(["--help"])
    assert result.returncode == 0
    for name in ("doctor", "test", "data", "gpu", "smoke"):
        assert name in result.stdout


def test_doctor_passes_in_valid_venv():
    result = _run(["doctor"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Required foundation" in result.stdout


def test_data_command_fails_clearly_on_missing_storage_root(tmp_path):
    empty_root = tmp_path / "empty_data_root"
    env = dict(os.environ)
    env["STORAGE_ROOT"] = str(empty_root)

    result = _run(["data"], env=env)

    assert result.returncode != 0
    assert "MISSING" in result.stdout
    assert not empty_root.exists(), "data command must never create the missing path"
