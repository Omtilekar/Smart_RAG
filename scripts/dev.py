#!/usr/bin/env python
"""Developer command interface for Phase 0 foundation checks.

    python scripts/dev.py doctor
    python scripts/dev.py test [--portable]
    python scripts/dev.py data
    python scripts/dev.py gpu
    python scripts/dev.py smoke

Thin wrappers around already-implemented, already-tested project behavior
(src.config, src.storage, pytest, torch) - not a second implementation of
any of them, and not a general task runner. See
project_plan/DEVELOPER_COMMANDS.md.

Repository root is resolved from this script's own location, not the
current working directory, so it works when invoked from anywhere.
Subprocesses always use sys.executable, so this always runs against the
same interpreter (and therefore the same .venv) the script itself was
launched with.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PORTABLE_MARKER_EXPR = "not local_data and not gpu and not model and not generation_api"
SMOKE_MARKER_EXPR = "local_data or gpu or model"
# generation_api (Task 1.7) is deliberately excluded from both expressions
# above - it makes a real, credentialed OpenRouter network call and must
# never run merely because a developer's local .env happens to have
# OPENROUTER_API_KEY/GENERATION_MODEL set. It only runs via the full
# `dev.py test` (no filter) or by name (`pytest -m generation_api`), and
# is the dedicated scripts/smoke_generation.py script's job to exercise
# deliberately.

CORE_PACKAGES = [
    "requests", "duckdb", "pyarrow", "bs4", "lxml",
    "sentence_transformers", "lancedb", "fastapi", "torch", "pytest",
]


def _run_pytest(extra_args: list[str]) -> int:
    cmd = [sys.executable, "-m", "pytest", *extra_args]
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode


def cmd_test(args: argparse.Namespace) -> int:
    if args.portable:
        return _run_pytest(["-m", PORTABLE_MARKER_EXPR])
    return _run_pytest([])


def cmd_smoke(args: argparse.Namespace) -> int:
    return _run_pytest(["-m", SMOKE_MARKER_EXPR])


def cmd_doctor(args: argparse.Namespace) -> int:
    """Read-only, offline environment/setup health check. Local data and
    CUDA are reported as informational only - a public clone without either
    must still be able to pass the required-foundation portion."""
    import importlib

    ok = True
    print("Required foundation")

    version_file = REPO_ROOT / ".python-version"
    running = f"{sys.version_info.major}.{sys.version_info.minor}"
    if version_file.is_file():
        expected = version_file.read_text().strip()
        match = running == expected
        print(f"  Python.............. {'PASS' if match else 'FAIL'} "
              f"{sys.version.split()[0]} (expected {expected}.x)")
        if not match:
            ok = False
    else:
        print(f"  Python.............. WARN {sys.version.split()[0]} (.python-version not found)")

    in_venv = sys.prefix != sys.base_prefix
    print(f"  Virtual env......... {'PASS' if in_venv else 'FAIL'}")
    if not in_venv:
        ok = False
        print("    Not running inside a virtual environment.")
        print("    See project_plan/ENVIRONMENT.md to create/activate .venv.")

    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    pip_ok = pip_check.returncode == 0
    print(f"  pip check........... {'PASS' if pip_ok else 'FAIL'}")
    if not pip_ok:
        ok = False
        print(f"    {pip_check.stdout.strip()}")

    missing = []
    for pkg in CORE_PACKAGES:
        try:
            importlib.import_module(pkg)
        except Exception as e:  # noqa: BLE001 - report any import failure, don't crash doctor
            missing.append(f"{pkg} ({type(e).__name__})")
    print(f"  Core imports........ {'PASS' if not missing else 'FAIL'}")
    if missing:
        ok = False
        print(f"    Missing/broken: {', '.join(missing)}")

    try:
        from src.config import get_settings
        settings = get_settings()
        print(f"  config.............. PASS (app_env={settings.app_env}, log_level={settings.log_level})")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"  config.............. FAIL ({type(e).__name__}: {e})")

    try:
        from src.storage import get_storage
        get_storage()
        print("  storage............. PASS (repo root detected, paths resolve)")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"  storage............. FAIL ({type(e).__name__}: {e})")

    print()
    print("Optional capabilities (informational only - absence is not a doctor failure)")
    try:
        from src.storage import get_storage
        storage = get_storage()
        data_present = storage.xbrl_db.is_file() and storage.msmarco_root.is_dir()
        print(f"  Local data.......... {'AVAILABLE' if data_present else 'NOT AVAILABLE'}")
    except Exception:  # noqa: BLE001
        print("  Local data.......... NOT AVAILABLE")

    try:
        import torch
        print(f"  CUDA................ {'AVAILABLE' if torch.cuda.is_available() else 'NOT AVAILABLE'}")
    except Exception:  # noqa: BLE001
        print("  CUDA................ NOT AVAILABLE")

    return 0 if ok else 1


def cmd_data(args: argparse.Namespace) -> int:
    """Frozen data-path availability check via src.storage - no scanning,
    no counting, no downloading. Missing required input is a failure,
    because the command was invoked explicitly."""
    from src.storage import get_storage

    storage = get_storage()
    checks = [
        ("MS MARCO root", storage.msmarco_root, "dir"),
        ("EDGAR-CORPUS root", storage.edgar_corpus_root, "dir"),
        ("Raw XBRL root", storage.raw_xbrl_root, "dir"),
        ("Primary filings root", storage.primary_docs_root, "dir"),
        ("XBRL DuckDB", storage.xbrl_db, "file"),
    ]

    print("Frozen data paths")
    ok = True
    for label, path, kind in checks:
        exists = path.is_dir() if kind == "dir" else path.is_file()
        try:
            shown = path.relative_to(storage.repo_root)
        except ValueError:
            shown = path
        extra = ""
        if exists and kind == "file":
            extra = f" ({path.stat().st_size / 1e9:.2f} GB)"
        status = "PASS" if exists else "MISSING"
        if not exists:
            ok = False
        print(f"  {label:.<22} {status} {shown}{extra}")

    if not ok:
        print()
        print("Some frozen data is missing. This command never downloads data -")
        print("see DATA_READINESS_REPORT.md for how it was originally acquired.")
    return 0 if ok else 1


def cmd_gpu(args: argparse.Namespace) -> int:
    """Explicit PyTorch/CUDA check. Unlike the portable test suite (where a
    machine without CUDA legitimately skips), this command was invoked
    explicitly to check GPU health, so missing or broken CUDA is a failure,
    not a skip. Does not load the embedding model - use `smoke` for that."""
    import torch

    print("GPU / CUDA")
    print(f"  torch version....... {torch.__version__}")
    print(f"  torch.version.cuda.. {torch.version.cuda}")

    available = torch.cuda.is_available()
    print(f"  CUDA available...... {'YES' if available else 'NO'}")
    if not available:
        print("  No CUDA-capable GPU detected on this machine.")
        return 1

    name = torch.cuda.get_device_name(0)
    major, minor = torch.cuda.get_device_capability(0)
    print(f"  GPU name............ {name}")
    print(f"  Compute capability.. {major}.{minor}")

    try:
        a = torch.randn(512, 512, device="cuda")
        b = torch.randn(512, 512, device="cuda")
        c = a @ b
        torch.cuda.synchronize()
        finite = torch.isfinite(c).all().item()
    except Exception as e:  # noqa: BLE001
        print(f"  CUDA kernel......... FAIL ({type(e).__name__}: {e})")
        return 1

    if not finite:
        print("  CUDA kernel......... FAIL (non-finite result)")
        return 1

    print("  CUDA kernel......... PASS (512x512 matmul, finite result)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev.py",
        description="Phase 0 developer command interface - thin wrappers around "
        "src.config / src.storage / pytest / torch. See project_plan/DEVELOPER_COMMANDS.md.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="environment/setup health check (read-only, offline)")

    test_parser = sub.add_parser("test", help="run the pytest suite")
    test_parser.add_argument(
        "--portable", action="store_true",
        help="run only the portable subset (excludes local_data/gpu/model)",
    )

    sub.add_parser("data", help="check canonical frozen data paths (no download, no scan)")
    sub.add_parser("gpu", help="verify PyTorch CUDA and run a real GPU kernel")
    sub.add_parser("smoke", help="run local-capability smoke tests (local_data/gpu/model)")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "doctor": cmd_doctor,
        "test": cmd_test,
        "data": cmd_data,
        "gpu": cmd_gpu,
        "smoke": cmd_smoke,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
