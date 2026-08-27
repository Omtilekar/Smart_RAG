"""Download EDGAR-CORPUS (config 'full') from the parquet mirror.

c3po-ai/edgar-corpus ships a custom loading script (edgar-corpus.py), same
as the deprecated eloukas/edgar-corpus - `datasets.load_dataset` either
refuses it (trust_remote_code) or is incompatible on newer `datasets`
releases. We bypass the script entirely and pull HF's auto-converted
parquet mirror (`refs/convert/parquet`) directly via the datasets-server
API, which is what actually backs the dataset viewer.

Tables are NOT in this dataset - EDGAR-CORPUS strips them, keeping only
section text (section_1 .. section_15). It's useful for vector/BM25
retrieval text but not for tree navigation over tabular data.

Usage:
    python -m src.ingest.fetch_edgar_corpus
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb
import requests

from .common import STORAGE_ROOT, setup_logging

log = logging.getLogger(__name__)

REPO_ID = "c3po-ai/edgar-corpus"
PARQUET_API = "https://datasets-server.huggingface.co/parquet"
SPLITS = ("train", "test", "validation")


def list_parquet_files(config: str) -> dict[str, list[dict]]:
    resp = requests.get(PARQUET_API, params={"dataset": REPO_ID, "config": config}, timeout=60)
    resp.raise_for_status()
    files = [f for f in resp.json()["parquet_files"] if f["config"] == config]
    by_split: dict[str, list[dict]] = {}
    for f in files:
        by_split.setdefault(f["split"], []).append(f)
    for split in by_split:
        by_split[split].sort(key=lambda f: f["filename"])
    return by_split


def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        log.info("%s already present, skipping", dest.name)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)
        tmp.replace(dest)
        log.info("%s downloaded (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=STORAGE_ROOT)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(args.verbose)

    out_dir = args.root / "edgar_corpus"
    shard_dir = out_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)

    by_split = list_parquet_files("full")
    log.info("config 'full': %s", ", ".join(f"{s}={len(fs)} shards" for s, fs in by_split.items()))

    con = duckdb.connect()
    split_paths: dict[str, Path] = {}

    for split, files in by_split.items():
        local_shards = []
        for f in files:
            dest = shard_dir / split / f["filename"]
            download_file(f["url"], dest)
            local_shards.append(dest)

        merged = out_dir / f"{split}.parquet"
        split_paths[split] = merged
        if merged.exists():
            log.info("%s already merged, skipping", merged.name)
            continue
        glob = str(shard_dir / split / "*.parquet").replace("'", "''")
        merged_sql = str(merged).replace("'", "''")
        con.execute(f"COPY (SELECT * FROM read_parquet('{glob}')) TO '{merged_sql}' (FORMAT PARQUET)")
        log.info("%s merged from %d shards", merged.name, len(local_shards))

    # ---- report ----
    print("\nPer-split row counts:")
    total_rows = 0
    for split in SPLITS:
        n = con.execute(f"SELECT count(*) FROM read_parquet('{split_paths[split]}')").fetchone()[0]
        total_rows += n
        print(f"  {split:<12} {n:,}")
    print(f"  {'total':<12} {total_rows:,}")

    union_sql = " UNION ALL ".join(
        f"SELECT * FROM read_parquet('{split_paths[s]}')" for s in SPLITS
    )
    distinct_filings = con.execute(f"SELECT count(DISTINCT filename) FROM ({union_sql})").fetchone()[0]
    distinct_ciks = con.execute(f"SELECT count(DISTINCT cik) FROM ({union_sql})").fetchone()[0]
    year_range = con.execute(f"SELECT min(year), max(year) FROM ({union_sql})").fetchone()
    print(f"\ndistinct filings (deduped across splits): {distinct_filings:,}")
    print(f"distinct CIKs: {distinct_ciks:,}")
    print(f"year range: {year_range[0]} - {year_range[1]}")

    print("\nPer-section fill rate (non-empty / non-null), across all splits:")
    section_cols = [f"section_{i}" for i in range(1, 16)]
    fill_sql = ", ".join(
        f"sum(CASE WHEN {c} IS NOT NULL AND length(trim({c})) > 0 THEN 1 ELSE 0 END) AS {c}_n"
        for c in section_cols
    )
    row = con.execute(f"SELECT {fill_sql}, count(*) AS total FROM ({union_sql})").fetchone()
    total = row[-1]
    for i, c in enumerate(section_cols):
        n = row[i]
        print(f"  {c:<12} {n:>7,} / {total:,}  ({n/total:.1%})")

    print(f"\nTotal on-disk size (merged): "
          f"{sum(split_paths[s].stat().st_size for s in SPLITS) / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
