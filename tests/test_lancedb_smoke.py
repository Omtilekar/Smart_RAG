"""Portable LanceDB smoke test - proves the installed lancedb + pyarrow +
Python 3.11 versions work together. Uses only pytest's tmp_path; never
touches the real project index (artifacts/indexes/) and builds no
embeddings."""

import lancedb
import pyarrow as pa


def test_lancedb_tiny_roundtrip(tmp_path):
    db = lancedb.connect(str(tmp_path / "lancedb_smoke"))
    data = pa.table({"id": [1, 2, 3], "vector": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]})
    table = db.create_table("smoke", data=data)

    assert table.count_rows() == 3

    arrow_tbl = table.to_arrow()
    assert set(arrow_tbl.column("id").to_pylist()) == {1, 2, 3}

    results = table.search([0.1, 0.2]).limit(2).to_arrow()
    assert results.num_rows == 2
