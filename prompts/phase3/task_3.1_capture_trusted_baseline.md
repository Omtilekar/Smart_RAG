# Task 3.1 — Capture the Trusted Baseline

## Objective

Start Phase 3 by capturing a **reproducible, trusted DEV baseline** before
changing chunking, embeddings, retrieval, reranking, routing, filtering, or
any other quality component.

This task implements exactly the intent of `PROJECT_EXECUTION.md` Task 3.1:

1. run the Phase 1 architecture through the trusted Phase 2 evaluation harness;
2. store baseline DEV results;
3. make the result **row 0 of the Phase 3 ablation table**.

This is a baseline-capture task, **not an optimization task**.

Do not start Task 3.2 in this task.

---

# Non-negotiable project state

Re-read the current repository before doing any work.

Authoritative order:

1. `project_plan/PROJECT_EXECUTION.md`
2. `Progress.md`
3. `project_plan/GIT_CONVENTIONS.md`
4. Phase 2 evaluation documents/configs/results
5. Phase 1 baseline documents/configs/results

The current roadmap says:

- Data Preparation: COMPLETE
- Phase 0: COMPLETE
- Phase 1: COMPLETE WITH WARN
- Phase 2: COMPLETE WITH NOTE
- Phase 3: NOT STARTED
- next task: **3.1 Capture the trusted baseline**

The Phase 2 note must remain explicit:

- original human judge calibration was not performed;
- Task 2.13 used the user-approved cross-model substitute;
- qwen3.5:9b vs gpt-oss:20b exact agreement = 88.0%;
- Cohen's kappa = 0.737;
- this is **not human validation**;
- `faithfulness.implemented` must remain false unless a later authoritative
  task changes it for a valid reason.

Protected SEC TEST status at Phase 3 entry:

- TEST payload opened for routine experimentation: NO
- official TEST runs consumed: 0/3

Phase 3 experiments use **DEV only**.

---

# Phase 1 architecture that must be preserved for row 0

Row 0 is the pre-optimization architecture.

Do not improve it while measuring it.

The relevant Phase 1 baseline is:

- simple Markdown normalization
- fixed 512-token chunks
- zero overlap
- no section-aware splitting
- no table pipeline
- `BAAI/bge-small-en-v1.5`
- model query/passage conventions from the frozen Phase 1 embedding contract
- vector retrieval only
- exact cosine LanceDB search
- no BM25 / FTS
- no hybrid fusion
- no reranker
- no CRAG
- no router
- no metadata pre-filtering beyond whatever was already part of the frozen
  Phase 1 retriever
- no XBRL SQL production path
- no tree navigation
- no graph retrieval

Known frozen Phase 1 identities must be verified from repository artifacts
rather than trusted blindly from this prompt:

```text
chunk_config_hash:
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

embedding identity:
b39a67c9eb6487fc98f266f23742afd0a30321d98067505802a1e219b27bec84

index identity:
ace70ee67d8e98e019d221f2a0215a5b88498a0fc5dcbe73ac7ef1277630b111
```

The historical Phase 1 200-question smoke result
`doc_recall@10 = 0.970000` is **NOT** the trusted Phase 3 baseline.

That question set was explicitly temporary and discarded in Phase 2.
Do not copy 0.97 into the Phase 3 ablation table.

---

# Phase 2 evaluation facts that must remain frozen

Verify these against the actual current files:

- authoritative generated evaluation set: 2,810 questions
- gold-ready deterministic questions: 2,760
- narrative pending review: 50
- DEV: 1,932
- TEST: 828
- CIK overlap DEV vs TEST: 0
- TEST remains protected
- Task 2.8 internal chunk-level gold remains unavailable:
  `gold_evidence_count = 0`
- FinanceBench Task 2.12 remains an external benchmark, not the Phase 3
  tuning split
- FinanceBench historical result must not be silently recomputed or used as
  the routine optimization target

Metric status at Phase 3 entry must be read from the current registry.

Expected current state from Task 2.6:

```text
doc_recall@10              implemented=true,  available=true
chunk_recall@10            implemented=true,  available=false
doc_mrr                    implemented=true,  available=true
chunk_mrr                  implemented=true,  available=false
doc_ndcg@10                implemented=true,  available=true
numeric_exact_match        implemented=true,  available=true
numeric_tolerance_match    implemented=false
correct_refusal_rate       implemented=true,  available=true
citation_format_compliance implemented=true,  available=true
citation_grounding         implemented=false, available=false
faithfulness               implemented=false, available=false
```

Re-read the actual registry and STOP on material disagreement.

Never turn N/A into 0.

Never derive chunk gold from same-document, same-section, same-company, or
other proxy labels.

---

# Stage 1/8 — Repository and Phase 3 entry preflight

Print:

```text
[STAGE 1/8] Phase 3 entry preflight
```

Before modifying anything:

1. Confirm branch and clean/dirty status.
2. Confirm Phase 2 completion tag/status according to repository convention.
3. Confirm `PROJECT_EXECUTION.md` identifies Task 3.1 as next.
4. Confirm Task 2.1–2.13 tracked result/config artifacts exist.
5. Confirm the protected TEST artifact is not opened.
6. Confirm official TEST runs remain 0/3.
7. Confirm the Phase 1 chunk, embedding, and vector-index artifacts exist.
8. Confirm Phase 1 index row count and identity.
9. Confirm current evaluation schema/metric registry.
10. Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Record exact pre-task counts.

## Git rule for Task 3.1

`GIT_CONVENTIONS.md` says:

- work on `main` normally;
- branch for **Phase 3 ablations**;
- one branch per experiment.

Task 3.1 is baseline capture, not an ablation candidate.

Therefore:

- stay on `main` for Task 3.1;
- do not create `ablation/...` yet;
- Task 3.2 and later experiments may use ablation branches.

If the current repository state contradicts this, STOP and report it.

---

# Stage 2/8 — Audit evaluation-corpus coverage before scoring

Print:

```text
[STAGE 2/8] DEV corpus/index coverage audit
```

This is a hard correctness gate.

The Phase 1 LanceDB index was built from a 1,500-filing development corpus.
The Phase 2 DEV questions were generated independently from the trusted
evaluation truth contract.

Do **not** assume every DEV target document is present in the Phase 1 index.

Before running any metric:

1. Load only the public/tracked DEV split.
2. Do not load TEST.
3. Determine the document target(s) required by each retrieval-applicable DEV
   question using its frozen provenance.
4. Map targets to the Phase 1 document identity using the repository's
   existing identity rules.
5. Do not fabricate an accession for EDGAR-CORPUS.
6. For ordinary numeric questions, target identity should come from the
   existing CIK/year/document provenance.
7. For year-over-year comparative questions, preserve all required operand
   documents.
8. For cross-entity comparative questions, preserve all required company/year
   operand documents.
9. For unanswerable/adversarial questions, do not invent a retrieval target
   when the metric is not applicable.
10. Compute and print:

```text
DEV total questions:
retrieval-applicable:
fully covered by current Phase 1 index:
partially covered:
not covered:
N/A for document retrieval:

coverage by category/subtype:
...
```

## Critical rule

An out-of-corpus target is **not a retrieval miss**.

If the Phase 1 index does not cover 100% of the retrieval-applicable DEV
questions, do not silently score uncovered questions as failures.

First inspect existing Phase 2/Phase 3 documentation for an already-frozen
policy.

If no policy exists, STOP before the formal baseline and report these two
valid choices:

### Option A — fixed Phase 3 evaluable subset

Freeze:

```text
Phase 2 DEV
INTERSECT
questions whose complete gold document set is present in the frozen
Phase 1 index
```

Requirements:

- immutable list of question IDs;
- deterministic `phase3_dev_scope_sha256`;
- same exact question set for every retrieval ablation in Phase 3;
- clearly label results as `DEV/evaluable-subset`, not full DEV.

### Option B — evaluation-only DEV baseline corpus

Build an evaluation corpus containing every document required by
retrieval-applicable DEV questions, while preserving the exact Phase 1
architecture/configuration:

- same normalizer semantics;
- same 512-token fixed chunking;
- same zero overlap;
- same BGE model/revision;
- same passage/query conventions;
- same exact cosine vector retrieval;
- no new retrieval features.

This changes corpus coverage, not architecture.

Use a separate versioned artifact identity and do not overwrite the original
Phase 1 artifacts.

### Recommendation if a user decision is required

Recommend **Option B** if all required source documents can be mapped
defensibly and the build remains within the project's small-development
scale, because Task 3.1 explicitly asks for baseline **DEV results**.

Recommend Option A only when full DEV source-document mapping is incomplete
or would require changing frozen source semantics.

Do not choose between A and B silently if no repository policy already
resolves it.

---

# Stage 3/8 — Freeze the Phase 3 baseline evaluation contract

Print:

```text
[STAGE 3/8] Freeze baseline evaluation contract
```

After corpus coverage is resolved, create a tracked config such as:

```text
configs/phase_3_1_trusted_baseline.json
```

Use Task 2.10 canonical `semantic_hash()` for identity.

Do not implement another hashing convention.

The baseline config must capture at least:

```text
phase3_task
baseline_name
evaluation_source
split
eval_set_version
source_dataset_sha256
split_version
split_assignment_sha256
phase3_dev_scope_kind
phase3_dev_scope_sha256
question_count
question_ids_sha256

normalizer_version
normalization_build_sha256
chunk_config_hash
chunk_schema_version

embedding_model
embedding_revision
embedding_identity

index_identity
index_type
distance_metric

retrieval_type
retrieval_top_k
generation_enabled

metric_schema_version
evaluation_schema_hash
metrics_requested

git_sha
```

If an evaluation-only DEV index is required, record its own artifact identities
rather than reusing the historical Phase 1 index identity falsely.

## Retrieval depth

For evaluation, retrieve **top 50** if the current retriever/index can do so
without changing ranking semantics.

Why:

- Phase 3 later requires Recall@50;
- Task 3.5 uses Recall@50 as a primary metric;
- storing top-50 now lets later metrics be recomputed without rerunning the
  baseline retrieval.

This does not change Phase 1 generation context. It is evaluation candidate
depth only.

The rank-1..50 ordering must be the raw Phase 1 vector ranking.

No reranking.

No deduplication that was not already part of the Phase 1 retriever.

---

# Stage 4/8 — Metric contract for row 0

Print:

```text
[STAGE 4/8] Baseline metric contract
```

Mandatory trusted retrieval metrics:

```text
doc_recall@10
doc_mrr
doc_ndcg@10
```

Use the Task 2.6 implementations.

Do not reimplement their mathematics.

Also retain the full top-50 ranked retrieval rows for each applicable
question.

## doc_recall@50

Phase 3 explicitly requires Recall@50 later.

If the current canonical metric registry already contains a document-level
Recall@50 by the time this task runs, use it.

If it does not:

- do not invent a conflicting definition;
- use the already-tested generic Task 2.6 `hit_at_k` / first-hit semantics;
- compute a clearly labelled Phase 3 diagnostic `doc_recall@50`;
- persist the exact numerator, denominator, and value in the tracked baseline
  result;
- do not silently claim it was part of the Phase 2 registry;
- do not mutate the Phase 2 registry merely for convenience unless the
  repository's schema/version policy clearly says that is the correct action.

The baseline row must distinguish:

```text
canonical Phase 2 metric
vs
Phase 3 derived diagnostic
```

## Metrics that are N/A in this baseline when no valid gold exists

Internal chunk gold is unavailable, therefore:

```text
chunk_recall@10 = N/A
chunk_mrr       = N/A
```

not zero.

`citation_grounding` and `faithfulness` remain N/A/unimplemented.

## Generation-based metrics

Do **not** make hundreds/thousands of paid Phase 1 OpenRouter generation
calls merely to capture the retrieval baseline.

The early Phase 3 tasks 3.2–3.6 optimize retrieval quality and need a clean,
cheap, repeatable retrieval baseline.

Therefore the default Task 3.1 formal run is:

```text
generation_enabled = false
```

and these metrics are recorded as N/A with a reason when applicable:

```text
numeric_exact_match
correct_refusal_rate
citation_format_compliance
citation_grounding
faithfulness
```

Do not call them 0.

If the current repository already contains an explicit authoritative Phase 3
policy requiring full generation in Task 3.1, STOP and report that conflict
instead of silently spending credits or changing generation models.

Do not substitute a local model for the historical Phase 1 generation model
inside row 0 without explicit approval; that would change more than one
variable.

---

# Stage 5/8 — Implement the reusable baseline runner

Print:

```text
[STAGE 5/8] Build trusted baseline runner
```

Prefer a thin orchestration script and reuse the frozen Phase 1/2 modules.

Suggested script:

```text
scripts/run_phase3_trusted_baseline.py
```

Do not duplicate:

- BGE encoding logic;
- LanceDB cosine-search logic;
- metric formulas;
- config hashing;
- eval-store lifecycle;
- DEV split loading;
- TEST access logic.

Reuse the existing modules directly.

The runner must:

1. load the frozen baseline config;
2. verify all referenced artifact hashes/identities before running;
3. load DEV only;
4. apply the frozen Phase 3 DEV scope;
5. retrieve top 50 for every retrieval-applicable question;
6. record ranked items;
7. derive document first-hit rank correctly;
8. compute trusted metrics;
9. record per-stage timings;
10. write a real Task 2.11 evaluation run;
11. save a small tracked summary JSON;
12. update row 0 of the Phase 3 ablation table;
13. fail loudly on incomplete run state;
14. be deterministic/idempotent for the same configuration.

## Visible progress is mandatory

The formal run must not disappear into a hidden background process.

Use a foreground, unbuffered command, for example:

```powershell
python -u scripts/run_phase3_trusted_baseline.py --run
```

Progress should print at least every 10–25 questions:

```text
[BASELINE]  100/1932   5.2%  hits@10=...  avg_ms=...  ETA ...
[BASELINE]  200/1932  10.4%  hits@10=...  avg_ms=...  ETA ...
```

Use `flush=True` or equivalent.

If resumability is implemented, checkpoint safely under git-ignored
`artifacts/`.

If no resumability is needed because the run is short, state that explicitly.

Never redirect the formal run to a hidden log.

---

# Stage 6/8 — Evaluation run logging and provenance

Print:

```text
[STAGE 6/8] Run-log provenance
```

Use the Task 2.11 run logger.

Do not create a competing run-log format.

The formal baseline run should have a clear kind/name such as:

```text
phase3_trusted_baseline
```

Record all available provenance required by Task 2.11, including:

- run_id
- git_sha
- git dirty state if supported
- eval_set_version
- source dataset hash
- split=`dev`
- split assignment hash
- question-set/scope hash
- question count
- chunk config hash
- index/retrieval config hash
- embedding model + revision
- reranker = null
- router = null
- CRAG = null
- generation = null/disabled
- metric schema version
- timestamp
- metrics
- stage timings

TEST linkage must be absent for a DEV run.

Never create a fake TEST access record.

## Clean provenance recommendation

For the strongest run provenance:

1. implement the runner/config/tests;
2. get them passing;
3. commit that working runner;
4. verify clean working tree;
5. run the formal baseline from that clean commit;
6. record that exact git SHA in the run;
7. then commit the result files/Progress update.

Two commits for Task 3.1 are acceptable and preferable if needed to make the
formal run point at a clean reproducible code SHA.

Suggested commit split:

```text
Add Phase 3 trusted baseline runner
Capture trusted Phase 3 DEV baseline
```

Do not create fake retroactive history.

---

# Stage 7/8 — Row 0 of the ablation table

Print:

```text
[STAGE 7/8] Freeze ablation row 0
```

Create the Phase 3 ablation table now because Task 3.1 explicitly requires
row 0 and Task 3.13 says the table must be maintained throughout Phase 3.

Preferred tracked artifacts:

```text
results/phase_3_ablation_table.csv
results/phase_3_1_trusted_baseline.json
```

A companion Markdown view is optional if useful.

Row 0 should contain enough provenance to reproduce it.

Recommended columns:

```text
row_id
configuration
status
run_id
git_sha
phase3_config_hash
eval_split
eval_scope_kind
eval_scope_sha256
question_count

corpus_document_count
chunk_count
chunk_config_hash
embedding_model
embedding_revision
embedding_identity
index_identity

retrieval
candidate_k

doc_recall_at_10
doc_recall_at_50
doc_mrr
doc_ndcg_at_10
precision_at_5
refusal_metric

retrieval_latency_p50_ms
retrieval_latency_p95_ms
query_embedding_latency_p50_ms
search_latency_p50_ms
index_size_bytes

notes
```

Use JSON null / empty CSV cells plus an explicit note for N/A values.

Never encode N/A as `0`.

For row 0:

```text
row_id = 0
configuration = vector_baseline_phase1
status = trusted_baseline
```

No future task may overwrite row 0.

Later Phase 3 tasks append rows.

Add tests proving:

- row 0 cannot be silently replaced with a different config hash;
- duplicate row IDs are rejected;
- same row/config idempotent rewrite is safe if that is the chosen API;
- N/A remains distinguishable from zero;
- table rows retain config hash + git SHA;
- Phase 3 result generation cannot read TEST.

---

# Stage 8/8 — Verification, documentation, Git, and stop

Print:

```text
[STAGE 8/8] Verify and close Task 3.1
```

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Report exact counts.

The single Ollama integration test may skip if the Ollama server is not
running; record that as an environment skip rather than a regression only if
that is still the repository's established behavior.

Update:

```text
project_plan/PHASE3_TRUSTED_BASELINE.md
project_plan/REPOSITORY_STRUCTURE.md   (only if new files require it)
Progress.md
```

Do not rewrite historical Phase 1 or Phase 2 results.

Do not modify:

- raw data;
- protected TEST artifact;
- Task 2.1 truth contract;
- Task 2.2 tag registry;
- Task 2.3 frozen dataset;
- Task 2.4 split assignment;
- Task 2.8 evidence outcome;
- Task 2.9 frozen chunk schema;
- Task 2.10 canonical hashing semantics;
- Task 2.12 FinanceBench result;
- Task 2.13 cross-model result.

## Git safety

Follow `project_plan/GIT_CONVENTIONS.md`.

Before commit:

```text
git status
git add -n <specific files>
secret scan
large-file scan
```

Never stage:

- `data/`
- `artifacts/`
- `*.duckdb`
- `*.parquet`
- LanceDB index data
- embeddings
- model caches
- `.env`
- API keys
- generated logs

Commit small configs/results/tests/docs.

No Phase 3 completion tag.

Do not tag until the Phase 3 exit gate passes.

Push only if a remote is configured; do not invent one.

---

# Required tests

Add targeted tests for the new Task 3.1 logic.

At minimum cover:

1. DEV-only split enforcement.
2. TEST file/access API is never touched by baseline runner.
3. pending/non-applicable questions are excluded according to frozen
   applicability rules rather than scored as misses.
4. multi-document comparative gold sets are handled correctly.
5. out-of-corpus target detection.
6. out-of-corpus targets are never automatically counted as misses.
7. phase3 scope hash determinism.
8. config hash determinism and sensitivity.
9. artifact identity mismatch causes hard failure.
10. top-50 retrieval preserves raw vector rank.
11. doc_recall@10 uses Task 2.6/Phase 1 semantics.
12. doc_mrr uses Task 2.6 implementation.
13. doc_ndcg@10 uses Task 2.6 implementation.
14. optional Phase 3 doc_recall@50 diagnostic is hand-checkable.
15. N/A != 0.
16. no chunk metric is emitted as available without chunk gold.
17. generation remains disabled for the formal row-0 run.
18. no paid API/network call occurs in portable tests.
19. Task 2.11 run log records DEV provenance.
20. completed run question count matches expected scope.
21. row 0 append/freeze behavior.
22. duplicate/config-drift protection for row 0.
23. result JSON contains config hash + git SHA + run_id.
24. full baseline result contains no TEST question IDs/payload.
25. existing Phase 1/2 frozen results remain unchanged.

Use tiny synthetic fixtures for portable tests.

Do not make the portable suite depend on the real full index or GPU.

A local-data/model/GPU integration test may exercise a tiny real baseline path
if useful, using existing pytest markers.

---

# Formal result summary

At completion print something like:

```text
PHASE 3 — TASK 3.1 TRUSTED BASELINE
===================================

Evaluation:
  source:                    internal Phase 2 evaluation set
  split:                     DEV
  scope:                     <full DEV or frozen evaluable subset>
  questions evaluated:       X
  scope_sha256:              ...

Architecture:
  chunking:                  fixed 512, zero overlap
  embedding:                 BAAI/bge-small-en-v1.5
  retrieval:                 vector-only exact cosine
  BM25:                      NO
  reranker:                  NO
  CRAG:                      NO
  router:                    NO
  metadata prefilter:        NO/new features
  generation formal run:     NO

Metrics:
  doc_recall@10:             ...
  doc_recall@50:             ... / N/A
  doc_mrr:                   ...
  doc_ndcg@10:               ...
  chunk_recall@10:           N/A — no internal chunk gold
  chunk_mrr:                 N/A — no internal chunk gold
  precision@5:               N/A — not yet frozen/implemented
  refusal metric:            N/A — generation disabled

Latency:
  retrieval p50:             ... ms
  retrieval p95:             ... ms
  query embedding p50:       ... ms
  vector search p50:         ... ms

Ablation table:
  row 0:                     FROZEN

Run provenance:
  run_id:                    ...
  git_sha:                   ...
  phase3_config_hash:        ...

Protected TEST:
  opened:                    NO
  official runs used:        0/3

FinanceBench:
  rerun:                     NO
  historical Task 2.12 result unchanged

Tests:
  doctor:                    PASS
  portable:                  ...
  full:                      ...

Git:
  branch:                    main
  commit(s):                 ...
  Phase 3 tag:               NOT CREATED

TASK 3.1 STATUS:
  COMPLETE

PHASE 3 STATUS:
  IN PROGRESS

NEXT:
  Task 3.2 — Chunking ablation
```

Then STOP.

Do not start Task 3.2 automatically.

---

# Stop conditions

STOP rather than guessing if any of the following occurs:

1. `PROJECT_EXECUTION.md` no longer says Task 3.1 is next.
2. Phase 2 is not actually complete under the recorded amendment.
3. protected TEST would need to be opened.
4. official TEST run budget would be consumed.
5. the DEV split hash/version does not match frozen Phase 2 provenance.
6. Phase 1 chunk/embedding/index identities do not match their frozen
   manifests.
7. the formal DEV target corpus is materially outside the current Phase 1
   index and no repository policy resolves whether to subset or build a
   DEV-only evaluation index.
8. a DEV question's source document cannot be mapped defensibly.
9. an out-of-corpus target would otherwise be counted as a miss.
10. a requested metric has no valid gold or no frozen definition.
11. generation would require paid API calls merely to create row 0.
12. someone proposes switching generation models inside the baseline without
    explicit approval.
13. someone proposes using FinanceBench as the routine tuning set.
14. someone proposes altering Phase 1 architecture before row 0 is frozen.
15. chunk-level relevance is inferred from a proxy rather than gold.
16. a new hashing implementation would duplicate Task 2.10.
17. a new run-log format would duplicate Task 2.11.
18. working tree/provenance cannot be made unambiguous for the formal run.
19. any regression changes Task 2.1–2.13 frozen results.
20. any data/artifact/secret is about to be committed.

---

# Success definition

Task 3.1 is complete only when:

- a defensible Phase 3 DEV scope is frozen;
- the untouched Phase 1 retrieval architecture has been evaluated on it;
- trusted retrieval metrics are recorded;
- unavailable metrics are explicitly N/A rather than fake zeros;
- a reproducible Task 2.11 run exists;
- row 0 of the Phase 3 ablation table is frozen;
- config hash + git SHA reproduce the row;
- TEST remains untouched at 0/3;
- all regression tests pass;
- the repository is ready for Task 3.2;
- **no optimization has begun yet**.
