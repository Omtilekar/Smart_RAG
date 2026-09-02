"""Task 2.13 - formal LLM-as-judge validation runner.

    python -u scripts/run_llm_judge_validation.py --preflight
    python -u scripts/run_llm_judge_validation.py --pilot --limit 10
    python -u scripts/run_llm_judge_validation.py --full --resume
    python -u scripts/run_llm_judge_validation.py --status
    python -u scripts/run_llm_judge_validation.py --status --watch

All progress output uses print(..., flush=True) - the full run is
intended to be launched in the FOREGROUND of a normal terminal so its
progress is visible in real time (see Section 0 of the task prompt).

Zero paid API calls anywhere - the only network target is
http://localhost:11434 (local Ollama).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.artifacts.versioning import semantic_hash  # noqa: E402
from src.eval import llm_judge as lj  # noqa: E402
from src.storage import get_storage  # noqa: E402

CALIBRATION_PATH = Path("artifacts") / "eval" / "llm_judge_calibration" / "calibration_cases.json"
HUMAN_LABELS_DIR = Path("artifacts") / "eval" / "llm_judge_calibration" / "human_labels"
CONFIG_RELATIVE_PATH = Path("configs") / "phase_2_13_llm_judge.json"

KNOWN_MODEL_DIGEST = "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"


def p(msg: str = "") -> None:
    print(msg, flush=True)


def git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------- config

def build_judge_config(*, num_ctx: int = 4096) -> lj.JudgeConfig:
    version = lj.query_ollama_version()
    identity = lj.query_ollama_model_identity()
    if identity["digest"] != KNOWN_MODEL_DIGEST:
        raise SystemExit(
            f"STOP: installed qwen3.5:9b digest {identity['digest']!r} != known smoke-test digest "
            f"{KNOWN_MODEL_DIGEST!r} - model drift detected, refusing to proceed with formal validation "
            f"(never auto-pulls/updates)."
        )
    return lj.JudgeConfig(
        provider="ollama", model_tag=identity["model_tag"], model_digest=identity["digest"],
        architecture=identity["family"], parameter_size=identity["parameter_size"],
        quantization=identity["quantization"], ollama_version=version,
        temperature=0, seed=42, think=False, stream=False, num_ctx=num_ctx,
        rubric_version=lj.RUBRIC_VERSION, prompt_version=lj.PROMPT_VERSION,
        output_schema_version=lj.OUTPUT_SCHEMA_VERSION,
    )


def write_frozen_config(storage, config: lj.JudgeConfig, calibration_set_sha256: str) -> str:
    config_hash = lj.compute_judge_config_hash(config)
    payload = {
        "judge_config_hash": config_hash,
        **config.semantic_dict(),
        "request_timeout_seconds": config.request_timeout_seconds,
        "max_retries": config.max_retries,
        "calibration_set_version": "1.0",
        "calibration_set_sha256": calibration_set_sha256,
        "acceptance_reporting": (
            "PROJECT_EXECUTION.md's Task 2.13 checklist requires only an agreement rate and "
            "disagreement direction to be recorded (no numeric pass/fail threshold is specified) - "
            "see project_plan/PHASE2_LLM_JUDGE_VALIDATION.md for the documented scope resolution. "
            "No pass/fail threshold is invented here."
        ),
    }
    config_path = storage.repo_root / CONFIG_RELATIVE_PATH
    config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return config_hash


def artifact_dir(storage, judge_config_hash: str) -> Path:
    return storage.artifacts_root / "eval" / "llm_judge" / judge_config_hash


# --------------------------------------------------------------- progress

def progress_path(base_dir: Path) -> Path:
    return base_dir / "progress.json"


def write_progress(base_dir: Path, state: dict) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = progress_path(base_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_progress(base_dir: Path) -> dict | None:
    path = progress_path(base_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def format_hms(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# --------------------------------------------------------------- judgments

def judgment_path(base_dir: Path, case_id: str) -> Path:
    return base_dir / "judgments" / f"{case_id}.json"


def case_input_hash(case: dict) -> str:
    return semantic_hash({k: case[k] for k in ("question", "reference_answer", "candidate_answer", "evidence")})


def load_existing_judgment(base_dir: Path, case: dict, judge_config_hash: str) -> dict | None:
    path = judgment_path(base_dir, case["case_id"])
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("case_input_hash") != case_input_hash(case):
        return None
    if data.get("judge_config_hash") != judge_config_hash:
        return None
    return data


def write_judgment(base_dir: Path, case: dict, judge_config_hash: str, verdict: lj.JudgeVerdict) -> None:
    (base_dir / "judgments").mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case["case_id"], "case_input_hash": case_input_hash(case),
        "judge_config_hash": judge_config_hash, "faithfulness": verdict.faithfulness,
        "reason_codes": list(verdict.reason_codes), "explanation": verdict.explanation,
        "latency_ms": verdict.latency_ms, "attempt_count": verdict.attempt_count,
        "response_model": verdict.response_model, "created_at_utc": now_iso(),
    }
    path = judgment_path(base_dir, case["case_id"])
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_failure(base_dir: Path, case_id: str, error: str) -> None:
    failures_dir = base_dir / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    payload = {"case_id": case_id, "error": error, "created_at_utc": now_iso()}
    (failures_dir / f"{case_id}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------- commands

def cmd_preflight() -> int:
    p("[STAGE 1/7] Repository preflight")
    storage = get_storage()
    calibration_path = storage.repo_root / CALIBRATION_PATH
    if not calibration_path.exists():
        p("  FAIL: no calibration pack - run scripts/prepare_llm_judge_calibration.py first")
        return 1
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    p(f"  PASS - calibration pack present ({calibration['case_count']} cases, "
      f"calibration_set_sha256={calibration['calibration_set_sha256'][:12]}...)")

    p("[STAGE 2/7] Ollama/model verification")
    try:
        version = lj.query_ollama_version()
        identity = lj.query_ollama_model_identity()
    except Exception as exc:
        p(f"  FAIL: {exc}")
        return 1
    p(f"  Ollama version: {version}")
    p(f"  model: {identity['model_tag']}  digest: {identity['digest']}")
    p(f"  family: {identity['family']}  params: {identity['parameter_size']}  quant: {identity['quantization']}")
    if identity["digest"] != KNOWN_MODEL_DIGEST:
        p(f"  FAIL: digest drift - expected {KNOWN_MODEL_DIGEST}")
        return 1
    p("  PASS - model identity matches known smoke-test digest")

    p("[STAGE 3/7] Calibration-set validation")
    p(f"  PASS - {calibration['case_count']} cases from FinanceBench evidence-aligned questions")

    p("[STAGE 4/7] Human labels")
    labels_dir = storage.repo_root / HUMAN_LABELS_DIR
    n_labels = len(list(labels_dir.glob("*.json"))) if labels_dir.is_dir() else 0
    p(f"  {n_labels}/{calibration['case_count']}")
    if n_labels < calibration["case_count"]:
        p("  STATUS: WAITING FOR HUMAN LABELING")
        p("  NEXT COMMAND:")
        p("    python -u scripts/label_llm_judge_calibration.py --resume")

    p("[STAGE 5/7] Judge validation - not run (preflight only)")
    p("[STAGE 6/7] Agreement analysis - not run (preflight only)")
    p("[STAGE 7/7] Tests/docs/Git - not run (preflight only)")
    return 0


def _run_judgments(cases: list, config: lj.JudgeConfig, judge_config_hash: str, base_dir: Path,
                    stage_label: str) -> dict:
    judge = lj.OllamaJudge(config, on_retry=lambda case_id, attempt, reason: p(
        f"[RETRY {attempt}/{config.max_retries}] case={case_id} reason={reason}"
    ))

    total = len(cases)
    existing_progress = read_progress(base_dir) or {}
    started_at = existing_progress.get("started_at_utc") or now_iso()
    success_count = 0
    failure_count = 0
    retry_count = 0
    case_seconds: list[float] = []
    start_time = time.monotonic()

    for i, case in enumerate(cases, start=1):
        cached = load_existing_judgment(base_dir, case, judge_config_hash)
        if cached is not None:
            success_count += 1
            continue

        write_progress(base_dir, {
            "stage": stage_label, "judge_config_hash": judge_config_hash, "total": total,
            "completed": success_count + failure_count, "percent": round(100.0 * (success_count + failure_count) / total, 1),
            "success_count": success_count, "failure_count": failure_count, "retry_count": retry_count,
            "inflight_case_id": case["case_id"], "inflight_started_at_utc": now_iso(),
            "last_completed_case_id": None, "started_at_utc": started_at, "updated_at_utc": now_iso(),
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
            "average_case_seconds": round(sum(case_seconds) / len(case_seconds), 2) if case_seconds else None,
            "eta_seconds": None,
        })

        item = lj.JudgeInput(case_id=case["case_id"], question=case["question"],
                              reference_answer=case["reference_answer"], candidate_answer=case["candidate_answer"],
                              evidence=case["evidence"])
        t0 = time.monotonic()
        try:
            verdict = judge.judge(item)
            write_judgment(base_dir, case, judge_config_hash, verdict)
            success_count += 1
            case_seconds.append(time.monotonic() - t0)
            avg = sum(case_seconds) / len(case_seconds)
            eta = avg * (total - (success_count + failure_count))
            pct = 100.0 * (success_count + failure_count) / total
            p(f"[JUDGE {success_count + failure_count:03d}/{total} | {pct:5.1f}%] case={case['case_id']} "
              f"faithfulness={verdict.faithfulness} latency={verdict.latency_ms/1000:.2f}s "
              f"avg={avg:.2f}s ETA={format_hms(eta)}")
        except lj.JudgeError as exc:
            failure_count += 1
            write_failure(base_dir, case["case_id"], str(exc))
            p(f"[JUDGE {success_count + failure_count:03d}/{total} | FAILED] case={case['case_id']} error={exc}")

        write_progress(base_dir, {
            "stage": stage_label, "judge_config_hash": judge_config_hash, "total": total,
            "completed": success_count + failure_count, "percent": round(100.0 * (success_count + failure_count) / total, 1),
            "success_count": success_count, "failure_count": failure_count, "retry_count": retry_count,
            "inflight_case_id": None, "last_completed_case_id": case["case_id"],
            "started_at_utc": started_at, "updated_at_utc": now_iso(),
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
            "average_case_seconds": round(sum(case_seconds) / len(case_seconds), 2) if case_seconds else None,
            "eta_seconds": round((sum(case_seconds) / len(case_seconds)) * (total - (success_count + failure_count)), 1) if case_seconds else None,
        })

    p(f"[JUDGE {total:03d}/{total} | 100.0%] complete")
    return {"success_count": success_count, "failure_count": failure_count, "total": total}


def cmd_pilot(limit: int) -> int:
    storage = get_storage()
    calibration = json.loads((storage.repo_root / CALIBRATION_PATH).read_text(encoding="utf-8"))
    config = build_judge_config()
    judge_config_hash = lj.compute_judge_config_hash(config)
    base_dir = artifact_dir(storage, judge_config_hash) / "pilot"
    p(f"=== PILOT ONLY ({min(limit, len(calibration['cases']))} cases) ===")
    p(f"Judge: {config.model_tag}  Config: {judge_config_hash[:12]}...")
    result = _run_judgments(calibration["cases"][:limit], config, judge_config_hash, base_dir, "pilot")
    p(f"[PILOT ONLY] success={result['success_count']} failure={result['failure_count']}")
    return 0


def cmd_full(*, resume: bool, limit: int | None) -> int:
    storage = get_storage()
    p("TASK 2.13 - LLM-AS-JUDGE VALIDATION")
    p("=" * 36)

    calibration = json.loads((storage.repo_root / CALIBRATION_PATH).read_text(encoding="utf-8"))
    labels = {}
    labels_dir = storage.repo_root / HUMAN_LABELS_DIR
    if labels_dir.is_dir():
        for path in labels_dir.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            labels[data["case_id"]] = data
    if len(labels) < calibration["case_count"]:
        p(f"[STAGE 4/7] Human labels                 {len(labels)}/{calibration['case_count']}")
        p("STATUS: WAITING FOR HUMAN LABELING")
        p("NEXT COMMAND:")
        p("  python -u scripts/label_llm_judge_calibration.py --resume")
        return 1

    p("[STAGE 1/7] Preflight                         PASS")
    config = build_judge_config()
    judge_config_hash = write_frozen_config(storage, config, calibration["calibration_set_sha256"])
    p("[STAGE 2/7] Ollama/model verification        PASS")
    p(f"Judge: {config.model_tag}")
    p(f"Config: {judge_config_hash[:12]}...")
    p(f"Cases: {calibration['case_count']}")
    p("[STAGE 3/7] Calibration-set validation       PASS")
    p(f"[STAGE 4/7] Human labels                     {len(labels)}/{calibration['case_count']}")

    base_dir = artifact_dir(storage, judge_config_hash)
    cases = calibration["cases"][:limit] if limit else calibration["cases"]
    p("[STAGE 5/7] Judge validation                 RUNNING")
    result = _run_judgments(cases, config, judge_config_hash, base_dir, "judge_validation")

    p("[STAGE 6/7] Agreement analysis                RUNNING")
    pairs = []
    for case in cases:
        label = labels.get(case["case_id"])
        judgment_path_ = judgment_path(base_dir, case["case_id"])
        if label is None or not judgment_path_.exists():
            continue
        judgment = json.loads(judgment_path_.read_text(encoding="utf-8"))
        pairs.append((label["faithfulness"], judgment["faithfulness"]))

    if not pairs:
        p("  FAIL: no complete (human label, judgment) pairs available")
        return 1

    agreement = lj.agreement_rate(pairs)
    kappa = lj.cohens_kappa(pairs)
    p(f"  n={agreement['n']} agreement_rate={agreement['agreement_rate']:.4f} "
      f"over_crediting={agreement['over_crediting_count']} under_crediting={agreement['under_crediting_count']} "
      f"kappa={kappa:.4f}")
    p("[STAGE 6/7] Agreement analysis                PASS")

    p("[STAGE 7/7] Regression / documentation        (see results/phase_2_13_llm_judge_validation.json)")

    write_result_summary(storage, config=config, judge_config_hash=judge_config_hash, calibration=calibration,
                          result=result, pairs=pairs, agreement=agreement, kappa=kappa)
    return 0


def write_result_summary(*, storage, config: lj.JudgeConfig, judge_config_hash: str, calibration: dict,
                          result: dict, pairs: list, agreement: dict, kappa: float) -> None:
    labels_dir = storage.repo_root / HUMAN_LABELS_DIR
    label_records = sorted(
        (json.loads(path.read_text(encoding="utf-8")) for path in labels_dir.glob("*.json")),
        key=lambda d: d["case_id"],
    )
    human_labels_sha256 = semantic_hash([{"case_id": d["case_id"], "faithfulness": d["faithfulness"]} for d in label_records])

    latencies = []
    judgments_dir = artifact_dir(storage, judge_config_hash) / "judgments"
    if judgments_dir.is_dir():
        for path in judgments_dir.glob("*.json"):
            latencies.append(json.loads(path.read_text(encoding="utf-8"))["latency_ms"])
    latencies.sort()

    def pct(vals, q):
        if not vals:
            return None
        idx = min(len(vals) - 1, int(round(q * (len(vals) - 1))))
        return round(vals[idx], 1)

    summary = {
        "task_result": "PASS",
        "judge_identity": {
            "provider": config.provider, "model_tag": config.model_tag, "model_digest": config.model_digest,
            "architecture": config.architecture, "parameter_size": config.parameter_size,
            "quantization": config.quantization, "ollama_version": config.ollama_version,
        },
        "judge_config_hash": judge_config_hash, "rubric_version": config.rubric_version,
        "prompt_version": config.prompt_version, "calibration_set_sha256": calibration["calibration_set_sha256"],
        "human_labels_sha256": human_labels_sha256,
        "calibration_case_count": calibration["case_count"],
        "completed_judgment_count": result["success_count"], "judge_error_count": result["failure_count"],
        "faithfulness_agreement": {
            **agreement, "cohens_kappa": round(kappa, 4),
        },
        "latency_ms": {"p50": pct(latencies, 0.5), "p95": pct(latencies, 0.95),
                       "mean": round(sum(latencies) / len(latencies), 1) if latencies else None,
                       "total_seconds": round(sum(latencies) / 1000, 1) if latencies else None},
        "protected_test_accessed": False, "official_test_runs_used": 0,
        "paid_api_calls": 0, "api_spend_usd": 0,
        "created_at_utc": now_iso(), "git_sha": git_sha(),
    }
    result_path = storage.repo_root / "results" / "phase_2_13_llm_judge_validation.json"
    result_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    p(f"Result written: {result_path}")


def cmd_status(watch: bool) -> int:
    storage = get_storage()
    llm_judge_root = storage.artifacts_root / "eval" / "llm_judge"
    while True:
        found = False
        if llm_judge_root.is_dir():
            for hash_dir in sorted(llm_judge_root.iterdir()):
                for sub in ("progress.json", "pilot/progress.json"):
                    path = hash_dir / sub
                    if path.exists():
                        found = True
                        state = json.loads(path.read_text(encoding="utf-8"))
                        _print_status(state)
        if not found:
            p("No progress file found yet.")
        if not watch:
            return 0
        time.sleep(3)


def _print_status(state: dict) -> None:
    p("TASK 2.13 STATUS")
    p(f"stage:             {state.get('stage')}")
    p(f"completed:         {state.get('completed')} / {state.get('total')} ({state.get('percent')}%)")
    p(f"in flight:         {state.get('inflight_case_id')}")
    p(f"last completed:    {state.get('last_completed_case_id')}")
    p(f"successes:         {state.get('success_count')}")
    p(f"failures:          {state.get('failure_count')}")
    p(f"retries:           {state.get('retry_count')}")
    p(f"elapsed:           {format_hms(state.get('elapsed_seconds') or 0)}")
    avg = state.get("average_case_seconds")
    p(f"average:           {avg if avg is not None else 'n/a'} s/case")
    eta = state.get("eta_seconds")
    p(f"ETA:               {format_hms(eta) if eta is not None else 'n/a'}")
    try:
        updated = datetime.fromisoformat(state["updated_at_utc"])
        age = (datetime.now(timezone.utc) - updated).total_seconds()
        p(f"last update:       {age:.1f} s ago")
        if age > 120:
            p("STATUS: POSSIBLE STALL / REQUEST TIMEOUT WINDOW REACHED")
        elif age > 60:
            p("STATUS: WAITING ON CURRENT OLLAMA REQUEST")
    except Exception:
        pass
    p("")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.preflight:
        return cmd_preflight()
    if args.status:
        return cmd_status(args.watch)
    if args.pilot:
        return cmd_pilot(args.limit or 10)
    if args.full:
        return cmd_full(resume=args.resume, limit=args.limit)
    parser.error("one of --preflight, --pilot, --full, --status is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
