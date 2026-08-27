"""Download MS MARCO (via the BeIR mirror) for the benchmark track.

This is not the project corpus - it exists only to verify the retrieval
and eval pipeline against published baselines before trusting it on SEC
filings.

Source repos (verified against the live Hub, not the loading-script
versions which are deprecated on newer `datasets`):
  BeIR/msmarco        corpus/corpus-00000-of-00001.parquet  (_id, title, text)
  BeIR/msmarco        queries/queries-00000-of-00001.parquet
  BeIR/msmarco-qrels  train.tsv / dev.tsv / test.tsv         (query-id, corpus-id, score)

IDs are a real gotcha: corpus/queries `_id` is a VARCHAR that happens to
look like an integer; qrels `query-id`/`corpus-id` are int64. Joining
without casting silently returns zero rows.

Usage:
    python -m src.ingest.fetch_msmarco
    python -m src.ingest.fetch_msmarco --limit-corpus 100000   # dev
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb
from huggingface_hub import hf_hub_download

from .common import STORAGE_ROOT, setup_logging

log = logging.getLogger(__name__)

MSMARCO_REPO = "BeIR/msmarco"
QRELS_REPO = "BeIR/msmarco-qrels"

# BeIR/msmarco-qrels ships plain TSVs, not named dataset splits. "dev" is the
# conventional alias for "validation" - HF's own split-inference rules treat
# them as synonyms - so that's the mapping used for our output filenames.
QRELS_FILES = {"train": "train.tsv", "validation": "dev.tsv", "test": "test.tsv"}


def fetch_hf_file(repo_id: str, filename: str) -> Path:
    return Path(hf_hub_download(repo_id=repo_id, filename=filename, repo_type="dataset"))


def download_corpus(out_dir: Path, limit: int | None, con: duckdb.DuckDBPyConnection) -> Path:
    dest = out_dir / "corpus.parquet"
    if dest.exists():
        log.info("%s already present, skipping", dest.name)
        return dest
    log.info("downloading BeIR/msmarco corpus parquet (~1.6 GB)")
    src = fetch_hf_file(MSMARCO_REPO, "corpus/corpus-00000-of-00001.parquet")
    src_sql = str(src).replace("'", "''")
    dest_sql = str(dest).replace("'", "''")
    if limit:
        con.execute(f"COPY (SELECT * FROM read_parquet('{src_sql}') LIMIT {int(limit)}) "
                    f"TO '{dest_sql}' (FORMAT PARQUET)")
    else:
        con.execute(f"COPY (SELECT * FROM read_parquet('{src_sql}')) TO '{dest_sql}' (FORMAT PARQUET)")
    return dest


def download_queries(out_dir: Path, con: duckdb.DuckDBPyConnection) -> Path:
    dest = out_dir / "queries.parquet"
    if dest.exists():
        log.info("%s already present, skipping", dest.name)
        return dest
    src = fetch_hf_file(MSMARCO_REPO, "queries/queries-00000-of-00001.parquet")
    src_sql = str(src).replace("'", "''")
    dest_sql = str(dest).replace("'", "''")
    con.execute(f"COPY (SELECT * FROM read_parquet('{src_sql}')) TO '{dest_sql}' (FORMAT PARQUET)")
    return dest


def download_qrels(out_dir: Path, con: duckdb.DuckDBPyConnection) -> dict[str, Path]:
    paths = {}
    for split, fname in QRELS_FILES.items():
        dest = out_dir / f"qrels_{split}.parquet"
        paths[split] = dest
        if dest.exists():
            log.info("%s already present, skipping", dest.name)
            continue
        src = fetch_hf_file(QRELS_REPO, fname)
        src_sql = str(src).replace("'", "''")
        dest_sql = str(dest).replace("'", "''")
        con.execute(
            f"COPY (SELECT * FROM read_csv('{src_sql}', delim='\t', header=true, "
            f"columns={{'query-id': 'BIGINT', 'corpus-id': 'BIGINT', 'score': 'INTEGER'}})) "
            f"TO '{dest_sql}' (FORMAT PARQUET)"
        )
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=STORAGE_ROOT)
    ap.add_argument("--limit-corpus", type=int, default=None,
                     help="only keep first N corpus rows (development)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(args.verbose)

    out_dir = args.root / "msmarco"
    out_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()

    corpus_path = download_corpus(out_dir, args.limit_corpus, con)
    queries_path = download_queries(out_dir, con)
    qrels_paths = download_qrels(out_dir, con)

    n_corpus = con.execute(f"SELECT count(*) FROM read_parquet('{corpus_path}')").fetchone()[0]
    n_queries = con.execute(f"SELECT count(*) FROM read_parquet('{queries_path}')").fetchone()[0]
    print(f"\ncorpus:  {n_corpus:,} rows  ({corpus_path})")
    print(f"queries: {n_queries:,} rows  ({queries_path})")

    print("\nqrels:")
    for split, path in qrels_paths.items():
        n_rows = con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
        n_q = con.execute(f'SELECT count(DISTINCT "query-id") FROM read_parquet(\'{path}\')').fetchone()[0]
        print(f"  {split:<10} {n_rows:>10,} rows   {n_q:>8,} distinct queries   ({path.name})")

    dev_small_target = 6980
    validation_n_q = con.execute(
        f'SELECT count(DISTINCT "query-id") FROM read_parquet(\'{qrels_paths["validation"]}\')'
    ).fetchone()[0]
    print(
        f"\ndev-small check: BeIR-qrels 'dev.tsv' -> our 'validation' split has "
        f"{validation_n_q:,} distinct queries (standard MS MARCO dev-small = {dev_small_target:,}). "
        f"{'MATCH - safe to compare against published dev-small baselines.' if validation_n_q == dev_small_target else 'MISMATCH - do not compare against dev-small baselines without investigating.'}"
    )

    print("\nID-cast join check (corpus._id is VARCHAR, qrels.corpus-id is BIGINT):")
    for split, path in qrels_paths.items():
        result = con.execute(
            f"""
            SELECT count(*) AS total,
                   sum(CASE WHEN c._id IS NOT NULL THEN 1 ELSE 0 END) AS matched
            FROM read_parquet('{path}') q
            LEFT JOIN read_parquet('{corpus_path}') c
                ON TRY_CAST(c._id AS BIGINT) = q."corpus-id"
            """
        ).fetchone()
        total, matched = result
        rate = matched / total if total else 0.0
        print(f"  {split:<10} {matched:,} / {total:,} qrels rows join to corpus after casting ({rate:.2%})")
        if args.limit_corpus and split != "validation":
            print(f"    (note: --limit-corpus {args.limit_corpus} truncates the corpus, "
                  f"so this rate is expected to be low except by chance)")


if __name__ == "__main__":
    main()
