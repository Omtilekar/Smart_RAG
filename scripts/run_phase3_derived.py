"""Task 3.11 - deterministic derived calculations for the two DEV
`operation` shapes with real ground truth: `difference` (year-over-year,
comparative/year_over_year_difference, intent_label=numeric_derived) and
`greater_than` (cross-company comparison,
comparative/cross_entity_comparison, intent_label=cross_entity). Every
operand is fetched via Task 3.10's `src.sql.xbrl_lookup.XbrlFactIndex`;
this script only performs deterministic arithmetic/comparison on
already-eligible facts - "retrieve facts with models/rules; calculate
facts with deterministic code" (PROJECT_EXECUTION.md's own Task 3.11
principle). See configs/phase_3_11_derived_calculations.json for the
full frozen contract, including the growth/percentage-of-revenue scope
decision.

cik/fiscal_year/tag are extracted from each question's raw TEXT ONLY via
Task 3.8's frozen `classify_intent()` - never the question record's own
hidden ground-truth fields (test leakage).

Never imports src.eval.test_access - Task 3.11 evaluation is DEV-only.
Read-only against data/xbrl.duckdb.

Usage:
    python -u scripts/run_phase3_derived.py --plan
    python -u scripts/run_phase3_derived.py --run
    python -u scripts/run_phase3_derived.py --status
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.artifacts.versioning import semantic_hash  # noqa: E402
from src.eval.tag_registry import get_registry  # noqa: E402
from src.router.rules import CompanyGazetteer, classify_intent  # noqa: E402
from src.sql.xbrl_lookup import XbrlFactIndex  # noqa: E402
from src.sql.derived import compute_difference, compute_greater_than  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_derived as p3d  # noqa: E402
from src.eval.metrics import numeric_exact_match, MetricInputError  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402

from scripts.run_phase3_router import build_gazetteer_from_dev  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_11_derived_calculations.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
TASK32_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"
TASK33_QWEN_RESULT_PATH = REPO_ROOT / "results" / "phase3_3" / "qwen3_embedding.json"
SPLIT_SUMMARY_PATH = REPO_ROOT / "results" / "phase_2_4_split_summary.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_11"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_11_derived_calculations.json"

ROW_ID = "derived_calculations"
CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
CHUNK_SCHEMA_VERSION = 1
EXPECTED_CHUNK_COUNT = 323971


def git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_experiment_config() -> tuple[dict, str]:
    config = _load_json(CONFIG_PATH)
    return config, semantic_hash(config)


def load_dev_questions() -> dict:
    return _load_json(REPO_ROOT / "results" / "phase_2_4_dev.json")


def verify_frozen_chunks(storage) -> "pq.Table":
    task32 = _load_json(TASK32_RESULT_PATH)
    if task32["final_winner"]["chunk_config_hash"] != CHUNK_CONFIG_HASH:
        raise SystemExit("FATAL: Task 3.2 final_winner chunk_config_hash changed. STOP.")
    table = pq.read_table(storage.chunks_dir(CHUNK_CONFIG_HASH) / "chunks.parquet")
    if table.num_rows != EXPECTED_CHUNK_COUNT:
        raise SystemExit(f"FATAL: chunk artifact has {table.num_rows} rows, expected {EXPECTED_CHUNK_COUNT}")
    return table


def cmd_plan() -> int:
    config, config_hash = load_experiment_config()
    print("[STAGE 3/10] Frozen Task 3.11 derived-calculations contract")
    print(f"phase3_11_config_hash: {config_hash}")
    print(json.dumps(config, indent=2))
    return 0


def cmd_status() -> int:
    print("Task 3.11 status (read-only)")
    path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not path.is_file():
        print(f"  {ROW_ID}: not run")
        return 0
    result = _load_json(path)
    dr, gr = result["difference_rates"], result["greater_than_rates"]
    print(f"  difference:    coverage={dr['routing_coverage']['value']:.4f} exact_match={dr['exact_match_rate']['value']:.4f}")
    print(f"  greater_than:  coverage={gr['routing_coverage']['value']:.4f} exact_match={gr['exact_match_rate']['value']:.4f}")
    return 0


def _first_two_distinct_in_order(values: tuple) -> tuple | None:
    distinct: list = []
    for v in values:
        if v not in distinct:
            distinct.append(v)
    return tuple(distinct[:2]) if len(distinct) == 2 else None


def run_full() -> int:
    print("[STAGE 1/10] Task 3.11 preflight")
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    qwen = _load_json(TASK33_QWEN_RESULT_PATH)
    config, config_hash = load_experiment_config()
    dev_payload = load_dev_questions()
    questions = dev_payload["questions"]
    print(f"Chunks: {chunk_table.num_rows}. DEV questions: {len(questions)}.")

    print("[STAGE 2/10] Build router gazetteer/registry and XBRL fact index (read-only)")
    gazetteer = CompanyGazetteer(build_gazetteer_from_dev(dev_payload))
    registry = get_registry()
    con = duckdb.connect(str(storage.xbrl_db), read_only=True)
    try:
        index = XbrlFactIndex(con, registry.supported_tags())
    finally:
        con.close()
    print(f"XBRL fact index built for {len(registry.supported_tags())} tags.")

    print("[STAGE 6/10] Validate derived-calculation behavior (synthetic smoke)")
    from src.sql.xbrl_lookup import XbrlLookupResult
    fake_a = XbrlLookupResult(outcome="found", cik=1, fiscal_year=2019, tag="Assets", value=100.0, unit="USD", adsh="x", company="A")
    fake_b = XbrlLookupResult(outcome="found", cik=1, fiscal_year=2020, tag="Assets", value=150.0, unit="USD", adsh="y", company="A")

    class _FakeIndex:
        def lookup(self, *, cik, fiscal_year, tag):
            return fake_a if fiscal_year == 2019 else fake_b
    smoke = compute_difference(_FakeIndex(), cik=1, tag="Assets", fiscal_year_a=2019, fiscal_year_b=2020)
    assert smoke.outcome == "computed" and smoke.value == 50.0, smoke
    print(f"[SMOKE] ok  difference(100,150) = {smoke.value}")

    print("[STAGE 7/10] Evaluate 'difference' (year-over-year) questions")
    diff_questions = [q for q in questions if q.get("operation") == "difference"]
    diff_attempted, diff_computed, diff_exact = [], [], []
    diff_per_question = {}
    for i, q in enumerate(diff_questions, start=1):
        decision = classify_intent(q["question"], gazetteer=gazetteer, registry=registry)
        ciks = set(decision.resolved_ciks)
        years_pair = _first_two_distinct_in_order(decision.fiscal_years)
        complete = decision.intent == "numeric_derived" and decision.concept is not None and len(ciks) == 1 and years_pair is not None
        diff_attempted.append(complete)
        computed = False
        exact = False
        if complete:
            cik = next(iter(ciks))
            result = compute_difference(index, cik=cik, tag=decision.concept,
                                         fiscal_year_a=years_pair[0], fiscal_year_b=years_pair[1])
            computed = result.outcome == "computed"
            diff_computed.append(computed)
            if computed:
                try:
                    exact = numeric_exact_match(
                        gold_value=q["expected_numeric_answer"], gold_unit=q["expected_unit"],
                        predicted_value=str(result.value), predicted_unit=result.operand_b.unit,
                    )
                except MetricInputError:
                    exact = False
            diff_exact.append(exact)
        diff_per_question[q["question_id"]] = {"attempted": complete, "computed": computed, "exact_match": exact}
        if i % 60 == 0 or i == len(diff_questions):
            print(f"[DERIVED EVAL]  difference {i}/{len(diff_questions)}  attempted={sum(diff_attempted)}  "
                  f"computed={sum(diff_computed)}  exact={sum(diff_exact)}", flush=True)

    print("[STAGE 7/10] Evaluate 'greater_than' (cross-company) questions")
    cmp_questions = [q for q in questions if q.get("operation") == "greater_than"]
    cmp_attempted, cmp_computed, cmp_exact = [], [], []
    cmp_per_question = {}
    for i, q in enumerate(cmp_questions, start=1):
        decision = classify_intent(q["question"], gazetteer=gazetteer, registry=registry)
        ciks_pair = _first_two_distinct_in_order(decision.resolved_ciks)
        years = set(decision.fiscal_years)
        complete = decision.intent == "cross_entity" and decision.concept is not None and ciks_pair is not None and len(years) == 1
        cmp_attempted.append(complete)
        computed = False
        exact = False
        if complete:
            fy = next(iter(years))
            result = compute_greater_than(index, cik_a=ciks_pair[0], cik_b=ciks_pair[1], tag=decision.concept, fiscal_year=fy)
            computed = result.outcome == "computed"
            cmp_computed.append(computed)
            if computed:
                expected_operand = next((op for op in q["operands"] if op["company"] == q["expected_answer"]), None)
                exact = expected_operand is not None and result.winner_cik == expected_operand["cik"]
            cmp_exact.append(exact)
        cmp_per_question[q["question_id"]] = {"attempted": complete, "computed": computed, "exact_match": exact}
        if i % 30 == 0 or i == len(cmp_questions):
            print(f"[DERIVED EVAL]  greater_than {i}/{len(cmp_questions)}  attempted={sum(cmp_attempted)}  "
                  f"computed={sum(cmp_computed)}  exact={sum(cmp_exact)}", flush=True)

    print("[STAGE 9/10] Compute rates")
    difference_rates = p3d.derived_rates(attempted_flags=diff_attempted, computed_flags=diff_computed, exact_match_flags=diff_exact)
    greater_than_rates = p3d.derived_rates(attempted_flags=cmp_attempted, computed_flags=cmp_computed, exact_match_flags=cmp_exact)
    print(f"[DERIVED] difference:   coverage={difference_rates['routing_coverage']['value']:.4f} "
          f"exact_match={difference_rates['exact_match_rate']['value']:.4f}")
    print(f"[DERIVED] greater_than: coverage={greater_than_rates['routing_coverage']['value']:.4f} "
          f"exact_match={greater_than_rates['exact_match_rate']['value']:.4f}")

    split_summary = _load_json(SPLIT_SUMMARY_PATH)
    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": qwen["repository"], "model_revision": qwen["revision"],
            "embedding_dimension": qwen["dimension"], "vector_dtype": "float32",
            "normalize_embeddings": qwen["normalize_embeddings"], "identity_hash": qwen["embedding_identity_hash"],
        },
        index_identity_hash=None,
        retrieval_config={"type": "deterministic_derived_calculations", "downstream_of": "xbrl_sql_path"},
        reranker_config={"enabled": False}, generation_model=None, split="dev",
        eval_set_version="phase2-v1", split_version="phase2-split-v1", split_sha256=split_summary["dev_sha256"],
        metrics={"difference_exact_match_rate": difference_rates["exact_match_rate"]["value"],
                 "greater_than_exact_match_rate": greater_than_rates["exact_match_rate"]["value"]},
        evaluation_source="internal_phase2", experiment_name="phase3_11_derived_calculations",
        run_kind="phase3_derived_calculations",
        notes=f"Task 3.11 deterministic derived calculations over {len(diff_questions)} difference + "
              f"{len(cmp_questions)} greater_than DEV questions.",
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[DERIVED] Task 2.11 run record written: {run_record_path}")

    payload = {
        "row_id": ROW_ID, "config_hash": config_hash, "run_id": run_record.run_id, "git_sha": git_sha(),
        "difference_question_count": len(diff_questions), "greater_than_question_count": len(cmp_questions),
        "difference_rates": difference_rates, "greater_than_rates": greater_than_rates,
        "difference_per_question": diff_per_question, "greater_than_per_question": cmp_per_question,
    }
    _write_json(CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json", payload)

    print("[STAGE 10/10] Record ablation row and final result")
    baseline = _load_json(BASELINE_RESULT_PATH)
    corpus_doc_count = len(set(chunk_table.column("document_id").to_pylist()))
    row = p3d.build_derived_ablation_row(
        row_id=ROW_ID, config_hash=config_hash, run_id=run_record.run_id, git_sha=payload["git_sha"],
        eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
        corpus_document_count=corpus_doc_count, chunk_count=EXPECTED_CHUNK_COUNT, chunk_config_hash=CHUNK_CONFIG_HASH,
        dense_repository=qwen["repository"], dense_revision=qwen["revision"],
        dense_embedding_identity_hash=qwen["embedding_identity_hash"], dense_index_identity_hash=qwen["index_identity_hash"],
        difference_question_count=len(diff_questions), greater_than_question_count=len(cmp_questions),
        difference_rates=difference_rates, greater_than_rates=greater_than_rates,
        notes=f"Task 3.11: difference exact_match={difference_rates['exact_match_rate']['value']:.4f}, "
              f"greater_than exact_match={greater_than_rates['exact_match_rate']['value']:.4f}.",
    )
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    report = {
        "task": "3.11", "phase3_11_config_hash": config_hash, "phase3_11_config": config,
        "chunk_config_hash": CHUNK_CONFIG_HASH, "chunk_count": EXPECTED_CHUNK_COUNT,
        "corpus_document_count": corpus_doc_count,
        "difference_question_count": len(diff_questions), "greater_than_question_count": len(cmp_questions),
        "difference_rates": difference_rates, "greater_than_rates": greater_than_rates, "ablation_row": row,
        "limitations": [
            "Only 'difference' and 'greater_than' operations were implemented/evaluated - the entire DEV "
            "corpus has zero growth-rate or percentage-of-revenue examples; those remain designed-but-"
            "unevaluated pending new eval data.",
            "routing_coverage depends entirely on Task 3.8's router extraction accuracy for TWO operands "
            "(two years or two companies), a stricter requirement than Task 3.10's single-operand lookup.",
            "No retrieval, reranking, CRAG gating, or generation in this path - pure deterministic arithmetic "
            "over already-eligible XBRL facts.",
        ],
        "next_task_readiness": (
            f"difference: coverage={difference_rates['routing_coverage']['value']:.4f}, "
            f"exact_match={difference_rates['exact_match_rate']['value']:.4f}. "
            f"greater_than: coverage={greater_than_rates['routing_coverage']['value']:.4f}, "
            f"exact_match={greater_than_rates['exact_match_rate']['value']:.4f}."
        ),
    }
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.11 report written: {FINAL_RESULT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.11 - Phase 3 deterministic derived calculations.")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.plan:
        return cmd_plan()
    if args.status:
        return cmd_status()
    if args.run:
        return run_full()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
