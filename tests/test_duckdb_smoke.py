"""local_data smoke tests: the frozen data/ tree from Data Preparation.
Skips cleanly (not a failure) on a public clone without the 26 GB dataset;
fails if the data is present but something is actually broken. Opens
xbrl.duckdb read-only and never writes anything."""

import duckdb
import pytest

from src.storage import get_storage


@pytest.mark.local_data
def test_frozen_data_paths_exist_when_present():
    storage = get_storage()
    paths = {
        "msmarco": storage.msmarco_root,
        "edgar_corpus": storage.edgar_corpus_root,
        "raw_xbrl": storage.raw_xbrl_root,
        "primary_docs": storage.primary_docs_root,
        "xbrl_db": storage.xbrl_db,
    }
    missing = [name for name, p in paths.items() if not p.exists()]
    if missing:
        pytest.skip(f"local frozen data not fully available (missing: {missing})")

    assert storage.msmarco_root.is_dir()
    assert storage.edgar_corpus_root.is_dir()
    assert storage.raw_xbrl_root.is_dir()
    assert storage.primary_docs_root.is_dir()
    assert storage.xbrl_db.is_file()


@pytest.mark.local_data
def test_xbrl_duckdb_read_only_smoke():
    storage = get_storage()
    if not storage.xbrl_db.is_file():
        pytest.skip("local frozen XBRL database not available")

    con = duckdb.connect(str(storage.xbrl_db), read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        assert "facts" in tables
        assert "submissions" in tables

        # COUNT(*) on a columnar table answers from row-group metadata, not
        # a full value scan - cheap enough to also confirm the frozen fact
        # count is unchanged from DATA_READINESS_REPORT.md.
        n_facts = con.execute("SELECT count(*) FROM facts").fetchone()[0]
        assert n_facts == 90_685_753
    finally:
        con.close()
