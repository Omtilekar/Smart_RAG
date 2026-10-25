"""Offline smoke/audit for Task 4.14 retrieval security.

Uses synthetic fixtures only. No model loading, no LanceDB, no generation
provider, no network, no AWS, and no protected TEST access.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.security.evaluation import evaluate_security_fixture  # noqa: E402
from src.security.retrieval_guard import RetrievalSecurityGuard  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "rag_poisoning"
RESULT_PATH = REPO_ROOT / "results" / "phase_4_14_retrieval_security_smoke.json"


def _load_cases() -> list[dict]:
    cases: list[dict] = []
    for path in sorted(FIXTURE_DIR.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cases.append(json.loads(line))
    return cases


def _candidate(i: int, text: str):
    return SimpleNamespace(
        rank=i + 1,
        score=0.9 - i * 0.01,
        distance=0.1 + i * 0.01,
        chunk_id=f"smoke.htm::chunk{i}",
        document_id="smoke.htm",
        text=text,
        cik=1000,
        company="SMOKE CO",
        form_type="10-K",
        fiscal_year=2020,
        source="edgar_corpus",
        source_filename="smoke.htm",
        source_split="synthetic",
        ordinal=i,
        token_count=12,
        chunk_config_hash="smoke-hash",
        normalizer_version="security-smoke-v1",
        normalization_build_sha256="x" * 64,
        development_manifest_sha256="y" * 64,
    )


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return ordered[index]


def _measure_latency(iterations: int = 500) -> dict[str, float | int]:
    candidates = [
        _candidate(0, "Revenue was $1M."),
        _candidate(1, "Operating income increased year over year."),
        _candidate(2, "The cybersecurity policy discussed audit instructions as ordinary governance text."),
        _candidate(3, "Cash and equivalents were reported in the balance sheet."),
        _candidate(4, "Net sales reflected higher demand in the period."),
    ]
    guard = RetrievalSecurityGuard()
    baseline_ms: list[float] = []
    guarded_ms: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        list(candidates)
        baseline_ms.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        guard.filter(query="synthetic smoke query", candidates=candidates)
        guarded_ms.append((time.perf_counter() - start) * 1000)

    return {
        "iterations": iterations,
        "baseline_copy_p50_ms": round(statistics.median(baseline_ms), 6),
        "baseline_copy_p95_ms": round(_percentile(baseline_ms, 0.95), 6),
        "guarded_p50_ms": round(statistics.median(guarded_ms), 6),
        "guarded_p95_ms": round(_percentile(guarded_ms, 0.95), 6),
        "overhead_p50_ms": round(statistics.median(guarded_ms) - statistics.median(baseline_ms), 6),
        "overhead_p95_ms": round(_percentile(guarded_ms, 0.95) - _percentile(baseline_ms, 0.95), 6),
    }


def main() -> int:
    cases = _load_cases()
    guard = RetrievalSecurityGuard()
    metrics = evaluate_security_fixture(cases, guard=guard)
    latency = _measure_latency()
    thresholds_passed = (
        metrics.high_confidence_poison_blocked_rate == 1.0
        and metrics.malicious_context_acceptance_rate == 0.0
        and metrics.missing_provenance_blocked_rate == 1.0
        and metrics.clean_candidate_retention_rate == 1.0
        and metrics.false_positive_rate == 0.0
    )
    payload = {
        "task": "4.14",
        "status": "PASS" if thresholds_passed else "FAIL",
        "protected_test_runs_used": "0/3",
        "fixtures": {
            "directory": str(FIXTURE_DIR.relative_to(REPO_ROOT)),
            "cases": len(cases),
        },
        "metrics": asdict(metrics),
        "latency": latency,
        "telemetry_after_fixture_eval": guard.status_snapshot()["telemetry"],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{payload['status']} wrote {RESULT_PATH}")
    return 0 if thresholds_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
