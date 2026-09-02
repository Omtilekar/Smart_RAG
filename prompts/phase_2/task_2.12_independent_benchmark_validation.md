# Task 2.12 — Independent Benchmark Validation (FinanceBench)

## Phase

**Phase 2 — Make the Numbers Trustworthy**

Current confirmed repository state:

```text
Data Preparation                              — COMPLETE
Phase 0 — Foundation                          — COMPLETE
Phase 1 — Make It Work End to End             — COMPLETE WITH WARN

Phase 2 — Make the Numbers Trustworthy        — IN PROGRESS
  2.1 XBRL Truth Contract                     — COMPLETE
  2.2 Freeze Supported Tag Registry           — COMPLETE
  2.3 Build Full Evaluation Dataset           — COMPLETE WITH NOTE
  2.4 DEV/TEST Split                          — COMPLETE
  2.5 Evaluation Schema                       — COMPLETE
  2.6 Metric Unit Tests                       — COMPLETE
  2.7 MS MARCO Harness Validation             — COMPLETE
  2.8 Primary Evidence Alignment              — COMPLETE WITH NOTE
  2.9 Freeze Chunk Metadata Schema            — COMPLETE
  2.10 Config Hashing & Artifact Versioning   — COMPLETE
  2.11 Evaluation Run Logging                 — COMPLETE
  2.12 Independent Benchmark Validation       — CURRENT
  2.13 LLM-as-Judge Validation                — DO NOT START
```

Known notes/warnings remain historical facts and must not be erased:

```text
Phase 1 citation-format compliance: 8/10
Task 2.3 narrative pending_review: 50, not gold
Task 2.8 current internal chunk gold: 0 because primary docs are FY2021–2024
  while the frozen truth contract is FY2016–2020
Task 2.6 numeric_tolerance_match: deferred
Task 2.6 citation_grounding: deferred
Task 2.6 faithfulness: deferred
official protected SEC TEST evaluations consumed: 0/3
```

Do not start Task 2.13 during this task.

---

# 1. Objective

Validate the project's evaluation and RAG machinery against an **independent external financial QA benchmark**, FinanceBench, without changing the benchmark to fit the system and without tuning the system to the benchmark.

Task 2.12 should answer:

```text
Can this repository consume an independently authored financial QA benchmark,
preserve its questions/answers/evidence correctly,
construct a leakage-free benchmark corpus,
run the frozen baseline retrieval/generation path where the roadmap requires it,
score only what can be scored defensibly,
record the run with Task 2.11 provenance,
and explain any difference between our metrics and the benchmark paper's protocol?
```

The purpose is **independent validation**, not leaderboard optimization.

The central rule is:

```text
FinanceBench is external evidence about our evaluation system.
It is not a tuning set for Phase 3.
```

---

# 2. Hard Precondition — Verify Task 2.11

Before implementing anything, inspect the actual repository.

Verify:

```text
Task 2.11 Evaluation Run Logging = COMPLETE
```

Expected current evidence includes:

```text
src/eval/run_logging.py
results/phase_2_11_evaluation_run_logging.json
project_plan/PHASE2_EVALUATION_RUN_LOGGING.md
```

Also verify the Task 2.11 commit exists and the repository is not carrying unexplained changes.

If Task 2.11 is not verifiably complete:

```text
STOP.
TASK 2.12 NOT STARTED.
```

Do not implement missing Task 2.11 functionality inside Task 2.12 except for a narrowly justified compatibility extension required to represent an external benchmark honestly, as described later in this prompt.

---

# 3. Read the Authoritative Task 2.12 Contract First

Before code changes, read:

1. `project_plan/PROJECT_EXECUTION.md`
2. `Progress.md`
3. `project_plan/PHASE2_EVALUATION_RUN_LOGGING.md`
4. `src/eval/run_logging.py`
5. `project_plan/PHASE2_ARTIFACT_VERSIONING.md`
6. `src/artifacts/versioning.py`
7. `project_plan/PHASE2_EVALUATION_SCHEMA.md`
8. `src/eval/evaluation_schema.py`
9. `src/eval/eval_store.py`
10. `src/eval/metrics.py`
11. `project_plan/PHASE2_METRIC_TESTS.md`
12. Task 2.7 MS MARCO harness code/docs
13. Task 2.8 parser/evidence code/docs
14. Phase 1 retriever/generation code and configs
15. `project_plan/GIT_CONVENTIONS.md`
16. `project_plan/REPOSITORY_STRUCTURE.md`
17. `src/storage.py`
18. `.gitignore`

Then read the exact Task 2.12 section in the **current local** `PROJECT_EXECUTION.md`.

If the authoritative local Task 2.12 scope materially differs from this prompt:

```text
PROJECT_EXECUTION.md WINS.
```

Document the discrepancy in `Progress.md` instead of silently broadening or narrowing the task.

---

# 4. Establish Baseline

Before changes:

```bash
git branch
git status --short
git log --oneline --decorate -15

python --version
python -c "import sys; print(sys.executable)"

python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Record:

```text
HEAD
working-tree state
portable-test baseline
full-test baseline
Task 2.11 run-schema version
Task 2.10 artifact-manifest version
chunk_schema_version
chunk_config_hash
embedding identity hash
index identity hash
internal eval_set_version
internal split_version
official SEC TEST runs consumed
```

Historical Task 2.11 reference:

```text
full suite: 1,059 passed
SEC TEST runs consumed: 0/3
```

Verify actual current values rather than forcing historical numbers.

---

# 5. Official FinanceBench Source Only

Use only the **official Patronus AI FinanceBench source** for benchmark questions, answers, evidence, metadata, and benchmark PDFs.

Expected public state at task drafting time:

```text
open-source FinanceBench sample: 150 annotated examples
full benchmark described by authors: 10,231 questions
public/open-source subset: 150 only
```

Do not attempt to obtain closed/private FinanceBench examples by scraping, guessing URLs, or bypassing access controls.

Unless the user has separately supplied authorized access to the full benchmark:

```text
Task 2.12 population = official open-source 150-example sample.
```

If the authoritative local roadmap explicitly requires a different authorized population, follow it and record why.

---

# 6. License / Redistribution Gate

Before downloading or committing anything, inspect the official dataset license and repository terms.

Expected current dataset-card license:

```text
CC BY-NC 4.0
```

Verify it from the official source.

Document:

```text
source organization
source repository/dataset
license
resolved revision or source commit if available
retrieval date
```

Do not commit third-party PDFs or large benchmark source payloads unless their license and the repository's Git policy clearly permit that.

Default:

```text
benchmark raw data / PDFs: local, ignored
tracked: configs, source revision/hashes, tests, summaries, docs
```

If license terms conflict with planned use or redistribution:

```text
STOP and surface the issue.
```

Do not silently treat an external benchmark as unrestricted project data.

---

# 7. Freeze a Reproducible Benchmark Source

Do not use a moving `main` branch without recording identity.

Freeze as much provenance as the official source exposes:

```text
repository or dataset revision/commit
question file SHA-256
metadata file SHA-256
PDF SHA-256 per document or a canonical document-manifest hash
```

If downloading from Hugging Face, record the resolved dataset revision/file hashes.

If downloading from the official GitHub repository, record the resolved Git commit and file hashes.

Do not rely on:

```text
"downloaded today"
"latest"
filesystem mtime
```

as benchmark identity.

---

# 8. Suggested Local Layout

Keep FinanceBench separate from the project's internal SEC corpus.

Use the repository's storage conventions after inspecting them.

A reasonable layout is:

```text
data/financebench/                    # frozen third-party benchmark inputs, ignored
artifacts/benchmark/financebench/     # derived parse/chunk/embed/index outputs, ignored
results/phase_2_12_financebench_validation.json
```

If `src/storage.py` needs one narrow read-only helper such as `financebench_root`, add it only if consistent with the storage architecture.

Do not insert FinanceBench PDFs/chunks into:

```text
Phase 1 SEC chunks
Phase 1 SEC embeddings
Phase 1 SEC LanceDB table
Task 2.3 internal eval dataset
Task 2.4 DEV/TEST/CI artifacts
Task 2.8 primary-document evidence artifacts
```

FinanceBench is an isolated external benchmark namespace.

---

# 9. Network Policy

Task 2.12 may require network access **only to acquire official FinanceBench benchmark assets** if they are not already local.

Permitted, when required:

```text
official PatronusAI FinanceBench dataset/repository
its official benchmark PDFs
```

Do not crawl random mirrors or investor websites when the official repository provides the benchmark documents.

After acquisition, all parsing/indexing/evaluation should be reproducible offline from the frozen local copy.

No benchmark download may occur implicitly during normal unit tests.

---

# 10. Validate the Benchmark Before Using It

Independently inspect the downloaded source.

Do not merely trust a README.

Verify at minimum:

```text
question row count
unique financebench_id count
null/empty question count
null/empty answer count
unique doc_name count
doc_type distribution
doc_period distribution
company count
question_type distribution if present
question_reasoning distribution if present
evidence-item count distribution
questions with zero evidence
document-reference integrity
```

Expected open-source row count:

```text
150
```

If the official open-source source no longer contains exactly the expected sample or has materially changed schema:

```text
STOP before evaluation.
```

Investigate and document the new official state.

Do not silently truncate or select 150 rows from a larger/mutated dataset to reproduce an old assumption.

---

# 11. Preserve Original Benchmark Fields

Keep original FinanceBench fields intact in the benchmark manifest where practical.

Potential official fields include:

```text
financebench_id
company
doc_name
doc_type
doc_period
doc_link
question
answer
justification
evidence
question_type
question_reasoning
gics_sector
```

Inspect the actual chosen official source because schemas differ slightly between repository versions/views.

Do not rename fields in a way that loses provenance.

A normalized internal benchmark record may add fields, but original benchmark identity must remain recoverable.

---

# 12. Benchmark Document Integrity

For every question, verify its referenced document exists locally or has a documented failure reason.

Report:

```text
questions total
documents referenced
documents successfully acquired
documents missing/corrupt
questions blocked by missing documents
```

PDF identity should be deterministic:

```text
doc_name
source URL/reference
SHA-256
size bytes
page count where available
```

A missing document must never cause the question to disappear silently from the denominator.

---

# 13. No Gold-Evidence Leakage

This is a hard rule.

FinanceBench supplies gold evidence.

Gold evidence is for **evaluation**, not retrieval input.

Do NOT create the retrieval corpus by indexing:

```text
evidence_text
justification
gold answer
question
```

The retrieval corpus must come from the benchmark's original source documents/PDFs.

The only acceptable use of FinanceBench evidence during retrieval evaluation is:

```text
source document/PDF
      ↓
parse/chunk/index independently
      ↓
retrieve from the document corpus
      ↓
compare retrieved evidence with gold evidence labels
```

Never:

```text
gold evidence text
      ↓
index
      ↓
retrieve
```

That is leakage and must FAIL Task 2.12.

---

# 14. Parse PDFs With Source/Page Identity

FinanceBench uses financial documents/PDFs.

Reuse the repository's existing parser stack where practical, especially any Docling dependency introduced for Task 2.8, but do not force the HTML-specific inline-XBRL pipeline onto PDFs.

For each parsed page/node preserve at minimum:

```text
benchmark document identity
doc_name
page number
node/element order
content type
text
table identity where preserved
```

Page numbering must be explicit:

```text
source page convention
internal page convention
```

If FinanceBench evidence page numbers are zero-indexed in the selected source version, preserve that fact explicitly rather than mixing it with 1-indexed PDF display pages.

Do not use OCR unless the PDF genuinely lacks extractable text and the authoritative roadmap permits a fallback.

If OCR is required for any document, record those documents separately.

---

# 15. Table Preservation

FinanceBench contains financial questions where tables matter.

Do not flatten tables into an unusable character stream if the current parser can preserve structure.

For table-bearing pages preserve:

```text
table identity
row order
cell text
header information where recoverable
page identity
```

Task 2.12 does not perform a table-serialization ablation.

Use one predetermined representation before seeing benchmark results.

Do not select a representation because it scores better on FinanceBench.

---

# 16. Evidence Mapping Contract

Create deterministic benchmark evidence labels from FinanceBench's supplied evidence.

Preferred hierarchy:

```text
financebench question
    ↓
doc_name
    ↓
gold page(s) / evidence item(s)
    ↓
parsed page/node
    ↓
benchmark chunk IDs
```

Use the strongest official evidence metadata first.

If exact evidence page numbers exist:

```text
page identity is authoritative
```

If only evidence text is available for some source version:

use deterministic text normalization/alignment and document the method.

Do not use an LLM to decide where evidence belongs.

Task 2.13 owns LLM-as-judge validation.

---

# 17. Evidence Alignment Status

Every evidence item should end in an explicit status such as:

```text
exact
normalized_exact
ambiguous
unmatched
document_missing
parse_failure
```

Do not fabricate a confidence probability.

Only exact/defensibly normalized-exact alignments should become retrieval gold.

Ambiguous/unmatched evidence remains diagnostic, never silently promoted.

Report evidence-alignment coverage before headline retrieval metrics.

---

# 18. Benchmark Chunking

Use a **frozen predetermined chunking configuration**.

Do not tune chunk size/overlap against FinanceBench.

Prefer reusing the project's existing baseline semantics where they apply:

```text
BAAI/bge-small-en-v1.5 tokenizer
512 content-token baseline
zero overlap
keep final partial window
```

However, FinanceBench evidence is page-oriented, so do not create chunks that make gold mapping impossible merely to imitate a historical implementation detail.

If page-bounded chunking is required to preserve benchmark evidence identity:

```text
freeze it before evaluation
version/hash it
explain why it is benchmark-specific
```

Do not present a benchmark-specific page boundary as a new production chunking recommendation.

---

# 19. Benchmark Chunk Identity

Use deterministic benchmark chunk IDs.

They must preserve:

```text
benchmark name/version
doc_name
page identity
ordinal/local ID
chunk configuration identity
```

Do not collide with SEC Phase 1/Task 2.9 chunk IDs.

Do not mutate Task 2.9's internal SEC canonical chunk schema merely to make FinanceBench fit.

Benchmark-specific extension metadata such as `page_number` is acceptable and should be documented.

---

# 20. Frozen Baseline Retrieval Configuration

Task 2.12 validates the current system.

It does not select the future Phase 3 stack.

Before measuring FinanceBench, freeze the exact retrieval configuration from existing project contracts.

At minimum record:

```text
embedding model repository
resolved revision
embedding dimension
normalize_embeddings
query prefix
passage convention
similarity metric
search type
top_k
```

If the local Task 2.12 roadmap names a specific configuration, use it.

Otherwise reuse the existing Phase 1 baseline wherever semantically applicable.

Do not run:

```text
BM25 sweep
hybrid weighting sweep
chunk-size sweep
model comparison
reranker comparison
query-rewrite tuning
prompt tuning
```

Task 2.12 produces one predetermined independent validation result.

---

# 21. Benchmark-Specific Index Isolation

Build a separate FinanceBench index.

Example conceptual location:

```text
artifacts/benchmark/financebench/<benchmark-config-hash>/index/
```

Do not mix FinanceBench vectors into the SEC Phase 1 LanceDB database.

Record:

```text
benchmark source hash
parse config hash
chunk config hash
embedding identity
index identity
row count
```

Reuse Task 2.10 canonical semantic-hash utilities rather than inventing another hashing convention.

---

# 22. Global Retrieval Must Be the Headline

Do not pre-filter retrieval to the gold `doc_name` for the headline benchmark result.

A gold-document prefilter leaks answer-side information.

Headline retrieval should search the complete FinanceBench benchmark corpus available to the run.

If useful, an **oracle-document** diagnostic may also be reported separately:

```text
GLOBAL retrieval       — headline
ORACLE-DOCUMENT retrieval — diagnostic only
```

Never mix the two or label oracle-document results as normal retrieval performance.

---

# 23. Retrieval Metrics

Use deterministic metrics whose gold semantics are defensible.

Potential benchmark metrics:

```text
document recall@k
document MRR
page/evidence recall@k
chunk/evidence MRR
nDCG@k where relevance semantics support it
```

Use Task 2.6 metric implementations when their definitions match exactly.

Do not reuse an internal metric merely because its name looks similar.

For example:

```text
SEC accession-level document relevance
```

is not automatically identical to:

```text
FinanceBench doc_name relevance.
```

Adapt only the identifier abstraction, not the mathematical definition, and test it.

---

# 24. Evidence Coverage Before Evidence Metrics

Do not report chunk/evidence recall as if all 150 questions have exact evidence labels unless they actually do.

First report:

```text
questions with exact/usable evidence labels
questions with ambiguous evidence
questions with unmatched evidence
questions blocked by missing documents
```

Evidence-level metrics must state their denominator explicitly.

Do not silently drop failures from the denominator.

If a metric is evaluated only on the exact-evidence subset, label it exactly that way.

---

# 25. Internal Chunk-Gold Availability Must Not Change

FinanceBench may provide independent external evidence labels.

That does **not** fix Task 2.8's internal SEC gold mismatch.

Do not change:

```text
chunk_recall@10.available_for_current_gold
chunk_mrr.available_for_current_gold
```

for the internal Phase 2 benchmark merely because FinanceBench can support external evidence metrics.

Keep internal and external benchmark availability distinct.

---

# 26. Generation Scope — Follow PROJECT_EXECUTION.md

FinanceBench is a financial QA benchmark, but do not assume Task 2.12 must call an LLM unless the authoritative local Task 2.12 contract requires answer generation.

If Task 2.12 is retrieval/evidence validation only:

```text
LLM calls = 0
API spend = $0
```

If the authoritative task explicitly requires the existing generation path:

- use the already frozen Phase 1 generation provider/model/settings;
- do not select a new model from current leaderboards;
- keep temperature/determinism semantics unchanged;
- estimate API calls/token usage/cost before the full run;
- require valid local credentials;
- do not expose credentials in logs/run records;
- do not call Task 2.13's LLM judge.

If credentials are absent and generation is a required acceptance criterion:

```text
STOP / BLOCKED.
```

Do not silently substitute another model.

---

# 27. Deterministic Answer Scoring Only

Task 2.12 must not implement the Task 2.13 LLM judge.

Score answers only with deterministic methods that are already frozen or can be defended mathematically.

Possible diagnostics:

```text
normalized exact string match
numeric exact match on safely parsed numeric-answer subset
correct refusal behavior only if benchmark contains a legitimate refusal population
```

Do not invent a numeric tolerance policy.

`numeric_tolerance_match` remains deferred unless a separately frozen policy already exists by the time this task runs.

Do not use fuzzy semantic similarity as a substitute for correctness.

---

# 28. FinanceBench Paper Comparability Warning

The FinanceBench paper's reported answer evaluations were manually reviewed for the evaluated model configurations.

Therefore:

```text
our deterministic exact/numeric metric
!=
FinanceBench paper human-reviewed accuracy
```

unless an apples-to-apples evaluator/protocol is genuinely reproduced.

Do not claim:

```text
"we achieved FinanceBench accuracy X"
```

if X comes from a different scoring protocol.

Use labels such as:

```text
our deterministic exact-match diagnostic
our retrieval evidence recall
official paper result — NOT DIRECTLY COMPARABLE
```

Task 2.13 may later validate an LLM-as-judge against human labels.

---

# 29. Published Baseline Comparisons

If the roadmap asks for comparison with published FinanceBench results:

freeze the comparison source before seeing the final measured result.

For each comparison record:

```text
paper/model configuration
retrieval/context configuration
judge/evaluation protocol
reported metric
our protocol compatibility
```

Classify:

```text
COMPARABLE
PARTIALLY COMPARABLE
NOT COMPARABLE
```

Do not force a numeric pass threshold where the protocols differ.

A correct `NOT COMPARABLE` conclusion is better than a misleading benchmark claim.

---

# 30. Task 2.11 Run Logging Must Be Used

Task 2.12 is the first clear opportunity for a real post-Task-2.11 experiment record.

For every actual benchmark execution that produces headline metrics, write an immutable Task 2.11 run record.

At minimum bind:

```text
run_id
git_sha
chunk_config_hash / benchmark chunk config identity
embedding model identity
retrieval config
reranker config
generation model
split / benchmark population
eval_set_version / benchmark version
timestamp
metrics
```

Do not create a fake run record if no real benchmark run occurred.

---

# 31. External-Benchmark Run-Logging Semantics Gate

Inspect `src/eval/run_logging.py` before writing FinanceBench records.

Task 2.11 intentionally reused the internal Task 2.5 split semantics.

FinanceBench is not the internal:

```text
dev
ci
test
```

population.

Do NOT lie by calling FinanceBench the protected SEC `test` split.

Do NOT increment the internal TEST access budget.

If the current run-log schema can already represent an external benchmark honestly, reuse it unchanged.

If it cannot, implement the **smallest backwards-compatible extension** required to distinguish:

```text
internal Phase 2 evaluation
external benchmark evaluation
```

Possible semantics may include:

```text
evaluation_source / run_kind
benchmark_name
benchmark_version
benchmark_source_hash
benchmark_split/population
```

If changing run-record meaning/schema is required:

- increment `EVALUATION_RUN_SCHEMA_VERSION` according to Task 2.11's evolution policy;
- keep existing version-1 records readable;
- do not modify Task 2.5's internal `VALID_SPLITS` merely to accommodate FinanceBench;
- add migration/compatibility tests;
- document the extension explicitly.

Do not silently shoehorn external benchmark identity into internal split semantics.

---

# 32. FinanceBench Benchmark Identity

Define an explicit semantic benchmark identity, for example conceptually:

```text
financebench-open-source-150-v1
```

Only use a name like that if it accurately reflects the frozen official source.

Identity inputs should include:

```text
official dataset revision/file hash
question population
source document manifest hash
evidence-alignment version
```

Do not include timestamps/Git SHA in the semantic benchmark identity.

---

# 33. Benchmark Config

Create a tracked config such as:

```text
configs/phase_2_12_financebench_validation.json
```

Record result-affecting semantics:

```text
benchmark source/revision
benchmark population
parser settings
page-number convention
chunking settings
embedding identity
retrieval/index settings
top_k values
generation settings if required
deterministic scoring methods
evidence-alignment policy
```

Compute a deterministic config hash using Task 2.10 utilities.

Do not put secrets, timestamps, or personal paths into the config hash.

---

# 34. Preflight Before Expensive Work

FinanceBench's public sample is small compared with MS MARCO, but still perform a preflight.

Print:

```text
question count
unique document count
PDF count/bytes
estimated parsed bytes
estimated chunk count
embedding dimension
estimated vector bytes
existing reusable artifacts
network assets missing
```

If the actual benchmark source unexpectedly requires substantially more storage/download than anticipated, report before proceeding.

Do not re-run any multi-million-passage MS MARCO build.

---

# 35. Pilot First

Before processing the full benchmark, use a deterministic small pilot.

For example:

```text
10–20 questions spanning multiple companies/document types/question types
```

Pilot must verify:

```text
source document resolution
PDF parsing
page identity
table survival where relevant
evidence alignment
chunk generation
embedding/index build
retrieval
metric calculation
Task 2.11 run-record construction in tmp_path / dry-run mode
```

Pilot results are not headline benchmark results.

Label them:

```text
PILOT ONLY
```

Do not tune settings based on pilot scores; only fix correctness defects.

---

# 36. Manual Pilot Audit

Select deterministic pilot examples.

Include where available:

```text
simple extraction
multi-step arithmetic/reasoning
cash-flow / balance-sheet / income-statement question
table-heavy evidence
narrative evidence
multiple evidence items
```

For each manually trace:

```text
financebench_id
question
gold answer
gold evidence
doc_name
source PDF/page
parsed text/table
mapped gold chunk(s)
retrieved result(s)
metric contribution
```

Do not cherry-pick only successes.

---

# 37. Full Benchmark Run

Only after pilot correctness passes, run the full official open-source population.

Expected population at drafting time:

```text
150 questions
```

Every source question must end in an explicit terminal status, for example:

```text
evaluated
blocked_document_missing
blocked_parse_failure
blocked_evidence_unmatched
infrastructure_error
```

Do not silently reduce the denominator.

Report exact counts.

---

# 38. Infrastructure Errors Are Not Retrieval Misses

Preserve the Task 2.5 evaluation distinction.

Do not convert:

```text
PDF missing
parser crash
index failure
model load failure
API failure
```

into:

```text
retrieval miss
wrong answer
```

Infrastructure failures need their own status.

Headline benchmark metrics must state how infrastructure failures affect denominators.

---

# 39. Determinism

From saved retrieval outputs, recompute deterministic metrics twice.

Expected:

```text
same evaluated question set
same metric values
same canonical metric/result hash
```

Where retrieval itself is deterministic, rerun a manageable subset twice and verify identical ranked IDs/scores within justified numeric tolerance.

Do not rerun external generation solely to test determinism if it costs API money and the provider is not guaranteed bit-deterministic.

Instead validate deterministic logging/scoring from saved outputs.

---

# 40. Independent Metric Recalculation

Independently recompute at least the headline retrieval metric from saved ranked IDs + gold evidence labels without calling the production aggregate helper.

Example:

```text
production evidence_recall@10:  X
independent recomputation:       X
```

They must agree exactly or within a mathematically justified tolerance.

If generation exact/numeric metrics are reported, independently recompute those too.

---

# 41. Breakdown Diagnostics

Report benchmark results by useful official categories where sample sizes permit.

Examples:

```text
question_type
question_reasoning
doc_type
doc_period
gics_sector
single vs multiple evidence items
```

Do not over-interpret tiny slices.

Always print sample size beside slice metrics.

These are diagnostics, not tuning targets.

---

# 42. No FinanceBench Tuning

Do NOT change configuration after seeing the full benchmark result to improve the score.

Specifically no:

```text
changing k
changing chunk size
giving larger context only to misses
changing prompts based on failure cases
changing model
changing reranker
changing query prefix
adding gold-document filters
```

If a genuine implementation bug is discovered:

1. document it;
2. fix it;
3. invalidate the affected run;
4. create a **new run_id**;
5. preserve the old result as failed/superseded if already persisted.

Do not overwrite history.

---

# 43. No LLM-as-Judge

Task 2.13 owns LLM-as-judge validation.

Task 2.12 must not implement or silently use:

```text
GPT judge
Claude judge
OpenRouter judge
semantic grading prompt
faithfulness judge
```

If FinanceBench answer correctness cannot be scored reliably without human/LLM judgment:

report the deterministic subset/diagnostics honestly and state:

```text
FULL SEMANTIC ANSWER ACCURACY DEFERRED TO TASK 2.13
```

Do not fake certainty with embedding similarity.

---

# 44. Protected Internal SEC TEST Discipline

FinanceBench is external.

It must not consume the protected internal Phase 2 TEST budget.

Do NOT:

```text
load artifacts/eval/phase_2_4_test.json
call load_test_set()
run internal SEC TEST retrieval/generation
```

Required invariant:

```text
official SEC TEST evaluations consumed = 0/3
```

A FinanceBench run is not an internal SEC TEST run.

Keep the terminology separate in logs/docs.

---

# 45. Result Artifacts

Create a compact tracked summary such as:

```text
results/phase_2_12_financebench_validation.json
```

Include at minimum:

```text
benchmark name/version
source/revision
license
question count
document count
source hashes
benchmark config hash
parse/chunk/evidence coverage
retrieval configuration
retrieval metrics
generation configuration if used
deterministic answer diagnostics if used
published-comparison status
run_id(s)
Task 2.11 run-record path(s)
manual audit count
determinism result
independent metric recomputation result
TEST budget status
final verdict
```

Large parsed PDFs/chunks/embeddings/index/retrieval traces remain ignored under benchmark artifacts.

Hash large derived artifacts/manifests where useful.

---

# 46. Per-Question Evidence Artifact

Preserve enough per-question data to independently recompute metrics, but keep large payloads out of Git.

A derived ignored artifact may contain:

```text
financebench_id
doc_name
gold evidence IDs/pages/chunks
retrieved document/chunk IDs
ranks
scores
answer output if generation was required
per-question deterministic metric contributions
status/error type
```

Do not duplicate full PDFs or giant context strings in tracked JSON.

Record the artifact SHA-256 in the tracked summary.

---

# 47. Tests

Create focused tests, likely:

```text
tests/test_financebench_validation.py
```

or an equivalent repository-consistent layout.

Cover at minimum:

### Dataset validation

```text
unique benchmark IDs
required fields
missing question/answer rejection
document-reference integrity
```

### Evidence

```text
page-number normalization
evidence alignment exact case
normalized whitespace case
ambiguous case
unmatched case
multiple evidence items
no arbitrary first-match selection
```

### Leakage prevention

```text
gold answer never enters retrieval corpus
gold evidence text never enters retrieval corpus
question text never indexed as document content
```

### Chunking/IDs

```text
deterministic benchmark chunk IDs
page identity retained
config change changes identity
```

### Retrieval metrics

```text
gold item at rank 1
gold item at rank k
multiple gold evidence items
no gold retrieved
infrastructure error separated from miss
```

### Run logging

```text
FinanceBench external run identity represented honestly
no internal TEST-budget mutation
Task 2.10/2.11 identities reused
schema-version compatibility if extension required
```

### Security

```text
no secrets in configs/run records
no absolute personal paths
```

Use tiny synthetic fixtures.

Do not make portable tests download FinanceBench or parse all PDFs.

---

# 48. Local-Data / Benchmark Tests

Mark real benchmark integration tests with an appropriate marker such as:

```text
local_data
benchmark
```

following existing pytest conventions.

A local integration test may inspect a tiny frozen FinanceBench sample/document set.

Normal portable CI must not:

```text
download benchmark data
parse every PDF
build full benchmark index
call external generation APIs
```

---

# 49. Audit / Runner Script

Provide explicit entry points according to repository conventions.

Likely:

```text
scripts/run_financebench_validation.py
```

Prefer modes such as:

```bash
python scripts/run_financebench_validation.py --dry-run
python scripts/run_financebench_validation.py --pilot
python scripts/run_financebench_validation.py --full
```

If source acquisition is owned by the script, require an explicit flag such as:

```text
--download
```

Do not download benchmark assets on import or during normal tests.

If generation is optional under the authoritative scope, use an explicit flag and never trigger paid calls during dry-run/pilot by default.

---

# 50. Dry Run

`--dry-run` should report without expensive work:

```text
benchmark source present/missing
source revision/hash
license
question count
document references
missing PDFs
config hash
artifact paths
embedding model cache availability
index reuse status
run-logging compatibility
protected TEST budget
```

No generation/API call in dry-run.

---

# 51. Resume / Artifact Reuse

If parsed/chunked/embedded/indexed FinanceBench artifacts already exist, reuse them only when provenance matches:

```text
benchmark source hash
parser config hash
chunk config hash
embedding identity
index identity
```

Reuse Task 2.10 compatibility utilities where possible.

Never reuse based solely on filename existence.

If incompatible:

```text
build a new versioned benchmark artifact
```

Do not overwrite the prior one.

---

# 52. Documentation

Create:

```text
project_plan/PHASE2_FINANCEBENCH_VALIDATION.md
```

Document:

- objective;
- why FinanceBench is independent validation;
- official source and license;
- exact frozen source revision/hashes;
- public 150-example scope vs. non-public/full benchmark distinction;
- dataset schema;
- document acquisition;
- no-leakage contract;
- PDF parsing/page semantics;
- table handling;
- evidence alignment;
- benchmark chunking;
- retrieval configuration;
- generation scope if applicable;
- deterministic scoring;
- why Task 2.13 LLM judge is not used here;
- run-logging integration;
- external-vs-internal split semantics;
- benchmark result;
- published-result comparability;
- category breakdowns;
- manual audit;
- known limitations;
- exact reproduction commands.

---

# 53. Repository Structure

Update:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

narrowly for actual Task 2.12 additions.

Potential files:

```text
src/eval/financebench.py
scripts/run_financebench_validation.py
configs/phase_2_12_financebench_validation.json
results/phase_2_12_financebench_validation.json
tests/test_financebench_validation.py
project_plan/PHASE2_FINANCEBENCH_VALIDATION.md
```

Only create files justified by the actual architecture.

---

# 54. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.12 Independent Benchmark Validation (FinanceBench)
```

Include:

```text
Objective
Initial State
Authoritative Contract
Official Source
License
Source Revision / Hashes
Dataset Validation
Document Integrity
No-Leakage Validation
PDF Parsing
Evidence Alignment
Benchmark Chunking
Embedding / Index Configuration
Pilot
Full Benchmark
Retrieval Metrics
Generation Scope
Deterministic Answer Metrics
Published Comparison
Run Logging
TEST Discipline
Manual Audit
Determinism
Independent Recalculation
Regression Gates
Tests
Frozen Data
Files Created/Modified
Git
Result
Phase Status
```

Append only.

Do not rewrite historical task entries.

---

# 55. Regression Gate — Task 2.11

Verify:

```text
run logging still validates all roadmap fields
existing schema-version records remain readable
secret rejection still works
tamper detection still works
create-once behavior still works
```

If Task 2.12 required a run-schema extension for external benchmarks:

- test backward compatibility explicitly;
- do not rewrite existing run records;
- document exactly why the version changed.

---

# 56. Regression Gate — Task 2.10

Verify:

```text
canonical hashing unchanged
Phase 1 chunk_config_hash unchanged
embedding identity unchanged
index identity unchanged
ArtifactCompatibility semantics unchanged
```

FinanceBench-specific artifact identities may be new, but must use the same canonical utilities.

---

# 57. Regression Gate — Task 2.9 / 2.8

Do not modify the internal SEC chunk schema or evidence truth.

Verify:

```text
Task 2.9 CHUNK_SCHEMA_VERSION unchanged unless an actual unrelated defect is discovered
Task 2.8 gold_evidence_count remains 0
Task 2.8 would-be-gold facts remain ineligible under frozen year window
```

FinanceBench evidence does not become internal SEC evidence gold.

---

# 58. Regression Gate — Tasks 2.1–2.7

No semantic changes to:

```text
truth contract
tag registry
internal evaluation dataset
DEV/TEST split
evaluation schema
metric definitions
MS MARCO harness result
```

Do not rerun the 8.8M MS MARCO build.

Run only lightweight existing regressions.

---

# 59. Regression Gate — Phase 1

Do not modify the historical baseline:

```text
1,500 development filings
162,357 chunks
BGE model/revision
Phase 1 embeddings
Phase 1 LanceDB index
BaselineRetriever
minimal generation layer
citation integrity smoke
Phase 1 baseline metrics
```

FinanceBench benchmark artifacts must remain isolated.

---

# 60. Frozen Internal Data Safety

Verify no writes to:

```text
data/xbrl.duckdb
data/edgar_corpus/
data/raw/xbrl/
data/raw/primary/
data/msmarco/
```

FinanceBench may add a new ignored benchmark-source directory if the storage contract permits it.

Do not mutate existing frozen sources.

---

# 61. Full Test Gate

After Task 2.12:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Record exact counts.

No existing test may be removed/xfailed simply to make the suite pass.

If the full suite contains API-marked tests and local credentials, retain the repository's existing marker discipline; Task 2.12 must not accidentally make portable tests spend API credits.

---

# 62. Git Safety

Before commit:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Confirm no large benchmark source/derived files are staged.

Specifically exclude where appropriate:

```text
FinanceBench PDFs
parsed benchmark documents
benchmark chunk parquet
benchmark embeddings
LanceDB benchmark index
full per-query traces
.env
credentials
model cache
```

Tracked:

```text
source code
small configs
tests
small result summary
run record(s)
documentation
Progress.md
```

Run secret/personal-path checks.

---

# 63. Commit

After all acceptance gates pass, create one coherent Task 2.12 commit.

Suggested message:

```text
Validate RAG pipeline on FinanceBench
```

or:

```text
Add independent FinanceBench validation
```

Choose the message that matches actual scope.

Do not tag Phase 2 complete.

Task 2.13 remains.

Do not push if no remote exists.

---

# 64. Stop Conditions

STOP rather than guessing if:

### A. Task 2.11 is not verifiably complete

Do not start 2.12.

### B. Local PROJECT_EXECUTION.md defines materially different Task 2.12 scope

Follow it and document the discrepancy.

### C. Official public FinanceBench population/source cannot be identified reproducibly

Do not use a random mirror.

### D. Dataset/license terms are incompatible with the planned use

Surface the issue.

### E. Official open-source sample unexpectedly differs from the expected population/schema

Investigate before running.

### F. A benchmark question's source document is unavailable

Record it explicitly; do not silently drop the question.

### G. Retrieval corpus would need to use gold evidence text

That is leakage. Stop and redesign.

### H. Evidence alignment requires arbitrary first-match selection

Keep ambiguous records non-gold.

### I. Task 2.11 cannot represent FinanceBench honestly

Do not call it internal `test` or fake `eval_set_version=phase2-v1`.
Implement the narrowest versioned external-benchmark extension or stop and surface the design conflict.

### J. Answer correctness requires an LLM judge

Defer semantic judging to Task 2.13.
Do not implement it here.

### K. Generation is required but credentials/model are unavailable

BLOCKED; do not silently substitute.

### L. Full FinanceBench access would require closed/private examples

Use only the authorized public 150-example set unless the user explicitly supplies licensed access.

### M. A major configuration change appears likely to improve FinanceBench score

Do not tune. Record it as a later Phase 3 hypothesis.

---

# 65. Acceptance Criteria

Task 2.12 is complete only when:

```text
PRECONDITION
[ ] Task 2.11 independently verified COMPLETE
[ ] exact local Task 2.12 contract confirmed

SOURCE
[ ] official FinanceBench source used
[ ] license verified/documented
[ ] exact source revision/file hashes frozen
[ ] open-source population independently counted
[ ] no unauthorized closed-source benchmark data obtained

DATASET
[ ] benchmark IDs unique
[ ] required question/answer fields valid
[ ] document-reference integrity audited
[ ] evidence-item distribution audited
[ ] missing documents/questions explicitly accounted for

LEAKAGE
[ ] source PDFs/documents are retrieval corpus
[ ] question text is not indexed as document content
[ ] gold answer is not indexed
[ ] gold evidence text is not used as retrieval corpus
[ ] no gold-document prefilter in headline retrieval

PARSING
[ ] PDFs parsed deterministically
[ ] page numbering semantics frozen
[ ] tables preserved where parser supports them
[ ] parse failures explicit

EVIDENCE
[ ] evidence-alignment method frozen
[ ] exact/normalized-exact/ambiguous/unmatched statuses explicit
[ ] ambiguous evidence not promoted to gold
[ ] evidence coverage reported before evidence metrics

BENCHMARK ARTIFACTS
[ ] benchmark namespace isolated from SEC corpus
[ ] deterministic benchmark chunk IDs
[ ] benchmark config hash computed with Task 2.10 utility
[ ] embeddings/index bind to exact benchmark source/config
[ ] no stale artifact reuse

RETRIEVAL
[ ] retrieval configuration frozen before full run
[ ] no tuning/sweeps
[ ] global retrieval is headline
[ ] oracle-document result, if present, clearly diagnostic only
[ ] deterministic retrieval metrics computed defensibly
[ ] metric denominator explicit

GENERATION
[ ] generation performed only if authoritative Task 2.12 requires it
[ ] existing frozen provider/model/settings used if required
[ ] API cost preflight performed if generation required
[ ] no model/prompt tuning against FinanceBench

SCORING
[ ] no LLM judge used
[ ] deterministic answer metrics only
[ ] no invented numeric tolerance
[ ] unavailable semantic answer accuracy labeled honestly
[ ] FinanceBench paper comparison marked comparable/not-comparable correctly

RUN LOGGING
[ ] each real headline benchmark run has Task 2.11 run_id
[ ] artifact identities recorded
[ ] benchmark identity recorded honestly
[ ] external benchmark is not mislabeled internal SEC TEST
[ ] run-record schema extended/versioned only if genuinely required
[ ] old run records remain valid/readable

TEST DISCIPLINE
[ ] internal SEC TEST payload not opened
[ ] official SEC TEST evaluations remain 0/3
[ ] FinanceBench run does not consume internal TEST budget

VALIDATION
[ ] deterministic pilot passes
[ ] manual pilot audit passes
[ ] full official public benchmark population accounted for
[ ] deterministic metric rerun passes
[ ] independent metric recomputation passes
[ ] per-question evidence artifact retained/hash-recorded

REGRESSION
[ ] Task 2.11 PASS
[ ] Task 2.10 PASS
[ ] Task 2.9 PASS
[ ] Task 2.8 PASS/no gold mutation
[ ] Task 2.1-2.7 PASS
[ ] Phase 1 PASS
[ ] frozen internal data unchanged

TESTS
[ ] new FinanceBench unit tests pass
[ ] portable suite passes
[ ] full suite passes
[ ] portable suite performs no benchmark download/API call

SAFETY
[ ] no credentials committed
[ ] no personal absolute paths committed
[ ] benchmark PDFs/large artifacts not stageable
[ ] Git dry-run safe

DOCUMENTATION
[ ] PHASE2_FINANCEBENCH_VALIDATION.md created
[ ] phase_2_12 result summary written
[ ] Task 2.11 run record(s) written only for real run(s)
[ ] repository structure updated narrowly
[ ] Progress.md appended
[ ] one coherent Task 2.12 commit created

BOUNDARY
[ ] Task 2.13 NOT started
[ ] no LLM-as-judge implementation added
```

---

# 66. Final Console Summary

Print:

```text
PHASE 2.12 — INDEPENDENT BENCHMARK VALIDATION (FINANCEBENCH)
============================================================

Source:
  benchmark:                         FinanceBench
  population:                        <official open-source count>
  source revision:                   <revision>
  source hash:                       <hash>
  license:                           <license>
  closed/private examples used:      NO

Documents:
  referenced documents:              <count>
  acquired:                          <count>
  missing/corrupt:                   <count>
  parse success:                     <count>/<count>

Evidence:
  evidence items:                    <count>
  exact/normalized-exact:            <count>
  ambiguous:                         <count>
  unmatched:                         <count>
  usable evidence questions:         <count>/<total>

Leakage checks:
  gold answers indexed:              NO
  gold evidence indexed:             NO
  gold doc prefilter headline:       NO

Benchmark config:
  config hash:                       <hash>
  parser:                            <config>
  chunking:                          <config>
  embedding model/revision:          <model/revision>
  embedding identity:                <hash>
  search type/metric:                <type/metric>
  top-k:                             <k>

Retrieval:
  evaluated questions:               <count>
  blocked/infrastructure:            <count>
  document recall@K:                 <value / N-A>
  document MRR:                      <value / N-A>
  evidence/chunk recall@K:           <value / N-A>
  evidence/chunk MRR:                <value / N-A>

Generation:
  required by Task 2.12:             YES / NO
  model:                             <model / N-A>
  LLM calls:                         <count>
  API spend:                         <cost / $0>
  deterministic exact diagnostic:    <value / N-A>
  numeric exact diagnostic:          <value / N-A>
  semantic answer accuracy:          DEFERRED TO TASK 2.13 / N-A

Published comparison:
  FinanceBench paper protocol:       <summary>
  apples-to-apples:                  YES / NO / PARTIAL
  interpretation:                    <text>

Run logging:
  run schema version:                <version>
  external benchmark represented:    PASS
  run_id(s):                         <ids>
  run record integrity:              PASS

TEST discipline:
  internal SEC TEST loaded:          NO
  official SEC TEST runs consumed:   0 / 3

Validation:
  manual audit:                      <n/n>
  deterministic metric rerun:        PASS
  independent recalculation:         PASS

Tests:
  new Task 2.12 tests:               <count>
  doctor:                            PASS
  portable:                          <result>
  full:                              <result>

Regression:
  Task 2.11:                         PASS
  Task 2.10:                         PASS
  Task 2.9:                          PASS
  Task 2.8:                          PASS
  Task 2.1-2.7:                      PASS
  Phase 1:                           PASS
  frozen internal data:              PASS

Git:
  commit:                            <sha/message>
  Phase 2 completion tag:            NO

FINAL RESULT:
PASS / PASS WITH NOTE / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
Task 2.13 — LLM-as-Judge Validation

DO NOT START TASK 2.13.
```

---

# Final Principle

Task 2.12 exists to test the project against a benchmark that **we did not design**.

The trustworthy chain is:

```text
official independent benchmark
        ↓
frozen questions + answers + evidence + source documents
        ↓
leakage-free document parsing/chunking
        ↓
frozen baseline retrieval/generation configuration
        ↓
deterministic metrics where defensible
        ↓
Task 2.11 immutable run provenance
        ↓
independent metric recomputation
        ↓
honest comparison with the benchmark's actual evaluation protocol
```

Do not optimize FinanceBench.

Do not index gold evidence.

Do not pre-filter to the gold document for the headline result.

Do not pretend exact match is the paper's human-reviewed accuracy.

Do not consume the protected internal SEC TEST budget.

Do not use the closed/private benchmark without authorized access.

Do not implement the LLM judge early.

A lower but reproducible, leakage-free, honestly scored result is more valuable than a higher result obtained by changing the benchmark or evaluation semantics.
