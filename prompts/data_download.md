# Prompt: download all four datasets and validate

Paste everything below the line into Claude Code. Fill in the bracketed value.

---

## Context

I'm building a RAG system with two tracks:

- **Benchmark track** — MS MARCO, used only to verify my retrieval and eval
  code is correctly wired against published baselines. Not the project corpus.
- **Project track** — SEC filings. This is what the project is actually about.

All previously downloaded data has been deleted. `src/ingest/` contains only
an empty `__init__.py`; assume no ingestion code exists.

My environment: `SEC_USER_AGENT="[YOUR NAME your@email.com]"`, storage root
`./data`, ~380 GB free. Expected total footprint below is ~17 GB.

### Hard-won context from a previous run — do not rediscover these

1. **Never download full SEC SGML submissions.** They include every exhibit.
   Measured: 27 GB for 1,500 filings, which extrapolates to ~1.8 TB. Fetch
   the **primary document only**.
2. **XBRL `num.txt` needs `coreg` and `segments` columns preserved.** Dropping
   them collapses per-holding fund line items onto the same key and produces a
   false 56.5% duplicate rate. The SEC-documented unique key is
   `(adsh, tag, version, ddate, qtrs, uom, coreg, segments)`.
3. **Restatement detection keys on `(cik, tag, ddate, qtrs)`**, not
   `(cik, fiscal_year, tag)` — the latter conflates a 10-Q quarter value with
   a 10-K annual value for the same nominal year.
4. **DuckDB cannot bind a prepared parameter inside
   `CREATE VIEW ... FROM read_parquet(?)`.** Inline the path.
5. **`master.idx` files are latin-1 encoded**, not UTF-8.
6. **Clean up orphaned `.part` files** when a download fails, or a resume run
   will treat them as complete.

### Verified dataset locations

- `BeIR/msmarco` — config `corpus` (8.8M rows, ~1.6 GB parquet: `_id`,
  `title`, `text`); config `queries` (510K rows)
- `BeIR/msmarco-qrels` — splits `train` / `validation` / `test`
  (`query-id` int64, `corpus-id` int64, `score`)
- `c3po-ai/edgar-corpus` — parquet mirror of EDGAR-CORPUS. Use config `full`
  (splits train 47K / test 22K / validation 22.1K ≈ **91K distinct filings**,
  ~5.6 GB). Columns: `filename`, `cik`, `year`, and `section_1` …
  `section_15` as separate text columns. **Tables are stripped from this
  dataset** — text only. Use the parquet mirror, not `eloukas/edgar-corpus`,
  which relies on a deprecated loading script.
- SEC Financial Statement Data Sets — quarterly ZIPs. If the URL 404s, find
  the current one from SEC's DERA data page rather than working around it.

## Task

Work in stages. **Do not start a stage until the previous one validates.**

### Stage 0 — scaffolding

Write `src/ingest/common.py`: `STORAGE_ROOT` from env (default `./data`),
rate limiter capped at 8 req/sec, retrying `requests` session with backoff on
429/500/502/503/504, atomic streaming download (write `.part`, rename on
success, delete `.part` on failure), and a `check_user_agent()` that refuses
to run without an email in `SEC_USER_AGENT`.

### Stage 1 — MS MARCO (~2 GB)

`src/ingest/fetch_msmarco.py`. Write `data/msmarco/{corpus,queries,qrels_*}.parquet`.
Support `--limit-corpus N` for development. Skip anything already on disk.

Note the ID type mismatch: qrels use int64 while corpus/queries use string
`_id`. Verify the join works after casting and report the match rate.

Also determine **which qrels split corresponds to the standard MS MARCO
"dev small" (~6,980 queries)** — this is what published baselines report
against, and comparing to the wrong split makes my numbers meaningless.

### Stage 2 — EDGAR-CORPUS (~5.6 GB)

`src/ingest/fetch_edgar_corpus.py`. Download config `full`, all three splits,
write to `data/edgar_corpus/`.

Report: distinct filings (dedupe across splits), year range, distinct CIKs,
and **per-section fill rate** — what fraction of filings have non-empty
`section_1A`, `section_7`, etc. Sparse sections directly affect whether tree
navigation is viable.

### Stage 3 — XBRL (~3 GB)

`src/ingest/fetch_xbrl.py`. Download quarterly ZIPs for **2016q1–2024q4**
(36 quarters — covers EDGAR-CORPUS's 2016-2020 tail plus the fresh-docs
window). Load into `data/xbrl.duckdb` as `submissions` and `facts`.

Preserve `coreg` and `segments` (see context note 2). Restrict `submissions`
to 10-K and 10-Q.

### Stage 4 — fresh primary documents (~6 GB)

`src/ingest/fetch_primary_docs.py`. New code — this is the only piece with
no prior version.

Purpose: EDGAR-CORPUS strips tables, so I need a small set of **complete,
table-intact filings** to build and test table extraction and inline-XBRL
parsing.

- Select ~1,000 recent 10-K filings, 2021–2024, from large companies.
  Pick companies by total `Assets` in the XBRL database from Stage 3 —
  don't hardcode a ticker list.
- For each filing, fetch `Archives/edgar/data/{cik}/{accession_nodash}/index.json`
  to discover the primary document filename, then fetch **only that file**.
  Two requests per filing, ~2,000 total, a few minutes at 8 req/sec.
- Write to `data/raw/primary/{cik}/{accession}.htm`
- Verify the URL pattern on the first filing before looping. If `index.json`
  isn't available, find the correct mechanism rather than guessing.
- Report actual total size. If it exceeds 15 GB, stop and tell me before
  continuing.

### Stage 5 — validation

`src/ingest/validate.py`, one script covering all four sources. Compute real
numbers. Never print a pass for a check that did not run.

**MS MARCO**
- Row counts; null/empty `text`; duplicate `_id`
- Referential integrity: fraction of `qrels.corpus-id` present in corpus, and
  `qrels.query-id` present in queries. Anything below 100% caps my achievable
  recall below 1.0 and would make me think retrieval is broken when it isn't
- Passage length distribution; relevant-docs-per-query distribution
- Print 3 random (query, relevant passage) pairs in full for eyeballing

**EDGAR-CORPUS**
- Distinct filings after dedupe across splits; year and CIK coverage
- Per-section fill rate and text length distribution
- Confirm tables really are absent (sample 10 `section_8` values and report
  whether numeric tabular content survives in any form)

**XBRL**
- Counts; duplicate rate on the **full** key (expect ~0%); restatement rate
  on `(cik, tag, ddate, qtrs)`
- Coverage for ~15 common eval tags (Revenues, ResearchAndDevelopmentExpense,
  NetIncomeLoss, Assets, Liabilities, OperatingIncomeLoss, etc.)
- Sanity: negative `Assets`, non-USD `uom`, absurd magnitudes

**Primary docs**
- Downloaded vs requested; zero-byte or under-10 KB files
- Do `<table>` elements survive? Report mean table count per document
- Is inline XBRL present (`ix:` namespace tags)? What fraction

**Cross-source**
- CIK overlap: EDGAR-CORPUS ∩ XBRL, and primary docs ∩ XBRL
- For filings present in both EDGAR-CORPUS and XBRL, can I join on
  `(cik, year)`? Report the match rate — this determines whether XBRL facts
  can serve as ground truth for EDGAR-CORPUS documents, which is the single
  most important question in this validation

**Thresholds**
- FAIL: MS MARCO referential integrity below 99%; any table empty;
  EDGAR-CORPUS ↔ XBRL CIK overlap below 50%; primary docs with no tables
- WARN: XBRL duplicate rate above 5%; restatement rate above 10%; any
  section fill rate below 50%; zero-byte files present

Write `data/validation_report.md` and print the same content.

### Stage 6 — Progress.md

Rewrite `Progress.md` as an engineering log, not a summary. Include:

- Exact commands run, per stage
- Real numbers throughout — never placeholders
- **Bugs found, root cause, and fix.** If a script needed changing, say what
  was wrong and why. This is the most valuable section
- Where my stated expectations differed from reality, with both numbers
  (e.g. I estimated ~2 GB for XBRL and ~6 GB for primary docs — report actual)
- Verdict per source with the threshold table
- Plain-language read: does this data support the four retrieval paths
  (vector, BM25, SQL-over-XBRL, tree navigation)? Which are solid, which
  are shaky, and why?
- Files touched, relative paths
- Open issues needing my sign-off

If `Progress.md` already has content, append a dated section instead of
overwriting.

## Constraints

- DuckDB or polars for analysis, never pandas — corpus is 8.8M rows
- Never exceed 8 req/sec against SEC
- Never re-download what's on disk; every fetch stage must be resumable
- Do not run Stage 4 until Stage 3 validates (it depends on the XBRL data
  to pick companies)
- If a check can't be computed, print why rather than skipping silently
- Stop and ask if any stage's on-disk size exceeds my estimate by more than 2×

## At the end, tell me

1. Which of the four retrieval paths this data actually supports, and which
   have gaps
2. Whether XBRL facts can serve as ground truth for EDGAR-CORPUS documents,
   based on the measured join rate
3. The real total disk footprint versus my ~17 GB estimate
4. Anything that would make my measurements misleading if I don't know it