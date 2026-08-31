# Task 2.2 — Freeze Supported Tag Registry

## Phase

**Phase 2 — Make the Numbers Trustworthy**

Task 2.1 is complete.

Current state:

```text
Data Preparation                              — COMPLETE
Phase 0 — Foundation                          — COMPLETE
Phase 1 — Make It Work End to End             — COMPLETE WITH WARN
Phase 2 — Make the Numbers Trustworthy        — IN PROGRESS
  2.1 XBRL Truth Contract                     — COMPLETE
  2.2 Freeze Supported Tag Registry           — CURRENT
```

Known historical Phase 1 warning remains:

```text
Task 1.7a citation-format compliance = 8/10
```

Do not rerun or modify that diagnostic.

---

# Objective

Freeze the authoritative **Phase 2 XBRL evaluation tag registry** in:

```text
configs/eval_tags.yaml
```

The registry must define exactly which XBRL concepts are supported for later evaluation-question generation and, for each supported concept, the semantic information required by the Task 2.1 truth contract.

At minimum this includes:

```text
tag/concept name
expected qtrs
concept type / period type
expected unit
enabled/supported status
```

where supported by the authoritative roadmap.

This task resolves the five tag/qtrs decisions deliberately left open by Task 2.1.

It must also remove the current architectural mismatch where Task 2.1 assumes `uom='USD'` globally even though the final registry may contain concepts whose correct XBRL unit is not USD.

The final result must be a deterministic, versioned, reviewed registry that later Phase 2 tasks can consume without re-deciding tag semantics.

---

# Why This Task Exists

Task 2.1 deliberately stopped at 10 resolved tags.

Current resolved mapping:

```text
Assets                                    -> qtrs 0
Liabilities                               -> qtrs 0
StockholdersEquity                        -> qtrs 0
CashAndCashEquivalentsAtCarryingValue     -> qtrs 0

Revenues                                  -> qtrs 4
ResearchAndDevelopmentExpense             -> qtrs 4
NetIncomeLoss                             -> qtrs 4
OperatingIncomeLoss                       -> qtrs 4
CostOfRevenue                             -> qtrs 4
GrossProfit                               -> qtrs 4
```

Current unresolved candidate tags:

```text
RevenueFromContractWithCustomerExcludingAssessedTax
OperatingExpenses
EarningsPerShareBasic
EarningsPerShareDiluted
IncomeTaxExpenseBenefit
```

Task 2.1 correctly refused to guess their semantics.

Task 2.2 owns resolving those decisions and freezing the resulting registry.

---

# Core Rule

**Do not freeze a tag because we want exactly 15 tags. Freeze it because its semantics are defensible.**

The target is approximately 15 supported concepts according to the roadmap.

However:

```text
correct registry > large registry
```

If one of the candidate concepts cannot be assigned trustworthy semantics from authoritative accounting/XBRL evidence and actual SEC data, it may be explicitly marked unsupported/excluded rather than silently guessed.

If the authoritative `PROJECT_EXECUTION.md` requires all 15, follow that requirement only after establishing defensible semantics for all 15.

---

# 1. Read Authoritative Sources First

Before changing code or configuration, read:

1. `project_plan/PROJECT_EXECUTION.md`
2. `DATA_READINESS_REPORT.md`
3. `project_plan/PHASE2_TRUTH_CONTRACT.md`
4. `src/eval/truth_contract.py`
5. `results/phase_2_1_truth_contract_summary.json`
6. `src/ingest/audit_data.py`
7. `src/ingest/fetch_xbrl.py`
8. relevant tests
9. `Progress.md`

Also inspect:

```text
project_plan/PROJECT_SPEC.md
```

only as secondary context where it has not been superseded.

Do not reintroduce stale data-readiness claims from older documentation.

---

# 2. Establish Baseline

Before modifying anything:

```bash
git branch
git status --short
git log --oneline --decorate -15
python --version
python -c "import sys; print(sys.executable)"
```

Run:

```text
doctor
portable tests
```

Record:

```text
HEAD
working tree state
portable test count
truth-contract config hash
current QTRS_BY_TAG
current UNRESOLVED_CANDIDATE_TAGS
```

Confirm Task 2.1 commit exists.

Expected Task 2.1 reference state is approximately:

```text
portable: 381 passed, 11 deselected
full:     392 passed
eligible facts using resolved 10-tag set: 185,506
```

These are historical reference values, not numbers to force after changing the registry.

---

# 3. Inspect the Candidate Registry

Establish the intended candidate set from repository evidence.

Current known 15 candidates are:

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

Do not silently add concepts beyond this set unless `PROJECT_EXECUTION.md` explicitly defines a different/current registry.

If authoritative documents disagree about the candidate set, document the conflict before proceeding.

---

# 4. Registry Schema

Create:

```text
configs/eval_tags.yaml
```

The registry must have an explicit schema.

A conceptual structure could resemble:

```yaml
version: 1

tags:
  Assets:
    enabled: true
    qtrs: 0
    period_type: instant
    unit: USD
    category: balance_sheet

  Revenues:
    enabled: true
    qtrs: 4
    period_type: duration
    unit: USD
    category: income_statement
```

This structure is illustrative.

Follow existing repository configuration conventions if they differ.

At minimum each supported entry must define enough information so later code does **not** need to infer:

```text
qtrs
period type
unit
support status
```

Recommended additional metadata where useful:

```text
description
statement/category
aliases or overlap notes
reason_supported
```

Do not turn the config into a large accounting ontology.

Keep only information needed for reproducible evaluation.

---

# 5. Resolve qtrs Semantics

The registry must explicitly freeze the expected `qtrs` value for every supported tag.

Task 2.1 established:

```text
qtrs = 0  -> instant
qtrs = 4  -> annual duration
```

Do not infer qtrs during evaluation.

Do not implement logic such as:

```python
if tag looks like balance-sheet concept:
    qtrs = 0
else:
    qtrs = 4
```

Do not derive it from the most common qtrs value at runtime.

The frozen registry must carry the answer.

---

# 6. Resolve the Five Previously Unresolved Tags

Investigate individually:

```text
RevenueFromContractWithCustomerExcludingAssessedTax
OperatingExpenses
EarningsPerShareBasic
EarningsPerShareDiluted
IncomeTaxExpenseBenefit
```

For each one, establish:

```text
instant vs duration semantics
expected qtrs
expected unit
real SEC coverage
real qtrs distribution
real unit distribution
whether it behaves consistently enough for evaluation
```

Do not approve them as a group without inspecting each separately.

---

# 7. Real-Data Evidence

Use:

```text
data/xbrl.duckdb
```

read-only.

For every candidate tag calculate at minimum:

```text
total raw rows
rows for form='10-K'
rows for fiscal_year 2016-2020
qtrs distribution
uom distribution
version/taxonomy distribution
coreg-null rate
segments-null rate
own-period alignment rate
non-null value rate
unique CIK count
unique accession count
```

Also compute eligible count under Task 2.1 truth validity for every tag once its semantics are specified.

Do not use total raw row count as evidence that a tag is trustworthy.

Coverage and semantic consistency are different things.

---

# 8. Unit Semantics — Critical

Task 2.1 currently applies:

```text
uom = 'USD'
```

to its 10 monetary concepts.

Task 2.2 must determine whether that rule remains correct for every final supported tag.

Do not assume all 15 concepts are USD-denominated.

Inspect actual `uom` distributions for each candidate.

Especially inspect:

```text
EarningsPerShareBasic
EarningsPerShareDiluted
```

carefully.

If their correct evaluation unit differs from ordinary USD monetary facts, the registry must express the correct per-tag unit semantics.

Do NOT:

```text
force EPS facts through uom='USD'
exclude valid tags merely because Task 2.1 used USD globally
silently convert units
strip denominator semantics
```

If the final registry contains multiple expected units, refactor the truth contract narrowly so eligibility is driven by the registry's per-tag unit requirement.

This is an allowed Task 2.2 change because the registry cannot be authoritative while the truth contract independently hardcodes incompatible unit semantics.

---

# 9. Refactor Hardcoded qtrs Ownership

Task 2.1 currently contains:

```text
QTRS_BY_TAG
UNRESOLVED_CANDIDATE_TAGS
```

inside:

```text
src/eval/truth_contract.py
```

After Task 2.2, `configs/eval_tags.yaml` should become the authoritative registry.

Do not leave two competing registries.

The production path should have one source of truth:

```text
configs/eval_tags.yaml
        ↓
registry loader
        ↓
truth contract
        ↓
later question generator
```

A compatibility constant derived from the registry may be acceptable if existing APIs require it, but it must not become a second manually maintained list.

The YAML registry owns the semantic values.

---

# 10. Implement a Registry Loader

Create an appropriate implementation under `src/eval/`, for example:

```text
src/eval/tag_registry.py
```

or follow the existing repository architecture if `PROJECT_EXECUTION.md` specifies another location.

The loader should:

```text
load configs/eval_tags.yaml
validate schema
reject duplicate tags
validate qtrs
validate period_type
validate unit
validate enabled status
return deterministic ordered registry
```

It should fail loudly on malformed configuration.

Do not silently skip invalid entries.

Suitable errors include:

```text
missing qtrs
invalid qtrs
missing unit
unknown period type
duplicate tag
empty registry
unsupported schema version
```

---

# 11. Registry Validation Rules

At minimum verify:

### Tag

```text
non-empty
unique
exact concept spelling
```

### qtrs

For current annual 10-K evaluation:

```text
instant -> 0
annual duration -> 4
```

Do not permit arbitrary qtrs values without explicit roadmap justification.

### period_type

Expected values should be explicit, e.g.:

```text
instant
duration
```

### unit

Must be explicit for every supported numeric concept.

Examples may include:

```text
USD
<other verified XBRL unit>
```

Do not invent unit labels.

Use what the actual data and approved semantics support.

### enabled

Must be explicit or have a documented deterministic default.

---

# 12. Supported vs Candidate vs Excluded

Avoid ambiguous registry states.

Every candidate concept should end Task 2.2 in one of two clear states:

```text
SUPPORTED
EXCLUDED
```

If excluded, document why.

Possible defensible reasons include:

```text
ambiguous semantics
insufficient coverage
inconsistent qtrs
inconsistent unit
overlap/redundancy that would distort category balance
truth-contract incompatibility
```

Do not use:

```text
TODO
maybe
probably
unresolved
```

in the final frozen registry.

The purpose of this task is to make the decision.

---

# 13. Overlapping Revenue Concepts

Inspect carefully the relationship between:

```text
Revenues
RevenueFromContractWithCustomerExcludingAssessedTax
```

These concepts may overlap semantically across filers/taxonomy versions.

Do not automatically merge them.

Do not assume they are interchangeable.

Determine:

- whether both should remain separate supported concepts;
- whether one acts as a newer/common alternative;
- whether including both causes duplicate/equivalent question populations for some companies;
- whether future question generation needs a concept-family relationship.

If the roadmap already specifies how to handle them, follow it.

Otherwise document the observed overlap and choose the smallest reproducible registry representation necessary for later evaluation.

Do not build a general synonym engine in this task.

---

# 14. EPS Concepts

Treat:

```text
EarningsPerShareBasic
EarningsPerShareDiluted
```

as distinct concepts.

Do not collapse basic and diluted EPS.

Verify separately:

```text
qtrs
unit
coverage
own-period alignment
eligible population
```

If supported, later evaluation must be able to distinguish a question asking basic EPS from diluted EPS.

Do not allow a registry alias that makes them equivalent.

---

# 15. Materiality Remains Out of Scope

Task 2.1 established an important architectural decision:

```text
truth validity != materiality/sampling policy
```

Do not add:

```text
min_magnitude
percentile threshold
large-cap threshold
sampling weight
```

to truth eligibility in this task.

If later evaluation generation needs materiality filtering, it belongs to the appropriate later Phase 2 sampling/generation task.

Do not modify Task 2.1's decision.

---

# 16. Period Alignment Remains Unchanged

Task 2.1 established:

```text
ddate = submissions.period
```

for own-period facts.

Do not weaken that rule merely to increase tag coverage.

Do not include comparative prior-period columns because a candidate tag otherwise produces fewer eligible facts.

Registry support should be measured **after** the existing truth contract, not achieved by weakening it.

---

# 17. Registry Versioning

The registry is a benchmark-defining artifact.

Give it a version.

For example:

```text
registry_version: 1
```

or whatever scheme matches repository conventions.

Compute a deterministic semantic hash over the registry.

The hash should change if any meaningful evaluation semantic changes, such as:

```text
supported tag set
qtrs
period type
unit
enabled status
```

It should NOT change because of:

```text
timestamp
Git SHA
formatting
YAML comment order
runtime
```

Use a canonicalized representation for hashing.

---

# 18. Truth Contract Hash Interaction

Task 2.1 currently produces:

```text
truth_contract_config_hash
```

After moving tag semantics into `eval_tags.yaml`, determine the correct provenance model.

At minimum, later evaluation must be able to identify both:

```text
truth-contract semantics
tag-registry semantics
```

Acceptable designs include:

```text
truth_contract_hash
tag_registry_hash
```

or a truth-contract hash that deterministically incorporates the tag-registry hash.

Follow existing artifact-versioning conventions.

Avoid ambiguous provenance where a result says which truth-contract code ran but not which tag registry was used.

---

# 19. Real-Data Registry Audit

Create a script such as:

```text
scripts/audit_eval_tag_registry.py
```

or use the location specified by existing architecture.

It must read:

```text
configs/eval_tags.yaml
data/xbrl.duckdb
```

and generate a small tracked result such as:

```text
results/phase_2_2_tag_registry_summary.json
```

The output should include at least:

```text
registry_version
registry_hash

candidate_tag_count
supported_tag_count
excluded_tag_count

per tag:
  enabled
  qtrs
  period_type
  unit

  raw_rows
  10k_rows
  2016_2020_rows
  qtrs_distribution
  unit_distribution
  eligible_rows
  unique_ciks
  unique_accessions
  own_period_alignment_rate

total eligible facts
total unique CIKs
total unique accessions

truth_contract_hash/reference
git_sha
created_at_utc
```

Keep timestamps outside semantic hashes.

---

# 20. Compare Before and After Task 2.2

Task 2.1's 10-tag eligible population was:

```text
185,506 eligible facts
28,859 unique accessions
7,809 unique CIKs
```

After freezing the registry, rerun Task 2.1 eligibility using the final supported registry.

Do not require the resulting values to be larger.

Report:

```text
before
after
delta
```

for:

```text
supported tags
eligible facts
unique accessions
unique CIKs
```

Explain why the population changed.

Do not optimize the registry for the largest eligible count.

---

# 21. Independent Semantic Verification

For every supported tag, manually or independently inspect real examples.

At minimum select:

```text
3 eligible facts per newly resolved tag
```

from different companies where possible.

Verify directly:

```text
tag
company
adsh
form
fiscal_year
ddate
submission period
qtrs
uom
value
coreg
segments
taxonomy version
```

For the five previously unresolved candidates, perform extra scrutiny.

Do not use the registry loader itself as the sole proof that the registry is correct.

---

# 22. Coverage Diagnostics

For every supported tag report coverage by:

```text
year
company/CIK
accession
```

for fiscal years:

```text
2016
2017
2018
2019
2020
```

Look for pathological cases such as:

```text
tag exists almost entirely in one year
tag exists for very few companies
tag suddenly disappears after taxonomy changes
one qtrs value dominates except for major anomalies
unexpected unit variation
```

Do not automatically reject a tag because it is less common.

But document material coverage limitations.

---

# 23. Redundancy Diagnostics

Check whether two supported concepts create substantial semantic or filing-level overlap.

Particularly inspect:

```text
Revenues
RevenueFromContractWithCustomerExcludingAssessedTax
```

and:

```text
EarningsPerShareBasic
EarningsPerShareDiluted
```

Do not remove legitimate distinct concepts solely because they correlate.

The goal is to detect accidental duplicate benchmark semantics, not eliminate accounting distinctions.

---

# 24. No Question Generation Yet

Task 2.2 freezes the registry only.

Do NOT:

```text
generate the ~3,000 questions
create natural-language templates
create expected answers
sample questions
create DEV/TEST split
create chunk relevance labels
parse primary docs
perform inline-XBRL alignment
run retrieval evaluation
```

Those belong to later Phase 2 tasks.

---

# 25. No LLM / Network Requirement

This task should remain deterministic and local.

Do not use:

```text
OpenRouter
OpenAI
Anthropic
LLMs
SEC downloads
Hugging Face downloads
web APIs
```

Use:

```text
repository decisions
frozen XBRL data
existing SEC metadata already stored
deterministic accounting/XBRL semantics already available to the project
```

No API credits should be spent.

---

# 26. Tests

Add comprehensive registry tests, likely:

```text
tests/test_tag_registry.py
```

and update:

```text
tests/test_truth_contract.py
```

where needed.

At minimum test:

### Config loading

```text
valid registry loads
missing file fails clearly
invalid YAML fails clearly
empty registry rejected
```

### Schema

```text
duplicate tag rejected
missing qtrs rejected
invalid qtrs rejected
missing unit rejected
invalid period_type rejected
invalid enabled/status value rejected
```

### Semantic consistency

```text
instant -> qtrs 0
annual duration -> qtrs 4
supported tag has explicit unit
all candidate tags accounted for
no unresolved candidate remains
```

### Determinism

```text
same registry -> same canonical form
same registry -> same hash
comment/formatting-only YAML change -> same semantic hash if parser semantics permit
semantic change -> different hash
```

### Truth-contract integration

```text
eligible_facts consumes registry semantics
qtrs no longer maintained independently in two places
per-tag unit is respected
unsupported tag rejected clearly
unknown tag rejected clearly
```

### EPS/unit behavior

If EPS is supported:

```text
valid EPS unit accepted
ordinary USD fact does not incorrectly satisfy EPS unit rule
```

Use the actual verified unit.

Do not hardcode a guessed value in this prompt.

### Regression

```text
the original 10 known mappings remain unchanged unless authoritative evidence explicitly requires correction
```

---

# 27. Real-Data Integration Test

Add at least one `local_data`-marked integration test that:

1. loads `configs/eval_tags.yaml`;
2. opens `data/xbrl.duckdb` read-only;
3. runs the truth contract over all supported tags;
4. verifies a non-empty eligible set;
5. confirms every returned tag is supported;
6. confirms every returned qtrs matches registry;
7. confirms every returned unit matches registry;
8. confirms period alignment;
9. confirms `coreg` and `segments` rules;
10. confirms deterministic ordering.

Do not make this part of the lightweight portable suite if it scans substantial local data.

---

# 28. Independent Registry Count Check

Independently verify:

```text
candidate count
supported count
excluded count
```

without relying solely on the registry loader's own summary.

If target candidate count is 15, assert:

```text
supported + excluded = 15
```

and:

```text
unresolved = 0
```

unless the authoritative roadmap explicitly changes the candidate set.

---

# 29. Frozen Data Safety

Verify before and after:

```text
data/xbrl.duckdb size
facts row count
submissions row count
```

Task 2.1 reference:

```text
size:        7,011,053,568 bytes
facts:       90,685,753
submissions: 218,166
```

Do not write into the database.

Do not add tables or indexes to it.

Do not modify raw XBRL ZIPs.

---

# 30. Phase 1 Regression Gate

Confirm no unintended changes to:

```text
src/retrieval/
src/generation/
src/index/
src/embeddings/
src/chunk/
src/normalize/
src/eval/citation_integrity.py
src/eval/smoke_dataset.py
src/eval/baseline_metrics.py
src/cli/
Phase 1 configs/results
```

Do not rerun Task 1.7a's frozen 10-case generation diagnostic.

Its 8/10 result remains historical evidence.

---

# 31. Task 2.1 Regression Gate

Verify Task 2.2 does not weaken Task 2.1's truth validity rules:

```text
10-K only
2016-2020
standard us-gaap taxonomy
coreg blank
segments blank
correct unit per tag
correct qtrs per tag
value valid/finite
ddate = submissions.period
same-accession duplicate safety
filing/accession provenance
no materiality filter
```

Changes needed to replace global qtrs/unit assumptions with registry-driven semantics are allowed.

Semantic weakening is not.

---

# 32. Documentation

Create:

```text
project_plan/PHASE2_TAG_REGISTRY.md
```

Document:

- objective
- authoritative candidate set
- final supported set
- excluded set, if any
- qtrs semantics
- period-type semantics
- unit semantics
- five previously unresolved decisions
- real-data coverage
- overlapping-concept observations
- registry version
- registry hash
- truth-contract integration
- test commands
- known limitations
- what remains intentionally deferred

Include a concise table:

| Tag | Supported | Period Type | qtrs | Unit | Eligible Facts | Notes |
|---|---|---|---:|---|---:|---|

Populate with actual observed values.

---

# 33. Repository Structure Documentation

Update narrowly:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

to add:

```text
configs/eval_tags.yaml
src/eval/tag_registry.py
```

if that is the chosen implementation location.

Do not mark later Phase 2 components implemented.

---

# 34. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.2 Freeze Supported Tag Registry
```

Include:

```text
Objective
Initial state
Authoritative sources
Candidate registry
Five unresolved decisions
Real-data qtrs diagnostics
Real-data unit diagnostics
Final supported registry
Excluded tags/reasons
Truth-contract integration changes
Registry version/hash
Before/after eligible population
Independent checks
Tests
Frozen-data safety
Phase 1 regression
Task 2.1 regression
Files modified
Git
Result
Phase status
```

Do not rewrite old entries.

---

# 35. Likely Files

Expected files may include:

```text
configs/eval_tags.yaml                         new
src/eval/tag_registry.py                      new
src/eval/truth_contract.py                    modified narrowly
tests/test_tag_registry.py                    new
tests/test_truth_contract.py                  updated
scripts/audit_eval_tag_registry.py            new
results/phase_2_2_tag_registry_summary.json   new
project_plan/PHASE2_TAG_REGISTRY.md           new
project_plan/REPOSITORY_STRUCTURE.md           updated
Progress.md                                   appended
```

Use repository architecture as the final authority.

Do not create unnecessary files merely to match this list.

---

# 36. Acceptance Criteria

Task 2.2 is complete only when:

```text
[ ] configs/eval_tags.yaml exists
[ ] registry has explicit version
[ ] candidate set established from authoritative evidence
[ ] every candidate has a final supported/excluded decision
[ ] no unresolved candidate remains
[ ] every supported tag has explicit qtrs
[ ] every supported tag has explicit period type
[ ] every supported tag has explicit unit
[ ] five Task 2.1 unresolved tags have been individually resolved
[ ] real qtrs distributions inspected
[ ] real unit distributions inspected
[ ] real coverage inspected
[ ] Revenue vs RevenueFromContract overlap reviewed
[ ] Basic vs diluted EPS remain distinguishable if supported
[ ] registry loader validates configuration
[ ] truth contract consumes registry semantics
[ ] no duplicate manually-maintained qtrs registry remains
[ ] no incompatible global unit assumption remains
[ ] Task 2.1 truth validity is not weakened
[ ] registry hash is deterministic
[ ] registry provenance is recorded
[ ] real-data summary artifact exists
[ ] before/after eligible counts recorded
[ ] independent verification completed
[ ] unit tests pass
[ ] real-data integration test passes
[ ] frozen XBRL database unchanged
[ ] Phase 1 regression gate passes
[ ] Task 2.1 regression gate passes
[ ] no network/LLM/API calls
[ ] documentation updated
[ ] Progress.md appended
[ ] secret scan clean
[ ] git add -n . safe
[ ] coherent Task 2.2 commit created
```

Do not mark Task 2.2 COMPLETE if semantic decisions remain unresolved.

---

# 37. Commit

Inspect:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Confirm no:

```text
data
artifacts
.venv
.env
credentials
large runtime files
```

would be staged.

Run the full required tests.

Then create one coherent commit.

Suggested message:

```text
Freeze Phase 2 evaluation tag registry
```

Do not tag Phase 2 complete.

Do not push unless a real configured remote exists and current Git conventions require it.

---

# 38. Final Console Summary

Print:

```text
PHASE 2.2 — FREEZE SUPPORTED TAG REGISTRY
=========================================

Candidate tags:              <count>
Supported tags:              <count>
Excluded tags:               <count>
Unresolved tags:             0

Registry:
  path:                      configs/eval_tags.yaml
  version:                   <version>
  hash:                      <hash>

Previously unresolved:
  RevenueFromContractWithCustomerExcludingAssessedTax
      qtrs:                  <value/status>
      unit:                  <value/status>
      result:                SUPPORTED / EXCLUDED

  OperatingExpenses
      qtrs:                  <value/status>
      unit:                  <value/status>
      result:                SUPPORTED / EXCLUDED

  EarningsPerShareBasic
      qtrs:                  <value/status>
      unit:                  <value/status>
      result:                SUPPORTED / EXCLUDED

  EarningsPerShareDiluted
      qtrs:                  <value/status>
      unit:                  <value/status>
      result:                SUPPORTED / EXCLUDED

  IncomeTaxExpenseBenefit
      qtrs:                  <value/status>
      unit:                  <value/status>
      result:                SUPPORTED / EXCLUDED

Truth-contract integration:  PASS
Registry validation:         PASS
Independent verification:    PASS
Frozen-data safety:          PASS
Phase 1 regression:          PASS
Task 2.1 regression:         PASS

Before:
  tags:                      10
  eligible facts:            185,506

After:
  tags:                      <count>
  eligible facts:            <count>

Tests:
  portable:                  <result>
  full:                      <result>

FINAL RESULT:
PASS / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
<exact Task 2.3 name from PROJECT_EXECUTION.md>
```

---

# Final Principle

The registry is part of the benchmark definition.

Once frozen, later retrieval experiments will be compared against it.

Therefore:

**Do not choose tag semantics to improve benchmark size, retrieval recall, or final scores.**

Choose them because they correctly represent the financial concept.

Do not infer semantics dynamically at evaluation time.

Do not leave two sources of truth.

Do not weaken Task 2.1 to make more facts eligible.

At the end of Task 2.2, a future developer should be able to open:

```text
configs/eval_tags.yaml
```

and answer, without reading implementation code:

```text
Which XBRL concepts do we evaluate?
What kind of accounting facts are they?
What qtrs value is valid?
What unit is valid?
Which candidates were excluded?
Which registry version produced this benchmark?
```

That is the completion standard.