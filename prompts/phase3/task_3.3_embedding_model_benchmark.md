# Phase 3 — Task 3.3: Embedding Model Benchmark

## Objective

Benchmark candidate embedding models **only after freezing Task 3.2's
winning chunking configuration**, then select one embedding model for all
subsequent Phase 3 retrieval experiments.

This task is an **embedding-model-only ablation**.

Do not add BM25, hybrid fusion, reranking, CRAG, routing, metadata
pre-filtering, SQL retrieval, graph retrieval, generation changes, ANN
quantization, or new chunking behavior.

Do not start Task 3.4 automatically.

---

# Authoritative sources and precedence

Before changing code, re-read the current repository state in this order:

1. `project_plan/PROJECT_EXECUTION.md`
2. `Progress.md`
3. `project_plan/GIT_CONVENTIONS.md`
4. `project_plan/PHASE3_TRUSTED_BASELINE.md`
5. `project_plan/PHASE3_CHUNKING_ABLATION.md`
6. `results/phase_3_1_trusted_baseline.json`
7. `results/phase_3_2_chunking_ablation.json`
8. `results/phase_3_ablation_table.csv`
9. `configs/phase_3_1_trusted_baseline.json`
10. `configs/phase_3_2_chunking_ablation.json`
11. Task 2.10 artifact/versioning code
12. Task 2.11 run-log code
13. current embedding/index/retrieval implementations and tests

Repository truth wins over stale prompt text.

If `PROJECT_EXECUTION.md` names a specific Task 3.3 candidate model set or
selection rule, use it exactly.

If the roadmap does **not** define the candidate model set sufficiently to
run a fair benchmark, STOP before downloading/building expensive artifacts
and report the ambiguity. Do not silently invent a benchmark list from a
leaderboard.

---

# Verified Task 3.2 input state

Task 3.2 is COMPLETE.

The selected chunking strategy is frozen as:

```text
split_mode:          fixed
window_size_tokens:  256
overlap_tokens:      0
stride_tokens:       256

chunk_config_hash:
ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
```

Task 3.2 winner metrics under the existing BGE-small control:

```text
configuration: fixed 256/0

questions:       89
doc_recall@10:   83/89 = 0.9326
doc_recall@50:   87/89 = 0.9775
doc_mrr:         0.7984
doc_ndcg@10:     0.8320
```

This Task 3.2 winner is now the **embedding benchmark control**.

The old row-0 Phase 1 architecture remains historically frozen:

```text
fixed 512/0
BAAI/bge-small-en-v1.5
doc_recall@10 = 82/89 = 0.921348
doc_recall@50 = 85/89 = 0.955056
doc_mrr       = 0.805056
doc_ndcg@10   = 0.833208
```

Do not overwrite row 0.

Do not compare new embedding candidates by silently changing chunking back
to 512 tokens.

All Task 3.3 candidate models must use the exact frozen 256/0/fixed chunks.

---

# Critical evaluation-scope rule

Every Task 3.3 candidate must be evaluated on the exact same frozen
Task 3.1 DEV/evaluable subset:

```text
question count: 89
```

Use the already-frozen question-ID artifact/hash.

Do not:

- regenerate the 89 IDs;
- recompute corpus coverage;
- add newly coverable questions;
- remove difficult questions;
- use a different subset for different models;
- use FinanceBench for model selection;
- use protected TEST.

If the scope hash or exact question IDs cannot be reproduced, STOP.

---

# Protected TEST discipline

Throughout Task 3.3:

```text
protected SEC TEST opened:       NO
official SEC TEST runs consumed: 0/3
```

No routine experiment may load TEST.

Do not inspect TEST question IDs, payloads, or failures.

Do not write fake TEST-access records for DEV experiments.

---

# Experimental principle

Change **one variable only: the embedding model**.

Freeze across every formal candidate:

```text
source corpus
normalized corpus
frozen 256/0/fixed chunk artifact
chunk_config_hash
89-question DEV scope
exact same document distractor corpus
vector-search backend
exact-search semantics
distance/ranking policy
candidate retrieval depth = 50
metric implementations
metric applicability
generation = disabled
BM25 = disabled
reranker = disabled
CRAG = disabled
router = disabled
metadata pre-filtering = disabled
```

Model-specific query/passage formatting that is explicitly required by a
model's own documented retrieval contract is part of the embedding model
choice and may vary by model. It must be frozen and recorded.

Do not use one model's query prefix with another model.

---

# Git / branch policy

Create a dedicated Phase 3 experiment branch:

```text
ablation/embedding-models
```

Before branching:

```powershell
git status
git branch --show-current
git log -1 --oneline
```

Task 3.2 must already be committed/integrated according to repository
convention.

If unrelated working-tree changes exist, STOP.

No Phase 3 completion tag.

---

# Stage 1/10 — Preflight

Print:

```text
[STAGE 1/10] Task 3.3 preflight
```

Verify:

1. Task 3.2 status = COMPLETE.
2. Task 3.3 is the current next roadmap task.
3. Task 3.2 winning `chunk_config_hash` matches:
   `ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06`.
4. The selected 256/0 chunk artifact exists and is complete.
5. Chunk count matches the real Task 3.2 result.
6. The 89-question DEV scope reproduces exactly.
7. Task 3.2 control metrics reproduce from stored results.
8. Row 0 remains frozen and unchanged.
9. Protected TEST remains unopened.
10. Official TEST budget remains 0/3.
11. No paid API is needed for embedding evaluation.
12. GPU/CUDA is available as expected.
13. Disk free space is sufficient for candidate embeddings/indexes.
14. Task 2.10 canonical hashing remains available.
15. Task 2.11 run logging remains available.

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Record exact pre-task counts.

---

# Stage 2/10 — Freeze the candidate model grid

Print:

```text
[STAGE 2/10] Freeze embedding candidate grid
```

Read the CURRENT Task 3.3 section in `PROJECT_EXECUTION.md`.

### Rule A — roadmap names models

If it names candidate models, benchmark exactly those plus the existing
control model if the control is not already listed.

### Rule B — roadmap describes classes but does not name exact repositories

Resolve exact Hugging Face repositories only from the roadmap's stated
intent and current project constraints.

Before committing to a full build, print a candidate table containing:

```text
candidate_id
repository
resolved revision
model family
parameter count if documented
embedding dimension
max sequence length
recommended similarity metric
query instruction/prefix
passage instruction/prefix
recommended normalization
trust_remote_code requirement
license
estimated model download size
expected GPU compatibility
```

If any exact repository choice remains subjective, STOP and ask instead of
silently choosing a leaderboard winner.

### Required control

The existing Task 3.2 control must be present:

```text
BAAI/bge-small-en-v1.5
```

Reuse its already-completed 256/0 embeddings/index/result if artifact
identity checks pass.

Do not rebuild it merely for symmetry.

### Model provenance

For every new model:

- pin exact repository;
- resolve and freeze exact immutable revision/commit;
- record tokenizer revision if separately relevant;
- record SentenceTransformers / Transformers versions;
- record whether custom code is required;
- record license text/identifier from authoritative local/model metadata;
- never use `revision="main"` as the final formal identity.

If a model requires `trust_remote_code=True`, flag it prominently before
execution and inspect what the repository currently allows.

Do not enable remote code silently.

---

# Stage 3/10 — Model-contract audit

Print:

```text
[STAGE 3/10] Audit embedding contracts
```

For each candidate, inspect its own model card/config rather than assuming
BGE semantics.

Record:

```text
max sequence length
embedding dimension
pooling strategy
query encoding convention
passage encoding convention
normalization convention
similarity convention
special-token behavior
```

The frozen chunks are 256 content tokens, so all formal candidates should
be able to encode the full chunk without semantic truncation.

Verify this empirically where practical.

If any candidate cannot encode the full 256-token chunk under its required
special-token budget:

- do not change chunking;
- do not silently truncate;
- record the incompatibility;
- STOP that candidate and report it as incompatible with the frozen Task
  3.2 chunking contract.

### Retrieval metric policy

Task 3.3 must keep the retrieval layer comparable.

Use exact cosine search for formal comparison unless the CURRENT roadmap
explicitly specifies another frozen policy.

For models whose recommended retrieval convention uses normalized vectors,
store normalized float32 vectors.

If a model's official retrieval contract materially requires a similarity
policy incompatible with the frozen exact-cosine comparison, STOP and
report the conflict instead of changing the retrieval backend for only that
candidate.

---

# Stage 4/10 — Freeze Task 3.3 experiment config

Print:

```text
[STAGE 4/10] Freeze embedding benchmark config
```

Create a tracked config such as:

```text
configs/phase_3_3_embedding_model_benchmark.json
```

Hash it using Task 2.10 canonical `semantic_hash()`.

Do not create a new hashing implementation.

The config must include at least:

```text
task
experiment_version

baseline_row_id
task32_winner_row_id
task32_result_identity

eval_split
eval_scope_kind
eval_scope_sha256
question_count
question_ids_sha256

chunk_config_hash
split_mode
window_size_tokens
overlap_tokens

candidate_models:
  candidate_id
  repository
  revision
  dimension
  max_seq_length
  query_convention
  passage_convention
  normalize_embeddings
  vector_dtype
  similarity_metric

retrieval_backend
search_mode
candidate_k

metric_schema_version
metric definitions

winner_selection_policy
bootstrap_seed
bootstrap_iterations
```

Freeze the full candidate list and winner-selection policy **before**
seeing new candidate results.

If the candidate list changes after a formal run begins, create a new
experiment version rather than rewriting history.

---

# Stage 5/10 — Generalize embedding support cleanly

Print:

```text
[STAGE 5/10] Generalize embedding model adapter
```

Do not duplicate one embedding pipeline per model.

Refactor toward a small model-spec / adapter boundary while preserving the
existing BGE behavior exactly.

A reasonable design may expose concepts like:

```text
EmbeddingModelSpec
load_embedding_model(spec)
encode_passages(spec, ...)
encode_queries(spec, ...)
embedding_identity(spec)
```

The exact API may differ if the repository already has a better pattern.

Requirements:

- BGE-small's existing behavior must remain regression-tested;
- query/passages must remain separate code paths;
- model-specific prefixes/instructions must be explicit;
- vector dtype = float32 for formal artifacts unless roadmap says otherwise;
- no silent CPU fallback;
- GPU OOM handling may reduce batch size and retry;
- every actual batch size used must be recorded;
- do not alter chunk text;
- do not alter chunk metadata;
- no network inside portable tests.

Do not couple Task 3.3 to generation or LLM provider code.

---

# Stage 6/10 — Pilot each new model before full embedding

Print:

```text
[STAGE 6/10] Candidate pilot
```

Before embedding all ~324K frozen 256-token chunks for a new candidate:

1. load the model;
2. encode a deterministic small passage sample;
3. encode a deterministic small query sample;
4. verify dimension;
5. verify dtype;
6. verify finiteness;
7. verify normalization when required;
8. verify query/passages differ where the model contract expects that;
9. verify full 256-token chunks are not unexpectedly truncated;
10. run a tiny exact-cosine retrieval smoke;
11. measure peak VRAM;
12. measure pilot throughput;
13. estimate full build time;
14. estimate output artifact size.

If projected VRAM exceeds the RTX 5060 Laptop GPU's usable capacity:

- reduce batch size;
- retry;
- record the effective batch size.

Do not switch precision/dtype/model architecture silently.

If a model cannot run reliably on this machine under a defensible batch
size, mark it `INCOMPATIBLE_LOCAL_GPU` and preserve that as a real negative
result.

Do not substitute another model automatically.

---

# Stage 7/10 — Build embeddings and exact indexes

Print:

```text
[STAGE 7/10] Build candidate embeddings and indexes
```

For every compatible candidate:

```text
frozen Task 3.2 chunks
    -> candidate passage embeddings
    -> candidate exact LanceDB cosine table
```

Use separate artifact identities.

Never overwrite Task 3.2's BGE-small artifact.

Suggested storage pattern should remain compatible with existing
`StoragePaths` conventions:

```text
artifacts/embeddings/<chunk_config_hash>/<model_key>/
artifacts/indexes/<chunk_config_hash>/<model_key>/
```

### Required embedding artifact validation

For every candidate:

```text
input chunk count == output vector count
unique chunk IDs unchanged
metadata equality exact
dimension correct
dtype correct
all values finite
normalization correct when frozen
model identity present
chunk_config_hash correct
```

### Required index validation

For every candidate:

```text
table row count == embedding row count
0 ANN indexes
cosine metric explicit
self-retrieval smoke passes
stored vectors match source sample
metadata traceability passes
```

### Resumability

Full candidate embedding builds may take a long time.

Reuse the resumable shard/checkpoint pattern already proven in Task 3.2
where practical.

Requirements:

- atomic shard writes;
- config/model identity stored in checkpoint;
- resume refuses mismatched model/chunk/config identity;
- completed shards are never silently recomputed;
- corrupted/incomplete shards are rejected;
- visible foreground progress.

Do not let a machine sleep/interruption destroy a multi-hour candidate run.

---

# Stage 8/10 — Evaluate all candidates on the frozen 89 questions

Print:

```text
[STAGE 8/10] Evaluate embedding candidates
```

For each candidate:

- encode queries with that candidate's frozen query convention;
- retrieve exact top 50;
- use the same 89 questions;
- use the same document-level relevance semantics fixed in Task 3.1;
- generation remains disabled.

Required metrics:

```text
doc_recall@10
doc_recall@50
doc_mrr
doc_ndcg@10
```

Also record raw counts:

```text
hits@10 / 89
hits@50 / 89
misses@10
misses@50
```

Store per-question diagnostic records under git-ignored artifacts:

```text
question_id
gold_document_ids
ranked chunk_ids 1..50
ranked document_ids 1..50
first gold-document hit rank
hit@10
hit@50
reciprocal_rank
ndcg@10
query_embedding_ms
vector_search_ms
total_retrieval_ms
```

Do not infer chunk-level gold.

Keep:

```text
chunk_recall@10 = N/A
chunk_mrr       = N/A
citation_grounding = N/A
faithfulness = N/A
generation metrics = N/A
```

unless a later authoritative task has explicitly changed their status.

N/A is never zero.

Every formal run must create a Task 2.11 run record.

---

# Stage 9/10 — Paired analysis and winner selection

Print:

```text
[STAGE 9/10] Compare and select embedding model
```

Compare every candidate against the Task 3.2 BGE-small control using the
same 89 question IDs.

Report:

```text
delta doc_recall@10
delta doc_recall@50
delta doc_mrr
delta doc_ndcg@10

hit@10:
  gained
  lost
  unchanged

hit@50:
  gained
  lost
  unchanged

first-hit rank:
  improved
  worsened
  unchanged
```

Use the already-established paired bootstrap convention unless the current
roadmap specifies otherwise:

```text
seed:        42
iterations:  10,000
unit:        question_id
```

Report 95% paired bootstrap intervals for:

```text
delta doc_recall@10
delta doc_recall@50
delta doc_mrr
delta doc_ndcg@10
```

Do not claim tiny differences on N=89 are definitive.

### Cost/performance comparison

For each model record:

```text
model parameter count if known
embedding dimension
model artifact size
embedding artifact size
index size
model load time
passage embedding throughput
query embedding p50/p95
exact search p50/p95
total retrieval p50/p95
peak GPU allocated
peak GPU reserved
full corpus embedding build time
effective batch size(s)
```

### Winner-selection rule

First, use any exact rule in the CURRENT `PROJECT_EXECUTION.md`.

If the roadmap does not define a more specific rule, use the same Phase 3
quality-first logic already frozen in Task 3.2:

1. `doc_recall@50`
2. `doc_mrr`
3. `doc_ndcg@10`
4. `doc_recall@10`

Treat candidates as practically tied when:

- Recall@50 differs by at most 1 question out of 89;
- MRR delta 95% paired-bootstrap CI includes 0;
- nDCG@10 delta 95% paired-bootstrap CI includes 0.

For practically tied quality, prefer:

1. lower embedding dimension / smaller index;
2. faster passage embedding throughput;
3. lower query-embedding latency;
4. lower retrieval p95;
5. lower VRAM;
6. smaller model artifact;
7. simpler / more standard model integration.

Do not pick a larger model merely because it is newer.

Do not pick a cheaper model if it has a clear quality regression.

If the quality-vs-cost tradeoff is genuinely unresolved by the frozen rule,
STOP and show the comparison for user decision.

A negative result where `BAAI/bge-small-en-v1.5` remains the winner is valid.

---

# Stage 10/10 — Results, ablation table, tests, docs, Git

Print:

```text
[STAGE 10/10] Verify and close Task 3.3
```

## Ablation table

Preserve row 0 exactly.

Preserve every Task 3.2 row exactly.

Append one row per formally evaluated Task 3.3 embedding configuration.

Each row should retain at least:

```text
row_id
task
configuration
status
run_id
git_sha
phase3_config_hash

eval_split
eval_scope_sha256
question_count

chunk_config_hash
split_mode
window_size_tokens
overlap_tokens

embedding_model
embedding_revision
embedding_dimension
embedding_identity
normalize_embeddings
query_convention
passage_convention

retrieval
candidate_k

doc_recall_at_10
doc_recall_at_10_hits
doc_recall_at_50
doc_recall_at_50_hits
doc_mrr
doc_ndcg_at_10

delta_vs_task32_control_recall10
delta_vs_task32_control_recall50
delta_vs_task32_control_mrr
delta_vs_task32_control_ndcg10

model_load_ms
passage_embedding_throughput
query_embedding_latency_p50_ms
query_embedding_latency_p95_ms
search_latency_p50_ms
search_latency_p95_ms
retrieval_latency_p50_ms
retrieval_latency_p95_ms

embedding_artifact_size_bytes
index_size_bytes
peak_gpu_allocated_bytes

winner
notes
```

Do not rewrite old rows to fit a new story.

## Result artifact

Create:

```text
results/phase_3_3_embedding_model_benchmark.json
```

Include:

- experiment config hash;
- frozen 89-question scope identity;
- Task 3.2 chunk winner identity;
- all candidate model identities;
- model contracts;
- build statistics;
- evaluation metrics;
- raw hit counts;
- paired deltas;
- bootstrap intervals;
- resource/latency comparison;
- excluded/incompatible candidates;
- final selected model;
- explicit rationale;
- limitations.

## Documentation

Update:

```text
project_plan/PHASE3_EMBEDDING_MODEL_BENCHMARK.md
project_plan/REPOSITORY_STRUCTURE.md   # only where required
Progress.md
```

Progress must clearly state:

- candidate list;
- exact revisions;
- model-specific query/passage conventions;
- same 256/0 chunks for every model;
- same 89 DEV questions for every model;
- quality metrics and raw counts;
- paired intervals;
- throughput/latency/VRAM/index-size effects;
- final selected embedding model;
- why it won;
- negative/incompatible results;
- protected TEST status;
- exact test counts;
- Git outcome;
- next roadmap task from the current `PROJECT_EXECUTION.md`.

## Required tests

Add deterministic tests covering at least:

1. Task 3.2 winner hash is required.
2. 256/0/fixed chunks cannot change.
3. exact 89-question scope cannot change.
4. candidate config hash determinism.
5. candidate config hash changes on model/revision change.
6. model revisions must be immutable/frozen.
7. BGE-small legacy query convention regression.
8. BGE-small legacy passage convention regression.
9. model-specific query/passages are not accidentally swapped.
10. candidate dimension validation.
11. candidate finite-vector validation.
12. normalization validation.
13. no silent CPU fallback.
14. OOM retry reduces batch size deterministically.
15. resume rejects different model identity.
16. resume rejects different chunk hash.
17. atomic checkpoint/shard behavior.
18. exact-cosine search remains exact.
19. zero ANN indexes.
20. candidate_k is exactly 50.
21. document relevance deduplication is preserved.
22. doc_recall@10 correctness.
23. doc_recall@50 correctness.
24. doc_mrr correctness.
25. doc_ndcg@10 correctness.
26. paired delta correctness.
27. deterministic bootstrap seed 42.
28. N/A stays distinct from 0.
29. generation remains disabled.
30. BM25/reranker/router/CRAG absent.
31. TEST split rejected.
32. protected TEST access module not imported.
33. Task 2.11 DEV run provenance is complete.
34. row 0 cannot be overwritten.
35. Task 3.2 rows cannot be silently rewritten.
36. candidate rows retain model + revision + chunk hash + run_id + git SHA.
37. portable tests never download models or call APIs.
38. prior Phase 1/2/3.1/3.2 result artifacts remain unchanged.

Use tiny synthetic fixtures for portable tests.

Do not perform full embedding builds inside pytest.

Model/GPU integration tests should be marked appropriately and skip only
when the established environment policy allows a real missing capability.

## Verification

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Report exact counts.

## Git safety

Before staging:

```powershell
git status
git diff --stat
git add -n <specific files>
```

Secret-scan and large-file-scan the staged set.

Never commit:

```text
data/
artifacts/
*.duckdb
*.parquet
*.lance/
embedding vectors
indexes
model weights
HF caches
.env
API keys
large logs
```

Commit only small source/config/test/result/doc artifacts.

Suggested coherent commit names:

```text
Add Phase 3 embedding benchmark harness
Benchmark Phase 3 embedding candidates
Select Phase 3 embedding model
```

Use real working history; do not manufacture fake granular commits after
the fact.

No Phase 3 completion tag.

---

# Visible progress requirements

All long operations must remain visible in the foreground.

Examples:

```text
[MODEL bge-small] REUSE verified Task 3.2 control artifacts

[MODEL candidate-x] loading...
[MODEL candidate-x] pilot PASS dim=... batch=... peak_vram=...

[EMBED candidate-x]  32768/323971  10.1%  ... chunks/s  ETA ...
[EMBED candidate-x]  65536/323971  20.2%  ... chunks/s  ETA ...

[INDEX candidate-x]  building exact cosine table...

[EVAL candidate-x]   10/89  11.2%  hits@10=... hits@50=...
[EVAL candidate-x]   20/89  22.5%  hits@10=... hits@50=...
```

Use unbuffered / flush-safe output.

Do not detach formal runs into the background.

Do not redirect progress only to a hidden log.

If resumability exists, provide read-only status output that does not mutate
artifacts or call models.

---

# Suggested CLI shape

Reuse Task 3.2 orchestration patterns where cleanly possible.

A reasonable interface is:

```powershell
python -u scripts/run_phase3_embedding_benchmark.py --plan
python -u scripts/run_phase3_embedding_benchmark.py --run --resume
python -u scripts/run_phase3_embedding_benchmark.py --status
python -u scripts/run_phase3_embedding_benchmark.py --compare
```

This is guidance, not a requirement to create a redundant script if the
repository has a cleaner established interface.

---

# Formal completion display

At completion print:

```text
PHASE 3 — TASK 3.3 EMBEDDING MODEL BENCHMARK
============================================

Evaluation:
  split:                         DEV
  scope:                         frozen Task 3.1 evaluable subset
  questions:                     89
  scope_sha256:                  ...

Frozen chunking:
  split_mode:                    fixed
  window_size_tokens:            256
  overlap_tokens:                0
  chunk_config_hash:             ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06

Frozen retrieval:
  exact cosine:                  YES
  candidate depth:               50
  BM25:                          NO
  reranker:                      NO
  CRAG/router:                   NO
  generation:                    OFF

Candidates:
---------------------------------------------------------------------------
Model                 Dim    R@10      R@50      MRR       nDCG@10
BAAI/bge-small...     384    83/89     87/89     0.7984    0.8320
<model 2>             ...    ...       ...       ...       ...
<model 3>             ...    ...       ...       ...       ...

Resource comparison:
---------------------------------------------------------------------------
Model                 Build time   Chunks/s   Index size   Query p50   VRAM
...

Final winner:
  model:                         ...
  revision:                      ...
  embedding dimension:           ...
  embedding identity:            ...
  query convention:              ...
  passage convention:            ...
  normalize_embeddings:          ...

Paired vs BGE-small Task 3.2 control:
  R@10 delta:                    ...
  R@50 delta:                    ...
  MRR delta:                     ...
  nDCG@10 delta:                 ...
  gained/lost @10:               ... / ...
  gained/lost @50:               ... / ...
  95% paired bootstrap intervals: ...

Ablation table:
  row 0:                         UNCHANGED
  Task 3.2 rows:                 UNCHANGED
  Task 3.3 rows appended:        ...
  selected embedding model:      FROZEN FOR NEXT TASK

Protected TEST:
  opened:                        NO
  official runs used:            0/3

FinanceBench:
  rerun for tuning:              NO

Paid embedding/generation APIs:
  0

Tests:
  doctor:                        ...
  portable:                      ...
  full:                          ...

Git:
  experiment branch:             ablation/embedding-models
  commits:                       ...
  integration outcome:           ...
  push:                          ...
  Phase 3 tag:                   NOT CREATED

TASK 3.3 STATUS:
  COMPLETE

PHASE 3 STATUS:
  IN PROGRESS

NEXT:
  <exact next roadmap task from current PROJECT_EXECUTION.md>
```

Then STOP.

Do not implement the next task automatically.

---

# Hard stop conditions

STOP and report rather than guessing if:

1. Task 3.2 is not actually complete.
2. Task 3.2 winner hash differs from the recorded frozen identity.
3. the selected 256/0 chunk artifact is missing/incomplete.
4. the 89-question scope cannot be reproduced exactly.
5. row 0 or Task 3.2 result rows changed unexpectedly.
6. the current roadmap names a candidate model list that conflicts with
   the planned benchmark.
7. exact model repository selection is ambiguous.
8. a candidate revision cannot be frozen immutably.
9. a model requires unapproved `trust_remote_code=True`.
10. a candidate cannot encode the full frozen 256-token chunks.
11. a candidate requires changing chunking.
12. a candidate requires changing the evaluation question set.
13. a candidate requires BM25/reranking/hybrid retrieval.
14. a candidate requires changing from the frozen exact-cosine comparison
    without an authoritative roadmap rule.
15. TEST would need to be opened.
16. an official TEST run would be consumed.
17. FinanceBench is proposed as the routine tuning set.
18. generation is proposed for the formal embedding benchmark.
19. chunk-level metrics are proposed without chunk gold.
20. a paid embedding API is proposed without explicit user approval.
21. local GPU cannot run a candidate reliably even at a defensible batch
    size.
22. model artifact download/license requirements are unclear.
23. experiment candidate list changes after formal results are seen without
    a versioned new experiment.
24. a new hashing implementation duplicates Task 2.10.
25. a new run-log format duplicates Task 2.11.
26. row 0 would be overwritten.
27. Task 3.2 rows would be rewritten.
28. prior Phase 1/2/3.1/3.2 frozen results change unexpectedly.
29. generated embeddings/index/model weights are about to be committed.
30. a secret/API key is about to be committed.
31. final winner depends on an unresolved quality/cost tradeoff outside the
    frozen selection rule.

---

# Success criteria

Task 3.3 is complete only when:

- Task 3.2's 256/0/fixed chunking remains frozen;
- every formal model uses the same exact chunk artifact;
- every formal model uses the same exact 89 DEV questions;
- the roadmap-defined candidate model set is benchmarked;
- exact revisions and model contracts are frozen;
- model-specific query/passage instructions are handled correctly;
- embeddings/indexes are validated and versioned;
- exact top-50 retrieval is used consistently;
- R@10, R@50, MRR, and nDCG@10 are recorded with raw hit counts;
- paired per-question deltas and uncertainty are reported;
- throughput, latency, index size, model size, and VRAM are measured;
- incompatible models are preserved as honest negative results;
- one embedding model is selected with a pre-frozen rule;
- row 0 remains unchanged;
- Task 3.2 rows remain unchanged;
- new Task 3.3 rows are appended;
- selected embedding model is frozen for the next Phase 3 task;
- TEST remains unopened at 0/3;
- no paid embedding/generation API is used;
- all regression tests pass;
- Task 3.3 is documented and committed;
- the next roadmap task has **not** started.
