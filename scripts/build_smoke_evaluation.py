"""Task 1.9 - build the 200-question Phase 1 smoke-evaluation dataset.

Reads the frozen Task 1.1 development-corpus manifest
(results/phase_1_1_development_corpus.json) and the frozen EDGAR-CORPUS
parquet (data/edgar_corpus/*.parquet, read-only) to deterministically
select 200 unique target filings (40 per category, 5 categories), render
one document-targeted question per filing from fixed templates, and write
a document-level smoke-evaluation dataset.

NOT the final benchmark. NOT chunk-level ground truth. Does not call
OpenRouter, does not run generation, does not compute doc_recall@10 (Task
1.10 owns that) - see project_plan/PHASE1_SMOKE_EVALUATION.md.

No network, no GPU, no LLM. DuckDB is used only to join the manifest's
1,500 document_ids against the frozen local EDGAR-CORPUS parquet files -
the same read-only join pattern already used by
scripts/normalize_development_corpus.py.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.storage import get_storage  # noqa: E402
from src.eval.smoke_dataset import (  # noqa: E402
    CATEGORY_ORDER,
    CATEGORY_SECTION_COLUMN,
    QUESTION_TEMPLATES,
    QUESTIONS_PER_CATEGORY,
    TARGET_QUESTION_COUNT,
    LABEL_GRANULARITY,
    RETRIEVAL_METRIC,
    TARGET_FORM_TYPE,
    selection_key,
    select_all_categories,
    build_question_record,
    assign_question_ids,
    compute_smoke_eval_sha256,
)

SCHEMA_VERSION = "1.0"
EXPECTED_MANIFEST_ROWS = 1500
EXPECTED_MANIFEST_SHA256 = "d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b"
EXPECTED_YEARS = {2016, 2017, 2018, 2019, 2020}

MANIFEST_RELATIVE_PATH = Path("results") / "phase_1_1_development_corpus.json"
NORMALIZATION_SUMMARY_RELATIVE_PATH = Path("results") / "phase_1_2_normalization_summary.json"
DATASET_RELATIVE_PATH = Path("results") / "phase_1_9_smoke_evaluation.json"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_1_9_smoke_evaluation_summary.json"
CONFIG_RELATIVE_PATH = Path("configs") / "phase_1_9_smoke_evaluation.json"

REQUIRED_SECTION_COLUMNS = tuple(sorted(set(CATEGORY_SECTION_COLUMN.values())))


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def load_and_verify_manifest(storage) -> dict:
    manifest_path = storage.repo_root / MANIFEST_RELATIVE_PATH
    storage.require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filings = manifest["filings"]

    if len(filings) != EXPECTED_MANIFEST_ROWS:
        raise SystemExit(
            f"BLOCKED - Task 1.1 development manifest changed unexpectedly: "
            f"expected {EXPECTED_MANIFEST_ROWS} rows, found {len(filings)}"
        )
    ids = [r["document_id"] for r in filings]
    if len(set(ids)) != len(ids):
        raise SystemExit("BLOCKED - Task 1.1 development manifest changed unexpectedly: duplicate document_id")

    blob = json.dumps(filings, sort_keys=True, separators=(",", ":")).encode("utf-8")
    recomputed = hashlib.sha256(blob).hexdigest()
    if recomputed != EXPECTED_MANIFEST_SHA256:
        raise SystemExit(
            f"BLOCKED - Task 1.1 development manifest changed unexpectedly: "
            f"recomputed development_manifest_sha256={recomputed} != expected {EXPECTED_MANIFEST_SHA256}"
        )

    years = {r["year"] for r in filings}
    if not years.issubset(EXPECTED_YEARS):
        raise SystemExit(f"BLOCKED - manifest contains years outside 2016-2020: {sorted(years - EXPECTED_YEARS)}")

    return manifest


def load_normalization_provenance(storage) -> tuple[str, str]:
    """Reads normalizer_version/normalization_build_sha256 from the tracked
    Task 1.2 summary - pure provenance for Task 1.9's question records,
    never recomputed from the (git-ignored, not guaranteed present)
    artifacts/normalized/ directory, so this script works on a fresh clone."""
    path = storage.repo_root / NORMALIZATION_SUMMARY_RELATIVE_PATH
    storage.require_file(path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    normalizer_version = summary["normalizer_version"]
    normalization_build_sha256 = summary["normalization_build_sha256"]
    if summary.get("development_manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise SystemExit("BLOCKED - Task 1.2 summary's development_manifest_sha256 does not match Task 1.1's")
    return normalizer_version, normalization_build_sha256


def verify_source_schema(storage) -> None:
    edgar_root = storage.edgar_corpus_root
    storage.require_dir(edgar_root)
    train_path = edgar_root / "train.parquet"
    storage.require_file(train_path)
    con = duckdb.connect()
    con.execute("PRAGMA disable_progress_bar")
    cols = {row[0] for row in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{train_path.as_posix()}') LIMIT 0"
    ).fetchall()}
    con.close()
    missing = [c for c in REQUIRED_SECTION_COLUMNS if c not in cols]
    if missing:
        raise SystemExit(f"BLOCKED - EDGAR-CORPUS parquet is missing required section columns: {missing}")


def resolve_source_rows(storage, filings: list[dict]) -> dict[str, dict]:
    """Same read-only union-of-splits join pattern as Task 1.2's
    resolve_source_rows() - resolves exactly the manifest's document_ids,
    cross-checks split/cik/year identity, and returns only the 5 category
    section columns (plus identity columns) needed here."""
    edgar_root = storage.edgar_corpus_root
    storage.require_dir(edgar_root)
    splits = {s: edgar_root / f"{s}.parquet" for s in ("train", "test", "validation")}
    existing = {s: p for s, p in splits.items() if p.exists()}
    if not existing:
        raise SystemExit("FATAL: no EDGAR-CORPUS split parquet files found")

    con = duckdb.connect()
    con.execute("PRAGMA disable_progress_bar")
    union_sql = " UNION ALL ".join(
        f"SELECT '{s}' AS split, * FROM read_parquet('{p.as_posix()}')" for s, p in existing.items()
    )
    con.execute(f"CREATE TEMP TABLE edgar AS SELECT * FROM ({union_sql})")
    con.execute("CREATE TEMP TABLE manifest_ids (document_id VARCHAR)")
    con.executemany("INSERT INTO manifest_ids VALUES (?)", [(r["document_id"],) for r in filings])

    match_counts = con.execute("""
        SELECT mi.document_id, count(e.filename) AS n
        FROM manifest_ids mi LEFT JOIN edgar e ON e.filename = mi.document_id
        GROUP BY mi.document_id HAVING count(e.filename) != 1
    """).fetchall()
    if match_counts:
        raise SystemExit(
            f"FATAL: {len(match_counts)} manifest rows do not map to exactly one EDGAR source row: "
            f"{match_counts[:5]}"
        )

    section_cols_sql = ", ".join(REQUIRED_SECTION_COLUMNS)
    rows = con.execute(f"""
        SELECT e.filename, e.split, e.cik, e.year, {section_cols_sql}
        FROM edgar e JOIN manifest_ids mi ON e.filename = mi.document_id
    """).fetchall()
    col_names = [d[0] for d in con.description]
    con.close()

    by_id: dict[str, dict] = {}
    for row in rows:
        record = dict(zip(col_names, row))
        by_id[record["filename"]] = record

    for r in filings:
        src = by_id.get(r["document_id"])
        if src is None:
            raise SystemExit(f"FATAL: manifest document_id not resolved: {r['document_id']}")
        if src["split"] != r["source_split"]:
            raise SystemExit(f"FATAL: split mismatch for {r['document_id']}")
        if int(src["cik"]) != r["cik"]:
            raise SystemExit(f"FATAL: cik mismatch for {r['document_id']}")
        if int(src["year"]) != r["year"]:
            raise SystemExit(f"FATAL: year mismatch for {r['document_id']}")

    return by_id


def validate_final_dataset(records: list[dict], filings_by_id: dict[str, dict], source_rows: dict[str, dict]) -> None:
    if len(records) != TARGET_QUESTION_COUNT:
        raise SystemExit(f"FATAL: expected {TARGET_QUESTION_COUNT} questions, built {len(records)}")

    question_ids = [r["question_id"] for r in records]
    if len(set(question_ids)) != TARGET_QUESTION_COUNT:
        raise SystemExit("FATAL: duplicate question_id")

    texts = [r["question"] for r in records]
    if len(set(texts)) != TARGET_QUESTION_COUNT:
        raise SystemExit("FATAL: duplicate question text")

    targets = [r["target_document_id"] for r in records]
    if len(set(targets)) != TARGET_QUESTION_COUNT:
        raise SystemExit("FATAL: duplicate target_document_id")

    counts: dict[str, int] = {}
    for r in records:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    for category in CATEGORY_ORDER:
        if counts.get(category) != QUESTIONS_PER_CATEGORY:
            raise SystemExit(f"FATAL: category {category!r} has {counts.get(category)} questions, expected {QUESTIONS_PER_CATEGORY}")

    for r in records:
        doc_id = r["target_document_id"]
        if doc_id not in filings_by_id:
            raise SystemExit(f"FATAL: target {doc_id} not in Task 1.1 manifest")
        manifest_row = filings_by_id[doc_id]
        if r["target_cik"] != manifest_row["cik"] or r["target_fiscal_year"] != manifest_row["year"]:
            raise SystemExit(f"FATAL: provenance mismatch for {doc_id}")
        if r["target_source_split"] != manifest_row["source_split"]:
            raise SystemExit(f"FATAL: source_split mismatch for {doc_id}")
        section_col = r["source_section_column"]
        section_text = source_rows[doc_id][section_col]
        if not (isinstance(section_text, str) and section_text.strip()):
            raise SystemExit(f"FATAL: assigned source section for {doc_id} is empty at validation time")
        if r["label_granularity"] != LABEL_GRANULARITY or r["retrieval_metric"] != RETRIEVAL_METRIC:
            raise SystemExit(f"FATAL: label contract mismatch for {doc_id}")
        if r["target_form_type"] != TARGET_FORM_TYPE:
            raise SystemExit(f"FATAL: target_form_type mismatch for {doc_id}")
        if "target_chunk_id" in r or "accession" in r or "expected_answer" in r or "answer_span" in r:
            raise SystemExit(f"FATAL: record for {doc_id} contains a disallowed fabricated field")


def write_or_verify_dataset(storage, dataset: dict, path: Path) -> None:
    """Idempotent-rewrite policy matching Task 1.3's chunk-artifact
    convention: if the file already exists, its stored smoke_eval_sha256
    must match this build's value (an identical rebuild is fine); a
    conflicting existing dataset is refused, never silently overwritten."""
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("smoke_eval_sha256") != dataset["smoke_eval_sha256"]:
            raise SystemExit(
                f"FATAL: {path} already exists with a different smoke_eval_sha256 "
                f"({existing.get('smoke_eval_sha256')} != {dataset['smoke_eval_sha256']}) - "
                f"refusing to silently overwrite a conflicting Task 1.9 artifact. STOP AND ASK before proceeding."
            )
    storage.ensure_dir(path.parent)
    path.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    storage = get_storage()

    manifest = load_and_verify_manifest(storage)
    filings = manifest["filings"]
    filings_by_id = {r["document_id"]: r for r in filings}
    normalizer_version, normalization_build_sha256 = load_normalization_provenance(storage)

    verify_source_schema(storage)
    source_rows = resolve_source_rows(storage, filings)

    selected_by_category, candidate_counts = select_all_categories(filings, source_rows)

    raw_records = []
    for category in CATEGORY_ORDER:
        for row in selected_by_category[category]:
            raw_records.append(build_question_record(
                category, row, source_rows,
                development_manifest_sha256=manifest["development_manifest_sha256"],
                normalizer_version=normalizer_version,
                normalization_build_sha256=normalization_build_sha256,
            ))

    records = assign_question_ids(raw_records)
    validate_final_dataset(records, filings_by_id, source_rows)
    smoke_eval_sha256 = compute_smoke_eval_sha256(records)

    dataset = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "development_manifest_sha256": manifest["development_manifest_sha256"],
        "normalizer_version": normalizer_version,
        "normalization_build_sha256": normalization_build_sha256,
        "label_granularity": LABEL_GRANULARITY,
        "retrieval_metric": RETRIEVAL_METRIC,
        "question_generation_method": "deterministic_offline_template",
        "smoke_eval_sha256": smoke_eval_sha256,
        "question_count": len(records),
        "questions": records,
    }
    dataset_path = storage.repo_root / DATASET_RELATIVE_PATH
    write_or_verify_dataset(storage, dataset, dataset_path)

    year_counts: dict[int, int] = {}
    cik_counts: dict[int, int] = {}
    unique_companies = set()
    for r in records:
        year_counts[r["target_fiscal_year"]] = year_counts.get(r["target_fiscal_year"], 0) + 1
        cik_counts[r["target_cik"]] = cik_counts.get(r["target_cik"], 0) + 1
        unique_companies.add(r["target_company"])

    selected_counts = {c: len(selected_by_category[c]) for c in CATEGORY_ORDER}

    config = {
        "schema_version": SCHEMA_VERSION,
        "target_question_count": TARGET_QUESTION_COUNT,
        "questions_per_category": QUESTIONS_PER_CATEGORY,
        "category_order": list(CATEGORY_ORDER),
        "category_section_column": CATEGORY_SECTION_COLUMN,
        "question_templates": QUESTION_TEMPLATES,
        "selection_algorithm": (
            "For each category in category_order: build the eligible candidate pool "
            "(manifest rows whose assigned EDGAR-CORPUS section column is a non-null, "
            "non-empty, non-whitespace-only string), sort by ascending selection_key, "
            "skip any document_id already selected by an earlier category, take the "
            "first questions_per_category."
        ),
        "selection_key_format": "sha256(category + '\\0' + document_id), hex digest, ascending",
        "label_granularity": LABEL_GRANULARITY,
        "retrieval_metric": RETRIEVAL_METRIC,
        "input_manifest": str(MANIFEST_RELATIVE_PATH.as_posix()),
        "development_manifest_sha256": manifest["development_manifest_sha256"],
    }
    config_path = storage.repo_root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dataset["created_at_utc"],
        "question_count": len(records),
        "unique_question_count": len({r["question"] for r in records}),
        "unique_target_document_count": len({r["target_document_id"] for r in records}),
        "category_candidate_counts": candidate_counts,
        "category_selected_counts": selected_counts,
        "year_distribution": {str(k): v for k, v in sorted(year_counts.items())},
        "unique_cik_count": len(cik_counts),
        "unique_company_count": len(unique_companies),
        "max_questions_per_cik": max(cik_counts.values()),
        "development_manifest_sha256": manifest["development_manifest_sha256"],
        "normalizer_version": normalizer_version,
        "normalization_build_sha256": normalization_build_sha256,
        "label_granularity": LABEL_GRANULARITY,
        "retrieval_metric": RETRIEVAL_METRIC,
        "question_generation_method": "deterministic_offline_template",
        "selection_algorithm": "sha256_ascending_first_n_per_category",
        "smoke_eval_sha256": smoke_eval_sha256,
        "manual_inspection_count": 15,
    }
    summary_path = storage.repo_root / SUMMARY_RELATIVE_PATH
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Manifest verified: {len(filings)} rows, checksum OK")
    print(f"Built {len(records)} questions across {len(CATEGORY_ORDER)} categories")
    for category in CATEGORY_ORDER:
        print(f"  {category}: candidates={candidate_counts[category]} selected={selected_counts[category]}")
    print(f"smoke_eval_sha256: {smoke_eval_sha256}")
    print(f"Dataset written to: {dataset_path}")
    print(f"Config written to: {config_path}")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
