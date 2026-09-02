"""Task 2.13 - builds the frozen 100-case LLM-judge calibration pack from
Task 2.12's real, evidence-aligned FinanceBench questions.

Never fabricates evidence or gold: every case's evidence text comes from
a real, already-parsed FinanceBench source PDF page that Task 2.12
independently aligned (`exact`/`normalized_exact`) to the question's
gold evidence. Every reference answer is FinanceBench's own real
`answer` field. Candidate answers are either the reference answer
verbatim, or a small, fully deterministic, documented transformation of
it (numeric corruption / an appended out-of-evidence clause) - never an
LLM-generated answer, and never a paid API call.

The perturbation TYPE is recorded for later diagnostic breakdown
(Section 50) but is never treated as ground truth and is never shown to
the human reviewer or the judge.

Usage:
    python scripts/prepare_llm_judge_calibration.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.artifacts.versioning import semantic_hash  # noqa: E402
from src.storage import get_storage  # noqa: E402

FINANCEBENCH_CONFIG_HASH = "a82c1b8ce54ea4fd343da5cac484e1d19f8cad9b8702b966cd8e11924ff25391"
DIAGNOSTICS_PATH = (
    Path("artifacts") / "benchmark" / "financebench" / FINANCEBENCH_CONFIG_HASH / "per_question_results.json"
)
PARSED_DIR = Path("artifacts") / "benchmark" / "financebench" / FINANCEBENCH_CONFIG_HASH / "parsed"
FINANCEBENCH_JSONL = Path("data") / "financebench" / "financebench_merged.jsonl"

CALIBRATION_SET_VERSION = "1.0"
POSITIVE_CASE_COUNT = 50
NEGATIVE_CASE_COUNT = 50

_NUMBER_RE = re.compile(r"[\d][\d,]*\.?\d*")

UNSUPPORTED_EXTRA_CLAUSE = (
    " This increase was primarily driven by a one-time divestiture gain "
    "recorded in a segment not discussed anywhere in the filing."
)


def parse_chunk_id(chunk_id: str) -> tuple[str, int]:
    # "financebench:<doc_name>:page<NNNNN>:chunk<NNNN>"
    parts = chunk_id.split(":")
    doc_name = parts[1]
    page_number = int(parts[2][len("page"):])
    return doc_name, page_number


def load_page_text(doc_name: str, page_number: int, page_cache: dict) -> str:
    if doc_name not in page_cache:
        path = PARSED_DIR / f"{doc_name}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        page_cache[doc_name] = {p["page_number"]: p["text"] for p in payload["pages"]}
    return page_cache[doc_name][page_number]


def numeric_corruption(answer: str) -> str | None:
    """Deterministically doubles the first numeric value found in the
    answer - never a random/nonsensical corruption. Returns None if no
    number is present (caller should fall back to another transform)."""
    match = _NUMBER_RE.search(answer)
    if not match:
        return None
    raw = match.group(0)
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    corrupted = value * 2
    corrupted_str = f"{corrupted:,.2f}" if "." in raw or value != int(value) else f"{int(corrupted):,}"
    return answer[: match.start()] + corrupted_str + answer[match.end():]


def build_case(*, case_id: str, financebench_id: str, question: str, reference_answer: str,
                candidate_answer: str, evidence: str, perturbation_type: str) -> dict:
    return {
        "case_id": case_id,
        "financebench_id": financebench_id,
        "question": question,
        "reference_answer": reference_answer,
        "candidate_answer": candidate_answer,
        "evidence": evidence,
        "perturbation_type": perturbation_type,
    }


def main() -> None:
    storage = get_storage()
    diagnostics = json.loads((REPO_ROOT / DIAGNOSTICS_PATH).read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (REPO_ROOT / FINANCEBENCH_JSONL).read_text(encoding="utf-8").splitlines() if line.strip()]
    rows_by_id = {r["financebench_id"]: r for r in rows}

    evaluated = sorted(
        (d for d in diagnostics if d["status"] == "evaluated" and d["gold_chunk_ids"]),
        key=lambda d: d["financebench_id"],
    )
    print(f"Evidence-aligned FinanceBench questions available: {len(evaluated)}")
    if len(evaluated) < POSITIVE_CASE_COUNT:
        raise SystemExit(f"STOP: only {len(evaluated)} evidence-aligned questions available, need at least {POSITIVE_CASE_COUNT}")

    page_cache: dict = {}
    cases = []

    positive_source = evaluated[:POSITIVE_CASE_COUNT]
    for d in positive_source:
        row = rows_by_id[d["financebench_id"]]
        pages = sorted({parse_chunk_id(cid)[1] for cid in d["gold_chunk_ids"]})
        doc_name = d["doc_name"]
        evidence = "\n\n".join(load_page_text(doc_name, p, page_cache) for p in pages)
        cases.append(build_case(
            case_id=f"{d['financebench_id']}-reference", financebench_id=d["financebench_id"],
            question=row["question"], reference_answer=row["answer"], candidate_answer=row["answer"],
            evidence=evidence, perturbation_type="reference_as_candidate",
        ))

    negative_source = evaluated[:NEGATIVE_CASE_COUNT]
    for d in negative_source:
        row = rows_by_id[d["financebench_id"]]
        pages = sorted({parse_chunk_id(cid)[1] for cid in d["gold_chunk_ids"]})
        doc_name = d["doc_name"]
        evidence = "\n\n".join(load_page_text(doc_name, p, page_cache) for p in pages)
        corrupted = numeric_corruption(row["answer"])
        if corrupted is not None:
            cases.append(build_case(
                case_id=f"{d['financebench_id']}-numeric-corruption", financebench_id=d["financebench_id"],
                question=row["question"], reference_answer=row["answer"], candidate_answer=corrupted,
                evidence=evidence, perturbation_type="numeric_corruption",
            ))
        else:
            cases.append(build_case(
                case_id=f"{d['financebench_id']}-unsupported-extra-claim", financebench_id=d["financebench_id"],
                question=row["question"], reference_answer=row["answer"],
                candidate_answer=row["answer"] + UNSUPPORTED_EXTRA_CLAUSE,
                evidence=evidence, perturbation_type="unsupported_extra_claim",
            ))

    print(f"Built {len(cases)} calibration cases ({len(positive_source)} reference + {len(negative_source)} degraded)")

    # Semantic calibration-set identity (Section 48): case_id + hashes of
    # question/reference/candidate/evidence text, never the raw source
    # text itself in the frozen manifest, and never perturbation_type
    # (that's a diagnostic label revealed only post-hoc, Section 50).
    semantic_cases = [
        {
            "case_id": c["case_id"],
            "question_sha256": semantic_hash(c["question"]),
            "reference_answer_sha256": semantic_hash(c["reference_answer"]),
            "candidate_answer_sha256": semantic_hash(c["candidate_answer"]),
            "evidence_sha256": semantic_hash(c["evidence"]),
        }
        for c in cases
    ]
    calibration_set_sha256 = semantic_hash(semantic_cases)

    out_dir = storage.artifacts_root / "eval" / "llm_judge_calibration"
    storage.ensure_dir(out_dir)
    full_path = out_dir / "calibration_cases.json"
    full_path.write_text(json.dumps({
        "calibration_set_version": CALIBRATION_SET_VERSION,
        "calibration_set_sha256": calibration_set_sha256,
        "case_count": len(cases),
        "source": "financebench-evidence-aligned",
        "financebench_config_hash": FINANCEBENCH_CONFIG_HASH,
        "cases": cases,
    }, indent=2), encoding="utf-8")

    manifest_path = out_dir / "calibration_manifest.json"
    manifest_path.write_text(json.dumps({
        "calibration_set_version": CALIBRATION_SET_VERSION,
        "calibration_set_sha256": calibration_set_sha256,
        "case_count": len(cases),
        "cases": semantic_cases,
    }, indent=2), encoding="utf-8")

    print(f"calibration_set_sha256: {calibration_set_sha256}")
    print(f"Written (gitignored, full text): {full_path}")
    print(f"Written (gitignored, hashes only): {manifest_path}")


if __name__ == "__main__":
    main()
