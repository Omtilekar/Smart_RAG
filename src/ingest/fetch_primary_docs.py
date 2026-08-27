"""Fetch a small set of complete, table-intact 10-K filings.

EDGAR-CORPUS strips tables entirely, so it can't be used to build or test
table extraction / inline-XBRL parsing. This grabs the primary document
(not the full SGML submission - see the disk-size lesson in fetch_filings
history) for ~1,000 recent 10-Ks from large companies, picked by total
Assets from the Stage 3 XBRL database.

Mechanism note: the task originally specified discovering the primary
document via index.json. Verified against a live filing (AAPL's FY2024
10-K) first, as instructed - index.json's "type" field is a generic MIME
icon class ("text.gif") for every document, so it cannot actually
disambiguate the primary document from exhibits without guessing at
filename patterns. `data.sec.gov/submissions/CIK{10-digit}.json` exposes
`primaryDocument` directly and authoritatively, and needs only one
request per company (covering all of that company's recent filings)
instead of one index.json per filing - so the total request count is
the same order (~1 per company + 1 per filing = ~2,000), but the per-doc
mapping is exact instead of guessed.

Usage:
    export SEC_USER_AGENT="Jane Doe jane@example.com"
    python -m src.ingest.fetch_primary_docs --limit 1000
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb

from .common import ARCHIVES, STORAGE_ROOT, check_user_agent, download_to, get, make_session, setup_logging

log = logging.getLogger(__name__)

SUBMISSIONS_API = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SIZE_STOP_GB = 15.0


def select_companies(db_path: Path, limit: int, year_from: int, year_to: int) -> list[tuple[int, str]]:
    """Rank companies by their most recent reported Assets in [year_from, year_to]."""
    con = duckdb.connect(str(db_path), read_only=True)
    rows = con.execute(
        """
        WITH latest AS (
            SELECT cik, company, fiscal_year, value,
                   row_number() OVER (PARTITION BY cik ORDER BY fiscal_year DESC) AS rn
            FROM facts
            WHERE tag = 'Assets'
              AND (coreg IS NULL OR coreg = '')
              AND form = '10-K'
              AND fiscal_year BETWEEN ? AND ?
              AND value > 0
        )
        SELECT cik, company, value FROM latest WHERE rn = 1
        ORDER BY value DESC
        LIMIT ?
        """,
        [year_from, year_to, limit],
    ).fetchall()
    con.close()
    log.info("selected %d companies by total Assets (%s .. %s)", len(rows), year_from, year_to)
    if rows:
        log.info("largest: %s (Assets=%.0f), smallest of the selection: %s (Assets=%.0f)",
                  rows[0][1], rows[0][2], rows[-1][1], rows[-1][2])
    return [(cik, company) for cik, company, _ in rows]


def find_recent_10k(session, cik: int, year_from: int, year_to: int) -> tuple[str, str] | None:
    """Return (accession, primary_document) for the most recent 10-K in range, or None."""
    url = SUBMISSIONS_API.format(cik=cik)
    resp = get(session, url)
    data = resp.json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])

    best: tuple[str, str, str] | None = None  # (filingDate, accession, doc)
    for form, date, accession, doc in zip(forms, dates, accessions, docs):
        if form != "10-K":
            continue
        year = int(date[:4])
        if not (year_from <= year <= year_to):
            continue
        if best is None or date > best[0]:
            best = (date, accession, doc)

    if best is None:
        return None
    return best[1], best[2]


def fetch_one(session, cik: int, accession: str, primary_doc: str, root: Path) -> tuple[str, int]:
    accession_nodash = accession.replace("-", "")
    url = f"{ARCHIVES}/edgar/data/{cik}/{accession_nodash}/{primary_doc}"
    dest = root / "raw" / "primary" / str(cik) / f"{accession}.htm"
    if dest.exists() and dest.stat().st_size > 0:
        return ("skip", dest.stat().st_size)
    size = download_to(session, url, dest)
    return ("ok", size)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--year-from", type=int, default=2021)
    ap.add_argument("--year-to", type=int, default=2024)
    ap.add_argument("--root", type=Path, default=STORAGE_ROOT)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(args.verbose)
    check_user_agent()

    db_path = args.root / "xbrl.duckdb"
    if not db_path.exists():
        raise SystemExit(f"{db_path} not found - run fetch_xbrl first (Stage 3 must validate before this stage)")

    companies = select_companies(db_path, args.limit, args.year_from, args.year_to)
    if not companies:
        raise SystemExit("no companies selected - check the XBRL data / year range")

    session = make_session()
    ok = skipped = failed = no_filing = 0
    total_bytes = 0
    stopped_early = False

    for i, (cik, company) in enumerate(companies, 1):
        try:
            found = find_recent_10k(session, cik, args.year_from, args.year_to)
        except Exception as exc:  # noqa: BLE001
            log.warning("cik=%s (%s) submissions lookup failed: %s", cik, company, exc)
            failed += 1
            continue

        if found is None:
            log.debug("cik=%s (%s) has no 10-K in %s-%s", cik, company, args.year_from, args.year_to)
            no_filing += 1
            continue

        accession, primary_doc = found
        try:
            status, size = fetch_one(session, cik, accession, primary_doc, args.root)
            total_bytes += size
            if status == "ok":
                ok += 1
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("cik=%s (%s) accession=%s failed: %s", cik, company, accession, exc)
            failed += 1

        if i % 100 == 0:
            log.info("%d/%d  ok=%d skip=%d fail=%d no_filing=%d  %.2f GB",
                      i, len(companies), ok, skipped, failed, no_filing, total_bytes / 1e9)

        if total_bytes / 1e9 > SIZE_STOP_GB:
            log.warning("cumulative size exceeded %.0f GB after %d/%d companies - stopping early",
                        SIZE_STOP_GB, i, len(companies))
            stopped_early = True
            break

    print(f"\ndone: ok={ok} skipped={skipped} failed={failed} no_filing_in_range={no_filing}")
    print(f"total size: {total_bytes / 1e9:.2f} GB")
    if stopped_early:
        print(f"\nSTOPPED EARLY: cumulative size exceeded the {SIZE_STOP_GB:.0f} GB threshold. "
              f"Re-run with a smaller --limit or review before continuing.")
    elif total_bytes / 1e9 > SIZE_STOP_GB:
        print(f"\nWARNING: total size {total_bytes/1e9:.2f} GB exceeds the {SIZE_STOP_GB:.0f} GB threshold.")


if __name__ == "__main__":
    main()
