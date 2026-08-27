# SEC RAG - Phase 1 Data Readiness Report

## Executive Summary

**Overall status: PHASE 2 READY**

Original Phase 1 audit: 0 BLOCKER(s), 0 formal WARNING(s). Two post-freeze metric-definition reviews (Check 1: strict value-revision rate; Check 2: 10-K-only EDGAR<->XBRL coverage with a semantically-chosen fiscal-year alignment field) were then run to verify the two most complex prior metrics under stricter definitions - see 'Methodological Corrections', 'Check 1', and 'Check 2' below. Strict cross-filing value-revision rate (all tags, consolidated facts only): 7.87% (1,044,801/13,276,577) - materially lower than the original loose 23.56% figure; segment/dimensional facts, unit mismatches, and same-accession duplicate/value rows (not coreg, which the loose method had already excluded) were the main drivers of the inflated loose metric. 10-K-only EDGAR<->XBRL coverage, 2016-2020, aligned on XBRL fy (the chosen semantic fiscal-year alignment field - see Check 2): 5,646/6,950 = 81.24%, with 1,249/1,304 of the unmatched pairs structural (company has no XBRL 10-K for that period), not a join-definition artifact. Sufficient aligned ground truth exists to proceed to Phase 2 while explicitly selecting the aligned (cik,year) subset for eval-question generation.

## Validation metrics: previous vs. measured

| Check | Previous | Current | Status | Note |
|---|---:|---:|---|---|
| MS MARCO corpus rows | 8,841,823 | 8,841,823 | PASS |  |
| MS MARCO dev-small (validation split distinct queries) | 6,980 | 6,980 | PASS |  |
| EDGAR-CORPUS distinct filings | 91,086 | 91,086 | PASS |  |
| EDGAR-CORPUS distinct CIKs | 25,937 | 25,937 | PASS |  |
| EDGAR-CORPUS section_1A fill rate | 25.6% | 25.6% | PASS |  |
| EDGAR-CORPUS section_1B fill rate | 24.4% | 24.4% | PASS |  |
| EDGAR-CORPUS section_9A fill rate | 30.1% | 30.1% | PASS |  |
| EDGAR-CORPUS section_9B fill rate | 27.0% | 27.0% | PASS |  |
| EDGAR-CORPUS section_15 fill rate | 32.4% | 32.4% | PASS |  |
| EDGAR-CORPUS tables present in sampled sections | 0/10 (prior) | 1/20 | INFO | reclassified after manual inspection: flattened numeric text, not structured table markup |
| XBRL facts | ~90.7M (90,685,753) | 90,685,753 | PASS |  |
| XBRL true duplicate rate (full key) | 32 / ~90.7M (~0.0000%) | 32 / 90685753 (0.0000%) | PASS |  |
| XBRL restatement rate (loose method - superseded by Check 1's value-revision rate) | 23.56% | 23.56% | PASS |  |
| Overall CIK overlap (EDGAR-CORPUS vs XBRL) | 26.51% | 26.51% | PASS |  |
| 2016-2020 CIK/year join (exact literal restriction) | 81.71% (prior method, wider window) | 83.45% | PASS | see per-year breakdown below; prior 81.71% used an 'XBRL years with >=1000 rows' window, not literal 2016-2020 |
| Primary docs | 990 | 990 | PASS |  |
| Primary docs table survival & mean tables/doc | ~100% docs, ~136 tables/doc | 30/30 docs, mean=134.3 | PASS |  |
| Primary docs inline-XBRL presence | 100% | 100.0% | PASS |  |


## 1. Dataset Inventory

Total files under `data`: 1,144  |  Total size: 26.28 GB

| Group | Kind | Files | Size (GB) |
|---|---|---:|---:|
| MS MARCO | RAW SOURCE | 5 | 1.66 |
| EDGAR-CORPUS | RAW SOURCE | 3 | 5.77 |
| XBRL quarterly ZIPs | RAW SOURCE | 36 | 3.45 |
| XBRL DuckDB (facts+submissions) | DERIVED | 1 | 7.01 |
| Primary 10-K documents | RAW SOURCE | 990 | 4.48 |
| audit_xbrl_meta (this audit's extraction) | DERIVED | 108 | 3.90 |
| validation_report.md (Phase 1 output) | LOG/REPORT | 1 | 0.00 |

Repo-root log files found: ['phase1_data_audit.log', 'stage1_msmarco.log', 'stage1_msmarco.log', 'stage2_edgar_corpus.log', 'stage2_edgar_corpus.log', 'stage3_xbrl.log', 'stage3_xbrl.log', 'stage4_primary.log', 'stage4_primary.log', 'stage5_validate.log', 'stage5_validate.log']

RAW SOURCE = as-downloaded, never modified. DERIVED = computed from raw sources by our own code. LOG/REPORT = narrative output of a previous run.

## 2. MS MARCO

**Corpus**: 8,841,823 passages, 0 duplicate `_id`, 0 null/empty (0.000%)
  text length (sample n=200,000): min=41 p50=301 p95=597 max=1411 chars

**Queries**: 509,962 total, 0 null/empty
  query length: min=5 p50=31 p95=56 max=215 chars

**Qrels (per split)**:
  train       rows=532,751  distinct_queries=502,939  distinct_passages=516,472  corpus-ref-integrity=100.000%  query-ref-integrity=100.000%
  validation  rows=7,437  distinct_queries=6,980  distinct_passages=7,433  corpus-ref-integrity=100.000%  query-ref-integrity=100.000%
  test        rows=9,260  distinct_queries=43  distinct_passages=9,139  corpus-ref-integrity=100.000%  query-ref-integrity=100.000%

`validation` split MATCHES the standard BEIR/MS MARCO dev-small benchmark (6,980 queries).

**Role in this project**: benchmark/harness validation only - proves the retrieval+eval pipeline reproduces published baselines before it's trusted on SEC filings. It is not part of the SEC production corpus.

## 3. EDGAR-CORPUS

rows: train=47,000, test=22,036, validation=22,050, total=91,086
distinct filings (deduped across splits): 91,086
distinct CIKs: 25,937
year range: 1993-2020
native cik column type: VARCHAR (VARCHAR - needs TRY_CAST for numeric joins)

years with data: 28 distinct years (1993-2020); filings/year ranges 1,326-10,106

**Section fill rate and length** (fraction non-null & non-empty, all splits):

| Section | Fill % | Median len | P95 len |
|---|---:|---:|---:|
| section_1 | 94.9% | 26,101 | 91,968 |
| section_1A | 25.6% | 33,098 | 131,253 |
| section_1B | 24.4% | 49 | 249 |
| section_2 | 94.9% | 976 | 6,856 |
| section_3 | 97.2% | 421 | 8,384 |
| section_4 | 95.9% | 172 | 4,313 |
| section_5 | 97.4% | 1,347 | 6,139 |
| section_6 | 93.6% | 383 | 3,765 |
| section_7 | 96.5% | 20,456 | 85,670 |
| section_7A | 58.5% | 792 | 7,635 |
| section_8 | 96.0% | 448 | 104,739 |
| section_9 | 95.9% | 117 | 1,697 |
| section_9A | 30.1% | 3,538 | 9,231 |
| section_9B | 27.0% | 51 | 1,804 |
| section_10 | 90.6% | 829 | 13,626 |
| section_11 | 89.4% | 335 | 15,331 |
| section_12 | 90.5% | 410 | 5,147 |
| section_13 | 90.7% | 347 | 7,863 |
| section_14 | 94.8% | 4,541 | 72,415 |
| section_15 | 32.4% | 9,204 | 132,687 |

**Table survival check** (20 filings, section_8, deterministic hash-order sample): 1/20 show any table-shaped structure (HTML `<table>`, markdown pipes, or aligned multi-number rows)

## 4. XBRL

**Derived tables in xbrl.duckdb** (loaded from sub.txt+num.txt of all quarterly ZIPs, filtered to form IN ('10-K','10-Q'), value TRY_CAST-able to DOUBLE):
  submissions=218,166  facts=90,685,753  distinct_ciks=10,757  distinct_tags=291,429

**tag.txt** (extracted from 36 quarterly ZIPs, never persisted by fetch_xbrl.py): 2,823,076 raw rows (repeats per quarter a tag/version was in use), 2,578,879 distinct (tag,version) pairs
columns: tag, version, custom (0/1), abstract (0/1), datatype, iord (I=instant/D=duration), crdr (debit/credit), tlabel, doc

**pre.txt** (presentation/statement layout, 36 quarters): 26,373,782 rows. columns: adsh, report, line, stmt, inpth, rfile, tag, version, plabel, negating. null tag: 0 (0.000%)
  role: maps each fact to where it appeared on a rendered financial statement (stmt=BS/IS/CF/etc, plabel=the label as printed). Not needed for numeric QA itself, useful later for statement-aware chunk/table alignment.
  sample rows: [('0000002178-16-000064', 'BS', 'CashAndCashEquivalentsAtCarryingValue', 'Cash and cash equivalents'), ('0000002178-16-000064', 'BS', 'AccountsReceivableNetCurrent', 'Accounts receivable, net of allowance for doubtful accounts of $206 and $179, respectively'), ('0000002178-16-000064', 'BS', 'EnergyRelatedInventory', 'Inventories')]

**Critical NUM checks**:
  ddate year coverage: 1932-2923
  top uom values: USD=82,511,115, shares=6,428,685, pure=1,527,912, CAD=108,473, Rate=26,889, EUR=16,678, AUD=13,896, Contract=12,170, GBP=7,857, CNY=6,746
  qtrs distribution: 0=36,753,984, 1=21,836,715, 4=15,029,198, 3=8,648,571, 2=8,393,131, 5=2,698, 8=2,134, 6=1,775, 7=1,453, 12=1,162
  coreg IS NULL/blank: 88,137,085 (97.190%)  |  non-null (co-registrant facts, e.g. subsidiary/BDC line items): 2,548,668
  segments IS NULL/blank: 47,789,055 (52.697%)  |  non-null (segment/dimensional breakdowns, not consolidated totals): 42,896,698
  negative values on major (should-be-nonnegative) tags: {'Liabilities': 11036, 'Assets': 33322, 'Revenues': 65948, 'StockholdersEquity': 1117494}
  null value count in facts: 0 (should be 0 - facts table filters WHERE value IS NOT NULL at load time)
  top 20 tags by frequency: StockholdersEquity=3,424,950, RevenueFromContractWithCustomerExcludingAssessedTax=2,383,954, StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest=2,019,405, NetIncomeLoss=1,755,230, Revenues=1,493,501, OperatingIncomeLoss=1,165,062, Assets=1,001,030, IncomeTaxExpenseBenefit=850,493, ProfitLoss=842,917, InvestmentOwnedAtFairValue=814,781, CashAndCashEquivalentsAtCarryingValue=743,832, CommonStockSharesOutstanding=674,988, InvestmentOwnedAtCost=668,447, AdjustmentsToAdditionalPaidInCapitalSharebasedCompensationRequisiteServicePeriodRecognitionValue=649,447, IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest=625,087, EarningsPerShareBasic=614,700, InterestExpense=601,964, EarningsPerShareDiluted=593,617, OtherComprehensiveIncomeLossNetOfTax=592,671, Goodwill=590,748

**Duplicate analysis** - exact key used: `(adsh, tag, version, ddate, qtrs, uom, coreg, segments)` (the full SEC-documented uniqueness key for num.txt; a simplified key that drops coreg/segments collapses distinct co-registrant/segment facts onto each other)
  duplicate rows on this key: 32 / 90,685,753 = 0.000035%
  (sanity check) same key but WITHOUT coreg/segments/uom/version: 49,981,128 rows collide (55.11%) - this is the number you'd wrongly see if coreg/segments were dropped from the identity, confirming why they matter

**Restatement analysis (loose method - see 'Check 1' below for the corrected, stricter cross-filing value-revision rate)** - (cik, tag, ddate, qtrs) groups reported by >1 filing (coreg-null/consolidated facts only): 14,260,160 groups, 3,359,610 with a differing value (23.56%)
  meaning: when the same company reports the same concept for the same period in two different filings (e.g. a 10-Q's Q3 numbers reappearing as a comparative in the next 10-K), 23.6% of the time the value differs - i.e. was restated/revised. For ground-truth QA this means picking ONE canonical filing per (cik,tag,period), not assuming any repeat of the concept agrees.

### Truth-contract prerequisite tags (Part 6)

`version = 'us-gaap'` (naive/wrong filter) matches 0 rows; `version LIKE 'us-gaap/%'` (correct - version is e.g. 'us-gaap/2015') matches 84,101,557 / 90,685,753 (92.7%) rows. Confirms: never filter on the literal string 'us-gaap'.

| Tag | Facts | Companies | Years | Top UOM | qtrs dist | custom | abstract | iord |
|---|---:|---:|---|---|---|---|---|---|
| Assets | 1,001,030 | 10,700 | 2004-2025 | USD | 0:1,001,030 | 0 | 0 | I |
| Liabilities | 493,654 | 9,563 | 2010-2025 | USD | 0:493,654 | 0 | 0 | I |
| StockholdersEquity | 3,424,950 | 10,162 | 2004-2025 | USD | 0:3,424,950 | 0 | 0 | I |
| CashAndCashEquivalentsAtCarryingValue | 743,832 | 9,841 | 2004-2025 | USD | 0:743,832 | 0 | 0 | I |
| Revenues | 1,493,501 | 5,694 | 2004-2025 | USD | 1:706,311,4:346,782,3:219,308 | 0 | 0 | D |
| ResearchAndDevelopmentExpense | 252,628 | 3,348 | 2010-2025 | USD | 1:120,595,4:52,232,3:39,265 | 0 | 0 | D |
| NetIncomeLoss | 1,755,230 | 10,418 | 2004-2025 | USD | 1:994,685,4:362,623,2:197,269 | 0 | 0 | D |
| OperatingIncomeLoss | 1,165,062 | 8,628 | 2004-2025 | USD | 1:583,175,4:240,281,2:170,529 | 0 | 0 | D |
| CostOfRevenue | 208,249 | 2,884 | 2004-2025 | USD | 1:101,134,4:41,846,3:32,695 | 0 | 0 | D |
| GrossProfit | 446,157 | 4,255 | 2004-2025 | USD | 1:236,460,4:84,062,3:62,644 | 0 | 0 | D |
| RevenueFromContractWithCustomerExcludingAssessedTax | 2,383,954 | 3,917 | 2016-2025 | USD | 1:1,119,973,4:509,487,3:379,485 | 0 | 0 | D |
| OperatingExpenses | 425,933 | 6,151 | 2004-2025 | USD | 1:211,044,4:83,249,2:65,443 | 0 | 0 | D |
| EarningsPerShareBasic | 614,700 | 8,522 | 2011-2025 | USD | 1:346,403,4:103,543,3:82,029 | 0 | 0 | D |
| EarningsPerShareDiluted | 593,617 | 8,185 | 2011-2025 | USD | 1:336,226,4:99,977,3:78,442 | 0 | 0 | D |
| IncomeTaxExpenseBenefit | 850,493 | 7,894 | 2010-2025 | USD | 1:392,845,4:210,561,3:122,945 | 0 | 0 | D |

Assets (instant concept) at qtrs=0: 1,001,030/1,001,030 (100.0%)
Revenues (annual duration concept) at qtrs=4: 346,782/1,493,501 (23.2%) (remainder mostly qtrs=1,2,3 from 10-Q quarterly/YTD reporting, which is expected)

## Submission / Filing Understanding (Part 7)

filtered submissions (form IN 10-K/10-Q): 218,166, distinct CIKs: 10,757
form distribution (filtered view): [('10-Q', 164357), ('10-K', 53809)]
duplicated adsh: 0
missing period: 0 (0.000%)

**Raw sub.txt (all forms, all quarters, unfiltered)**: 245,553 rows
  top forms: [('10-Q', 164357), ('10-K', 53809), ('20-F', 6043), ('10-Q/A', 4028), ('6-K', 2969), ('S-1/A', 2851), ('10-K/A', 2837), ('S-1', 2313), ('POS AM', 1213), ('S-4/A', 1188), ('40-F', 967), ('8-K', 577), ('S-4', 566), ('20-F/A', 493), ('F-1/A', 228)]
  missing CIK: 0  |  missing SIC: 1,282 (0.52%) - SIC is present in raw sub.txt but NOT carried into xbrl.duckdb's `submissions` table (fetch_xbrl.py doesn't select it) - a real gap if industry-based eval stratification is planned later
  fp (fiscal period) distribution: [('FY', 65147), ('Q2', 57986), ('Q3', 56942), ('Q1', 56576), (None, 8855), ('H1', 28)]

**Traceability: NUM fact -> SUB -> company** (3 deterministic examples, seed=42)

  NUM: adsh=0001144204-18-042656 tag=Assets value=427,071,000
    -> SUB: cik=1041657 company='URBAN ONE, INC.' form=10-Q filed=20180808 period=20180630 fiscal_year=2018 SIC=4832

  NUM: adsh=0001144204-18-042656 tag=Assets value=67,334,000
    -> SUB: cik=1041657 company='URBAN ONE, INC.' form=10-Q filed=20180808 period=20180630 fiscal_year=2018 SIC=4832

  NUM: adsh=0001144204-18-042656 tag=Assets value=1,316,755,000
    -> SUB: cik=1041657 company='URBAN ONE, INC.' form=10-Q filed=20180808 period=20180630 fiscal_year=2018 SIC=4832


## 6. Cross-Dataset Joins

**Company-level overlap**: EDGAR-CORPUS CIKs=25,937, XBRL CIKs=10,757, intersection=6,877, intersection/EDGAR-CIKs=26.51%
Structurally low by construction: EDGAR-CORPUS spans 1993-2020, XBRL structured data only exists from ~2009 (mandate) and this fetch starts at 2016q1 - most EDGAR-CORPUS companies from the 1990s-2000s stopped filing, deregistered, or were acquired before the XBRL window even starts.

**2016-2020 (cik, fiscal_year) join** (exact literal restriction, no >=1000-row noise filter): numerator=5,800, denominator=6,950, rate=83.45%

Per-year breakdown (numerator = EDGAR-CORPUS (cik,year) pairs also present in XBRL; denominator = all EDGAR-CORPUS (cik,year) pairs for that year):

| Year | EDGAR (cik,year) pairs | Matched in XBRL | Rate |
|---|---:|---:|---:|
| 2016 | 1,454 | 1,253 | 86.18% |
| 2017 | 1,409 | 1,175 | 83.39% |
| 2018 | 1,377 | 1,156 | 83.95% |
| 2019 | 1,339 | 1,086 | 81.11% |
| 2020 | 1,371 | 1,130 | 82.42% |

This tells us whether 2016-2020 is a justified evaluation window: the per-year rates above should be checked for consistency - if any single year has a materially lower match rate, ground-truth question generation should weight away from it.

## 5. Primary SEC Documents

total files: 990, total size: 4.48 GB, unique CIKs: 990, unique accessions: 990
size distribution: min=444,740 median=3,645,170 p95=9,630,579 max=31,571,327 bytes
filing-year distribution (from accession prefix): {2021: 3, 2022: 24, 2023: 23, 2024: 940}
zero-byte/corrupt files: 0

**Table survival** (deterministic sample of 30, seed=42): 30/30 have >=1 <table>; mean=134.3 median=133 p95=260 max=267 tables/doc
**Inline XBRL presence**: 30/30 (100.0%)

**HTML structure examples**:
  cik=36270 accession=0000950170-24-017990 title='10-K' tables=158 inline-xbrl-facts=4252 chars=14,423,868
  cik=1099800 accession=0001099800-24-000004 title='ew-20231231' tables=89 inline-xbrl-facts=2085 chars=2,807,361
  cik=1024725 accession=0001024725-22-000005 title='ten-20211231' tables=162 inline-xbrl-facts=2958 chars=5,675,066
  cik=73309 accession=0000950170-24-021195 title='10-K' tables=70 inline-xbrl-facts=1714 chars=4,371,466
  cik=1411342 accession=0001411342-24-000021 title='efc-20231231' tables=163 inline-xbrl-facts=5694 chars=8,468,334

## 7. Data Quality Findings

No schema drift detected across quarterly XBRL ZIP headers (sub/num/tag/pre all identical column sets).
EDGAR-CORPUS cik column type: VARCHAR; XBRL facts.cik type: BIGINT. Confirmed a naive `==` comparison between these would silently return empty results (see Part 8 - correct code always applies TRY_CAST(... AS BIGINT) first).

**Invalid `ddate` years (manually followed up on the "1932-2923" range surfaced in Part 4's Critical NUM checks):** 323 / 90,685,753 facts (0.00036%) have a `ddate` year outside a sane 1990-2026 window. Spot-checked: the low end is a real row with `ddate=19320731` (a filer typo, XBRL didn't exist until ~2009); the high end has several rows with `ddate=29231231`/`29230930` (accession `0001654954-24-003228`, `0001017386-24-000018` - almost certainly "2023" mistyped as "2923" in the filer's own submission). Classification: **INFO, not a blocker** - the count is negligible and these are upstream filer errors in the source data, not a bug in our pipeline, but any downstream code building period-based ground truth should filter `ddate` to a plausible year range rather than trusting it blindly.

**EDGAR-CORPUS table-content leakage (followed up on the "1/20" table-survival WARN in Part 4):** manually inspected the one matching sample (`310764_2007.htm`, section_8). It is **not** an HTML `<table>` or markdown table - EDGAR-CORPUS's section stripping is real and no markup survives. What leaks through is the raw *numeric content* of what was originally a table, flattened into tab/newline-separated lines (e.g. `"U.S. Treasury debt securities\n245.0\n\t(0.7)\n\t244.3"`). Classification: **INFO** - confirms structured table markup is genuinely gone (safe for BM25/vector text retrieval), but a small fraction of sections (roughly 1/20 in this sample) retain enough tab-aligned numeric fragments that a downstream chunker should not assume section text is 100% prose-clean.

Summary of findings by severity is at the end of this report (Part 12: Blockers).

## 8. Important Data Semantics


```
                          SEC RAG DATA

  EDGAR-CORPUS                                    MS MARCO
  narrative sections (section_1..15)              separate benchmark only
  91,086 filings, 25,937 CIKs, 1993-2020           8.84M passages, BEIR dev-small
  cik: VARCHAR, tables stripped                    verified referential integrity 100%
        |
        | TRY_CAST(cik AS BIGINT), year
        v
  XBRL SUB (submissions) ---------- XBRL NUM (facts)
  218,166 filings, 10-K/10-Q only    90.7M numeric facts, coreg/segments preserved
  cik: BIGINT, SIC in raw sub.txt    identity key = (adsh,tag,version,ddate,qtrs,uom,coreg,segments)
  only (not in derived table)        23.56% loose restatement rate (superseded - see Check 1: 7.87% strict)
        |
        | accession / cik
        v
  Primary 10-K HTML documents
  990 complete filings, 4.48 GB
  tables + inline XBRL intact (100% of sampled docs)
```

**EDGAR-CORPUS** -> large-scale narrative retrieval (vector/BM25 over section text). **XBRL** -> deterministic numeric QA + ground truth (SQL-over-facts). **Primary documents** -> tables + parsing + inline-XBRL evidence alignment (tree navigation). **MS MARCO** -> retrieval/evaluation harness sanity check only, never mixed into the SEC corpus.

## 9. Ten Concrete Data Examples

1. EDGAR-CORPUS filing: filename=1556487_2020.htm cik=1556487 year=2020
2. Item 1 excerpt: 'Item 1. Business.\nOmitted.\nItem 1A.'...
3. Item 7 excerpt: 'Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations.\nOmitted.\nItem 7A.'...
4. XBRL Assets fact: adsh=0001144204-18-042656 cik=1041657 company='URBAN ONE, INC.' ddate=20171231 value=435,031,000
5. XBRL Revenues fact: adsh=0001558370-20-009670 cik=910329 company='MEDIFAST INC' ddate=20190630 qtrs=2 value=352,979,000
6. Fact with coreg (co-registrant, e.g. a subsidiary reported alongside the parent): ('0001594686-19-000034', 1594686, 'CashDistributionsAndLossesInUnconsolidatedEntitiesAtEquity', 'WashingtonPrimeGroupLP', 15421000.0)
7. Fact with segment metadata (a dimensional breakdown, not the consolidated total): ('0001654954-22-013824', 1126115, 'NetIncomeLoss', 'EquityComponents=RetainedEarnings;', -13976.0)
8. Restated concept across filings: cik=1443089 tag=StockIssuedDuringPeriodSharesIssuedForServices ddate=20211231 qtrs=1 -> [('0001683168-22-003390', 10000000.0), ('0001683168-22-003390', -10000000.0), ('0001683168-22-001842', 10000000.0), ('0001683168-23-003638', -10000000.0), ('0001683168-23-003638', 10000000.0), ('0001683168-22-001842', -10000000.0)]
9. Primary HTML table sample from data\raw\primary\36270\0000950170-24-017990.htm: '☒ ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EX CHANGE ACT OF 1934'...
10. MS MARCO query -> relevant passage: QUERY='what is the best used by date'  PASSAGE='Use By Date. A â\x80\x98use by dateâ\x80\x99 is the product manufacturers recommended date to use the product in order to still get peak quality. After that date, the product quality could decline, and if proper storage measures arenâ\x80\x99t used, your health could '...

## 10. Confirmed Assumptions

- MS MARCO corpus rows: 8,841,823 matches prior (8,841,823)
- MS MARCO dev-small (validation split distinct queries): 6,980 matches prior (6,980)
- EDGAR-CORPUS distinct filings: 91,086 matches prior (91,086)
- EDGAR-CORPUS distinct CIKs: 25,937 matches prior (25,937)
- EDGAR-CORPUS section_1A fill rate: 25.6% matches prior (25.6%)
- EDGAR-CORPUS section_1B fill rate: 24.4% matches prior (24.4%)
- EDGAR-CORPUS section_9A fill rate: 30.1% matches prior (30.1%)
- EDGAR-CORPUS section_9B fill rate: 27.0% matches prior (27.0%)
- EDGAR-CORPUS section_15 fill rate: 32.4% matches prior (32.4%)
- XBRL facts: 90,685,753 matches prior (~90.7M (90,685,753))
- XBRL true duplicate rate (full key): 32 / 90685753 (0.0000%) matches prior (32 / ~90.7M (~0.0000%))
- XBRL restatement rate (loose method, superseded by Check 1's 7.87% strict value-revision rate): 23.56% matches prior (23.56%)
- Overall CIK overlap (EDGAR-CORPUS vs XBRL): 26.51% matches prior (26.51%)
- 2016-2020 CIK/year join (exact literal restriction, ANY XBRL form): 83.45% - NOT the same measurement as the prior 81.71%; they use different overlap-window definitions (see 'Methodological Corrections' below). Both numbers are superseded for Phase 2 planning by the 10-K-only, semantically-aligned figure in 'Check 2'.
- Primary docs: 990 matches prior (990)
- Primary docs table survival & mean tables/doc: 30/30 docs, mean=134.3 matches prior (~100% docs, ~136 tables/doc)
- Primary docs inline-XBRL presence: 100.0% matches prior (100%)

## 11. Assumptions That Differed From Prior Numbers

- EDGAR-CORPUS tables present in sampled sections: prior=0/10 (prior), now=1/20 - reclassified INFO. Structured table markup is absent; a small amount of flattened numeric/table-like text survives. EDGAR-CORPUS does NOT contain structured tables.

## 12. Warnings / Limitations


## 13. Blockers

None.

## Methodological Corrections (post-freeze review)

Two corrections were identified after this report's first pass and are detailed in the 'Check 1' / 'Check 2' sections below:

1. **81.71% vs 83.45% are not directly comparable.** They use different overlap-window definitions (an earlier 'XBRL years with >=1000 rows' window vs this audit's literal 2016-2020 restriction), not two measurements of the same thing. Neither is 'wrong' under its own definition. See 'Check 2' below for the semantically-correct **10-K-only** coverage figure, which supersedes both for Phase 2 planning.
2. **'Restatement rate' (23.56%) is renamed 'cross-filing value revision rate.'** The original metric measured the same (cik,tag,ddate,qtrs) concept reported with a differing value across filings, including segment/dimensional facts and mismatched units - not a proven accounting restatement. See 'Check 1' below for the corrected, stricter figure computed on consolidated, non-dimensional, same-unit facts only, with same-accession duplicates collapsed first.


## Check 1: Strict Cross-Filing Value-Revision Rate

**Population**: `xbrl.facts` WHERE (coreg IS NULL OR coreg='') AND (segments IS NULL OR segments='') - consolidated, non-dimensional facts only.

**Grain**: (cik, tag, ddate, qtrs, uom). **Cross-filing repeat**: >1 distinct `adsh` after collapsing same-accession duplicates to one row. **Revision candidate**: >1 distinct `value` among those accessions.

**Variant A - all tags**: A(repeated groups)=13,276,577  B(differing-value groups)=1,044,801  rate=B/A=7.87%
**Variant B - standard non-abstract tags only (TAG.custom=0, TAG.abstract=0)**: A=12,276,158  B=982,323  rate=8.00%
**Variant C - 15-tag supported registry**: A=1,916,013  B=199,117  rate=10.39%

| Metric | Previous (loose) method | Strict method (Variant A, all tags) |
|---|---:|---:|
| repeated groups | 14,260,160 | 13,276,577 |
| differing-value groups | 3,359,610 | 1,044,801 |
| rate | 23.56% | 7.87% |

Strict rate **decreased materially from** the loose 23.56% figure. The loose method excluded only coreg; it left in segment/dimensional facts (52.7% of all facts), did not require matching `uom`, and did not collapse same-accession duplicate rows before comparing distinct values. The strict method removes each of those sources of apparent-but-not-real disagreement, so a materially different rate would mean the loose metric was measurably distorted by them; a similar rate means those factors were not, in practice, the main driver.

**5 example groups with genuinely differing values** (deterministic, hash-ordered):

- cik=1575828 tag=IncreaseDecreaseInAccountsReceivable ddate=20210630 qtrs=2 uom=USD
    adsh=0001437749-21-018804 form=10-Q filed=20210806 company="FRANK'S INTERNATIONAL N.V." value=17,618,000.00
    adsh=0001437749-22-018896 form=10-Q filed=20220804 company='EXPRO GROUP HOLDINGS N.V.' value=38,756,000.00
- cik=1022079 tag=NetCashProvidedByUsedInFinancingActivities ddate=20141231 qtrs=4 uom=USD
    adsh=0001022079-16-000195 form=10-K filed=20160226 company='QUEST DIAGNOSTICS INC' value=92,000,000.00
    adsh=0001022079-17-000032 form=10-K filed=20170222 company='QUEST DIAGNOSTICS INC' value=86,000,000.00
- cik=1568669 tag=MortgageServicingRightsMSRAmortizationImpairmentFairValueChangeFromNonAffiliates ddate=20161231 qtrs=4 uom=USD
    adsh=0001558370-17-001522 form=10-K filed=20170309 company='PENNYMAC FINANCIAL SERVICES, INC.' value=-324,198,000.00
    adsh=0001558370-18-001782 form=10-K filed=20180309 company='PENNYMAC FINANCIAL SERVICES, INC.' value=324,198,000.00
- cik=1134765 tag=InterestPaidNet ddate=20180930 qtrs=3 uom=USD
    adsh=0001654954-18-013017 form=10-Q filed=20181120 company='TRUE DRINKS HOLDINGS, INC.' value=432.00
    adsh=0001654954-19-013045 form=10-Q filed=20191114 company="CHARLIE'S HOLDINGS, INC." value=0.00
- cik=1117057 tag=NetCashProvidedByUsedInOperatingActivities ddate=20170331 qtrs=1 uom=USD
    adsh=0001062993-17-005218 form=10-Q filed=20171211 company='AMERICAN LORAIN CORP' value=7,603,636.00
    adsh=0001062993-18-002331 form=10-Q filed=20180521 company='AMERICAN LORAIN CORP' value=7,031,851.00

**Terminology correction**: this metric measures *the same (cik,tag,period,uom) concept reported with a different value across two or more separate accessions*. That is accurately called a **cross-filing value revision rate**, not a formal accounting 'restatement' - a real restatement is a specific legal/accounting event (e.g. an Item 4.02 8-K or an explicit restatement footnote) that value-level XBRL data alone cannot prove. Some of the differing values above may be comparative-period figures reprinted (and sometimes lightly adjusted, e.g. for a later reclassification) in a subsequent filing rather than formal restatements. The rest of this report uses 'value revision' going forward; 'restatement' is retained only in historical Part 5 text with a pointer back to this section.


## Check 2: EDGAR-CORPUS <-> XBRL 10-K-Only Coverage

XBRL submissions restricted to `form='10-K'` only: 53,809 rows (excludes 10-Q, 10-K/A, 20-F, 40-F, S-1, etc).

**Step 2A - year-semantics evidence** (all EDGAR-CORPUS (cik,year) pairs where the CIK has >=1 XBRL 10-K anywhere - 30,694 pairs; a pair counts as a match on a field if ANY of that cik's 10-Ks has that field equal to the EDGAR year):
  EDGAR year == XBRL `fy`: 6,766/30,694 (22.04%)
  EDGAR year == YEAR(XBRL `period`): 6,736/30,694 (21.95%)
  EDGAR year == YEAR(XBRL `filed`): 5,263/30,694 (17.15%)

  concrete examples (EDGAR year vs that cik's XBRL fy / period_year / filed_year):
    cik=1570279 EDGAR_year=2018  adsh=0001165527-17-000096 fy=2016 period_year=2016 filed_year=2017
    cik=1570279 EDGAR_year=2018  adsh=0001165527-19-000040 fy=2018 period_year=2018 filed_year=2019
    cik=1570279 EDGAR_year=2018  adsh=0001165527-18-000059 fy=2017 period_year=2017 filed_year=2018
    cik=1570279 EDGAR_year=2018  adsh=0001165527-16-000709 fy=2015 period_year=2015 filed_year=2016
    cik=1570279 EDGAR_year=2018  adsh=0001640334-20-001593 fy=2019 period_year=2019 filed_year=2020

**Conclusion**: measured 2016-2020 coverage under each alignment (Step 2C below) - fy 94.24%, period year 95.04%, filed year 87.85%. For Phase 2, XBRL `fy` is the chosen semantic alignment field for EDGAR-CORPUS `year`. XBRL `period` year produces nearly identical coverage, while filing year performs materially worse. The available data supports `fy` as the appropriate fiscal-year alignment field, but does not independently prove the original EDGAR-CORPUS field-definition semantics - `fy` is used below because it is semantically appropriate, not because it produces the largest number.

**Step 2C - coverage under all three alignments, 2016-2020** (denominator here is only EDGAR pairs whose cik has >=1 XBRL 10-K ever, for apples-to-apples comparison across alignments; Step 2B below uses the full, correct denominator):

| Alignment | Matched | Total | Coverage |
|---|---:|---:|---:|
| EDGAR year <-> XBRL fy | 5,646 | 5,991 | 94.24% |
| EDGAR year <-> XBRL period year | 5,694 | 5,991 | 95.04% |
| EDGAR year <-> XBRL filed year | 5,263 | 5,991 | 87.85% |

The field chosen in Step 2A (XBRL fy) is used below **because it is the semantically correct field**, not because it produces the largest number here.

**Step 2B - 10-K-only coverage, 2016-2020, aligned on XBRL fy**:

| Year | EDGAR pairs | XBRL 10-K matched | Coverage |
|---|---:|---:|---:|
| 2016 | 1,454 | 1,197 | 82.32% |
| 2017 | 1,409 | 1,145 | 81.26% |
| 2018 | 1,377 | 1,126 | 81.77% |
| 2019 | 1,339 | 1,066 | 79.61% |
| 2020 | 1,371 | 1,112 | 81.11% |
| **TOTAL** | **6,950** | **5,646** | **81.24%** |

**Step 2D - unmatched-pair classification** (1,304 unmatched (cik,year) pairs, 2016-2020, XBRL fy alignment):

  959 (73.5% of unmatched) - no XBRL 10-K available (cik never files a plain 10-K in our data)
  209 (16.0% of unmatched) - XBRL 10-K coverage starts later
  81 (6.2% of unmatched) - XBRL 10-K coverage ends before this year / company stopped filing
  52 (4.0% of unmatched) - filing-year/fiscal-year offset (off by exactly 1 year)
  3 (0.2% of unmatched) - other / CIK-year gap within coverage window

1,249/1,304 (95.8% of unmatched, ~18.0% of ALL 2016-2020 pairs) are structural - the company simply has no XBRL 10-K for that period - not a join-definition bug. This is evidence the residual gap is structural, not an artifact of our methodology.

**Step 2E**: EDGAR-CORPUS's schema (filename, cik, year, section_1..15) carries no accession-number field and none can be reliably reconstructed from it, so accession-level matching is not possible with this dataset. Stated explicitly per instructions; not treated as a blocker.

## Frozen Phase 1 Metrics

Numbers downstream Phase 2 work is authorized to cite as the final Phase 1 dataset statistics. Where a metric has a non-obvious definition, the definition is given alongside the number.

| Metric | Value |
|---|---:|
| MS MARCO passages | 8,841,823 |
| MS MARCO dev-small (validation) queries | 6,980 |
| EDGAR-CORPUS filings | 91,086 |
| EDGAR-CORPUS CIKs | 25,937 |
| EDGAR-CORPUS year range | 1993-2020 |
| XBRL facts | 90,685,753 |
| XBRL submissions (10-K+10-Q, as loaded by fetch_xbrl.py) | 218,166 |
| XBRL CIKs | 10,757 |
| XBRL distinct tags | 291,429 |
| XBRL full-key duplicate count/rate | 32 / 90,685,753 = 0.000035% |
| Cross-filing value revision rate - Variant A, all tags | 1,044,801 / 13,276,577 = 7.87% |
| Cross-filing value revision rate - Variant B, standard non-abstract tags | 982,323 / 12,276,158 = 8.00% |
| Cross-filing value revision rate - Variant C, 15-tag registry | 199,117 / 1,916,013 = 10.39% |
| Value-revision definition | population: coreg AND segments both blank; grain: (cik,tag,ddate,qtrs,uom); cross-accession only; same-accession dupes collapsed first (see 'Check 1' section) |
| EDGAR-CORPUS <-> XBRL 10-K-only coverage, 2016-2020 | 5,646 / 6,950 = 81.24% |
| 10-K coverage year semantics used | XBRL `fy` chosen as the semantic fiscal-year alignment field for EDGAR-CORPUS `year` - period year gives near-identical coverage (95.04% vs 94.24%), filed year performs materially worse (87.85%); supports `fy` as appropriate, does not independently prove EDGAR-CORPUS's original field semantics (see 'Check 2', Step 2A) |
| 10-K coverage unmatched pairs, structural share | 1,249 / 1,304 (95.8%) - company has no XBRL 10-K for that period, not a join-definition issue |
| Primary filings | 990 |
| Primary docs table survival | 30/30 sampled (100%), mean 134.3 tables/doc |
| Primary docs inline-XBRL survival | 30/30 sampled (100%) |
| Raw source data size (MS MARCO + EDGAR-CORPUS + XBRL ZIPs + Primary HTML) | approximately 15.36 GB |
| Total `data/` directory size (raw + derived: xbrl.duckdb, audit_xbrl_meta, reports) | 26.28 GB |

## 14. Final Recommendation

**PHASE 2 READY**

Strict cross-filing value-revision rate (all tags, consolidated facts only): 7.87% (1,044,801/13,276,577) - materially lower than the original loose 23.56% figure; segment/dimensional facts, unit mismatches, and same-accession duplicate/value rows (not coreg, which the loose method had already excluded) were the main drivers of the inflated loose metric. 10-K-only EDGAR<->XBRL coverage, 2016-2020, aligned on XBRL fy (the chosen semantic fiscal-year alignment field, not the field that happened to maximize coverage - see Check 2): 5,646/6,950 = 81.24%, with 1,249/1,304 of the unmatched pairs structural (company has no XBRL 10-K for that period), not a join-definition artifact. Sufficient aligned ground truth exists to proceed to Phase 2 while explicitly selecting the aligned (cik,year) subset for eval-question generation.

### Phase 1 Freeze

Phase 1 data acquisition, validation, and methodological review are complete.

The raw source datasets are now considered frozen for downstream development. The metrics in `Frozen Phase 1 Metrics` are the authoritative Phase 1 figures. Historical measurements retained elsewhere in this report are included only for traceability and must not be used as Phase 2 headline metrics.

**Status: PHASE 1 COMPLETE — DATA FROZEN — PHASE 2 READY**
