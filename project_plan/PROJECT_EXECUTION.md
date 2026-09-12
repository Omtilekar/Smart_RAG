# SEC RAG — Project Execution Plan

**Status:** Data preparation complete; engineering execution ready  
**Project style:** Build a working vertical slice first, then make measurement trustworthy, then improve quality, then productionize.  
**Authoritative source documents:** `PROJECT_SPEC.md`, `DATA_READINESS_REPORT.md`

---

## 0. Guiding Principles

1. **Working system before sophisticated system.**
   - The first engineering milestone is a deliberately simple end-to-end RAG pipeline.

2. **Measurement before optimization.**
   - Phase 1 produces a crude number.
   - Phase 2 establishes whether that number and the evaluation harness can be trusted.
   - Phase 3 is where optimization begins.

3. **Every component must earn its place.**
   - A component stays only if it measurably improves the metric for the problem it is designed to solve.
   - If it does not help, revert it.

4. **Raw data is frozen.**
   - Phase 1 data acquisition, validation, and methodological review are complete.
   - Raw datasets are read-only from this point forward.
   - All transformed artifacts are versioned and reproducible.

5. **Develop small, scale once.**
   - Experiment on a 1,500-filing development corpus.
   - Do not embed/index the full 91,086-filing corpus until architecture choices are stable.

6. **Test and development sets remain separate.**
   - All routine experiments use `dev`.
   - The locked `test` set is used only at planned milestones.

7. **Production complexity comes late.**
   - Guardrails, deployment, graph retrieval, advanced table RAG, ColBERT, and other expensive capabilities do not block the core system.

---

# Data Preparation — COMPLETE

This work was previously referred to as Phase 1 in the data-acquisition documents. It is now treated as a completed prerequisite to the engineering roadmap below.

### Completed

- [x] Download MS MARCO benchmark data.
- [x] Download EDGAR-CORPUS.
- [x] Download SEC XBRL financial statement datasets.
- [x] Download 990 complete primary SEC 10-K HTML filings.
- [x] Validate file integrity and schema consistency.
- [x] Reproduce critical dataset statistics independently.
- [x] Validate EDGAR-CORPUS ↔ XBRL overlap.
- [x] Correct the loose XBRL value-revision methodology.
- [x] Confirm table and inline-XBRL survival in primary filings.
- [x] Freeze authoritative Phase 1 metrics.
- [x] Declare raw datasets immutable for downstream development.

### Frozen facts relevant to execution

- EDGAR-CORPUS: **91,086 filings**
- EDGAR-CORPUS CIKs: **25,937**
- XBRL facts: **90,685,753**
- XBRL submissions loaded: **218,166**
- XBRL CIKs: **10,757**
- EDGAR ↔ XBRL 10-K coverage, 2016–2020: **5,646 / 6,950 = 81.24%**
- Primary filings: **990**
- Primary sample with tables: **30/30**
- Primary sample with inline XBRL: **30/30**
- MS MARCO passages: **8,841,823**
- MS MARCO dev-small queries: **6,980**

### Exit gate

**PASSED — DATA FROZEN, ENGINEERING READY**

---

# Phase 0 — Build the System Foundation

## Objective

Create a reproducible development environment and repository structure so later RAG failures are not confused with environment, CUDA, path, configuration, or dependency problems.

This phase builds **infrastructure for development**, not RAG functionality.

## Subtasks

### 0.1 Python environment

- [ ] Select and document the project Python version.
- [ ] Create the project virtual environment.
- [ ] Verify activation on the primary development machine.
- [ ] Record the setup command in the README/developer setup guide.

### 0.2 CUDA / PyTorch / GPU validation

- [ ] Install a PyTorch build compatible with the RTX 50-series GPU.
- [ ] Confirm CUDA is visible from PyTorch.
- [ ] Confirm the expected GPU name is detected.
- [ ] Record CUDA runtime and PyTorch versions.
- [ ] Run a small tensor operation on GPU.
- [ ] Run a small embedding inference on GPU.
- [ ] Record VRAM usage for the smoke test.

### 0.3 Repository structure

Create/finalize the engineering layout:

```text
src/
  ingest/
  normalize/
  chunk/
  embeddings/
  index/
  retrieval/
  generation/
  eval/
  router/
  rerank/
  crag/
  guards/
  api/
  cli/
  storage.py
  config.py

configs/
tests/
scripts/
prompts/
data/
  raw/                  # frozen
  benchmark/
  derived/
  eval/
  okf/
  chunks/
  index/

artifacts/
logs/
infra/
```

- [ ] Ensure raw data directories are clearly separated from derived artifacts.
- [ ] Ensure generated artifacts are ignored appropriately by Git.
- [ ] Preserve reports and lightweight experiment metadata where useful.

### 0.4 Dependency management

- [ ] Create the initial `requirements.txt` or equivalent dependency definition.
- [ ] Separate optional/dev dependencies if helpful.
- [ ] Pin critical packages where reproducibility matters.
- [ ] Include at minimum the libraries needed for:
  - DuckDB
  - PyArrow/Parquet
  - sentence-transformers
  - PyTorch
  - LanceDB
  - tokenization
  - FastAPI
  - testing
  - environment configuration

### 0.5 Configuration system

- [ ] Create centralized configuration loading.
- [ ] Support `.env` for secrets.
- [ ] Add `.env.example` with variable names only.
- [ ] Never commit API keys.
- [ ] Define `STORAGE_ROOT`.
- [ ] Define model configuration through config rather than hardcoded values.
- [ ] Define environment-aware paths for local development and future object storage.

### 0.6 Logging

- [ ] Create a minimal structured logging utility.
- [ ] Log timestamps, stage names, and failures.
- [ ] Establish `logs/` conventions.
- [ ] Avoid ad hoc `print()` output for long-running pipelines where structured logs are more useful.

### 0.7 Storage abstraction skeleton

- [ ] Create `src/storage.py`.
- [ ] Centralize all important dataset/artifact paths.
- [ ] Confirm code does not spread hardcoded absolute paths throughout the repository.
- [ ] Support local filesystem first.
- [ ] Keep the abstraction compatible with future S3-backed artifacts.

### 0.8 Basic automated tests

- [ ] Test configuration loading.
- [ ] Test path resolution.
- [ ] Test DuckDB connectivity.
- [ ] Test LanceDB initialization.
- [ ] Test GPU availability when GPU mode is requested.
- [ ] Test one tiny embedding request.
- [ ] Add a smoke-test command.

### 0.9 Developer commands

Define simple commands/scripts for:

```text
setup / environment check
tests
data path check
GPU check
```

The exact interface can be CLI, Makefile, or scripts, but it must be documented.

### 0.10 Serving feasibility spike

**Moved here from Phase 3.** Every latency figure in the design is currently
an estimate. This spike either validates the serving assumptions or changes
them — and it must run *before* quantization strategy, reranker size, and
candidate-pool size are chosen, because all three depend on the answer.

Build a throwaway. Do not integrate it with the main codebase.

- [ ] Embed ~100,000 chunks (any subset — quality is irrelevant here).
- [ ] Build a LanceDB index and place it in object storage.
- [ ] Deploy a minimal retrieval function to the candidate serving target.
- [ ] Measure cold-start latency.
- [ ] Measure warm p50 and p95.
- [ ] Break latency down by stage: index load, query embedding, vector search,
      FTS, reranking.
- [ ] Measure peak memory.
- [ ] Repeat with and without binary quantization.
- [ ] Repeat across plausible memory allocations.

Decision thresholds:

| Warm p95 | Action |
|---|---|
| < 500 ms | Proceed with the serverless design |
| 500 ms – 2 s | Proceed, but constrain reranker size and candidate pool in Phase 3 |
| > 2 s | Change serving target to warm compute; revisit Phase 3 assumptions |

Also record whether cold start alone exceeds 10 s. If it does, the serverless
target is unsuitable regardless of warm performance.

- [ ] Record results in `Progress.md`.
- [ ] Record the serving-target decision explicitly, with the measurement
      behind it.

## Deliverables

- Working virtual environment
- Dependency file(s)
- Final repository skeleton
- `.env.example`
- `.gitignore`
- `src/config.py`
- `src/storage.py`
- environment/GPU smoke tests
- documented setup instructions
- serving feasibility measurements and serving-target decision

## Exit criteria

Phase 0 is complete only when:

- [ ] A fresh terminal can activate the project environment.
- [ ] Python imports all core dependencies.
- [ ] PyTorch sees the GPU and can perform GPU computation.
- [ ] A sentence-transformer can embed sample text.
- [ ] DuckDB opens the local XBRL database.
- [ ] LanceDB can create/read a tiny test table.
- [ ] Configuration and storage roots load without hardcoded local-machine assumptions.
- [ ] Core smoke tests pass.
- [ ] Serving latency has been measured, not estimated.
- [ ] The serving target is chosen and the decision is recorded.

## If short on time

Nothing here is optional. Phase 0 is the cheapest phase and skipping it means
later failures get misattributed to RAG design rather than environment.

**Phase 0 question:** *Can we reliably build and run the project?*

---

# Phase 1 — Make It Work End to End

## Objective

Build the crudest possible complete RAG system.

A question must go in and a cited answer must come out.

Quality is intentionally secondary. The purpose is to expose integration failures early.

## Baseline constraints

The Phase 1 system deliberately uses:

- **1,500 EDGAR-CORPUS filings**
- **2016–2020 aligned region where possible**
- simple Markdown normalization
- fixed **512-token chunks**
- no section-aware splitting
- no table pipeline
- `bge-small-en-v1.5`
- vector retrieval only
- top-5 context for generation
- simple API-model prompt
- no BM25
- no reranker
- no CRAG
- no router
- no graph
- no production guardrail stack

## Subtasks

### 1.1 Select the development corpus

- [ ] Build the eligible 2016–2020 aligned `(CIK, year)` population.
- [ ] Select 1,500 filings reproducibly.
- [ ] Use a deterministic seed or deterministic sampling rule.
- [ ] Save the selected corpus manifest.
- [ ] Record company/year distribution.
- [ ] Ensure every selected filing can be traced back to the source data.

### 1.2 Minimal document normalization

- [ ] Convert selected EDGAR-CORPUS records into one normalized Markdown representation per filing.
- [ ] Add YAML frontmatter containing available metadata.
- [ ] Preserve source identity.
- [ ] Normalize CIK to `int64`.
- [ ] Normalize year to `int32`.
- [ ] Do not attempt sophisticated cleaning.

Minimum frontmatter:

```yaml
cik:
company:
form_type: 10-K
fiscal_year:
source: edgar_corpus
source_filename:
```

### 1.3 Minimal fixed-window chunker

- [ ] Tokenize normalized text.
- [ ] Split into fixed 512-token chunks.
- [ ] Use zero or a single simple fixed overlap policy.
- [ ] Ignore section boundaries.
- [ ] Ignore tables.
- [ ] Preserve document metadata on every chunk.
- [ ] Assign deterministic baseline chunk IDs.
- [ ] Save chunks to Parquet.

### 1.4 Baseline embedding pipeline

- [ ] Load `bge-small-en-v1.5`.
- [ ] Apply the model's required query/passage conventions correctly.
- [ ] Batch embeddings on GPU.
- [ ] Record embedding throughput.
- [ ] Store the embeddings with chunk IDs and metadata.

### 1.5 Vector-only index

- [ ] Build one LanceDB vector index/table.
- [ ] No BM25.
- [ ] No hybrid search.
- [ ] No reranking.
- [ ] Verify retrieved IDs map back to exact source chunks.
- [ ] Verify metadata survives indexing.

### 1.6 Baseline retriever

Implement:

```text
question
   ↓
query embedding
   ↓
vector search
   ↓
top-k chunks
```

- [ ] Support configurable `k`.
- [ ] Return scores, chunk IDs, document IDs, and source metadata.
- [ ] Make retrieval callable independently of generation.

### 1.7 Minimal generation layer

Use a simple provider interface:

```python
generate(question, context) -> answer
```

- [ ] Send the question plus top-5 chunks to an API model.
- [ ] Use a minimal grounded prompt.
- [ ] Ask the model to cite supplied chunk IDs.
- [ ] Return answer + citations.
- [ ] Do not build sophisticated guardrails yet.

### 1.8 Citation integrity smoke check

- [ ] Confirm every cited chunk ID exists.
- [ ] Confirm citations refer only to chunks supplied to the generator.
- [ ] Fail clearly when the generator emits an unknown citation.
- [ ] Store source metadata needed to inspect citations manually.

### 1.9 Build a 200-question smoke evaluation

This is **not** the final benchmark.

- [ ] Generate approximately 200 questions from the aligned development subset.
- [ ] Prefer questions with a defensible document-level target.
- [ ] Keep provenance for each question.
- [ ] Label the initial retrieval metric explicitly as `doc_recall@10` unless true chunk evidence is available.
- [ ] Do not present Phase 1 numbers as final research results.

**These 200 questions are discarded in Phase 2, not carried forward.** They
are generated before the XBRL truth contract exists, so some will be
semantically wrong — segment-level values, incorrect `qtrs`, non-consolidated
facts. They are adequate for detecting integration failures and inadequate as
ground truth. Regenerate the full set under the truth contract in 2.3.

### 1.10 Baseline metric runner

- [ ] Implement `doc_recall@10`.
- [ ] Hand-check a few calculations.
- [ ] Print question count, hit count, and recall.
- [ ] Save run metadata and configuration.

### 1.11 End-to-end command

Provide one documented command that can:

1. accept a question,
2. retrieve chunks,
3. generate an answer,
4. print citations.

Also provide one command that runs the 200-question smoke evaluation.

## Deliverables

- 1,500-filing development manifest
- baseline normalized Markdown
- baseline chunk Parquet
- baseline LanceDB vector index
- vector retriever
- simple generation provider
- cited answer output
- 200-question smoke set
- baseline `doc_recall@10`
- one-command demo
- one-command smoke evaluation

## Exit criteria

- [ ] One command accepts a question and returns an answer.
- [ ] The answer contains valid source citations.
- [ ] Every citation resolves back to a stored source chunk.
- [ ] A 200-question evaluation runs end to end.
- [ ] `doc_recall@10` is printed and saved.
- [ ] Integration bugs found during the vertical slice are documented.
- [ ] No advanced retrieval component has been added prematurely.

**Phase 1 question:** *Does the whole system work, even badly?*

---

# Phase 2 — Make the Numbers Trustworthy

## Objective

Phase 1 produced a number. Phase 2 establishes whether the evaluation system and ground truth are correct enough to trust.

**This phase adds no production retrieval features.**

## Subtasks

### 2.1 Implement the XBRL truth contract

Create:

```text
src/eval/truth_contract.py
```

- [ ] Restrict to the supported evaluation window.
- [ ] Restrict to intended filing types.
- [ ] Require consolidated facts:
  - `coreg` blank/null
  - `segments` blank/null
- [ ] Enforce correct unit by tag.
- [ ] Enforce instant/duration semantics.
- [ ] Enforce explicit `qtrs` expectations.
- [ ] Validate plausible `ddate`.
- [ ] Use standard, non-abstract tag metadata.
- [ ] Anchor facts to the intended filing/accession when available.
- [ ] Reject ambiguous facts rather than silently choosing one.
- [ ] Keep materiality/sampling policy separate from truth validity.

### 2.2 Freeze supported tag registry

Validate and freeze the initial ~15 financial concepts.

For each tag record:

- [ ] tag name
- [ ] label
- [ ] expected unit
- [ ] expected `iord`
- [ ] expected `qtrs`
- [ ] availability
- [ ] company coverage
- [ ] year coverage
- [ ] allowed question templates

Store this in a versioned config such as:

```text
configs/eval_tags.yaml
```

### 2.3 Build the full evaluation dataset

Target approximately **3,000 questions** across categories such as:

- [ ] numeric facts
- [ ] derived/comparative numeric questions
- [ ] narrative questions
- [ ] unanswerable questions
- [ ] adversarial/guardrail questions

Every item must retain enough provenance to reproduce its expected answer.

### 2.4 Company-disjoint DEV / TEST split

- [ ] Split by CIK, not by question.
- [ ] Target approximately 70% DEV / 30% TEST.
- [ ] Stratify where practical by fiscal year and SIC.
- [ ] Assert no CIK overlap.
- [ ] Keep CI/golden examples inside DEV.
- [ ] Freeze TEST.
- [ ] Version the eval set.

### 2.5 Evaluation schema

Freeze fields needed for reproducible experiments, including:

```text
question_id
question
question_type
expected_answer
unit
cik
year
accession/adsh where available
tag
source
evidence label where available
split
eval_set_version
```

### 2.6 Metric unit tests

Implement deterministic tests for:

- [ ] Recall@K
- [ ] document Recall@K
- [ ] chunk Recall@K
- [ ] MRR
- [ ] nDCG@K
- [ ] exact match
- [ ] refusal metrics when applicable

Use tiny hand-constructed examples where expected answers can be calculated manually.

### 2.7 MS MARCO harness validation

- [ ] Load the frozen MS MARCO benchmark artifacts.
- [ ] Run the retrieval evaluation code on dev-small.
- [ ] Compare with reasonable published/known behavior for the chosen baseline.
- [ ] Investigate large deviations before trusting SEC metrics.
- [ ] Record configuration and results.

### 2.8 Primary-document parsing for evidence labels

Purpose: **evaluation**, not feature expansion.

- [ ] Parse the 990 primary 10-K HTML files.
- [ ] Preserve table and inline-XBRL structure.
- [ ] Extract inline XBRL facts.
- [ ] Align inline-XBRL values to source positions.
- [ ] Map aligned positions to chunks.
- [ ] Produce a chunk-level gold evidence subset.
- [ ] Validate alignment on manually inspected examples.

### 2.9 Freeze chunk metadata schema

Freeze the canonical fields before large-scale indexing.

At minimum:

```text
chunk_uid
chunk_local_id
accession/document identity
cik
company
form_type
fiscal_year
period_end
filed_date
sic
section_id
section_title
ordinal
char_start
char_end
content_type
table_id
source
text
token_count
chunk_config_hash
```

### 2.10 Config hashing and artifact versioning

- [ ] Hash chunking configuration.
- [ ] Version chunk directories.
- [ ] Version index directories.
- [ ] Store embedding model identity.
- [ ] Store eval-set version.
- [ ] Prevent stale-index / new-config mismatches.
- [ ] Add CI assertions for artifact compatibility.

### 2.11 Evaluation run logging

Every experiment should record:

```text
run_id
git_sha
chunk_config_hash
embedding model
retrieval config
reranker config
generation model
split
eval_set_version
timestamp
metrics
```

### 2.12 Independent benchmark validation (FinanceBench)

The ~3,000-question set is auto-generated, so a systematic flaw in generation
inflates every score invisibly — the same logic produces both the questions
and the expected answers. An independent, human-annotated set is the only
external check.

- [ ] Load FinanceBench (150 expert-annotated questions over real 10-K filings).
- [ ] Note the licence: CC-BY-NC, evaluation use only. Do not redistribute.
- [ ] Add the referenced filings to the development corpus where they are not
      already present.
- [ ] Map its `evidence` field (`doc_name`, `evidence_page_num`,
      `evidence_text`) onto chunk-level labels where possible.
- [ ] Run the same retrieval harness against it.
- [ ] Report FinanceBench metrics alongside the internal set.
- [ ] **Investigate any large gap between the two before proceeding.** A wide
      divergence indicates generator bias in the internal set, not merely
      domain difficulty.

### 2.13 LLM-as-judge validation

Judge-scored metrics (faithfulness, narrative answer quality) carry an unknown
error bar until the judge itself is measured.

- [ ] Select a judge model from a **different family** than the generation
      model, to avoid self-preference bias.
- [ ] Hand-label 100 answers for faithfulness (supported / unsupported).
- [ ] Run the judge over the same 100.
- [ ] Report agreement rate, and disagreement direction (over- or
      under-crediting).
- [ ] Record the agreement figure so every judge-based metric can cite it.
- [ ] Re-run judge validation if the judge model or prompt changes.

Known judge failure modes to check for in the disagreements: preference for
verbose answers, run-to-run inconsistency, and agreement with whatever
content is presented.

> **Task 2.13 methodology amendment (2026-09-08, user-approved):** the
> checklist above — specifically "hand-label 100 answers" and "report
> agreement rate... against blinded human labels" — was never completed as
> written. Manual 100-case human calibration is deferred/not performed. By
> explicit user decision, the completed cross-model agreement study
> (`qwen3.5:9b` vs `gpt-oss:20b`, 88.0% exact agreement, Cohen's kappa 0.737 —
> see `results/phase_2_13_cross_model_agreement.json` and
> `project_plan/PHASE2_LLM_JUDGE_VALIDATION.md`) is accepted as the Task 2.13
> substitute. This substitution does **not** make the judge human-validated.
> `faithfulness.implemented` in the Task 2.5/2.6 metric registry must not be
> flipped solely because of cross-model agreement, and no
> accuracy/precision/recall/F1 against human truth may be claimed from this
> study. The original checklist above is left unchecked and unmodified as
> the historical record of what was actually planned and not literally
> satisfied.

## Deliverables

- XBRL truth contract
- frozen tag registry
- ~3,000-question versioned benchmark
- company-disjoint DEV/TEST split
- metric unit tests
- MS MARCO validation results
- FinanceBench validation results
- judge agreement rate against human labels
- parsed primary-doc evidence subset
- chunk-level relevance labels
- canonical chunk schema
- artifact/config hashing
- evaluation run log

## Exit criteria

- [ ] Truth-contract tests pass.
- [ ] No DEV/TEST company overlap exists.
- [ ] MS MARCO evaluation behaves plausibly relative to known baselines.
- [ ] Retrieval metrics pass hand-constructed unit tests.
- [ ] Chunk evidence labels are validated on primary filings.
- [ ] Chunk schema is frozen.
- [ ] Config/artifact hashes are enforced.
- [ ] The TEST split is frozen and protected from routine experimentation.
- [ ] FinanceBench has been run and any gap versus the internal set explained.
- [ ] Judge agreement against human labels is measured and recorded.
      **Amended 2026-09-08** — unmet as literally written (no human labels
      were collected); satisfied instead via the user-approved cross-model
      agreement substitute above. Not human validation.

## If short on time

This phase is the project's credibility and should not be cut. If something
must give:

- **Keep**: truth contract, DEV/TEST split, metric unit tests, MS MARCO
  validation, schema freeze, config hashing.
- **Reduce**: the evidence-label subset (2.8) can start at ~100 validated
  documents instead of all 990 — enough to report `chunk_recall@k` honestly.
- **Defer**: FinanceBench (2.12) can move to Phase 4 if necessary, but must
  happen before the README is written.

**Phase 2 question:** *Can we trust the numbers we are about to optimize?*

---

# Phase 3 — Make It Good

## Objective

Improve the working system one component at a time.

Every addition must solve a defined problem and demonstrate measurable value on **DEV**.

## Rule

> A component stays only if it improves the metric appropriate to the problem it is designed to solve.

No component is retained merely because it was expensive to build.

## Subtasks

### 3.1 Capture the trusted baseline

- [ ] Run Phase 1 architecture through the now-trusted Phase 2 evaluation harness.
- [ ] Store baseline DEV results.
- [ ] Treat this as row 0 of the ablation table.

### 3.2 Chunking ablation

Benchmark a small, controlled set such as:

- [ ] 256 tokens
- [ ] 512 tokens
- [ ] 1024 tokens
- [ ] selected overlap values
- [ ] fixed vs section-aware splitting

Measure retrieval quality and index implications.

Select the winner before full-corpus processing.

### 3.3 Embedding model benchmark

Benchmark candidates on a representative subset rather than the full corpus.

Candidates may include:

- [ ] `bge-small-en-v1.5`
- [ ] `bge-base-en-v1.5`
- [ ] `nomic-embed-text-v1.5`
- [ ] `Qwen3-Embedding-0.6B`
- [ ] optional commercial reference model

Measure:

- Recall@10
- Recall@50
- MRR
- nDCG@10
- query latency
- embedding throughput
- memory
- index size

Choose one production embedding model.

### 3.4 Add BM25 / FTS

- [ ] Add LanceDB-native FTS/BM25 as the initial sparse baseline.
- [ ] Verify metadata filtering behavior.
- [ ] Verify raw scores/ranks are available for fusion.
- [ ] Compare dense vs sparse retrieval independently.

### 3.5 Add RRF hybrid fusion

Implement:

```text
dense candidates
      +
sparse candidates
      ↓
     RRF
```

Measure whether hybrid retrieval improves the intended retrieval metrics.

Primary metrics:

- Recall@50
- MRR

### 3.6 Add cross-encoder reranking

- [ ] Benchmark a small serving candidate.
- [ ] Optionally compare to a larger quality ceiling.
- [ ] Rerank a fixed candidate pool.
- [ ] Keep candidate-set recall separate from reranked top-k quality.

Primary metrics:

- MRR
- nDCG@10
- Precision@5
- Recall@5

### 3.7 Add CRAG-style confidence grading

Reuse existing retrieval/reranker signals rather than adding an LLM grader.

Candidate features:

- [ ] top-1 reranker score
- [ ] top-3 mean score
- [ ] top-1 to top-5 score gap
- [ ] candidate count after filtering

- [ ] Calibrate thresholds on DEV only.
- [ ] Prefer per-intent thresholds if score distributions differ.

Measure:

- true refusal rate
- false refusal rate
- missed failure rate

### 3.8 Add rules-first router

Initial intents:

```text
xbrl_fact
numeric_derived
numeric_narrative
comparative
cross_entity
narrative
section_summary
unanswerable
out_of_scope
advice
```

- [ ] Company-name → CIK resolution.
- [ ] Fiscal-year extraction.
- [ ] Form-type extraction.
- [ ] Known-XBRL-concept lookup.
- [ ] Rule-based path selection.
- [ ] Build a labelled router evaluation set.
- [ ] Report confusion matrix and per-class metrics.
- [ ] Benchmark an LLM router only if the rule baseline leaves meaningful gaps.

### 3.9 Metadata pre-filtering

Apply scope **before** retrieval where possible:

- [ ] CIK
- [ ] year
- [ ] form
- [ ] section

Use exact/brute-force search for very narrow filtered candidate pools where it is more accurate and cheaper than ANN.

### 3.10 Add structured XBRL SQL path

For supported numeric questions:

```text
question
  ↓
router
  ↓
XBRL fact lookup
```

- [ ] Use the truth-contract semantics in the production selector.
- [ ] Return value + unit + filing provenance.
- [ ] Do not route unsupported numeric narrative questions to SQL.

### 3.11 Add deterministic derived calculations

Examples:

- growth
- percentage of revenue
- difference between years
- cross-company comparisons

Principle:

> Retrieve facts with models/rules; calculate facts with deterministic code.

### 3.12 Add simple tree/section navigation

For queries such as:

```text
Summarize Item 7 of this filing.
```

- [ ] Identify the filing.
- [ ] Navigate directly to the requested normalized section.
- [ ] Avoid unnecessary global retrieval.

### 3.13 Maintain the ablation table

Example structure:

| Configuration | Recall@50 | MRR | nDCG@10 | Precision@5 | Refusal metric | Latency |
|---|---:|---:|---:|---:|---:|---:|
| Vector baseline | | | | | | |
| + better chunks/embed | | | | | | |
| + BM25/RRF | | | | | | |
| + reranker | | | | | | |
| + CRAG | | | | | | |
| + router/filtering | | | | | | |

Every row must be reproducible from config + git SHA.

### 3.14 Re-check against the Phase 0 serving budget

The feasibility spike now runs in Phase 0 (0.10), because reranker size,
quantization strategy, and candidate-pool size all depend on its results.
This step confirms the components chosen during Phase 3 still fit that budget.

- [ ] Re-measure end-to-end latency with the actual selected reranker and
      candidate pool, not the spike's placeholders.
- [ ] Confirm the chosen embedding model's query-time latency on CPU matches
      the spike assumption.
- [ ] Confirm index size after the selected quantization fits the serving
      memory ceiling.
- [ ] If any component breaks the budget, revisit it here rather than in
      Phase 4 — this is the last cheap moment to change an architectural
      decision.

## Deliverables

- trusted baseline
- chunking decision
- embedding-model decision
- hybrid retriever
- reranker
- CRAG confidence layer
- rules-first router
- metadata filters
- SQL numeric path
- tree/section path
- ablation table
- confirmation that selected components fit the Phase 0 serving budget

## Exit criteria

- [ ] Every retained component has a measured justification on DEV.
- [ ] Final chunking strategy is selected.
- [ ] Final embedding model is selected.
- [ ] Hybrid retrieval is benchmarked.
- [ ] Reranking is benchmarked.
- [ ] CRAG thresholds are calibrated on DEV.
- [ ] Router accuracy is measured.
- [ ] SQL and narrative paths are separated correctly.
- [ ] Selected components fit the serving budget measured in Phase 0.
- [ ] Architecture is stable enough to scale once.

## If short on time

Subtasks are ordered by value per hour. Stop wherever time runs out and
document the rest as designed-but-unbuilt — an ablation table with four
honest rows beats seven components with no measurements.

Suggested stopping points, best first:

1. **After 3.6 (reranking).** Baseline → chunk/embed choice → BM25/RRF →
   reranker is a complete, defensible ablation table and the largest quality
   gains are already captured.
2. **After 3.8 (router).** Adds the SQL path, which is the project's most
   distinctive feature.
3. **After 3.12.** Full scope as planned.

Do not skip 3.1 (trusted baseline) or 3.13 (ablation table) under any
circumstance — without them the rest of the phase produces no evidence.

**Phase 3 question:** *Which components actually make the system better?*

---

# Phase 4 — Make It Real

## Objective

Scale the proven architecture, add the production safety/serving layer, deploy it, and produce the main project results.

Someone other than the developer should be able to use the system without local intervention.

## Subtasks

### 4.1 Full-corpus normalization

- [ ] Apply the selected normalization pipeline to the complete EDGAR-CORPUS.
- [ ] Preserve deterministic IDs.
- [ ] Preserve frozen metadata schema.
- [ ] Record config hash and build manifest.

### 4.2 Full-corpus chunking

- [ ] Apply the Phase 3 winning chunk configuration.
- [ ] Write versioned Parquet artifacts.
- [ ] Validate expected counts.
- [ ] Validate no source documents disappeared.
- [ ] Sample-check chunk quality.

### 4.3 Full-corpus embedding

- [ ] Embed all production chunks using the selected model.
- [ ] Use GPU batching.
- [ ] Support resume/checkpoint behavior.
- [ ] Log throughput and failures.
- [ ] Do not silently skip failed batches.

### 4.4 Production index build

- [ ] Build full vector index.
- [ ] Build FTS/BM25 index.
- [ ] Build required scalar metadata indexes.
- [ ] Apply selected quantization strategy only if Phase 3 validated it.
- [ ] Verify index/chunk config compatibility.

### 4.5 XBRL serving representation

- [ ] Keep `xbrl.duckdb` for offline analysis.
- [ ] Export serving-appropriate XBRL artifacts, likely partitioned Parquet.
- [ ] Partition based on measured query patterns such as CIK/year.
- [ ] Validate partition pruning.
- [ ] Benchmark real SQL-path latency.

### 4.6 Generation production interface

- [ ] Finalize the provider abstraction.
- [ ] Select the live generation model.
- [ ] Preserve local/offline implementation where useful for experiments.
- [ ] Track token usage and request latency.

### 4.7 Input guardrails

Add:

- [ ] request length limits
- [ ] scope enforcement
- [ ] advice detection/refusal
- [ ] PII checks appropriate to the SEC use case
- [ ] injection-pattern handling
- [ ] rate limiting strategy

### 4.8 Context guardrails

- [ ] Treat retrieved content as untrusted data.
- [ ] Clearly delimit retrieved evidence.
- [ ] Preserve raw evidence for provenance.
- [ ] Plant adversarial/instruction-shaped retrieval examples.
- [ ] Test that retrieved text cannot override system instructions.

### 4.9 Output guardrails

- [ ] Verify cited chunk IDs exist.
- [ ] Verify citations refer to provided evidence.
- [ ] Add groundedness checks.
- [ ] Validate numeric provenance for structured answers.
- [ ] Refuse unsupported financial advice.
- [ ] Avoid unsupported claims.

### 4.10 FastAPI service

Implement a thin API layer over stable Python modules.

Initial endpoints may include:

```text
POST /query
GET  /health
GET  /status
```

- [ ] Keep retrieval/generation logic outside FastAPI.
- [ ] Define request/response models.
- [ ] Return citations and useful metadata.

### 4.11 Deployment

Using the Phase 3 serving spike:

- [ ] deploy to the selected compute target,
- [ ] configure object storage where required,
- [ ] configure secrets safely,
- [ ] configure logging,
- [ ] test cold/warm behavior,
- [ ] test system availability independently of the development machine.

### 4.12 Observability

Log per query:

```text
query_id
router decision
resolved filters
retrieval path(s)
candidate count
retrieved chunk IDs
retrieval scores
reranker scores
CRAG state
generation model
token usage
latency by stage
citations
errors
```

### 4.13 Production performance evaluation

Measure:

- [ ] p50 latency
- [ ] p95 latency
- [ ] cold-start latency
- [ ] memory
- [ ] approximate cost/query
- [ ] index build time
- [ ] query-stage latency breakdown

### 4.14 Run locked TEST milestone

This should be a planned test-set run, not routine development evaluation.

- [ ] Run the frozen test set.
- [ ] Save config + git SHA.
- [ ] Do not tune against individual test failures afterward without treating the run appropriately.
- [ ] Produce final headline metrics.

### 4.15 Failure analysis

Create/update:

```text
FAILURES.md
```

Include at least 10 real system failures:

```text
query
expected behavior
actual behavior
failing stage
root cause
possible fix
status
```

### 4.16 README / final documentation

Document:

- [ ] problem
- [ ] dataset
- [ ] frozen data statistics
- [ ] architecture
- [ ] evaluation methodology
- [ ] DEV vs TEST discipline
- [ ] ablation results
- [ ] final test metrics
- [ ] latency/cost
- [ ] failure cases
- [ ] limitations
- [ ] reproducibility
- [ ] deployment usage

## Deliverables

- full normalized corpus
- full chunk corpus
- production vector + FTS indexes
- structured XBRL serving path
- generation + guardrails
- FastAPI service
- deployed endpoint/service
- observability logs
- production latency/cost results
- locked-test results
- `FAILURES.md`
- final README

## Exit criteria

- [ ] Full corpus is indexed with the chosen architecture.
- [ ] API works independently of the developer's local machine.
- [ ] Citations are returned and validated.
- [ ] Core guardrails pass their labelled tests.
- [ ] p50/p95 latency is measured.
- [ ] cost/query is estimated/measured.
- [ ] locked TEST milestone is complete.
- [ ] README reports reproducible results.
- [ ] another user can use the deployed system without developer intervention.

## If short on time

The full corpus is the most expensive and least essential item here. A
measured system on a smaller corpus with a documented scaling analysis is a
stronger result than an unmeasured system on all 91,086 filings.

- **Keep, always**: locked TEST run (4.14), `FAILURES.md` (4.15), README
  (4.16), citation validation, scope and advice guardrails.
- **Reduce**: scale to a defensible subset (for example the full 2016–2020
  aligned region) rather than the complete corpus, and state the measured
  chunk count with an extrapolation to full scale.
- **Defer**: deployment (4.11). A locally reproducible system with a
  documented deployment design is acceptable; an undocumented half-deployed
  one is not.

If deployment is deferred, say so plainly in the README rather than implying
a live system exists.

**Phase 4 question:** *Can someone else reliably use this system?*

---

# Phase 5 — Stretch / Research Extensions

## Objective

Explore additional capabilities only after the core project is complete.

**Nothing in this phase is required for project success.**

Every item may be cut without affecting completion of Phases 0–4.

## Candidate subtasks

### 5.1 Table-aware retrieval

- [ ] Parse and normalize primary-document tables.
- [ ] Compare table serialization:
  - Markdown
  - HTML
  - CSV
  - key-value rows
- [ ] Preserve headers when splitting large tables.
- [ ] Evaluate on FinQA and/or SEC-specific evidence labels.

### 5.2 Table-summary retrieval

Implement:

```text
table
  ↓
summary chunk
  ↓
retrieve summary
  ↓
link raw table
  ↓
answer from table
```

- [ ] Evaluate whether summary-assisted retrieval improves table question recall.

### 5.3 Exhibit 21 subsidiary graph

- [ ] Fetch Exhibit 21 where useful.
- [ ] Parse company-subsidiary relationships.
- [ ] Build deterministic graph tables.
- [ ] Evaluate relationship queries.

### 5.4 XBRL presentation hierarchy

- [ ] Load/use `pre.txt`.
- [ ] Build statement-aware hierarchy.
- [ ] Explore statement/tree retrieval.
- [ ] Evaluate whether it improves financial-statement navigation.

### 5.5 SIC / industry relationships

- [ ] Load SIC metadata.
- [ ] Support industry filtering.
- [ ] Explore industry-based comparison queries.

### 5.6 Company co-mention graph

- [ ] Build deterministic company gazetteer.
- [ ] Extract co-mentions.
- [ ] Evaluate whether the graph adds unique answer capability.

### 5.7 ColBERT / late-interaction retrieval

- [ ] Benchmark only if compute/time allows.
- [ ] Compare against the final Phase 3 retriever.
- [ ] Keep only if quality gain justifies storage and serving cost.

### 5.8 Query decomposition / multi-hop retrieval

- [ ] Add only for query classes that current routing cannot solve well.
- [ ] Measure independently.

### 5.9 Alternative models

Optional experiments:

- alternative embeddings
- alternative rerankers
- alternate generation models
- learned router

Each remains an ablation, not an assumed improvement.

## Exit criteria

No mandatory exit gate.

A stretch feature is considered successful only if:

- [ ] it addresses a clearly identified failure mode,
- [ ] it is evaluated,
- [ ] it adds measurable value,
- [ ] its cost/complexity is documented.

**Phase 5 question:** *What additional capabilities are worth the added complexity?*

---

# Execution Overview

```text
DATA PREPARATION ✅
Acquire → validate → audit → freeze
                ↓
PHASE 0
Foundation
Environment → CUDA → structure → config → smoke tests → SERVING SPIKE
                ↓
PHASE 1
Make It Work
1,500 filings → 512 chunks → bge-small → vector → LLM → citations → crude metric
                ↓
PHASE 2
Make It Trustworthy
truth contract → 3K eval → DEV/TEST → evidence labels → MS MARCO
              → FinanceBench → judge validation → schema freeze
                ↓
PHASE 3
Make It Good
chunk/embed ablations → BM25/RRF → rerank → CRAG → router/filtering → measure
                ↓
PHASE 4
Make It Real
full corpus → guardrails → API → deploy → observe → locked TEST → README
                ↓
PHASE 5
Stretch
tables → graph → ColBERT → extra routes → research extensions
```

---

# Suggested Time Budget

A planning estimate, not a deadline. Stated in **working hours** rather than
days, because "a day" is ambiguous and this plan was previously estimated
roughly 3–5× too optimistically.

| Phase | Hours | At 30 hrs/week |
|---|---:|---|
| Phase 0 — Foundation | 12–16 | ~0.5 week |
| Phase 1 — Make It Work | 20–28 | ~1 week |
| Phase 2 — Make It Trustworthy | 35–45 | ~1.5 weeks |
| Phase 3 — Make It Good | 40–55 | ~1.5–2 weeks |
| Phase 4 — Make It Real | 40–50 | ~1.5 weeks |
| **Phases 0–4 total** | **150–190** | **~5–6 weeks** |
| Phase 5 — Stretch | Optional | — |

## Where the time actually goes

Three tasks dominate and are consistently underestimated:

**2.8 — inline-XBRL evidence alignment (12–18 hrs).** Mapping
`ix:nonFraction` elements through HTML parsing, into normalized text, through
chunking, to character offsets, then validating the alignment by hand. This is
the single hardest task in the plan and the one most likely to overrun.

**4.3 — full-corpus embedding (multiple overnight runs).** ~14M chunks on an
8 GB GPU. Wall-clock time is largely unattended, but budget for at least one
failed run at 60% completion and a restart. Checkpointing is not optional.

**Phase 1 integration debugging (unpredictable).** The first end-to-end run
surfaces ID mismatches, encoding issues, and metadata lost during chunking.
This is exactly why Phase 1 exists, but it means the estimate has a wide
variance.

## Scheduling guidance

- A 1–2 week schedule is not realistic for Phases 0–4. Plan for 5–6 weeks at
  30 hrs/week, or reduce scope deliberately using the "If short on time"
  section in each phase.
- Do not start Phase 5 until Phase 4 passes its exit criteria.
- If the calendar compresses, cut **within** Phase 3 and Phase 4 using their
  stated stopping points. Do not cut Phase 2 — it is what makes every other
  number meaningful.

---

# Project Completion Definition

The core project is complete when **Phase 4 passes**.

Success does **not** require:

- graph retrieval,
- ColBERT,
- advanced table RAG,
- every proposed retrieval path,
- every possible model benchmark.

A successful project has:

1. a reproducible environment,
2. a working end-to-end RAG system,
3. trustworthy evaluation,
4. measured quality improvements,
5. a full-corpus implementation,
6. citations and guardrails,
7. deployment and observability,
8. reproducible final metrics,
9. documented failures and limitations.

---

# Current Status

```text
Data Preparation   ✅ COMPLETE
Phase 0            ✅ COMPLETE
Phase 1            ⚠️ COMPLETE WITH WARN (Task 1.7a citation-format compliance: 8/10)
Phase 2            ⚠️ COMPLETE WITH NOTE (see below)
Phase 3            ⬜ NOT STARTED
Phase 4            ⬜ NOT STARTED
Phase 5            ⭐ STRETCH
```

```text
Phase 2 — COMPLETE WITH NOTE

NOTE:
The original human LLM-judge calibration was not performed.
By explicit user-approved roadmap amendment, Task 2.13 used a completed
cross-model agreement study instead:
qwen3.5:9b vs gpt-oss:20b,
88.0% exact agreement, Cohen's kappa 0.737.
This is not human validation.
```

See `Progress.md` for the full dated engineering log behind this summary,
including every Phase 0/1 subtask entry, the Phase 1 Independent Task
Verification audit, the Task 2.13 cross-model agreement study, the Task
3.1 trusted baseline (row 0), and the Task 3.2 chunking ablation
(2026-09-08).

```text
Phase 3 — Make It Good                                — IN PROGRESS
  3.1 Capture the trusted baseline                    — COMPLETE
  3.2 Chunking ablation                                — COMPLETE
    winner: fixed 256-token windows, zero overlap, fixed (non-section-
    aware) splitting - see project_plan/PHASE3_CHUNKING_ABLATION.md
  3.3 Embedding model benchmark                        — COMPLETE
    winner: Qwen/Qwen3-Embedding-0.6B (dim 1024) - see
    project_plan/PHASE3_EMBEDDING_MODEL_BENCHMARK.md
  3.4 LanceDB BM25/FTS sparse retrieval baseline        — COMPLETE
    sparse-only, LanceDB-native FTS over the frozen 256/0/fixed chunks;
    dense reference (qwen3_embedding) recorded for provenance/comparison
    only, never rebuilt or used to score a sparse query - see
    project_plan/PHASE3_BM25_FTS_BASELINE.md
  3.5 RRF hybrid fusion                                 — COMPLETE
    negative result: hybrid preserves dense's 89/89 R@50 ceiling and
    raises MRR/nDCG@10 as point estimates, but is practically tied with
    dense (Recall@10 hit delta=0, both 95% CIs include 0) - dense-only
    selected as the simpler architecture - see
    project_plan/PHASE3_RRF_HYBRID_FUSION.md
  3.6 Cross-encoder reranking                           — COMPLETE
    large negative result: cross-encoder/ms-marco-MiniLM-L6-v2 reranking
    of the dense-only candidate pool credibly REGRESSES MRR/nDCG@10/
    Recall@5/Precision@5 (95% CIs entirely below 0; gained=0/lost=17 at
    hit@5) - no_rerank selected - see
    project_plan/PHASE3_CROSS_ENCODER_RERANKING.md
```

**Next action:** Phase 3, Task 3.7 — CRAG-style confidence grading,
using `qwen3_embedding` dense-only unreranked retrieval (Task 3.6
selected `no_rerank`) as the candidate source (do not start
implementation from this document alone without re-reading the exact
next subtask).
