# Task 2.3 — Build the Full Evaluation Dataset

## Phase

**Phase 2 — Make the Numbers Trustworthy**

Current project state:

```text
Data Preparation                              — COMPLETE
Phase 0 — Foundation                          — COMPLETE
Phase 1 — Make It Work End to End             — COMPLETE WITH WARN

Phase 2 — Make the Numbers Trustworthy        — IN PROGRESS
  2.1 XBRL Truth Contract                     — COMPLETE
  2.2 Freeze Supported Tag Registry           — COMPLETE
  2.3 Build the Full Evaluation Dataset       — CURRENT
```

Known Phase 1 warning remains:

```text
Task 1.7a citation-format compliance = 8/10
```

Do not rerun, reinterpret, or modify that historical diagnostic.

---

# Objective

Build the project's authoritative **full Phase 2 evaluation dataset** from the already frozen:

```text
Task 2.1 truth contract
+
Task 2.2 supported tag registry
+
frozen SEC source data
```

The dataset must be:

- reproducible;
- versioned;
- deterministic wherever possible;
- traceable to source evidence;
- resistant to label leakage;
- large enough to support later retrieval/generation/system evaluation;
- structured so DEV/TEST splitting can be performed correctly later;
- independent of retrieval-system outputs.

The target design is approximately:

```text
~3,000 total evaluation questions
```

but the exact current task contract in `PROJECT_EXECUTION.md` takes precedence over older planning estimates.

Do not optimize the dataset merely to hit exactly 3,000 rows.

Ground-truth correctness is more important than count.

---

# 1. Authoritative Sources

Before changing code, read in this order:

1. `project_plan/PROJECT_EXECUTION.md`
2. `DATA_READINESS_REPORT.md`
3. `project_plan/PHASE2_TRUTH_CONTRACT.md`
4. `project_plan/PHASE2_TAG_REGISTRY.md`
5. `configs/eval_tags.yaml`
6. `src/eval/tag_registry.py`
7. `src/eval/truth_contract.py`
8. `results/phase_2_1_truth_contract_summary.json`
9. `results/phase_2_2_tag_registry_summary.json`
10. `project_plan/PROJECT_SPEC.md`
11. `Progress.md`

Also inspect relevant:

```text
src/eval/
tests/
data/xbrl.duckdb
data/edgar_corpus/
data/raw/primary/
```

Use `PROJECT_SPEC.md` only where it has not been superseded by:

```text
PROJECT_EXECUTION.md
DATA_READINESS_REPORT.md
Task 2.1
Task 2.2
```

Do not reintroduce stale Phase 1 metric definitions.

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
working-tree state
portable-test count
registry version
registry hash
truth-contract version
truth-contract hash
supported tag count
Task 2.2 eligible fact count
```

Expected historical Task 2.2 state:

```text
supported tags:       15
excluded tags:        0
unresolved tags:      0

registry version:     1
registry hash:
a230373e2a788423026142beb93c5c454a291f23468d46cfb40f5692e48b8070

truth-contract hash:
8ce68e8f53395f8f983e0002c53e62a31bb121b8551f28e739fcebb7f462988c

eligible facts:       255,527
unique accessions:    28,863
unique CIKs:          7,810

portable suite:       416 passed, 11 deselected
full suite:           427 passed
```

These are reference values.

Do not alter algorithms merely to reproduce them if the repository has legitimately changed.

---

# 3. Determine Exact Task 2.3 Category Contract

Before implementing the dataset, inspect the current `PROJECT_EXECUTION.md` definition of Task 2.3.

Historical project design planned approximately:

```text
Numeric                         ~2,000
Comparative / multi-hop           ~500
Narrative                         ~200
Unanswerable                      ~200
Adversarial                       ~100
---------------------------------------
Total                           ~3,000
```

Do **not** blindly assume those exact counts remain authoritative.

First compare them against the current execution plan.

If `PROJECT_EXECUTION.md` provides revised counts/categories, use those exact definitions.

Record the final adopted category contract in the Task 2.3 documentation before generating anything.

---

# 4. Dataset Must Be Retrieval-Independent

The evaluation dataset must be created from:

```text
source data
truth contract
tag registry
deterministic transformations
verified source evidence
```

It must NOT be constructed by asking the current RAG system:

```text
"What questions can you answer?"
```

or by retrieving passages first and then defining those retrieved passages as gold.

Never use:

```text
current vector retriever
BM25
reranker
CRAG
router
generation answer
retrieved top-k output
```

to decide whether a question is valid ground truth.

Doing so would evaluate the system against labels produced by itself.

---

# 5. Freeze a Dataset Schema First

Before generating the full dataset, define a single record schema.

Create an explicit implementation such as:

```text
src/eval/evaluation_dataset.py
```

or whatever location the repository architecture specifies.

Every record should have stable required fields appropriate to its category.

Recommended common fields:

```text
question_id
category
subtype
question
answer_type

cik
company
fiscal_year
accession

source_kind
source_provenance

registry_version
registry_hash
truth_contract_version
truth_contract_hash

generator_version
```

Category-specific fields may include:

```text
tag
expected_value
expected_unit

operand_tags
operand_values
operation
expected_numeric_answer

source_section
source_section_hash

expected_behavior
```

Do not include fields with fabricated values merely to make every category share identical columns.

Nullable/category-specific fields are acceptable when clearly defined.

---

# 6. Question IDs

Question IDs must be:

- deterministic;
- stable across rebuilds with identical config/source data;
- independent of physical row ordering;
- not based on Python's built-in `hash()`.

Use an explicit scheme such as:

```text
phase2-eval-000001
...
```

with deterministic ordering before assignment,

or derive stable IDs from canonical semantic identity.

Document whichever approach is chosen.

A rebuild with identical semantic inputs must produce identical question IDs.

---

# 7. Dataset Version

Freeze an explicit evaluation dataset version.

For example:

```text
eval_set_version: phase2-v1
```

Follow repository conventions if one already exists.

The version is semantically important.

A later change to:

```text
question population
question wording rules
truth contract
tag registry
category definitions
gold labels
```

must not silently overwrite the old benchmark.

---

# 8. Numeric Questions

Numeric questions should be derived directly from:

```text
eligible_facts(...)
```

using the Task 2.1 truth contract and Task 2.2 registry.

Do not independently recreate XBRL eligibility SQL.

The production flow should conceptually be:

```text
configs/eval_tags.yaml
        ↓
tag registry
        ↓
truth contract
        ↓
eligible facts
        ↓
Task 2.3 question generator
```

Do not bypass this chain.

---

# 9. Numeric Ground Truth

Each simple numeric question should preserve enough provenance to identify exactly:

```text
cik
company
accession/adsh
tag
fiscal_year
reporting period
qtrs
unit
expected numeric value
```

The expected value comes directly from the eligible XBRL fact.

Do not ask an LLM to calculate or restate the gold value.

Do not round the stored gold value merely for display convenience.

Store the canonical underlying value.

Question rendering may format it differently, but scoring later must know the canonical numeric answer.

---

# 10. Accession Anchoring

Questions must preserve the specific filing/accession identity.

However, do not confuse:

```text
document relevance
```

with:

```text
evidence/chunk relevance
```

An accession gives a document-level target.

It does **not** automatically identify the correct chunk.

Therefore Task 2.3 may store:

```text
target_accession
```

for document-level evaluation.

Do not fabricate:

```text
target_chunk_id
```

unless an authoritative chunk-level label already exists.

Primary-document / inline-XBRL evidence alignment belongs to its dedicated later task unless `PROJECT_EXECUTION.md` explicitly moves it here.

---

# 11. Question Wording Must Not Leak Labels

Never include machine-facing identifiers in user-visible question text.

Do not expose:

```text
adsh/accession string
chunk_id
target document ID
XBRL tag name
expected value
truth-contract hash
registry hash
```

unless the natural question intentionally refers to a filing date/document in human language.

Bad:

```text
For accession 0000320193-20-000096,
what is NetIncomeLoss?
```

Better natural form:

```text
What net income did Apple report in its 2020 annual filing?
```

But only use wording whose semantics uniquely identify the intended filing under the current contract.

---

# 12. Template-Based Numeric Generation

Simple numeric questions should preferably be generated deterministically from reviewed templates.

Examples of semantic patterns:

```text
What were {company}'s total assets in {period}?

How much revenue did {company} report in {period}?

What was {company}'s research and development expense in {period}?

What basic earnings per share did {company} report in {period}?
```

Do not use a single awkward generic template for every concept.

Use concept-aware templates.

However:

```text
template wording != accounting semantics
```

Accounting semantics come from the registry/truth contract.

Templates only express them naturally.

---

# 13. Concept Display Metadata

If natural-language question generation requires human-readable concept names, add a small deterministic display field to the appropriate registry/config rather than hardcoding tag→English mappings throughout the generator.

For example:

```yaml
EarningsPerShareDiluted:
  display_name: diluted earnings per share
```

Only add this if Task 2.3 legitimately needs it.

Do not change qtrs/unit/period semantics established in Task 2.2.

If the registry schema changes semantically, version/hash it appropriately.

---

# 14. Selection / Sampling Policy

Task 2.1 deliberately kept:

```text
truth validity
```

separate from:

```text
sampling/materiality policy
```

Task 2.3 is where evaluation sampling policy may now be applied if the authoritative roadmap assigns it here.

The sampling policy must be:

- explicit;
- deterministic;
- reproducible;
- documented;
- independent of current model performance.

Possible considerations include:

```text
tag balance
year balance
company concentration
magnitude/materiality
duplicate question semantics
coverage across industries if metadata exists
```

Do not silently introduce a `$1M` threshold simply because it appeared as an old planning suggestion.

Use the current approved Task 2.3 policy.

If materiality remains unresolved in `PROJECT_EXECUTION.md`, document the decision rather than inventing it.

---

# 15. Avoid Company Domination

Do not allow a small number of prolific filers to dominate the benchmark.

Measure:

```text
questions per CIK
questions per company
questions per accession
questions per tag
questions per year
```

Set deterministic caps/selection rules if required by the roadmap.

Do not set caps by trial-and-error against retrieval scores.

---

# 16. Numeric Category Balance

Report numeric question distribution across all 15 supported tags.

Do not claim the set is balanced if it is merely proportional to raw XBRL frequency.

If equal/near-equal tag quotas are required, enforce them deterministically.

If the plan instead wants population-proportional sampling, document that explicitly.

The choice must be visible.

---

# 17. Fiscal-Year Coverage

The SEC/EDGAR evaluation scope remains:

```text
2016–2020
```

unless `PROJECT_EXECUTION.md` explicitly supersedes it.

Do not generate ordinary answerable EDGAR-linked questions outside this overlapping range merely to increase dataset size.

Task 2.1 already filters to:

```text
10-K
2016–2020
own-period XBRL facts
```

Preserve that.

---

# 18. Comparative / Multi-Hop Questions

If Task 2.3 owns the planned comparative/multi-hop category, generate it deterministically from trusted XBRL facts.

Examples of valid operations may include:

```text
difference
ratio
percentage
growth rate
greater/less comparison
same-company multi-period comparison
cross-entity comparison
```

Only implement operation families explicitly approved by the current execution plan.

Do not add arbitrary reasoning tasks merely to make the benchmark look harder.

---

# 19. Comparative Operands

Every derived numeric question must record its source operands explicitly.

Example conceptual record:

```text
question:
"How much did Company X's revenue increase from 2019 to 2020?"

operation:
difference

operands:
  - accession: ...
    tag: Revenues
    fiscal_year: 2019
    value: ...

  - accession: ...
    tag: Revenues
    fiscal_year: 2020
    value: ...

expected_answer:
...
```

The expected answer must be computed in code from source facts.

Do not have an LLM compute gold arithmetic.

---

# 20. Arithmetic Precision

Define deterministic numeric arithmetic rules.

Specify:

```text
Decimal vs float
rounding mode
percentage representation
division-by-zero policy
display precision
scoring tolerance metadata
```

Prefer exact decimal arithmetic where practical.

Do not allow platform-dependent floating-point formatting to change dataset hashes.

---

# 21. Comparative Validity

Do not compare facts unless their semantics are compatible.

At minimum verify compatibility of:

```text
tag/concept
unit
period type
qtrs
company/entity requirements
reporting-period requirements
```

Do not compare:

```text
basic EPS vs diluted EPS
USD vs non-USD
instant vs duration
different concepts merely because values look similar
```

unless the question explicitly asks for that distinction.

---

# 22. Cross-Entity Questions

If the authoritative Task 2.3 contract includes cross-entity comparisons, ensure both source facts independently satisfy the truth contract.

Record both CIKs/accessions.

Use deterministic entity selection.

Do not select companies because the current retriever happens to handle them well.

---

# 23. Narrative Questions

The historical design includes approximately:

```text
~200 narrative questions
```

from filing narrative sections.

Before implementing them, check whether the current `PROJECT_EXECUTION.md` assigns narrative generation to Task 2.3.

If yes, follow that contract.

Potential source sections include filing narrative such as:

```text
Item 1
Item 1A
Item 7
Item 7A
```

according to the approved plan.

Do not automatically use sparse sections without recording coverage limitations.

---

# 24. Narrative Gold Evidence

Narrative questions are fundamentally different from XBRL numeric questions.

Do not manufacture exact numeric-style labels for them.

Each narrative record must preserve source evidence sufficient for later human/LLM judging, such as:

```text
target document/accession
source section
source section hash
source text span or source artifact reference
question-generation provenance
```

Do not fabricate a target chunk before chunk-level gold alignment exists.

---

# 25. LLM-Generated Narrative Questions

Historical design allows LLM-generated narrative questions followed by human verification.

If current Task 2.3 still requires this:

1. isolate the LLM-assisted component from deterministic categories;
2. version the prompt;
3. record model/provider;
4. record generation settings;
5. never allow the LLM to invent ground truth;
6. questions must be generated from supplied source text only;
7. source evidence remains authoritative;
8. every accepted narrative question must pass validation/review.

Do not use the same generated answer as both gold truth and evaluation judge.

---

# 26. No Mandatory Paid API Usage Unless Required

Do not spend API credits merely because the historical spec once suggested LLM-generated narrative questions.

First inspect the current execution plan.

If narrative generation is explicitly required and an approved local/provider path already exists, follow repository conventions.

If the provider/model decision is not yet authorized:

```text
build the deterministic categories
build the narrative generation interface/schema
surface the unresolved generation dependency
```

rather than silently choosing a new API/model.

Do not substitute random Claude/OpenAI/OpenRouter calls without project authorization.

---

# 27. Human-Review Boundary

If narrative questions require hand verification, create a review artifact/schema rather than falsely marking unchecked generated questions as gold.

Potential statuses:

```text
pending_review
accepted
rejected
```

Only:

```text
accepted
```

questions belong in the frozen evaluation dataset.

If Task 2.3 cannot legitimately complete narrative review autonomously, clearly report that as a task blocker/warning according to the execution plan.

Do not fake “human verified”.

---

# 28. Unanswerable Questions

If Task 2.3 owns the unanswerable category, construct it deliberately.

An unanswerable question must be:

```text
plausible
in-domain
specific enough to evaluate
actually unsupported by the target corpus
```

Examples may involve:

```text
company outside corpus
year outside supported corpus
unsupported filing/document
missing fact
```

but use only mechanisms approved by the current roadmap.

---

# 29. Verify Unanswerability Against Source, Not Retriever

A crucial rule:

Do NOT classify a question as unanswerable because:

```text
vector search returned nothing
```

A retrieval miss is not proof that the corpus lacks the answer.

Verify unanswerability against source metadata/data directly.

For XBRL-style cases, query the truth source.

For narrative cases, verify against the relevant frozen source scope using deterministic source inspection.

---

# 30. Unanswerable Gold Label

Record an explicit expected behavior such as:

```text
expected_behavior: refuse_insufficient_evidence
```

or the repository's approved taxonomy.

Do not assign a fake answer like:

```text
"Unknown"
```

unless that is the actual evaluation contract.

---

# 31. Adversarial Questions

If Task 2.3 owns the adversarial category, include the types explicitly required by the project.

Historical design includes:

```text
prompt injection
financial advice
off-scope
```

Potential expected behavior:

```text
guard trigger
refusal
safe scoped response
```

Do not implement guardrails themselves during this task.

Task 2.3 only creates labelled evaluation inputs.

---

# 32. Do Not Poison Production Source Data

If an adversarial evaluation later requires a poisoned document, do not edit frozen SEC source data during Task 2.3 unless the execution plan explicitly defines a separate test fixture.

Use isolated test/evaluation fixtures.

Never alter:

```text
data/edgar_corpus/
data/raw/primary/
data/xbrl.duckdb
```

to manufacture adversarial cases.

---

# 33. Evaluation Intent / Category Labels

Use a stable taxonomy for question categories/subtypes.

Where appropriate align later router-oriented labels with the approved taxonomy, e.g.:

```text
xbrl_fact
numeric_derived
comparative
cross_entity
narrative
unanswerable
out_of_scope
advice
```

but do not prematurely implement router behavior.

The evaluation dataset can carry intended semantic labels without creating the router.

Use the current authoritative taxonomy.

---

# 34. Do Not Perform DEV/TEST Split Unless Task 2.3 Explicitly Owns It

The broader design requires:

```text
DEV ≈70%
TEST ≈30%
```

with company-level separation and no CIK appearing in both.

However, before implementing the split, inspect `PROJECT_EXECUTION.md`.

If DEV/TEST splitting is owned by a later Phase 2 task:

```text
DO NOT SPLIT HERE.
```

Instead make the Task 2.3 master dataset **split-ready** by preserving:

```text
cik
fiscal_year
category
tag/subtype
```

and any other future stratification fields.

Do not randomly assign `dev`/`test` early.

If `PROJECT_EXECUTION.md` explicitly says Task 2.3 includes the split, then follow that current instruction rather than this boundary.

---

# 35. SIC / Industry Metadata

The broader review design suggests stratifying future DEV/TEST splits by:

```text
SIC
fiscal year
```

But prior data-readiness work noted that SIC exists in raw SEC metadata and was not necessarily persisted in `xbrl.duckdb`.

Do not mutate the frozen XBRL database merely to add SIC during Task 2.3.

If needed for future split-readiness:

- load it read-only from approved existing raw metadata; or
- defer enrichment to the explicit split task.

Do not invent industry labels.

---

# 36. Master Dataset Output

Create a tracked master evaluation artifact using the repository's small-result conventions.

Potential path:

```text
results/phase_2_3_evaluation_dataset.json
```

or the exact location specified in `PROJECT_EXECUTION.md`.

If ~3,000 full records make JSON inconvenient, JSONL may be technically preferable, but check the existing `.gitignore`/Git conventions first.

Do not create a format that becomes accidentally ignored.

The artifact must remain small enough to track.

Do not store large filing text repeatedly inside every record.

Store hashes/references/provenance instead.

---

# 37. Dataset Config

Create a tracked deterministic build configuration, for example:

```text
configs/phase_2_3_evaluation_dataset.yaml
```

It should capture semantic build parameters such as:

```text
eval_set_version
category definitions
category target counts
selection/sampling rules
year window
source contract hash
registry hash
question template version
arithmetic rules
materiality/sampling policy if applicable
```

Do not put timestamps or Git SHA in the semantic config hash.

---

# 38. Dataset Manifest

Create a small manifest/summary artifact, for example:

```text
results/phase_2_3_evaluation_dataset_summary.json
```

Include:

```text
eval_set_version
dataset_sha256

question_count

counts_by_category
counts_by_subtype
counts_by_year
counts_by_tag
counts_by_answer_type

unique_ciks
unique_companies
unique_accessions

max_questions_per_cik
max_questions_per_accession

registry_version
registry_hash

truth_contract_version
truth_contract_hash

build_config_hash
template_version

created_at_utc
git_sha
```

Distinguish semantic hashes from run metadata.

---

# 39. Dataset Hash

Compute a deterministic SHA-256 over a canonical representation of the semantic dataset.

Exclude:

```text
created_at
runtime
git SHA
file path
non-semantic formatting
```

Include:

```text
question IDs
questions
gold labels
category/subtype
source identities
relevant provenance
```

Two fresh builds from identical inputs must produce the same semantic hash.

---

# 40. Numeric Answer Representation

Do not store numeric answers only as formatted strings.

Store a machine-readable canonical value and unit.

Example:

```json
{
  "expected_value": "123456789.00",
  "expected_unit": "USD",
  "display_answer": "$123.46 million"
}
```

The exact schema may differ.

The critical point is:

```text
display formatting must not destroy exact gold truth.
```

---

# 41. Numeric Formatting

If question text or display answers use:

```text
thousand
million
billion
percent
EPS decimals
```

define deterministic formatting rules.

Do not let formatting depend on locale or operating system.

Record whether scoring later compares:

```text
raw canonical numeric value
normalized numeric value
formatted answer
```

Task 2.3 does not need to implement the scorer unless explicitly assigned.

---

# 42. Negative and Zero Values

Task 2.1 intentionally accepts valid signed values.

Do not blindly exclude:

```text
negative NetIncomeLoss
negative EPS
zero values
```

merely because they look unusual.

If Task 2.3 applies materiality/sampling rules, apply them according to the approved policy, not by assuming negatives are errors.

Do not resurrect stale blanket statements such as:

```text
all negative financial values are tagging errors
```

without current contract support.

---

# 43. Duplicate Questions

Prevent semantic duplicates.

At minimum detect identical:

```text
question text
```

and identical semantic identity such as:

```text
category
CIK
accession
tag
operation
operands
```

where relevant.

Do not treat two differently punctuated versions of the same generated question as meaningful additional examples.

---

# 44. Leakage Checks

Run explicit checks that user-facing `question` text does not accidentally contain:

```text
expected answer
target accession ID
internal document ID
target chunk ID
truth hash
registry hash
SQL/XBRL field names
```

unless genuinely part of natural financial language.

A benchmark that leaks its labels is invalid.

---

# 45. Answerability Checks

For every answerable deterministic question:

```text
1. recompute/resolve the source truth;
2. compare with the stored gold;
3. fail if they disagree.
```

Do not simply trust the generation function that originally wrote the record.

Validation must be an independent pass.

---

# 46. Independent Numeric Recalculation

For a deterministic sample from each numeric/derived category:

- query the raw XBRL database independently;
- apply the frozen truth semantics;
- recompute the answer without calling the question-generation function;
- compare against the dataset.

At minimum inspect enough examples to cover:

```text
instant facts
duration facts
EPS
negative value
large value
derived arithmetic
multi-period comparison
cross-entity comparison
```

where those categories exist.

---

# 47. Manual Question Inspection

Manually inspect a deterministic sample across every category.

Minimum:

```text
numeric:              >=15
comparative/multi-hop >=10
narrative:            >=10 if present
unanswerable:         >=10 if present
adversarial:          >=10 if present
```

or stricter counts if the execution plan requires them.

Check:

```text
natural wording
no label leakage
correct company
correct year/period
correct question semantics
correct gold answer
correct expected behavior
source provenance
```

Do not cherry-pick only good examples.

Define deterministic sample selection before inspection.

---

# 48. Distribution Diagnostics

Report:

```text
category distribution
tag distribution
year distribution
company distribution
answer-type distribution
question length distribution
numeric magnitude distribution
```

and any relevant subtype distribution.

Flag severe concentration.

Do not silently rebalance after seeing model results.

This task occurs before optimization.

---

# 49. Reproducibility Run

Run the entire deterministic build twice in fresh processes.

Verify:

```text
same question count
same question IDs
same ordering
same questions
same deterministic gold values
same semantic dataset hash
same build-config hash
```

For any LLM-assisted narrative subset, separate deterministic and nondeterministic provenance clearly.

Do not falsely claim the LLM-generated portion is byte-reproducible unless it actually is.

---

# 50. No Retrieval Evaluation Yet

Task 2.3 builds the instrument.

Do NOT run the new full dataset against:

```text
vector retrieval
BM25
hybrid retrieval
reranker
CRAG
router
generation system
```

unless `PROJECT_EXECUTION.md` explicitly assigns a tiny validation smoke.

Do not publish retrieval numbers from this task.

The dataset must exist before tuning starts.

---

# 51. Do Not Tune Phase 1 Retrieval

Do not alter:

```text
embedding model
chunk size
retrieval k
index
prompt
generation model
```

because of observations made while creating Task 2.3.

Dataset construction must remain independent of system optimization.

---

# 52. Tests

Add comprehensive tests, likely:

```text
tests/test_evaluation_dataset.py
```

At minimum cover:

### Schema

```text
required common fields
category-specific required fields
question_id uniqueness
question non-empty
valid category
valid answer_type
```

### Determinism

```text
same inputs -> same selection
same inputs -> same question IDs
same inputs -> same ordering
same inputs -> same dataset hash
```

### Numeric

```text
source fact -> correct question
expected value preserved
unit preserved
accession preserved
tag preserved internally
tag not leaked into question text where inappropriate
```

### Derived

```text
correct operand selection
correct arithmetic
division-by-zero handling
rounding policy
unit compatibility
```

### Leakage

```text
question does not contain expected answer
question does not expose machine identifiers
```

### Duplicates

```text
duplicate IDs rejected
duplicate semantic records rejected/flagged
```

### Registry integration

```text
only supported tags
registry semantics reused
registry hash recorded
```

### Truth-contract integration

```text
numeric source facts come from eligible_facts()
truth-contract hash recorded
```

### Unanswerable

If present:

```text
expected behavior explicit
source-based absence validation
```

### Adversarial

If present:

```text
expected behavior explicit
no guard implementation dependency
```

---

# 53. Real-Data Integration Test

Add a `local_data`-marked test that builds or validates the actual Task 2.3 dataset against frozen local data.

Verify:

```text
all numeric gold facts resolve
all CIKs/accessions exist where required
all supported tags are valid
all registry hashes match
all truth-contract hashes match
all expected units/qtrs match
no source mutation
```

Avoid expensive regeneration in every portable CI run.

---

# 54. Dataset Validation Command

Create a deterministic validation/build script such as:

```text
scripts/build_evaluation_dataset.py
```

and/or:

```text
scripts/validate_evaluation_dataset.py
```

according to repository conventions.

A fresh developer should be able to reproduce/validate the benchmark without editing Python source code.

---

# 55. Frozen Data Safety

Verify before and after:

```text
data/xbrl.duckdb
data/edgar_corpus/
data/raw/primary/
```

are unchanged.

For XBRL, compare at minimum:

```text
size
facts row count
submissions row count
```

Historical reference:

```text
xbrl.duckdb: 7,011,053,568 bytes
facts:        90,685,753
submissions:  218,166
```

Do not write into the source database.

---

# 56. Task 2.1 Regression Gate

Verify Task 2.3 has not weakened:

```text
10-K only
2016–2020
coreg blank
segments blank
us-gaap taxonomy
per-tag unit
per-tag qtrs
finite values
ddate = submissions.period
duplicate/conflict handling
no materiality in truth validity
```

Sampling policy may operate on top of truth validity.

It must never replace it.

---

# 57. Task 2.2 Regression Gate

Verify:

```text
configs/eval_tags.yaml
```

remains the one authoritative tag registry.

Do not recreate:

```text
QTRS_BY_TAG
MONETARY_UOM
SUPPORTED_TAGS
```

as independently maintained constants inside the dataset generator.

Derived views are acceptable.

Competing registries are not.

---

# 58. Phase 1 Regression Gate

Confirm no unintended semantic changes to:

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

Do not rerun Task 1.7a.

---

# 59. Documentation

Create:

```text
project_plan/PHASE2_EVALUATION_DATASET.md
```

Document:

- Task objective
- authoritative source hierarchy
- adopted category counts
- final dataset schema
- evaluation version
- numeric-generation method
- comparative-generation method
- narrative-generation/review method if applicable
- unanswerable construction method
- adversarial construction method
- sampling strategy
- materiality policy if applicable
- leakage prevention
- duplicate prevention
- deterministic hashing
- source provenance
- distribution diagnostics
- known limitations
- DEV/TEST split status
- evidence-label status
- test commands

Clearly distinguish:

```text
document-level target available
```

from:

```text
chunk-level evidence target available
```

Do not claim the latter until it actually exists.

---

# 60. Repository Structure

Update narrowly:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

for newly implemented files, likely including:

```text
src/eval/evaluation_dataset.py
scripts/build_evaluation_dataset.py
configs/phase_2_3_evaluation_dataset.*
results/phase_2_3_*
```

Do not mark DEV/TEST split, evidence alignment, metric runner, router, or Phase 3 functionality complete unless they truly belong to Task 2.3.

---

# 61. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.3 Build the Full Evaluation Dataset
```

Include:

```text
Objective
Initial State
Authoritative Sources
Adopted Category Contract
Dataset Schema
Evaluation Version
Sampling Policy
Numeric Dataset
Comparative/Multi-Hop Dataset
Narrative Dataset
Unanswerable Dataset
Adversarial Dataset
Provenance
Distribution Diagnostics
Leakage Checks
Independent Validation
Determinism
Tests
Frozen-Data Safety
Task 2.1 Regression
Task 2.2 Regression
Phase 1 Regression
Files Created/Modified
Git
Result
Phase Status
```

Do not rewrite prior history.

---

# 62. Result Artifact Size

Before committing, inspect the size of generated evaluation artifacts.

The full question dataset should be a compact metadata/QA artifact.

Do not embed entire 10-K documents or large source sections repeatedly.

If a tracked result unexpectedly grows above repository Git-size conventions:

```text
STOP
```

and redesign provenance representation rather than committing large source text.

---

# 63. Git / Security

Before committing:

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
credentials
API keys
large model files
large filing source files
```

will be staged.

Run the existing secret/personal-path scan.

---

# 64. Commit

After all gates pass, create one coherent Task 2.3 commit.

Suggested message:

```text
Build Phase 2 evaluation dataset
```

Do not tag Phase 2 complete.

Do not push unless a real remote exists and repository conventions require the session push.

Never invent a remote.

---

# 65. Stop Conditions

STOP and surface the issue rather than silently weakening the benchmark if:

### A. Current category contract is ambiguous

If `PROJECT_EXECUTION.md` materially disagrees with the older ~3,000-category plan.

### B. Numeric quota cannot be filled honestly

Do not duplicate questions or weaken the truth contract.

### C. Comparative labels are ambiguous

Do not include incompatible operands.

### D. Narrative gold cannot be verified

Do not label unreviewed generated material as gold.

### E. Unanswerability cannot be proven from source data

Do not use retrieval failure as proof.

### F. Required source identity cannot be resolved

Do not guess accession/document mappings.

### G. Dataset construction requires modifying frozen source data

Do not modify it.

### H. A category requires a provider/model decision not yet authorized

Surface the dependency.

### I. DEV/TEST ownership is unclear

Build only the master dataset and explicitly defer the split.

### J. Chunk-level evidence labels are unavailable

Store document-level provenance only.

Do not manufacture `target_chunk_id`.

---

# 66. Acceptance Criteria

Task 2.3 is complete only when all applicable requirements pass:

```text
[ ] exact Task 2.3 category contract confirmed from PROJECT_EXECUTION.md
[ ] master evaluation dataset exists
[ ] dataset version frozen
[ ] schema documented
[ ] question IDs deterministic and unique
[ ] numeric questions derive only from Task 2.1 eligible facts
[ ] all numeric tags come from Task 2.2 registry
[ ] numeric gold values independently verified
[ ] accession/document provenance preserved
[ ] no fabricated chunk labels
[ ] comparative/multi-hop gold computed deterministically if in scope
[ ] arithmetic policy explicit
[ ] narrative questions validated/reviewed appropriately if in scope
[ ] unanswerable cases source-verified if in scope
[ ] adversarial cases labelled if in scope
[ ] no retrieval output used to construct gold truth
[ ] no current model performance used for sampling
[ ] no label leakage detected
[ ] duplicate questions checked
[ ] company/accession concentration measured
[ ] year/tag/category distributions reported
[ ] dataset semantic hash deterministic
[ ] build-config hash deterministic
[ ] registry hash recorded
[ ] truth-contract hash recorded
[ ] two fresh deterministic builds match
[ ] independent sample verification passes
[ ] portable tests pass
[ ] local-data integration test passes
[ ] full suite passes
[ ] frozen source data unchanged
[ ] Task 2.1 regression passes
[ ] Task 2.2 regression passes
[ ] Phase 1 regression passes
[ ] DEV/TEST split only performed if explicitly owned by Task 2.3
[ ] documentation updated
[ ] Progress.md appended
[ ] secret scan clean
[ ] git add -n . safe
[ ] one coherent Task 2.3 commit created
```

---

# 67. Final Console Summary

Print:

```text
PHASE 2.3 — BUILD THE FULL EVALUATION DATASET
==============================================

Eval-set version:             <version>
Dataset path:                 <path>
Dataset hash:                 <hash>
Build-config hash:            <hash>

Registry:
  version:                    <version>
  hash:                       <hash>
  supported tags:             15

Truth contract:
  version:                    <version>
  hash:                       <hash>

Questions:
  total:                      <count>
  numeric:                    <count>
  comparative/multi-hop:      <count>
  narrative:                  <count>
  unanswerable:               <count>
  adversarial:                <count>

Coverage:
  unique CIKs:                <count>
  unique companies:           <count>
  unique accessions:          <count>
  years:                      <distribution>

Validation:
  schema:                     PASS
  source provenance:          PASS
  numeric gold:               PASS
  arithmetic gold:            PASS / N/A
  leakage checks:             PASS
  duplicate checks:           PASS
  independent sample:         PASS
  deterministic rebuild:      PASS
  frozen-data safety:         PASS

DEV/TEST split:
  <DEFERRED TO NEXT TASK / COMPLETED ONLY IF 2.3 OWNS IT>

Chunk-level evidence labels:
  NOT CREATED unless independently justified by real evidence alignment

Tests:
  portable:                   <result>
  full:                       <result>

FINAL RESULT:
PASS / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
<exact next task from PROJECT_EXECUTION.md>
```

---

# Final Principle

**This dataset is the measuring instrument for the rest of the project.**

If the instrument is biased, leaked, ambiguous, or derived from the system being evaluated, every later number becomes misleading.

Therefore:

```text
Do not maximize dataset size.
Do not maximize retrieval scores.
Do not generate labels from retrieval output.
Do not weaken truth validity.
Do not fabricate evidence labels.
Do not call an unreviewed LLM output "gold".
Do not randomly split companies across DEV/TEST.
Do not change questions after seeing model performance.
```

Build the benchmark first.

Freeze its semantics.

Then optimize the system against the appropriate development portion later.