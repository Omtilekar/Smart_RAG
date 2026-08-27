"""Download SEC Financial Statement Data Sets and load them into DuckDB.

Each quarterly ZIP is ~40-110MB and contains four tab-separated files:

  sub.txt   one row per submission  (adsh, cik, name, form, fy, fp, period)
  num.txt   one row per numeric fact (adsh, tag, ddate, qtrs, uom, coreg,
            segments, value)
  pre.txt   presentation / statement layout
  tag.txt   tag definitions

`coreg` and `segments` are preserved deliberately: the SEC-documented
unique key for num.txt is (adsh, tag, version, ddate, qtrs, uom, coreg,
segments). Dropping coreg/segments collapses per-holding fund/BDC line
items onto the same (adsh, tag, ddate, qtrs) key and makes the data look
far more duplicated than it is.

Usage:
    export SEC_USER_AGENT="Jane Doe jane@example.com"
    python -m src.ingest.fetch_xbrl --start 2016q1 --end 2024q4
"""

from __future__ import annotations

import argparse
import logging
import re
import zipfile
from pathlib import Path

import duckdb

from .common import (
    STORAGE_ROOT,
    check_user_agent,
    download_to,
    make_session,
    setup_logging,
)

log = logging.getLogger(__name__)

# NOTE: SEC has relocated this path before. If you get a 404, find the current
# URL from https://www.sec.gov/dera/data/financial-statement-data-sets.html
BASE_URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets"

QUARTER_RE = re.compile(r"^(\d{4})q([1-4])$", re.IGNORECASE)


def parse_quarter(text: str) -> tuple[int, int]:
    m = QUARTER_RE.match(text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"expected format like 2019q1, got {text!r}")
    return int(m.group(1)), int(m.group(2))


def quarter_range(start: tuple[int, int], end: tuple[int, int]) -> list[str]:
    out: list[str] = []
    year, q = start
    while (year, q) <= end:
        out.append(f"{year}q{q}")
        q += 1
        if q > 4:
            year, q = year + 1, 1
    return out


def download_quarters(quarters: list[str], raw_dir: Path) -> list[Path]:
    """Fetch each quarterly ZIP, skipping any already on disk."""
    check_user_agent()
    session = make_session()
    paths: list[Path] = []

    for quarter in quarters:
        dest = raw_dir / f"{quarter}.zip"
        if dest.exists() and dest.stat().st_size > 0:
            log.info("%s already present, skipping", quarter)
            paths.append(dest)
            continue

        url = f"{BASE_URL}/{quarter}.zip"
        try:
            size = download_to(session, url, dest)
            log.info("%s downloaded (%.1f MB)", quarter, size / 1e6)
            paths.append(dest)
        except Exception as exc:  # noqa: BLE001
            # A missing quarter is normal near the present day - SEC publishes
            # roughly a quarter in arrears. Don't kill the whole run.
            log.warning("%s failed: %s", quarter, exc)

    return paths


def extract(zips: list[Path], extract_dir: Path) -> list[Path]:
    """Unpack sub.txt and num.txt from each ZIP into per-quarter folders."""
    wanted = {"sub.txt", "num.txt"}
    out: list[Path] = []

    for zpath in zips:
        target = extract_dir / zpath.stem
        if (target / "num.txt").exists():
            log.info("%s already extracted", zpath.stem)
            out.append(target)
            continue

        target.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(zpath) as zf:
                for member in zf.namelist():
                    if Path(member).name in wanted:
                        zf.extract(member, target)
            out.append(target)
            log.info("%s extracted", zpath.stem)
        except zipfile.BadZipFile:
            log.error("%s is corrupt - delete it and re-run", zpath)

    return out


def load_duckdb(quarter_dirs: list[Path], db_path: Path) -> None:
    """Build the facts table, preserving coreg/segments (see module docstring)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))

    sub_globs = [str(d / "sub.txt") for d in quarter_dirs if (d / "sub.txt").exists()]
    num_globs = [str(d / "num.txt") for d in quarter_dirs if (d / "num.txt").exists()]

    if not sub_globs or not num_globs:
        raise SystemExit("no extracted sub.txt/num.txt found - did the download succeed?")

    log.info("loading %d quarters into %s", len(sub_globs), db_path)

    con.execute("DROP TABLE IF EXISTS submissions")
    con.execute(
        """
        CREATE TABLE submissions AS
        SELECT
            adsh, CAST(cik AS BIGINT) AS cik, name, form,
            TRY_CAST(fy AS INTEGER) AS fiscal_year, fp,
            TRY_CAST(period AS VARCHAR) AS period,
            TRY_CAST(filed AS VARCHAR) AS filed
        FROM read_csv(?, delim='\t', header=true, all_varchar=true,
                      ignore_errors=true)
        WHERE form IN ('10-K', '10-Q')
        """,
        [sub_globs],
    )

    con.execute("DROP TABLE IF EXISTS facts")
    con.execute(
        """
        CREATE TABLE facts AS
        SELECT
            n.adsh, s.cik, s.name AS company, s.form, s.fiscal_year, s.fp,
            n.tag, n.version, n.ddate, TRY_CAST(n.qtrs AS INTEGER) AS qtrs,
            n.uom, n.coreg, n.segments, TRY_CAST(n.value AS DOUBLE) AS value
        FROM read_csv(?, delim='\t', header=true, all_varchar=true,
                      ignore_errors=true) AS n
        JOIN submissions AS s USING (adsh)
        WHERE n.value IS NOT NULL AND TRY_CAST(n.value AS DOUBLE) IS NOT NULL
        """,
        [num_globs],
    )

    con.execute("CREATE INDEX IF NOT EXISTS idx_facts_cik ON facts(cik)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_facts_tag ON facts(tag)")

    n_sub = con.execute("SELECT count(*) FROM submissions").fetchone()[0]
    n_facts = con.execute("SELECT count(*) FROM facts").fetchone()[0]
    n_co = con.execute("SELECT count(DISTINCT cik) FROM facts").fetchone()[0]

    log.info("submissions: %s", f"{n_sub:,}")
    log.info("facts:       %s", f"{n_facts:,}")
    log.info("companies:   %s", f"{n_co:,}")

    print("\nMost common tags (these become your eval questions):")
    rows = con.execute(
        """
        SELECT tag, count(*) AS n
        FROM facts GROUP BY tag ORDER BY n DESC LIMIT 15
        """
    ).fetchall()
    for tag, n in rows:
        print(f"  {n:>10,}  {tag}")

    con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", type=parse_quarter, default="2016q1")
    ap.add_argument("--end", type=parse_quarter, default="2024q4")
    ap.add_argument("--root", type=Path, default=STORAGE_ROOT)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    setup_logging(args.verbose)

    start = args.start if isinstance(args.start, tuple) else parse_quarter(args.start)
    end = args.end if isinstance(args.end, tuple) else parse_quarter(args.end)

    quarters = quarter_range(start, end)
    log.info("%d quarters: %s .. %s", len(quarters), quarters[0], quarters[-1])

    raw_dir = args.root / "raw" / "xbrl"
    extract_dir = args.root / "interim" / "xbrl"
    db_path = args.root / "xbrl.duckdb"

    zips = download_quarters(quarters, raw_dir)
    dirs = extract(zips, extract_dir)
    load_duckdb(dirs, db_path)

    print(f"\nDone. Query it:  duckdb {db_path}")


if __name__ == "__main__":
    main()
