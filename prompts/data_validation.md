You are working inside my **SEC RAG** repository.

Phase 1 — data acquisition — is complete. Before we begin normalization, evaluation generation, chunking, embeddings, or retrieval, I want one final **DATA READINESS + DATA UNDERSTANDING AUDIT**.

The purpose of this task is:

1. independently inspect the actual datasets currently on disk,
2. understand their schemas and basic characteristics,
3. reproduce the most important Phase 1 validation numbers,
4. detect any silent inconsistencies,
5. confirm that the corpus is safe to use for Phase 2,
6. produce a concise but rigorous dataset readiness report.

## Important constraints

Do **NOT**:

* redownload any dataset,
* delete or mutate raw data,
* start parsing/chunking,
* generate embeddings,
* build indexes,
* build the RAG pipeline,
* create the eval question set yet,
* change the architecture,
* silently "fix" suspicious data.

Treat all existing datasets as **read-only**.

You may create:

* reusable audit/inspection Python scripts,
* audit logs,
* summary CSV/Parquet files if useful,
* one final Markdown report.

Before writing new code, inspect and reuse the existing code under:

```text
src/ingest/
```

especially:

```text
common.py
fetch_edgar_corpus.py
fetch_msmarco.py
fetch_primary_docs.py
fetch_xbrl.py
validate.py
```

Also inspect:

```text
Progress.md
stage1_msmarco.log
stage2_edgar_corpus*.log
stage3_xbrl.log
stage4_primary.log
stage5_validate.log
```

Do not trust previous logs blindly. Use them as references, then independently verify the critical results from the actual data.

---

# PART 1 — INVENTORY THE ACTUAL DATA

First recursively inspect the `data/` directory.

Produce a dataset inventory containing:

* dataset/source
* file paths
* number of files
* total disk size
* file formats
* row/document counts where applicable
* available year range
* unique companies / CIKs
* important partitions/splits
* whether the dataset appears complete
* any unexpected files
* any missing expected files

Do not print millions of filenames.

Summarize intelligently.

Expected sources are:

1. MS MARCO
2. EDGAR-CORPUS
3. SEC XBRL Financial Statement Data Sets
4. SEC primary 10-K documents

Also identify derived artifacts already present, such as:

```text
xbrl.duckdb
```

and clearly distinguish:

```text
RAW SOURCE DATA
vs
DERIVED DATA
vs
LOGS
```

---

# PART 2 — UNDERSTAND EACH DATASET

I want more than counts. I want us to understand what each dataset actually contains.

For every major table/file, report:

* schema
* column names
* physical data types
* sample values
* null percentages for important fields
* uniqueness where relevant
* minimum/maximum dates or years
* obvious categorical distributions
* unusual/extreme values
* relationships to the other datasets

Do not dump every column blindly. Focus on fields that matter for SEC RAG.

---

# PART 3 — MS MARCO AUDIT

Inspect:

```text
corpus
queries
qrels
```

and all available splits.

Report at least:

### Corpus

* passage count
* unique passage IDs
* duplicate ID count
* empty/null passage count
* text length statistics:

  * min
  * median
  * p95
  * max

### Queries

* query count by split
* unique query IDs
* null/empty queries
* query length statistics

### Qrels

For every split:

* qrel count
* unique queries referenced
* unique passages referenced
* missing query references
* missing corpus references

Explicitly verify referential integrity.

Confirm whether:

```text
dev-small = 6,980 queries
```

If the local naming differs, determine which split corresponds to the BEIR/MS MARCO dev-small benchmark.

Explain in plain English:

> What role will MS MARCO play in this project?

It should be treated as a **benchmark/harness validation dataset**, not part of the SEC production corpus.

---

# PART 4 — EDGAR-CORPUS AUDIT

Inspect all train/test/validation Parquet files.

Report:

* total filings
* filings by split
* unique CIK count
* year range
* filings/year
* companies/year
* form types if available
* duplicate filing/accession indicators
* null rates for key metadata
* native CIK type
* section columns available

## Section analysis

For every available SEC section:

calculate:

```text
number populated
fill percentage
median text length
p95 text length
```

Pay special attention to:

```text
Item 1
Item 1A
Item 1B
Item 7
Item 7A
Item 8
Item 9A
Item 9B
Item 15
```

Reproduce/verify the known sparse-section issue.

Previously observed approximate fill rates include:

```text
section_1A ≈ 25.6%
section_1B ≈ 24.4%
section_9A ≈ 30.1%
section_9B ≈ 27.0%
section_15 ≈ 32.4%
```

Do not force the new result to match.

If numbers differ materially, investigate and explain why.

## Table check

Randomly inspect a reproducible sample of at least 20 filings.

Determine whether EDGAR-CORPUS contains recognizable tabular structure.

Check indicators such as:

* HTML table elements
* Markdown tables
* repeated aligned columns
* pipe-delimited rows
* tab-separated tabular blocks

We currently believe tables were stripped.

Verify this independently.

---

# PART 5 — XBRL DATA AUDIT

This is the most important dataset.

Inspect the XBRL DuckDB and/or source files.

First identify all relevant tables, particularly:

```text
num
sub
tag
pre
```

or their local equivalents.

For each table report:

* row count
* schema
* key columns
* null rates on important columns
* sample rows
* approximate role of the table

Explain in plain English what:

```text
adsh
cik
tag
version
coreg
ddate
qtrs
uom
segments
value
filed
period
sic
```

mean for this project.

## Critical NUM checks

Report:

* total facts
* distinct CIKs
* distinct tags
* year/date coverage
* unit distribution
* `qtrs` distribution
* `coreg IS NULL` vs non-null
* `segments IS NULL` vs non-null
* negative value counts by major tags
* null value count
* top 20 tags by frequency

## Duplicate analysis

Recalculate duplicates using the proper SEC fact identity.

Do not use a simplified key that collapses segment/coreg distinctions.

Clearly state the exact key used.

Verify whether the previously measured true duplicate rate remains approximately:

```text
32 / ~90.7M
≈ 0.0000%
```

## Restatement analysis

Calculate repeated facts across filings using something conceptually equivalent to:

```text
(cik, tag, ddate, qtrs)
```

while respecting the full fact structure.

Determine how often different filings report the same concept/period.

Compare with the previous approximately:

```text
23.56%
```

Again, do not force agreement.

Explain what this number actually means.

---

# PART 6 — CHECK XBRL TRUTH-CONTRACT PREREQUISITES

We are NOT generating eval questions yet.

We are only checking whether the data needed for the future truth contract exists.

For the initial standard financial concepts, investigate whether these tags are available and sufficiently populated:

```text
Assets
Liabilities
StockholdersEquity
CashAndCashEquivalentsAtCarryingValue
Revenues
ResearchAndDevelopmentExpense
NetIncomeLoss
OperatingIncomeLoss
CostOfRevenue
GrossProfit
```

Also identify sensible candidates for the remaining tags if a 15-tag evaluation registry is planned.

For each candidate report:

```text
tag
fact count
company count
year coverage
uom distribution
qtrs distribution
TAG.custom
TAG.abstract
TAG.iord
```

where available.

Do NOT assume:

```text
version == "us-gaap"
```

means "standard US-GAAP tag."

Use the SEC TAG metadata and specifically inspect:

```text
custom
abstract
iord
```

We eventually want a supported-tag whitelist using standard, non-abstract concepts.

Validate whether:

```text
qtrs = 0
```

corresponds appropriately to instant concepts such as Assets, and:

```text
qtrs = 4
```

is appropriate for annual duration concepts such as Revenues.

Report exceptions rather than hiding them.

---

# PART 7 — SUBMISSION / FILING UNDERSTANDING

Inspect the submission metadata.

Report:

* unique submissions
* unique CIKs
* form distribution
* year distribution
* SIC availability
* fiscal year / period fields
* filed-date coverage
* duplicated accession numbers
* missing CIKs
* missing period dates

Show how a numerical XBRL fact can be traced:

```text
NUM.adsh
    ↓
SUB.adsh
    ↓
CIK
company
form
filed date
period end
fiscal year
SIC
```

Take 3 concrete random examples and demonstrate this relationship.

Use a deterministic random seed.

---

# PART 8 — EDGAR-CORPUS ↔ XBRL JOIN AUDIT

This is critical because a previous silent bug occurred from comparing:

```text
string CIK
vs
integer CIK
```

First inspect the physical types in both sources.

Do NOT rely on implicit casting.

For the audit, explicitly normalize:

```text
CIK → int64
year → int32
```

in memory/query logic.

Do not mutate raw source files.

Calculate:

### Company-level overlap

```text
unique CIKs in EDGAR-CORPUS
unique CIKs in XBRL
intersection
intersection / EDGAR CIKs
```

Compare with the previously observed approximately:

```text
26.51%
```

Explain why this overall number is structurally low.

### Filing-period overlap

Restrict to the meaningful overlapping period:

```text
2016–2020
```

Calculate the join coverage over:

```text
(cik, fiscal_year)
```

or the closest correctly aligned fields available.

Compare with the previously observed:

```text
81.71%
```

Be extremely careful here.

Do not allow:

* string/int mismatches
* accidental `r[0]`-style tuple truncation
* years with tiny noise counts to distort the denominator
* fiscal-year vs filing-year confusion

Show the numerator and denominator explicitly.

Also calculate coverage separately for each year:

```text
2016
2017
2018
2019
2020
```

This should tell us whether the proposed SEC evaluation period of 2016–2020 is justified.

---

# PART 9 — PRIMARY DOCUMENT AUDIT

Inspect the downloaded SEC primary documents.

Report:

* total files
* total size
* unique CIKs
* unique accessions if derivable
* year distribution
* min/median/p95/max document size
* empty/corrupt/unreadable files

Use a deterministic random sample of at least 30 documents.

For the sample check:

### Tables

Determine whether actual HTML tables survive.

Report:

```text
documents containing tables / sample size
mean tables/document
median
p95
max
```

Compare with the previous observation that almost all sampled documents contained tables and the mean was roughly 136 tables/document.

### Inline XBRL

Determine whether inline-XBRL elements exist, including elements such as:

```text
ix:nonFraction
ix:nonNumeric
```

Report:

```text
documents with inline XBRL / sample size
```

This matters because these documents may later provide automatic chunk-level evidence labels.

### Basic HTML structure

For several examples identify:

```text
title/company if visible
filing/accession
major sections
number of tables
number of inline-XBRL facts
document character count
```

Do not parse them with Docling yet.

This is inspection only.

---

# PART 10 — DATA QUALITY / ANOMALY AUDIT

Search specifically for cases that could silently break later stages.

Examples:

```text
CIK type mismatch
leading-zero IDs
duplicate accessions
invalid years
unexpected form types
missing company names
missing fiscal years
missing filing dates
bad period dates
empty sections
extremely tiny/huge documents
extreme financial values
negative Assets
mixed units
segment facts masquerading as consolidated facts
co-registrant facts
duplicate source files
partial downloads
zero-byte files
schema drift across yearly XBRL ZIPs
schema drift across EDGAR splits
```

For every discovered issue classify it:

```text
INFO
WARN
BLOCKER
```

A BLOCKER means we should not start Phase 2.

Do not label normal SEC complexity as a blocker just because it exists.

---

# PART 11 — DATASET RELATIONSHIP MAP

Create a simple conceptual map showing how our sources relate.

Something like:

```text
                     SEC RAG DATA

 EDGAR-CORPUS
 narrative sections
       │
       │ CIK/year
       ▼
 XBRL SUB ───────── XBRL NUM
 metadata             financial facts
       │
       │ accession / CIK
       ▼
 Primary 10-K HTML
 complete documents
 tables + inline XBRL


 MS MARCO
 separate benchmark only
```

Improve this based on the actual fields discovered.

Also explain what each source will eventually be used for:

```text
EDGAR-CORPUS → large-scale narrative retrieval

XBRL → deterministic numeric QA + ground truth

Primary documents → tables + parsing + inline-XBRL evidence alignment

MS MARCO → retrieval/evaluation harness sanity check
```

---

# PART 12 — 10 CONCRETE DATA EXAMPLES

I want to understand the data intuitively, not only statistically.

Select a few real records and show examples such as:

1. one EDGAR-CORPUS filing
2. one Item 1 section
3. one Item 7 section
4. one XBRL Assets fact
5. one Revenues fact
6. one fact with `coreg`
7. one fact with segment metadata
8. one restated concept across two filings
9. one primary HTML table
10. one MS MARCO query → relevant passage pair

Keep samples short.

Do not dump huge SEC sections.

Explain what each example teaches us.

---

# PART 13 — PRODUCE A DATA READINESS REPORT

Create:

```text
DATA_READINESS_REPORT.md
```

at repository root.

Use this structure:

```markdown
# SEC RAG — Phase 1 Data Readiness Report

## Executive Summary

Overall status:

GO
GO WITH WARNINGS
or
NO-GO

## 1. Dataset Inventory

## 2. MS MARCO

## 3. EDGAR-CORPUS

## 4. XBRL

## 5. Primary SEC Documents

## 6. Cross-Dataset Joins

## 7. Data Quality Findings

## 8. Important Data Semantics

## 9. Confirmed Assumptions

## 10. Assumptions That Were Wrong

## 11. Warnings / Limitations

## 12. Blockers

## 13. Phase 2 Readiness Checklist

## 14. Final Recommendation
```

For every major validation include:

```text
expected/reference result
new measured result
difference
PASS/WARN/FAIL
```

Example:

| Check                   | Previous |  Current | Status |
| ----------------------- | -------: | -------: | ------ |
| XBRL facts              |   ~90.7M | measured |        |
| EDGAR filings           |   91,086 | measured |        |
| Overall CIK overlap     |   26.51% | measured |        |
| 2016–2020 CIK/year join |   81.71% | measured |        |
| XBRL restatement rate   |   23.56% | measured |        |
| Primary docs            |      990 | measured |        |

Do not mark something FAIL merely because the number differs slightly.

Investigate material differences.

---

# PART 14 — PHASE 2 READINESS GATE

At the end, explicitly answer these questions:

### Acquisition

* Are all four datasets present?
* Are files readable?
* Are counts plausible?
* Are there partial downloads?

### Schema

* Do we understand the relevant schemas?
* Are identifier types known?
* Can CIKs be normalized safely?
* Are accession IDs usable?

### XBRL

* Can facts be linked deterministically to submissions?
* Do we have enough standard concepts for the planned numeric benchmark?
* Are `coreg`, `segments`, units, qtrs and period semantics understood?
* Can we distinguish instant and duration concepts?

### Narrative

* Is EDGAR-CORPUS suitable for large-scale narrative retrieval?
* Are sparse sections quantified?
* Are tables indeed unavailable there?

### Primary documents

* Do tables survive?
* Does inline XBRL survive?
* Are these documents suitable for our later table/evidence experiments?

### Cross-source alignment

* Is 2016–2020 still the appropriate evaluation window?
* Is `(CIK, year)` coverage acceptable?

### Final gate

Return exactly one of:

```text
PHASE 2 READY
```

```text
PHASE 2 READY WITH WARNINGS
```

or:

```text
PHASE 2 BLOCKED
```

If blocked, list the exact blockers and the minimum action necessary to resolve each one.

---

# IMPLEMENTATION GUIDELINES

Prefer:

* DuckDB SQL for large analytical queries,
* PyArrow/Polars/Pandas only where appropriate,
* streaming or aggregate operations instead of loading huge datasets into RAM,
* deterministic seeds for samples,
* reusable functions,
* explicit type casts,
* assertions for invariants.

The machine has enough data to make careless full-memory loading expensive.

Do not do:

```python
df = load_all_90_million_rows_into_pandas()
```

Use DuckDB for large XBRL analysis.

For expensive operations, print progress.

Time every major audit section.

Catch failures and report them; do not silently skip checks.

---

# REPRODUCIBILITY

If the current validation code is messy or too specific to acquisition, create:

```text
src/ingest/audit_data.py
```

It should be possible to run:

```bash
python -m src.ingest.audit_data
```

and reproduce the important dataset-readiness checks.

Do not duplicate existing good validation functions unnecessarily. Refactor/reuse where safe.

Save the execution log as:

```text
phase1_data_audit.log
```

The script should exit:

```text
0 → no blockers
1 → blocker detected or audit failed
```

Warnings should not produce exit code 1.

---

# IMPORTANT ENGINEERING BEHAVIOR

The most important principle for this task:

> A believable number is not evidence that the calculation is correct.

For every major metric:

1. inspect the schema,
2. state the numerator,
3. state the denominator,
4. state filters,
5. state key columns,
6. state casts/conversions,
7. sanity-check the result independently where practical.

We previously found silent bugs involving:

* `coreg` / `segments` being omitted from identity logic,
* misunderstanding the XBRL `version` field,
* string vs integer CIK comparison,
* accidentally reducing `(cik, year)` tuples to one element,
* denominator inflation from noisy years.

Design this audit specifically so those classes of errors cannot silently return plausible results again.

---

# FINAL RESPONSE TO ME

After completing the audit, do not just say "done."

Give me:

1. **Final status:** READY / READY WITH WARNINGS / BLOCKED
2. Total disk/data inventory
3. The 8–12 most important measured numbers
4. Any differences from our previous Phase 1 numbers
5. Every WARN
6. Every BLOCKER
7. Five things we learned about the data that matter for RAG
8. Exact files created/modified
9. Exact command used to reproduce the audit
10. Whether you recommend proceeding to the next phase

Do **not** begin Phase 2 automatically.

Stop after the audit and wait for my approval.
