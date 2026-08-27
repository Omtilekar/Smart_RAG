# Phase 1 Development Corpus

Established in Task 1.1. This is the small, frozen, reproducible 1,500-filing
population that all remaining Phase 1 tasks (1.2 normalization onward)
consume. It is not the final Phase 2 evaluation corpus and not a DEV/TEST
split — see "Known limitations" below.

## Purpose

Phase 0 built infrastructure. Phase 1 builds the crudest possible working
RAG system. `PROJECT_EXECUTION.md`'s "develop small, scale once" principle
means Phase 1 experiments on 1,500 filings, not the full 91,086-filing
EDGAR-CORPUS.

## Source datasets

- **EDGAR-CORPUS** (`data/edgar_corpus/{train,test,validation}.parquet`,
  frozen, read-only): 91,086 filings, 25,937 CIKs, years 1993-2020. Schema:
  `filename`, `cik` (VARCHAR), `year` (VARCHAR), `section_1`..`section_15`.
  No company-name or accession field exists in this dataset.
- **XBRL** (`data/xbrl.duckdb`, frozen, read-only, opened read-only by the
  selection script): `submissions` table, `cik` (BIGINT), `form`,
  `fiscal_year`, `adsh`, `period`, `filed`, `name`.

## Authoritative alignment definition

Reproduced independently from `src/ingest/audit_data.py`'s
`check2_10k_alignment()` (see `DATA_READINESS_REPORT.md`, "Check 2") rather
than inventing a new join:

- **Window**: EDGAR-CORPUS `year` in `[2016, 2020]`.
- **Form filter**: XBRL `submissions.form = '10-K'` only (excludes 10-Q,
  10-K/A, 20-F, 40-F, S-1, etc).
- **CIK normalization**: `TRY_CAST(cik AS BIGINT)` on both sides. Rows that
  fail to convert are rejected, not coerced (0 rejected in the real run).
- **Year normalization**: `TRY_CAST(year AS INTEGER)` on the EDGAR side.
- **Year semantic field**: XBRL `fiscal_year` (`fy`) — chosen in the
  original audit because it is the semantically correct fiscal-year field
  for aligning against EDGAR-CORPUS `year`, not because it produces the
  largest number (period-year alignment is nearly identical; filed-year
  alignment is materially worse — see `DATA_READINESS_REPORT.md` Check 2,
  Step 2A/2C).
- **Join grain**: `(cik, year)`. An EDGAR `(cik, year)` pair is eligible if
  at least one XBRL 10-K submission for that `cik` has `fiscal_year == year`.
- **EDGAR-side duplicates**: none. EDGAR-CORPUS `filename` is exactly
  `{cik}_{year}.{ext}` and is 1:1 with `(cik, year)` — verified directly
  (0 groups with more than one distinct filename per `(cik, year)`).

## Eligible population — independently reconstructed and validated

```text
eligible aligned population: 5,646
denominator (all EDGAR 2016-2020 pairs):  6,950
coverage: 81.24%
```

Reproduced exactly against the frozen authoritative figure
(`DATA_READINESS_REPORT.md`: "5,646 / 6,950 = 81.24%"), including the
identical per-year breakdown:

| Year | EDGAR pairs | XBRL 10-K matched | Coverage |
|---|---:|---:|---:|
| 2016 | 1,454 | 1,197 | 82.32% |
| 2017 | 1,409 | 1,145 | 81.26% |
| 2018 | 1,377 | 1,126 | 81.77% |
| 2019 | 1,339 | 1,066 | 79.61% |
| 2020 | 1,371 | 1,112 | 81.11% |
| **TOTAL** | **6,950** | **5,646** | **81.24%** |

## Duplicate XBRL 10-K accessions (user-approved resolution)

29 of the 5,646 aligned `(cik, fiscal_year)` pairs in the 2016-2020 window
have more than one candidate 10-K `adsh` sharing that fiscal year (e.g.
`cik=844887, fy=2017` has both `0001445866-18-000392` and
`0001445866-18-000407`). The audited Check-2 methodology only proves
alignment *exists* (`EXISTS(...)` in SQL) — it never picks a canonical
accession, and no other part of the repository resolves this.

**User-approved decision (asked before implementation, since no existing
rule resolved it)**: no canonical `adsh` is chosen. Each manifest row
instead carries `xbrl_10k_candidate_count`, which is `1` for 5,617 rows and
`>1` for 29 rows. This matches the audited methodology exactly rather than
inventing a new tiebreak rule (earliest-filed / latest-filed / etc).

## Document identity and traceability

**Stable EDGAR document identity = `filename`** (e.g. `1005817_2016.htm`).
Verified: 91,086 distinct filenames, 1:1 with `(cik, year)`, 0 duplicates
across the train/test/validation splits. This is the manifest's
`document_id` and is stable under re-scan (it does not depend on
filesystem/row order).

**Accession limitation** (stated explicitly, not silently worked around):
EDGAR-CORPUS carries no accession-number field, and none can be reliably
reconstructed from it (`DATA_READINESS_REPORT.md` "Check 2", Step 2E). No
EDGAR accession is fabricated anywhere in this manifest or its generating
code. XBRL `adsh` values recorded as alignment evidence are never labeled
as "the EDGAR accession."

Traceability chain per manifest row:
`document_id` (EDGAR `filename`) → EDGAR source row (`cik`, `year`, `split`)
→ `(cik, year)` membership in the aligned population → XBRL `10-K`
submission(s) with matching `fiscal_year` (evidence only, count recorded,
no canonical accession chosen).

5–10 rows spanning all five years were manually traced through this full
chain against the live frozen data and confirmed correct (see Task 1.1
Progress.md entry for the exact rows and results).

## Selection rule (user-approved)

`PROJECT_EXECUTION.md` requires "a deterministic seed or deterministic
sampling rule" without specifying which, and no prior Phase 1 sampling rule
existed anywhere in the repository (Task 1.1 is the first Phase 1 task).

**User-approved rule (Option A)**: SHA-256 over each eligible filing's
`document_id`, sorted ascending, first 1,500 taken. No replacement. No PRNG
seed to lose or depend on a specific RNG algorithm/version — the same 5,646
eligible identities always hash-sort into the same first 1,500, on any
machine, forever.

No stratification by year, company, industry, split, or document length was
applied — `PROJECT_EXECUTION.md` requires *recording* company/year
distribution, not forcing a balanced one, and stratification was not
otherwise specified.

## Manifest location (user-approved)

`results/phase_1_1_development_corpus.json`, tracked in Git. None of
`STORAGE.md` / `REPOSITORY_STRUCTURE.md` / `GIT_CONVENTIONS.md` defined a
location for this specific artifact type (it doesn't key off a
`chunk_config_hash`/embedding-model pair like `artifacts/chunks/` or
`artifacts/indexes/` do), so this was asked rather than assumed. `results/`
was chosen because `REPOSITORY_STRUCTURE.md` and `.gitignore` already carve
out `results/*.json` as a tracked exception for exactly this kind of small,
reproducibility-critical, human-inspectable output.

## Manifest schema

Top-level fields: `manifest_schema_version`, `created_at_utc`, `git_sha`,
`source_datasets`, `eligible_window_years`, `alignment_definition`,
`eligible_count`, `eligible_denominator`, `eligible_coverage_pct`,
`selection_count`, `selection_method`, `seed` (always `null`),
`storage_sort_rule`, `development_manifest_sha256`,
`eligible_population_distribution`, `selected_corpus_distribution`,
`filings` (array of 1,500 rows).

Per-filing fields (JSON integers; downstream Phase 1 code should cast
`cik` to `int64` and `year` to `int32` per the Task 1.2 frontmatter
contract):

```text
document_id                   stable EDGAR-CORPUS identity (== source_filename)
cik                            int
year                           int (== the aligned XBRL fiscal_year for this pair)
source                         "edgar_corpus"
source_split                   "train" | "test" | "validation"
source_filename                EDGAR-CORPUS filename (identical to document_id)
company_name                   from XBRL submissions.name (informational only,
                                not part of document identity; if the 29
                                multi-candidate pairs have differing names
                                across accessions, the alphabetically-first
                                name is recorded deterministically)
xbrl_alignment_year_field       "fy" (always - the field used for this row's match)
xbrl_10k_candidate_count        count of distinct XBRL 10-K adsh matching (cik, fy);
                                1 for 5,617 rows, >1 for 29 rows (see above)
```

**`development_manifest_sha256`** is computed over the canonical JSON
serialization (`sort_keys=True, separators=(",", ":")`) of the `filings`
array *only* — not the whole document, so the hash is not self-referential.
The `filings` array itself is stored sorted ascending by `document_id` for
readability; this storage order is independent of, and does not affect,
which 1,500 rows were selected (selection order is ascending
SHA-256(`document_id`), computed before the canonical sort is applied).

## Selected corpus

```text
selected filings:        1,500
unique CIKs:              1,376
unique company names:     1,389 (informational only - see "company_name" note above)
filings per CIK:           min=1  median=1.0  p95=2  max=3
```

| Year | Eligible | Eligible % | Selected | Selected % |
|---|---:|---:|---:|---:|
| 2016 | 1,197 | 21.20% | 332 | 22.13% |
| 2017 | 1,145 | 20.28% | 321 | 21.40% |
| 2018 | 1,126 | 19.94% | 288 | 19.20% |
| 2019 | 1,066 | 18.88% | 275 | 18.33% |
| 2020 | 1,112 | 19.70% | 284 | 18.93% |

The selected-year mix is close to, but not forced to match, the eligible
population's year mix — hash-order sampling was not stratified, so mild
drift (e.g. 2016 at 22.13% selected vs 21.20% eligible) is expected sampling
noise, not a bug. No stratification was applied, so the selected
distribution is not claimed to be representative beyond what unbiased
hash-order sampling from the eligible population supports. No pathological
company concentration was found (max 3 filings from any single CIK out of
1,500).

## Known limitations

- The Phase 1 development corpus is only 1,500 filings — a development
  subset, not the full 91,086-filing corpus and not the final Phase 2
  benchmark.
- Restricted to the 2016-2020 aligned region, not the full 1993-2020
  EDGAR-CORPUS year range.
- EDGAR-CORPUS structured tables are absent (see `DATA_READINESS_REPORT.md`)
  and some EDGAR sections are sparse (Item 1A/1B/9A/9B/15) — properties of
  the source data, not something this selection can fix.
- This is a development corpus, not a locked DEV/TEST split. Phase 2 (Task
  2.4) owns the company-disjoint DEV/TEST split; Task 1.1 does not create
  one.
- XBRL alignment establishes `(cik, year)` eligibility; it does not create
  an EDGAR accession number that EDGAR-CORPUS itself does not provide.
- `company_name` is informational (sourced from XBRL, not EDGAR-CORPUS,
  which has no such field) and must not be treated as part of document
  identity — `document_id` (EDGAR `filename`) is the identity field, and
  `cik` is the entity key.
- 29 of 1,500 selected rows may have `xbrl_10k_candidate_count > 1`,
  meaning more than one XBRL 10-K accession shares that row's alignment
  year; no single accession is asserted as canonical for those rows.

## Reproducing this manifest

```bash
python scripts/select_development_corpus.py
```

Reads `data/edgar_corpus/*.parquet` and `data/xbrl.duckdb` read-only,
performs no network access, writes only
`results/phase_1_1_development_corpus.json`. Running it again against
unchanged frozen data reproduces an identical `development_manifest_sha256`
(verified in a fresh process during Task 1.1) and refuses to silently
overwrite an existing manifest whose checksum differs.
