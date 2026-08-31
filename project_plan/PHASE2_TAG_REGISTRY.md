# Phase 2 Evaluation Tag Registry

Established in Task 2.2. Freezes the authoritative set of XBRL concepts
Phase 2 evaluation may use, and resolves the five tag/qtrs decisions Task
2.1 deliberately left open. `configs/eval_tags.yaml` is now the **only**
place per-tag `qtrs`/`unit`/`period_type`/`enabled` semantics are decided
— `src/eval/truth_contract.py` consumes it via `src/eval/tag_registry.py`
and no longer maintains an independent mapping.

## Objective

A future developer should be able to open `configs/eval_tags.yaml` and
answer, without reading implementation code: which XBRL concepts do we
evaluate, what kind of accounting facts are they, what `qtrs`/unit is
valid, which candidates were excluded, and which registry version
produced a given benchmark.

## Authoritative candidate set

The 15-tag candidate set was established from `src.ingest.audit_data.CANDIDATE_TAGS`
(the exact list that produced `DATA_READINESS_REPORT.md`'s own 15-tag
table) — no concept was added beyond this set:

```text
Assets, Liabilities, StockholdersEquity, CashAndCashEquivalentsAtCarryingValue,
Revenues, ResearchAndDevelopmentExpense, NetIncomeLoss, OperatingIncomeLoss,
CostOfRevenue, GrossProfit, RevenueFromContractWithCustomerExcludingAssessedTax,
OperatingExpenses, EarningsPerShareBasic, EarningsPerShareDiluted,
IncomeTaxExpenseBenefit
```

## Final result: 15 SUPPORTED, 0 EXCLUDED, 0 unresolved

Every candidate received a defensible SUPPORTED decision — none was
excluded, and **not** because "approximately 15" was a target to hit:
each of the 5 previously-unresolved tags was investigated individually
against real 2016-2020/10-K data and found to have the same
dominant-annual-figure pattern (>99% of filings that report the tag at
all report it at `qtrs=4`) already established for the 10 tags Task 2.1
resolved, plus defensible coverage (1,796–7,737 unique eligible CIKs
across all 15 tags — no candidate is pathologically sparse).

| Tag | Supported | Period Type | qtrs | Unit | Eligible Facts | Notes |
|---|---|---|---:|---|---:|---|
| Assets | ✅ | instant | 0 | USD | 28,448 | Task 2.1 |
| Liabilities | ✅ | instant | 0 | USD | 23,301 | Task 2.1 |
| StockholdersEquity | ✅ | instant | 0 | USD | 26,468 | Task 2.1 |
| CashAndCashEquivalentsAtCarryingValue | ✅ | instant | 0 | USD | 25,065 | Task 2.1 |
| Revenues | ✅ | duration | 4 | USD | 11,168 | Task 2.1; overlaps RevenueFromContract for 766 (cik,fy) pairs — kept distinct |
| ResearchAndDevelopmentExpense | ✅ | duration | 4 | USD | 8,035 | Task 2.1 |
| NetIncomeLoss | ✅ | duration | 4 | USD | 26,263 | Task 2.1 |
| OperatingIncomeLoss | ✅ | duration | 4 | USD | 21,497 | Task 2.1 |
| CostOfRevenue | ✅ | duration | 4 | USD | 4,935 | Task 2.1 |
| GrossProfit | ✅ | duration | 4 | USD | 10,326 | Task 2.1 |
| RevenueFromContractWithCustomerExcludingAssessedTax | ✅ | duration | 4 | USD | 5,721 | New in Task 2.2 — see ASC 606 note below |
| OperatingExpenses | ✅ | duration | 4 | USD | 13,609 | New in Task 2.2 |
| EarningsPerShareBasic | ✅ | duration | 4 | USD | 15,374 | New in Task 2.2 |
| EarningsPerShareDiluted | ✅ | duration | 4 | USD | 14,918 | New in Task 2.2 |
| IncomeTaxExpenseBenefit | ✅ | duration | 4 | USD | 20,399 | New in Task 2.2 |

\* Per-tag eligible counts for the 5 newly-resolved tags, from
`results/phase_2_2_tag_registry_summary.json`'s `per_tag` breakdown.

Full per-tag diagnostics (raw rows, 10-K rows, window rows, qtrs/unit
distributions, own-period alignment rate) are in the tracked summary
JSON, not duplicated here.

## qtrs semantics

Frozen: `instant -> qtrs 0`, `annual duration -> qtrs 4`. No other qtrs
value is permitted (`src/eval/tag_registry.py`'s `_validate_entry` raises
if `qtrs` doesn't match the tag's declared `period_type`) — this project's
truth contract never consumes 10-Q quarterly data, so no quarterly qtrs
value (1/2/3) is ever a valid registry entry.

## The five previously-unresolved tags — individually resolved

### RevenueFromContractWithCustomerExcludingAssessedTax → SUPPORTED

```text
qtrs:        4 (duration) — 6,240 of 6,244 distinct 10-K filings reporting
             this tag report it at qtrs=4 (99.9%)
unit:        USD (verified directly — no non-USD unit issue)
coverage:    2,528 unique eligible CIKs
```

**Material coverage limitation, documented not hidden:** raw coverage by
year is 2016:2, 2017:10, 2018:1690, 2019:2204, 2020:2332 — a real
accounting-standard transition (ASC 606, "Revenue from Contracts with
Customers," became effective for most public companies in fiscal 2018),
not a data-quality defect. **Redundancy diagnostic:** raw (pre-filter)
rows for this tag are dominated by dimensional revenue-stream/segment
breakdowns — one company's single filing contributed ~70 raw rows for one
company-period, of which the existing `segments IS NULL OR segments=''`
rule correctly keeps exactly 1 (verified directly, `cik=1513965`,
`fy=2018`). The segments filter is doing real, necessary work for this
tag specifically, more than for any other of the 15.

### OperatingExpenses → SUPPORTED

```text
qtrs:        4 (duration) — 13,749 of 13,822 distinct filings (99.5%)
unit:        USD (verified directly)
coverage:    4,104 unique eligible CIKs, consistent 2,561-2,869/year
```

No material limitation found.

### EarningsPerShareBasic → SUPPORTED

```text
qtrs:        4 (duration) — 15,769 of 15,801 distinct filings (99.8%)
unit:        USD — this was the Task 2.2 prompt's explicit "especially
             inspect" concern (a "USD/shares" compound unit would have
             required a truth-contract refactor beyond per-tag string
             matching). Verified directly: every uom value for this tag
             in data/xbrl.duckdb is a plain currency code (USD, CAD, AUD,
             EUR, ...), never a compound/divide unit. 613,983 of 614,700
             raw facts are USD.
coverage:    4,201 unique eligible CIKs
```

**Redundancy diagnostic:** raw ROW counts favor `qtrs=1` (79,682) over
`qtrs=4` (48,482) within 10-K filings — the opposite of every other
duration tag. Investigated: one accession alone contributed 126 separate
`qtrs=1` `EarningsPerShareBasic` rows. This is explained by filers
embedding extensive **quarterly EPS footnote schedules** ("selected
quarterly financial data," historically common, though the SEC eliminated
the explicit requirement around 2018) inside the 10-K, each quarter tagged
with the same base concept. The relevant evidence for qtrs selection is
**per-filing dominance** (99.8% of filings use qtrs=4 for their primary
figure), not raw row count, which is inflated by this footnote-schedule
artifact — not evidence that qtrs=1 is the correct annual figure.

### EarningsPerShareDiluted → SUPPORTED

```text
qtrs:        4 (duration) — 15,279 of 15,305 distinct filings (99.8%)
unit:        USD (same verification as EarningsPerShareBasic)
coverage:    4,042 unique eligible CIKs
```

Kept fully distinct from `EarningsPerShareBasic` — no alias, no merge, no
equivalence. A later question generator must be able to ask specifically
about basic or specifically about diluted EPS.

### IncomeTaxExpenseBenefit → SUPPORTED

```text
qtrs:        4 (duration) — 20,831 of 20,898 distinct filings (99.7%)
unit:        USD (verified directly)
coverage:    5,572 unique eligible CIKs — the second-highest coverage of
             all 15 tags after Assets (7,737)
```

No material limitation found.

## Unit semantics — the "critical" check, resolved

Task 2.2's Section 8 explicitly required inspecting whether Task 2.1's
global `uom='USD'` assumption held for every final tag, "especially"
`EarningsPerShareBasic`/`EarningsPerShareDiluted`. **Verified directly
against `data/xbrl.duckdb`: every one of the 15 candidate tags, including
both EPS concepts, uses a plain `USD` (or other plain currency code)
`uom` value — never a `USD/shares`-style compound/divide unit.** The
"critical" concern the task raised turned out not to apply to this
dataset. Nonetheless, the truth contract was refactored so unit is
**driven per-tag by the registry** (`unit_by_tag` in
`build_contract_config()`'s output, `CASE f.tag ... END` in
`eligible_facts()`'s SQL) rather than a single global `MONETARY_UOM`
constant — required regardless of whether today's values differ, because
a registry claiming per-tag authority over unit cannot coexist with code
that independently hardcodes one global unit.

## Overlapping revenue concepts — not merged

`Revenues` and `RevenueFromContractWithCustomerExcludingAssessedTax`
overlap for 766 of 11,450 `Revenues` (cik, fiscal_year) pairs and 766 of
6,238 `RevenueFromContract` pairs (2016-2020) — a small fraction of
either population. Both are kept as **distinct SUPPORTED concepts**,
per Task 2.2's explicit instruction not to merge correlated-but-distinct
accounting concepts. `Revenues` is the older, broader "total revenue"
concept; `RevenueFromContractWithCustomerExcludingAssessedTax` is the
specific post-ASC-606 concept for revenue from customer contracts
(excluding third-party taxes collected). A future question generator
(Task 2.3+) should avoid producing near-duplicate questions for the same
company/period across both tags — noted as a deferred concern, not solved
here (Task 2.2 does not build a synonym/relationship engine).

## Registry schema

```yaml
version: 1
tags:
  <TagName>:
    enabled: true|false      # required, explicit boolean
    period_type: instant|duration   # required
    qtrs: 0|4                # required; must match period_type (0<->instant, 4<->duration)
    unit: USD                # required, non-empty string
    category: balance_sheet|income_statement   # optional
    label: <short human name>                  # optional
    reason: <why this decision>                 # present on every entry in the frozen file
    notes: <known limitations/observations>       # optional
```

`src/eval/tag_registry.py`'s `load_registry()`/`parse_registry()` reject,
never silently skip: a missing file, invalid YAML, a duplicate tag key
(PyYAML's default loader silently keeps the *last* occurrence of a
repeated key — a custom `_DuplicateKeyCheckingLoader` catches this),
missing/invalid `enabled`/`qtrs`/`unit`/`period_type`, an inconsistent
`qtrs`/`period_type` pair, an unsupported schema version, or an empty
registry.

## Truth-contract integration

`src/eval/truth_contract.py`'s `eligible_facts(con, tags)` now asks
`src.eval.tag_registry.get_registry()` for each requested tag's
`qtrs`/`unit`, raising `TruthContractError` for anything not `enabled`
in the registry. `build_contract_config(tags)` embeds
`tag_registry_version` and `tag_registry_hash` directly in its output, so
`compute_contract_config_hash()`'s result (`truth_contract_hash`)
transitively identifies both which truth-contract code ran **and** which
tag-registry semantics were in effect — no result can identify one
without the other. `CONTRACT_VERSION` was bumped `1.0 -> 2.0` to reflect
this structural change (registry-driven qtrs/unit, not a semantic
weakening).

```text
registry_version:      1
registry_hash:            a230373e2a788423026142beb93c5c454a291f23468d46cfb40f5692e48b8070
truth_contract_hash:         8ce68e8f53395f8f983e0002c53e62a31bb121b8551f28e739fcebb7f462988c
                             (over the full 15-tag supported set)
```

Both hashes are deterministic and timestamp-free — verified stable across
repeated loads, and verified to change under a semantic edit (tag added/
removed, `enabled` flipped, `qtrs`/`unit`/`period_type` changed) but
**not** under a comment, formatting, or YAML key-order change.

## Real-data coverage (before/after Task 2.1 → Task 2.2)

```text
before (Task 2.1, 10 tags):   185,506 eligible facts, 28,859 unique accessions, 7,809 unique CIKs
after  (Task 2.2, 15 tags):      255,527 eligible facts, 28,863 unique accessions, 7,810 unique CIKs
delta:                               +70,021 facts, +4 accessions, +1 CIK
```

The delta is almost entirely **more facts about the same already-covered
filings**, not many new companies — expected, since companies reporting
`Assets`/`Revenues` in a 10-K overwhelmingly also report EPS/income-tax/
operating-expense figures in that same filing. Not optimized for size;
the 5 new tags were added because their semantics are defensible, not to
inflate this number (see Core Rule in the Task 2.2 prompt).

## Materiality and period alignment — unchanged

Task 2.2 did not revisit either of Task 2.1's frozen decisions:
materiality/sampling remains entirely out of scope for truth validity
(`PROJECT_EXECUTION.md`'s own Task 2.1 checklist item), and the
`ddate = submissions.period` own-period-only alignment rule was not
weakened to admit comparative/prior-period columns for any tag, even
though doing so would have increased every tag's raw eligible count.

## Real-data summary artifact

```bash
python scripts/audit_eval_tag_registry.py
```

Reads `configs/eval_tags.yaml` and `data/xbrl.duckdb` read-only, writes
only `results/phase_2_2_tag_registry_summary.json` (tracked). Contains
per-tag raw/10-K/window row counts, qtrs and unit distributions,
own-period-alignment rates, eligible counts, and the before/after
comparison above.

## Test commands

```bash
python -m pytest tests/test_tag_registry.py -q      # 34 tests, all portable
python -m pytest tests/test_truth_contract.py -q    # 39 tests (38 portable + 1 local_data)
```

## Independent verification

3 real eligible facts from 3 different companies were manually inspected
for **each** of the 5 newly-resolved tags (15 facts total) — every field
(`coreg`, `segments`, `version`, `uom`, `qtrs`, `form`, `fiscal_year`,
`ddate == submissions.period`) re-queried directly from the raw tables,
never trusting `eligible_facts()` to prove itself. 15/15 confirmed
correct, including plausible per-share dollar values for both EPS
concepts ($0.70, -$0.60, $13.76, ...).

## Known limitations

- `RevenueFromContractWithCustomerExcludingAssessedTax` has near-zero
  coverage before fiscal 2018 (ASC 606 adoption) — a property of the
  accounting-standard timeline, not fixable by this registry.
- `Revenues` and `RevenueFromContractWithCustomerExcludingAssessedTax`
  overlap for a small population of companies/periods — both kept, no
  concept-family/synonym relationship is modeled.
- Only USD-denominated facts are ever eligible; non-USD monetary facts
  (a small fraction of every tag) are excluded entirely, not converted.
- No question templates, materiality/sampling policy, or DEV/TEST split
  exist yet — explicitly deferred (see below).

## What remains intentionally deferred

```text
Task 2.3 — ~3,000-question generation, natural-language templates,
  expected answers, materiality/sampling policy at generation time,
  DEV/TEST split
Task 2.8 — primary-document/inline-XBRL evidence alignment
```

## Next task

Per `PROJECT_EXECUTION.md`: **2.3 — Build the full evaluation dataset.**
