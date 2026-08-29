# Progress: four-source RAG data pipeline (MS MARCO benchmark + SEC project corpus)

Ran `prompts/data_download.md` (the four-dataset version) end to end.
`src/ingest/` started as an empty `__init__.py`; all previously downloaded
data had been deleted. Every stage validated before the next one started.

## Commands run, per stage

```
# Stage 1 - MS MARCO
python -m src.ingest.fetch_msmarco

# Stage 2 - EDGAR-CORPUS
python -m src.ingest.fetch_edgar_corpus

# Stage 3 - XBRL
export SEC_USER_AGENT="Your Name your.email@example.com"
python -m src.ingest.fetch_xbrl --start 2016q1 --end 2024q4

# Stage 4 - primary documents (ran only after Stage 3 validated)
python -m src.ingest.fetch_primary_docs --limit 1000 --year-from 2021 --year-to 2024

# Stage 5 - validation
python -m src.ingest.validate
```

## Real numbers, per source

| Source | Real numbers |
|---|---|
| MS MARCO | corpus 8,841,823 rows; queries 509,962; qrels train 532,751 (502,939 distinct queries), validation 7,437 (6,980 distinct), test 9,260 (43 distinct) |
| EDGAR-CORPUS | 91,086 distinct filings, 25,937 distinct CIKs, years 1993-2020 |
| XBRL | submissions 218,166; facts 90,685,753; companies 10,757; distinct tags 291,429 |
| Primary docs | 990/1000 downloaded (10 companies had no 10-K in 2021-2024); 4.48 GB |

## Bugs found, root cause, and fix

This is the most valuable section - five real bugs, three of them in code I
wrote for this run.

### 1. `fetch_filings`-style `UNNEST` bug did not recur, but the coreg/segments lesson from the prior run did

Carried forward from the earlier SEC-only run: `fetch_xbrl.py`'s `facts`
table preserves `coreg` and `segments` from `num.txt` from the start this
time. Verified: duplicate rate on the full SEC-documented key
`(adsh, tag, version, ddate, qtrs, uom, coreg, segments)` is **0.0000%**
(32 rows out of 90,685,753).

### 2. `index.json` cannot actually identify a filing's primary document

The task spec called for discovering the primary document via
`Archives/edgar/data/{cik}/{accession}/index.json`. Verified against a
live filing (AAPL's FY2024 10-K, accession 0000320193-24-000123) before
looping, as instructed:

```
{'name': 'a10-kexhibit10199282024.htm', 'type': 'text.gif', 'size': '56948'}
```

Every entry's `"type"` field is a generic MIME-icon class
(`text.gif`, `compressed.gif`) - it does not distinguish the primary
10-K document from an exhibit. Using it would mean guessing from
filename patterns, exactly what the task said not to do.

**Fix**: used `data.sec.gov/submissions/CIK{cik:010d}.json` instead,
which exposes `primaryDocument` directly per filing. Same total request
budget (~1 request per company + 1 per filing ≈ 2,000), but the mapping
is exact instead of guessed. Implemented in
[fetch_primary_docs.py](src/ingest/fetch_primary_docs.py).

### 3. `.part` cleanup was missing from the shared download helper

The prior run's `edgar_common.py` left a `.part` file on disk when
`download_to()` raised partway through a stream - harmless for resume
correctness (only the final filename is checked) but wastes disk on
large files and was flagged as a known issue to fix. Fixed in
[common.py](src/ingest/common.py): `download_to()` now deletes the
`.part` file in an `except` clause before re-raising.

### 4. Cross-source CIK overlap was silently computing 0% due to a type mismatch

First `validate.py` run reported:

```
[FAIL] Cross-source / CIK overlap: EDGAR-CORPUS vs XBRL: 0 / 25,937 (0.00%)
```

Root cause: EDGAR-CORPUS stores `cik` and `year` as `VARCHAR`
(`'92116'`), while the XBRL tables store `cik` as `BIGINT`. The Python
set intersection `xbrl_ciks & edgar_ciks` compared strings against
integers and silently returned empty - no error, no warning, just a
wrong zero. **Fix**: `TRY_CAST(cik AS BIGINT)` / `TRY_CAST(year AS
INTEGER)` in every cross-source query. Real overlap: **26.51%**
(6,877 / 25,937 CIKs).

### 5. The (cik, year) join was also silently wrong - a set-comprehension bug this time

After fixing #4, the join check still reported exactly **0.00%** match
even for CIKs confirmed to overlap. Root cause, in my own new code:

```python
xbrl_cik_years = {r[0] for r in con.execute(
    "SELECT DISTINCT cik, fiscal_year FROM facts ..."
).fetchall()}
```

`r[0]` kept only the `cik` half of each `(cik, fiscal_year)` tuple -
copy-pasted from the CIK-only overlap check just above it. The
membership test `(cik, year) in xbrl_cik_years` was then comparing a
2-tuple against a set of bare integers, which can never match. **Fix**:
`set(con.execute(...).fetchall())` to keep full tuples. Real match rate
on the years both sources actually cover: **81.71%**.

### 6. The "overlap window" itself needed a data-driven definition, not a naive one

Fixing #5 first produced 27.17% (still clearly wrong) because "XBRL
years present" was defined as any year that appears in the fiscal_year
column at all - including single-digit-row artifacts back to 2004 (SEC
data occasionally carries stray prior-year comparative tags). Those
noise years inflated the denominator with EDGAR-CORPUS rows that could
never realistically match. **Fix**: restricted "XBRL coverage" to years
with >=1,000 submissions, which cleanly separates the real 2015-2025
coverage from the noise. Final, correct number: 81.71%
(6,910 / 8,457 pairs).

## Where estimates differed from reality

| Item | Estimated | Actual |
|---|---|---|
| MS MARCO total | ~2 GB | 1.6 GB |
| EDGAR-CORPUS total | ~5.6 GB | 5.4 GB (after removing redundant download shards) |
| XBRL total footprint | ~3 GB | 2.9 GB raw zips + **6.6 GB DuckDB file** + 14 GB disposable extracted-text intermediate. The DuckDB file alone (with two indices over 90.7M rows) is more than double the raw-zip estimate - `num.txt`/`sub.txt` decompress to several times their zipped size before indexing. |
| Primary docs | ~6 GB | 4.48 GB (990/1000 - inline-XBRL 10-K primary documents run smaller than exhibit-heavy full submissions) |
| **Total project data** | **~17 GB** | **35 GB during the run, 21 GB after deleting the disposable `data/interim/xbrl` extraction cache** (with the user's confirmation - flagged per the "stop if >2x estimate" constraint, since the XBRL stage alone briefly hit ~23.5 GB against its ~3 GB estimate) |

380 GB free disk was never remotely at risk either way, but the XBRL
estimate was the one worth naming explicitly for next time: budget for
the loaded-and-indexed DuckDB size, not the compressed download size.

## Verdict per source

Full detail: [data/validation_report.md](data/validation_report.md)

| Source | Check | Result | Threshold |
|---|---|---|---|
| MS MARCO | referential integrity (all 3 splits) | 100.00% | FAIL < 99% |
| MS MARCO | duplicate `_id`, null/empty text | 0 | - |
| EDGAR-CORPUS | per-section fill rate | 5 of 20 sections < 50% (section_1A 25.6%, section_1B 24.4%, section_9A 30.1%, section_9B 27.0%, section_15 32.4%) | WARN < 50% |
| EDGAR-CORPUS | tables genuinely absent (10-sample check) | 0/10 show any tabular structure | - |
| XBRL | duplicate rate, full key | 0.0000% | WARN > 5% |
| XBRL | restatement rate (cik,tag,ddate,qtrs) | 23.56% | WARN > 10% |
| XBRL | negative Assets / non-USD uom | 33,322 negative Assets rows (~0.5% of Assets facts); 8.17M non-USD uom rows (9.0% of facts, mostly `shares`/`pure`/FX - expected for non-monetary tags) | - |
| Primary docs | table survival | 298/300 sampled docs have >=1 `<table>`, mean 135.8 tables/doc | FAIL if none had tables |
| Primary docs | inline XBRL presence | 300/300 (100%) | - |
| Cross-source | CIK overlap, EDGAR-CORPUS vs XBRL | **26.51% - FAIL** (structural: EDGAR-CORPUS spans 1993-2020, XBRL only 2016-2024) | FAIL < 50% |
| Cross-source | (cik,year) join, years both sources cover | **81.71%** | the number that actually answers the ground-truth question |

**Overall verdict: FAIL** (1 hard threshold failure - the raw CIK
overlap - plus 4 warnings). See plain-language read below for why the
FAIL is mostly definitional rather than a real data problem.

## Plain-language read: does this support the four retrieval paths?

- **Vector / BM25 (MS MARCO benchmark track)**: solid. 100% referential
  integrity on all three splits, zero nulls/duplicates, dev-small
  confirmed exact (6,980 queries) so published baselines are a valid
  comparison. Nothing shaky here.

- **Vector / BM25 (EDGAR-CORPUS, project track text)**: solid for the
  numbered sections (90%+ fill on 15 of 20), shaky for Item 1A/1B/9A/9B
  (25-30% fill) and Item 15 (32%) - many older or shorter filings simply
  don't populate those items, which is a property of the source
  filings, not a scraping defect. Confirmed tables are genuinely gone
  (0/10 samples show any surviving tabular structure), not just
  detagged-but-present.

- **SQL-over-XBRL**: solid. True duplicate rate is ~0%, all 15 eval tags
  have tens of thousands of company-years of coverage, and the 23.56%
  restatement rate is real but resolvable by picking one canonical
  value per (cik,tag,ddate,qtrs) - same conclusion as the earlier
  SEC-only run.

- **Tree navigation (primary docs)**: solid. 990 complete, table-intact,
  inline-XBRL-tagged 10-Ks from the largest filers by Assets, all under
  the 15 GB stop threshold at 4.48 GB. 298/300 sampled docs retain
  tables (mean 135.8/doc) and 100% carry inline XBRL - both text and
  structured extraction are viable here.

- **Can XBRL serve as ground truth for EDGAR-CORPUS documents?** Yes,
  for the years both sources actually cover. The raw CIK-overlap number
  (26.51%) fails the 50% threshold, but that's almost entirely a
  consequence of the two sources' non-overlapping time ranges
  (EDGAR-CORPUS 1993-2020, XBRL 2016-2024) rather than a data-quality
  problem - most of EDGAR-CORPUS's 25,937 companies simply stopped
  filing, deregistered, or predate the XBRL mandate before 2016. Within
  the years both sources cover, the (cik,year) join rate is **81.71%**,
  which is the number that should drive the eval-question design: build
  ground-truth questions against EDGAR-CORPUS filings from 2016-2020
  specifically, not the full 1993-2020 span.

## Files touched

- [src/ingest/common.py](src/ingest/common.py) - renamed from the prior run's `edgar_common.py`; added `.part` cleanup on failed downloads
- [src/ingest/fetch_msmarco.py](src/ingest/fetch_msmarco.py) - new
- [src/ingest/fetch_edgar_corpus.py](src/ingest/fetch_edgar_corpus.py) - new
- [src/ingest/fetch_xbrl.py](src/ingest/fetch_xbrl.py) - carried forward from the prior run (coreg/segments preserved from the start), quarter range changed to 2016q1-2024q4
- [src/ingest/fetch_primary_docs.py](src/ingest/fetch_primary_docs.py) - new, no prior version
- [src/ingest/validate.py](src/ingest/validate.py) - new, covers all four sources plus cross-source checks
- `data/msmarco/{corpus,queries,qrels_train,qrels_validation,qrels_test}.parquet`
- `data/edgar_corpus/{train,test,validation}.parquet`
- `data/xbrl.duckdb`, `data/raw/xbrl/*.zip`
- `data/raw/primary/{cik}/{accession}.htm` (990 files)
- `data/validation_report.md`

## Open issues needing sign-off

1. **EDGAR-CORPUS eval scope**: build eval questions against EDGAR-CORPUS
   filings from 2016-2020 (where the 81.71% XBRL join rate applies), not
   the full 1993-2020 range, if XBRL facts are meant to be ground truth.
2. **Sparse EDGAR-CORPUS sections**: Item 1A/1B/9A/9B and Item 15 are
   30% or less filled. If tree navigation depends on these items
   specifically, expect real gaps for a third of filings - this is a
   property of the source data, not fixable by re-scraping.
3. Disk usage note for next time: budget for the *loaded* DuckDB size
   (6.6 GB here) when estimating an XBRL stage, not the compressed
   download size (2.9 GB) - roughly 2.3x larger once indexed.

---

## 2026-08-26 — Pre-Phase-0 Repository Baseline

Independent inspection of the repository as it exists on disk, done before
any Phase 0 work starts. Everything below was verified against actual files,
`git` output, and one-off read-only checks (e.g. `torch.cuda.is_available()`)
run during this audit - not copied from planning documents.

### Status

**Data Preparation: COMPLETE**
**Engineering roadmap: READY TO START**
**Next: Phase 0 — Foundation**

### Repository Snapshot

```text
RAG/
├── .git/                       initialized, 0 commits, no remote, no .gitignore
├── .tmp/                       2.6 GB — orphaned DuckDB spill files, NOT project content
├── data/                       26.28 GB total (frozen, read-only from here on)
│   ├── edgar_corpus/*.parquet  5.77 GB raw source
│   ├── msmarco/*.parquet       1.66 GB raw source
│   ├── raw/xbrl/*.zip          3.45 GB raw source
│   ├── raw/primary/{cik}/*.htm 4.48 GB raw source (990 files)
│   ├── interim/audit_xbrl_meta/  3.90 GB derived (tag/pre/sub.txt, extracted for auditing)
│   ├── xbrl.duckdb             7.01 GB derived (facts + submissions)
│   └── validation_report.md    Phase 1 validation output
├── project_plan/
│   ├── README.md                reading-order index (3 of the 7 listed docs do not exist yet)
│   ├── PROJECT_SPEC.md          STALE — still cites pre-correction numbers, see warning below
│   └── PROJECT_EXECUTION.md     current — frozen numbers match DATA_READINESS_REPORT.md
├── prompts/                     4 task prompts (data_download, data_validation x2, this one)
├── src/
│   ├── __init__.py               empty
│   └── ingest/                   the only implemented module
│       ├── common.py             (139 lines) shared rate-limited HTTP + logging
│       ├── fetch_msmarco.py      (155 lines)
│       ├── fetch_edgar_corpus.py (138 lines)
│       ├── fetch_xbrl.py         (216 lines)
│       ├── fetch_primary_docs.py (176 lines)
│       ├── validate.py           (515 lines) Phase 1 validation, all 4 sources + cross-source
│       └── audit_data.py         (1,819 lines) full readiness audit + `--final-checks` mode
├── DATA_READINESS_REPORT.md      authoritative, frozen (root, not inside project_plan/)
├── Progress.md                   this file (root, not inside project_plan/)
├── phase1_data_audit.log
└── stage{1..5}_*.log             per-stage acquisition logs
```

Not present anywhere in the repository: `tests/`, `configs/`, `scripts/`,
`results/`, `infra/`, `logs/`, `artifacts/`, `.gitignore`, `requirements.txt`
/ `pyproject.toml` / `environment.yml`, `.env` / `.env.example`, root
`README.md`, `GIT_CONVENTIONS.md`, `REVIEW_RESOLUTIONS.md`, `FAILURES.md`.

### Completed Work

- **Data acquisition** (`src/ingest/fetch_*.py`) — IMPLEMENTED / VERIFIED.
  All four sources downloaded and reproducible via documented commands
  (Stage 1 section above).
- **Data validation** (`src/ingest/validate.py`) — IMPLEMENTED / VERIFIED.
  Runs and writes `data/validation_report.md`.
- **Independent readiness audit + final metric-definition review**
  (`src/ingest/audit_data.py`) — IMPLEMENTED / VERIFIED. Reproduces every
  Phase 1 number from source data rather than trusting prior logs, corrects
  two metric definitions (restatement rate methodology, EDGAR↔XBRL 10-K
  alignment), and writes/patches `DATA_READINESS_REPORT.md`. Two entry
  points: `python -m src.ingest.audit_data` (full audit, ~9 min) and
  `python -m src.ingest.audit_data --final-checks` (reuses cached XBRL
  metadata, ~3.5 min).
- **Frozen, authoritative data-readiness report** — VERIFIED. See below.

### Frozen Dataset State

Source of truth: `DATA_READINESS_REPORT.md`, section "Frozen Phase 1
Metrics". Historical numbers earlier in that report (and in
`PROJECT_SPEC.md` — see warning below) are superseded and must not be cited
as headline figures.

| Metric | Value |
|---|---:|
| MS MARCO passages | 8,841,823 |
| MS MARCO dev-small queries | 6,980 |
| EDGAR-CORPUS filings | 91,086 |
| EDGAR-CORPUS CIKs | 25,937 |
| EDGAR-CORPUS year range | 1993–2020 |
| XBRL facts | 90,685,753 |
| XBRL submissions (10-K+10-Q) | 218,166 |
| XBRL CIKs | 10,757 |
| XBRL distinct tags | 291,429 |
| Full-key duplicate rate | 32 / 90,685,753 = 0.000035% |
| Cross-filing value-revision rate — all tags | 1,044,801 / 13,276,577 = 7.87% |
| Cross-filing value-revision rate — standard non-abstract tags | 982,323 / 12,276,158 = 8.00% |
| Cross-filing value-revision rate — 15-tag registry | 199,117 / 1,916,013 = 10.39% |
| EDGAR ↔ XBRL 10-K coverage, 2016–2020, aligned on `fy` | 5,646 / 6,950 = 81.24% |
| — unmatched pairs, structural share | 1,249 / 1,304 = 95.8% |
| Primary filings | 990 |
| Primary docs table survival | 30/30 sampled (100%), mean 134.3 tables/doc |
| Primary docs inline-XBRL survival | 30/30 sampled (100%) |
| Raw source data size | ≈15.36 GB |
| Total `data/` directory size | 26.28 GB |

**`PHASE 1 COMPLETE — DATA FROZEN — PHASE 2 READY`**

### Important Findings From Data Preparation

The five original acquisition/validation bugs are recorded above (Stage 1
section, "Bugs found, root cause, and fix"). Three more were found during the
later independent audit and final metric-definition review — kept separate
here because they were caught by *re-deriving* numbers independently rather
than by the original pipeline failing loudly.

#### 1. The loose restatement rate (23.56%) was measuring the wrong population
**Problem:** the original XBRL "restatement rate" grouped facts by
`(cik, tag, ddate, qtrs)` after excluding only `coreg`. It counted
segment/dimensional facts (52.7% of all XBRL facts) as if they were
comparable to consolidated totals, ignored unit mismatches, and never
collapsed same-accession duplicate rows before comparing values.
**Why it mattered:** 23.56% looked like a "one in four facts gets restated"
result, which would materially complicate ground-truth generation.
**Resolution:** recomputed under a strict definition — `coreg` AND `segments`
both blank, same `uom`, cross-accession only, same-accession duplicates
collapsed first. Result: **7.87%** (all tags), rising to 10.39% on the core
15-tag registry. Renamed **cross-filing value-revision rate** — the data
cannot prove formal accounting "restatement" status. Full derivation in
`DATA_READINESS_REPORT.md`, "Check 1".

#### 2. EDGAR-CORPUS's `year` field semantics were assumed, then verified, then the verification language itself was softened
**Problem:** the `(cik, year)` join between EDGAR-CORPUS and XBRL needs a
correct XBRL year field to align against (`fy`, period year, or filed year) —
picking wrong, or picking whichever maximizes the join rate, would silently
bias eval-question generation.
**Why it mattered:** filing year and fiscal year diverge by exactly one year
for most December-FYE companies (10-K filed ~Feb/Mar of the following year),
so the three candidate fields give measurably different coverage.
**Resolution:** measured 2016–2020 coverage under all three fields — `fy`
94.24%, period year 95.04%, filed year 87.85%. `fy` and period year are
close enough that either is defensible; filed year is clearly worse. `fy`
was adopted as the *chosen semantic alignment field* — not because it
produced the largest number (it didn't; period year did), and the report is
explicit that this supports `fy` as appropriate without independently
proving EDGAR-CORPUS's original field-definition semantics.

#### 3. `ddate` contains a small number of physically impossible years
**Problem:** the audit's own critical-checks pass surfaced `ddate` values
ranging `1932-07-31` to `2923-12-31` — XBRL did not exist before ~2009, and
2923 cannot be a real filing period.
**Why it mattered:** an unfiltered `ddate` range check like this would look
"suspicious" without a size estimate, and could otherwise waste time chasing
a phantom pipeline bug.
**Resolution:** counted and spot-checked: 323 / 90,685,753 facts (0.00036%),
traced to filer typos in the *original SEC submission* (e.g. `2923` for
`2023`), not a bug in our code. Classified INFO, not a blocker. Any
period-based ground-truth code should still filter `ddate` to a sane range
defensively.

Also carried forward from the original validation, still true: EDGAR-CORPUS
has no structured tables (confirmed on a 20-sample check — one sample showed
flattened tab-separated numeric text, not real table markup); primary
documents retain both tables (100% of a 30-doc sample) and inline XBRL
(100%); `pre.txt` and `sic` exist in the raw SEC ZIPs but were never
persisted into `xbrl.duckdb` (the audit script loads them transiently for
its own checks, then discards them — Phase 0/2 work still needs to decide
whether to persist `sic` and `pre.txt` properly, per `PROJECT_SPEC.md`
Open Decision #3).

### Existing Code

`src/ingest/` is the only implemented module (3,158 lines total). Everything
in it is acquisition- and validation-focused; none of it is reusable RAG
pipeline code (no chunker, embedder, or retriever exists yet — this is
expected, since data acquisition was the only work scoped so far).

| File | Role | Status |
|---|---|---|
| `common.py` | Rate-limited SEC HTTP session, atomic downloads, logging setup | implemented / working |
| `fetch_msmarco.py` | MS MARCO corpus/queries/qrels via HF datasets-server | implemented / working |
| `fetch_edgar_corpus.py` | EDGAR-CORPUS parquet mirror download | implemented / working |
| `fetch_xbrl.py` | Quarterly XBRL ZIPs → `xbrl.duckdb` (`submissions`, `facts`) | implemented / working |
| `fetch_primary_docs.py` | 990 complete primary 10-K HTML filings | implemented / working |
| `validate.py` | Phase 1 validation across all 4 sources + cross-source checks | implemented / working |
| `audit_data.py` | Independent full audit + `--final-checks` metric-definition review | implemented / working |

No code exists yet (anywhere in the repo) for: normalization, chunking,
embedding, indexing, retrieval, generation, evaluation, routing, reranking,
CRAG, guardrails, API, or deployment. All PLANNED — not implemented.

### Existing Tests

None. `tests/` does not exist. No test files were found anywhere in the
repository. Test suite status: **not applicable — nothing to run yet.**
Phase 0.8 ("Basic automated tests") has not started.

### Environment / Dependency State

No `requirements.txt`, `pyproject.toml`, or `environment.yml` exists, and no
project-local virtual environment (`.venv`/`venv`) exists — Phase 0.1/0.4
have **not started**.

That said, the global Python 3.14.3 interpreter on this machine already has
several relevant packages installed (verified by direct import during this
audit, not assumed): `duckdb 1.5.4`, `pandas 2.3.3`, `pyarrow 23.0.1`,
`beautifulsoup4 4.14.3`, `lxml 6.1.1`, `requests 2.33.0`,
`huggingface_hub 1.8.0`, `torch 2.11.0+cu128`, `sentence_transformers 5.3.0`,
`fastapi 0.135.2`. `lancedb` is **not installed**.

**The single biggest open technical risk in `PROJECT_SPEC.md` — RTX 50-series
(Blackwell) CUDA compatibility — already looks resolved at the environment
level**, verified with a direct, read-only check during this audit:

```text
torch.cuda.is_available()      -> True
torch.cuda.get_device_name(0)  -> NVIDIA GeForce RTX 5060 Laptop GPU
torch.cuda.get_device_capability(0) -> (12, 0)   # sm_120, matches Blackwell
```

This is **not** the same as Phase 0.2 being complete: there is no documented
venv, no recorded dependency versions, no smoke-test script, and no VRAM
benchmark. Treat this as "the risk is very likely resolvable, ad hoc,
un-formalized" rather than "Phase 0.2 done."

### Git State

- Branch: `main`. **0 commits** — `git log` reports no commits yet.
- No remote configured (`git remote -v` empty).
- Working tree: everything is untracked (`git status` lists every top-level
  entry, including `data/` and `.tmp/`, as untracked — nothing has been
  staged or committed).
- `git count-objects`: empty pack, 0 bytes — consistent with zero commits.
- No tags.

**Git warnings:**

1. **No `.gitignore` exists.** With zero commits and no ignore rules, a
   careless `git add -A` right now would attempt to stage all of `data/`
   (26.28 GB, including the 7.01 GB `xbrl.duckdb`) plus the orphaned 2.6 GB
   `.tmp/` spill directory — roughly **29 GB** into a repo intended to be
   public on GitHub. This must be fixed before the first commit, not after.
2. **`.tmp/` (2.6 GB) is orphaned DuckDB spill, not project content.** It
   contains `duckdb_temp_storage_*.tmp` files left behind by an early audit
   run before `audit_data.py` was given an explicit `temp_directory`
   setting. It is disk waste, not a data artifact, and must never be
   committed. (Left in place — this task's file-modification limit is
   `Progress.md` only.)
3. **`.claude/`** (harness/IDE state, e.g. `scheduled_tasks.lock`) is also
   currently untracked and un-ignored; it is tooling state, not project
   content.
4. No secrets or `.env` files were found anywhere in the repository — no
   credential-leak risk from the current untracked state, only a size/noise
   risk.

### Documentation State

- `project_plan/README.md` defines a 7-document reading order
  (`PROJECT_SPEC.md` → `DATA_READINESS_REPORT.md` → `REVIEW_RESOLUTIONS.md`
  → `PROJECT_EXECUTION.md` → `GIT_CONVENTIONS.md` → `Progress.md` →
  `FAILURES.md`), but **`REVIEW_RESOLUTIONS.md`, `GIT_CONVENTIONS.md`, and
  `FAILURES.md` do not exist yet.** Not a Phase 0 blocker — documentation
  improvement, tracked here for visibility.
- `DATA_READINESS_REPORT.md` and `Progress.md` live at the repository root,
  not inside `project_plan/`, even though `project_plan/README.md`'s
  reading order doesn't specify a location. Worth deciding deliberately
  (move vs. cross-link) before the docs go public.
- **`PROJECT_SPEC.md` is stale relative to the frozen data-readiness
  report.** It still states the pre-correction numbers — 23.56% restatement
  rate, 81.71% `(cik,year)` join, 26.51% CIK overlap headline, "21 GB on
  disk" — none of which match the current frozen figures above (7.87%
  value-revision rate, 81.24% 10-K-only coverage, 26.28 GB / 15.36 GB raw).
  **`PROJECT_EXECUTION.md`, by contrast, already carries the corrected
  numbers** ("Frozen facts relevant to execution" section matches
  `DATA_READINESS_REPORT.md` exactly). `PROJECT_EXECUTION.md` was used as
  the authoritative roadmap for this snapshot per its own precedence over
  `PROJECT_SPEC.md`, but `PROJECT_SPEC.md`'s data-inventory numbers should
  be reconciled before it's read by anyone else.

### Implemented vs Planned

#### Implemented
- Data acquisition (`fetch_msmarco.py`, `fetch_edgar_corpus.py`,
  `fetch_xbrl.py`, `fetch_primary_docs.py`)
- Data validation (`validate.py`)
- Independent data-readiness audit + final metric-definition review
  (`audit_data.py`)
- Frozen, corrected `DATA_READINESS_REPORT.md`

#### Planned / Not Started
- `src/storage.py`, `src/config.py` — storage/config abstraction
- Normalizer (OKF Markdown layer)
- Chunker (fixed-window baseline, later section-aware)
- Embedding pipeline
- LanceDB vector index, BM25/FTS index
- Retrieval (hybrid, metadata pre-filtering)
- Reranking, CRAG confidence grading
- Rules-first router, later LLM router
- Guardrails (input/context/output)
- Truth contract (`src/eval/truth_contract.py`), frozen tag registry,
  ~3,000-question eval set, DEV/TEST split
- FastAPI service, deployment
- `tests/`, `configs/`, `scripts/`, `infra/`, `artifacts/`, `logs/`
  directories
- `.gitignore`, `requirements.txt`, `.env.example`, root `README.md`,
  `GIT_CONVENTIONS.md`, `REVIEW_RESOLUTIONS.md`, `FAILURES.md`

### Known Risks Going Into Engineering

Only risks actually supported by `PROJECT_SPEC.md` / `PROJECT_EXECUTION.md`
or this audit's own findings.

| Risk | Status | Note |
|---|---|---|
| RTX 50-series (Blackwell) CUDA compatibility | Likely RESOLVED, not yet formalized | `torch.cuda.is_available()` True, `sm_120` detected globally; no documented venv/smoke test yet (see Environment section) |
| Serverless LanceDB/S3 latency | OPEN | Phase 0.10 serving-feasibility spike not yet run; every latency figure in `PROJECT_SPEC.md` is an estimate |
| Full-corpus vector index size (~14M chunks) | OPEN | Estimated 1.8 GB (binary quantized) to 57 GB (fp32); ablation planned for Phase 3, not measured |
| XBRL serving format for production | DEFERRED | Phase 4.5; `xbrl.duckdb` fine for offline analysis, not yet exported to a serving-appropriate partitioned format |
| EDGAR-CORPUS has no tables | RESOLVED (understood, not fixable) | Confirmed structurally absent; table retrieval can only be evaluated on the 990 primary docs |
| Primary-doc parsing / inline-XBRL evidence alignment | OPEN | Flagged in `PROJECT_EXECUTION.md` as the single hardest task in the whole plan (12–18 hrs, step 2.8); not started |
| Evaluation truth-contract correctness | PARTIALLY OPEN | The value-revision-rate correction (this audit's Check 1) is a preview of the rigor the full truth contract (`src/eval/truth_contract.py`, Phase 2.1) still needs to formalize; that module does not exist yet |
| `pre.txt` / `sic` not persisted for reuse | OPEN | Both exist in raw ZIPs and were loaded transiently by `audit_data.py` for its own checks, but neither is in `xbrl.duckdb`; decision needed before Phase 5.4/5.5 |
| Exhibit 21 not downloaded | DEFERRED (Phase 5.3, stretch) | Best-quality subsidiary graph source is simply missing |
| Repo hygiene: no `.gitignore`, 2.6 GB orphaned `.tmp/` | OPEN | See Git warnings above; must be resolved before the first commit |

### Phase Status

| Stage | Status | Evidence |
|---|---|---|
| Data Preparation | COMPLETE | acquisition scripts + `validate.py` + `audit_data.py` + frozen `DATA_READINESS_REPORT.md` |
| Phase 0 — Foundation | NOT STARTED | no venv, no `requirements.txt`, no `src/config.py`/`src/storage.py`, no `tests/`, no serving spike; GPU/CUDA looks favorable but unformalized (see Environment section) |
| Phase 1 — Make It Work | NOT STARTED | no normalizer, chunker, embedder, index, retriever, or generation code anywhere in `src/` |
| Phase 2 — Make It Trustworthy | NOT STARTED | no `src/eval/truth_contract.py`, no eval set, no DEV/TEST split |
| Phase 3 — Make It Good | NOT STARTED | no BM25, reranker, CRAG, or router code |
| Phase 4 — Make It Real | NOT STARTED | no guardrails, no FastAPI, no deployment |
| Phase 5 — Stretch | STRETCH | not applicable pre-Phase-4 |

### Next Step

**Phase 0 — Build the System Foundation**, per `PROJECT_EXECUTION.md`.

First incomplete subtask: **0.1 Python environment** — select/document the
project Python version, create the project virtual environment, verify
activation, record the setup command. (Note: a compatible interpreter and
most Phase-0-relevant packages, including a CUDA-capable PyTorch build,
already exist globally on this machine per the Environment section above —
Phase 0.1/0.4 still need to turn that into a documented, reproducible,
project-local environment rather than relying on whatever happens to be
globally installed.)

Immediately after or alongside 0.1: **create `.gitignore` before the first
commit** — not itself a numbered `PROJECT_EXECUTION.md` subtask, but a
precondition for subtask 0.3 ("ensure generated artifacts are ignored
appropriately by Git") and for avoiding an accidental 29 GB first commit.

### Baseline Declaration

This entry records the repository state immediately before Phase 0
implementation begins. `NEXT: Phase 0 — Foundation`. No Phase 0
implementation has started. The repository baseline is now documented.

---

## 2026-08-26 — Phase 0.0 Git Safety Preflight

### Objective

The repository had 0 commits, no `.gitignore`, and every file untracked —
including `data/` (26.28 GB) and an orphaned `.tmp/` (2.6 GB). A careless
`git add .` at this point would have attempted to stage roughly 29 GB into a
repo intended to be public. This task makes the repository safe for its
first commit; it does not create that commit.

### Initial State

```text
commits:          0
.gitignore:       did not exist
GIT_CONVENTIONS.md: does not exist anywhere in the repo (already flagged in
                     the pre-Phase-0 baseline entry above; still unresolved -
                     this task proceeded using the Git conventions listed
                     inline in its own prompt as a fallback)
data/:             25 GiB (26.28 GB per DATA_READINESS_REPORT.md's byte-exact count)
.tmp/:             2.6 GB - orphaned DuckDB temp-spill files
tracked files:     0 (git status --short showed all 14 top-level entries as
                     untracked: .claude/, .tmp/, DATA_READINESS_REPORT.md,
                     Progress.md, data/, 5 stage log files,
                     phase1_data_audit.log, project_plan/, prompts/, src/)
secrets found:     none (.env/.env.local/credentials*/secrets*/*.pem/*.key -
                     all searched, none present). SEC_USER_AGENT appears
                     only as an env-var name and a placeholder example in
                     code/docs, and as the user's real contact string in this
                     file's Stage 3 command - not a secret: SEC requires a
                     public contact identifier in the User-Agent header, it
                     is not an authentication credential.
```

### Changes Made

Created root `.gitignore` covering:

- **Data**: `data/*` ignored, `!data/.gitkeep` exception so the directory's
  existence (and where data belongs) is still communicated in Git without
  committing its contents.
- **Temp files**: `.tmp/`, `tmp/`, `temp/`.
- **Generated artifacts**: `artifacts/`, `logs/`, `*.duckdb`,
  `*.duckdb.wal`, `*.parquet`, `*.zip`, `*.idx`, `*.part`, `*.lance/`.
- **Models/caches**: `models/`, `.cache/`, `**/.huggingface/`, `*.onnx`,
  `*.safetensors`, `*.bin`.
- **Secrets**: `.env`, `.env.local`, `.env.*` (with `!.env.example`
  exception for when Phase 0.5 creates it), `*.pem`, `*.key`,
  `credentials*`, `secrets*`.
- **Python**: `__pycache__/`, `*.py[cod]`, `.venv/`, `venv/`, `env/`,
  `*.egg-info/`, `.pytest_cache/`, `.ipynb_checkpoints/`.
- **IDE/OS**: `.DS_Store`, `.idea/`, `.vscode/`, `*.swp`.
- **Local tooling state**: `.claude/`.
- **Results**: `results/*` ignored but `!results/*.csv` / `.json` / `.md`
  kept trackable, per the "don't ignore the whole directory" instruction -
  `results/` doesn't exist yet, this is forward-looking for when it does.

Created `data/.gitkeep` (empty placeholder file).

### Verification

```text
git check-ignore -v data/xbrl.duckdb                    -> matched *.duckdb (ignored)
git check-ignore -v data/raw/xbrl/2016q1.zip             -> matched data/* (ignored)
git check-ignore -v data/edgar_corpus/train.parquet      -> matched data/* (ignored)
git check-ignore -v .tmp/duckdb_temp_storage_DEFAULT-0.tmp -> matched .tmp/ (ignored)
git check-ignore -v .claude/scheduled_tasks.lock         -> matched .claude/ (ignored)
git check-ignore -v data/interim/audit_xbrl_meta/2016q1/tag.txt -> matched data/* (ignored)
git check-ignore -v data/.gitkeep                        -> NOT ignored (the !data/.gitkeep exception works)
git check-ignore -v Progress.md / DATA_READINESS_REPORT.md / project_plan/PROJECT_SPEC.md
                    / src/ingest/common.py / prompts/data_download.md / .gitignore -> none ignored (all trackable)
```

`git add -n .` dry run: **27 files staged, 0 data/temp/secret files among
them.** Full list: `.gitignore`, `data/.gitkeep`, both `__init__.py` files,
7 `src/ingest/*.py` modules, `DATA_READINESS_REPORT.md`, `Progress.md`,
`project_plan/{README,PROJECT_SPEC,PROJECT_EXECUTION}.md`, all 4 `prompts/`
files (including the nested `phase_0_Foundation/` one), and the 6 root
`.log` files (5 stage logs + `phase1_data_audit.log` - left trackable since
the `.gitignore` template ignores a `logs/` *directory*, not loose root
`*.log` files, and these are small human-readable engineering artifacts
consistent with "commit small eval result files/configs").

Total size of everything that would be staged: **~0.40 MB**. Largest single
file: `src/ingest/audit_data.py` at 96.6 KB - nowhere near the 10 MB warning
threshold; every other file is under 42 KB.

`git count-objects -vH`: `count: 0, size: 0 bytes` - unchanged, since
nothing was staged or committed (as instructed).

### Safety Result

```text
PASS — repository is safe for the first commit
```

### Files Modified

- `.gitignore` (new)
- `data/.gitkeep` (new)
- `Progress.md` (this entry)

### Remaining Git Notes

- First commit not yet created - that's the next task, not this one.
- No remote configured yet.
- `.tmp/` (2.6 GB) still consumes disk - safely ignored, not deleted. Disk
  cleanup was out of scope for this task (Git safety, not housekeeping);
  it's already recorded as an open item in the pre-Phase-0 baseline entry
  above and remains open.
- `GIT_CONVENTIONS.md` still does not exist anywhere in the repo. This task
  used the Git principles listed inline in its own prompt (commit per
  subtask, push at end of session, tag phase exits, never commit data or
  secrets, keep `Progress.md` history, commit small eval result files) as a
  stand-in. Creating the actual file remains open.

### Phase Status

```text
Data Preparation           — COMPLETE
Phase 0                    — IN PROGRESS
  0.0 Git Safety Preflight — COMPLETE
  0.1 Python environment   — NEXT
```

---

## 2026-08-26 — Phase 0.1 Python Environment

### Objective

Move from the ad hoc global Python interpreter (whatever happened to be
installed on this machine) to a reproducible, project-local `.venv`. A
globally working `torch`/`duckdb`/`fastapi`/etc. installation does not make
the repository reproducible for anyone else who clones it.

Also carried a small Git-safety correction forward from Task 0.0: a real
personal contact string (`SEC_USER_AGENT="<name> <email>"`) was still
present in this file's Stage 3 command from the original data-acquisition
entry. Replaced with the neutral placeholder
`SEC_USER_AGENT="Your Name your.email@example.com"` per `GIT_CONVENTIONS.md`
("Never commit ... `SEC_USER_AGENT` with a real address"). No other text in
that historical entry was changed.

### Initial State

```text
project-local venv: did not exist
global Python:       3.14.3  (C:\Python314\python.exe)
py launcher list:    3.14 (default), 3.11 - 3.12 not installed
selected version:    3.11.9 (already installed, no install step needed)
why global was insufficient: nothing pins versions, nothing isolates
  project packages from whatever else is installed system-wide - not
  reproducible for a second developer or a fresh clone
```

### Python Version Decision

```text
selected:            Python 3.11.9
other versions considered: 3.14.3 (global default - rejected), 3.12 (preferred
  per policy, but not installed on this machine and not installed for this
  task, since 3.11 - the documented fallback - was already available)
reason: PROJECT_EXECUTION.md Task 0.1 prefers 3.12.x, falling back to 3.11.x.
  3.12 was not present via the `py` launcher; 3.11.9 was, so no interpreter
  installation was necessary. The newest global interpreter (3.14) was
  deliberately not used - it maximizes wheel-availability risk for a stack
  this dependent on prebuilt binaries (PyTorch, sentence-transformers,
  LanceDB, ONNX Runtime, Docling).
```

### Environment Created

```text
location:    .venv/  (repository root)
creation:    py -3.11 -m venv .venv
activation:  .\.venv\Scripts\Activate.ps1   (Windows PowerShell)
```

### Verification

```text
python --version                 -> Python 3.11.9
sys.executable                   -> .venv\Scripts\python.exe (inside .venv)
sys.prefix                       -> .venv (inside .venv)
pip                               -> .venv\Lib\site-packages\pip (inside .venv)
pyvenv.cfg                       -> include-system-site-packages = false
isolation (direct test)          -> `import duckdb` (installed globally,
                                     not installed in .venv) raised
                                     ModuleNotFoundError inside the activated
                                     venv - confirms real isolation, not just
                                     the config flag
fresh-process reactivation       -> verified in a new shell process:
                                     activation, version, and executable path
                                     all reproduced without relying on any
                                     state from the creation command
bootstrap tooling                -> pip/setuptools/wheel upgraded to latest
                                     inside .venv (pip 24.0 -> 26.2.1); `pip
                                     list` shows exactly 4 packages
                                     (pip, setuptools, wheel, packaging) -
                                     no project dependencies installed
```

Full setup/verification commands are documented in
`project_plan/ENVIRONMENT.md` (new).

### Files Created / Modified

```text
.python-version              (new - "3.11")
project_plan/ENVIRONMENT.md  (new - setup/activation/verification commands)
Progress.md                  (this entry, plus the SEC_USER_AGENT sanitization above)
```

`.venv/` created locally and ignored by Git - not a tracked repository file,
internals not enumerated here.

Also observed (not created by this task): `project_plan/GIT_CONVENTIONS.md`
now exists, resolving a documentation gap flagged in both the pre-Phase-0
baseline and the Task 0.0 entry above. Its stated `.gitignore` contents and
commit conventions are consistent with what Task 0.0 already put in place
using the inline fallback principles from its own prompt - no correction
needed as a result.

### Phase Result

```text
PASS — reproducible project-local Python environment established
```

### Phase Status

```text
Data Preparation             — COMPLETE
Phase 0                      — IN PROGRESS
  0.0 Git Safety Preflight   — COMPLETE
  0.1 Python Environment     — COMPLETE
  0.2 CUDA/GPU Validation    — NEXT
```

---

## 2026-08-26 — Phase 0.2 CUDA / GPU Validation

### Objective

Formalize GPU support inside the project-local `.venv`, replacing the
earlier ad hoc observation from the global environment. `torch.cuda.is_available() == True`
in the global interpreter was encouraging but did not prove anything about
`.venv`, which had no PyTorch installed at all until this task.

### Initial State

```text
Python:            3.11.9 (.venv, from Task 0.1)
.venv:              working, isolated (verified in Task 0.1)
PyTorch in .venv:   absent before this task
prior GPU signal:   global-environment observation only (torch 2.11.0+cu128,
                     RTX 5060, sm_120) - not yet proven inside .venv
```

### NVIDIA Environment

```text
GPU model:                  NVIDIA GeForce RTX 5060 Laptop GPU
VRAM:                       8.55 GB (torch-reported) / 8151 MiB (nvidia-smi)
NVIDIA driver:               610.74 (WDDM)
driver-supported CUDA:       13.3 (nvidia-smi "CUDA UMD Version" - this
                              nvidia-smi build reports it under that label
                              rather than the older "CUDA Version:" field;
                              same concept - the driver's max supported CUDA,
                              not the runtime PyTorch actually uses)
```

### PyTorch Decision

```text
selected:          torch 2.13.0+cu130
install source:     official index, https://download.pytorch.org/whl/cu130
reason: queried `pip index versions torch` against the official cu128/cu129/
  cu130 indices rather than copying the global environment's cu128 build.
  cu128's newest was 2.11.0+cu128 (a generation behind); cu129's newest was
  a stale 2.9.0+cu129; cu130's newest was 2.13.0+cu130 - the current,
  actively-maintained channel, closest to this driver's reported CUDA 13.3.
  sm_120 appears directly in torch.cuda.get_arch_list() under cu130
  (compiled kernels), which is stronger evidence than cu128 alone provided.
  torchvision/torchaudio were not installed - not needed for embeddings-only
  work.
```

`nvidia-smi`'s driver-supported CUDA (13.3) and `torch.version.cuda` (13.0,
the runtime bundled with the installed wheel) were recorded separately and
are not the same number, as required - conflating them would misrepresent
what's actually running. The full CUDA Toolkit (`nvcc`) was not installed;
the standard PyTorch wheel bundles what ordinary execution needs, and
nothing in this project compiles custom CUDA extensions.

### CUDA Verification

```text
torch.cuda.is_available():        True
device_count:                     1
device_name(0):                   NVIDIA GeForce RTX 5060 Laptop GPU
device_capability(0):             (12, 0)  -- sm_120, matches Blackwell
torch.cuda.get_arch_list():       includes sm_120 (compiled, not PTX-only)
cuDNN version:                    92000 (9.2.0)
real CUDA tensor kernel (2048x2048 matmul on cuda:0): PASS - finite result,
  transferred back to CPU successfully
CPU/GPU numerical sanity check (512x512 matmul, seed=42,
  torch.allclose(atol=1e-3, rtol=1e-3)): PASS - max abs diff ~4.6e-5
FP16 (alloc + 1024x1024 matmul + finite check): PASS
BF16 (alloc + 1024x1024 matmul + finite check): PASS
compatibility warnings observed: none (no "no kernel image available" /
  "not compatible" messages from PyTorch)
GPU memory baseline (tiny smoke test, not a capacity estimate): a single
  2048x2048 matmul allocated/reserved ~83.9 MB
```

### Embedding Verification

```text
model:            BAAI/bge-small-en-v1.5 (sentence-transformers)
device requested: "cuda" (explicit - no silent CPU fallback allowed)
device confirmed: cuda:0 (model parameters directly inspected)
embedding dim:     384 (verified via get_sentence_embedding_dimension(),
                    not assumed)
texts encoded:      40 short SEC-style sentences (revenue, Item 1A risk
                    factors, net income, dividend, R&D expense - repeated/
                    truncated to 40)
batch size:         16
elapsed:            0.061 s (one untimed warm-up batch excluded)
smoke throughput:   ~652 texts/sec  -- GPU smoke benchmark, NOT a production
                    benchmark; not to be cited as a system-performance number
peak GPU memory allocated during timed encode: 171.78 MB
```

No-CPU-fallback evidence (three independent signals, per instructions - not
timing alone): embeddings tensor reported `device=cuda:0`; peak GPU memory
allocated rose to ~171.8 MB during encoding; computation completed via real
CUDA tensors with no CPU-path exceptions. **sentence-transformers GPU
execution: VERIFIED.**

Model cache: `HF_HOME`/`HUGGINGFACE_HUB_CACHE`/`TRANSFORMERS_CACHE` were all
unset, so Hugging Face used its default user-level cache outside the repo -
not trackable by Git, not committed. (A harmless Windows-only warning about
symlink support being degraded without Developer Mode appeared; informational
only, does not affect correctness.)

### Files Created / Modified

```text
project_plan/ENVIRONMENT.md   (added "GPU / CUDA" section)
Progress.md                   (this entry)
```

`.venv/` gained `torch`, `sentence-transformers`, and their transitive
dependencies - not enumerated here (see `project_plan/ENVIRONMENT.md` for
the short list of directly-installed packages with exact versions). Not a
tracked repository file; internals not listed.

### Packages Added Locally

```text
torch==2.13.0+cu130
sentence-transformers==6.0.0
transformers==5.16.1
huggingface-hub==1.28.0
tokenizers==0.23.1
numpy==2.4.6
safetensors==0.8.0
```

(plus each package's own transitive dependencies, installed normally via
pip - full `pip list` not pasted here per instructions)

### Result

```text
PASS — CUDA and GPU embedding inference validated inside project .venv
```

### Phase Status

```text
Data Preparation              — COMPLETE
Phase 0                       — IN PROGRESS
  0.0 Git Safety Preflight    — COMPLETE
  0.1 Python Environment      — COMPLETE
  0.2 CUDA/GPU Validation     — COMPLETE
  0.3 Repository Structure    — NEXT
```

---

## 2026-08-26 — Phase 0.3 Repository Structure

### Objective

Establish the final high-level repository skeleton before implementation
spreads across the project — directories and package boundaries, not RAG
functionality. A directory existing does not mean a feature is implemented;
every new `src/` package below is intentionally empty except `__init__.py`.

### Initial State

```text
src/               contained only ingest/ (7 modules) + root __init__.py
src/normalize, chunk, embeddings, index, retrieval, generation, eval,
  router, rerank, crag, guards, api, cli:  absent (none pre-existed)
configs/, tests/, scripts/, results/, infra/:  absent
```

### Structure Created

```text
SEC-RAG/
├── src/
│   ├── ingest/          (unchanged - 7 modules, all preserved exactly)
│   ├── normalize/  chunk/  embeddings/  index/  retrieval/  generation/
│   ├── eval/  router/  rerank/  crag/  guards/  api/  cli/
│   │   (13 new packages, each containing only an empty __init__.py)
├── configs/.gitkeep  tests/.gitkeep  scripts/.gitkeep  infra/.gitkeep
├── results/.gitkeep  (results/*.csv|.json|.md stay trackable per existing rule)
├── project_plan/  (unchanged, + new REPOSITORY_STRUCTURE.md)
├── prompts/  data/  (both unchanged)
├── Progress.md  .python-version  .gitignore
```

Full tree with all files: see `project_plan/REPOSITORY_STRUCTURE.md`.

### Package Responsibilities

`src/ingest/` remains the only implemented package. The 13 new packages
(`normalize`, `chunk`, `embeddings`, `index`, `retrieval`, `generation`,
`eval`, `router`, `rerank`, `crag`, `guards`, `api`, `cli`) are
**STRUCTURE ONLY — functionality not implemented.** Each maps to a specific
later phase/subtask in `PROJECT_EXECUTION.md` (e.g. `chunk/` -> Phase 1.3
baseline, later Phase 3.2 ablation; `eval/` -> Phase 2.1's truth contract).
Full mapping table in `project_plan/REPOSITORY_STRUCTURE.md`.

`src/config.py` and `src/storage.py` were deliberately **not** stubbed out -
they belong to Tasks 0.5/0.7, and an empty placeholder file now would risk
later looking like a completed feature.

### Top-Level Directories

```text
configs/   versioned experiment/system configuration - empty for now
tests/     unit/integration/smoke tests - Task 0.8 owns implementation,
           placeholder only
scripts/   developer/build/maintenance commands - empty for now
results/   small public metrics/summaries (.csv/.json/.md) - directory
           tracked via results/.gitkeep, contents ignored except those
           3 extensions
infra/     deployment/infrastructure definitions - empty for now
artifacts/, logs/  runtime-generated, git-ignored; intentionally NOT created
           as empty directories - they appear only when something writes
           to them, so the repo tree isn't padded with directories that
           imply activity that hasn't happened
```

### Documentation Added

`project_plan/REPOSITORY_STRUCTURE.md` (new) - explains every top-level
directory's purpose, maps each `src/` package to the phase/subtask that will
implement it, and explicitly separates tracked source-of-truth content from
local/generated/git-ignored content, for the benefit of anyone cloning the
public repository.

### Verification

```text
new package imports (13/13):  PASS - src.normalize, chunk, embeddings,
  index, retrieval, generation, eval, router, rerank, crag, guards, api,
  cli all import cleanly with `python -c "import src.<pkg>"`
existing src/ingest preserved: YES - all 7 modules present, unmodified;
  `import src.ingest.<module>` for all 7 resolves the package path
  correctly and fails only on `ModuleNotFoundError: No module named
  'requests'` / `'duckdb'` - i.e. a missing-dependency condition expected
  because Task 0.4 (dependency management) has not run yet, not a
  package-structure problem. Distinguished explicitly per instructions
  rather than reported as a false failure.
Git dry-run safety:            PASS - `git add -n .` lists 51 files (all
  __init__.py / .gitkeep / existing tracked docs and code); zero data/,
  .venv/, .tmp/, or model-cache paths appear
```

Small `.gitignore` correction made: added `!results/.gitkeep` so the new
placeholder is trackable without weakening the existing protection on other
`results/` content (still ignored except `.csv`/`.json`/`.md`).

### Files Created / Modified

```text
src/{normalize,chunk,embeddings,index,retrieval,generation,eval,router,
  rerank,crag,guards,api,cli}/__init__.py   (13 new files, 0 bytes each)
configs/.gitkeep  tests/.gitkeep  scripts/.gitkeep  infra/.gitkeep
  results/.gitkeep   (5 new placeholders, 0 bytes each)
project_plan/REPOSITORY_STRUCTURE.md          (new)
.gitignore                                    (added !results/.gitkeep)
Progress.md                                   (this entry)
```

### Result

```text
PASS — repository structure established
```

### Phase Status

```text
Data Preparation               — COMPLETE
Phase 0                        — IN PROGRESS
  0.0 Git Safety Preflight     — COMPLETE
  0.1 Python Environment       — COMPLETE
  0.2 CUDA/GPU Validation      — COMPLETE
  0.3 Repository Structure     — COMPLETE
  0.4 Dependency Management    — NEXT
```

---

## 2026-08-26 — Phase 0.4 Dependency Management

### Objective

Convert the working-but-ad-hoc `.venv` (only the Task 0.2 GPU/embedding
stack installed) into a documented, reproducible dependency specification —
intentional direct-dependency pins rather than a raw `pip freeze` dump —
suitable for a fresh clone, not just this machine.

### Initial State

```text
Python 3.11.9, .venv working
torch 2.13.0+cu130, sentence-transformers 6.0.0: already validated (Task 0.2)
requirements files: none existed
src.ingest.* imports: failing on missing requests/duckdb (Task 0.3 finding)
beautifulsoup4/lxml: not installed (used by validate.py/audit_data.py)
LanceDB, FastAPI, pytest: not installed
```

### Dependency Strategy

Three-file split, exactly as specified:

```text
requirements-gpu.txt    torch==2.13.0+cu130 only, from the official cu130
                         index - installed FIRST so sentence-transformers'/
                         transformers' generic torch>=2.2 requirement can't
                         silently pull in a default (often CPU-only) build
requirements.txt        direct runtime dependencies
requirements-dev.txt    pytest only
```

Source-imports inventory drove most of `requirements.txt`: grepped
`src/ingest/*.py` for actual `import`/`from` statements rather than
inferring from planning documents. Found direct imports of `requests`,
`duckdb`, `huggingface_hub`, and (inside `validate.py`/`audit_data.py`)
`bs4`/lxml-backed parsing. `pyarrow` (Parquet), `lancedb` (vector index),
`fastapi`+`uvicorn` (serving), and `python-dotenv` (Task 0.5) were added on
top because `PROJECT_EXECUTION.md`'s own Task 0.4 subtask explicitly names
them as minimum Phase 0/1 requirements, not because current code imports
them yet. No pandas - not imported anywhere in current code and not on that
explicit minimum list.

### Direct Dependencies

| Group | Package | Version | Why |
|---|---|---:|---|
| GPU | torch | 2.13.0+cu130 | validated Task 0.2, RTX 5060/cu130 |
| Runtime | requests | 2.34.2 | `src/ingest/common.py` HTTP session |
| Runtime | huggingface_hub | 1.28.0 | `fetch_msmarco.py` direct import |
| Runtime | duckdb | 1.5.5 | XBRL DB, validation, audit |
| Runtime | pyarrow | 25.0.1 | Parquet chunk output (Phase 1.3), LanceDB dep |
| Runtime | beautifulsoup4 | 4.15.0 | table/inline-XBRL checks |
| Runtime | lxml | 6.1.2 | bs4 parser backend |
| Runtime | sentence-transformers | 6.0.0 | embedding pipeline (Phase 1.4) |
| Runtime | lancedb | 0.37.1 | vector index (Phase 1.5) |
| Runtime | fastapi | 0.141.1 | API serving (Phase 4.10) |
| Runtime | uvicorn | 0.52.4 | ASGI server for fastapi |
| Runtime | python-dotenv | 1.2.3 | `.env` loading, Task 0.5 (package only) |
| Dev | pytest | 9.1.1 | test suite, Task 0.8 (package only) |

All pinned to the exact version that actually resolved and installed inside
`.venv` (Python 3.11.9) - not copied from the machine's earlier global-env
observations, and not a `pip freeze` dump (transitive packages like numpy,
transformers, pydantic, scipy, scikit-learn are left to pip's resolver,
unpinned).

### Installation Order

```text
1. python -m pip install -r requirements-gpu.txt
2. python -m pip install -r requirements.txt
3. python -m pip install -r requirements-dev.txt
```

Verified this order does not disturb torch: after step 2, `sentence-
transformers->torch>=2.2` reported "already satisfied (2.13.0+cu130)" -
no replacement occurred.

### Verification

```text
pip check (after runtime deps):        PASS - "No broken requirements found"
pip check (after dev deps):            PASS
ingestion imports (7/7 src.ingest.*):  PASS - all resolve cleanly now
core Phase 0 imports (torch,
  sentence_transformers, duckdb,
  pyarrow, requests, lancedb,
  fastapi, pytest, bs4):               PASS - all 9 import cleanly
CUDA regression (post-install):        PASS - torch 2.13.0+cu130 unchanged,
  torch.version.cuda 13.0 unchanged, CUDA available, 512x512 matmul finite
bge-small CUDA regression:             PASS - device=cuda:0, encoded
  successfully (no throughput re-benchmark, per instructions)
LanceDB tiny smoke test:               PASS - created/read a 3-row table
  under .tmp/lancedb_smoke_test/, then deleted it
DuckDB read-only open of
  data/xbrl.duckdb:                    PASS - tables ['facts','submissions'],
  facts row count 90,685,753 (exact match to the frozen Phase 1 number,
  confirming duckdb 1.5.5 reads the existing 7GB database correctly)
```

### Fresh Environment Reproduction

```text
PASS
```

Built `.tmp/dependency_check_venv/` from scratch (`py -3.11 -m venv`),
reproduced the documented 3-step install sequence using pip's normal HTTP
cache (12.4 GB already cached from this task's earlier installs - no
unnecessary multi-GB re-download; GPU install completed in ~67s, runtime in
~45s, dev in ~3s). Inside that fresh environment: `pip check` passed,
`torch.__version__`/`torch.version.cuda` matched exactly (2.13.0+cu130 /
13.0), `torch.cuda.is_available()` was `True`, a real CUDA tensor op
succeeded, and `duckdb`/`pyarrow`/`lancedb`/`fastapi`/`pytest`/
`sentence_transformers` all imported. This proves the requirements files
themselves can reconstruct the working environment, not merely describe the
already-mutated `.venv`. Temp environment removed cleanly afterward (no
Windows file-lock issue).

### Files Created / Modified

```text
requirements-gpu.txt              (new)
requirements.txt                  (new)
requirements-dev.txt              (new)
project_plan/DEPENDENCIES.md      (new)
project_plan/ENVIRONMENT.md       (updated: "Notes" section pointed at
  DEPENDENCIES.md instead of saying deps are "not yet installed")
Progress.md                       (this entry)
```

### Result

```text
PASS — dependency environment is reproducible from declared requirements
```

### Phase Status

```text
Data Preparation                 — COMPLETE
Phase 0                          — IN PROGRESS
  0.0 Git Safety Preflight       — COMPLETE
  0.1 Python Environment         — COMPLETE
  0.2 CUDA/GPU Validation        — COMPLETE
  0.3 Repository Structure       — COMPLETE
  0.4 Dependency Management      — COMPLETE
  0.5 Configuration System       — NEXT
```

---

## 2026-08-26 — Phase 0.5 Configuration System

### Objective

Establish one typed, environment-aware configuration boundary
(`src/config.py`) so future modules (`normalize/`, `chunk/`, `embeddings/`,
`retrieval/`, ...) consume settings instead of each scattering its own
hardcoded paths, model names, or `os.environ` reads.

### Initial State

```text
src/config.py:   absent
.env, .env.example: absent
python-dotenv:   already installed (Task 0.4)
existing env-var reads: src/ingest/common.py reads STORAGE_ROOT and
  SEC_USER_AGENT directly via os.getenv(), with a repo-relative default
  ("./data") - not machine-specific, not touched by this task
```

### Configuration Design

```text
API:            get_settings() -> Settings (cached via functools.lru_cache);
                 load_settings() for an uncached one-off read;
                 get_settings.cache_clear() to reset the cache (verified)
object:          frozen dataclass, 9 fields, no API-key fields at all
precedence:      process env > .env > code default, via python-dotenv's
                 load_dotenv(..., override=False) - its default behavior
                 already implements this, no extra logic needed
paths:           repo_root derived from Path(__file__).resolve().parent.parent
                 (portable, never hardcoded); storage_root defaults to
                 <repo_root>/data, overridable via STORAGE_ROOT, resolved to
                 an absolute path but never created on load
validation:      ConfigError (ValueError subclass) raised immediately for
                 invalid APP_ENV/LOG_LEVEL/DEVICE, naming the variable, the
                 bad value, and the allowed set
secret strategy: no API-key field on Settings at all - GENERATION_PROVIDER/
                 GENERATION_MODEL name which provider/model, but the actual
                 credential (e.g. OPENAI_API_KEY) will be read directly from
                 the environment by whatever provider-client module
                 implements that integration later. Chosen specifically so
                 Settings can never leak a credential via repr()/logging,
                 because it never holds one - "the simpler secure option"
                 per the task's own Step 19 guidance.
```

### Settings

| Variable | Default | Required | Purpose |
|---|---|---|---|
| APP_ENV | development | No | development / test / production |
| STORAGE_ROOT | `<repo>/data` | No | local storage root, repo-relative default |
| EMBEDDING_MODEL | BAAI/bge-small-en-v1.5 | No | Phase 1 baseline |
| DEVICE | auto | No | auto / cuda / cpu - resolved lazily via `resolve_device()`, not at config-load time |
| GENERATION_PROVIDER | (none) | No | optional until Phase 1 generation exists |
| GENERATION_MODEL | (none) | No | optional until Phase 1 generation exists |
| LOG_LEVEL | INFO | No | DEBUG/INFO/WARNING/ERROR/CRITICAL |
| SEC_USER_AGENT | (none) | only for SEC network access | not a secret - SEC's required public contact header - but no real value belongs in a tracked file |

Full table with rationale: `project_plan/CONFIGURATION.md`.

### Path Behavior

```text
repository-root detection: Path(__file__).resolve().parent.parent inside
  src/config.py - portable, no hardcoded absolute path anywhere
default STORAGE_ROOT:      <repo_root>/data
override behavior:         verified - STORAGE_ROOT env var fully respected
directory creation:        verified NONE - pointed STORAGE_ROOT at a path
  that does not exist, loaded settings, confirmed the path was still absent
  afterward
```

Detailed artifact paths (`chunks/`, `index/`, `eval.duckdb`, etc.) remain
`task_0.7_storage_abstraction.md`'s job - this task only established the
roots.

### Verification

```text
default load:                    PASS - all fields load with safe defaults,
  no secret required, storage_root resolves correctly
environment override (APP_ENV,
  LOG_LEVEL, DEVICE, EMBEDDING_MODEL,
  STORAGE_ROOT - all 5 at once):  PASS - every override respected
dotenv precedence:                PASS - created a temporary .env with fake
  values (LOG_LEVEL=INFO, APP_ENV=test; deleted immediately after this
  test), confirmed a conflicting process-env LOG_LEVEL=DEBUG won over the
  .env value, and confirmed .env's APP_ENV=test won over the code default
  when no process override was set - full chain: process > .env > default
invalid value rejection (APP_ENV=banana,
  LOG_LEVEL=LOUD, DEVICE=tpu):     PASS - each raised a clear ConfigError
  naming the variable/value/allowed set, none silently coerced
cache_clear() behavior:           PASS - demonstrated stale cached value
  persisting until cache_clear(), then picking up the new env value
.env ignored / .env.example
  trackable:                       PASS - `git check-ignore -v .env` matches
  the existing `.env` rule; `git add -n .env.example` stages it (the
  `!.env.example` exception works)
import side effects:              PASS - `import src.config` took ~35ms and
  left torch/duckdb/lancedb/sentence_transformers/transformers absent from
  sys.modules; resolve_device() imports torch lazily only when called
  (auto correctly resolved to cuda on this machine's validated GPU; cuda/cpu
  pass through literally, never silently downgraded)
secret scan of all new/modified
  files:                           PASS - no API-key/password/Bearer/AWS-
  credential patterns, no real email besides the sanctioned generic
  placeholder, no absolute personal filesystem paths
```

### Files Created / Modified

```text
src/config.py                       (new)
.env.example                        (new)
project_plan/CONFIGURATION.md       (new)
project_plan/REPOSITORY_STRUCTURE.md (small edit: src/config.py marked
  implemented, cross-linked to CONFIGURATION.md)
Progress.md                          (this entry)
```

`project_plan/ENVIRONMENT.md` and `project_plan/DEPENDENCIES.md` needed no
changes - neither referenced configuration incorrectly.

### Result

```text
PASS — centralized configuration system established
```

### Phase Status

```text
Data Preparation                  — COMPLETE
Phase 0                           — IN PROGRESS
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — NEXT
```

---

## 2026-08-26 — Phase 0.6 Logging

### Objective

Establish one predictable logging convention before Phase 1 starts
producing normalization, chunking, embedding, indexing, retrieval,
evaluation, and generation logs — so every future module's output is
readable the same way, with verbosity controlled through the `src.config`
boundary Task 0.5 already established, instead of each module reinventing
its own format or reading `LOG_LEVEL` directly.

### Initial State

```text
existing ingestion logging: src/ingest/common.py's setup_logging() calls
  logging.basicConfig(level=..., format="%(asctime)s  %(levelname)-7s  %(message)s")
  once per CLI script's main(); each fetch_*.py module creates its own
  logging.getLogger(__name__); heavy use of print() for human-readable
  report output (row counts, per-section stats). audit_data.py additionally
  writes its own log file (phase1_data_audit.log) as a deliberate,
  first-class tool output.
no centralized future-application logging utility existed
LOG_LEVEL already centralized by Task 0.5 (src.config.get_settings().log_level)
```

### Design

```text
module:          src/logging_utils.py (deliberately not logging.py, to
                  avoid stdlib-name confusion)
public API:       configure_logging(level=None), get_logger(name),
                  log_event(logger, level, event, **fields)
output:           console/stderr only (logging.StreamHandler(), no file
                  handlers, no logs/ directory created)
timestamp:        UTC, timezone-aware, YYYY-MM-DDTHH:MM:SS.sssZ (custom
                  formatTime() override - never local/naive time)
logger naming:    plain logging.getLogger(name) passthrough - module
                  provenance preserved (e.g. "src.embeddings")
structured events: context assembled directly into the message string,
                  never via logging's extra= dict - eliminates any
                  possibility of a field name colliding with a reserved
                  LogRecord attribute (name/msg/args/levelname/pathname/...)
                  because nothing ever touches LogRecord's own namespace
secret redaction: field names matching password/secret/api_key/apikey/
                  token/authoriz.../credential (case-insensitive) have
                  their value replaced with "[REDACTED]" before formatting -
                  documented explicitly as a narrow, defensive check on
                  recognized field names only, not a guarantee about
                  free-form message text
idempotency:      configure_logging() finds its own named handler
                  ("sec_rag_console_handler") on the root logger and
                  updates its level in place rather than ever adding a
                  second one; other libraries' handlers are left untouched
```

### Example

```text
2026-08-27T00:07:24.250Z level=INFO logger=src.embeddings event=embedding_batch_completed stage=embedding batch=3 processed=96 elapsed_ms=122
```

### Verification

```text
INFO filtering:               PASS - DEBUG hidden, INFO/WARNING visible
DEBUG filtering:               PASS - DEBUG becomes visible after reconfigure
duplicate-handler prevention:  PASS - 3 repeated configure_logging() calls
  left exactly 1 project handler; one logged event appeared exactly once
reconfiguration (INFO->DEBUG): PASS - handler count stayed at 1, new level
  took effect on the existing handler immediately
structured fields:              PASS - tested str/int/float/bool/None/Path/
  string-with-spaces (correctly JSON-quoted)/an unsupported nested list
  (safely fell back to json.dumps rather than raising)
secret redaction:               PASS - fake value SHOULD_NOT_APPEAR_12345
  under api_key/token/password/authorization/apikey never appeared in
  captured output; a non-matching field (safe_field) passed through
  visibly. (Fake value used only in a temporary verification script,
  confirmed absent from every tracked file.)
exception traceback:            PASS - intentional ZeroDivisionError via
  logger.exception(...) preserved full traceback and exception type
no file creation:               PASS - logs/ absent before and after; no
  new root *.log files beyond the pre-existing Data Preparation stage logs
lightweight import:             PASS - `import src.logging_utils` took
  ~45ms and left torch/duckdb/lancedb/sentence_transformers/transformers
  all absent from sys.modules; root logger had zero handlers immediately
  after import (no auto-configuration)
config integration:             PASS - configure_logging() with no explicit
  level, under a process LOG_LEVEL=DEBUG override, correctly sourced DEBUG
  through src.config rather than reading os.environ directly
```

### Existing Ingestion Behavior

`src/ingest/` was **not** modified. Existing acquisition logging (`logging.
basicConfig` via `setup_logging()`, plus extensive `print()`-based report
output, plus `audit_data.py`'s own `phase1_data_audit.log` file) is
retained as legacy working behavior; all new application modules use
`src.logging_utils`. No conflict was found between the two - ingestion
scripts configure logging only inside their own `main()` when run
standalone, so nothing about adding a new, separately-imported module
disturbs them.

### Files Created / Modified

```text
src/logging_utils.py                  (new)
project_plan/LOGGING.md               (new)
project_plan/REPOSITORY_STRUCTURE.md  (small edit: src/logging_utils.py
  marked implemented + cross-linked; logs/ description clarified as
  console-only for now, not yet used)
project_plan/CONFIGURATION.md         (small edit: LOG_LEVEL row
  cross-linked to LOGGING.md)
Progress.md                            (this entry)
```

No dependency files modified - stdlib `logging`/`json`/`re`/`datetime`
only, plus the already-existing `src.config` import. No new package added.

### Result

```text
PASS — centralized logging foundation established
```

### Phase Status

```text
Data Preparation                  — COMPLETE
Phase 0                           — IN PROGRESS
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — NEXT
```

---

## 2026-08-26 — Phase 0.7 Storage Abstraction

### Objective

Centralize where things live — frozen inputs and generated outputs alike —
before Phase 1 starts producing normalized documents, chunks, indexes, and
eval artifacts, so no future module invents its own `Path("data/...")` or
`Path("artifacts/...")` independently.

### Initial State

```text
frozen data layout existed on disk (inspected directly, not assumed):
  data/{msmarco,edgar_corpus,raw/{xbrl,primary},interim/audit_xbrl_meta}
  + xbrl.duckdb + validation_report.md + .gitkeep
artifacts/ did not exist on disk (results/ did, from Task 0.3 - just .gitkeep)
future modules had no centralized path API - only src.ingest.common's
  direct os.getenv("STORAGE_ROOT") existed
STORAGE_ROOT already came from src.config (Task 0.5)
```

### Storage Design

```text
module/API:        src/storage.py - StoragePaths (frozen dataclass),
                    get_storage() (cached), safe_component(), StorageError
frozen-input root:  settings.storage_root (data/ by default)
generated-artifact
  root:             <repo_root>/artifacts - a sibling of data/, not nested
                    inside it (see "Layout note" below)
results root:       <repo_root>/results (unchanged from Task 0.3)
read/write
  boundary:         frozen-input properties are read-only Path accessors;
                    the only writer in the module is ensure_dir(), which
                    refuses (raises StorageError) to create anything
                    outside artifacts_root/results_root
directory creation: explicit only - import, get_storage(), and plain path
                    construction (chunks_dir(...) etc.) never write to disk
```

**Layout note**: `PROJECT_SPEC.md`'s storage-architecture section sketches
an earlier `data/okf/`, `data/chunks/`, `data/index/` convention (generated
artifacts nested inside `data/`). Neither that layout nor `artifacts/`
existed on disk before this task, and this task's own spec explicitly
directs using `artifacts/` as a sibling root unless the repo already
implements a different convention - it didn't. Followed the task's
explicit instruction; flagged the `PROJECT_SPEC.md` inconsistency in
`project_plan/STORAGE.md` for future reconciliation (same category of
staleness already noted for `PROJECT_SPEC.md` in the pre-Phase-0 baseline).

### Frozen Inputs

```text
storage.msmarco_root       -> data/msmarco/
storage.edgar_corpus_root  -> data/edgar_corpus/
storage.raw_xbrl_root      -> data/raw/xbrl/
storage.primary_docs_root  -> data/raw/primary/
storage.xbrl_db            -> data/xbrl.duckdb
```

All repository-relative through `settings.storage_root`; none hardcoded.
`data/interim/audit_xbrl_meta/` and `data/validation_report.md` were not
turned into properties - current code doesn't need them centralized (Step 9's
"useful centralization, not mirroring the filesystem" guidance).

### Generated Layout

```text
artifacts/
├── normalized/<version>/
├── chunks/<chunk_config_hash>/
├── indexes/<chunk_config_hash>/<embedding_model_key>/
└── eval/<eval_version>/
```

Example (from live verification): `storage.index_dir("abc123",
"BAAI/bge-small-en-v1.5")` -> `artifacts/indexes/abc123/BAAI--bge-small-en-v1.5`.

### Versioning

`chunks_dir(chunk_config_hash)` and the other three helpers take an
already-computed identity string and map it deterministically - Task 0.7
does not compute a chunk-config hash, generate a normalizer version, or
define an eval-set version; those belong to the future modules that
actually produce those artifacts. `index_dir` requires **both**
`chunk_config_hash` and `embedding_model` together, since the same chunks
may be embedded with several models in Phase 3 and neither key alone is
sufficient identity.

### S3 Boundary

```text
Local filesystem: implemented (the only backend)
S3 backend: NOT IMPLEMENTED - no boto3/s3fs/AWS credentials, no S3Storage/
  CloudStorage placeholder classes, nothing added to requirements
Future logical-key compatibility: yes - every generated path is built from
  POSIX-style logical components (chunks/<hash>, indexes/<hash>/<model>)
  resolved beneath one root, so a future S3 backend could map the same
  keys under an S3 prefix instead - but that backend does not exist yet,
  and this is stated plainly rather than implied
```

### Verification

```text
frozen input paths resolve:     PASS - msmarco/edgar_corpus/xbrl_db/
  raw_xbrl/primary_docs all confirmed .is_dir()/.is_file() True;
  require_file/require_dir pass on valid paths, raise StorageError with a
  clear message on a deliberately missing path
generated paths deterministic:  PASS - chunks_dir("abc123") called twice
  returned equal paths; different hash produced a different path; path
  confirmed under artifacts_root
different versions -> different
  locations:                     PASS - index_dir differed correctly by
  chunk_config_hash alone and by embedding_model alone (tested independently)
safe model-key conversion:       PASS - "BAAI/bge-small-en-v1.5" ->
  "BAAI--bge-small-en-v1.5"; "model with spaces" -> "model-with-spaces";
  "ns:model" -> "ns-model"
path traversal rejection:        PASS - "../escape", "..\\escape", "/path",
  "C:\\escape", "..", ".", "" all raised StorageError (not silently
  sanitized); storage.chunks_dir("../escape") - the literal example from
  this task's own spec - confirmed to raise
explicit directory creation:     PASS - tested via a disposable
  artifacts/chunks/_task07_smoke_test/ child (removed after): absent
  before, created only on explicit ensure_dir() call, idempotent repeat
  call succeeded without error, cleaned up afterward, artifacts/ left
  fully absent again
ensure_dir root restriction:     PASS - attempts to ensure_dir() a path
  under data/ or the bare repo root both raised StorageError and created
  nothing (verified on disk)
no import-time directory
  creation:                       PASS - `import src.storage` alone left
  artifacts/ absent; get_storage() and plain path construction (chunks_dir
  etc.) also created nothing
STORAGE_ROOT override:           PASS - overriding STORAGE_ROOT moved
  data_root/msmarco_root as expected, left artifacts_root/results_root
  correctly unaffected (repo-relative regardless of where data/ lives),
  and created no directory merely from loading config/storage
lightweight import:               PASS - ~43ms, torch/sentence_transformers/
  duckdb/lancedb/pyarrow all absent from sys.modules after import
frozen data unchanged:            PASS - xbrl.duckdb size (7,011,053,568
  bytes), msmarco/edgar_corpus file counts, raw/xbrl ZIP count (36),
  raw/primary directory count (990), and data/ top-level directory count
  (5) all identical before and after this task
Git safety:                       PASS - see below
```

### Existing Ingestion

```text
unchanged — frozen Data Preparation code retained
```

`src/ingest/` was not modified and does not use `src.storage`.
`src/ingest/common.py`'s direct `os.getenv("STORAGE_ROOT", "./data")`
continues to work exactly as before.

### Files Created / Modified

```text
src/storage.py                        (new)
project_plan/STORAGE.md               (new)
project_plan/REPOSITORY_STRUCTURE.md  (small edit: src/storage.py marked
  implemented, cross-linked; artifacts/ description cross-linked to
  STORAGE.md)
project_plan/CONFIGURATION.md         (small edit: storage-paths pointer
  updated from "task_0.7... not this file's" to cross-link the now-
  implemented STORAGE.md)
Progress.md                           (this entry)
```

No dependency files modified - stdlib only (`pathlib`, `dataclasses`,
`functools`, `re`), plus the already-existing `src.config`/
`src.logging_utils` imports. No new package added.

### Result

```text
PASS — centralized storage abstraction established
```

### Phase Status

```text
Data Preparation                  — COMPLETE
Phase 0                           — IN PROGRESS
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — COMPLETE
  0.8 Basic Automated Tests       — NEXT
```

---

## 2026-08-26 — Phase 0.8 Basic Automated Tests

### Objective

Tasks 0.1–0.7 relied mostly on manual, one-off verification (recorded in
each Progress.md entry, but never re-runnable). Task 0.8 turns the
important invariants from that manual work — config defaults/overrides/
validation/caching, logging idempotency/redaction, storage determinism/
traversal-safety, dependency compatibility, and the CUDA/LanceDB/DuckDB/
embedding capability checks — into a repeatable `pytest` suite that
protects the Phase 0 foundation before Phase 1 builds on top of it.

### Initial State

```text
pytest 9.1.1 already installed (Task 0.4)
tests/ existed only as a placeholder (tests/.gitkeep, from Task 0.3)
zero automated tests anywhere in the repository
foundation modules implemented and manually verified: src/config.py (0.5),
  src/logging_utils.py (0.6), src/storage.py (0.7)
```

### Test Strategy

Portable tests (no machine-specific capability required) vs. three marked
local-capability smoke-test categories (`local_data`, `gpu`, `model`).
Missing capability skips with a clear reason; present-but-broken capability
fails - never silently converted to a skip. Offline-only: no test
downloads a dataset or model or calls an external API; the one test that
could plausibly reach the network (`test_embedding_smoke.py`) sets
`HF_HUB_OFFLINE=1` and `local_files_only=True`, and pre-checks
`huggingface_hub.try_to_load_from_cache(...)` to distinguish "not cached"
(skip) from "cached but broken" (fail) before ever calling
`SentenceTransformer(...)`.

Process-global state (Python `logging`, and `get_settings()`/`get_storage()`'s
`lru_cache`) is snapshotted and restored around every test via two autouse
fixtures in `tests/conftest.py`, so tests can freely `monkeypatch` env vars
or call `configure_logging()` without leaking state between tests or files.

### Test Inventory

| Test area | Tests | Category |
|---|---:|---|
| Configuration | 9 | portable |
| Logging | 8 | portable |
| Storage | 21 | portable |
| Dependency imports | 10 | portable |
| Ingest module imports | 7 | portable |
| LanceDB (temp DB only) | 1 | portable |
| DuckDB / local data presence | 2 | local_data |
| CUDA kernel | 1 | gpu |
| Embedding (bge-small) | 1 | gpu + model |
| **Total** | **60** | |

### Portable Test Result

```text
command:  python -m pytest -m "not local_data and not gpu and not model"
passed:   56
failed:   0
skipped:  0
runtime:  6.72s
```

### Full Local Test Result

```text
command:  python -m pytest
passed:   60
failed:   0
skipped:  0
runtime:  9.04s (first run), 8.42s and 7.67s on two repeated runs -
          identical pass count each time, confirming order/state
          independence
```

No skips to explain - this machine has the frozen data, the RTX 5060 GPU,
and the cached `bge-small` model, so every local-capability test actually
executed rather than skipping.

### Machine Smoke Results

```text
DuckDB read-only (data/xbrl.duckdb):        PASS - facts/submissions tables
  present, facts count 90,685,753 (exact match to the frozen figure)
LanceDB temp DB (tmp_path only):             PASS - 3-row create/count/
  search round-trip via to_arrow(), no pandas dependency assumed
CUDA kernel (512x512 matmul):                PASS - finite result on
  NVIDIA GeForce RTX 5060 Laptop GPU
BAAI/bge-small-en-v1.5 offline/cached
  GPU inference:                              PASS - loaded with
  local_files_only=True (no download), 2 embeddings, shape (2, 384), all
  finite, device=cuda
```

No throughput benchmark repeated here - that's Task 0.2's job, not this
one's.

### Offline / Safety Verification

```text
no network downloads:        confirmed - fetch_* modules only imported,
  never executed; embedding test guarded by HF_HUB_OFFLINE=1 +
  local_files_only=True + a pre-check that skips before any load attempt
no API credentials required: confirmed - full suite runs with no
  OPENAI_API_KEY/ANTHROPIC_API_KEY/SEC_USER_AGENT/AWS credentials set
no frozen data mutation:     confirmed - xbrl.duckdb size (7,011,053,568
  bytes), msmarco/edgar_corpus file counts, raw/xbrl ZIP count (36), and
  raw/primary directory count (990) all identical before and after the
  full suite ran three times
temporary writes isolated:   confirmed - tmp_path for LanceDB/config/
  storage-override tests; a disposable artifacts/ child (removed in a
  finally block, plus a session-scoped conftest.py backstop) for the one
  ensure_dir() idempotency test; artifacts/ confirmed absent again after
  the run
warnings:                    zero - full suite produces no pytest warnings
```

### Files Created / Modified

```text
pytest.ini                          (new - registers local_data/gpu/model markers)
tests/conftest.py                   (new)
tests/test_config.py                (new, 9 tests)
tests/test_logging_utils.py         (new, 8 tests)
tests/test_storage.py               (new, 21 tests)
tests/test_dependencies.py          (new, 10 tests)
tests/test_ingest_imports.py        (new, 7 tests)
tests/test_lancedb_smoke.py         (new, 1 test)
tests/test_duckdb_smoke.py          (new, 2 tests)
tests/test_gpu_smoke.py             (new, 1 test)
tests/test_embedding_smoke.py       (new, 1 test)
tests/.gitkeep                      (removed - no longer needed)
project_plan/TESTING.md             (new)
project_plan/REPOSITORY_STRUCTURE.md (small edits: tests/ marked
  implemented and cross-linked to TESTING.md; tracked-files list updated
  to include pytest.ini/requirements*.txt/.env.example, which had
  accumulated since Task 0.3's tree without being reflected there)
Progress.md                          (this entry)
```

No dependency files modified - `pytest==9.1.1` was already present from
Task 0.4; only stdlib + pytest builtins (`tmp_path`, `monkeypatch`) used.

### Result

```text
PASS — Phase 0 foundation test suite established with zero failures
```

### Phase Status

```text
Data Preparation                  — COMPLETE
Phase 0                           — IN PROGRESS
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — COMPLETE
  0.8 Basic Automated Tests       — COMPLETE
  0.9 Developer Commands          — NEXT
```

---

## 2026-08-26 — Phase 0.9 Developer Commands

### Objective

Consolidate the routine foundation checks built across Tasks 0.1–0.8
(environment health, tests, data-path presence, GPU capability, local
smoke tests) behind one memorable, cross-platform developer interface,
instead of requiring several raw commands to be remembered and typed
correctly every time.

### Initial State

```text
scripts/ contained only scripts/.gitkeep (placeholder, Task 0.3)
tests/ had 60 passing tests, 0 failures, 0 skips, 0 warnings (Task 0.8 baseline,
  reconfirmed before starting this task)
routine checks required raw commands: python -m pytest [-m ...],
  ad hoc python -c "..." snippets for config/storage/GPU checks
```

### Developer Interface

```text
python scripts/dev.py doctor
python scripts/dev.py test
python scripts/dev.py test --portable
python scripts/dev.py data
python scripts/dev.py gpu
python scripts/dev.py smoke
```

Pure standard library (`argparse`, `subprocess`, `pathlib`) plus the
project's own `src.config`/`src.storage`/`pytest`/`torch` - no CLI
framework added. Repository root resolved from the script's own file
location (`Path(__file__).resolve().parents[1]`), not the working
directory - verified by invoking `--help` and `doctor` from `%TEMP%`, well
outside the repo, with identical correct output. All subprocesses use
`sys.executable`, so the script always runs against whatever interpreter
(and `.venv`) it was itself launched with.

### Command Behavior

```text
doctor: required-foundation checks (Python version vs .python-version,
  venv detection, pip check, core dependency imports, src.config/src.storage
  load) must all pass for a zero exit. Local data and CUDA are reported
  separately as "Optional capabilities" - informational only, never fail
  doctor, so a public clone without the 26 GB dataset or a GPU still gets
  a clean doctor PASS on the required-foundation section.
data: explicit invocation, so missing frozen input IS a failure (unlike
  doctor) - checks is_dir()/is_file() only via src.storage, never scans,
  counts, or downloads.
gpu: explicit invocation, so missing or broken CUDA IS a failure - runs one
  real 512x512 CUDA matmul via torch, never silently falls back to CPU.
  Deliberately does not load the embedding model (kept fast; that's
  smoke's job).
test / test --portable / smoke: thin subprocess wrappers around
  `python -m pytest [-m ...]`, exit code preserved exactly, no pytest
  logic reimplemented. --portable and smoke reuse the exact Task 0.8
  marker expressions, not duplicated logic.
```

### Verification

```text
--help              PASS - exit 0, lists all 5 commands
doctor               PASS - exit 0, all required-foundation lines PASS,
                     optional capabilities both AVAILABLE on this machine
test --portable      PASS - exit 0, 56 passed / 0 failed / 0 skipped, 6.21s
data                 PASS - exit 0, all 5 frozen paths PASS, repo-relative
                     output only (no personal absolute path printed)
gpu                  PASS - exit 0, RTX 5060 Laptop GPU, sm_120 (12.0),
                     512x512 matmul finite
smoke                PASS - exit 0, 4 passed / 0 failed / 0 skipped
                     (local_data x2, gpu, model), 6.72s
test (full)          PASS - exit 0, 60 passed / 0 failed / 0 skipped, 6.97s
```

All 6 commands verified from the repository root; `--help` and `doctor`
additionally verified from `%TEMP%` (a directory well outside the repo),
confirming repo-root detection does not depend on the working directory.

### Automated Tests

Added `tests/test_dev_commands.py` (3 tests: `--help` lists commands and
exits 0; `doctor` passes in this venv; `data` fails clearly and creates
nothing when pointed at an empty `STORAGE_ROOT`) - run as real subprocesses,
never launching `test`/`smoke` recursively (that would start a second,
nested pytest run of this same suite).

```text
new total test count:  63 (was 60; +3 from test_dev_commands.py)
portable result:        59 passed, 0 failed, 0 skipped, 13.48s
full result:             63 passed, 0 failed, 0 skipped, 14.45s (14.38s on
                         a repeated run - stable)
```

No skips to explain - same as Task 0.8, this machine has the data, GPU,
and cached model.

### Safety

```text
no network access:            confirmed - all commands offline by design;
  smoke inherits Task 0.8's HF_HUB_OFFLINE=1 / local_files_only=True /
  cache-precheck guarantees for the embedding test
no downloads:                  confirmed - data/gpu/doctor never fetch
  anything; test/smoke only run already-installed pytest
no frozen-data mutation:        confirmed - xbrl.duckdb size
  (7,011,053,568 bytes) identical before/after this task's full command
  and test-suite runs
no credentials required:        confirmed - all 6 commands run with no
  OPENAI_API_KEY/ANTHROPIC_API_KEY/SEC_USER_AGENT/AWS credentials set
no package installation:        confirmed - dev.py never calls pip;
  doctor's pip check is read-only diagnostic only
```

### Phase 0 Exit Gate — IMPORTANT DISCREPANCY FOUND

This task's own Step 33 checklist (9 items) is fully satisfied:

```text
[x] fresh terminal can activate project environment  - doctor PASS
[x] core dependencies import                          - doctor + test_dependencies.py PASS
[x] PyTorch sees GPU                                   - gpu command PASS
[x] real GPU computation succeeds                       - gpu command's matmul PASS
[x] sentence-transformer embeds sample text              - smoke / test_embedding_smoke.py PASS
[x] DuckDB opens local XBRL database                      - data + test_duckdb_smoke.py PASS
[x] LanceDB creates/reads tiny test table                  - test_lancedb_smoke.py PASS (portable suite)
[x] config/storage roots are portable                       - test_config.py/test_storage.py override tests PASS
[x] core smoke tests pass                                    - smoke command, 4/4 PASS
```

**However**, `project_plan/PROJECT_EXECUTION.md`'s actual, current Phase 0
"Exit criteria" section (re-read directly during this task, not from
memory) lists **10** items, not 9 - it still includes:

```text
- [ ] Serving latency has been measured, not estimated.
- [ ] The serving target is chosen and the decision is recorded.
```

These map directly to **Task 0.10 - Serving feasibility spike**, which
`PROJECT_EXECUTION.md` still defines as part of Phase 0 (`### 0.10 Serving
feasibility spike`, with its own subtasks and a decision-threshold table).
This task's own prompt (`task_0.9_developer_commands.md`) states "This is
the final numbered Phase 0 subtask in the current execution plan" and "Do
NOT invent a task_0.10 during this task" - but Task 0.10 demonstrably
already exists in `project_plan/PROJECT_EXECUTION.md` and has never been
executed in this session. Neither serving latency nor a serving-target
decision has been measured or recorded anywhere in this project.

This is a real conflict between this task's instructions and the
authoritative planning document, in the same category as the
`PROJECT_SPEC.md` staleness flagged in the pre-Phase-0 baseline entry - not
something to silently resolve by picking a side. Per this task's own stop
condition ("Phase 0 exit gate has any unresolved required item") and
acceptance criterion ("Phase 0 marked COMPLETE only if exit gate passes"),
**Phase 0 is not marked COMPLETE below.**

### Files Created / Modified

```text
scripts/dev.py                        (new)
scripts/.gitkeep                      (removed - no longer needed)
tests/test_dev_commands.py            (new, 3 tests)
project_plan/DEVELOPER_COMMANDS.md    (new)
project_plan/ENVIRONMENT.md           (small edit: doctor cross-link)
project_plan/TESTING.md               (small edit: dev.py command
  shortcuts alongside the existing raw pytest commands)
project_plan/REPOSITORY_STRUCTURE.md  (small edits: scripts/ marked
  implemented and cross-linked; tracked-files list updated)
Progress.md                           (this entry)
```

No dependency files modified - stdlib only, plus the project's own
existing modules.

### Result

```text
PASS — developer commands established; Phase 0 exit gate has an
  unresolved item (Task 0.10, see discrepancy above) that this task's own
  scope explicitly forbids starting
```

### Phase Status

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — 9/10 exit criteria met, NOT COMPLETE
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — COMPLETE
  0.8 Basic Automated Tests       — COMPLETE
  0.9 Developer Commands          — COMPLETE
  0.10 Serving Feasibility Spike  — NOT STARTED (exists in
                                     PROJECT_EXECUTION.md; this task's own
                                     prompt did not account for it - see
                                     discrepancy note above; awaiting a
                                     decision on how to proceed)
```

## 2026-08-26 — Phase 0.10 Serving Feasibility Spike

### Objective

Task 0.10 resolves the discrepancy flagged at the end of Task 0.9: the
Task 0.9 prompt asserted it was the final Phase 0 subtask, but
`project_plan/PROJECT_EXECUTION.md` still listed Task 0.10 and two Phase 0
exit criteria ("serving latency has been measured, not estimated"; "the
serving target is chosen and the decision is recorded") that nothing prior
had satisfied. This task replaces those remaining serving-architecture
estimates with a representative measured experiment: build a disposable
~100,000-chunk benchmark corpus, embed it, index it in LanceDB (flat +
`IVF_PQ`), load an ONNX INT8 MiniLM reranker, and measure warm and
process-cold latency on the CPU serving path — then apply
`PROJECT_EXECUTION.md`'s frozen decision thresholds to choose a default
Phase 4 serving target (Lambda vs. Fargate).

### Initial State

```text
Tasks 0.0-0.9 complete
Phase 0 not complete (9/10 exit criteria met per Task 0.9's own report)
serving latency unmeasured
serving target unresolved
```

### Benchmark Configuration

```text
representative chunk count: 100,000 (actual: 100,000)
chunk length:                512 tokens, no overlap
embedding model:             BAAI/bge-small-en-v1.5 (384-dim, verified)
vector store:                LanceDB 0.37.1 - flat (brute-force) + IVF_PQ
                              (100 partitions, 48 sub-vectors, 8 bits)
retrieval top-k:              50
reranker:                     Xenova/ms-marco-MiniLM-L-6-v2, ONNX Runtime
                              1.29.0, INT8, CPUExecutionProvider
query count:                  180 measured + 10 warm-up, x2 reproducibility
                              passes, + 10 process-cold subprocess samples
CPU/resource configuration:   CPU_THREADS=2 (torch + ONNX Runtime intra-op)
```

New dev dependency: `onnxruntime==1.29.0`, `psutil==7.2.2`, added to
`requirements-dev.txt` (Task 0.10 scope only; not a production runtime
dependency yet since no `src/` production code exists). `pip check` and
the portable suite both verified clean after the addition.

### Corpus

100,000 chunks selected deterministically (`ORDER BY hash(filename)`) from
`data/edgar_corpus/*.parquet`, sections `section_1, section_1A, section_7,
section_7A, section_8`, spanning 2,504 unique filings (mean 485.0 tokens,
p50/p95 512). Labeled explicitly in code, config, and results as the
**DISPOSABLE SERVING-SPIKE CORPUS** — not the Phase 1 development corpus.
`data/` was read-only throughout; frozen-data invariants (below) confirm
no mutation.

### Methodology

```text
warm-up count:            10 (unmeasured)
warm measured request count: 180 per pass, 2 passes for reproducibility
cold-process sample count:   10 independent fresh subprocesses
component timing method:     time.perf_counter() around each stage inside
                              run_single_query() (embed / flat search /
                              rerank / quantized search)
memory measurement method:   psutil RSS at 6 defined stages + peak during
                              warm benchmark
```

A first dry run (`--target-chunks 2000 --rebuild`) was executed and fully
diagnosed before committing to the real run: every individual component
(DuckDB corpus query, tokenizer, reranker load, LanceDB index build, GPU
embedding build) timed fast in isolation, but the full warm-benchmark loop
took ~12-25 minutes. This was confirmed to be genuine CPU-bound ONNX
reranking cost (up to 50 passages x up to 512 tokens per query, under the
deliberate 2-thread constraint), not a bug — the dry run completed cleanly
end-to-end with a self-consistent decision output before the 100K
production run was launched.

### Results

**Component timing (ms, warm pass 1, n=170):**

| Component | p50 | p90 | p95 | p99 |
|---|---:|---:|---:|---:|
| Query embedding (CPU) | 20.2 | 27.1 | 32.2 | 39.9 |
| Vector retrieval (flat) | 101.1 | 152.5 | 171.4 | 199.2 |
| Vector retrieval (quantized) | 10.0 | 21.2 | 28.6 | 39.8 |
| Reranking (ONNX INT8, top-50) | 2801.7 | 3399.3 | 3830.2 | 3961.1 |

**End-to-end path timing (ms, warm pass 1, n=170):**

| Path | p50 | p95 |
|---|---:|---:|
| Vector-only (flat) | 120.2 | 205.5 |
| Vector-only (quantized) | 30.4 | 56.7 |
| Vector + rerank | 2939.4 | **4014.2** |

Reproducibility pass 2: vector-only p95 209.3 ms (+1.9% vs pass 1);
vector+rerank p95 4544.0 ms (+13.2% vs pass 1) - larger drift than ideal,
attributed to laptop thermal/background-load variance on the CPU-bound
reranker stage specifically (component-level embedding/retrieval timing
stayed stable between passes). Does not change the decision - both passes
clear every relevant threshold by a wide margin.

**Process-cold proxy (10 subprocess samples):** p50 14.26 s, p90 14.99 s,
p95 18.65 s. Explicitly labeled *local process-cold proxy — not a real AWS
Lambda cold start*.

**Memory (RSS):** baseline 2897.8 MB -> after reranker load 2975.2 MB ->
after one query 5052.2 MB -> peak during warm benchmark 7347.1 MB.

**Artifact sizes:** LanceDB flat index 287.6 MB, LanceDB quantized index
292.9 MB, reranker ONNX INT8 model 23.0 MB. `.venv` size not reported as a
deployment estimate (CUDA dev environment, not representative of a CPU
serving package).

**Embedding build (offline, GPU, excluded from serving latency):** 100,000
chunks in 1197.4 s, peak VRAM 2656.7 MB.

Full results: `results/phase_0_10_serving_spike.json`,
`results/phase_0_10_serving_spike.csv`. Config:
`configs/serving_spike.json` (`spike_config_hash=6dcdff763323d2b1`).

### Decision Thresholds

From `project_plan/PROJECT_EXECUTION.md` (applied without modification
after seeing results):

```text
warm p95 < 500 ms         -> proceed with the serverless design
warm p95 500 ms - 2 s     -> proceed, but constrain reranker/candidate pool
warm p95 > 2 s             -> change serving target to warm compute
process-cold proxy > 10 s -> serverless target unsuitable regardless
```

### Serving Decision

**Fargate / continuously warm service preferred** as the Phase 4 default
serving target. Both independent thresholds triggered the same direction:
warm p95 (vector+rerank) = 4014.2 ms (pass 1, 4544.0 ms pass 2), both
> 2 s; process-cold p95 = 18.65 s, > 10 s. The dominant cost is CPU-bound
ONNX reranking of 50 candidates (p50 ~2.8 s of the ~2.9-3.9 s total path),
not embedding or vector search - meaning Phase 3's reranker-size /
candidate-pool choices are what could later change this picture, not this
decision itself. This is a default deployment direction for later
engineering, not a built production environment - Task 0.10 deployed
nothing; Phase 4 still owns actual deployment.

### Limitations

```text
100,000 chunks - a representative subset, not the full ~14M-chunk
  projected production corpus
local process-cold proxy, not a real AWS Lambda cold start
no generation/LLM latency included
no trusted relevance evaluation performed or claimed
provisional retrieval components (bge-small, MiniLM, 512-token chunking,
  top-50) - not final Phase 3 selections
cloud memory-tier scaling (Lambda 1/2/4 GB) not reproduced - Docker
  installed but daemon not running; single-configuration RSS only
single development machine, single measurement session - laptop
  thermal/background-load variance observed directly (pass 1 vs pass 2
  rerank delta)
```

**Recorded discrepancy** (per the standing "follow PROJECT_EXECUTION.md,
record rather than silently resolve" instruction): `PROJECT_EXECUTION.md`'s
Task 0.10 checklist also names "deploy a minimal retrieval function to the
candidate serving target," "repeat with and without binary quantization,"
and "repeat across plausible memory allocations." None of these three were
performed literally - the local process-cold proxy substitutes for actual
deployment (Step 22/23 of the task prompt explicitly sanctions this
substitution), the quantization comparison performed is flat vs. LanceDB
`IVF_PQ` (product quantization, the simplest defensible LanceDB ANN
configuration) rather than binary quantization specifically, and
memory-tier repetition was skipped per the task prompt's own Step 26 WARN
fallback since Docker's daemon was not running. Full detail in
`project_plan/SERVING_FEASIBILITY.md`.

### Phase 3 Re-check

The selected production-like retrieval stack must be re-benchmarked
against this Phase 0 feasibility budget after chunking, embeddings,
reranking, and retrieval configuration have been scientifically selected in
Phase 3. This decision is not permanently frozen.

### Files Created / Modified

```text
scripts/serving_spike.py            (new - benchmark code, clearly labeled
                                      FEASIBILITY/BENCHMARK, not production)
configs/serving_spike.json          (new)
results/phase_0_10_serving_spike.json  (new)
results/phase_0_10_serving_spike.csv   (new)
project_plan/SERVING_FEASIBILITY.md  (new)
tests/test_serving_spike.py          (new - 7 deterministic helper tests:
                                      config hash determinism/uniqueness/
                                      key-order stability, percentile stats,
                                      default_config required keys)
requirements-dev.txt                 (modified - onnxruntime, psutil added)
project_plan/REPOSITORY_STRUCTURE.md (modified - configs/, scripts/,
                                      tests/ entries updated for Task 0.10)
project_plan/DEVELOPER_COMMANDS.md   (modified - cross-link to
                                      serving_spike.py / SERVING_FEASIBILITY.md)
Progress.md                          (this entry)
```

Large generated benchmark artifacts (100K-chunk corpus, embeddings,
LanceDB flat + quantized indexes) live under
`artifacts/serving_spike/6dcdff763323d2b1/` and `artifacts/serving_spike/
<dry-run-hash>/` - both git-ignored, confirmed not stageable (see Safety
below).

### Tests

```text
python scripts/dev.py doctor         -> PASS (required foundation all PASS;
                                         local data + CUDA both AVAILABLE)
python scripts/dev.py test --portable -> 66 passed, 4 deselected, 0 failed
python scripts/dev.py test            -> 70 passed, 0 failed, 0 skipped
```

The 4 new `test_serving_spike.py` cases beyond the original 66/70-portable
baseline plus the 3 pre-existing local-capability tests bring the full
suite from 63 (end of Task 0.9) to 70 total collected tests.

### Frozen Data

```text
data/xbrl.duckdb:      7,011,053,568 bytes - byte-identical to every prior
                        task's recorded baseline (unchanged)
data/edgar_corpus/:    3 parquet files (train/test/validation) - unchanged
data/raw/xbrl/*.zip:   36 files - unchanged
data/raw/primary/:     990 filings - unchanged
```

Verified before and after both the dry run and the 100K production run.
`scripts/serving_spike.py` only reads from `data/`.

### Safety

```text
git status --short / --ignored --short:  only small tracked deliverables
  untracked (this repo has no commits yet - see Task 0.0); artifacts/,
  data/*, .venv/, .tmp/, __pycache__/ all correctly ignored (!!)
git add -n .:  would stage scripts/serving_spike.py, configs/serving_spike
  .json, results/phase_0_10_serving_spike.{json,csv}, project_plan/
  SERVING_FEASIBILITY.md, tests/test_serving_spike.py, requirements-dev.txt,
  Progress.md, plus everything already pending from prior tasks - no
  100K-chunk corpus, embeddings, LanceDB index, or ONNX weights included
git count-objects -vH:  0 objects, 0 bytes (no commit has been made this
  session, consistent with every prior task)
no network access beyond documented model downloads: bge-small and MiniLM
  reranker fetched from Hugging Face (cache outside repo, source
  documented, no weights tracked)
no LLM generation involved: confirmed - retrieval/reranking path only
```

### Result

```text
PASS - serving feasibility measured and serving target selected
```

No Git commit created. No Git push performed. No Phase 1 work started.

## Phase Status (updated)

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — COMPLETE
  0.8 Basic Automated Tests       — COMPLETE
  0.9 Developer Commands          — COMPLETE
  0.10 Serving Feasibility Spike  — COMPLETE

Phase 1 — Make It Work End to End — NEXT
```

## 2026-08-26 — Phase 0 Checkup

### Objective

Independent post-implementation verification of the entire Phase 0
foundation (Tasks 0.0–0.10) before starting Phase 1. Nothing was accepted
solely because `Progress.md` claimed it passed — every check below was
re-run against the repository as it currently exists.

### Repository State

```text
branch:         main
commit count:   0 (repository has never been committed)
remote:         none configured
tags:           none
working tree:   90 files would be staged by `git add -n .` (all Phase 0/
                Phase 1 data-acquisition deliverables); 0 dangerous
                patterns (no data/, *.duckdb, *.lance, *.parquet, *.zip,
                model weights, .venv/, .tmp/) found in the dry-run list
```

### Phase 0 Task Audit

| Task | Result | Evidence |
|---|---|---|
| 0.0 Git Safety | WARN | `.gitignore` correct and verified live; repo still has 0 commits despite `GIT_CONVENTIONS.md` explicitly saying "make an initial commit now, before Phase 0" — see Git Safety below |
| 0.1 Python Environment | PASS | `.venv` interpreter/pip both inside `.venv`, `include-system-site-packages = false`, Python 3.11.9 matches `.python-version`, `pip check` clean |
| 0.2 CUDA/GPU | PASS | `dev.py gpu` re-run: real 512x512 matmul kernel executed, finite result, RTX 5060 Laptop GPU, compute capability 12.0 |
| 0.3 Repository Structure | PASS | expected tree present; all 13 Phase 1+ `src/` packages confirmed to contain only empty `__init__.py` (no accidental implementation) |
| 0.4 Dependency Management | WARN (fixed) | all 8 key imports + `pip check` clean; all installed direct versions match pinned versions exactly; **found and fixed**: `DEPENDENCIES.md` had 2 stale "not implemented yet" lines (python-dotenv, pytest) contradicted by working code/70 passing tests, and was missing `onnxruntime`/`psutil` entries added in Task 0.10 |
| 0.5 Configuration | PASS | `import src.config` alone, and `config+logging+storage` together, load zero heavy modules (torch/sentence_transformers/duckdb/lancedb); `.env` ignored, `.env.example` trackable (verified via `git add -n`, not just `check-ignore`) |
| 0.6 Logging | PASS | covered by 8 passing `test_logging_utils.py` cases in the full suite; no unexpected `logs/`/`*.log` files created by the application logger |
| 0.7 Storage | PASS | no S3 code exists in `src/storage.py`; `STORAGE.md` states "S3 backend: NOT IMPLEMENTED" truthfully; path-safety covered by 21 passing `test_storage.py` cases |
| 0.8 Basic Automated Tests | PASS | 70 collected, 70 passed, 0 failed, 0 skipped on this re-run |
| 0.9 Developer Commands | PASS | `doctor`/`test`/`test --portable`/`data`/`gpu`/`smoke` all re-run directly; `--help` and `doctor` also re-run from `C:\Users\omtil` (outside repo root) with identical correct output — confirms CWD-independence |
| 0.10 Serving Feasibility Spike | PASS | `spike_config_hash` identical across `configs/serving_spike.json` and `results/phase_0_10_serving_spike.json` (`6dcdff763323d2b1`); real numeric measurements present (not estimates); `artifacts/serving_spike/` confirmed git-ignored |

### Foundation Verification

```text
doctor:              PASS (Python/venv/pip check/core imports/config/
                      storage all PASS; local data + CUDA both AVAILABLE)
pip check:            No broken requirements found
portable tests:        66 passed, 4 deselected, 0 failed (19-20s)
smoke tests:            4 passed, 66 deselected, 0 failed, 0 skipped
                      (local_data/gpu/model all AVAILABLE - no skips to
                      explain on this machine)
full tests:            70 passed, 0 failed, 0 skipped (~21s)
data paths:             MS MARCO / EDGAR-CORPUS / raw XBRL / primary
                      filings / xbrl.duckdb (7.01 GB) all PASS
GPU:                    real CUDA kernel (512x512 matmul), finite result
cached embedding:       covered by test_embedding_smoke.py (offline,
                      cache-precheck, 384-dim, finite)
DuckDB:                 read-only smoke passes (test_duckdb_smoke.py x2)
LanceDB:                temp create/write/read/search smoke passes
```

### Serving Check

```text
warm p50 (vector+rerank):    2939.4 ms
warm p95 (vector+rerank):    4014.2 ms  (pass 2 reproducibility: 4544.0 ms)
process-cold p50:            14.26 s
process-cold p95:            18.65 s   (local process-cold proxy, not a
                              real Lambda cold start - labeled as such
                              throughout)
peak RSS during warm bench:  7347.1 MB
serving decision:            Fargate / continuously warm service preferred
threshold interpretation:    warm p95 > 2s -> "change serving target to
                              warm compute" (frozen PROJECT_EXECUTION.md
                              table); cold proxy > 10s -> "serverless
                              target unsuitable regardless" - both
                              triggered independently, same direction
```

### Reproducibility

```text
Python version contract:     .python-version=3.11, venv=3.11.9 - match
requirements state:          torch==2.13.0+cu130, sentence-transformers==
                              6.0.0, duckdb==1.5.5, pyarrow==25.0.1,
                              lancedb==0.37.1, fastapi==0.141.1,
                              pytest==9.1.1, onnxruntime==1.29.0,
                              psutil==7.2.2 - every installed direct
                              version matches its pin exactly, 0 drift
config provenance:            ENVIRONMENT.md / DEPENDENCIES.md (now
                              corrected) / CONFIGURATION.md all present
                              and consistent with actual code
serving benchmark provenance: configs/serving_spike.json + results/
                              phase_0_10_serving_spike.{json,csv} +
                              SERVING_FEASIBILITY.md all cross-linked by
                              spike_config_hash=6dcdff763323d2b1
```

### Git Safety

```text
dry-run staging result:      90 files would be staged, all small Phase
                              0/data-acquisition deliverables; 0 matches
                              for data/*.duckdb/*.lance/*.parquet/*.zip/
                              model-weight/.venv/.tmp/artifacts patterns
largest stageable file:      Progress.md, 109,490 bytes (~107 KB)
approximate total stageable size: ~0.91 MB
ignored large/generated categories: data/, artifacts/, .venv/, .tmp/,
                              *.duckdb, __pycache__/ - all verified live
                              via git check-ignore, not assumed
secret scan result:          clean - no API keys/AWS credentials/private
                              keys/passwords/bearer tokens and no real
                              personal email or home-directory path found
                              in any of the 90 stageable files
```

**Significant finding**: the repository has **0 commits**. `GIT_CONVENTIONS.md`
explicitly instructs "make an initial commit now, before Phase 0, containing
the planning documents" and "commit per subtask." All of Tasks 0.0–0.10 were
implemented and verified across this entire session without a single commit
being made — every task's own prompt correctly withheld commits pending
explicit approval, so this is expected given how the session was run, but it
means the full engineering history (five silent validation bugs' worth of
work, per `GIT_CONVENTIONS.md`'s own framing of why history matters) exists
only in `Progress.md` prose, not in commit granularity. This is recorded as a
WARNING, not a blocker, because none of `PROJECT_EXECUTION.md`'s 10 official
Phase 0 exit criteria mention Git history — but it should be resolved (an
initial commit, then per-subtask history) before Phase 1 work accumulates
further uncommitted state on top of it. Per this checkup's own instructions,
no commit was created to "fix" this.

### Scope Check

```text
Phase 1 implementation detected: NO
```

All 13 Phase 1+ `src/` packages (`normalize/`, `chunk/`, `embeddings/`,
`index/`, `retrieval/`, `generation/`, `eval/`, `router/`, `rerank/`,
`crag/`, `guards/`, `api/`, `cli/`) contain only an empty `__init__.py`.
`scripts/serving_spike.py`'s benchmark-local chunking/embedding code stays
inside the script, clearly labeled `FEASIBILITY / BENCHMARK CODE - NOT
PRODUCTION PIPELINE IMPLEMENTATION`, and does not touch any `src/` package.

### Documentation Warnings

```text
DEPENDENCIES.md (FIXED this checkup): 2 stale "not implemented yet"
  annotations (python-dotenv, pytest) contradicted current working code
  and a 70-test passing suite; onnxruntime/psutil (added Task 0.10) were
  missing from the dependency table entirely. Corrected in place - no
  architecture change, docs-only, re-verified with a full doctor/portable/
  full test re-run afterward (still 70/70 passing).
project_plan/README.md: its 7-item reading order references
  REVIEW_RESOLUTIONS.md and FAILURES.md, neither of which exists yet.
  Not a Phase 0 defect - these are later-phase documents (design-problem
  and failure logs) that naturally don't exist before Phase 1 produces
  content for them - but flagged as broken links per this checkup's own
  instructions.
PROJECT_SPEC.md: "Position: end of week 1-2 of an ~8 week plan" and its
  "Not started" section predate Phase 0 and were already identified as
  stale by the Pre-Phase-0 Repository Baseline. Confirmed again here:
  this is pre-publication cleanup, not a Phase 0 correctness issue, and
  per this task's explicit instruction was not rewritten.
Root *.log files (stage1-5_*.log, phase1_data_audit.log): currently
  stageable under .gitignore. GIT_CONVENTIONS.md bans committing the
  `logs/` directory but does not explicitly address these root-level
  one-time data-acquisition provenance logs. Ambiguous - worth an
  explicit keep/exclude decision before the first commit rather than
  defaulting silently either way.
.tmp/ (2.6 GB): confirmed git-ignored and confirmed not to affect any
  test or benchmark. Contains historical DuckDB temp-spill files (from
  the Phase 1 audit memory-bug debugging) plus 4 now-superseded Task 0.10
  diagnostic scripts. Disk housekeeping only, explicitly not touched per
  this checkup's non-goals and Task 0.10's own instructions.
```

### Official Exit Gate

| Criterion (from `project_plan/PROJECT_EXECUTION.md`) | Status |
|---|---|
| A fresh terminal can activate the project environment | PASS |
| Python imports all core dependencies | PASS |
| PyTorch sees the GPU and can perform GPU computation | PASS |
| A sentence-transformer can embed sample text | PASS |
| DuckDB opens the local XBRL database | PASS |
| LanceDB can create/read a tiny test table | PASS |
| Configuration and storage roots load without hardcoded local-machine assumptions | PASS |
| Core smoke tests pass | PASS |
| Serving latency has been measured, not estimated | PASS |
| The serving target is chosen and the decision is recorded | PASS |

All 10/10 official Phase 0 exit criteria PASS.

### Remaining Issues

```text
BLOCKERS: none

WARNINGS:
  - 0 Git commits despite GIT_CONVENTIONS.md's explicit "commit now,
    before Phase 0" instruction (see Git Safety above)
  - root *.log files' commit status is undecided against
    GIT_CONVENTIONS.md's logs/ policy

DEFERRED / LATER-PHASE ITEMS:
  - PROJECT_SPEC.md staleness (position/not-started section) - known,
    pre-publication cleanup, not rewritten per instruction
  - README.md references to REVIEW_RESOLUTIONS.md/FAILURES.md, which are
    later-phase documents that don't exist yet
  - .tmp/ 2.6 GB of ignored disk waste - housekeeping, not correctness
  - S3 backend, actual cloud deployment, memory-tier reproduction -
    already correctly deferred to Phase 4/later per SERVING_FEASIBILITY.md
```

### Final Result

```text
WARN — Phase 0 complete with documented non-blocking issues
```

### Phase Status

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE WITH WARNINGS
  0.0 Git Safety Preflight        — COMPLETE (WARN: 0 commits - see above)
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE (doc fix applied this checkup)
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — COMPLETE
  0.8 Basic Automated Tests       — COMPLETE
  0.9 Developer Commands          — COMPLETE
  0.10 Serving Feasibility Spike  — COMPLETE
  Phase 0 Checkup                 — WARN

Phase 1 — Make It Work End to End — READY
```

No Git commit created. No Git push performed. No Phase 1 work started.

## 2026-08-27 — Phase 0 Git Checkpoint

### Objective

Resolves the final repository-process warning from the Phase 0 Checkup by
creating the repository's first honest version-control checkpoint. This is
a repository-hygiene task, not engineering work: Tasks 0.0–0.10 (and the
Phase 0 Checkup) were all completed and independently verified while the
repository had zero commits, per every task's own instruction to withhold
Git operations pending explicit approval. No retroactive per-task commits
are manufactured here — this creates one truthful checkpoint representing
"Phase 0 foundation complete," and from Phase 1 onward commits follow
`GIT_CONVENTIONS.md`'s per-subtask convention.

### Initial State

```text
branch:         main
commit count:   0
remote:         none configured
tags:           none
Phase 0 status: COMPLETE WITH WARNINGS (Phase 0 Checkup, 2026-08-26)
test status:    70/70 passing (last verified during Phase 0 Checkup)
Phase 1:        not started
```

### Root Log Policy

Root `*.log` files (`stage1_msmarco.log` ... `stage5_validate.log`,
`phase1_data_audit.log`) are local, generated, one-time data-acquisition
and audit run logs — not application runtime output, and not something
`GIT_CONVENTIONS.md`'s "commit configs/tests/planning docs, never commit
generated logs" stance was meant to include as trackable. Resolved in
favor of **not committing** them: added a root-level `*.log` rule to
`.gitignore` (with a comment explaining the resolution and pointing back
to the Phase 0 Checkup finding). The files remain on disk, untouched —
only their Git trackability changed. Verified live: `git check-ignore -v
stage1_msmarco.log` and `phase1_data_audit.log` both now match the new
`*.log` rule, while `Progress.md`, `DATA_READINESS_REPORT.md`,
`results/*.json`, `results/*.csv`, and `SERVING_FEASIBILITY.md` all remain
independently confirmed trackable.

### Safety Verification

```text
git add -n . result:        85 files (down from the Checkup's 90 - the 5
                             root *.log files are now correctly excluded)
stageable file count:        85
approximate total size:      0.88 MB
largest file:                 Progress.md, 122,299 bytes
secret scan result:           clean - one pattern match
                             (prompts/phase_0_Foundation/task_0.6_logging.md,
                             `api_key="abc123"`) inspected and confirmed to
                             be the task prompt's own fake-placeholder
                             redaction-testing example, not a real secret
ignored large/generated categories: data/*.duckdb, data/edgar_corpus/
                             *.parquet, artifacts/, .venv/, .tmp/, .env,
                             __pycache__/, .pytest_cache/, *.onnx,
                             *.safetensors, *.bin, *.log - all individually
                             re-verified live via git check-ignore, not
                             assumed from the previous checkup
```

### Foundation Verification

```text
doctor:            PASS
pip check:          No broken requirements found
portable tests:      66 passed, 4 deselected, 0 failed
smoke tests:         4 passed, 66 deselected, 0 failed
full tests:          70 passed, 0 failed, 0 skipped
```

Frozen-data lightweight invariants re-checked and unchanged:
`data/xbrl.duckdb` 7,011,053,568 bytes, 36 raw XBRL ZIPs, 990 primary
filings. Serving-spike provenance re-confirmed present and trackable
(`configs/serving_spike.json`, `results/phase_0_10_serving_spike.{json,csv}`,
`project_plan/SERVING_FEASIBILITY.md`); large benchmark artifacts under
`artifacts/serving_spike/` confirmed still git-ignored.

### Git History Decision

Tasks 0.0–0.10 and the Phase 0 Checkup were all completed before any Git
commit existed in this repository. No fake per-task commits were
reconstructed after the fact — doing so would misrepresent when the work
actually happened relative to review/verification. This task creates one
truthful Phase 0 snapshot commit instead. From Phase 1 onward, commits
will follow `GIT_CONVENTIONS.md` per-subtask granularity (commit when
something works, push at end of session, tag phase exits).

### Commit Plan

```text
Checkpoint Phase 0 foundation
```

### Tag Plan

```text
phase-0-complete (annotated)
```

### Remaining Warnings

```text
PROJECT_SPEC.md stale pre-Phase-0 wording (pre-publication cleanup, not
  rewritten - out of scope for this task per its own instruction)
project_plan/README.md references REVIEW_RESOLUTIONS.md/FAILURES.md,
  later-phase documents that don't exist yet (not created here - empty
  placeholders would be worse than the current honest absence)
.tmp/ (2.6 GB) ignored disk waste - untouched, disk housekeeping is a
  separate decision from Git correctness
no remote configured - push deferred, not attempted, no remote invented
```

### Result

```text
PASS — Phase 0 repository checkpoint committed and tagged
```

(Finalized after the commit and tag below were verified to succeed.)

### Phase Status

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — COMPLETE
  0.8 Basic Automated Tests       — COMPLETE
  0.9 Developer Commands          — COMPLETE
  0.10 Serving Feasibility Spike  — COMPLETE
  Phase 0 Checkup                 — COMPLETE WITH WARNINGS
  Phase 0 Git Checkpoint          — COMPLETE

Phase 1 — Make It Work End to End — READY
```

## 2026-08-27 — Phase 1.1 Select Development Corpus

### Objective

The first Phase 1 engineering task. Freezes the small, reproducible
1,500-filing development population that all remaining Phase 1 tasks
(1.2 normalization onward) will consume, per `PROJECT_EXECUTION.md`'s
"develop small, scale once" principle. This task selects filings; it does
not normalize, chunk, embed, or index them.

### Initial State

```text
Phase 0 checkpoint: aeba3b3, tag phase-0-complete - verified via
  git log --oneline --decorate -5 / git tag --list before starting
Phase 1: not previously implemented (all 13 Phase 1+ src/ packages still
  empty __init__.py; no development manifest existed)
doctor / test --portable: re-verified 0 failures before starting
  (66 passed, 4 deselected)
```

### Alignment Method

Reproduced independently from `src/ingest/audit_data.py`'s
`check2_10k_alignment()` (see `DATA_READINESS_REPORT.md`, "Check 2") rather
than inventing a new join:

- EDGAR fields: `cik`, `year`, `filename` (from
  `data/edgar_corpus/{train,test,validation}.parquet`, unioned).
- XBRL fields: `cik`, `form`, `fiscal_year` (`fy`), `adsh`, `name` (from
  `data/xbrl.duckdb` `submissions`, read-only).
- Join grain: `(cik, year)` — eligible if a `form='10-K'` XBRL submission
  for that `cik` has `fiscal_year == EDGAR year`.
- Form filter: XBRL `form = '10-K'` only (excludes 10-Q, 10-K/A, 20-F, etc).
- Year semantics: XBRL `fy` (the chosen semantic alignment field per the
  original audit — not the field that happened to maximize coverage).
- Type normalization: `TRY_CAST(cik AS BIGINT)` and
  `TRY_CAST(year AS INTEGER)` on the EDGAR side, explicit, no implicit
  coercion; 0 rows rejected in the real run.
- Duplicate handling: verified 0 EDGAR `(cik, year)` pairs map to more than
  one `filename` (EDGAR-CORPUS `filename` is exactly `{cik}_{year}.{ext}`,
  1:1 with `(cik, year)`). Found 29 `(cik, fy)` pairs in the 2016-2020
  window with more than one candidate XBRL 10-K `adsh` — no approved
  resolution rule existed anywhere in the repo, so **stopped and asked**
  before proceeding (see "User decisions" below).

### Eligible Population

```text
candidate denominator: 6,950
aligned population:     5,646
coverage:               81.24%
```

Reproduced exactly against the frozen authoritative figure, including the
identical per-year breakdown (2016: 1,454/1,197=82.32%, 2017:
1,409/1,145=81.26%, 2018: 1,377/1,126=81.77%, 2019: 1,339/1,066=79.61%,
2020: 1,371/1,112=81.11%). Independently re-run with a standalone DuckDB
query before writing any selection code, per the task's "validate before
selecting" requirement.

### User Decisions

Three genuine ambiguities where repository documentation did not resolve
the answer — stopped and asked before implementing, per the task's
explicit rule (did not silently pick a reasonable-looking answer):

1. **XBRL duplicate 10-K accessions** (29 of 5,646 aligned pairs): decided
   not to choose a canonical `adsh` at all — matches the audited Check-2
   methodology exactly (which only proves alignment `EXISTS`, never picks
   one). Each manifest row instead carries `xbrl_10k_candidate_count`.
2. **Selection rule**: PROJECT_EXECUTION.md requires "a deterministic seed
   or deterministic sampling rule" without specifying which, and no prior
   Phase 1 rule existed in the repo. Decided on Option A: SHA-256 over each
   eligible filing's `document_id` (EDGAR `filename`), ascending, first
   1,500. No seed, no PRNG/RNG-version dependency.
3. **Manifest location**: none of STORAGE.md/REPOSITORY_STRUCTURE.md/
   GIT_CONVENTIONS.md defined a location for this artifact type (it doesn't
   key off a `chunk_config_hash` like `artifacts/chunks/`/`indexes/` do).
   Decided on `results/phase_1_1_development_corpus.json`, tracked in Git,
   matching the existing `results/*.json` tracked-exception convention.

### Selection Rule

```text
method: SHA-256(document_id) ascending, first 1,500, no replacement
seed:   none (deterministic hash order, not a PRNG)
sort (storage): filings array canonically sorted by document_id ascending
  for readability - independent of, and does not affect, selection order
```

### Selected Corpus

```text
selected filings:     1,500
unique CIKs:           1,376
unique company names:  1,389 (informational only, from XBRL `name` - not
  EDGAR-CORPUS, which has no company-name field; not used as identity)
filings per CIK:        min=1  median=1.0  p95=2  max=3 (no pathological
  concentration)
development_manifest_sha256: d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b
```

| Year | Eligible | Eligible % | Selected | Selected % |
|---|---:|---:|---:|---:|
| 2016 | 1,197 | 21.20% | 332 | 22.13% |
| 2017 | 1,145 | 20.28% | 321 | 21.40% |
| 2018 | 1,126 | 19.94% | 288 | 19.20% |
| 2019 | 1,066 | 18.88% | 275 | 18.33% |
| 2020 | 1,112 | 19.70% | 284 | 18.93% |

No stratification applied (not specified by the project plan); mild drift
from the eligible-population year mix is expected unbiased sampling noise.

### Traceability

Manifest identity is EDGAR-CORPUS `filename` (e.g. `1005817_2016.htm`),
verified 1:1 with `(cik, year)` and stable under re-scan. 10 rows (2 per
year, 2016-2020) were manually traced: `document_id` → EDGAR source row
(`split`/`cik`/`year` match) → XBRL 10-K submission(s) with matching
`fiscal_year` — all 10/10 passed. Example:
`1005817_2016.htm` → EDGAR `(validation, cik=1005817, year=2016)` → XBRL
`adsh=0001005817-17-000004, form=10-K, fiscal_year=2016, name='TOMPKINS
FINANCIAL CORP'`.

**Accession limitation, stated explicitly**: EDGAR-CORPUS carries no
accession-number field and none can be reliably reconstructed from it. No
EDGAR accession is fabricated anywhere in the manifest or its generating
code; XBRL `adsh` is recorded only as alignment evidence
(`xbrl_10k_candidate_count`), never labeled as "the EDGAR accession."

### Files Created / Modified

```text
scripts/select_development_corpus.py       (new)
results/phase_1_1_development_corpus.json  (new, tracked)
tests/test_select_development_corpus.py    (new, 17 tests)
project_plan/PHASE1_DEVELOPMENT_CORPUS.md  (new)
Progress.md                                 (this entry)
```

No `src/ingest/` file modified. No dependency files modified — stdlib +
`duckdb` only, both already present.

### Verification

```text
determinism:          PASS - re-ran in a fresh process; identical
  development_manifest_sha256; only the non-hashed `created_at_utc`
  provenance field differed between runs
manual traceability:   PASS - 10/10 sampled rows (2 per year, 2016-2020)
tests:                  17 new tests (selection_hash, select_top_n,
  canonical_sort, manifest_checksum, distribution stats), all passing;
  full suite 70 -> 87
doctor:                 PASS
portable suite:         83 passed, 4 deselected, 0 failed
full suite:              87 passed, 0 failed, 0 skipped
frozen-data invariants:  unchanged - xbrl.duckdb 7,011,053,568 bytes,
  36 raw XBRL ZIPs, 990 primary filings, edgar_corpus 3 parquet files
  (identical before/after)
```

### Git

```text
git status --short before commit: only 4 new untracked files (the prompt
  file, the manifest, the script, the test file) - 0 data/artifacts/venv
  content stageable
secret scan:            clean (no api_key/password/secret/bearer/SEC email
  patterns found in any new file)
```

Committed as one coherent Task 1.1 commit: "Select reproducible Phase 1
development corpus". No remote configured — push deferred, not attempted.

### Result

```text
PASS — 1,500-filing Phase 1 development corpus selected reproducibly
```

### Phase Status

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
Phase 1 — Make It Work End to End — IN PROGRESS
  1.1 Select Development Corpus   — COMPLETE
  1.2 Minimal Normalization       — NEXT
```

## 2026-08-27 — Phase 1.2 Minimal Document Normalization

### Objective

Converts the frozen 1,500-document Task 1.1 corpus into the first
deterministic Markdown representation consumed by Task 1.3's fixed-window
chunker. Whole normalized filings only - no tokenization, chunking,
embedding, or indexing.

### Initial State

```text
Task 1.1 commit: c776998, manifest results/phase_1_1_development_corpus.json,
  development_manifest_sha256:
  d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b
  1,500 selected filings, verified via `git log --oneline --decorate -5` /
  `git tag --list` before starting
src/normalize/: empty __init__.py, no normalizer previously implemented
doctor / test --portable: re-verified 0 failures before starting
  (83 passed, 4 deselected)
```

### Input Verification

```text
manifest row count:                1,500
unique document_id:                 1,500
recomputed development_manifest_sha256:
  d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b - MATCH
source rows resolved:                1,500 / 1,500
identity mismatches (split/cik/year):  0
```

Recomputed independently via Task 1.1's documented procedure, not trusted
from the value stored inside the file.

### Normalization Contract

```text
CRLF/CR -> \n
leading/trailing whitespace stripped per section
null/empty/whitespace-only sections omitted (no heading, no body)
Markdown item headings: "## Item {N|N-letter}" - exact SEC item id from the
  source column name, no invented titles
YAML frontmatter, fixed key order, JSON-escaped string values (stdlib json,
  no new dependency)
UTF-8, exactly one trailing newline per file
```

No LLM rewriting, semantic cleaning, OCR, boilerplate removal, table
reconstruction, or any other advanced transformation - conservative
normalization only, per the task's explicit non-goals.

**Section order**: taken directly from the source parquet's own column
order (verified via DuckDB schema inspection), which is already natural
SEC Item order - no reordering logic needed.

**7 known-empty filings** (all 20 section_* columns present but
empty-string in EDGAR-CORPUS itself - verified against live data, not a
bug): 18498_2018.htm (GENESCO), 1324424_2018.htm (EXPEDIA GROUP),
71691_2016.htm (NEW YORK TIMES), 1388410_2016.htm and 1388410_2018.htm
(PARALLAX HEALTH SCIENCES, both years), 883241_2017.htm (SYNOPSYS),
1110803_2019.htm (ILLUMINA). **Stopped and asked** before deciding how to
handle these, since the Task 1.1 manifest is frozen and none of the
existing rules covered this case. **User-approved**: normalize as
frontmatter-only documents (empty body, zero Item headings) - an explicit,
documented exception to the "at least one heading" output check, rather
than dropping/replacing/substituting a frozen manifest row.

### Metadata Contract

Frontmatter keys (fixed order): `cik`, `company`, `form_type`,
`fiscal_year`, `source`, `source_filename`, `document_id`, `source_split`,
`development_manifest_sha256`. `company` is XBRL-sourced provenance (via
the Task 1.1 manifest), present for all 1,500 rows - not from EDGAR-CORPUS,
which has no company-name field.

```text
fabricated accession fields: NONE
```

### User Decisions

Two genuine ambiguities where repository documentation did not resolve the
answer - stopped and asked before implementing:

1. **Normalizer version**: `src/storage.py`'s `normalized_dir(version)` was
   a path helper only - Task 0.7 never picked a value, and no normalizer
   existed until now. Decided on `v1`.
2. **7 known-empty filings**: decided on frontmatter-only documents (see
   above), not dropping, substituting, or reopening Task 1.1's manifest.

### Output

```text
normalizer_version:                v1
generated artifact path:            artifacts/normalized/v1/ (git-ignored)
Markdown document count:             1,500
total normalized size:               430,712,686 bytes (~410.8 MiB)
normalization_build_sha256:          fd0abad26111412d792033373e02a0a6a3fb1d0d7a47dbad6063e98c2272244b
```

### Corpus Statistics

```text
character count:        min=282  median=271,065  p95=543,714  max=2,364,857
non-empty sections:      min=0  median=20  p95=20  max=20
known-empty documents:   7
```

Per-section presence ranges 93.93% (Item 11) to 99.00% (Item 3/5) across
the selected 1,500 - materially higher than the full EDGAR-CORPUS
population's rates in `DATA_READINESS_REPORT.md` (e.g. Item 1A 25.6%
overall vs 94.67% here), because the 2016-2020 XBRL-aligned selection skews
toward larger, more completely-scraped filers.

### Determinism

```text
run 1 normalization_build_sha256: fd0abad26111412d792033373e02a0a6a3fb1d0d7a47dbad6063e98c2272244b
run 2 normalization_build_sha256: fd0abad26111412d792033373e02a0a6a3fb1d0d7a47dbad6063e98c2272244b
identical: YES (file count, filenames, and byte content all verified
  identical via `diff -rq` on both output directories, in addition to the
  checksum match)
```

### Manual Inspection

11 documents traced (2 per year, 2016-2020, plus one known-empty filing)
through the full chain: Task 1.1 manifest row -> raw EDGAR-CORPUS source
row -> normalized Markdown. All 11/11 passed, including one sparse case
(1004702_2020.md, 16/20 sections present, missing Item 1/1A) and the
known-empty case (18498_2018.md, 0 body characters, 0 headings, valid
frontmatter, matching the approved policy exactly).

### Tests

```text
new Task 1.2 tests:  30 (section ordering, empty-section omission,
  multiline/Unicode/CRLF preservation, safe YAML quoting, frontmatter key
  order, output filename mapping, normalization_build_sha256 determinism)
doctor:              PASS
portable suite:       113 passed, 4 deselected, 0 failed
full suite:            117 passed, 0 failed, 0 skipped (was 87)
```

### Frozen Data

```text
data/xbrl.duckdb:      7,011,053,568 bytes - unchanged
raw XBRL ZIPs:           36 - unchanged
primary filings:          990 - unchanged
EDGAR Parquet files:       3 - unchanged
```

### Files Created / Modified

```text
src/normalize/edgar_markdown.py                  (new)
scripts/normalize_development_corpus.py          (new)
configs/normalize_development_corpus.json        (new, tracked)
results/phase_1_2_normalization_summary.json     (new, tracked)
tests/test_document_normalization.py              (new, 30 tests)
project_plan/PHASE1_NORMALIZATION.md              (new)
project_plan/REPOSITORY_STRUCTURE.md              (updated: src/normalize/
  marked implemented, configs/ and scripts/ listings updated)
Progress.md                                        (this entry)
```

1,500 generated `.md` files under `artifacts/normalized/v1/` are git-ignored
and not listed individually. No `src/ingest/` file modified. No dependency
files modified - stdlib + `duckdb` only, both already present.

### Git

```text
git status --short before commit: 6 new untracked tracked-worthy files
  (prompt, module, script, config, summary, tests) plus doc updates - 0
  artifacts/data/venv content stageable (confirmed via git status --ignored)
secret scan:            clean (no api_key/password/secret/bearer/SEC email/
  personal-path patterns found in any new file)
```

Committed as one coherent Task 1.2 commit: "Add minimal Markdown
normalization". No remote configured - push deferred, not attempted.

### Result

```text
PASS — 1,500 development filings normalized deterministically to Markdown
```

### Phase Status

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
Phase 1 — Make It Work End to End — IN PROGRESS
  1.1 Select Development Corpus   — COMPLETE
  1.2 Minimal Normalization       — COMPLETE
  1.3 Fixed-Window Chunker        — NEXT
```

## 2026-08-27 — Phase 1.2 Correction: normalizer_version renamed v1 -> phase1-minimal-v1

### Objective

Before starting Task 1.3, a Task 1.3 task prompt arrived asserting "The
normalizer-version correction is explicitly approved:
`normalizer_version = phase1-minimal-v1`" and that the repository must not
use the previously implemented `v1` location. This did not match the
actual recorded Task 1.2 decision: Task 1.2's own version-naming question
offered `"phase1-minimal-v1 (Recommended)"` as an option, but the answer
actually given and built at the time was `"v1"`. Flagged this discrepancy
directly rather than silently complying with an unrecorded "approval," per
the standing rule against acting on claims that contradict the actual
conversation record. Asked for clarification: real new decision, or a
stale/incorrect task file? **Confirmed: real new decision** - the user
does want the rename. This entry records that correction, applied
mechanically before any Task 1.3 code was written.

### What Changed

```text
normalizer_version:  "v1"  ->  "phase1-minimal-v1"
artifact path:         artifacts/normalized/v1/  ->  artifacts/normalized/phase1-minimal-v1/
```

`normalizer_version` was never part of any normalized document's YAML
frontmatter or filename (confirmed via `src/normalize/edgar_markdown.py`'s
`FRONTMATTER_KEYS` and `output_filename()`), so this is purely a
location/provenance rename - no document byte changed.

### Steps Taken

1. Updated `NORMALIZER_VERSION` constant in
   `scripts/normalize_development_corpus.py` (`"v1"` -> `"phase1-minimal-v1"`).
2. Re-ran the build: wrote 1,500 documents to the new
   `artifacts/normalized/phase1-minimal-v1/` location, regenerated
   `configs/normalize_development_corpus.json` and
   `results/phase_1_2_normalization_summary.json` with the corrected
   version string.
3. Verified `normalization_build_sha256` unchanged:
   `fd0abad26111412d792033373e02a0a6a3fb1d0d7a47dbad6063e98c2272244b` before
   and after - confirms the content is identical, only the path/label moved.
4. Byte-diffed the old `artifacts/normalized/v1/` against the new
   `artifacts/normalized/phase1-minimal-v1/` directory (`diff -rq`, 0
   differences) before deleting the old, now-orphaned `v1/` directory
   (git-ignored generated state created this session - safe to remove).
5. Re-ran the build a second time to reverify determinism/idempotency at
   the corrected location: identical `normalization_build_sha256`.
6. Updated `project_plan/PHASE1_NORMALIZATION.md`'s `v1` references
   (artifact path, output-location section) to `phase1-minimal-v1`, with an
   explicit correction note explaining what changed and why.

### Verification

```text
normalization_build_sha256 (before and after): fd0abad26111412d792033373e02a0a6a3fb1d0d7a47dbad6063e98c2272244b
old vs new artifact directory diff:              0 differences (diff -rq)
document count at corrected location:            1,500
config normalizer_version:                        phase1-minimal-v1
summary normalizer_version:                        phase1-minimal-v1
```

### Files Modified

```text
scripts/normalize_development_corpus.py       (NORMALIZER_VERSION constant + docstring)
configs/normalize_development_corpus.json     (regenerated by rerun)
results/phase_1_2_normalization_summary.json  (regenerated by rerun)
project_plan/PHASE1_NORMALIZATION.md          (v1 -> phase1-minimal-v1 references + correction note)
Progress.md                                    (this entry)
```

`artifacts/normalized/v1/` (git-ignored) deleted;
`artifacts/normalized/phase1-minimal-v1/` (git-ignored) is now the sole
normalized-corpus location.

### Result

```text
PASS — normalizer_version corrected to phase1-minimal-v1, verified
  byte-identical to the prior v1 build, ready for Task 1.3
```

Committed separately as its own commit (`b0162fe`), per Task 1.3's own hard
precondition requiring the corrected Task 1.2 state be committed and the
working tree clean before chunking begins.

## 2026-08-28 — Phase 1.3 Minimal Fixed-Window Chunker

### Objective

Splits each of the 1,500 corrected Task 1.2 normalized documents into
deterministic 512-token fixed windows and persists them as Parquet - the
chunk artifact Task 1.4's baseline embedding pipeline will consume.

### Initial State

```text
Task 1.2 correction commit: b0162fe, verified clean before starting
normalizer_version:          phase1-minimal-v1 (confirmed in config/summary)
normalized document count:    1,500
src/chunk/: empty __init__.py, no chunker previously implemented
```

An unexplained working-tree change to `Progress.md` (a broken
`<actual message>` placeholder fragment, not real content) was found and
discarded (`git checkout -- Progress.md`) before starting - see the note in
this session's transcript. Working tree was clean before Task 1.3 began.

### Task 1.2 Corrected Provenance

```text
normalizer_version:               phase1-minimal-v1 - verified in config
  and summary
normalization_build_sha256:        fd0abad26111412d792033373e02a0a6a3fb1d0d7a47dbad6063e98c2272244b
  - independently recomputed from the live artifacts/normalized/
  phase1-minimal-v1/*.md files (not trusted from the stored value), matches
development_manifest_sha256:        d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b
  - independently recomputed from results/phase_1_1_development_corpus.json
```

### User Decisions

Ten genuine chunking-semantics ambiguities, none resolved by existing docs
- stopped and asked before implementing, in three batches:

1. **Tokenizer**: `BAAI/bge-small-en-v1.5`'s tokenizer (matches Task 1.4's
   embedding model; window_size=512 matches its context length per
   `PROJECT_SPEC.md`'s model table, but this was never stated explicitly
   for Task 1.3, so it was confirmed rather than assumed).
2. **Overlap/stride**: zero overlap (`stride=512`).
3. **Partial final window**: kept, never dropped/merged.
4. **What gets chunked**: body only; frontmatter parsed into metadata.
5. **Special-token counting**: 512 content tokens only
   (`add_special_tokens=False`).
6. **Text preservation**: offset-mapping slicing (exact source substrings),
   not token-id decode.
7. **7 empty-source documents**: 0 chunks each, approved exception.
8. **Parquet layout**: single file.
9. **Chunk schema**: full traceability set (16 columns).
10. **Chunk ID / ordinal**: `{document_id}::chunk{ordinal}`, zero-based.

### Tokenizer Contract

```text
repository:    BAAI/bge-small-en-v1.5
revision:       5c38ec7c405ec4b44b94cc5a9bb96e735b38267a (cached, Task 0.2)
offline:         HF_HUB_OFFLINE=1 + local_files_only=True + explicit
                try_to_load_from_cache() precheck per required asset file
                before load - BLOCKED (not a silent download) if missing
fast tokenizer:   verified (tokenizer.is_fast == True) - required for
                return_offsets_mapping
special tokens:   add_special_tokens=False
```

### Chunking Contract

```text
window_size_tokens:      512
stride_tokens:             512 (overlap_tokens = 0)
partial_window_policy:      keep
frontmatter_body_policy:     body_only_frontmatter_to_metadata
heading_behavior:             Item headings are ordinary body text, never
                              treated specially, never duplicated/stripped
decode_offset_policy:          offset_mapping_slicing
```

Text preservation verified empirically on a synthetic Unicode/punctuation
sample before the real build: offset-mapping slicing reconstructs the
original text exactly except for pure-whitespace runs between tokens
(confirmed once, documented as a known limitation, never real content
loss). Window generation verified exhaustive/non-overlapping by unit test
(`test_windows_cover_every_token_exactly_once_with_zero_overlap`).

### Chunk Schema

16 columns: `chunk_id`, `document_id`, `cik` (int64), `company`,
`form_type`, `fiscal_year` (int32), `source`, `source_filename`,
`source_split`, `ordinal` (int32), `text`, `token_count` (int32),
`chunk_config_hash`, `normalizer_version`, `normalization_build_sha256`,
`development_manifest_sha256`. Explicitly a **Phase 1 baseline schema**,
not the later Phase 2 frozen chunk schema (`PROJECT_EXECUTION.md` Task
2.9) - stated plainly in `PHASE1_CHUNKING.md`, not silently promoted.

### Chunk ID Contract

```text
chunk_id:   "{document_id}::chunk{ordinal}", e.g. "1005817_2016.htm::chunk0"
ordinal:     zero-based, sequential per document
```

### chunk_config_hash

```text
algorithm: SHA-256 over canonical JSON (sort_keys, no whitespace) of the
  chunk config dict - the same convention already established by Task
  1.1's development_manifest_sha256 and Task 1.2's
  normalization_build_sha256, deliberately reused rather than invented
chunk_config_hash (real build): f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
```

### Output / Parquet Layout

```text
artifact path:  artifacts/chunks/f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd/chunks.parquet
layout:           single Parquet file
size:              190,631,710 bytes (~181.8 MiB)
```

### Chunk Statistics

```text
chunk count:               162,357
documents with chunks:      1,493
documents without chunks:      7 (approved empty-source set, exact match)

chunks/document:  min=1  median=103  p95=208  max=869
tokens/chunk:      min=1  median=512  p95=512  max=512

full (512-token) chunks:  160,872
partial chunks:               1,485
total emitted tokens:       82,748,156
build runtime:                ~182-199s (two independent runs)
```

The `tokens/chunk` min of 1 (chunk_id `27673_2016.htm::chunk69`, text
`"."`) was inspected directly and confirmed genuine - a document's final
partial window landing on a single trailing token, not a bug.

### Empty-Source Handling

Same 7 documents from Task 1.2 produce exactly 0 chunks each: 18498_2018.htm,
1324424_2018.htm, 71691_2016.htm, 1388410_2016.htm, 1388410_2018.htm,
883241_2017.htm, 1110803_2019.htm. Falls out naturally from
`compute_token_windows(0, ...)` returning `[]` - no special-casing needed
in the windowing logic. The build script separately cross-checks the
zero-chunk document set against this exact approved list.

### Determinism

```text
run 1 chunk_config_hash: f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
run 2 chunk_config_hash: f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
logical dataset identical: YES (162,357 rows both runs; SHA-256 over the
  newline-joined chunk_id column identical; SHA-256 over the NUL-joined
  text column identical)
chunk IDs identical: YES
```

### Manual Inspection

11 documents traced (2 per year 2016-2020, one known-sparse
[1004702_2020.htm, first heading correctly `## Item 1B` since Item 1/1A
were empty], one known-empty [18498_2018.htm, confirmed 0 chunks]) from
normalized Markdown through to their chunks. All 11/11 passed - correct
metadata, correct chunk counts, first/last chunk boundaries as expected. A
token-boundary continuity check on one document confirmed exact, gap-free
text coverage across a chunk boundary (`"...polyole"` + `"fin-based..."` =
`"polyolefin-based"` - a genuine mid-word split, no character lost or
duplicated).

### Tests

```text
new Task 1.3 tests:  27 (window computation, text slicing, chunk ID,
  frontmatter/body parsing round-trip, chunk_config_hash determinism,
  normalization_build_sha256 helper) - tiny synthetic fixtures, no real
  tokenizer or full-corpus build inside pytest
doctor:              PASS
portable suite:       140 passed, 4 deselected, 0 failed
full suite:            144 passed, 0 failed, 0 skipped (was 117)
```

### Safety

```text
data/ unchanged:                     xbrl.duckdb 7,011,053,568 bytes, 36
                                     raw XBRL ZIPs, 990 primary filings, 3
                                     EDGAR parquet files - all identical
normalized Markdown unchanged:         1,500 files, normalization_build_sha256
                                     re-verified identical
                                     (fd0abad2...2244b) after the build
no network downloads:                  tokenizer loaded offline from cache
                                     only, precheck-guarded
no embeddings created:                  confirmed - tokenizer/text-processing
                                     only
no index created:                        confirmed
```

### Files Created / Modified

```text
src/chunk/fixed_window.py                  (new)
scripts/chunk_development_corpus.py        (new)
configs/chunk_development_corpus.json       (new, tracked)
results/phase_1_3_chunking_summary.json     (new, tracked)
tests/test_fixed_window_chunker.py           (new, 27 tests)
project_plan/PHASE1_CHUNKING.md               (new)
project_plan/REPOSITORY_STRUCTURE.md           (updated: src/chunk/ marked
  implemented, configs/ and scripts/ listings updated)
Progress.md                                     (this entry; also corrected
  a stale closing sentence in the prior Phase 1.2 Correction entry that no
  longer matched reality after that correction was committed separately)
```

162,357-row `chunks.parquet` under `artifacts/chunks/<hash>/` is
git-ignored and not listed individually. No `src/normalize/`, `src/ingest/`,
or normalized Markdown file modified. No dependency files modified -
`transformers`/`huggingface_hub`/`pyarrow` already present.

### Git

```text
git status --short before commit: 6 new untracked tracked-worthy files
  (prompt, module, script, config, summary, tests) plus doc updates - 0
  artifacts/data/venv content stageable
secret scan:            clean
```

Committed as one coherent Task 1.3 commit: "Add minimal fixed-window
chunker". No remote configured - push deferred, not attempted.

### Result

```text
PASS — Phase 1 development corpus chunked deterministically into 512-token fixed windows
```

### Phase Status

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE
  1.3 Minimal Fixed-Window Chunker — COMPLETE
  1.4 Baseline Embedding Pipeline  — NEXT
```

## 2026-08-28 — Phase 1.4 Baseline Embedding Pipeline

### Objective

Converts all 162,357 Task 1.3 fixed-window chunks into 384-dimensional
BAAI/bge-small-en-v1.5 dense vectors on GPU - the embedding artifact Task
1.5's LanceDB vector-only index will consume.

### Initial State

```text
Task 1.3 commit: 3c30baf
chunk_config_hash:  f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
chunk artifact:       artifacts/chunks/f1dc04d4.../chunks.parquet
input row count:       162,357 - verified: unique chunk_id 162,357, single
                       chunk_config_hash value, 0 empty text rows
src/embeddings/: empty __init__.py, no embedding pipeline previously
  implemented
```

### User Decisions / Clarifications

Two conventions resolved by direct inspection of the cached model's own
README (an authoritative source per the task's own rule), not assumed or
asked about:

1. **Passage convention**: raw text, no instruction - "no instruction
   needs to be added to passages" (model card).
2. **Query convention** + **normalize_embeddings**: prepend `"Represent
   this sentence for searching relevant passages: "` to queries;
   `normalize_embeddings=True` for both - both directly from the model
   card's own documented usage example, not sentence-transformers'
   library default (which is `normalize_embeddings=False`).

Six further ambiguities with no resolution anywhere in the repo - asked
before implementing:

3. **Vector dtype**: `float32`.
4. **GPU batch size**: `128`.
5. **Precision policy**: full FP32, no autocast.
6. **OOM fallback**: halve batch size, retry, record actual batch size(s)
   used (never triggered - build completed at batch_size=128 throughout).
7. **Artifact location**: new `storage.embeddings_dir(chunk_config_hash,
   embedding_model)`, mirroring `index_dir`'s existing compound-key
   pattern.
8. **Artifact format / metadata policy**: single self-contained Parquet
   file, all 16 Task 1.3 chunk columns + a `vector` column.

### Model Contract

```text
model repository:     BAAI/bge-small-en-v1.5
resolved revision:      5c38ec7c405ec4b44b94cc5a9bb96e735b38267a (same
                        cached snapshot as Task 1.3's tokenizer - only one
                        cached revision existed, unambiguous)
dimension:               384 (verified via model.get_embedding_dimension())
sentence-transformers:    6.0.0
torch:                     2.13.0+cu130 / CUDA 13.0
GPU:                        NVIDIA GeForce RTX 5060 Laptop GPU
```

### Query / Passage Contract

`src/embeddings/bge.py` exposes genuinely separate `encode_passages()` /
`encode_queries()` functions (not a flag on one call site). Verified
directly that the same text embedded via each path produces measurably
different vectors. The real 162,357-chunk build used only
`encode_passages()`; a query-path smoke test (offline, `model`+`gpu`
marked) verifies the future Task 1.6 query path without performing
retrieval.

### Vector Contract

```text
normalize_embeddings:  True
vector_dtype:            float32
dimension:                384
```

Verified across the full artifact: all finite, every norm within `1e-6` of
`1.0` (measured min 0.9999999, max 1.0000001).

### Build Configuration

```text
device:              cuda (verified via model parameter device; would raise
                     rather than silently fall back to CPU)
batch_size:            128 (no OOM - batch_sizes_used == [128] throughout)
precision_policy:       full FP32, no autocast
offline/cache policy:    HF_HUB_OFFLINE=1 + local_files_only=True + explicit
                     per-file try_to_load_from_cache() precheck across 10
                     required model assets before construction
```

### Output

```text
artifact location:  artifacts/embeddings/f1dc04d4.../BAAI--bge-small-en-v1.5/embeddings.parquet
format:               single Parquet file - all 16 chunk columns +
                     vector: fixed_size_list<float32>[384]
metadata policy:        full self-contained copy, verified column-for-column
                     identical to chunks.parquet across all 162,357 rows
vector count:            162,357
artifact size:            440,703,576 bytes (~420.3 MiB)
```

`storage.embeddings_dir(chunk_config_hash, embedding_model)` added to
`src/storage.py` as a new, narrow helper mirroring `index_dir`'s existing
compound-key pattern, covered by 3 new tests.

### Performance

```text
model load:            3.66s
embedding inference:      1154.74s (~19.2 min)
artifact write:              1.50s
total wall time:              1161.47s (~19.4 min)
chunks/sec:                     140.6
tokens/sec:                       71,659.9 (82,748,156 Task 1.3 tokens /
                                embedding_inference_seconds)
peak VRAM allocated:               1,411,858,944 bytes (~1.41 GB)
peak VRAM reserved:                  1,962,934,272 bytes (~1.96 GB)
```

Not Task 0.2's tiny 40-sentence smoke throughput - measured against the
real 162,357-chunk corpus.

### Validation

```text
row count:                162,357 output vectors for 162,357 input chunks
unique chunk IDs:            162,357, no missing/duplicate/extra
dimensions:                    384, verified for every vector
finite values:                   verified, full corpus (not sampled)
dtype:                             float32, verified via native PyArrow ->
                                NumPy conversion (a first check via
                                .to_pylist() falsely read float64 due to
                                Python-object boxing - caught and corrected
                                before trusting it)
normalization:                     norms within 1e-6 of 1.0, full corpus
metadata traceability:               all 16 columns compared full-corpus
                                against chunks.parquet - exact match, plus
                                chunk_id row order confirmed identical
                                (index-aligned, not just set-equal)
```

### Manual Inspection

6 rows inspected: first chunk overall, the single-token chunk found in
Task 1.3 (`27673_2016.htm::chunk69`), a long document's final partial
chunk (`1005817_2016.htm::chunk143`), first chunks from 2017/2018/2020
documents, and the artifact's last row. All 6/6 correct metadata, shape,
finite values, unit norm.

### Repeat / Numeric-Stability Check

Fresh process re-encoded the first 20 chunk_ids independently:

```text
same model revision/config/chunk IDs/order: YES
shape/dtype match:                             YES
max abs difference:                               2.98e-08
tolerance used:                                     1e-5 (justified: GPU
  inference isn't claimed bit-identical across runs, but measured deviation
  here is within float32 machine epsilon)
result: PASS
```

### Tests

```text
new Task 1.4 tests:  16 (12 in test_baseline_embeddings.py including 1
  model+gpu-marked offline integration test, 4 new storage tests for
  embeddings_dir())
doctor:              PASS
portable suite:       155 passed, 5 deselected, 0 failed
full suite:            160 passed, 0 failed, 0 skipped (was 144)
```

### Safety

```text
chunks.parquet unchanged:      confirmed - metadata comparison against
  embeddings.parquet matched exactly, file opened read-only
normalized Markdown unchanged:    normalization_build_sha256 re-verified
  identical (fd0abad2...2244b)
data/ unchanged:                    xbrl.duckdb 7,011,053,568 bytes, 36 raw
  XBRL ZIPs, 990 primary filings - all identical
no network download:                  offline guarantee held throughout
embedding artifact ignored by Git:      confirmed via git status --ignored
no LanceDB index created:                 confirmed
no retrieval implemented:                   confirmed
```

### Files Created / Modified

```text
src/embeddings/bge.py                      (new)
scripts/embed_development_corpus.py        (new)
configs/embed_development_corpus.json      (new, tracked)
results/phase_1_4_embedding_summary.json   (new, tracked)
tests/test_baseline_embeddings.py           (new, 12 tests)
src/storage.py                               (modified: added
  embeddings_dir(chunk_config_hash, embedding_model))
tests/test_storage.py                          (modified: 3 new tests for
  embeddings_dir())
project_plan/PHASE1_EMBEDDINGS.md               (new)
project_plan/REPOSITORY_STRUCTURE.md              (updated: src/embeddings/
  marked implemented, configs/ and scripts/ listings updated)
Progress.md                                        (this entry)
```

440,703,576-byte `embeddings.parquet` under `artifacts/embeddings/<hash>/`
is git-ignored and not listed individually. No `src/chunk/`,
`src/normalize/`, `src/ingest/`, chunks.parquet, normalized Markdown, or
frozen `data/` modified. No new dependency added -
`sentence-transformers`/`torch`/`pyarrow`/`huggingface_hub` already
present.

### Git

```text
git status --short before commit: 8 new/modified tracked-worthy files - 0
  artifacts/data/venv content stageable (confirmed via git status --ignored)
secret scan:            clean
```

Committed as one coherent Task 1.4 commit: "Add baseline BGE embedding
pipeline". No remote configured - push deferred, not attempted.

### Result

```text
PASS — baseline BGE embeddings generated for all Phase 1 chunks
```

### Phase Status

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE
  1.3 Minimal Fixed-Window Chunker — COMPLETE
  1.4 Baseline Embedding Pipeline  — COMPLETE
  1.5 Vector-Only Index            — NEXT
```

## 2026-08-28 — Phase 1.5 Vector-Only Index

### Objective

Creates the first exact LanceDB cosine-search table over all 162,357 Task
1.4 embeddings - the queryable vector store Task 1.6's baseline retriever
will use.

### Initial State

```text
Task 1.4 commit: 6cd0b36
embedding artifact: artifacts/embeddings/f1dc04d4.../BAAI--bge-small-en-v1.5/embeddings.parquet
chunk_config_hash:    f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
embedding model/revision: BAAI/bge-small-en-v1.5 / 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
embedding row count:        162,357 - independently re-verified before
  starting (unique chunk_id 162,357, single chunk_config_hash, vector
  fixed_size_list<float32>[384], all finite)
```

### Frozen User Decisions

The task prompt arrived with four decisions marked "explicitly resolved
before this prompt was drafted": plain LanceDB table / exact search,
cosine metric, all 17 columns retained, table name `chunks`. Unlike Task
1.3's earlier false-approval incident, nothing in the repository
contradicted these (no prior Task 1.5 artifact existed to disagree with),
so they were accepted as given, per the task's own "do not ask again
unless the repository materially contradicts them" instruction.

```text
index type:     plain table / exact search
metric:            cosine
table columns:        all 17
table name:              chunks
```

### Backend / Storage

```text
LanceDB version:  0.37.1 (matches pinned requirement)
database path:      artifacts/indexes/f1dc04d4.../BAAI--bge-small-en-v1.5/
table name:            chunks
```

Built via `src.storage.get_storage().index_dir(chunk_config_hash,
embedding_model)` - the existing Task 0.7 contract, no new path
convention. No separate index-config hash introduced - the existing
`(chunk_config_hash, embedding_model)` compound key already captures
everything that affects index content for Phase 1.

### LanceDB API Verification

Before touching real data, a tiny synthetic 4-vector table (identical,
near-duplicate, orthogonal, opposite) was built and queried to verify
actual installed 0.37.1 behavior:

```text
same-as-query -> _distance 0.0
near-duplicate -> _distance ~0.006
orthogonal -> _distance 1.0
opposite -> _distance 2.0
```

Confirmed: lower `_distance` = more similar; `.distance_type("cosine")`
(current API, `.metric()` is a deprecated alias) must be called
explicitly - untouched default is `"l2"`. `lancedb.connect(path)` uses
`path` directly as the database root, no nested subdirectory.
`create_table()` creates zero ANN indexes automatically
(`list_indices() == []`) - exact search is simply the absence of
`.create_index()`, never called anywhere in this codebase.

### Search Contract

```text
mode:          exact (no ANN index on the table)
metric:           cosine, requested explicitly via .distance_type("cosine")
distance field:      _distance (LanceDB's own name, never renamed to "score")
ranking:                lower _distance = more similar
ANN index count:          0
```

### Table Schema

17 columns exactly as produced by Task 1.4: `chunk_id`, `document_id`,
`cik` (int64), `company`, `form_type`, `fiscal_year` (int32), `source`,
`source_filename`, `source_split`, `ordinal` (int32), `text`,
`token_count` (int32), `chunk_config_hash`, `normalizer_version`,
`normalization_build_sha256`, `development_manifest_sha256`,
`vector` (fixed_size_list<float32>[384]).

### Build

```text
input rows:      162,357
table rows:         162,357
build runtime:        8.94s (first build), 6.72s (idempotent-reuse rerun -
  detected existing table with correct row count, skipped re-ingestion)
database size:          493,178,075 bytes (~470.3 MiB)
ANN indexes created:       0
```

### Validation

```text
row-count match:        162,357 == 162,357
chunk-ID uniqueness:       162,357 unique, no duplicates
metadata equality:           full corpus (not sampled), all 16 non-vector
  columns, chunk_id-keyed (not physical row order): exact match
vector dimension/dtype:        384, float32 - verified via native PyArrow
  -> NumPy conversion (not Python-object boxing)
finite vectors:                  verified
stored-vs-source vectors:          200-row deterministic sample, 200/200
  exact bit-for-bit matches, max abs diff 0.0 - LanceDB preserves float32
  exactly, no precision loss
```

Physical row order not relied upon anywhere - every comparison keyed by
`chunk_id`.

### Self-Retrieval

```text
real vectors tested:      40 (deterministic, evenly spaced across the
  full corpus)
same chunk at rank 1:        40/40
anomalies:                       none
self-distance range:               min -1.19e-07, max 0.0
```

The tiny negative self-distance is a float32 rounding artifact of
`1 - cosine_similarity` on a self-comparison - not a bug, far below any
meaningful tolerance, and noted explicitly rather than silently accepted.

### Search Diagnostics

```text
label:          Phase 1 smoke diagnostic - not a production benchmark
query count:       50 (+5 unmeasured warm-up)
top-k:                5 (reused PROJECT_EXECUTION.md's already-frozen
                    "top-5 context for generation" constant, not a new
                    contract invented for this diagnostic)
p50:                   ~143-154 ms (two build runs)
p95:                     ~153-165 ms (two build runs)
```

Brute-force exact scan over 162,357 vectors - expected to be slower than
an ANN index; not compared against Task 0.10's non-binding IVF_PQ numbers.

### Tests

```text
new Task 1.5 tests:  20 (table creation/name/columns/no-ANN-index,
  validate_chunk_table invariants, query-vector rejection cases,
  exact_cosine_search self-match/orthogonal/opposite ranking, metadata
  traceability, malformed-query rejection) - temporary LanceDB dirs + tiny
  synthetic data throughout
doctor:              PASS
portable suite:       175 passed, 5 deselected, 0 failed
full suite:            180 passed, 0 failed, 0 skipped (was 160)
```

### Safety

```text
embeddings.parquet unchanged:  opened read-only, never rewritten
chunks.parquet unchanged:         sha256 3bd684c5... matches Task 1.4's
  recorded value
normalized Markdown unchanged:      normalization_build_sha256 re-verified
  identical (fd0abad2...2244b)
data/ unchanged:                       xbrl.duckdb 7,011,053,568 bytes, 36
  raw XBRL ZIPs, 990 primary filings - all identical
index artifact ignored by Git:           confirmed via git status --ignored
no ANN index:                                confirmed (list_indices()==[])
no BM25/FTS:                                   confirmed - vector-only
no retriever pipeline:                            confirmed - Task 1.6 not
  started
```

### Files Created / Modified

```text
src/index/lancedb_index.py           (new)
scripts/build_vector_index.py        (new)
configs/build_vector_index.json      (new, tracked)
results/phase_1_5_vector_index_summary.json  (new, tracked)
tests/test_vector_index.py            (new, 20 tests)
project_plan/PHASE1_VECTOR_INDEX.md    (new)
project_plan/REPOSITORY_STRUCTURE.md     (updated: src/index/ marked
  implemented, configs/ and scripts/ listings updated)
Progress.md                                (this entry)
```

493,178,075-byte LanceDB dataset under `artifacts/indexes/<hash>/` is
git-ignored and not listed individually. No `src/embeddings/`,
`src/chunk/`, `src/normalize/`, `src/ingest/`, embeddings.parquet,
chunks.parquet, normalized Markdown, or frozen `data/` modified. No new
dependency - `lancedb`/`pyarrow` already present.

### Git

```text
git status --short before commit: 6 new untracked tracked-worthy files
  plus doc updates - 0 artifacts/data/venv content stageable
secret scan:            clean
```

Committed as one coherent Task 1.5 commit: "Add exact LanceDB vector
index". No remote configured - push deferred, not attempted.

### Result

```text
PASS — exact cosine LanceDB index built for all Phase 1 embeddings
```

### Phase Status

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE
  1.3 Minimal Fixed-Window Chunker — COMPLETE
  1.4 Baseline Embedding Pipeline  — COMPLETE
  1.5 Vector-Only Index            — COMPLETE
  1.6 Baseline Retriever           — NEXT
```

## 2026-08-29 — Phase 1.6 Baseline Retriever

### Objective

Composes Task 1.4's BGE query encoder with Task 1.5's exact-cosine LanceDB
search into the first natural-language retrieval path - independent of
generation.

### Initial State

```text
Task 1.5 commit: b744fe7
index path:        artifacts/indexes/f1dc04d4.../BAAI--bge-small-en-v1.5/
table:                chunks, 162,357 rows (independently re-verified: 0
                     ANN indexes, correct 17-column schema)
model/revision:         BAAI/bge-small-en-v1.5 /
                     5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
chunk_config_hash:         f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
```

### Frozen User Decisions

Arrived pre-approved with the task prompt; nothing in the repo
contradicted them (no prior Task 1.6 artifact existed), so accepted as
given, same policy as Task 1.5's frozen decisions:

```text
default k = 5, caller-configurable, positive int only
distance returned (raw LanceDB _distance, lower better)
score returned (1.0 - distance, higher better), never clamped
vector never returned
```

### Retriever Contract

`src/retrieval/baseline.py`'s `BaselineRetriever.retrieve(question, k=5)`:
validates inputs (rejects non-str/empty/whitespace-only question, rejects
non-int/bool/non-positive k - never silently coerces), calls
`encode_queries()` exactly once (query convention, never passage
convention), calls `exact_cosine_search()` with `limit=k`, and converts
the result to a list of `RetrievalResult`. `encode_fn`/`search_fn` are
constructor-injectable (default to the real Task 1.4/1.5 functions) so
portable tests never need a real model or LanceDB table. A retriever
instance reuses its model/table handle across calls.

**Long-query behavior** (Step 24): `bge.py` defines no truncation of its
own - inherited from sentence-transformers' default `encode()`, which
truncates at the model's `max_seq_length` (verified 512). A 2000+-token
synthetic query returned a valid `(1,384)` finite vector with no error -
confirmed as Task 1.4's pre-existing, unmodified behavior, not a new
policy introduced here.

### Result Schema

`rank`, `score`, `distance`, `chunk_id`, `document_id`, `text`, `cik`,
`company`, `form_type`, `fiscal_year`, `source`, `source_filename`,
`source_split`, `ordinal`, `token_count`, `chunk_config_hash`,
`normalizer_version`, `normalization_build_sha256`,
`development_manifest_sha256`. No `vector`. Internal `_distance` column
name never exposed directly.

### Validation

```text
default k=5:                PASS
k=10:                           PASS
invalid k (0/negative/
  non-int/bool):                    PASS - all rejected
empty/whitespace/non-str
  question:                             PASS - all rejected
score = 1-distance,
  no clamping:                             PASS - regression-tested incl.
  negative-distance case (distance=-1e-7 -> score=1.0000001, not clamped)
rank/order preserved:                       PASS
vector omitted:                                PASS
approved metadata fields:                        PASS (exact set match)
Unicode query:                                      PASS
determinism (repeated query):                          PASS - identical
  chunk IDs/order, max score diff 0.00e+00
```

### Real-Corpus Smoke

6 SEC-style smoke questions (revenue, risk factors, net income, R&D, debt,
dividends) at k=5, plus explicit k=10 and one Unicode query - all returned
correct result counts with intact provenance. Example: "What was the
company's total revenue?" -> `1158114_2016.htm::chunk106` (APPLIED
OPTOELECTRONICS, INC., FY2016, score=0.7573). Not a relevance-quality
claim - integration correctness only.

### Performance

```text
Phase 1 smoke diagnostic - NOT a production benchmark
query count:        30 (+3 unmeasured warm-up)
k:                      5
query embedding:           p50 ~9.9 ms
exact search:                 p50 ~120.6 ms
total retrieve:                  p50 ~131.8 ms, p95 ~139.4 ms
```

Consistent with Task 1.5's standalone search diagnostic (~143-165 ms
p50/p95 at the same k=5) plus ~10ms query embedding overhead.

### Tests

```text
new Task 1.6 tests:  29 (k behavior, input validation, encoder-called-once,
  384-d query vector, rank/order, distance/score regression incl.
  no-clamping, vector omission, metadata field set, Unicode, plus 1
  model+gpu+local_data-marked real integration test against the actual
  Task 1.5 index)
doctor:              PASS
GPU smoke:            PASS
portable suite:        203 passed, 6 deselected, 0 failed
full suite:              209 passed, 0 failed, 0 skipped (was 180)
```

### Safety

```text
index unchanged:          162,357 rows, 0 ANN indexes, re-verified
embeddings unchanged:        sha256 52210a51... matches Task 1.5's recorded value
chunks unchanged:              sha256 3bd684c5... matches recorded value
normalized Markdown unchanged:    normalization_build_sha256 re-verified
  identical (fd0abad2...2244b)
data/ unchanged:                    xbrl.duckdb 7,011,053,568 bytes, 36 raw
  XBRL ZIPs, 990 primary filings - all identical
no network:                            offline throughout
no generation:                            confirmed - no LLM call, no prompt
  formatting
no BM25/reranker:                             confirmed - vector path only
```

### Files Created / Modified

```text
src/retrieval/baseline.py            (new)
scripts/smoke_retrieval.py           (new)
results/phase_1_6_retriever_summary.json  (new, tracked)
tests/test_baseline_retriever.py      (new, 29 tests)
project_plan/PHASE1_RETRIEVER.md       (new)
project_plan/REPOSITORY_STRUCTURE.md     (updated: src/retrieval/ marked
  implemented, scripts/ listing updated)
Progress.md                                (this entry)
```

No new config file created (Step 26: no new runtime semantics required
one beyond what Task 1.5's config/summary already capture). No
`src/index/`, `src/embeddings/`, `src/chunk/`, `src/normalize/`,
`src/ingest/`, index data, embeddings, chunks, normalized Markdown, or
frozen `data/` modified. No new dependency.

### Git

```text
git status --short before commit: 5 new untracked tracked-worthy files
  plus doc updates - 0 artifacts/data/venv content stageable
secret scan:            clean
```

Committed as one coherent Task 1.6 commit: "Add baseline vector
retriever". No remote configured - push deferred, not attempted.

### Result

```text
PASS — baseline natural-language vector retriever implemented
```

### Phase Status

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE
  1.3 Minimal Fixed-Window Chunker — COMPLETE
  1.4 Baseline Embedding Pipeline  — COMPLETE
  1.5 Vector-Only Index            — COMPLETE
  1.6 Baseline Retriever           — COMPLETE
  1.7 Minimal Generation Layer     — NEXT
```
