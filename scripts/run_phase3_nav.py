"""Task 3.12 - simple tree/section navigation for queries like
"Summarize Item 7 of this filing." No retrieval, no embedding call, no
generation, no full-corpus scan. See
configs/phase_3_12_tree_section_navigation.json for the full frozen
contract, including the zero-DEV-example scope decision and the
corpus-level evaluation methodology this task uses instead.

Never imports src.eval.test_access - Task 3.12 evaluation is DEV/local-
corpus-only. Read-only against data/xbrl.duckdb and the already-parsed
artifacts/primary_docs/parsed/ corpus (Task 2.8, gitignored, never
written by this script).

Usage:
    python -u scripts/run_phase3_nav.py --plan
    python -u scripts/run_phase3_nav.py --run
    python -u scripts/run_phase3_nav.py --status
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

from src.storage import get_storage, safe_component  # noqa: E402
from src.artifacts.versioning import semantic_hash  # noqa: E402
from src.nav.section_navigation import navigate_to_section, resolve_filing_document_id  # noqa: E402
from src.eval import phase3_baseline as p3  # noqa: E402
from src.eval import phase3_nav as p3n  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_12_tree_section_navigation.json"
BASELINE_RESULT_PATH = REPO_ROOT / "results" / "phase_3_1_trusted_baseline.json"
TASK32_RESULT_PATH = REPO_ROOT / "results" / "phase_3_2_chunking_ablation.json"
TASK33_QWEN_RESULT_PATH = REPO_ROOT / "results" / "phase3_3" / "qwen3_embedding.json"
SPLIT_SUMMARY_PATH = REPO_ROOT / "results" / "phase_2_4_split_summary.json"
CANDIDATE_RESULTS_DIR = REPO_ROOT / "results" / "phase3_12"
ABLATION_TABLE_PATH = REPO_ROOT / "results" / "phase_3_ablation_table.csv"
FINAL_RESULT_PATH = REPO_ROOT / "results" / "phase_3_12_tree_section_navigation.json"

ROW_ID = "tree_section_navigation"
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
    print("[STAGE 3/9] Frozen Task 3.12 tree/section-navigation contract")
    print(f"phase3_12_config_hash: {config_hash}")
    print(json.dumps(config, indent=2))
    return 0


def cmd_status() -> int:
    print("Task 3.12 status (read-only)")
    path = CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json"
    if not path.is_file():
        print(f"  {ROW_ID}: not run")
        return 0
    result = _load_json(path)
    rates = result["rates"]
    print(f"  filing_resolution_rate={rates['filing_resolution_rate']['value']:.4f} "
          f"section_found_rate={rates['section_found_rate']['value']:.4f} "
          f"scope_leak_rate={rates['scope_leak_rate']['value']:.4f}")
    return 0


def _parse_document_id(document_id: str) -> tuple[int, str]:
    _prefix, cik_str, accession = document_id.split(":", 2)
    return int(cik_str), accession


def run_full() -> int:
    print("[STAGE 1/9] Task 3.12 preflight")
    storage = get_storage()
    chunk_table = verify_frozen_chunks(storage)
    qwen = _load_json(TASK33_QWEN_RESULT_PATH)
    config, config_hash = load_experiment_config()
    manifest_path = storage.artifacts_root / "primary_docs" / "manifest.json"
    manifest = _load_json(manifest_path)
    parsed_document_ids = sorted(
        doc_id for doc_id, rec in manifest["documents"].items() if rec.get("status") == "success"
    )
    print(f"Chunks: {chunk_table.num_rows}. Parsed primary documents: {len(parsed_document_ids)}.")

    print("[STAGE 6/9] Validate navigation behavior (synthetic smoke)")
    con = duckdb.connect(str(storage.xbrl_db), read_only=True)
    try:
        smoke_outcome, _ = resolve_filing_document_id(con, cik=-1, fiscal_year=1900)
        assert smoke_outcome == "filing_not_found", smoke_outcome
        print("[SMOKE] ok  resolve_filing_document_id returns filing_not_found for a nonexistent (cik, fiscal_year)")

        print("[STAGE 7/9] Evaluate filing resolution + section navigation over the parsed corpus")
        resolution_flags: list[bool] = []
        section_found_flags: list[bool] = []
        leak_flags: list[bool] = []
        per_document: dict = {}
        skipped_non_10k = 0
        skipped_no_submission = 0

        for i, document_id in enumerate(parsed_document_ids, start=1):
            cik, accession = _parse_document_id(document_id)
            row = con.execute(
                "SELECT fiscal_year, form FROM submissions WHERE cik = ? AND adsh = ?",
                [cik, accession],
            ).fetchone()
            if row is None:
                skipped_no_submission += 1
                continue
            fiscal_year, form = row
            if form != "10-K":
                skipped_non_10k += 1
                continue

            # --- filing_resolution_rate: does (cik, fiscal_year) round-trip
            # back to the SAME document_id Task 2.8 actually parsed?
            resolved_outcome, resolved_id = resolve_filing_document_id(con, cik=cik, fiscal_year=fiscal_year)
            resolved_ok = resolved_outcome == "found" and resolved_id == document_id
            resolution_flags.append(resolved_ok)

            nodes = json.loads((storage.artifacts_root / "primary_docs" / "parsed" / f"{safe_component(document_id)}.json").read_text(encoding="utf-8"))
            detected_items = sorted({n["section_id"] for n in nodes if n.get("section_id")})
            doc_record = {"cik": cik, "fiscal_year": fiscal_year, "resolution_ok": resolved_ok, "items": {}}

            for item in detected_items:
                result = navigate_to_section(con, cik=cik, fiscal_year=fiscal_year, item=item)
                found = result.outcome == "found"
                section_found_flags.append(found)
                if found:
                    # Hard invariant: a successful navigation must return
                    # strictly fewer nodes than the whole document - proof
                    # no unnecessary global/full-document read occurred.
                    leaked = result.node_count >= result.total_document_node_count
                    leak_flags.append(leaked)
                doc_record["items"][item] = result.outcome
            per_document[document_id] = doc_record

            if i % 150 == 0 or i == len(parsed_document_ids):
                print(f"[NAV EVAL]  {i}/{len(parsed_document_ids)}  "
                      f"resolved={sum(resolution_flags)}  section_attempts={len(section_found_flags)}  "
                      f"section_found={sum(section_found_flags)}", flush=True)
    finally:
        con.close()

    print(f"Skipped (no submission row): {skipped_no_submission}. Skipped (non-10-K form): {skipped_non_10k}.")

    print("[STAGE 8/9] Compute rates")
    rates = p3n.nav_rates(resolution_flags=resolution_flags, section_found_flags=section_found_flags, leak_flags=leak_flags)
    print(f"[NAV] filing_resolution_rate={rates['filing_resolution_rate']['value']:.4f} "
          f"section_found_rate={rates['section_found_rate']['value']:.4f} "
          f"scope_leak_rate={rates['scope_leak_rate']['value']:.4f}")

    split_summary = _load_json(SPLIT_SUMMARY_PATH)
    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_model={
            "model_repository": qwen["repository"], "model_revision": qwen["revision"],
            "embedding_dimension": qwen["dimension"], "vector_dtype": "float32",
            "normalize_embeddings": qwen["normalize_embeddings"], "identity_hash": qwen["embedding_identity_hash"],
        },
        index_identity_hash=None,
        retrieval_config={"type": "tree_section_navigation", "downstream_of": "primary_html_structural_parse"},
        reranker_config={"enabled": False}, generation_model=None, split="dev",
        eval_set_version="phase2-v1", split_version="phase2-split-v1", split_sha256=split_summary["dev_sha256"],
        metrics={"filing_resolution_rate": rates["filing_resolution_rate"]["value"],
                 "section_found_rate": rates["section_found_rate"]["value"],
                 "scope_leak_rate": rates["scope_leak_rate"]["value"]},
        evaluation_source="internal_phase2", experiment_name="phase3_12_tree_section_navigation",
        run_kind="phase3_tree_section_navigation",
        notes=f"Task 3.12 filing/section navigation over {len(parsed_document_ids)} Task-2.8-parsed documents, "
              f"{len(section_found_flags)} section-navigation attempts.",
    )
    run_record_path = rl.write_run_record(run_record)
    print(f"[NAV] Task 2.11 run record written: {run_record_path}")

    payload = {
        "row_id": ROW_ID, "config_hash": config_hash, "run_id": run_record.run_id, "git_sha": git_sha(),
        "parsed_document_count": len(parsed_document_ids), "navigation_attempt_count": len(section_found_flags),
        "rates": rates, "per_document": per_document,
    }
    _write_json(CANDIDATE_RESULTS_DIR / f"{ROW_ID}.json", payload)

    print("[STAGE 9/9] Record ablation row and final result")
    baseline = _load_json(BASELINE_RESULT_PATH)
    corpus_doc_count = len(set(chunk_table.column("document_id").to_pylist()))
    row = p3n.build_nav_ablation_row(
        row_id=ROW_ID, config_hash=config_hash, run_id=run_record.run_id, git_sha=payload["git_sha"],
        eval_scope_sha256=baseline["phase3_config"]["phase3_dev_scope_sha256"],
        corpus_document_count=corpus_doc_count, chunk_count=EXPECTED_CHUNK_COUNT, chunk_config_hash=CHUNK_CONFIG_HASH,
        dense_repository=qwen["repository"], dense_revision=qwen["revision"],
        dense_embedding_identity_hash=qwen["embedding_identity_hash"], dense_index_identity_hash=qwen["index_identity_hash"],
        parsed_document_count=len(parsed_document_ids), navigation_attempt_count=len(section_found_flags),
        rates=rates,
        notes=f"Task 3.12: filing_resolution_rate={rates['filing_resolution_rate']['value']:.4f}, "
              f"section_found_rate={rates['section_found_rate']['value']:.4f}, "
              f"scope_leak_rate={rates['scope_leak_rate']['value']:.4f}.",
    )
    existing_rows = p3.load_ablation_table(ABLATION_TABLE_PATH)
    existing_rows = p3.upsert_row(existing_rows, row)
    p3.write_ablation_table(ABLATION_TABLE_PATH, existing_rows)
    print(f"Ablation table updated: {ABLATION_TABLE_PATH}")

    report = {
        "task": "3.12", "phase3_12_config_hash": config_hash, "phase3_12_config": config,
        "chunk_config_hash": CHUNK_CONFIG_HASH, "chunk_count": EXPECTED_CHUNK_COUNT,
        "corpus_document_count": corpus_doc_count,
        "parsed_document_count": len(parsed_document_ids), "navigation_attempt_count": len(section_found_flags),
        "rates": rates, "ablation_row": row,
        "limitations": [
            "PROJECT_EXECUTION.md's Task 3.12 example query ('Summarize Item 7 of this filing') has zero "
            "matching examples anywhere in the 1,932-question DEV corpus; formal evaluation here measures the "
            "navigation layer's own structural correctness/coverage against Task 2.8's parsed corpus instead "
            "of natural-language question answering (generation stays out of scope, same as every other Phase "
            "3 task).",
            f"Navigation coverage is bounded by Task 2.8's own HTML-parsing coverage: only {len(parsed_document_ids)} "
            f"of the corpus's {corpus_doc_count} documents have been parsed - an honest, pre-existing gap, not "
            "a new sampling decision by this task.",
            f"Skipped {skipped_no_submission} parsed documents with no matching submissions row and "
            f"{skipped_non_10k} with a non-10-K form.",
            "No retrieval, embedding call, reranking, CRAG gating, or generation in this path - a pure "
            "structural lookup over Task 2.8's already-computed section boundaries.",
        ],
        "next_task_readiness": (
            f"filing_resolution_rate={rates['filing_resolution_rate']['value']:.4f}, "
            f"section_found_rate={rates['section_found_rate']['value']:.4f}, "
            f"scope_leak_rate={rates['scope_leak_rate']['value']:.4f} (must be 0.0 - hard safety invariant)."
        ),
    }
    _write_json(FINAL_RESULT_PATH, report)
    print(f"Final Task 3.12 report written: {FINAL_RESULT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 3.12 - Phase 3 simple tree/section navigation.")
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
