"""Task 4.5 - serving-appropriate partitioned-Parquet export of the frozen
`data/xbrl.duckdb` `facts`/`submissions` tables.

`data/xbrl.duckdb` itself is untouched and remains the offline-analysis
source of truth (per PROJECT_EXECUTION.md's Task 4.5 wording: "Keep
xbrl.duckdb for offline analysis"). This script is a purely additive,
read-only-of-source, physical I/O reorganization for the ACTUAL measured
production query pattern - it never reimplements or bakes in
`src.eval.truth_contract.eligible_facts()`'s eligibility/dedup logic (a
frozen Task 2.1/2.2 decision this task does not reopen).

Measured query pattern (verified directly from the real code, not
assumed from PROJECT_EXECUTION.md's generic pre-Phase-3 wording): Task
3.10's `src.sql.xbrl_lookup.XbrlFactIndex` calls
`eligible_facts(con, [tag])` ONCE PER REGISTRY TAG (15 tags), each a
`WHERE f.tag IN (...)` full-table scan, then serves all
(cik, fiscal_year) lookups from an in-memory index - `cik`/`fiscal_year`
never appear in a SQL WHERE clause in the current production code path.
Both partitioning schemes are still built and honestly benchmarked here
(PROJECT_EXECUTION.md's own "such as CIK/year" wording is a real,
plausible future serving pattern - e.g. a per-company lookup endpoint -
even though it is not what today's code exercises), and the discrepancy
between the roadmap's example and the measured reality is recorded
rather than silently resolved.

Three partitioned artifacts, all built from the SAME frozen row scope
(facts whose `tag` is one of the 15 enabled `configs/eval_tags.yaml`
tags - "serving-appropriate" means scoped to what the one real consumer
actually reads, not a mirror of all 291,429 raw XBRL tags):

    facts_by_tag              - PARTITION_BY (tag)               15,852,990 rows
    facts_by_cik_fiscal_year  - PARTITION_BY (cik, fiscal_year)   (same rows)
    submissions_by_cik        - PARTITION_BY (cik)                218,166 rows (full table - small, no tag column)
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.artifacts.versioning import semantic_hash  # noqa: E402
from src.eval.tag_registry import get_registry, compute_registry_hash  # noqa: E402

FACTS_COLUMNS: tuple[str, ...] = (
    "adsh", "cik", "company", "form", "fiscal_year", "fp", "tag",
    "version", "ddate", "qtrs", "uom", "coreg", "segments", "value",
)
SUBMISSIONS_COLUMNS: tuple[str, ...] = (
    "adsh", "cik", "name", "form", "fiscal_year", "fp", "period", "filed",
)

SAMPLE_TAG_COUNT = 5
SAMPLE_CIK_YEAR_COUNT = 5
DIAGNOSTIC_QUERY_COUNT = 5  # small deliberately - see docs for rationale

CONFIG_RELATIVE_PATH = Path("configs") / "phase_4_5_xbrl_serving_export.json"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_4_5_xbrl_serving_export_summary.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def build_config() -> dict:
    registry = get_registry()
    return {
        "xbrl_serving_schema_version": 1,
        "source": "data/xbrl.duckdb",
        "eval_tag_registry_version": registry.version,
        "eval_tag_registry_hash": compute_registry_hash(registry),
        "facts_scope": "tag IN (enabled eval_tags.yaml tags)",
        "partition_schemes": {
            "facts_by_tag": ["tag"],
            "facts_by_cik_fiscal_year": ["cik", "fiscal_year"],
            "submissions_by_cik": ["cik"],
        },
        "parquet_format": "duckdb COPY ... (FORMAT PARQUET, PARTITION_BY (...))",
    }


def fingerprint_sql(table_expr: str, columns: tuple[str, ...]) -> str:
    cols_sql = ", ".join(columns)
    return (
        f"SELECT count(*) AS n, "
        f"sum(hash(({cols_sql}))) AS fp "
        f"FROM {table_expr}"
    )


def row_count_and_fingerprint(con, table_expr: str, columns: tuple[str, ...]) -> tuple[int, int]:
    n, fp = con.execute(fingerprint_sql(table_expr, columns)).fetchone()
    return n, fp


def export_partitioned(con, *, select_sql: str, partition_by: tuple[str, ...], out_dir: Path,
                        expected_row_count: int, columns: tuple[str, ...]) -> dict:
    """Safe create/reuse: if `out_dir` already contains files, verify its
    row count/fingerprint against the freshly-recomputed source before
    reusing - never silently overwrite a conflicting export. Builds fresh
    via DuckDB's native partitioned COPY otherwise."""
    already_has_files = out_dir.is_dir() and any(out_dir.rglob("*.parquet"))
    read_expr = f"read_parquet('{out_dir.as_posix()}/**/*.parquet', hive_partitioning=true)"

    if already_has_files:
        existing_n, existing_fp = row_count_and_fingerprint(con, read_expr, columns)
        source_n, source_fp = row_count_and_fingerprint(con, f"({select_sql})", columns)
        if existing_n != source_n or existing_fp != source_fp:
            raise SystemExit(
                f"FATAL: existing export at {out_dir} (rows={existing_n}, fp={existing_fp}) "
                f"does not match current source (rows={source_n}, fp={source_fp}) - "
                f"refusing to silently overwrite. Investigate manually."
            )
        return {"reused": True, "row_count": existing_n, "fingerprint": existing_fp}

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    partition_cols_sql = ", ".join(partition_by)
    con.execute(
        f"COPY ({select_sql}) TO '{out_dir.as_posix()}' "
        f"(FORMAT PARQUET, PARTITION_BY ({partition_cols_sql}), OVERWRITE_OR_IGNORE true)"
    )
    n, fp = row_count_and_fingerprint(con, read_expr, columns)
    if n != expected_row_count:
        raise SystemExit(f"FATAL: exported {out_dir} has {n} rows, expected {expected_row_count}")
    return {"reused": False, "row_count": n, "fingerprint": fp}


CIK_BATCH_SIZE = 250


def export_facts_by_cik_fiscal_year_batched(con, *, select_sql: str, out_dir: Path,
                                             expected_row_count: int, columns: tuple[str, ...],
                                             config_hash: str) -> dict:
    """A single COPY ... PARTITION_BY (cik, fiscal_year) over all
    64,457 (cik, fiscal_year) combinations hit a real, reproducible
    DuckDB out-of-memory error on this machine even after disabling
    insertion-order preservation and capping memory_limit (verified
    directly - see project_plan/PHASE4_XBRL_SERVING_REPRESENTATION.md).
    This batches the export by CIK ranges instead - each batch's COPY
    only ever touches a small slice of the 64,457 partitions - with a
    config/source-identity-bound `_export_state.json` checkpoint (same
    resumable pattern as Task 4.1/4.2/4.4's checkpoints) so an
    interrupted run skips already-completed batches on restart."""
    read_expr = f"read_parquet('{out_dir.as_posix()}/**/*.parquet', hive_partitioning=true)"
    already_has_files = out_dir.is_dir() and any(out_dir.rglob("*.parquet"))

    if already_has_files:
        existing_n, existing_fp = row_count_and_fingerprint(con, read_expr, columns)
        source_n, source_fp = row_count_and_fingerprint(con, f"({select_sql})", columns)
        if existing_n == source_n and existing_fp == source_fp:
            return {"reused": True, "row_count": existing_n, "fingerprint": existing_fp, "batches": None}

    checkpoint_path = out_dir.parent / (out_dir.name + "._export_state.json")
    ciks = [r[0] for r in con.execute(f"SELECT DISTINCT cik FROM ({select_sql}) ORDER BY cik").fetchall()]
    batches = [ciks[i:i + CIK_BATCH_SIZE] for i in range(0, len(ciks), CIK_BATCH_SIZE)]
    identity = {
        "config_hash": config_hash, "cik_batch_size": CIK_BATCH_SIZE,
        "total_ciks": len(ciks), "total_batches": len(batches),
    }

    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        for key, value in identity.items():
            if checkpoint.get(key) != value:
                raise SystemExit(
                    f"FATAL: existing checkpoint at {checkpoint_path} was built under a "
                    f"different identity ({key}={checkpoint.get(key)!r} != {value!r}) - refusing to resume."
                )
        completed = set(checkpoint["completed_batches"])
    else:
        if already_has_files:
            raise SystemExit(
                f"FATAL: {out_dir} already has files but no checkpoint exists and its "
                f"fingerprint does not match the current source - refusing to guess which "
                f"batches it contains. Investigate manually."
            )
        completed = set()

    out_dir.mkdir(parents=True, exist_ok=True)
    for i, batch in enumerate(batches):
        if i in completed:
            continue
        cik_list_sql = ",".join(str(c) for c in batch)
        con.execute(
            f"COPY (SELECT * FROM ({select_sql}) WHERE cik IN ({cik_list_sql})) TO '{out_dir.as_posix()}' "
            f"(FORMAT PARQUET, PARTITION_BY (cik, fiscal_year), OVERWRITE_OR_IGNORE true)"
        )
        completed.add(i)
        payload = dict(identity)
        payload["completed_batches"] = sorted(completed)
        tmp_path = checkpoint_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(checkpoint_path)
        print(f"  cik batch {i + 1}/{len(batches)} done ({len(batch)} ciks)", flush=True)

    n, fp = row_count_and_fingerprint(con, read_expr, columns)
    if n != expected_row_count:
        raise SystemExit(f"FATAL: exported {out_dir} has {n} rows, expected {expected_row_count}")
    return {"reused": False, "row_count": n, "fingerprint": fp, "batches": len(batches)}


def validate_partition_pruning_correctness(con, *, facts_by_tag_dir: Path, facts_by_cik_year_dir: Path,
                                            tags_sql: str,
                                            sample_tags: list[str], sample_cik_years: list[tuple[int, int]]) -> dict:
    """For each deterministic sample key, verifies the partitioned-Parquet
    read returns EXACTLY the same rows (via count+fingerprint) as the
    equivalent WHERE-filtered query against the live `facts` table -
    never just "fast", also *correct*. The live baseline always includes
    `AND tag IN ({tags_sql})` (the same 15-enabled-tag scope the export
    itself is restricted to) - comparing against an unscoped `facts` table
    (all 291,429 raw tags) would be an apples-to-oranges row-count
    mismatch by construction, not a real pruning-correctness bug (caught
    directly: the first version of this check raised exactly that false
    positive for every (cik, fiscal_year) sample before this scope was
    added)."""
    results = {"by_tag": [], "by_cik_fiscal_year": []}

    for tag in sample_tags:
        escaped = tag.replace("'", "''")
        live = row_count_and_fingerprint(con, f"(SELECT * FROM facts WHERE tag = '{escaped}')", FACTS_COLUMNS)
        parquet = row_count_and_fingerprint(
            con,
            f"(SELECT * FROM read_parquet('{facts_by_tag_dir.as_posix()}/**/*.parquet', "
            f"hive_partitioning=true) WHERE tag = '{escaped}')",
            FACTS_COLUMNS,
        )
        results["by_tag"].append({"tag": tag, "match": live == parquet, "live": live, "parquet": parquet})

    for cik, fiscal_year in sample_cik_years:
        live = row_count_and_fingerprint(
            con,
            f"(SELECT * FROM facts WHERE cik = {cik} AND fiscal_year = {fiscal_year} AND tag IN ({tags_sql}))",
            FACTS_COLUMNS,
        )
        parquet = row_count_and_fingerprint(
            con,
            f"(SELECT * FROM read_parquet('{facts_by_cik_year_dir.as_posix()}/**/*.parquet', "
            f"hive_partitioning=true) WHERE cik = {cik} AND fiscal_year = {fiscal_year})",
            FACTS_COLUMNS,
        )
        results["by_cik_fiscal_year"].append({
            "cik": cik, "fiscal_year": fiscal_year, "match": live == parquet, "live": live, "parquet": parquet,
        })

    all_match = all(r["match"] for r in results["by_tag"]) and all(r["match"] for r in results["by_cik_fiscal_year"])
    if not all_match:
        raise SystemExit(f"FATAL: partition-pruning correctness check failed: {results}")
    return results


def timed(con, sql: str) -> float:
    start = time.perf_counter()
    con.execute(sql).fetchall()
    return (time.perf_counter() - start) * 1000


def latency_diagnostic(con, *, facts_by_tag_dir: Path, facts_by_cik_year_dir: Path, tags_sql: str,
                        sample_tags: list[str], sample_cik_years: list[tuple[int, int]]) -> dict:
    """Smoke diagnostic (small n, this dev machine only) comparing the
    live single-DuckDB-file scan against BOTH partitioned-Parquet layouts
    for BOTH query shapes - including the "wrong" layout for each shape,
    to make the pruning benefit (and its absence when partitioned on the
    wrong column) visible rather than assumed."""

    def by_tag_ms(tag: str) -> dict:
        escaped = tag.replace("'", "''")
        return {
            "tag": tag,
            "live_duckdb_ms": timed(con, f"SELECT count(*), sum(value) FROM facts WHERE tag = '{escaped}'"),
            "parquet_by_tag_ms": timed(
                con,
                f"SELECT count(*), sum(value) FROM read_parquet("
                f"'{facts_by_tag_dir.as_posix()}/**/*.parquet', hive_partitioning=true) WHERE tag = '{escaped}'",
            ),
            "parquet_by_cik_fiscal_year_ms": timed(
                con,
                f"SELECT count(*), sum(value) FROM read_parquet("
                f"'{facts_by_cik_year_dir.as_posix()}/**/*.parquet', hive_partitioning=true) WHERE tag = '{escaped}'",
            ),
        }

    def by_cik_year_ms(cik: int, fiscal_year: int) -> dict:
        return {
            "cik": cik, "fiscal_year": fiscal_year,
            "live_duckdb_ms": timed(
                con,
                f"SELECT count(*), sum(value) FROM facts WHERE cik = {cik} AND fiscal_year = {fiscal_year} "
                f"AND tag IN ({tags_sql})",
            ),
            "parquet_by_cik_fiscal_year_ms": timed(
                con,
                f"SELECT count(*), sum(value) FROM read_parquet("
                f"'{facts_by_cik_year_dir.as_posix()}/**/*.parquet', hive_partitioning=true) "
                f"WHERE cik = {cik} AND fiscal_year = {fiscal_year}",
            ),
            "parquet_by_tag_ms": timed(
                con,
                f"SELECT count(*), sum(value) FROM read_parquet("
                f"'{facts_by_tag_dir.as_posix()}/**/*.parquet', hive_partitioning=true) "
                f"WHERE cik = {cik} AND fiscal_year = {fiscal_year}",
            ),
        }

    by_tag_results = [by_tag_ms(t) for t in sample_tags]
    by_cik_year_results = [by_cik_year_ms(c, y) for c, y in sample_cik_years]

    def summarize(results: list[dict], key: str) -> dict:
        values = sorted(r[key] for r in results)
        return {"n": len(values), "p50_ms": round(statistics.median(values), 2), "min_ms": round(min(values), 2), "max_ms": round(max(values), 2)}

    return {
        "label": "Phase 4.5 smoke diagnostic - not a production benchmark",
        "by_tag_query": {
            "samples": by_tag_results,
            "live_duckdb": summarize(by_tag_results, "live_duckdb_ms"),
            "parquet_by_tag": summarize(by_tag_results, "parquet_by_tag_ms"),
            "parquet_by_cik_fiscal_year (wrong layout for this query)": summarize(by_tag_results, "parquet_by_cik_fiscal_year_ms"),
        },
        "by_cik_fiscal_year_query": {
            "samples": by_cik_year_results,
            "live_duckdb": summarize(by_cik_year_results, "live_duckdb_ms"),
            "parquet_by_cik_fiscal_year": summarize(by_cik_year_results, "parquet_by_cik_fiscal_year_ms"),
            "parquet_by_tag (wrong layout for this query)": summarize(by_cik_year_results, "parquet_by_tag_ms"),
        },
    }


def main() -> int:
    build_start = time.monotonic()
    storage = get_storage()
    con = duckdb.connect(str(storage.xbrl_db), read_only=True)
    # facts_by_cik_fiscal_year has 64,457 partitions - a single COPY with
    # DuckDB's default preserve_insertion_order=true buffers per-partition
    # writers in a way that hit an out-of-memory error on this machine
    # (verified directly: "Out of Memory ... 24.9 GiB/25.0 GiB used").
    # Row order was never a project contract for this artifact (same
    # "do not rely on physical row order" precedent as Task 1.5's LanceDB
    # table), so disabling it is safe - this is DuckDB's own documented
    # fix for exactly this many-partition-write scenario.
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET memory_limit='6GB'")
    con.execute("SET threads=2")

    config = build_config()
    config_hash = semantic_hash(config)
    registry = get_registry()
    tags = registry.supported_tags()
    tags_sql = ",".join(f"'{t}'" for t in tags)
    facts_select_sql = f"SELECT * FROM facts WHERE tag IN ({tags_sql})"

    source_facts_n, source_facts_fp = row_count_and_fingerprint(con, f"({facts_select_sql})", FACTS_COLUMNS)
    source_submissions_n, source_submissions_fp = row_count_and_fingerprint(con, "submissions", SUBMISSIONS_COLUMNS)
    print(f"Source scope: {source_facts_n:,} facts rows (tag in {len(tags)} enabled registry tags), "
          f"{source_submissions_n:,} submissions rows")

    facts_by_tag_dir = storage.xbrl_serving_dir(config_hash, "facts_by_tag")
    facts_by_cik_year_dir = storage.xbrl_serving_dir(config_hash, "facts_by_cik_fiscal_year")
    submissions_by_cik_dir = storage.xbrl_serving_dir(config_hash, "submissions_by_cik")

    print("Exporting facts_by_tag ...")
    facts_by_tag_result = export_partitioned(
        con, select_sql=facts_select_sql, partition_by=("tag",), out_dir=facts_by_tag_dir,
        expected_row_count=source_facts_n, columns=FACTS_COLUMNS,
    )
    print("Exporting facts_by_cik_fiscal_year (CIK-batched)...")
    facts_by_cik_year_result = export_facts_by_cik_fiscal_year_batched(
        con, select_sql=facts_select_sql, out_dir=facts_by_cik_year_dir,
        expected_row_count=source_facts_n, columns=FACTS_COLUMNS, config_hash=config_hash,
    )
    print("Exporting submissions_by_cik ...")
    submissions_result = export_partitioned(
        con, select_sql="SELECT * FROM submissions", partition_by=("cik",), out_dir=submissions_by_cik_dir,
        expected_row_count=source_submissions_n, columns=SUBMISSIONS_COLUMNS,
    )

    for label, result in (("facts_by_tag", facts_by_tag_result), ("facts_by_cik_fiscal_year", facts_by_cik_year_result)):
        if result["fingerprint"] != source_facts_fp or result["row_count"] != source_facts_n:
            raise SystemExit(f"FATAL: {label} fingerprint/row-count mismatch against source facts scope")
    if submissions_result["fingerprint"] != source_submissions_fp or submissions_result["row_count"] != source_submissions_n:
        raise SystemExit("FATAL: submissions_by_cik fingerprint/row-count mismatch against source submissions table")

    build_time_s = time.monotonic() - build_start
    print(f"All 3 artifacts exported/verified. Fingerprint match: facts (both layouts) and submissions all agree "
          f"with the live source. Build time: {build_time_s:.2f}s")

    # Deterministic sample keys (evenly spaced, not arbitrary/random)
    sample_tags = sorted(tags)[::max(1, len(tags) // SAMPLE_TAG_COUNT)][:SAMPLE_TAG_COUNT]
    cik_year_rows = con.execute(
        f"SELECT DISTINCT cik, fiscal_year FROM facts WHERE tag IN ({tags_sql}) ORDER BY cik, fiscal_year"
    ).fetchall()
    step = max(1, len(cik_year_rows) // SAMPLE_CIK_YEAR_COUNT)
    sample_cik_years = cik_year_rows[::step][:SAMPLE_CIK_YEAR_COUNT]

    print("Validating partition-pruning correctness...")
    pruning_correctness = validate_partition_pruning_correctness(
        con, facts_by_tag_dir=facts_by_tag_dir, facts_by_cik_year_dir=facts_by_cik_year_dir, tags_sql=tags_sql,
        sample_tags=sample_tags, sample_cik_years=sample_cik_years,
    )
    print(f"  {len(sample_tags)} tag keys + {len(sample_cik_years)} (cik, fiscal_year) keys: all match live DuckDB")

    print("Running latency smoke diagnostic...")
    diagnostic = latency_diagnostic(
        con, facts_by_tag_dir=facts_by_tag_dir, facts_by_cik_year_dir=facts_by_cik_year_dir, tags_sql=tags_sql,
        sample_tags=sample_tags, sample_cik_years=sample_cik_years,
    )

    def dir_size(path: Path) -> int:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

    sizes = {
        "facts_by_tag_bytes": dir_size(facts_by_tag_dir),
        "facts_by_cik_fiscal_year_bytes": dir_size(facts_by_cik_year_dir),
        "submissions_by_cik_bytes": dir_size(submissions_by_cik_dir),
    }

    config_path = storage.repo_root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps({**config, "xbrl_serving_config_hash": config_hash}, indent=2) + "\n", encoding="utf-8")

    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "xbrl_serving_config_hash": config_hash,
        "enabled_tags": tags,
        "eval_tag_registry_hash": config["eval_tag_registry_hash"],
        "source_facts_row_count": source_facts_n,
        "source_submissions_row_count": source_submissions_n,
        "facts_by_tag": {**facts_by_tag_result, "dir": str(facts_by_tag_dir.relative_to(storage.repo_root).as_posix())},
        "facts_by_cik_fiscal_year": {**facts_by_cik_year_result, "dir": str(facts_by_cik_year_dir.relative_to(storage.repo_root).as_posix())},
        "submissions_by_cik": {**submissions_result, "dir": str(submissions_by_cik_dir.relative_to(storage.repo_root).as_posix())},
        "sizes_bytes": sizes,
        "build_runtime_seconds": round(build_time_s, 2),
        "partition_pruning_correctness": pruning_correctness,
        "latency_diagnostic": diagnostic,
    }
    summary_path = storage.repo_root / SUMMARY_RELATIVE_PATH
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
