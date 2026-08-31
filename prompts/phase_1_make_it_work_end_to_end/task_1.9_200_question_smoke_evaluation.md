# Task 1.9 — Build the 200-Question Smoke Evaluation

You are working inside my SEC RAG repository.

Task file:

`task_1.9_200_question_smoke_evaluation.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.9 — Build a 200-Question Smoke Evaluation
```

Current status:

```text
Data Preparation                              — COMPLETE
Phase 0 — Foundation                          — COMPLETE
Phase 1 — Make It Work End to End             — IN PROGRESS
  1.1 Select Development Corpus               — COMPLETE
  1.2 Minimal Normalization                   — COMPLETE
  1.3 Minimal Fixed-Window Chunker            — COMPLETE
  1.4 Baseline Embedding Pipeline             — COMPLETE
  1.5 Vector-Only Index                       — COMPLETE
  1.6 Baseline Retriever                      — COMPLETE
  1.7 Minimal Generation Layer                — COMPLETE
  1.8 Citation Integrity Smoke                — COMPLETE WITH HISTORICAL WARN
  1.7a Citation Format Compliance Correction  — COMPLETE WITH WARN
  1.9 200-Question Smoke Evaluation           — CURRENT
  1.10 Baseline Metric Runner                 — NOT STARTED
```

Do NOT begin Task 1.10.

---

# AUTHORITATIVE TASK DEFINITION

`project_plan/PROJECT_EXECUTION.md` defines Task 1.9 as:

```text
- Generate approximately 200 questions from the aligned development subset.
- Prefer questions with a defensible document-level target.
- Keep provenance for each question.
- Label the initial retrieval metric explicitly as doc_recall@10 unless true
  chunk evidence is available.
- Do not present Phase 1 numbers as final research results.
```

Task 1.10 separately owns implementation of `doc_recall@10`, hand-checking
calculations, printing question/hit/recall counts, and saving run metadata.

Therefore Task 1.9 builds and validates the smoke-evaluation DATASET only.

---

# USER DECISION — PROCEED DESPITE TASK 1.7a WARN

Task 1.8 originally produced:

```text
3/10 citation-integrity PASS
```

Task 1.7a's prompt-only correction improved the exact same frozen smoke set
to:

```text
8/10 citation-integrity PASS
```

The two residual failures were still malformed fullwidth `【】` citation
markers. Task 1.7a still had:

```text
unknown_chunk_id cases:           0
out-of-context citation cases:    0
```

Task 1.7a was truthfully recorded as `COMPLETE WITH WARN`.

The user has now explicitly requested Task 1.9. Treat that as authorization
to proceed while keeping the citation-format limitation visible.

Do NOT rewrite history to claim Task 1.7a reached 10/10.
Do NOT mark citation compliance resolved.
Do NOT weaken citation validation.

---

# TASK 1.9 BASELINE DECISIONS — FROZEN

## 1. Exactly 200 questions

Build exactly:

```text
200 questions
```

## 2. Deterministic offline question construction

Use deterministic source metadata + fixed templates.

Do NOT use:

```text
OpenRouter
another LLM
web search
external question-generation APIs
random free-form generation
```

## 3. One unique target filing per question

Use:

```text
200 unique target_document_id values
```

One question per filing.

## 4. Five section categories

Use exactly:

```text
business                -> section_1
risk_factors            -> section_1A
mdna                    -> section_7
market_risk             -> section_7A
financial_statements    -> section_8
```

Target exactly:

```text
40 questions/category
```

## 5. Assigned section must be real and non-empty

A target is eligible only when the assigned EDGAR-CORPUS section is:

```text
not null
not empty
not whitespace-only
```

Do not use the seven known empty-source filings.

## 6. Document-level target only

The authoritative target is:

```text
target_document_id
```

Set:

```text
label_granularity = "document"
retrieval_metric = "doc_recall@10"
```

Do NOT claim target chunk evidence, answer spans, or exact answer truth.

## 7. No generation run

Task 1.9 does NOT call Task 1.7 generation for 200 questions.
Do not spend OpenRouter credits.
Do not score answer correctness.

---

# CRITICAL RULE — DO NOT ASSUME

Before any implementation/design decision not explicitly frozen above:

1. inspect the repository,
2. inspect authoritative docs,
3. inspect the Task 1.1 manifest,
4. inspect actual EDGAR-CORPUS schema,
5. inspect current eval/retrieval code,
6. inspect existing result/config conventions.

If the answer is not unambiguous:

**STOP AND ASK ME.**

This especially applies to source-section column names, conflicting existing
Task 1.9 artifacts, schema coercion, insufficient category candidates,
duplicate target documents, artifact overwrite behavior, a temptation to use
XBRL as trusted answer truth, an LLM question generator, dependency changes,
or Git push policy.

---

# PURPOSE

Build:

```text
Task 1.1 aligned development corpus
          ↓
verify non-empty source sections
          ↓
deterministically choose 200 unique filings
          ↓
render one document-targeted question per filing
          ↓
store provenance + document-level label
          ↓
Task 1.10 computes doc_recall@10
```

This is a crude Phase 1 smoke set, not the final benchmark.

---

# QUESTION TEMPLATES

Use these stable templates.

## business / section_1

```text
What does {company} report about its business in its fiscal year {fiscal_year} 10-K?
```

## risk_factors / section_1A

```text
What risk factors does {company} report in its fiscal year {fiscal_year} 10-K?
```

## mdna / section_7

```text
What does {company} report in Management's Discussion and Analysis for fiscal year {fiscal_year}?
```

## market_risk / section_7A

```text
What does {company} report about quantitative and qualitative market risk in its fiscal year {fiscal_year} 10-K?
```

## financial_statements / section_8

```text
What financial statements and related information does {company} report for fiscal year {fiscal_year}?
```

Do not invent amounts, products, risks, subsidiaries, markets, or accounting
facts.

---

# STEP 1 — VERIFY GIT STATE

Run:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -10
git tag --list
```

Verify Task 1.7a is committed, working tree is clean except intentional
Task 1.9 prompt state, and Task 1.10 implementation does not exist.

If unexplained changes exist: **STOP AND ASK ME.**

---

# STEP 2 — VERIFY FOUNDATION

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Required: zero failures.

Recorded post-Task-1.7a reference:

```text
portable: 289 passed, 8 deselected
full:     297 passed
```

Use actual current counts.

---

# STEP 3 — READ AUTHORITATIVE MATERIAL

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_DEVELOPMENT_CORPUS.md
project_plan/PHASE1_NORMALIZATION.md
project_plan/PHASE1_CHUNKING.md
project_plan/PHASE1_RETRIEVER.md
project_plan/PHASE1_GENERATION.md
project_plan/PHASE1_CITATION_INTEGRITY.md
project_plan/TESTING.md
project_plan/GIT_CONVENTIONS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Inspect:

```text
results/phase_1_1_development_corpus.json
results/phase_1_2_normalization_summary.json
results/phase_1_3_chunking_summary.json
results/phase_1_6_retriever_summary.json
results/phase_1_8_citation_integrity_summary.json
results/phase_1_7a_citation_format_correction_summary.json
src/eval/
src/retrieval/baseline.py
```

---

# STEP 4 — VERIFY TASK 1.7a WARN

Confirm tracked state remains approximately:

```text
before: 3/10
after:  8/10
```

with two residual malformed fullwidth-bracket cases and zero unknown or
out-of-context citations.

Do not rerun OpenRouter.
Do not change Task 1.7a.

---

# STEP 5 — VERIFY TASK 1.1 DEVELOPMENT CORPUS

Expected:

```text
selected filings: 1,500
development_manifest_sha256:
d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b
```

Verify:

```text
manifest exists
1,500 rows
1,500 unique document_ids
years 2016–2020
every document resolves to EDGAR-CORPUS
```

Do not mutate the manifest.

---

# STEP 6 — VERIFY SOURCE SCHEMA

Inspect actual EDGAR-CORPUS Parquet schema.

Required expected columns:

```text
section_1
section_1A
section_7
section_7A
section_8
```

If names differ materially: **STOP AND ASK ME.**

---

# STEP 7 — BUILD CATEGORY CANDIDATES

Use only the 1,500 Task 1.1 documents.

Eligibility:

```text
business             -> non-empty section_1
risk_factors         -> non-empty section_1A
mdna                 -> non-empty section_7
market_risk          -> non-empty section_7A
financial_statements -> non-empty section_8
```

Also require company, document_id, 2016–2020 fiscal year, and `10-K`.

Do not add filings outside the development corpus.

---

# STEP 8 — EXCLUDE EMPTY-SOURCE DOCUMENTS NATURALLY

The seven known Task 1.2 empty-source filings should be ineligible because
their sections are empty.

Verify none is selected.

---

# STEP 9 — VERIFY ENOUGH CANDIDATES

Before selecting, record per-category candidate counts.

There must be enough unused candidates to select 40/category with 200 unique
target documents.

If not: **STOP AND ASK ME.**

Do not relax uniqueness or rebalance categories silently.

---

# STEP 10 — DETERMINISTIC SELECTION

Use no PRNG.

For category and document:

```text
selection_key = SHA-256(category + "\0" + document_id)
```

ascending.

Fixed category order:

```text
1. business
2. risk_factors
3. mdna
4. market_risk
5. financial_statements
```

For each category:

1. sort eligible rows by selection key,
2. skip target documents already selected,
3. take first 40.

Required final population:

```text
200 questions
200 unique target documents
40/category
```

Do not use Python built-in `hash()`.

---

# STEP 11 — RENDER QUESTIONS

Use only the frozen templates and verified company/fiscal_year provenance.

Do not paraphrase with an LLM.
Do not expose target document ID in the question text.

---

# STEP 12 — QUESTION IDS

Order final records by:

```text
category order
then target_document_id ascending
```

Assign:

```text
phase1-smoke-0001
...
phase1-smoke-0200
```

Target identity remains `target_document_id`.

---

# STEP 13 — QUESTION RECORD SCHEMA

Each record must contain at minimum:

```text
question_id
question
category
template_id
source_section_column

target_document_id
target_cik
target_company
target_form_type
target_fiscal_year
target_source_filename
target_source_split

label_granularity
retrieval_metric

development_manifest_sha256
normalizer_version
normalization_build_sha256
source_section_sha256
```

Expected fixed values:

```text
target_form_type = "10-K"
label_granularity = "document"
retrieval_metric = "doc_recall@10"
normalizer_version = "phase1-minimal-v1"
```

Do NOT add:

```text
target_chunk_id
accession
expected_answer
answer_span
XBRL fact value
```

unless a genuine prior artifact supplies it unambiguously.

Do not fabricate accession.

---

# STEP 14 — SOURCE-SECTION HASH

Store:

```text
source_section_sha256
```

over the exact UTF-8 source-section string used for eligibility.

This is provenance only, not chunk ground truth.

If source representation is ambiguous after actual inspection:
**STOP AND ASK ME.**

---

# STEP 15 — NO CHUNK-EVIDENCE CLAIM

Task 1.3 uses fixed 512-token chunks with no section-aware gold labels.

Therefore state explicitly:

```text
true chunk evidence is unavailable for Task 1.9
```

Do not manufacture a target chunk by searching for headings or choosing a
retrieved chunk.

Task 1.10 must evaluate document recall only.

---

# STEP 16 — OUTPUT FILES

Preferred tracked dataset:

```text
results/phase_1_9_smoke_evaluation.json
```

Preferred tracked config:

```text
configs/phase_1_9_smoke_evaluation.json
```

Preferred tracked summary:

```text
results/phase_1_9_smoke_evaluation_summary.json
```

If a conflicting existing Task 1.9 artifact exists:
**STOP AND ASK ME.**

Do not overwrite blindly.

---

# STEP 17 — CONFIG CONTENT

Config should capture:

```text
schema_version
target_question_count = 200
questions_per_category = 40
category order
category -> section mapping
selection algorithm
selection key format
question templates
label_granularity = document
retrieval_metric = doc_recall@10
development manifest path/checksum
```

No generation provider/model/key belongs here.

---

# STEP 18 — DATASET HASH

Compute:

```text
smoke_eval_sha256
```

over canonical JSON of the 200 logical question records only.

Use sorted keys, stable separators, UTF-8, and no timestamps inside the
hashed payload.

Do not use Python `hash()`.

---

# STEP 19 — DETERMINISM

Build twice.

Required:

```text
same 200 IDs
same questions
same categories
same targets
same provenance
same smoke_eval_sha256
```

A timestamp may differ only if excluded from the logical hash.

---

# STEP 20 — UNIQUENESS

Verify:

```text
question count = 200
unique question_id = 200
unique question text = 200
unique target_document_id = 200
```

If duplicate visible question text occurs and fixing it requires changing
templates: **STOP AND ASK ME.**

---

# STEP 21 — CATEGORY DISTRIBUTION

Required exactly:

```text
business             40
risk_factors         40
mdna                 40
market_risk          40
financial_statements 40
```

Record candidate counts and selected counts.

Do not claim population representativeness.

---

# STEP 22 — DISTRIBUTION DIAGNOSTICS

Record descriptively:

```text
questions by fiscal year
unique target CIKs
unique target companies
questions per CIK
```

Do not add year/SIC stratification in Phase 1.

---

# STEP 23 — FULL TRACEABILITY

For all 200 validate:

```text
question
→ target_document_id
→ Task 1.1 manifest row
→ exact EDGAR source row
→ assigned non-empty source section
```

No missing targets.
No target outside the development corpus.
No CIK/year/source-split mismatch.

---

# STEP 24 — MANUAL INSPECTION

Inspect at least:

```text
15 questions
3/category
```

For each check wording, company, fiscal year, target document, assigned
source section, non-empty source content, and document-target defensibility.

Do not judge retrieval performance yet.

---

# STEP 25 — OPTIONAL TINY RETRIEVER SANITY

A 3–5-question `k=10` retriever sanity check is permitted only to prove the
dataset can be consumed.

Do NOT calculate or report `doc_recall@10`.

If Task 1.6 already makes this redundant, skip it.

---

# STEP 26 — NO 200 GENERATION CALLS

Do not call OpenRouter for the 200 questions.
Do not score answers.
Do not inspect citations for all 200.

---

# STEP 27 — DO NOT IMPLEMENT TASK 1.10

Do not implement full target-doc matching, hit counts, recall, metric-run
metadata, or final printed `doc_recall@10`.

Task 1.10 owns all of that.

---

# STEP 28 — DO NOT BUILD PHASE 2 TRUTH

Do not implement:

```text
truth_contract.py
XBRL fact canonicalization
unit/qtrs/ddate validity
tag registry
DEV/TEST split
3,000-question eval
```

Task 1.9 is document-level smoke data only.

---

# STEP 29 — IMPLEMENTATION LOCATION

Prefer a narrow module such as:

```text
src/eval/smoke_dataset.py
```

and thin script:

```text
scripts/build_smoke_evaluation.py
```

Use repo-consistent names if current conventions differ.

Do not name this `truth_contract.py`.

---

# STEP 30 — TESTS

Add focused portable tests, e.g.:

```text
tests/test_smoke_evaluation_dataset.py
```

Cover at minimum:

```text
category/section mapping
empty-section rejection
SHA-256 determinism
category-sensitive selection key
used-document skipping
balanced selection
target-document uniqueness
template rendering
question-ID determinism
dataset ordering
dataset hash determinism
document-level metric labels
absence of target_chunk_id
no accession fabrication
source_section_sha256 determinism
```

No network/GPU/OpenRouter required.

---

# STEP 31 — REAL-DATA INTEGRATION TEST

Where appropriate, add a `local_data`-marked test validating the real 200
questions:

```text
200 rows
200 unique targets
40/category
all targets in Task 1.1
all assigned sections non-empty
years 2016–2020
```

Missing local data may skip per current policy; present-but-broken must fail.

---

# STEP 32 — SUMMARY

The summary should include:

```text
schema_version
question_count
unique_question_count
unique_target_document_count
category candidate counts
category selected counts
year distribution
unique CIK count
unique company count
development_manifest_sha256
normalizer_version
normalization_build_sha256
label_granularity
retrieval_metric
question_generation_method
selection_algorithm
smoke_eval_sha256
manual_inspection_count
created_at_utc
```

Do not include a recall result.

---

# STEP 33 — DOCUMENTATION

Create:

```text
project_plan/PHASE1_SMOKE_EVALUATION.md
```

Document:

- purpose,
- exact 200-question count,
- five categories,
- 40/category,
- section mappings,
- templates,
- SHA-256 selection,
- document-level ground truth,
- `doc_recall@10` label,
- lack of true chunk evidence,
- provenance schema,
- determinism/hash,
- manual inspection,
- known limitations,
- Task 1.7a's unresolved 8/10 citation-format warning,
- Task 1.10 as next consumer.

State prominently:

```text
NOT THE FINAL BENCHMARK
```

---

# STEP 34 — UPDATE REPOSITORY STRUCTURE

Update `project_plan/REPOSITORY_STRUCTURE.md` narrowly.

Be precise that `src/eval/` contains:
- citation-integrity smoke logic,
- Phase 1 smoke dataset builder.

The Phase 2 truth-contract system remains unimplemented.

---

# STEP 35 — BUILD COMMAND

Provide one command:

```bash
python scripts/build_smoke_evaluation.py
```

It must:

1. validate Task 1.1 provenance,
2. read EDGAR source read-only,
3. build category candidate pools,
4. verify enough unique candidates,
5. deterministically select 40/category,
6. render 200 questions,
7. validate provenance,
8. compute `smoke_eval_sha256`,
9. write dataset + summary,
10. exit non-zero on invariant failure.

No network.
No generation.
No vector search required.

---

# STEP 36 — REAL BUILD + SECOND BUILD

Run against actual local data.

Required:

```text
questions               200
unique question IDs     200
unique question text    200
unique targets          200
each category            40
```

Then rerun to prove deterministic logical identity.

Do not silently overwrite a conflicting artifact.

---

# STEP 37 — SAFETY

Confirm unchanged:

```text
Task 1.1 manifest
normalized Markdown
chunks
embeddings
LanceDB index
retriever behavior
generation behavior
citation validator
frozen data/
```

No API key needed.
No network needed.

---

# STEP 38 — TEST SUITES

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Required: zero failures.

Use actual current counts.

---

# STEP 39 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Expected trackable files may include:

```text
src/eval/smoke_dataset.py
scripts/build_smoke_evaluation.py
configs/phase_1_9_smoke_evaluation.json
results/phase_1_9_smoke_evaluation.json
results/phase_1_9_smoke_evaluation_summary.json
tests/test_smoke_evaluation_dataset.py
project_plan/PHASE1_SMOKE_EVALUATION.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Do not stage `.env`, data, artifacts, embeddings, LanceDB fragments, or large
source dumps.

Run secret/personal-path scan.

---

# STEP 40 — UPDATE Progress.md

Append:

```markdown
## YYYY-MM-DD — Phase 1.9 200-Question Smoke Evaluation
```

Preserve all history.

Record explicitly:

```text
Task 1.7a ended 8/10 with two residual fullwidth citation-format failures.
User explicitly approved proceeding to Task 1.9 with that limitation
documented.
```

Do not state the warning was resolved.

Include:
- objective,
- initial state,
- 200-question contract,
- deterministic selection,
- category candidate/selected counts,
- dataset paths/hash,
- year/company/CIK distribution,
- document-level ground-truth limitation,
- manual inspection,
- tests,
- safety,
- Git,
- result.

Use exactly one result:

```text
PASS — deterministic 200-question document-target smoke evaluation built

WARN — 200-question smoke set built with one documented non-blocking issue

BLOCKED — a defensible deterministic 200-question smoke set could not be built
```

If PASS:

```text
1.8 Citation Integrity Smoke               — COMPLETE WITH HISTORICAL WARN
1.7a Citation Format Compliance Correction — COMPLETE WITH WARN
1.9 200-Question Smoke Evaluation           — COMPLETE
1.10 Baseline Metric Runner                 — NEXT
```

---

# STEP 41 — COMMIT

After real build, determinism, provenance validation, manual inspection,
tests, safety, and Progress update all succeed, create one coherent commit.

Preferred message:

```text
Add Phase 1 smoke evaluation set
```

Do not include Task 1.10.

Do not tag Phase 1 yet.

---

# STEP 42 — PUSH POLICY

Inspect:

```bash
git remote -v
```

If no remote:

```text
push deferred — no remote configured
```

Do not invent one.

If authorization is unclear: **STOP AND ASK ME.**

Never force-push.

---

# ACCEPTANCE CRITERIA

```text
[ ] Task 1.7a 8/10 WARN preserved truthfully
[ ] user decision to proceed recorded
[ ] Task 1.10 not started

[ ] Task 1.1 manifest verified
[ ] 1,500 selected docs verified
[ ] manifest checksum matches
[ ] required EDGAR section columns verified

[ ] exactly 200 questions
[ ] 200 unique question IDs
[ ] 200 unique question texts
[ ] 200 unique target documents

[ ] 40 business
[ ] 40 risk_factors
[ ] 40 mdna
[ ] 40 market_risk
[ ] 40 financial_statements

[ ] every target inside Task 1.1
[ ] assigned source section non-empty
[ ] no known empty-source doc selected
[ ] all targets 10-K / 2016–2020

[ ] deterministic SHA-256 selection
[ ] no PRNG
[ ] fixed category order documented
[ ] fixed templates documented
[ ] no LLM question generation
[ ] no network access

[ ] document-level provenance retained
[ ] label_granularity=document
[ ] retrieval_metric=doc_recall@10
[ ] source_section_sha256 retained
[ ] no fabricated accession
[ ] no target_chunk_id claim
[ ] no expected answer fabricated

[ ] smoke_eval_sha256 canonical and deterministic
[ ] two builds logically identical
[ ] all 200 source traces validated

[ ] 15 manual inspections
[ ] 3/category

[ ] focused Task 1.9 tests
[ ] real-data validation where appropriate
[ ] doctor passes
[ ] portable suite zero failures
[ ] full suite zero failures

[ ] no doc_recall@10 runner
[ ] no 200-question generation calls
[ ] no answer scoring
[ ] no Phase 2 truth contract
[ ] no DEV/TEST split

[ ] upstream artifacts unchanged
[ ] frozen data unchanged

[ ] PHASE1_SMOKE_EVALUATION.md created
[ ] REPOSITORY_STRUCTURE.md updated narrowly
[ ] Progress.md updated without erasing citation WARN history

[ ] staged content reviewed
[ ] one Task 1.9 commit created
[ ] no Task 1.10 work
[ ] no force-push
```

---

# STOP CONDITIONS

STOP AND ASK ME if:

```text
Task 1.7a result differs materially from 8/10
Task 1.1 manifest count/checksum differs
required EDGAR section columns differ
a category cannot supply 40 unused eligible docs
duplicate visible questions require changing templates
an existing Task 1.9 artifact conflicts
provenance would require fabricated accession/chunk evidence
you believe XBRL should become answer truth in Task 1.9
you believe an LLM should generate questions
a dependency change appears necessary
implementation starts calculating doc_recall@10
repo docs materially conflict
Git push authorization is unclear
any other durable decision would require guessing
```

---

# IMPORTANT NON-GOALS

Task 1.9 does NOT:
- fix Task 1.7a citation formatting,
- switch generation model,
- call OpenRouter,
- run 200 generations,
- score generated answers,
- validate semantic citation support,
- calculate `doc_recall@10`,
- implement Task 1.10,
- create XBRL truth-contract logic,
- create the 3,000-question final eval,
- create DEV/TEST splits,
- create chunk-level gold labels,
- add BM25/reranking/CRAG/router,
- implement FastAPI.

---

# FINAL RESPONSE TO ME

After completing Task 1.9, return:

## Task

```text
task_1.9_200_question_smoke_evaluation.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Accepted Warning

Report Task 1.7a's before/after citation-smoke result and the user decision
to proceed.

## Input

Report manifest path/checksum, selected corpus size, and year range.

## Dataset

Report dataset path, summary path, question count, unique question count,
unique target documents, and `smoke_eval_sha256`.

## Category Distribution

Report candidate and selected counts for all five categories.

## Target Distribution

Report questions by year, unique CIKs, unique companies, and max questions
per CIK.

## Label Contract

Confirm:

```text
label granularity = document
metric label = doc_recall@10
true chunk evidence = NO
expected answer truth = NO
```

## Determinism

Report whether two builds produced identical IDs/questions/targets/hash.

## Traceability

Report:

```text
200/200 targets in Task 1.1
200/200 source rows resolved
200/200 assigned source sections non-empty
```

## Manual Inspection

Report 15 inspected, 3/category, and result.

## Tests

Report new tests, portable/full counts, doctor.

## Safety

Confirm no OpenRouter calls, no source mutation, no retrieval/generation/
citation-validator changes, no Task 1.10 metric runner.

## Files Modified

List actual tracked files only.

## Git

Report commit created, hash, message, remote, push status.

## Progress.md

Confirm the Task 1.9 entry was appended and Task 1.7a's WARN remains visible.

## Next Task

If PASS:

```text
task_1.10_baseline_metric_runner.md
```

Do not start it.

Finally state:

```text
No Task 1.10 work started.
```

Stop and wait for my approval.
