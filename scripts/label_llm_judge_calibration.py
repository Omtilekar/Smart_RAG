"""Task 2.13 - blinded human labeling CLI for the LLM-judge calibration
pack.

The human reviewer sees ONLY: case ID, question, reference answer,
candidate answer, evidence, and the rubric. Never shown: the
perturbation type, which case is a "reference" vs "degraded" variant, or
any judge output (the judge has not even been run against these labels
yet - Section 46's required sequence: freeze judge config -> build pack
-> human labels -> THEN run the judge).

Every accepted label is written to its own file immediately (atomic,
one file per case) - a reviewer can label 20 cases, quit, and resume
tomorrow at case 21 without losing work.

Usage:
    python -u scripts/label_llm_judge_calibration.py --start
    python -u scripts/label_llm_judge_calibration.py --resume
    python -u scripts/label_llm_judge_calibration.py --status
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.eval.llm_judge import FAITHFULNESS_LABELS  # noqa: E402
from src.storage import get_storage  # noqa: E402

CALIBRATION_PATH = Path("artifacts") / "eval" / "llm_judge_calibration" / "calibration_cases.json"
HUMAN_LABELS_DIR = Path("artifacts") / "eval" / "llm_judge_calibration" / "human_labels"
REVIEWER_LABEL = "reviewer_1"


def load_calibration(storage) -> dict:
    path = storage.repo_root / CALIBRATION_PATH
    if not path.exists():
        raise SystemExit("STOP: no calibration pack found - run scripts/prepare_llm_judge_calibration.py first")
    return json.loads(path.read_text(encoding="utf-8"))


def label_path(storage, case_id: str) -> Path:
    return storage.repo_root / HUMAN_LABELS_DIR / f"{case_id}.json"


def load_existing_labels(storage) -> dict:
    labels_dir = storage.repo_root / HUMAN_LABELS_DIR
    labels = {}
    if labels_dir.is_dir():
        for path in sorted(labels_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            labels[data["case_id"]] = data
    return labels


def write_label(storage, case_id: str, faithfulness: str, note: str) -> None:
    labels_dir = storage.repo_root / HUMAN_LABELS_DIR
    labels_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case_id, "faithfulness": faithfulness, "note": note,
        "reviewer": REVIEWER_LABEL, "labeled_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    path = label_path(storage, case_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    import os
    os.replace(tmp, path)


def cmd_status(storage) -> int:
    calibration = load_calibration(storage)
    total = calibration["case_count"]
    labels = load_existing_labels(storage)
    completed = len(labels)
    print(f"Completed: {completed} / {total} ({100.0 * completed / total:.1f}%)")
    print(f"Remaining: {total - completed}")
    return 0


def run_labeling(storage) -> int:
    calibration = load_calibration(storage)
    cases = calibration["cases"]
    total = len(cases)
    labels = load_existing_labels(storage)

    remaining = [c for c in cases if c["case_id"] not in labels]
    if not remaining:
        print(f"All {total} cases already labeled.")
        return 0

    print("LLM-JUDGE HUMAN CALIBRATION")
    print("=" * 27)
    for case in remaining:
        completed = len(load_existing_labels(storage))
        print(f"\nCompleted: {completed} / {total} ({100.0 * completed / total:.1f}%)")
        print(f"Remaining: {total - completed}")
        print(f"Current case: {case['case_id']}\n")
        print("QUESTION")
        print(case["question"])
        print("\nREFERENCE")
        print(case["reference_answer"])
        print("\nCANDIDATE")
        print(case["candidate_answer"])
        print("\nEVIDENCE")
        print(case["evidence"][:4000])
        print("\nRUBRIC")
        print("  supported   = every material factual claim in the candidate is directly")
        print("                supported by the evidence above.")
        print("  unsupported = at least one material factual claim is not supported by,")
        print("                or is contradicted by, the evidence above.")

        while True:
            raw = input("\nFaithfulness [supported/unsupported] (q=quit, s=skip): ").strip().lower()
            if raw == "q":
                print("Saved. Exiting - resume with --resume.")
                return 0
            if raw == "s":
                print("Skipped.")
                break
            if raw in FAITHFULNESS_LABELS:
                note = input("Optional note (press Enter to skip): ").strip()
                write_label(storage, case["case_id"], raw, note)
                completed = len(load_existing_labels(storage))
                print(f"Saved.\nProgress: {completed} / {total} ({100.0 * completed / total:.1f}%)")
                break
            print(f"Invalid input - enter one of {FAITHFULNESS_LABELS}, 'q', or 's'.")

    print(f"\nAll {total} cases labeled.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    storage = get_storage()
    if args.status:
        return cmd_status(storage)
    if args.start or args.resume:
        return run_labeling(storage)
    parser.error("one of --start, --resume, --status is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
