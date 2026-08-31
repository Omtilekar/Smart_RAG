"""Task 1.8 - real 10-case live citation-integrity smoke.

For each configured question: one retrieval (recorded, exact supplied
top-5 captured), one generation call, then mechanical citation-integrity
evaluation against the real Task 1.5 chunks table and that exact supplied
context. No citation repair, no regeneration, no second LLM judge. Exits
non-zero if any of the 10 cases fails citation integrity - this is the
point of the smoke check, not a bug to hide.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import get_settings  # noqa: E402
from src.storage import get_storage  # noqa: E402
from src.embeddings.bge import load_model  # noqa: E402
from src.index.lancedb_index import open_database, open_chunk_table  # noqa: E402
from src.retrieval.baseline import BaselineRetriever  # noqa: E402
from src.generation.openrouter import OpenRouterProvider, API_KEY_ENV_VAR  # noqa: E402
from src.generation.minimal import MinimalGenerator  # noqa: E402
from src.eval.citation_integrity import (  # noqa: E402
    RecordingRetriever,
    LanceDBResolvers,
    evaluate_citation_integrity,
)

CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
MODEL_REPO = "BAAI/bge-small-en-v1.5"
EXPECTED_ROW_COUNT = 162357
CONFIG_RELATIVE_PATH = Path("configs") / "citation_integrity_smoke.json"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_1_8_citation_integrity_summary.json"

# Task 1.7a: optional output-path override so a corrective rerun of this exact
# same smoke can be written to a separate file instead of overwriting the
# historical Task 1.8 result. Defaults to the original path unchanged - no
# behavior change for existing callers.
OUTPUT_PATH_ENV_VAR = "CITATION_SMOKE_OUTPUT_PATH"


def load_question_config(storage) -> list[dict]:
    path = storage.repo_root / CONFIG_RELATIVE_PATH
    storage.require_file(path)
    config = json.loads(path.read_text(encoding="utf-8"))
    questions = config["questions"]
    if len(questions) != 10:
        raise SystemExit(f"FATAL: expected 10 configured questions, found {len(questions)}")
    n_answer = sum(1 for q in questions if q["expected_behavior"] == "answer")
    n_abstain = sum(1 for q in questions if q["expected_behavior"] == "abstain")
    if n_answer != 8 or n_abstain != 2:
        raise SystemExit(f"FATAL: expected 8 answer + 2 abstain cases, found {n_answer} + {n_abstain}")
    return questions


def verify_index(storage):
    db_path = storage.index_dir(CHUNK_CONFIG_HASH, MODEL_REPO)
    storage.require_dir(db_path)
    db = open_database(db_path)
    names = db.list_tables().tables
    if names != ["chunks"]:
        raise SystemExit(f"FATAL: expected table ['chunks'], found {names}")
    table = open_chunk_table(db)
    if table.count_rows() != EXPECTED_ROW_COUNT:
        raise SystemExit(f"FATAL: table has {table.count_rows()} rows, expected {EXPECTED_ROW_COUNT}")
    return db_path, table


def verify_supplied_context(case_id: str, supplied) -> None:
    ids = [r.chunk_id for r in supplied]
    if len(supplied) != 5 or len(set(ids)) != 5:
        raise SystemExit(f"FATAL: {case_id} did not receive exactly 5 unique supplied chunks")
    for r in supplied:
        if not r.chunk_id or not r.document_id or not r.text:
            raise SystemExit(f"FATAL: {case_id} supplied chunk has an empty required field")


def main() -> int:
    settings = get_settings()
    storage = get_storage()

    if (settings.generation_provider or "").strip().lower() != "openrouter":
        print("FATAL: GENERATION_PROVIDER must be 'openrouter'.", file=sys.stderr)
        return 1
    model = (settings.generation_model or "").strip()
    if not model:
        print("FATAL: GENERATION_MODEL is not set. Refusing to guess a model.", file=sys.stderr)
        return 1
    if not os.environ.get(API_KEY_ENV_VAR, "").strip():
        print(f"FATAL: {API_KEY_ENV_VAR} is not set.", file=sys.stderr)
        return 1

    questions = load_question_config(storage)
    db_path, table = verify_index(storage)
    resolvers = LanceDBResolvers(table)

    embed_model = load_model(device="cuda")
    real_retriever = BaselineRetriever(model=embed_model, table=table)
    recorder = RecordingRetriever(real_retriever)
    provider = OpenRouterProvider(model=model)
    generator = MinimalGenerator(recorder, provider)

    case_records = []
    response_model = None

    for q in questions:
        gen_result, provider_response, _retrieval_ms = generator._answer_with_diagnostics(q["question"])
        response_model = provider_response.response_model or response_model

        supplied = recorder.last_results
        verify_supplied_context(q["id"], supplied)
        supplied_ids = {r.chunk_id for r in supplied}
        supplied_by_id = {r.chunk_id: r for r in supplied}

        case_result = evaluate_citation_integrity(
            answer=gen_result.answer,
            generation_citations=gen_result.citations,
            supplied_chunk_ids=supplied_ids,
            exists_fn=resolvers.exists,
            metadata_fn=resolvers.metadata,
            abstention_expected=(q["expected_behavior"] == "abstain"),
        )

        enriched_checks = []
        for check in case_result.citation_checks:
            metadata = check.source_metadata
            if check.was_supplied and metadata is not None and check.chunk_id in supplied_by_id:
                r = supplied_by_id[check.chunk_id]
                metadata = {**metadata, "retrieval_rank": r.rank, "retrieval_score": r.score,
                            "retrieval_distance": r.distance}
            enriched_checks.append({
                "chunk_id": check.chunk_id,
                "exists_in_index": check.exists_in_index,
                "was_supplied": check.was_supplied,
                "source_metadata": metadata,
            })

        case_records.append({
            "case_id": q["id"],
            "question": q["question"],
            "expected_behavior": q["expected_behavior"],
            "answer": gen_result.answer,
            "parsed_citations": gen_result.citations,
            "citation_attempts": [
                {"raw": a.raw, "bracket_style": a.bracket_style, "strict_valid": a.strict_valid}
                for a in case_result.citation_attempts
            ],
            "malformed_citation_attempts": [a.raw for a in case_result.malformed_attempts],
            "supplied_chunk_ids": sorted(supplied_ids),
            "citation_checks": enriched_checks,
            "case_status": case_result.status,
            "failure_reasons": case_result.failure_reasons,
            "requested_provider": "openrouter",
            "requested_model": model,
            "response_reported_model": provider_response.response_model,
        })

        line = f"{case_result.status} {q['id']}"
        if case_result.status == "FAIL":
            line += f": {', '.join(case_result.failure_reasons)}"
            if case_result.malformed_attempts:
                line += f'  malformed="{case_result.malformed_attempts[0].raw}"'
        print(line)

    passed = sum(1 for c in case_records if c["case_status"] == "PASS")
    failed = len(case_records) - passed

    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "chunk_config_hash": CHUNK_CONFIG_HASH,
        "embedding_model": MODEL_REPO,
        "requested_provider": "openrouter",
        "requested_model": model,
        "response_reported_model": response_model,
        "total_cases": len(case_records),
        "passed_cases": passed,
        "failed_cases": failed,
        "answer_expected_cases": 8,
        "abstention_control_cases": 2,
        "cases_with_valid_citations": sum(1 for c in case_records if c["parsed_citations"]),
        "cases_with_malformed_attempts": sum(1 for c in case_records if c["malformed_citation_attempts"]),
        "cases_with_unknown_ids": sum(1 for c in case_records if "unknown_chunk_id" in c["failure_reasons"]),
        "cases_with_out_of_context_ids": sum(
            1 for c in case_records if "citation_not_in_supplied_context" in c["failure_reasons"]
        ),
        "cases_missing_required_citation": sum(
            1 for c in case_records if "missing_required_citation" in c["failure_reasons"]
        ),
        "total_valid_citations": sum(len(c["parsed_citations"]) for c in case_records),
        "valid_citations_existing": sum(
            1 for c in case_records for chk in c["citation_checks"] if chk["exists_in_index"]
        ),
        "valid_citations_supplied": sum(
            1 for c in case_records for chk in c["citation_checks"] if chk["was_supplied"]
        ),
        "cases": case_records,
    }
    output_override = os.environ.get(OUTPUT_PATH_ENV_VAR, "").strip()
    summary_path = (storage.repo_root / output_override) if output_override else (storage.repo_root / SUMMARY_RELATIVE_PATH)
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"\n{passed}/{len(case_records)} cases passed citation integrity.")
    print(f"Summary written to: {summary_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
