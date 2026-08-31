# Task 2.1 — XBRL Truth Contract

## Phase

**Phase 2 — Make the Numbers Trustworthy**

This is the **first Phase 2 implementation task**.

Phase 1 has already been independently verified complete with one accepted non-blocking warning:

```text
Task 1.7a citation-format compliance = 8/10
```

Do not attempt to fix, rerun, reinterpret, or otherwise modify that Phase 1 warning during this task.

---

# Objective

Implement the project's **single authoritative XBRL truth contract**:

```text
src/eval/truth_contract.py
```

The truth contract defines exactly which rows from the SEC XBRL `facts` data are eligible to become ground-truth numeric facts in later Phase 2 evaluation-question generation.

This task exists because a raw XBRL row being technically valid does **not** mean it is suitable evaluation ground truth.

The same `(company, tag, year)` can contain:

- consolidated facts
- segment facts
- subsidiary/co-registrant facts
- different units
- instant vs duration values
- quarterly vs annual values
- duplicate rows
- same-accession duplicates
- cross-filing revisions
- custom taxonomy extensions
- facts for the wrong reporting period
- immaterial values

Phase 2 must prevent those ambiguities from silently creating incorrect evaluation questions.

The contract implemented here must become the **single source of truth** used by all later Phase 2 generators and validators.

---

# Authoritative Sources

Before modifying code, read the repository in this order and determine the current source-of-truth hierarchy:

1. `project_plan/PROJECT_EXECUTION.md`
2. `DATA_READINESS_REPORT.md`
3. `project_plan/REVIEW_RESOLUTIONS.md`
4. `project_plan/PROJECT_SPEC.md`
5. `Progress.md`
6. existing Phase 1 evaluation code/config/results

Also inspect:

```text
src/ingest/audit_data.py
src/ingest/fetch_xbrl.py
src/eval/
tests/
configs/
data/xbrl.duckdb
```

Use the **current authoritative execution/data-readiness documents** when older documentation contains stale numeric claims.

Do not blindly copy historical numbers from an older document.

---

# Critical Historical Correction

One especially important stale statement exists in earlier project planning.

The original analysis called this:

```text
restatement rate = 23.56%
```

That metric was later independently audited and found to measure the wrong population.

The frozen corrected interpretation is:

```text
cross-filing value-revision rate — all tags:
7.87%

cross-filing value-revision rate — standard non-abstract tags:
8.00%

cross-filing value-revision rate — 15-tag registry:
10.39%
```

The correction came from using stricter comparability:

```text
coreg blank
segments blank
same unit
cross-accession comparison only
same-accession duplicate rows collapsed first
```

The data does **not** establish that every changed value is a formal accounting restatement.

Therefore:

```text
DO NOT call the 23.56% value the current restatement rate.
DO NOT encode logic based on that stale headline number.
DO NOT use “restatement” where “cross-filing value revision” is the accurate concept.
```

The underlying policy of anchoring later evaluation questions to a specific filing/accession may still be valid, but the old numeric interpretation must not be resurrected.

---

# Scope

This task implements:

```text
XBRL fact eligibility
```

It does **not**:

- generate evaluation questions
- create the ~3,000-question benchmark
- create DEV/TEST splits
- perform evidence/chunk alignment
- parse primary filing HTML
- create inline-XBRL chunk labels
- implement BM25
- implement hybrid retrieval
- implement reranking
- implement CRAG
- implement router logic
- modify generation
- modify citation behavior
- optimize retrieval
- change Phase 1 artifacts
- begin Phase 3

Do not expand this task into the rest of Phase 2.

---

# 1. Establish Baseline

Before changing anything, inspect and record:

```bash
git branch
git status --short
git log --oneline --decorate -15
python --version
python -c "import sys; print(sys.executable)"
```

Confirm:

- current branch
- current HEAD
- project `.venv` is active
- Phase 1 is complete
- no Phase 2 implementation already exists that would conflict with this task
- `data/xbrl.duckdb` exists
- XBRL DB opens read-only
- current portable/full test baseline
- frozen source data remains unchanged

Run the project's existing doctor command.

Run the portable test suite before implementation.

Record the exact baseline.

---

# 2. Inspect the Real XBRL Schema

Do not implement the truth contract from documentation alone.

Open:

```text
data/xbrl.duckdb
```

read-only and inspect the actual:

```text
facts
submissions
```

schemas.

Confirm the real names/types/meaning of fields required by the truth contract.

At minimum inspect availability and behavior of:

```text
adsh
tag
version
ddate
qtrs
uom
coreg
segments
value
cik
form
fy / fiscal_year
period
filed
```

Do not guess column names.

If documentation and the database schema disagree, document the discrepancy before proceeding.

Do not mutate the database.

---

# 3. Eligibility Contract

A fact may be returned as evaluation-eligible only when **all applicable truth-contract rules pass**.

The intended contract includes the following.

---

## 3.1 Consolidated entity only

Exclude subsidiary/co-registrant-specific rows.

Equivalent conceptual requirement:

```text
coreg IS NULL / blank
```

Inspect the real stored representation before deciding whether the implementation must treat:

```text
NULL
""
whitespace
```

as equivalent.

Do not assume.

Test the real data.

---

## 3.2 No segment/dimensional facts

Exclude business-segment or dimensional breakdowns.

Conceptually:

```text
segments IS NULL / blank
```

Again, inspect how absence is actually encoded.

This is especially important because the earlier audit established that segment/dimensional rows form a very large part of raw XBRL facts and materially distort comparisons if treated as consolidated facts.

---

## 3.3 Standard taxonomy only

For the Phase 2 truth set, use the approved standard taxonomy semantics.

Historical contract:

```text
version = 'us-gaap'
```

Verify how this appears in the real dataset and current execution plan.

Do not silently accept arbitrary custom-extension concepts unless current authoritative documentation explicitly permits them.

---

## 3.4 Correct units

For monetary evaluation tags, enforce the approved monetary unit.

Historically:

```text
uom = 'USD'
```

Do not incorrectly apply this to non-monetary tags if the eventual registry contains them.

Unit semantics must be explicit and testable.

Never compare facts across incompatible units.

---

# 4. Per-Tag Period Semantics

`qtrs` is not globally interchangeable.

Examples already established by the project:

```text
qtrs = 0 → instant fact
qtrs = 1 → single-quarter duration
qtrs = 4 → annual duration
```

Known mappings include:

```text
Assets                                   -> 0
Liabilities                              -> 0
StockholdersEquity                       -> 0
CashAndCashEquivalentsAtCarryingValue    -> 0

Revenues                                 -> 4
ResearchAndDevelopmentExpense            -> 4
NetIncomeLoss                            -> 4
OperatingIncomeLoss                      -> 4
CostOfRevenue                            -> 4
GrossProfit                              -> 4
```

The project calls for a **15-tag evaluation registry**.

### Important

Do NOT invent the remaining tags or their `qtrs` values.

Before implementing a complete registry:

1. search current repository documentation/configuration for the authoritative 15-tag set;
2. verify each tag against current project decisions and real XBRL coverage;
3. verify its intended `qtrs` semantics.

If the repository still does **not** resolve all 15 tags or their `qtrs` mappings, STOP before inventing them and report exactly what is unresolved.

A missing project decision is not permission to make one.

---

# 5. Reporting-Period Alignment

A fact's date must correspond to the filing/reporting period required by the truth contract.

The earlier review specifically rejected the loose rule:

```text
ddate merely occurs somewhere in fiscal year
```

The contract requires appropriate alignment to the filing's period end.

Inspect the actual relationship among:

```text
facts.ddate
submissions.period
submissions.fy
submissions.file-dates
```

and the current authoritative roadmap.

Implement the currently approved semantic relationship exactly.

Do not pick whichever field produces the highest match rate.

The data-readiness audit previously emphasized this principle when choosing `fy` for EDGAR↔XBRL alignment: semantic correctness comes before maximizing coverage.

---

# 6. Value Validity

Eligible facts must have:

```text
value IS NOT NULL
```

Also verify:

- value is numerically usable
- no NaN/Inf equivalent reaches the truth set
- decimal/numeric conversion is deterministic
- sign is preserved
- zero values are not silently discarded unless a documented rule says so

Do not normalize negative numbers into positive values.

Accounting values can legitimately be negative.

---

# 7. Materiality

The project requires a materiality filter so evaluation questions are not dominated by trivial line items.

Historical review guidance suggested:

```text
abs(value) >= 1_000_000
```

for large-company questions, while also noting that a percentile-based rule could be considered.

That guidance is a **decision point**, not permission to silently choose whichever rule is convenient.

First inspect:

```text
PROJECT_EXECUTION.md
DATA_READINESS_REPORT.md
current configs
current Phase 2 decisions
```

If the authoritative current plan freezes:

```text
min_magnitude = 1_000_000
```

implement it exactly.

If materiality is still unresolved, STOP and surface the decision instead of silently inventing one.

If implemented, expose the magnitude threshold explicitly through the contract API/config rather than burying it as an unexplained SQL literal.

Expected conceptual interface:

```python
eligible_facts(
    con,
    tags,
    min_magnitude=...
)
```

---

# 8. Same-Accession Duplicate Handling

The data-readiness audit established that comparisons must not mistake duplicate representations inside the same filing for cross-filing value revisions.

Design the contract so same-accession duplicates are handled deterministically.

Before implementing the rule:

- inspect the full XBRL fact key
- inspect duplicate examples
- understand whether duplicates differ in irrelevant fields
- inspect `audit_data.py`'s already-validated methodology

Do not create a new incompatible definition.

Where equivalent rows within the same accession represent the same fact/value, collapse or deduplicate according to the current audited methodology.

Do not silently choose between genuinely conflicting same-accession values.

If such conflicts exist and no repository policy resolves them, report them.

---

# 9. Cross-Filing Value Revisions

Do not globally select one “canonical” value across multiple filings reporting the same historical period unless the authoritative current plan explicitly defines such a rule.

When distinct `adsh` filings report different values for otherwise comparable facts, preserve enough identity/provenance to distinguish them.

Later evaluation question generation should be capable of anchoring a question to a specific filing/accession.

Therefore an eligible fact must preserve, at minimum, the identifying provenance required to distinguish:

```text
company
concept/tag
reporting period
qtrs
unit
filing/accession (adsh)
value
```

Do not collapse away `adsh`.

---

# 10. Single Source of Truth

The truth contract must live in:

```text
src/eval/truth_contract.py
```

The central eligibility logic must be implemented **once**.

Expected conceptual structure:

```python
QTRS_BY_TAG = {
    ...
}

def eligible_facts(
    con,
    tags,
    *,
    min_magnitude=...
):
    """
    Return only XBRL facts permitted to become evaluation ground truth.
    """
    ...
```

The exact API may differ if current repository conventions strongly favor another design, but there must be one clearly identifiable authoritative implementation.

Do not:

```text
copy the eligibility SQL into scripts
copy it into validators
copy it into question generators
copy it into tests as a second production implementation
```

Later code must import/reuse the contract.

Tests may independently calculate expected values for verification, but they must not create a competing production truth definition.

---

# 11. Deterministic Output

For identical:

```text
database
tag registry
truth-contract config
```

the eligible fact set must be deterministic.

Define deterministic ordering.

Do not depend on DuckDB's incidental physical row ordering.

When returning rows, use an explicit stable sort/key.

Suitable identifying fields may include combinations of:

```text
adsh
tag
ddate
qtrs
uom
```

Use the actual approved grain established after inspecting the data.

---

# 12. Truth-Contract Provenance

The output/summary must make the contract reproducible.

Create an appropriate deterministic config/provenance representation containing at least:

```text
contract version
allowed tags / tag-registry reference
qtrs mapping
taxonomy rule
unit rule
coreg rule
segments rule
date/period rule
materiality rule
dedup rule
source database identity
```

Compute a deterministic hash for the contract configuration if this matches the project's existing artifact-versioning conventions.

Do not hash timestamps into semantic configuration hashes.

Do not make a config hash change merely because the run occurred later.

---

# 13. Implementation Result Artifact

Create a small tracked result/summary artifact, following existing project conventions, for example:

```text
results/phase_2_1_truth_contract_summary.json
```

Do not store the full eligible XBRL population in Git.

The summary should contain useful diagnostics such as:

```text
source fact count
eligible fact count
rejected count

counts rejected by:
- coreg
- segments
- taxonomy/version
- unit
- qtrs
- date/period
- null/invalid value
- materiality

eligible counts by tag
eligible counts by year
eligible counts by qtrs
unique accessions
unique CIKs

same-accession duplicates encountered
cross-accession comparable groups
cross-filing value-revision diagnostics

truth_contract_config_hash
git_sha
created_at_utc
```

Do not claim filtering reasons are mutually exclusive unless implementation actually measures them that way.

If rejection diagnostics overlap, label them clearly as independent diagnostic counts rather than additive partitions.

---

# 14. Do Not Reproduce the Stale Metric

As part of implementation verification, explicitly check that documentation/result output does not reintroduce:

```text
23.56% restatement rate
```

as a current Phase 2 fact.

Current frozen data-readiness evidence uses:

```text
cross-filing value-revision
```

and treats comparable facts much more strictly.

If your Task 2.1 diagnostics produce a different number from the frozen 7.87% / 10.39% values, do not force them to match.

Investigate whether:

- the population differs
- tag filtering differs
- qtrs filtering differs
- materiality changed the denominator
- same-accession dedup differs
- period-end filtering differs

Then document why.

Never alter the algorithm just to reproduce an expected number.

---

# 15. Tests

Create comprehensive tests, likely:

```text
tests/test_truth_contract.py
```

Follow repository testing conventions.

At minimum cover:

### Consolidation

```text
coreg null/blank accepted when otherwise valid
coreg populated rejected
segments null/blank accepted
segments populated rejected
```

### Taxonomy

```text
us-gaap accepted
custom taxonomy rejected
```

### Units

```text
USD monetary fact accepted
wrong monetary unit rejected
```

### qtrs

```text
instant tag with qtrs=0 accepted
instant tag with qtrs=4 rejected
annual-duration tag with qtrs=4 accepted
annual-duration tag with qtrs=0 rejected
unknown/unregistered tag handled explicitly
```

### Period alignment

```text
ddate matching required period accepted
wrong-period fact rejected
```

### Values

```text
null value rejected
valid positive accepted
valid negative accepted
zero behavior matches documented contract
```

### Materiality

```text
abs(value) below threshold rejected
positive value at threshold accepted
negative value at threshold accepted
custom threshold behaves deterministically
```

### Filing identity

```text
different adsh values remain distinguishable
cross-filing revisions are not silently collapsed into one canonical value
```

### Duplicate handling

```text
same-accession equivalent duplicates handled deterministically
```

### Determinism

```text
same inputs → same rows
same inputs → same ordering
same semantic config → same contract hash
```

### Security / mutation

```text
truth contract performs no writes to frozen XBRL database
```

---

# 16. Real-Data Integration Tests

In addition to unit tests, add a small real-data integration test using:

```text
data/xbrl.duckdb
```

under the project's existing local-data marker/convention.

The integration test should verify real behavior such as:

- eligible result is non-empty
- only approved tags appear
- no prohibited `coreg`
- no prohibited `segments`
- correct qtrs per tag
- correct units
- no null values
- magnitude condition
- period alignment
- required provenance fields present

Do not scan all 90M facts in every ordinary portable test.

Keep expensive/full-data work appropriately marked.

---

# 17. Independent Verification

After implementation, verify the contract independently from the implementation itself.

For a deterministic sample of eligible rows:

1. select at least 20 facts across multiple tags;
2. inspect their original rows directly from DuckDB;
3. manually or independently confirm every eligibility condition.

Also select deterministic rejected examples for several major rejection reasons and confirm they were rejected correctly.

Do not use `eligible_facts()` itself to prove `eligible_facts()` is correct.

For at least one aggregate, compute the value using a separate one-off query/calculation and compare it with the production output.

---

# 18. Performance

This task is evaluation infrastructure, not a production-serving benchmark.

Still record:

```text
eligible_facts runtime
source rows considered
eligible rows returned
```

Avoid obviously pathological query patterns.

Do not add indexes to the frozen XBRL database merely to improve this task's runtime unless explicitly approved.

Do not mutate XBRL storage.

---

# 19. Frozen Data Safety

Before and after implementation verify that:

```text
data/xbrl.duckdb
```

was not modified.

At minimum compare:

```text
file size
modification behavior if meaningful
relevant table row counts
```

Prefer a stronger checksum if already used by project conventions and practical.

Also confirm no raw XBRL ZIPs or EDGAR data were modified.

Phase 2 reads frozen data.

It does not rewrite it.

---

# 20. No Network / No LLM

Task 2.1 should be deterministic and local.

It should require:

```text
no OpenRouter
no OpenAI
no Anthropic
no LLM
no web calls
no SEC downloads
no Hugging Face downloads
```

Do not spend API credits.

Do not generate truth-contract rules with an LLM.

The truth contract comes from frozen repository decisions and source data semantics.

---

# 21. Documentation

Create:

```text
project_plan/PHASE2_TRUTH_CONTRACT.md
```

Document:

- objective
- why raw XBRL is unsafe as direct truth
- authoritative eligibility contract
- approved tag/qtrs mapping available at this stage
- unit rules
- consolidation rules
- period-alignment rule
- materiality rule
- same-accession dedup rule
- cross-filing value-revision terminology
- deterministic ordering
- provenance/hash semantics
- result-summary location
- test commands
- known limitations
- decisions explicitly deferred to later Phase 2 tasks

Clearly state that:

```text
eligible XBRL fact != generated evaluation question
```

Task 2.1 only defines the allowed fact population.

---

# 22. Repository Documentation

Update narrowly where appropriate:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

Mark:

```text
src/eval/truth_contract.py
```

as implemented.

Do not mark the entire evaluation system or Phase 2 complete.

Do not mark:

```text
question generation
DEV/TEST split
evidence alignment
3,000-question benchmark
```

as implemented.

They are later work.

---

# 23. Progress.md

Append a new historical entry:

```text
## YYYY-MM-DD — Phase 2.1 XBRL Truth Contract
```

Include:

```text
Objective
Initial state
Authoritative decisions used
Historical stale-metric correction
Real XBRL schema verified
Eligibility contract
Tag/qtrs status
Materiality decision
Duplicate/revision handling
Implementation
Real-data diagnostics
Independent checks
Tests
Frozen-data safety
Files created/modified
Git state
Result
Phase status
```

Do not rewrite prior Phase 0 or Phase 1 history.

Expected phase status:

```text
Data Preparation                              — COMPLETE
Phase 0 — Foundation                          — COMPLETE
Phase 1 — Make It Work End to End             — COMPLETE WITH WARN
Phase 2 — Make the Numbers Trustworthy        — IN PROGRESS
  2.1 XBRL Truth Contract                     — COMPLETE
  next Phase 2 task                            — NEXT
```

Do not invent the next task number/name if the authoritative execution document gives one.

Use its exact wording.

---

# 24. Files Expected

Likely files include:

```text
src/eval/truth_contract.py
tests/test_truth_contract.py
project_plan/PHASE2_TRUTH_CONTRACT.md
results/phase_2_1_truth_contract_summary.json
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

A config file may be appropriate **only if** Task 2.1 owns a resolved truth-contract configuration under the authoritative roadmap.

Do not create a fake final 15-tag registry if that registry belongs to the next task or remains unresolved.

---

# 25. Test Gate

Before declaring Task 2.1 complete, run:

```text
doctor
portable tests
Task 2.1 tests
appropriate local-data tests
full non-destructive test suite
```

Report exact current counts.

Historical test counts from Phase 1 are reference points only.

The current repository may legitimately contain more tests.

Requirements:

```text
0 unexpected failures
0 silently ignored relevant tests
```

---

# 26. Phase 1 Regression Gate

Explicitly verify Task 2.1 did not change:

```text
src/retrieval/
src/generation/
src/index/
src/embeddings/
src/chunk/
src/normalize/
src/eval/citation_integrity.py
Phase 1 smoke dataset
Phase 1 baseline metric semantics
Phase 1 CLI behavior
```

Do not rerun the frozen Task 1.7a 10-case generation diagnostic merely for regression checking.

Its accepted historical result remains:

```text
8/10
```

unless a future explicitly approved comparable evaluation supersedes it.

---

# 27. Git / Security

Before commit:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Verify no:

```text
data/
artifacts/
.venv/
.env
API keys
credentials
large runtime files
```

would be committed.

Run the existing secret/personal-path scan.

---

# 28. Commit

When the task genuinely passes all gates, create one coherent commit following the repository's Git conventions.

Suggested message:

```text
Add Phase 2 XBRL truth contract
```

Do not create a Phase 2 completion tag.

Phase 2 is not complete after Task 2.1.

Do not push unless current repository conventions/instructions explicitly require it and a remote actually exists.

Never invent a remote.

---

# 29. Stop Conditions

STOP and surface the issue rather than inventing a decision if any of these occur:

### A. 15-tag registry unresolved

If the repository does not contain the complete authoritative 15-tag list.

### B. qtrs semantics unresolved

If any chosen eval tag lacks an approved instant/duration mapping.

### C. Materiality unresolved

If no current authoritative source resolves the materiality strategy.

### D. Period-end semantics ambiguous

If current docs/database do not establish how `ddate` must align to the submission period.

### E. Conflicting duplicate facts

If same-accession conflicting values remain after applying the existing audited rules and no resolution policy exists.

### F. Frozen source would need modification

Do not mutate frozen data to make the contract easier.

### G. Authoritative documents disagree materially

Document the conflict and stop before encoding one interpretation silently.

A deliberate stop is better than producing a benchmark with false ground truth.

---

# 30. Acceptance Criteria

Task 2.1 is complete only when all applicable criteria pass:

```text
[ ] src/eval/truth_contract.py exists
[ ] one authoritative eligibility implementation exists
[ ] real XBRL schema independently inspected
[ ] consolidated-only rule enforced
[ ] segment facts excluded
[ ] taxonomy rule enforced
[ ] unit semantics enforced
[ ] per-tag qtrs semantics enforced
[ ] reporting-period alignment enforced
[ ] null/invalid values excluded
[ ] materiality rule explicit and reproducible
[ ] same-accession duplicate handling deterministic
[ ] filing/accession identity preserved
[ ] cross-filing values not silently canonicalized
[ ] deterministic ordering implemented
[ ] truth-contract provenance/config recorded
[ ] real-data summary generated
[ ] stale 23.56% restatement interpretation not reintroduced
[ ] unit tests pass
[ ] real-data integration checks pass
[ ] independent manual/sample verification passes
[ ] frozen XBRL data unchanged
[ ] no network/LLM/API use
[ ] Phase 1 regression checks pass
[ ] documentation updated
[ ] Progress.md appended
[ ] secret scan clean
[ ] Git staging dry-run safe
[ ] one coherent commit created
```

If any required item is unresolved, do not label Task 2.1 plain COMPLETE.

---

# 31. Final Console Summary

Print a concise final summary:

```text
PHASE 2.1 — XBRL TRUTH CONTRACT
================================

XBRL database:                VERIFIED
Truth-contract implementation: PASS
Consolidated-only filter:      PASS
Segment exclusion:             PASS
Taxonomy rule:                 PASS
Unit rule:                     PASS
qtrs mapping:                  PASS / BLOCKED
Period alignment:              PASS / BLOCKED
Materiality:                   PASS / BLOCKED
Duplicate handling:            PASS
Filing provenance:             PASS
Determinism:                   PASS
Independent verification:      PASS
Frozen-data safety:            PASS
Phase 1 regression:            PASS
Tests:                         <current result>

Eligible source facts:         <observed>
Unique CIKs:                   <observed>
Unique accessions:             <observed>
Tags covered:                  <observed>

Truth-contract config hash:    <hash>

FINAL RESULT:
PASS / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
<exact next task from PROJECT_EXECUTION.md>
```

---

# Core Rule

**Phase 2 evaluation quality can never be better than its ground truth.**

Do not maximize the number of eligible facts.

Do not maximize coverage.

Do not reproduce an expected percentage.

Do not choose the easiest accounting interpretation.

The goal of Task 2.1 is to produce the **smallest defensible, deterministic, reproducible set of XBRL facts that we can honestly call ground truth**.

Correctness is more important than dataset size.

If a fact is ambiguous, exclude it or surface the unresolved policy.

Never silently turn ambiguity into a label.