"""Validate all four downloaded sources: MS MARCO, EDGAR-CORPUS, XBRL, and
primary documents - plus the cross-source joins that determine whether they
actually support the four retrieval paths (vector, BM25, SQL-over-XBRL,
tree navigation).

Every check computes a real number from data on disk. Run after all of
fetch_msmarco / fetch_edgar_corpus / fetch_xbrl / fetch_primary_docs:

    python -m src.ingest.validate
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from .common import STORAGE_ROOT

EVAL_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "ResearchAndDevelopmentExpense",
    "NetIncomeLoss",
    "Assets",
    "Liabilities",
    "OperatingIncomeLoss",
    "CashAndCashEquivalentsAtCarryingValue",
    "StockholdersEquity",
    "GrossProfit",
    "CostOfRevenue",
    "OperatingExpenses",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "IncomeTaxExpenseBenefit",
]

SECTION_COLS = [
    "section_1", "section_1A", "section_1B", "section_2", "section_3", "section_4",
    "section_5", "section_6", "section_7", "section_7A", "section_8", "section_9",
    "section_9A", "section_9B", "section_10", "section_11", "section_12", "section_13",
    "section_14", "section_15",
]

FAIL_MSMARCO_REFINT_MIN = 0.99
FAIL_CIK_OVERLAP_MIN = 0.50
WARN_DUP_RATE_MAX = 0.05
WARN_RESTATE_RATE_MAX = 0.10
WARN_SECTION_FILL_MIN = 0.50

# Table-like line: 3+ numeric tokens (with optional $, commas, parens, %)
# separated by whitespace runs of 2+ - the shape a flattened HTML table
# leaves behind if any numeric content survived at all.
TABLE_LINE_RE = re.compile(
    r"(?:[\$\(]?-?[\d,]+\.?\d*%?\)?\s{2,}){2,}[\$\(]?-?[\d,]+\.?\d*%?\)?"
)


@dataclass
class Check:
    section: str
    name: str
    status: str
    detail: str


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, section: str, name: str, status: str, detail: str) -> None:
        self.checks.append(Check(section, name, status, detail))
        print(f"[{status:4}] {section} / {name}: {detail}")

    def skip(self, section: str, name: str, reason: str) -> None:
        self.add(section, name, "SKIP", f"not computed - {reason}")


def esc(path: Path | str) -> str:
    return str(path).replace("'", "''")


# =============================================================== MS MARCO


def check_msmarco(root: Path, con: duckdb.DuckDBPyConnection, report: Report) -> None:
    section = "MS MARCO"
    d = root / "msmarco"
    corpus, queries = d / "corpus.parquet", d / "queries.parquet"
    qrels = {s: d / f"qrels_{s}.parquet" for s in ("train", "validation", "test")}

    if not corpus.exists() or not queries.exists():
        report.skip(section, "all checks", "corpus.parquet/queries.parquet missing")
        return

    n_corpus = con.execute(f"SELECT count(*) FROM read_parquet('{esc(corpus)}')").fetchone()[0]
    n_queries = con.execute(f"SELECT count(*) FROM read_parquet('{esc(queries)}')").fetchone()[0]
    if n_corpus == 0 or n_queries == 0:
        report.add(section, "row counts", "FAIL", "corpus or queries table is empty")
    else:
        report.add(section, "row counts", "PASS", f"corpus={n_corpus:,} queries={n_queries:,}")

    null_empty = con.execute(
        f"SELECT sum(CASE WHEN text IS NULL OR length(trim(text))=0 THEN 1 ELSE 0 END), count(*) "
        f"FROM read_parquet('{esc(corpus)}')"
    ).fetchone()
    n_empty, n_total = null_empty
    report.add(section, "null/empty text", "WARN" if n_empty > 0 else "PASS",
               f"{n_empty:,} / {n_total:,} corpus rows have null/empty text ({n_empty/n_total:.2%})")

    dup_ids = con.execute(
        f"SELECT count(*) FROM (SELECT _id FROM read_parquet('{esc(corpus)}') GROUP BY _id HAVING count(*)>1)"
    ).fetchone()[0]
    report.add(section, "duplicate _id", "WARN" if dup_ids > 0 else "PASS",
               f"{dup_ids:,} duplicated _id values in corpus")

    for split, path in qrels.items():
        if not path.exists():
            report.skip(section, f"referential integrity ({split})", f"{path.name} missing")
            continue
        row = con.execute(
            f"""
            SELECT count(*),
                   sum(CASE WHEN c._id IS NOT NULL THEN 1 ELSE 0 END),
                   sum(CASE WHEN q._id IS NOT NULL THEN 1 ELSE 0 END)
            FROM read_parquet('{esc(path)}') qr
            LEFT JOIN read_parquet('{esc(corpus)}') c ON TRY_CAST(c._id AS BIGINT) = qr."corpus-id"
            LEFT JOIN read_parquet('{esc(queries)}') q ON TRY_CAST(q._id AS BIGINT) = qr."query-id"
            """
        ).fetchone()
        total, corpus_hits, query_hits = row
        corpus_rate = corpus_hits / total if total else 0.0
        query_rate = query_hits / total if total else 0.0
        status = "FAIL" if min(corpus_rate, query_rate) < FAIL_MSMARCO_REFINT_MIN else "PASS"
        report.add(
            section, f"referential integrity ({split})", status,
            f"corpus-id match={corpus_rate:.2%}, query-id match={query_rate:.2%} (n={total:,})",
        )

    lens = con.execute(
        f"SELECT length(text) FROM read_parquet('{esc(corpus)}') USING SAMPLE 200000 ROWS"
    ).fetchall()
    lens = sorted(l for (l,) in lens if l is not None)
    if lens:
        n = len(lens)
        report.add(section, "passage length distribution (sample)", "PASS",
                   f"min={lens[0]} p50={lens[n//2]} p95={lens[int(n*0.95)]} max={lens[-1]} chars")
    else:
        report.skip(section, "passage length distribution", "no rows sampled")

    if qrels["validation"].exists():
        rpq = con.execute(
            f'SELECT count(*) FROM (SELECT "query-id", count(*) AS n '
            f"FROM read_parquet('{esc(qrels['validation'])}') GROUP BY \"query-id\")"
        ).fetchone()[0]
        dist = con.execute(
            f'SELECT n, count(*) FROM (SELECT "query-id", count(*) AS n '
            f"FROM read_parquet('{esc(qrels['validation'])}') GROUP BY \"query-id\") "
            f"GROUP BY n ORDER BY n"
        ).fetchall()
        dist_desc = ", ".join(f"{n} rel-doc(s): {c:,} queries" for n, c in dist)
        report.add(section, "relevant-docs-per-query (validation split)", "PASS", dist_desc)

    if qrels["validation"].exists():
        samples = con.execute(
            f"""
            SELECT q.text, c.text
            FROM read_parquet('{esc(qrels['validation'])}') qr
            JOIN read_parquet('{esc(queries)}') q ON TRY_CAST(q._id AS BIGINT) = qr."query-id"
            JOIN read_parquet('{esc(corpus)}') c ON TRY_CAST(c._id AS BIGINT) = qr."corpus-id"
            USING SAMPLE 3 ROWS
            """
        ).fetchall()
        print("\n  Sample (query, relevant passage) pairs:")
        for i, (qtext, ptext) in enumerate(samples, 1):
            print(f"  [{i}] QUERY: {qtext}")
            print(f"      PASSAGE: {ptext[:500]}{'...' if len(ptext) > 500 else ''}")
        report.add(section, "sample query/passage pairs", "PASS", f"{len(samples)} pairs printed above")


# =========================================================== EDGAR-CORPUS


def check_edgar_corpus(root: Path, con: duckdb.DuckDBPyConnection, report: Report) -> None:
    section = "EDGAR-CORPUS"
    d = root / "edgar_corpus"
    splits = {s: d / f"{s}.parquet" for s in ("train", "test", "validation")}
    existing = {s: p for s, p in splits.items() if p.exists()}

    if not existing:
        report.skip(section, "all checks", "no split parquet files found")
        return

    union_sql = " UNION ALL ".join(f"SELECT * FROM read_parquet('{esc(p)}')" for p in existing.values())

    total = con.execute(f"SELECT count(*) FROM ({union_sql})").fetchone()[0]
    distinct_filings = con.execute(f"SELECT count(DISTINCT filename) FROM ({union_sql})").fetchone()[0]
    distinct_ciks = con.execute(f"SELECT count(DISTINCT cik) FROM ({union_sql})").fetchone()[0]
    # cik/year are VARCHAR in this dataset - cast for correct numeric min/max.
    years = con.execute(
        f"SELECT min(TRY_CAST(year AS INTEGER)), max(TRY_CAST(year AS INTEGER)) FROM ({union_sql})"
    ).fetchone()
    if total == 0:
        report.add(section, "row counts", "FAIL", "no rows across splits")
        return
    report.add(section, "distinct filings / CIK / year coverage", "PASS",
               f"rows={total:,} distinct_filings={distinct_filings:,} distinct_ciks={distinct_ciks:,} "
               f"years={years[0]}-{years[1]}")

    fill_sql = ", ".join(
        f"sum(CASE WHEN {c} IS NOT NULL AND length(trim({c}))>0 THEN 1 ELSE 0 END) AS {c}_n, "
        f"avg(CASE WHEN {c} IS NOT NULL AND length(trim({c}))>0 THEN length({c}) END) AS {c}_avglen"
        for c in SECTION_COLS
    )
    row = con.execute(f"SELECT {fill_sql} FROM ({union_sql})").fetchone()
    low_fill = []
    for i, c in enumerate(SECTION_COLS):
        n, avglen = row[2 * i], row[2 * i + 1]
        rate = n / total
        if rate < WARN_SECTION_FILL_MIN:
            low_fill.append(f"{c}={rate:.1%}")
        avglen_s = f"{avglen:.0f}" if avglen is not None else "n/a"
        print(f"    {c:<12} fill={rate:.1%}  n={n:,}  avg_len={avglen_s} chars")
    status = "WARN" if low_fill else "PASS"
    report.add(section, "per-section fill rate", status,
               f"see breakdown above" + (f"; below {WARN_SECTION_FILL_MIN:.0%}: {', '.join(low_fill)}" if low_fill else ""))

    samples = con.execute(f"SELECT section_8 FROM ({union_sql}) WHERE section_8 IS NOT NULL "
                           f"AND length(trim(section_8))>0 USING SAMPLE 10 ROWS").fetchall()
    n_with_table_like_content = 0
    for (text,) in samples:
        if TABLE_LINE_RE.search(text):
            n_with_table_like_content += 1
    report.add(
        section, "tables absent confirmation (10 section_8 samples)",
        "PASS" if n_with_table_like_content == 0 else "WARN",
        f"{n_with_table_like_content}/10 sampled section_8 values still contain table-shaped numeric "
        f"content (aligned multi-number lines) despite HTML tables being stripped" if n_with_table_like_content
        else "0/10 sampled section_8 values show any tabular numeric structure - tables are genuinely gone, "
             "not just detagged",
    )


# =================================================================== XBRL


def check_xbrl(con: duckdb.DuckDBPyConnection, report: Report) -> None:
    section = "XBRL"
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "submissions" not in tables or "facts" not in tables:
        report.skip(section, "all checks", "submissions/facts table missing - run fetch_xbrl first")
        return

    n_sub = con.execute("SELECT count(*) FROM submissions").fetchone()[0]
    n_facts = con.execute("SELECT count(*) FROM facts").fetchone()[0]
    n_co = con.execute("SELECT count(DISTINCT cik) FROM facts").fetchone()[0]
    n_tags = con.execute("SELECT count(DISTINCT tag) FROM facts").fetchone()[0]
    if n_sub == 0 or n_facts == 0:
        report.add(section, "row counts", "FAIL", "submissions or facts table is empty")
        return
    report.add(section, "row counts", "PASS",
               f"submissions={n_sub:,} facts={n_facts:,} companies={n_co:,} tags={n_tags:,}")

    real_dup_rows = con.execute(
        """
        SELECT sum(n) FROM (
            SELECT count(*) AS n FROM facts
            GROUP BY adsh, tag, ddate, qtrs, uom, coreg, segments HAVING count(*) > 1
        )
        """
    ).fetchone()[0] or 0
    real_dup_rate = real_dup_rows / n_facts
    report.add(section, "duplicate rate (full SEC-documented key)",
               "WARN" if real_dup_rate > WARN_DUP_RATE_MAX else "PASS",
               f"{real_dup_rows:,} rows ({real_dup_rate:.4%} of facts)")

    period_restate = con.execute(
        """
        WITH grp AS (
            SELECT cik, tag, ddate, qtrs,
                   count(DISTINCT adsh) AS n_adsh, count(DISTINCT value) AS n_values
            FROM facts WHERE coreg IS NULL OR coreg = ''
            GROUP BY cik, tag, ddate, qtrs HAVING count(DISTINCT adsh) > 1
        )
        SELECT count(*), sum(CASE WHEN n_values > 1 THEN 1 ELSE 0 END) FROM grp
        """
    ).fetchone()
    p_groups, p_restated = period_restate
    p_groups, p_restated = p_groups or 0, p_restated or 0
    p_rate = p_restated / p_groups if p_groups else 0.0
    report.add(section, "restatement rate (cik,tag,ddate,qtrs across filings)",
               "WARN" if p_rate > WARN_RESTATE_RATE_MAX else "PASS",
               f"{p_restated:,} / {p_groups:,} groups ({p_rate:.2%})")

    tag_sql = ", ".join(f"'{t}'" for t in EVAL_TAGS)
    cov_rows = con.execute(
        f"""
        SELECT tag, count(DISTINCT cik) AS companies, count(DISTINCT (cik, fiscal_year)) AS company_years
        FROM facts WHERE tag IN ({tag_sql}) GROUP BY tag ORDER BY company_years DESC
        """
    ).fetchall()
    found_tags = {r[0] for r in cov_rows}
    missing = [t for t in EVAL_TAGS if t not in found_tags]
    detail = "; ".join(f"{tag}={cy:,} co-years" for tag, co, cy in cov_rows)
    report.add(section, "eval-tag coverage", "WARN" if missing else "PASS",
               detail + (f" | MISSING: {', '.join(missing)}" if missing else ""))

    neg_assets = con.execute("SELECT count(*) FROM facts WHERE tag='Assets' AND value<0").fetchone()[0]
    absurd = con.execute("SELECT count(*) FROM facts WHERE abs(value)>1e13").fetchone()[0]
    non_usd = con.execute("SELECT count(*) FROM facts WHERE uom != 'USD'").fetchone()[0]
    report.add(section, "sanity (negative Assets / magnitude / uom)",
               "WARN" if neg_assets > 0 or absurd > 0 else "PASS",
               f"negative Assets={neg_assets:,}, |value|>1e13={absurd:,}, non-USD uom rows={non_usd:,}")


# ============================================================ PRIMARY DOCS


def check_primary_docs(root: Path, requested: int | None, report: Report) -> list[Path]:
    section = "Primary docs"
    d = root / "raw" / "primary"
    paths = list(d.glob("*/*.htm")) if d.exists() else []

    if not paths:
        report.add(section, "downloaded vs requested", "FAIL", "no primary documents on disk")
        return paths

    if requested:
        report.add(section, "downloaded vs requested", "PASS" if len(paths) > 0 else "FAIL",
                   f"{len(paths):,} downloaded (requested up to {requested:,} companies)")
    else:
        report.add(section, "downloaded vs requested", "PASS", f"{len(paths):,} downloaded")

    sizes = [(p, p.stat().st_size) for p in paths]
    zero_byte = [p for p, s in sizes if s == 0]
    small = [p for p, s in sizes if 0 < s < 10_000]
    report.add(section, "zero-byte / small files", "WARN" if zero_byte else "PASS",
               f"zero-byte={len(zero_byte):,}, <10KB={len(small):,}, total={len(sizes):,}")

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        report.skip(section, "table survival / inline XBRL", "beautifulsoup4 not installed")
        return paths

    table_counts = []
    ix_present = 0
    sample = paths if len(paths) <= 300 else random.sample(paths, 300)
    for p in sample:
        raw = p.read_bytes()
        if b"<ix:" in raw.lower() or b"xmlns:ix" in raw.lower():
            ix_present += 1
        soup = BeautifulSoup(raw, "lxml")
        table_counts.append(len(soup.find_all("table")))

    docs_with_tables = sum(1 for n in table_counts if n > 0)
    mean_tables = sum(table_counts) / len(table_counts) if table_counts else 0.0
    status = "FAIL" if docs_with_tables == 0 else "PASS"
    report.add(section, f"table survival (sample of {len(sample)})", status,
               f"{docs_with_tables}/{len(sample)} docs have >=1 <table> element, "
               f"mean {mean_tables:.1f} tables/doc")

    ix_rate = ix_present / len(sample) if sample else 0.0
    report.add(section, f"inline XBRL presence (sample of {len(sample)})", "PASS",
               f"{ix_present}/{len(sample)} docs contain ix: tags ({ix_rate:.1%})")

    return paths


# ============================================================ CROSS-SOURCE


def check_cross_source(root: Path, con: duckdb.DuckDBPyConnection, primary_paths: list[Path],
                        report: Report) -> None:
    section = "Cross-source"
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    edgar_train = root / "edgar_corpus" / "train.parquet"
    edgar_test = root / "edgar_corpus" / "test.parquet"
    edgar_val = root / "edgar_corpus" / "validation.parquet"
    edgar_paths = [p for p in (edgar_train, edgar_test, edgar_val) if p.exists()]

    if "facts" not in tables:
        report.skip(section, "all checks", "XBRL facts table missing")
        return
    if not edgar_paths:
        report.skip(section, "all checks", "EDGAR-CORPUS parquet files missing")
        return

    edgar_union = " UNION ALL ".join(f"SELECT * FROM read_parquet('{esc(p)}')" for p in edgar_paths)

    # cik/year are VARCHAR in EDGAR-CORPUS but BIGINT in the XBRL tables - cast
    # or a set intersection between str and int silently returns empty every time.
    xbrl_ciks = {r[0] for r in con.execute("SELECT DISTINCT cik FROM facts").fetchall()}
    edgar_ciks = {r[0] for r in con.execute(
        f"SELECT DISTINCT TRY_CAST(cik AS BIGINT) FROM ({edgar_union})"
    ).fetchall()}
    overlap = xbrl_ciks & edgar_ciks
    overlap_rate = len(overlap) / len(edgar_ciks) if edgar_ciks else 0.0
    status = "FAIL" if overlap_rate < FAIL_CIK_OVERLAP_MIN else "PASS"
    report.add(section, "CIK overlap: EDGAR-CORPUS vs XBRL", status,
               f"{len(overlap):,} / {len(edgar_ciks):,} EDGAR-CORPUS CIKs also in XBRL ({overlap_rate:.2%}); "
               f"XBRL has {len(xbrl_ciks):,} total CIKs")

    if primary_paths:
        primary_ciks = {int(p.parent.name) for p in primary_paths}
        p_overlap = primary_ciks & xbrl_ciks
        report.add(section, "CIK overlap: primary docs vs XBRL", "PASS",
                   f"{len(p_overlap):,} / {len(primary_ciks):,} primary-doc CIKs also in XBRL "
                   f"({len(p_overlap)/len(primary_ciks):.2%} - expected ~100%, companies were selected from XBRL)")
    else:
        report.skip(section, "CIK overlap: primary docs vs XBRL", "no primary docs on disk")

    edgar_cik_years = con.execute(
        f"SELECT DISTINCT TRY_CAST(cik AS BIGINT), TRY_CAST(year AS INTEGER) FROM ({edgar_union})"
    ).fetchall()
    xbrl_cik_years = set(con.execute(
        "SELECT DISTINCT cik, fiscal_year FROM facts WHERE fiscal_year IS NOT NULL"
    ).fetchall())
    matched = sum(1 for cik, year in edgar_cik_years if (cik, year) in xbrl_cik_years)
    total_pairs = len(edgar_cik_years)
    match_rate = matched / total_pairs if total_pairs else 0.0
    report.add(section, "EDGAR-CORPUS <-> XBRL join on (cik, year), full range", "PASS" if match_rate >= 0.5 else "WARN",
               f"{matched:,} / {total_pairs:,} distinct (cik,year) pairs ({match_rate:.2%}) - low by "
               f"construction, EDGAR-CORPUS runs 1993-2020 but XBRL only covers 2016-2024")

    # A handful of (cik, fiscal_year) rows carry stray prior-year comparative
    # tags going back to 2004 - real but statistically noise (single-digit
    # counts). Restrict "XBRL coverage" to years with substantial data so the
    # overlap window reflects the actual fetch range, not those artifacts.
    year_counts: dict[int, int] = {}
    for _, y in xbrl_cik_years:
        year_counts[y] = year_counts.get(y, 0) + 1
    xbrl_years_present = {y for y, n in year_counts.items() if n >= 1000}
    overlap_window = [(c, y) for c, y in edgar_cik_years if y in xbrl_years_present]
    overlap_matched = sum(1 for c, y in overlap_window if (c, y) in xbrl_cik_years)
    overlap_total = len(overlap_window)
    overlap_rate = overlap_matched / overlap_total if overlap_total else 0.0
    report.add(section, "EDGAR-CORPUS <-> XBRL join on (cik, year), overlap window only",
               "PASS" if overlap_rate >= 0.5 else "WARN",
               f"{overlap_matched:,} / {overlap_total:,} EDGAR-CORPUS (cik,year) pairs where year is within "
               f"XBRL's coverage ({overlap_rate:.2%}) - this is the number that determines whether XBRL facts "
               f"can serve as ground truth for EDGAR-CORPUS documents in the years both sources cover")


# ================================================================= report


def verdict(report: Report) -> str:
    fails = [c for c in report.checks if c.status == "FAIL"]
    warns = [c for c in report.checks if c.status == "WARN"]
    skips = [c for c in report.checks if c.status == "SKIP"]
    if fails:
        return f"FAIL - {len(fails)} check(s) failed, {len(warns)} warning(s), {len(skips)} skipped"
    if warns:
        return f"WARN - {len(warns)} check(s) need attention, {len(skips)} skipped"
    return f"PASS - all checks green ({len(skips)} skipped)"


def render_markdown(report: Report) -> str:
    lines = ["# Validation report", "", f"**Verdict: {verdict(report)}**", ""]
    flagged = [c for c in report.checks if c.status in ("FAIL", "WARN")]
    if flagged:
        lines += ["## FAIL / WARN summary", "", "| Status | Section | Check | Detail |", "|---|---|---|---|"]
        for c in flagged:
            lines.append(f"| {c.status} | {c.section} | {c.name} | {c.detail} |")
        lines.append("")

    by_section: dict[str, list[Check]] = {}
    for c in report.checks:
        by_section.setdefault(c.section, []).append(c)
    for section, checks in by_section.items():
        lines += [f"## {section}", "", "| Status | Check | Detail |", "|---|---|---|"]
        for c in checks:
            lines.append(f"| {c.status} | {c.name} | {c.detail} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    root = STORAGE_ROOT
    report = Report()
    con = duckdb.connect()
    con.execute("SET enable_progress_bar=false")

    check_msmarco(root, con, report)
    check_edgar_corpus(root, con, report)

    db_path = root / "xbrl.duckdb"
    if db_path.exists():
        xbrl_con = duckdb.connect(str(db_path), read_only=True)
        xbrl_con.execute("SET enable_progress_bar=false")
        check_xbrl(xbrl_con, report)
        # attach for cross-source checks that need both facts and edgar parquet in one connection
        con.execute(f"ATTACH '{esc(db_path)}' AS xbrl (READ_ONLY)")
        con.execute("CREATE OR REPLACE TEMP VIEW facts AS SELECT * FROM xbrl.facts")
        xbrl_con.close()
    else:
        report.skip("XBRL", "all checks", f"{db_path} does not exist - run fetch_xbrl first")

    primary_paths = check_primary_docs(root, None, report)
    check_cross_source(root, con, primary_paths, report)

    print()
    print(f"VERDICT: {verdict(report)}")

    out_path = root / "validation_report.md"
    out_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
