We have completed the Phase 1 data-readiness audit and currently have:

```text
DATA_READINESS_REPORT.md
phase1_data_audit.log
```

The report currently concludes:

```text
PHASE 2 READY
```

Before freezing Phase 1, I want to run **two additional metric-definition checks** identified during review.

This is NOT a new full audit.

Do not:

* redownload anything,
* modify raw data,
* start Phase 2,
* generate eval questions,
* parse/chunk documents,
* generate embeddings,
* build indexes,
* change architecture.

Use the existing data and existing audit code wherever possible.

The objectives are:

1. recalculate the XBRL restatement/revision metric using a stricter semantic definition,
2. recalculate EDGAR-CORPUS ↔ XBRL coverage using **10-K-only XBRL submissions** and verify year semantics,
3. update `DATA_READINESS_REPORT.md` with the corrected results,
4. give a final Phase 1 GO / NO-GO decision.

---

# CHECK 1 — STRICT XBRL RESTATEMENT / REVISION RATE

The current report gives:

```text
23.56%
```

using repeated:

```text
(cik, tag, ddate, qtrs)
```

groups across filings.

However, we need to verify that this is not inflated by:

* segment/dimensional facts,
* co-registrants,
* different units,
* multiple distinct facts inside the same accession.

## Goal

Calculate a stricter revision/restatement metric over comparable **consolidated facts only**.

At minimum, the comparison population must require:

```text
coreg IS NULL / blank
segments IS NULL / blank
same cik
same tag
same ddate
same qtrs
same uom
```

Facts must come from **different accessions/adsh** before they can count as a cross-filing repeat.

Do not count two different rows inside the same accession as a restatement.

---

## Step 1A — Establish the exact comparison grain

First inspect the relevant schema and clearly state the comparison identity.

Use a semantic key conceptually equivalent to:

```text
(cik, tag, ddate, qtrs, uom)
```

after restricting:

```text
coreg IS NULL/blank
segments IS NULL/blank
```

Then group values by distinct:

```text
adsh
```

A group is a **repeated cross-filing fact** only if:

```text
COUNT(DISTINCT adsh) > 1
```

A group is a **value revision candidate** only if:

```text
COUNT(DISTINCT value) > 1
```

after the above restrictions.

---

## Step 1B — Report exact numerator and denominator

Report:

```text
A = number of comparable fact groups reported by >1 distinct accession

B = number of those groups where >1 distinct value exists

revision_rate = B / A
```

Show:

```text
A
B
B/A
```

Do not report only a percentage.

---

## Step 1C — Compare against the previous 23.56%

Report:

| Metric                 | Previous method | Strict method |
| ---------------------- | --------------: | ------------: |
| repeated groups        |                 |               |
| differing-value groups |                 |               |
| rate                   |          23.56% |               |

Explain exactly why the strict result:

* stayed similar,
* decreased,
* or increased.

Do not force agreement with 23.56%.

---

## Step 1D — Run useful sanity variants

Also calculate the strict metric for:

### Variant A

All tags.

### Variant B

Only standard non-abstract taxonomy concepts where available:

```text
TAG.custom = 0
TAG.abstract = 0
```

### Variant C

Our planned supported financial-tag registry, at minimum:

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
RevenueFromContractWithCustomerExcludingAssessedTax
OperatingExpenses
EarningsPerShareBasic
EarningsPerShareDiluted
IncomeTaxExpenseBenefit
```

The goal is to understand whether the headline rate is mainly being driven by obscure/custom tags.

---

## Step 1E — Inspect examples

Select approximately:

```text
5 groups with genuinely differing values
```

from the strict calculation.

For each show:

```text
cik
company
tag
ddate
qtrs
uom

adsh 1
form
filed date
value

adsh 2
form
filed date
value
```

Check whether they look like:

* genuine subsequent revisions/restatements,
* comparative-period reporting differences,
* amendments,
* unexpected data artifacts.

Do not claim legal/accounting "restatement" status unless the data actually proves it.

If "revision" is more technically accurate than "restatement," update the report terminology accordingly.

This distinction is important.

---

# CHECK 2 — EDGAR-CORPUS ↔ XBRL 10-K COVERAGE

The current report gives:

```text
2016–2020
5800 / 6950
83.45%
```

but the derived XBRL submissions table contains both:

```text
10-K
10-Q
```

We need to verify that the overlap reflects **10-K-to-10-K coverage**, not merely the presence of any XBRL filing for a company-year.

---

# Step 2A — Understand EDGAR-CORPUS year semantics

Before recalculating anything, inspect:

```text
fetch_edgar_corpus.py
source parquet
original metadata
filename construction
```

Determine exactly what EDGAR-CORPUS:

```text
year
```

represents.

Possible meanings include:

```text
filing calendar year
fiscal year
reporting period year
year inferred from filename/source
```

Do not assume.

Document the evidence that supports your conclusion.

If necessary, inspect several filings and compare:

```text
EDGAR year
vs
10-K filing date
vs
XBRL filed
vs
XBRL period
vs
XBRL fy
```

Use real examples.

---

# Step 2B — Calculate 10-K-only overlap using current year definition

Restrict XBRL submissions to:

```sql
form = '10-K'
```

Do not include:

```text
10-Q
10-K/A
20-F
40-F
```

for this first comparison.

Normalize explicitly:

```text
CIK → BIGINT / int64
year → int32
```

Do not rely on implicit casting.

Calculate:

```text
EDGAR-CORPUS unique (cik, year) pairs
2016–2020
```

versus:

```text
XBRL 10-K unique (cik, comparable_year) pairs
2016–2020
```

using the XBRL year field that most correctly matches the meaning of the EDGAR year identified in Step 2A.

Show:

```text
numerator
denominator
rate
```

overall and by year:

| Year  | EDGAR pairs | XBRL 10-K matched | Coverage |
| ----- | ----------: | ----------------: | -------: |
| 2016  |             |                   |          |
| 2017  |             |                   |          |
| 2018  |             |                   |          |
| 2019  |             |                   |          |
| 2020  |             |                   |          |
| TOTAL |             |                   |          |

---

# Step 2C — Compare alternative year alignments

Because a fiscal year can end in one calendar year while its 10-K is filed in the next, compare at least:

### Alignment A

```text
EDGAR year ↔ XBRL fy
```

### Alignment B

```text
EDGAR year ↔ YEAR(XBRL period)
```

### Alignment C

```text
EDGAR year ↔ YEAR(XBRL filed)
```

Only if the required fields are available.

Report coverage for all three.

Example:

| Alignment                | Matched | Total | Coverage |
| ------------------------ | ------: | ----: | -------: |
| EDGAR year ↔ XBRL fy     |         |       |          |
| EDGAR year ↔ period year |         |       |          |
| EDGAR year ↔ filed year  |         |       |          |

Then determine which one has the **correct semantics**, not merely which gives the largest percentage.

We must not choose a definition just because it maximizes overlap.

---

# Step 2D — Inspect unmatched records

For each year, inspect a deterministic sample of unmatched EDGAR `(cik, year)` pairs.

Classify likely causes where possible:

```text
no XBRL 10-K available
XBRL starts later
filing-year/fiscal-year offset
company stopped filing
CIK mismatch
10-K/A only
source metadata issue
other
```

Summarize counts if practical.

The purpose is to determine whether the residual 15–20% mismatch is:

```text
structural
```

or:

```text
our join definition is wrong
```

---

# Step 2E — Optional stronger accession check

If EDGAR-CORPUS contains enough information to derive or recover an accession number, test accession-level matching for any available subset.

If accession is unavailable in EDGAR-CORPUS, state that explicitly and do not invent one.

Do not make this a blocker.

---

# CHECK 3 — REPORT CONSISTENCY CLEANUP

Update the existing:

```text
DATA_READINESS_REPORT.md
```

Do not create a second competing readiness report unless there is a strong technical reason.

Make the following consistency corrections.

---

## 3A — EDGAR table check severity

The current headline comparison table says:

```text
1/20 → WARN
```

but later manual inspection established that this was flattened numeric table content, not surviving structured table markup.

Therefore change the appropriate status to:

```text
INFO
```

and explain:

```text
Structured table markup is absent.
A small amount of flattened numeric/table-like text survives.
```

Do not describe EDGAR-CORPUS as containing structured tables.

---

## 3B — 81.71% vs 83.45%

Do not say:

```text
83.45% matches 81.71%
```

Instead explain that they were calculated under different denominator/window definitions.

Use wording conceptually like:

```text
Previous: 81.71% using earlier overlap-window logic
Audit: 83.45% using literal 2016–2020 restriction
Difference is methodological and reproduced/explained
```

Then replace the headline number with the new **10-K-only, semantically correct alignment** from Check 2.

Keep historical numbers in the report for traceability.

---

## 3C — Restatement terminology

If Check 1 demonstrates that the metric represents:

```text
same concept/period reported with differing values across filings
```

but does not prove formal accounting restatement status, rename it to something safer such as:

```text
cross-filing value revision rate
```

or:

```text
repeated-fact differing-value rate
```

You may note that formal restatements are a subset/interpretation requiring more filing context.

Do not overclaim.

---

# CHECK 4 — UPDATE THE FINAL READINESS GATE

After incorporating the results, update:

```text
## Executive Summary
```

and:

```text
## Final Recommendation
```

Use exactly one final state:

```text
PHASE 2 READY
```

or:

```text
PHASE 2 READY WITH WARNINGS
```

or:

```text
PHASE 2 BLOCKED
```

Only use BLOCKED if the new checks reveal a problem that prevents us from constructing reliable Phase 2 ground truth.

A lower overlap percentage by itself is not automatically a blocker if:

* the reason is understood,
* enough aligned filings remain,
* evaluation generation can explicitly select the aligned subset.

---

# CHECK 5 — ADD A FINAL "FROZEN PHASE 1 NUMBERS" SECTION

At the end of:

```text
DATA_READINESS_REPORT.md
```

add:

```markdown
## Frozen Phase 1 Metrics
```

This should contain the numbers that downstream work is allowed to cite as the final Phase 1 dataset statistics.

Include at least:

```text
MS MARCO passages
MS MARCO dev-small queries

EDGAR filings
EDGAR CIKs
EDGAR year range

XBRL facts
XBRL submissions
XBRL CIKs
XBRL tags

full-key duplicate count/rate

strict cross-filing revision metric:
numerator
denominator
rate
definition

EDGAR ↔ XBRL 10-K coverage:
numerator
denominator
rate
year semantics used

primary filings
primary table survival
primary inline-XBRL survival

total raw data size
```

For sensitive/complex metrics include the definition next to the number.

Example:

```text
10-K alignment coverage:
X / Y = Z%
Definition: unique EDGAR (CIK, <year semantics>) pairs from 2016–2020
matching XBRL submissions where form='10-K' using <chosen year field>.
```

This section becomes the authoritative source for Phase 2.

---

# CHECK 6 — PRESERVE REPRODUCIBILITY

If possible, implement these checks inside the existing:

```text
src/ingest/audit_data.py
```

rather than one-off notebook/terminal SQL.

Create reusable functions conceptually like:

```python
audit_strict_revision_rate(...)
audit_edgar_xbrl_10k_alignment(...)
```

Do not duplicate large existing helper functions.

Use explicit SQL/comments documenting:

```text
filters
keys
numerator
denominator
casts
```

Update:

```text
phase1_data_audit.log
```

or append a clearly marked final-verification section.

If modifying the existing audit script would make it messy, create:

```text
src/ingest/final_phase1_checks.py
```

and document the command.

Preferred command:

```bash
python -m src.ingest.final_phase1_checks
```

or, if integrated:

```bash
python -m src.ingest.audit_data --final-checks
```

Do not rerun expensive unrelated checks unnecessarily.

---

# CHECK 7 — DO NOT MODIFY RAW DATA

All operations must be read-only against:

```text
MS MARCO
EDGAR-CORPUS
XBRL ZIP files
primary HTML filings
```

Derived metadata/cache/report artifacts may be updated.

If temporary tables are required, place them in temporary/derived storage.

---

# FINAL RESPONSE TO ME

After running the checks, report:

## 1. Strict cross-filing revision metric

```text
Old:
23.56%

New:
X / Y = Z%

Definition:
...
```

Include results for:

```text
all comparable facts
standard non-abstract facts
15 supported tags
```

## 2. 10-K-only EDGAR ↔ XBRL alignment

```text
Old literal audit:
5800 / 6950 = 83.45%

New 10-K-only:
X / Y = Z%
```

Include the chosen year semantics and per-year results.

## 3. Alternative year-alignment comparison

Show:

```text
fy
period year
filed year
```

and explain which is semantically correct.

## 4. Unmatched analysis

Give the main causes.

## 5. Report corrections

State exactly what changed in:

```text
DATA_READINESS_REPORT.md
```

## 6. Final Phase 1 status

Return one:

```text
PHASE 2 READY
PHASE 2 READY WITH WARNINGS
PHASE 2 BLOCKED
```

## 7. Files modified

List them.

## 8. Reproduction command

Give the exact command.

---

# MOST IMPORTANT RULE

Do not optimize calculations to reproduce our previous numbers.

We are trying to discover the correct numbers.

For every metric explicitly state:

```text
population
filters
grouping key
numerator
denominator
```

If the new number is materially different from what we previously believed, investigate and report why.

Do NOT begin Phase 2 after finishing.

Stop and wait for my approval.
