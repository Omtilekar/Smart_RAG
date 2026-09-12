"""Task 3.10 - structured XBRL SQL path for xbrl_fact-routed questions:

    question -> Task 3.8 router -> (cik, fiscal_year, tag) -> Task 2.1/2.2
    truth-contract fact lookup -> value + unit + filing provenance

No retrieval, no embedding call, no generation anywhere in this path.
cik/fiscal_year/tag are extracted from each question's raw TEXT ONLY via
Task 3.8's frozen `classify_intent()` - never the question record's own
hidden ground-truth fields (test leakage); those are used only to score
the SQL lookup's output afterward. See
configs/phase_3_10_xbrl_sql_path.json for the full frozen contract.

Never imports src.eval.test_access - Task 3.10 evaluation is DEV-only.
Read-only against data/xbrl.duckdb.

Usage:
    python -u scripts/run_phase3_sql.py --plan
    python -u scripts/run_phase3_sql.py --run
    python -u scripts/run_phase3_sql.py --status
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
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_sql as p3s  # noqa: E402
from src.eval.metrics import numeric_exact_match, MetricInputError  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402

from scripts.run_phase3_router import build_gazetteer_from_dev  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_10_xbrl_sql_path.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
TASK32_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"
TASK33_QWEN_RESULT_PATH = REPO_ROOT / "results" / "phase3_3" / "qwen3_embedding.json"
SPLIT_SUMMARY_PATH = REPO_ROOT / "results" / "phase_2_4_split_summary.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_10"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_10_xbrl_sql_path.json"

ROW_ID = "xbrl_sql_path"
CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
CHUNK_SCHEMA_VERSION = 1
EXPECTED_CHUNK_COUNT = 323971
TRAP_SUBTYPES = ("unsupported_tag", "year_outside_window")


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
    print("[STAGE 3/10] Frozen Task 3.10 structured XBRL SQL path contract")
    print(f"phase3_10_config_hash: {config_hash}")
    registry = get_registry()
    live_tags = sorted(registry.supported_tags())
    if live_tags != sorted(config["tags_indexed"]):
        raise SystemExit(f"FATAL: live registry tags {live_tags} != frozen config tags {sorted(config['tags_indexed'])}. STOP.")
    print(f"Live registry tags match frozen config: {len(live_tags)} tags.")
    print(json.dumps(config, indent=2))
    return 0


def cmd_status() -> int:
    print("Task 3.10 status (read-only)")
    path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not path.is_file():
        print(f"  {ROW_ID}: not run")
        return 0
    result = _load_json(path)
    rates = result["rates"]
    print(f"  {ROW_ID}: routing_coverage={rates['routing_coverage']['value']:.4f} "
          f"sql_found_rate={rates['sql_found_rate']['value']:.4f} "
          f"sql_exact_match_rate={rates['sql_exact_match_rate']['value']:.4f} "
          f"trap_leak_rate={rates['trap_leak_rate']['value']:.4f}")
    return 0


def run_full() -> int:
    print("[STAGE 1/10] Task 3.10 preflight")
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
    print(f"XBRL fact index built for {len(registry.supported_tags())} tags (data/xbrl.duckdb, read-only).")

    print("[STAGE 6/10] Validate lookup behavior (synthetic smoke)")
    smoke = index.lookup(cik=-1, fiscal_year=2019, tag="Assets")
    assert smoke.outcome == "not_found", smoke
    # A dedicated tiny index that WAS asked to build an unsupported tag -
    # demonstrates the registry's own TruthContractError is caught and
    # recorded as outcome="unsupported_tag", never silently answered.
    unsupported_probe = XbrlFactIndex(con=duckdb.connect(str(storage.xbrl_db), read_only=True),
                                       tags=["DepreciationDepletionAndAmortization"])
    smoke2 = unsupported_probe.lookup(cik=-1, fiscal_year=2019, tag="DepreciationDepletionAndAmortization")
    assert smoke2.outcome == "unsupported_tag", smoke2
    print(f"[SMOKE] ok  unknown (cik,year) -> {smoke.outcome!r}; unsupported tag -> {smoke2.outcome!r}")

    print("[STAGE 7/10] Route every DEV question and attempt SQL lookup where applicable")
    xbrl_fact_questions = [q for q in questions if q["intent_label"] == "xbrl_fact"]
    trap_questions = [q for q in questions if q.get("subtype") in TRAP_SUBTYPES]
    print(f"xbrl_fact target population: {len(xbrl_fact_questions)}. Trap population: {len(trap_questions)}.")

    attempted_flags, found_flags, exact_match_flags = [], [], []
    per_question_xbrl_fact = {}
    for i, q in enumerate(xbrl_fact_questions, start=1):
        decision = classify_intent(q["question"], gazetteer=gazetteer, registry=registry)
        routed = decision.intent == "xbrl_fact"
        ciks, years = set(decision.resolved_ciks), set(decision.fiscal_years)
        complete = routed and decision.concept is not None and len(ciks) == 1 and len(years) == 1
        attempted_flags.append(complete)

        result = None
        exact = False
        if complete:
            cik, fy = next(iter(ciks)), next(iter(years))
            result = index.lookup(cik=cik, fiscal_year=fy, tag=decision.concept)
            found_flags.append(result.outcome == "found")
            if result.outcome == "found":
                try:
                    exact = numeric_exact_match(
                        gold_value=q["expected_value"], gold_unit=q["expected_unit"],
                        predicted_value=str(result.value), predicted_unit=result.unit,
                    )
                except MetricInputError:
                    exact = False
            exact_match_flags.append(exact)

        per_question_xbrl_fact[q["question_id"]] = {
            "attempted": complete, "routed_intent": decision.intent, "concept_matched": decision.concept,
            "outcome": result.outcome if result else None, "exact_match": exact if complete else None,
        }
        if i % 300 == 0 or i == len(xbrl_fact_questions):
            print(f"[SQL EVAL]  xbrl_fact {i}/{len(xbrl_fact_questions)}  "
                  f"attempted={sum(attempted_flags)}  found={sum(found_flags)}  exact={sum(exact_match_flags)}", flush=True)

    trap_leak_flags = []
    per_question_trap = {}
    for q in trap_questions:
        decision = classify_intent(q["question"], gazetteer=gazetteer, registry=registry)
        ciks, years = set(decision.resolved_ciks), set(decision.fiscal_years)
        complete = decision.intent == "xbrl_fact" and decision.concept is not None and len(ciks) == 1 and len(years) == 1
        outcome = None
        leaked = False
        if complete:
            cik, fy = next(iter(ciks)), next(iter(years))
            result = index.lookup(cik=cik, fiscal_year=fy, tag=decision.concept)
            outcome = result.outcome
            leaked = result.outcome == "found"
        trap_leak_flags.append(leaked)
        per_question_trap[q["question_id"]] = {"routed_intent": decision.intent, "attempted": complete,
                                                 "outcome": outcome, "leaked": leaked}

    rates = p3s.sql_rates(attempted_flags=attempted_flags, found_flags=found_flags,
                           exact_match_flags=exact_match_flags, trap_leak_flags=trap_leak_flags)

    print("[STAGE 9/10] Compute rates")
    print(f"[SQL] routing_coverage: {rates['routing_coverage']['value']:.4f} "
          f"({rates['routing_coverage']['numerator']}/{rates['routing_coverage']['denominator']})")
    print(f"[SQL] sql_found_rate: {rates['sql_found_rate']['value']:.4f} "
          f"({rates['sql_found_rate']['numerator']}/{rates['sql_found_rate']['denominator']})")
    print(f"[SQL] sql_exact_match_rate: {rates['sql_exact_match_rate']['value']:.4f} "
          f"({rates['sql_exact_match_rate']['numerator']}/{rates['sql_exact_match_rate']['denominator']})")
    print(f"[SQL] trap_leak_rate: {rates['trap_leak_rate']['value']:.4f} "
          f"({rates['trap_leak_rate']['numerator']}/{rates['trap_leak_rate']['denominator']})")
    if rates["trap_leak_rate"]["numerator"] > 0:
        leaked_ids = [qid for qid, v in per_question_trap.items() if v["leaked"]]
        print(f"[SQL] WARNING: {len(leaked_ids)} trap question(s) received a confident wrong SQL answer: {leaked_ids}")

    split_summary = _load_json(SPLIT_SUMMARY_PATH)
    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": qwen["repository"], "model_revision": qwen["revision"],
            "embedding_dimension": qwen["dimension"], "vector_dtype": "float32",
            "normalize_embeddings": qwen["normalize_embeddings"], "identity_hash": qwen["embedding_identity_hash"],
        },
        index_identity_hash=None,
        retrieval_config={"type": "structured_xbrl_sql_path", "downstream_of": "rules_first_router"},
        reranker_config={"enabled": False}, generation_model=None, split="dev",
        eval_set_version="phase2-v1", split_version="phase2-split-v1", split_sha256=split_summary["dev_sha256"],
        metrics={k: v["value"] for k, v in rates.items()}, evaluation_source="internal_phase2",
        experiment_name="phase3_10_xbrl_sql_path", run_kind="phase3_xbrl_sql_path",
        notes=f"Task 3.10 structured XBRL SQL path over {len(xbrl_fact_questions)} xbrl_fact + "
              f"{len(trap_questions)} trap DEV questions.",
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[SQL] Task 2.11 run record written: {run_record_path}")

    payload = {
        "row_id": ROW_ID, "config_hash": config_hash, "run_id": run_record.run_id, "git_sha": git_sha(),
        "xbrl_fact_question_count": len(xbrl_fact_questions), "trap_question_count": len(trap_questions),
        "rates": rates, "per_question_xbrl_fact": per_question_xbrl_fact, "per_question_trap": per_question_trap,
    }
    _write_json(CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json", payload)

    print("[STAGE 10/10] Record ablation row and final result")
    baseline = _load_json(BASELINE_RESULT_PATH)
    corpus_doc_count = len(set(chunk_table.column("document_id").to_pylist()))
    row = p3s.build_sql_ablation_row(
        row_id=ROW_ID, config_hash=config_hash, run_id=run_record.run_id, git_sha=payload["git_sha"],
        eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
        corpus_document_count=corpus_doc_count, chunk_count=EXPECTED_CHUNK_COUNT, chunk_config_hash=CHUNK_CONFIG_HASH,
        dense_repository=qwen["repository"], dense_revision=qwen["revision"],
        dense_embedding_identity_hash=qwen["embedding_identity_hash"], dense_index_identity_hash=qwen["index_identity_hash"],
        xbrl_fact_question_count=len(xbrl_fact_questions), trap_question_count=len(trap_questions), rates=rates,
        notes=f"Task 3.10: structured XBRL SQL path, routing_coverage={rates['routing_coverage']['value']:.4f}, "
              f"sql_exact_match_rate={rates['sql_exact_match_rate']['value']:.4f}, "
              f"trap_leak_rate={rates['trap_leak_rate']['value']:.4f}.",
    )
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    report = {
        "task": "3.10", "phase3_10_config_hash": config_hash, "phase3_10_config": config,
        "chunk_config_hash": CHUNK_CONFIG_HASH, "chunk_count": EXPECTED_CHUNK_COUNT,
        "corpus_document_count": corpus_doc_count,
        "xbrl_fact_question_count": len(xbrl_fact_questions), "trap_question_count": len(trap_questions),
        "rates": rates, "ablation_row": row,
        "limitations": [
            "routing_coverage/sql_found_rate/sql_exact_match_rate depend on Task 3.8's router extraction "
            "accuracy - a misrouted or incompletely-extracted xbrl_fact question is never attempted, and is "
            "counted against routing_coverage, not against the SQL path's own correctness.",
            "trap_leak_rate is the hard safety invariant this task must not violate; a nonzero value would "
            "mean the SQL path confidently answered a question with no valid answer.",
            "No retrieval, reranking, CRAG, or generation in this path - a pure structured lookup.",
        ],
        "next_task_readiness": (
            f"routing_coverage={rates['routing_coverage']['value']:.4f}, "
            f"sql_exact_match_rate={rates['sql_exact_match_rate']['value']:.4f}, "
            f"trap_leak_rate={rates['trap_leak_rate']['value']:.4f}."
        ),
    }
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.10 report written: {FINAL_RESULT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.10 - Phase 3 structured XBRL SQL path.")
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
