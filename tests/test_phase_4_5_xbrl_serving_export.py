"""Tests for scripts/export_xbrl_serving.py (Task 4.5).

Uses a tiny synthetic in-memory DuckDB table and pytest tmp_path
throughout - never touches the real 90.7M-row data/xbrl.duckdb. The real
export is scripts/export_xbrl_serving.py's own run, not a unit test.
"""

import json

import duckdb
import pytest

import scripts.export_xbrl_serving as m

FACTS_COLUMNS = m.FACTS_COLUMNS


def _synthetic_con():
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE facts AS SELECT * FROM (VALUES
            ('a1', 1, 'C1', '10-K', 2018, 'FY', 'Assets', 'us-gaap/2018', '2018-12-31', 0, 'USD', NULL, NULL, 100.0),
            ('a1', 1, 'C1', '10-K', 2018, 'FY', 'Liabilities', 'us-gaap/2018', '2018-12-31', 0, 'USD', NULL, NULL, 40.0),
            ('a2', 2, 'C2', '10-K', 2019, 'FY', 'Assets', 'us-gaap/2019', '2019-12-31', 0, 'USD', NULL, NULL, 200.0),
            ('a3', 3, 'C3', '10-K', 2019, 'FY', 'Assets', 'us-gaap/2019', '2019-12-31', 0, 'USD', NULL, NULL, 300.0),
            ('a4', 4, 'C4', '10-K', 2020, 'FY', 'Revenues', 'us-gaap/2020', '2020-12-31', 4, 'USD', NULL, NULL, 400.0)
        ) AS v(adsh, cik, company, form, fiscal_year, fp, tag, version, ddate, qtrs, uom, coreg, segments, value)
    """)
    con.execute("""
        CREATE TABLE submissions AS SELECT * FROM (VALUES
            ('a1', 1, 'C1', '10-K', 2018, 'FY', '2018-12-31', '2019-02-01'),
            ('a2', 2, 'C2', '10-K', 2019, 'FY', '2019-12-31', '2020-02-01'),
            ('a3', 3, 'C3', '10-K', 2019, 'FY', '2019-12-31', '2020-02-01'),
            ('a4', 4, 'C4', '10-K', 2020, 'FY', '2020-12-31', '2021-02-01')
        ) AS v(adsh, cik, name, form, fiscal_year, fp, period, filed)
    """)
    return con


# ------------------------------------------------------- fingerprinting

def test_fingerprint_matches_for_identical_data():
    con = _synthetic_con()
    n1, fp1 = m.row_count_and_fingerprint(con, "facts", FACTS_COLUMNS)
    n2, fp2 = m.row_count_and_fingerprint(con, "(SELECT * FROM facts)", FACTS_COLUMNS)
    assert n1 == n2 == 5
    assert fp1 == fp2


def test_fingerprint_differs_for_different_data():
    con = _synthetic_con()
    n_all, fp_all = m.row_count_and_fingerprint(con, "facts", FACTS_COLUMNS)
    n_subset, fp_subset = m.row_count_and_fingerprint(con, "(SELECT * FROM facts WHERE tag = 'Assets')", FACTS_COLUMNS)
    assert n_subset < n_all
    assert fp_subset != fp_all


# ------------------------------------------------------- export_partitioned

def test_export_partitioned_creates_expected_row_count(tmp_path):
    con = _synthetic_con()
    out_dir = tmp_path / "facts_by_tag"
    result = m.export_partitioned(
        con, select_sql="SELECT * FROM facts", partition_by=("tag",), out_dir=out_dir,
        expected_row_count=5, columns=FACTS_COLUMNS,
    )
    assert result["reused"] is False
    assert result["row_count"] == 5
    assert (out_dir / "tag=Assets").is_dir()
    assert (out_dir / "tag=Liabilities").is_dir()
    assert (out_dir / "tag=Revenues").is_dir()


def test_export_partitioned_reuses_matching_existing_export(tmp_path):
    con = _synthetic_con()
    out_dir = tmp_path / "facts_by_tag"
    first = m.export_partitioned(
        con, select_sql="SELECT * FROM facts", partition_by=("tag",), out_dir=out_dir,
        expected_row_count=5, columns=FACTS_COLUMNS,
    )
    second = m.export_partitioned(
        con, select_sql="SELECT * FROM facts", partition_by=("tag",), out_dir=out_dir,
        expected_row_count=5, columns=FACTS_COLUMNS,
    )
    assert first["reused"] is False
    assert second["reused"] is True
    assert second["row_count"] == first["row_count"]
    assert second["fingerprint"] == first["fingerprint"]


def test_export_partitioned_rejects_conflicting_existing_export(tmp_path):
    con = _synthetic_con()
    out_dir = tmp_path / "facts_by_tag"
    m.export_partitioned(
        con, select_sql="SELECT * FROM facts WHERE tag = 'Assets'", partition_by=("tag",), out_dir=out_dir,
        expected_row_count=3, columns=FACTS_COLUMNS,
    )
    # Same directory, but the source query now scopes different rows -
    # must refuse to silently overwrite.
    with pytest.raises(SystemExit, match="does not match current source"):
        m.export_partitioned(
            con, select_sql="SELECT * FROM facts WHERE tag = 'Liabilities'", partition_by=("tag",), out_dir=out_dir,
            expected_row_count=1, columns=FACTS_COLUMNS,
        )


# --------------------------------------------- batched cik/fiscal_year export

def test_batched_export_creates_expected_row_count_and_checkpoint(tmp_path):
    con = _synthetic_con()
    out_dir = tmp_path / "facts_by_cik_fiscal_year"
    result = m.export_facts_by_cik_fiscal_year_batched(
        con, select_sql="SELECT * FROM facts", out_dir=out_dir, expected_row_count=5,
        columns=FACTS_COLUMNS, config_hash="deadbeef" * 8,
    )
    assert result["reused"] is False
    assert result["row_count"] == 5
    checkpoint_path = out_dir.parent / (out_dir.name + "._export_state.json")
    assert checkpoint_path.is_file()
    checkpoint = json.loads(checkpoint_path.read_text())
    assert checkpoint["total_ciks"] == 4  # ciks 1,2,3,4
    assert len(checkpoint["completed_batches"]) == checkpoint["total_batches"]


def test_batched_export_resumes_from_partial_checkpoint(tmp_path, monkeypatch):
    con = _synthetic_con()
    out_dir = tmp_path / "facts_by_cik_fiscal_year"
    monkeypatch.setattr(m, "CIK_BATCH_SIZE", 1)  # force multiple small batches (4 ciks -> 4 batches)

    result = m.export_facts_by_cik_fiscal_year_batched(
        con, select_sql="SELECT * FROM facts", out_dir=out_dir, expected_row_count=5,
        columns=FACTS_COLUMNS, config_hash="deadbeef" * 8,
    )
    assert result["batches"] == 4

    # Simulate an interrupted run: drop the last completed batch from the
    # checkpoint and delete that batch's data, then rerun - only the
    # missing batch's data should be rebuilt, not everything.
    checkpoint_path = out_dir.parent / (out_dir.name + "._export_state.json")
    checkpoint = json.loads(checkpoint_path.read_text())
    checkpoint["completed_batches"] = checkpoint["completed_batches"][:-1]
    checkpoint_path.write_text(json.dumps(checkpoint))

    resumed = m.export_facts_by_cik_fiscal_year_batched(
        con, select_sql="SELECT * FROM facts", out_dir=out_dir, expected_row_count=5,
        columns=FACTS_COLUMNS, config_hash="deadbeef" * 8,
    )
    assert resumed["row_count"] == 5  # final state is still fully correct


def test_batched_export_rejects_mismatched_checkpoint_identity(tmp_path):
    # A checkpoint on disk (e.g. from an interrupted run under a different
    # config/batch-size) must never be silently resumed onto - out_dir has
    # no parquet files yet, so the fingerprint-based quick-reuse path is
    # never reached; only the checkpoint identity check applies.
    con = _synthetic_con()
    out_dir = tmp_path / "facts_by_cik_fiscal_year"
    out_dir.mkdir(parents=True)
    checkpoint_path = out_dir.parent / (out_dir.name + "._export_state.json")
    checkpoint_path.write_text(json.dumps({
        "config_hash": "some_other_config_hash",
        "cik_batch_size": m.CIK_BATCH_SIZE,
        "total_ciks": 4,
        "total_batches": 1,
        "completed_batches": [],
    }))
    with pytest.raises(SystemExit, match="different identity"):
        m.export_facts_by_cik_fiscal_year_batched(
            con, select_sql="SELECT * FROM facts", out_dir=out_dir, expected_row_count=5,
            columns=FACTS_COLUMNS, config_hash="a" * 64,
        )


# ------------------------------------------------------- pruning correctness

def test_partition_pruning_correctness_passes_for_matching_export(tmp_path):
    con = _synthetic_con()
    tags_sql = "'Assets','Liabilities','Revenues'"
    facts_by_tag_dir = tmp_path / "facts_by_tag"
    facts_by_cik_year_dir = tmp_path / "facts_by_cik_fiscal_year"
    select_sql = f"SELECT * FROM facts WHERE tag IN ({tags_sql})"
    m.export_partitioned(con, select_sql=select_sql, partition_by=("tag",), out_dir=facts_by_tag_dir,
                          expected_row_count=5, columns=FACTS_COLUMNS)
    m.export_partitioned(con, select_sql=select_sql, partition_by=("cik", "fiscal_year"), out_dir=facts_by_cik_year_dir,
                          expected_row_count=5, columns=FACTS_COLUMNS)

    result = m.validate_partition_pruning_correctness(
        con, facts_by_tag_dir=facts_by_tag_dir, facts_by_cik_year_dir=facts_by_cik_year_dir, tags_sql=tags_sql,
        sample_tags=["Assets"], sample_cik_years=[(1, 2018)],
    )
    assert all(r["match"] for r in result["by_tag"])
    assert all(r["match"] for r in result["by_cik_fiscal_year"])


def test_partition_pruning_correctness_catches_unscoped_live_query_bug(tmp_path):
    # Regression guard for the real bug hit during Task 4.5 development:
    # comparing a TAG-SCOPED export against an UNSCOPED live query for the
    # (cik, fiscal_year) branch produces a false "mismatch" because the
    # live side legitimately has more rows (all tags) than the export
    # (only the enabled subset) - tags_sql must be applied to the live
    # query too.
    con = _synthetic_con()
    tags_sql = "'Assets'"  # deliberately excludes 'Liabilities', which cik=1 also has
    facts_by_tag_dir = tmp_path / "facts_by_tag"
    facts_by_cik_year_dir = tmp_path / "facts_by_cik_fiscal_year"
    select_sql = f"SELECT * FROM facts WHERE tag IN ({tags_sql})"
    m.export_partitioned(con, select_sql=select_sql, partition_by=("tag",), out_dir=facts_by_tag_dir,
                          expected_row_count=3, columns=FACTS_COLUMNS)
    m.export_partitioned(con, select_sql=select_sql, partition_by=("cik", "fiscal_year"), out_dir=facts_by_cik_year_dir,
                          expected_row_count=3, columns=FACTS_COLUMNS)

    # cik=1, fiscal_year=2018 has both Assets and Liabilities rows in the
    # source, but the export only contains Assets - the correctly-scoped
    # check must still pass (comparing like-for-like).
    result = m.validate_partition_pruning_correctness(
        con, facts_by_tag_dir=facts_by_tag_dir, facts_by_cik_year_dir=facts_by_cik_year_dir, tags_sql=tags_sql,
        sample_tags=["Assets"], sample_cik_years=[(1, 2018)],
    )
    assert result["by_cik_fiscal_year"][0]["match"] is True
    assert result["by_cik_fiscal_year"][0]["live"][0] == 1  # only the Assets row, not both


# ------------------------------------------------------- config

def test_build_config_includes_registry_hash():
    config = m.build_config()
    assert config["xbrl_serving_schema_version"] == 1
    assert "eval_tag_registry_hash" in config
    assert config["partition_schemes"]["facts_by_tag"] == ["tag"]
    assert config["partition_schemes"]["facts_by_cik_fiscal_year"] == ["cik", "fiscal_year"]


# --------------------------------------------------- real artifact (local_data)

@pytest.mark.local_data
def test_real_xbrl_serving_export_row_counts():
    from src.storage import get_storage

    storage = get_storage()
    summary_path = storage.repo_root / m.SUMMARY_RELATIVE_PATH
    if not summary_path.is_file():
        pytest.skip(f"Task 4.5 export summary not present at {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    config_hash = summary["xbrl_serving_config_hash"]

    facts_by_tag_dir = storage.xbrl_serving_dir(config_hash, "facts_by_tag")
    facts_by_cik_year_dir = storage.xbrl_serving_dir(config_hash, "facts_by_cik_fiscal_year")
    submissions_dir = storage.xbrl_serving_dir(config_hash, "submissions_by_cik")
    if not facts_by_tag_dir.is_dir():
        pytest.skip(f"Task 4.5 real export artifact not present at {facts_by_tag_dir}")

    import duckdb as duckdb_module
    con = duckdb_module.connect()
    n_tag = con.execute(
        f"SELECT count(*) FROM read_parquet('{facts_by_tag_dir.as_posix()}/**/*.parquet', hive_partitioning=true)"
    ).fetchone()[0]
    n_cik_year = con.execute(
        f"SELECT count(*) FROM read_parquet('{facts_by_cik_year_dir.as_posix()}/**/*.parquet', hive_partitioning=true)"
    ).fetchone()[0]
    n_submissions = con.execute(
        f"SELECT count(*) FROM read_parquet('{submissions_dir.as_posix()}/**/*.parquet', hive_partitioning=true)"
    ).fetchone()[0]

    assert n_tag == summary["facts_by_tag"]["row_count"] == summary["source_facts_row_count"]
    assert n_cik_year == summary["facts_by_cik_fiscal_year"]["row_count"] == summary["source_facts_row_count"]
    assert n_submissions == summary["submissions_by_cik"]["row_count"] == summary["source_submissions_row_count"]
