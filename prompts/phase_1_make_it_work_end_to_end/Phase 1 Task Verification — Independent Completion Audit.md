# Phase 1 Task Verification — Independent Completion Audit

## Objective

Perform a **full independent verification of Phase 1 — “Make It Work End to End”**.

Do **not** assume Phase 1 is complete merely because `Progress.md`, project documentation, commit messages, or result files say it is complete.

Your job is to inspect the repository as it exists **right now**, re-run appropriate checks, independently validate important artifacts/results, compare implementation against the authoritative Phase 1 requirements, identify inconsistencies or incomplete work, and determine whether Phase 1 is genuinely complete and clean enough to proceed to Phase 2.

This is primarily a **verification/audit task**, not a new feature-development task.

---

# 1. Authoritative Sources

Before running or modifying anything, inspect the repository and establish the applicable source-of-truth hierarchy.

At minimum read:

- `project_plan/PROJECT_EXECUTION.md`
- `Progress.md`
- `project_plan/REPOSITORY_STRUCTURE.md`
- `project_plan/DEVELOPER_COMMANDS.md`
- all existing `project_plan/PHASE1_*.md` documents
- relevant Phase 1 configs under `configs/`
- relevant Phase 1 result files under `results/`
- relevant source modules under `src/`
- relevant Phase 1 scripts
- relevant tests

Use `PROJECT_EXECUTION.md` as the authoritative definition of what Phase 1 is supposed to accomplish unless another repository document explicitly establishes a stronger precedence rule.

Treat `Progress.md` as historical evidence, **not proof**.

Do not alter old historical entries in `Progress.md`.

---

# 2. Scope

Verify every Phase 1 task individually:

1. **1.1 — Select Development Corpus**
2. **1.2 — Minimal Normalization**
3. **1.3 — Minimal Fixed-Window Chunker**
4. **1.4 — Baseline Embedding Pipeline**
5. **1.5 — Vector-Only Index**
6. **1.6 — Baseline Retriever**
7. **1.7 — Minimal Generation Layer**
8. **1.8 — Citation Integrity Smoke**
9. **1.7a — Citation Format Compliance Correction**
10. **1.9 — 200-Question Smoke Evaluation**
11. **1.10 — Baseline Metric Runner**
12. **1.11 — End-to-End Command**

Also verify the **Phase 1 exit criteria as a whole**.

Do NOT begin Phase 2.

Do NOT add:

- BM25
- hybrid retrieval
- reranking
- CRAG
- routing
- advanced chunking
- production ANN optimization
- guardrails
- answer-quality judges
- new evaluation frameworks
- Phase 2 truth-contract functionality
- unrelated refactors

Absence of those later-phase components is **not a Phase 1 failure**.

Phase 1 deliberately uses a simple vertical slice.

---

# 3. Audit Philosophy

For every important claim, distinguish:

- **documented**
- **implemented**
- **tested**
- **independently verified**
- **not verified**
- **failed**

Never convert “document says complete” into “verified complete”.

Whenever practical, derive important facts directly from source artifacts rather than trusting generated summaries.

Examples:

- count rows directly instead of trusting a JSON count
- hash artifacts directly instead of copying a documented hash
- inspect LanceDB directly instead of trusting an index summary
- run tests instead of trusting previous test counts
- recompute evaluation aggregates independently
- inspect actual CLI behavior
- inspect actual citation validation rules
- verify Git ignore behavior directly

---

# 4. Establish Repository Baseline

Before making any changes, capture:

```text
git branch
git status --short
git log --oneline --decorate -20
python --version
sys.executable
```

Confirm the project-local `.venv` is being used.

Run the project's existing environment/doctor command if one exists.

Record:

- current branch
- current HEAD
- dirty/clean status
- Python version
- environment path
- CUDA availability if relevant
- whether required local artifacts exist
- whether required environment variables for live generation are configured

Do not print secret values.

---

# 5. Git and Security Safety

Before doing substantive verification:

### Verify ignored content

Confirm these cannot accidentally be committed:

- `.env`
- `.venv/`
- `data/`
- large runtime artifacts
- LanceDB indexes
- generated embeddings
- normalized corpus artifacts
- temporary files
- model caches
- credentials/secrets

Use commands such as:

```bash
git status --ignored
git check-ignore -v <representative paths>
git add -n .
```

The dry run must not attempt to stage large data, secrets, `.env`, `.venv`, or runtime artifacts.

### Secret scan

Inspect trackable/currently tracked files for:

- API keys
- bearer tokens
- passwords
- private credentials
- accidentally committed `.env` contents
- personal machine-specific absolute paths where inappropriate

Never print a secret into the audit report.

If a secret is discovered, stop treating the repository as clean and report it prominently.

---

# 6. Task 1.1 — Development Corpus

Verify the Phase 1 development corpus from the actual artifact/source.

Expected historical characteristics include:

```text
1,500 documents
1,500 unique document IDs
EDGAR-CORPUS based
2016–2020
```

Do not trust those numbers blindly.

Independently verify:

- artifact exists
- exact row count
- unique `document_id` count
- no unexpected duplicate document IDs
- expected year range
- expected source provenance
- required metadata fields
- deterministic selection behavior
- manifest/config hash if one is part of the contract
- underlying source documents can still be resolved

Verify that later Phase 1 tasks use the same frozen Task 1.1 corpus rather than silently selecting a different corpus.

Status:

```text
VERIFIED / WARN / FAIL
```

Record evidence.

---

# 7. Task 1.2 — Minimal Normalization

Inspect the actual normalizer and normalized artifacts.

Verify:

- implementation exists
- normalization is deterministic
- output count corresponds correctly to Task 1.1
- document IDs are preserved
- source metadata/provenance survives
- normalization does not invent content
- known empty-source cases are handled intentionally
- repeated builds produce equivalent output/hash where the contract requires it
- raw `data/` is not mutated

Check the recorded normalization build hash against a fresh calculation if feasible.

Do not rebuild expensive data unnecessarily if existing artifacts can be independently validated.

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 8. Task 1.3 — Minimal Fixed-Window Chunker

Inspect chunking implementation, config, artifact, tests and metadata.

Verify:

- fixed-window baseline is actually what is implemented
- no later section-aware/semantic chunking was silently introduced
- deterministic chunk IDs
- deterministic chunk ordering
- no duplicate chunk IDs
- all chunks map to valid source documents
- required metadata survives
- chunks have valid/non-empty text according to the contract
- overlap/window values come from config rather than undocumented magic numbers
- artifact is internally consistent

Independently count total chunks.

Historical Phase 1 records indicate approximately:

```text
162,357 chunks
```

Treat this as a value to verify, not an assumption.

Check the chunk configuration hash and confirm all downstream Phase 1 components refer to the same chunk build.

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 9. Task 1.4 — Baseline Embedding Pipeline

Inspect implementation and real embedding artifact.

Verify:

- configured embedding model
- pinned/reproducible model revision if required
- expected embedding dimension
- exact embedding row count
- one embedding per expected chunk
- unique chunk IDs
- no missing chunk embeddings
- all vectors finite
- correct numeric dtype
- correct normalization/query-document behavior for the selected embedding model
- GPU use is intentional where configured
- CPU fallback is not silently being mistaken for GPU execution
- embedding artifact carries sufficient provenance

Historical state indicates:

```text
model: BAAI/bge-small-en-v1.5
dimension: 384
rows: 162,357
```

Independently verify these.

Do not re-embed the entire corpus unless a real verification gap requires it.

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 10. Task 1.5 — Vector-Only Index

Inspect the real LanceDB artifact.

Verify directly:

- table exists
- expected table name
- expected row count
- schema
- vector dimension
- metadata columns
- exact relationship to Task 1.4 embedding artifact
- no missing/extra rows
- search metric
- queryability

Phase 1 intentionally used an exact vector baseline.

Verify that no ANN index has silently altered the historical Phase 1 baseline unless documentation explicitly records such a change.

Historical expected state:

```text
table: chunks
rows: 162,357
metric: cosine
ANN indexes: 0
```

Perform at least one real search against the local index.

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 11. Task 1.6 — Baseline Retriever

Inspect the retriever implementation.

Verify that:

- natural-language question is encoded using the expected query path
- it queries the Task 1.5 index
- default/explicit `k` semantics are correct
- ranks are deterministic where expected
- returned objects contain required fields
- `chunk_id` resolves
- `document_id` resolves
- source text/metadata corresponds to stored chunks
- scores/distances are interpreted correctly
- no generation is invoked
- no BM25/hybrid/reranker/CRAG/router is involved

Perform several real retrieval queries.

For each manually inspect returned chunks and confirm the IDs exist in storage.

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 12. Task 1.7 — Minimal Generation Layer

Inspect:

- minimal generator
- provider abstraction
- OpenRouter provider
- generation config
- citation parser
- prompt contract
- abstention behavior
- tests

Verify:

- provider is replaceable
- API key is read securely
- no API key is hardcoded
- model is runtime-configurable
- generation uses retrieved context only
- context passed to the model contains identifiable chunk IDs
- citation syntax contract is explicit
- citations are parsed from generated output
- insufficient-context behavior is intentional
- deterministic generation settings match Phase 1 requirements

Do not expose `.env` values.

Do not make a paid API call merely to increase confidence if the existing test/artifact evidence is sufficient.

If a live call is necessary to validate a contract, first determine whether the repository's existing verification convention permits it and make the absolute minimum number of calls.

Never retry/cherry-pick until a desired result appears.

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 13. Task 1.8 — Citation Integrity Smoke

Inspect the citation-integrity implementation independently.

Confirm that it validates at minimum:

- valid syntax
- cited chunk exists
- cited chunk was actually supplied in the exact generation context
- malformed citation attempts
- non-abstaining answer requiring appropriate citation behavior
- unknown chunk IDs
- out-of-context chunk IDs

Review tests carefully.

Manually construct adversarial cases instead of relying only on existing tests.

At minimum test examples resembling:

```text
valid [document::chunkN]
unknown chunk ID
valid existing chunk not supplied to model
fullwidth brackets 【...】
truncated chunk identifier
answer with no citation when one is required
valid abstention
```

Confirm the validator itself is correct.

Do NOT weaken the validator merely to make a model output pass.

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 14. Task 1.7a — Citation Format Compliance Correction

This task is especially important.

Historical evidence records that the original 10-case citation smoke performed poorly and that the prompt-only correction improved compliance but did **not** make it perfect.

The governing historical diagnostic is:

```text
8 / 10 citation-format compliance
2 residual fullwidth-bracket failures
0 unknown-chunk failures
0 out-of-context citation failures
```

Verify:

- correction was prompt-only as intended
- citation parser was not loosened
- integrity validator was not weakened
- malformed citations were not silently normalized/repaired after generation
- provider/model/settings used for the correction match the recorded experiment
- before/after artifacts exist
- historical Task 1.8 result remains preserved
- Task 1.7a result does not overwrite history

### Critical rule

Do **not** mark this warning resolved because one later generation call happened to produce a correct citation.

Do **not** rerun repeatedly and cherry-pick a better number.

Unless a formally approved new evaluation supersedes the frozen 10-case diagnostic, preserve:

```text
Task 1.7a — COMPLETE WITH WARN
citation format compliance — 8/10
```

This warning is accepted Phase 1 technical debt, not evidence that the Phase 1 implementation task itself was never completed.

Status should therefore distinguish:

```text
IMPLEMENTATION COMPLETE?
YES / NO

KNOWN MODEL-COMPLIANCE WARNING?
YES / NO
```

---

# 15. Task 1.9 — 200-Question Smoke Evaluation Dataset

Verify the dataset itself, not merely the summary.

Expected contract:

```text
200 questions
200 unique target_document_id values
1 question per filing

5 categories × 40:
- business
- risk_factors
- mdna
- market_risk
- financial_statements

label granularity: document
metric intended: doc_recall@10
```

Verify directly:

- exactly 200 records
- exact category balance
- unique question IDs
- unique target document IDs
- every target document belongs to Task 1.1 corpus
- assigned source section exists and is non-empty
- deterministic selection algorithm
- deterministic question construction
- no LLM-generated questions
- no fabricated answer spans
- no fabricated `target_chunk_id`
- no accidental generation/API dependency
- dataset hash matches its recorded provenance

Independently sample at least 10 cases and resolve them back to source data.

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 16. Task 1.10 — Baseline Metric Runner

Inspect metric implementation before executing it.

Verify the exact metric contract:

```text
metric = doc_recall@10
k = 10 chunk results
target match = exact document_id equality
no document deduplication before cutoff
maximum one hit per question
first_hit_rank = diagnostic only
retrieval errors must not silently become misses
```

Check that it does **not** accidentally implement:

- Recall@k over chunks
- MRR
- fuzzy CIK/company matching
- fiscal-year matching
- answer correctness
- generation scoring

Run the real 200-question evaluation using the existing frozen dataset/index.

Historical baseline:

```text
questions:      200
hits:           194
doc_recall@10:  0.970000
```

Independently recompute:

```text
hit_count
hit_count / question_count
```

without calling the same summary helper used by production code.

Compare results.

Also verify deterministic behavior where practical.

If today's result differs from 194/200, investigate before changing anything.

Do not “fix” the metric to recover the expected result.

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 17. Task 1.11 — End-to-End Command

Inspect:

```bash
python -m src.cli.phase1 answer --question "..."
python -m src.cli.phase1 evaluate
```

or whatever exact commands the current repository defines.

Verify that the CLI composes existing Phase 1 components rather than duplicating their logic.

### Answer command

Check:

- accepts question
- rejects empty/invalid input
- calls baseline retriever
- passes retrieved context into generator
- returns non-empty answer when provider succeeds
- presents parsed citations
- does not dump embeddings/vectors/full internal context
- errors produce safe non-zero exit behavior
- secret values never appear
- retrieval `k` matches generation contract

### Evaluate command

Check:

- invokes/reuses Task 1.10 metric runner
- does not duplicate metric math
- evaluates all 200 questions
- prints question count
- prints hit count
- prints `doc_recall@10`
- saves result separately from historical baseline when appropriate
- does not call generation/OpenRouter

Expected evaluation:

```text
questions = 200
hits = 194
doc_recall@10 = 0.970000
```

Status:

```text
VERIFIED / WARN / FAIL
```

---

# 18. Full Automated Test Verification

Determine the repository's intended test commands from existing documentation.

Run the appropriate:

1. doctor/environment check
2. portable suite
3. local-data suite
4. full non-destructive suite

Historical Task 1.11 baseline was approximately:

```text
portable:
344 passed
10 deselected
0 failed

full:
354 passed
0 failed
```

Do not require the current test count to equal those numbers if new legitimate tests have since been added.

Instead verify:

- zero unexpected failures
- no relevant tests silently skipped
- deselections correspond to documented markers
- no test accidentally makes expensive API calls
- all Phase 1 modules have meaningful coverage
- tests test behavior, not just existence/imports

Report current counts.

If the current suite has fewer tests than the historical baseline, investigate why.

---

# 19. Independent Artifact Traceability

Trace the Phase 1 vertical slice end to end:

```text
raw EDGAR source
    ↓
Task 1.1 manifest
    ↓
Task 1.2 normalized documents
    ↓
Task 1.3 chunks
    ↓
Task 1.4 embeddings
    ↓
Task 1.5 LanceDB
    ↓
Task 1.6 retrieval
    ↓
Task 1.7 generation
    ↓
Task 1.8 citation validation
```

Separately trace evaluation:

```text
Task 1.1 corpus
    ↓
Task 1.9 200-question dataset
    ↓
Task 1.6 retriever @ k=10
    ↓
Task 1.10 doc_recall@10
    ↓
Task 1.11 evaluate CLI
```

Confirm identifiers/hashes/configuration provenance do not silently diverge between stages.

Check especially:

- document IDs
- chunk IDs
- chunk config hash
- embedding model/revision
- vector dimension
- index row count
- smoke-dataset hash
- metric config
- result provenance

---

# 20. Documentation Consistency Audit

Compare actual implementation against:

- `Progress.md`
- `PROJECT_EXECUTION.md`
- `REPOSITORY_STRUCTURE.md`
- `DEVELOPER_COMMANDS.md`
- every `PHASE1_*.md`
- configs
- result summaries

Look for:

- stale counts
- stale hashes
- outdated paths
- incorrect task status
- docs claiming features that do not exist
- implemented files still marked “planned”
- features implemented but undocumented
- references to deleted files
- contradictory command examples
- historical result accidentally presented as current
- 8/10 citation warning accidentally described as resolved

Fix trivial documentation inconsistencies only when the correct answer is unambiguous from repository evidence.

Do not rewrite historical Progress entries.

---

# 21. Code Quality / “Neatness” Review

Phase 1 should not merely execute—it should be understandable and maintainable.

Review changed Phase 1 code for:

- unnecessary duplication
- giant functions
- dead code
- debug prints
- commented-out experiments
- unexplained constants
- hardcoded machine paths
- hardcoded secrets
- hardcoded model where configuration should own it
- weak error handling
- silent exception swallowing
- silent CPU/API fallbacks
- inconsistent naming
- duplicated metric calculations
- duplicated retrieval logic
- circular imports
- improper package boundaries
- missing type hints where the surrounding project consistently uses them
- nondeterministic behavior where determinism is promised
- runtime-generated artifacts accidentally tracked by Git

Do not perform broad aesthetic refactoring.

Only make small, clearly justified corrections that reduce real Phase 1 technical debt without changing architecture or experimental semantics.

---

# 22. Frozen Data Safety

The project's source data is frozen.

Confirm verification did not mutate:

- EDGAR-CORPUS source parquet
- MS MARCO source data
- XBRL source files/database
- primary filings

Record representative hashes/size/count evidence before/after when appropriate.

Do not redownload data.

Do not regenerate Phase 1 source selection from the internet.

---

# 23. Result Reproducibility

For deterministic/offline stages, verify reproducibility as far as practical.

Strong candidates:

- Task 1.1 manifest hash
- normalization build hash
- chunk configuration hash
- smoke-evaluation dataset hash
- Task 1.10 metric result/hash
- Task 1.11 evaluate result

Separate:

```text
deterministic data/build outputs
```

from:

```text
non-deterministic external model outputs
```

Do not pretend an API-based LLM generation result is perfectly reproducible simply because `temperature=0`.

---

# 24. Phase 1 Official Exit Criteria

Independently evaluate every official Phase 1 exit criterion from `PROJECT_EXECUTION.md`.

At minimum verify the recorded criteria corresponding to:

1. One command accepts a question and returns an answer.
2. The answer can contain valid source citations.
3. Every accepted citation resolves to a stored source chunk supplied to generation.
4. A 200-question evaluation runs end to end.
5. `doc_recall@10` is calculated, printed and saved.
6. Integration bugs/limitations discovered during the vertical slice are documented.
7. Advanced retrieval components were not prematurely introduced into the Phase 1 baseline.

Do not inherit PASS values from `Progress.md`.

Produce fresh evidence for each.

---

# 25. Do Not Hide Warnings

A phase can be implementation-complete while carrying an explicitly accepted warning.

The known citation warning must remain visible unless stronger, formally comparable evidence genuinely supersedes it.

Expected likely overall state:

```text
Phase 1 — COMPLETE WITH WARN

Known warning:
Task 1.7a citation-format compliance = 8/10
```

Do not change this to plain `COMPLETE` merely because:

- unit tests pass
- Task 1.11 produced one good live answer
- the metric is 0.97
- citation integrity works when citations are syntactically valid

Those facts test different contracts.

---

# 26. Repair Policy

This task is audit-first.

### You MAY fix:

- obvious broken documentation references
- missing narrow regression tests
- trivial CLI/help inconsistencies
- obvious deterministic bugs whose intended behavior is already unambiguously defined by Phase 1
- accidental generated-file tracking
- small repository hygiene problems

### You MUST NOT silently fix:

- architecture
- retrieval strategy
- citation policy
- evaluation definition
- model selection
- accepted experimental warning
- Phase 2 functionality
- benchmark definitions
- historical result artifacts

If a substantial defect is found, document it as a blocker rather than changing the experiment until it “passes”.

---

# 27. Final Verification Report

Create:

```text
project_plan/PHASE1_VERIFICATION_REPORT.md
```

The report must contain:

## A. Executive Verdict

Exactly one:

```text
PASS — Phase 1 independently verified complete
PASS WITH WARN — Phase 1 complete, documented non-blocking warning(s) remain
FAIL — Phase 1 is not actually complete
BLOCKED — verification could not be completed
```

Do not choose PASS if meaningful unresolved warnings remain.

Given the current historical state, `PASS WITH WARN` is the expected outcome **only if fresh verification confirms everything else**.

---

## B. Per-Task Matrix

Use a table:

| Task | Requirement | Implementation | Tests | Artifact/Runtime Evidence | Status |
|---|---|---|---|---|---|
| 1.1 | Development corpus | ... | ... | ... | VERIFIED/WARN/FAIL |
| 1.2 | Normalization | ... | ... | ... | ... |
| 1.3 | Chunking | ... | ... | ... | ... |
| 1.4 | Embeddings | ... | ... | ... | ... |
| 1.5 | Vector index | ... | ... | ... | ... |
| 1.6 | Retriever | ... | ... | ... | ... |
| 1.7 | Generation | ... | ... | ... | ... |
| 1.8 | Citation integrity | ... | ... | ... | ... |
| 1.7a | Citation correction | ... | ... | ... | ... |
| 1.9 | 200-question dataset | ... | ... | ... | ... |
| 1.10 | Baseline metric | ... | ... | ... | ... |
| 1.11 | End-to-end CLI | ... | ... | ... | ... |

---

## C. Recomputed Key Facts

Report freshly observed values such as:

```text
development documents:
normalized documents:
chunks:
embeddings:
embedding dimension:
LanceDB rows:
ANN indexes:
smoke questions:
metric hits:
doc_recall@10:
portable tests:
full tests:
citation-format frozen diagnostic:
```

Clearly distinguish historical values from freshly reproduced ones.

---

## D. Phase Exit Criteria

Table:

| Criterion | Evidence | Result |
|---|---|---|
| question → answer command | ... | PASS/FAIL |
| source citations | ... | PASS/FAIL |
| citation resolution | ... | PASS/FAIL |
| 200-question evaluation | ... | PASS/FAIL |
| doc_recall@10 persisted | ... | PASS/FAIL |
| integration issues documented | ... | PASS/FAIL |
| no premature advanced retrieval | ... | PASS/FAIL |

---

## E. Warnings / Technical Debt

At minimum explicitly state the status of:

```text
Task 1.7a citation-format compliance
```

Also list any newly discovered warning.

Separate:

```text
blocking
non-blocking
deferred by roadmap
```

Do not label an intentionally deferred Phase 2 feature as Phase 1 technical debt unless the roadmap itself does so.

---

## F. Reproducibility

Document:

- commands run
- hashes independently recomputed
- artifacts inspected
- deterministic reruns
- API calls, if any
- anything intentionally not rerun and why

---

## G. Git / Security

Report:

```text
secret scan:
.env ignored:
data ignored:
artifacts ignored:
git add -n safety:
working-tree state:
```

Never include actual secret values.

---

## H. Files Changed by Verification

List every file modified by this audit and explain why.

A verification task should result in minimal repository changes.

---

# 28. Progress.md Update

Only after verification is complete, append a new historical entry to `Progress.md`:

```text
## YYYY-MM-DD — Phase 1 Independent Task Verification
```

Include:

- objective
- baseline
- commands run
- independently verified facts
- discrepancies found
- fixes made, if any
- test results
- Phase 1 exit-criteria result
- known warnings
- files modified
- Git state
- final verdict

Do not edit or rewrite any previous Phase 1 entries.

If the final verdict remains:

```text
PASS WITH WARN
```

preserve:

```text
Phase 1 — COMPLETE WITH WARN
Task 1.7a citation-format compliance — 8/10
```

unless genuinely superseded by approved comparable evidence.

---

# 29. Commit Policy

After all checks pass and only appropriate verification/report changes remain:

1. inspect `git diff`
2. inspect `git diff --stat`
3. run final secret scan
4. run `git add -n .`
5. ensure no data/artifacts/secrets will be staged
6. run final tests
7. make **one coherent verification commit**

Suggested commit:

```text
Verify Phase 1 completion
```

Do not create a Phase 2 commit.

Do not push unless the repository already has a configured remote and existing project instructions explicitly say this task should push.

Do not invent remote/tag behavior.

If phase tagging policy is ambiguous, leave tagging unchanged and document that fact.

---

# 30. Final Console Summary

At the end, print a concise summary in this exact spirit:

```text
PHASE 1 INDEPENDENT VERIFICATION
================================

1.1 Development Corpus ............. VERIFIED
1.2 Minimal Normalization .......... VERIFIED
1.3 Fixed-Window Chunker ........... VERIFIED
1.4 Baseline Embeddings ............ VERIFIED
1.5 Vector-Only Index .............. VERIFIED
1.6 Baseline Retriever ............. VERIFIED
1.7 Minimal Generation ............. VERIFIED
1.8 Citation Integrity ............. VERIFIED
1.7a Citation Correction ........... VERIFIED WITH WARN
1.9 200-Question Evaluation ........ VERIFIED
1.10 Baseline Metric Runner ........ VERIFIED
1.11 End-to-End Command ............ VERIFIED

Tests:             <current result>
Questions:         <current result>
Hits:              <current result>
doc_recall@10:     <current result>
Citation warning:  <current verified state>

Phase exit criteria: <N>/<N> PASS

FINAL VERDICT:
PASS / PASS WITH WARN / FAIL / BLOCKED
```

Then state clearly:

```text
READY FOR PHASE 2: YES / NO
```

If YES with warnings, name the warning immediately below it.

---

# Core Rule

**Do not prove the documentation correct. Prove the repository correct.**

A completed task requires real code/artifacts/tests/runtime evidence consistent with the Phase 1 contract.

If documentation and reality disagree, reality wins.

If a historical warning still exists, preserve it.

If Phase 1 genuinely satisfies its contract with only the already accepted citation-format warning, conclude:

```text
PASS WITH WARN
READY FOR PHASE 2: YES

Known accepted warning:
Task 1.7a citation-format compliance remains 8/10.
```

Do not start Phase 2 during this task.