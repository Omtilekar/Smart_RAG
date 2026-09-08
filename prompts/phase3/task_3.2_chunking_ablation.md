# Phase 3 — Task 3.2: Chunking Ablation

## Objective

Run a controlled **DEV-only chunking ablation** and select the Phase 3
chunking strategy before Task 3.3 changes the embedding model.

This task implements exactly the intent of
`project_plan/PROJECT_EXECUTION.md` Task 3.2:

- benchmark 256-token chunks;
- benchmark the existing 512-token baseline;
- benchmark 1024-token chunks;
- benchmark selected overlap values;
- compare fixed-window vs section-aware splitting;
- measure retrieval quality **and** index/build implications;
- select one winning chunking strategy before moving to the embedding-model
  benchmark.

This is a **chunking-only** experiment.

Do not add BM25, hybrid fusion, reranking, CRAG, routing, metadata
pre-filtering, SQL retrieval, graph retrieval, generation changes, or a new
embedding model.

Do not start Task 3.3 in this task.

---

# Authoritative sources and precedence

Before writing code, re-read the current repository state in this order:

1. `project_plan/PROJECT_EXECUTION.md`
2. `Progress.md`
3. `project_plan/GIT_CONVENTIONS.md`
4. `project_plan/PHASE3_TRUSTED_BASELINE.md`
5. `results/phase_3_1_trusted_baseline.json`
6. `results/phase_3_ablation_table.csv`
7. `configs/phase_3_1_trusted_baseline.json`
8. Task 2.9 chunk-schema documentation/code
9. Task 2.10 hashing/versioning code
10. Task 2.11 run-logging code
11. Phase 1 normalization/chunking/embedding/index/retrieval modules
12. current tests for all of the above

Local repository truth wins over any stale descriptive value in this prompt.

STOP on a material contradiction rather than silently resolving it.

---

# Expected Phase 3 entry state

Task 3.1 should already be COMPLETE and row 0 should be frozen.

Expected trusted row-0 result from the most recent project state:

```text
evaluation split:        DEV
evaluation scope:        frozen DEV/evaluable-subset
question count:          89

doc_recall@10:           0.921348  (82/89)
doc_recall@50:           0.955056  (85/89)
doc_mrr:                 0.805056
doc_ndcg@10:             0.833208

baseline architecture:
  chunking:              fixed 512 tokens
  overlap:               0
  embedding:             BAAI/bge-small-en-v1.5
  retrieval:             vector-only exact cosine
  BM25:                  NO
  reranker:              NO
  CRAG:                  NO
  router:                NO
  generation:            disabled for formal retrieval ablation

Task 3.1 run_id:
  28547fec-af47-43f4-b995-e02af858b20d

Task 3.1 phase3_config_hash:
  18acae71fab0e7ffa4209da2530f26904cecc9dcb9b2c5e32cd791e5fd4a26e4
```

Do not trust these values blindly. Re-read the real result/config/ablation
table and verify them.

If they differ materially, STOP and show the repository values.

The old Phase 1 200-question smoke result `doc_recall@10=0.970000` is
historical and must NOT be used as the Phase 3 comparison baseline.

---

# Critical evaluation-scope rule

Task 3.1 found that the 1,500-filing Phase 1 corpus covers only a small
fraction of the full retrieval-applicable Phase 2 DEV set.

The user selected the **fixed evaluable-subset policy**.

Therefore every Task 3.2 configuration must be evaluated on the **exact same
89 frozen question IDs** used by row 0.

This is non-negotiable.

Do not:

- regenerate the 89 IDs;
- recalculate a new intersection per chunk configuration;
- remove questions that a candidate performs badly on;
- add newly coverable questions;
- use FinanceBench as the tuning set;
- use TEST;
- treat out-of-scope DEV questions as retrieval misses.

Load the Task 3.1 frozen scope artifact/hash and verify the exact question-ID
set before every formal candidate run.

If the 89-question scope cannot be reproduced byte-for-byte / hash-for-hash,
STOP.

---

# Protected TEST discipline

Routine Phase 3 optimization is DEV-only.

Throughout Task 3.2:

```text
protected TEST payload opened: NO
official TEST runs consumed:   0/3
```

Do not load the protected TEST question file even for a "sanity check."

Do not write a TEST-access record for a DEV run.

Do not inspect individual TEST failures.

---

# Experimental principle

Change **one chunking dimension at a time** while freezing everything else.

Frozen across all configurations:

```text
normalized source corpus
development corpus / distractor corpus
89-question Phase 3 DEV scope
embedding model + revision
query/passage conventions
embedding normalization
vector dtype
vector-search backend
distance metric
exact-search semantics
candidate retrieval depth
metric implementations
metric applicability rules
evaluation schema
generation-disabled policy
```

Only chunking may change.

---

# Branching / Git policy

`project_plan/GIT_CONVENTIONS.md` requires Phase 3 ablations to use branches.

Create one experiment branch for this controlled Task 3.2 study:

```text
ablation/chunking
```

This entire Task 3.2 grid is one scientific experiment, so one branch is
sufficient unless the existing Git conventions explicitly require a
different branch structure.

Do not run Task 3.2 directly as unreviewed optimization work on `main`.

Before branching:

```powershell
git status
git branch --show-current
git log -1 --oneline
```

The Task 3.1 result must already be committed.

If the working tree contains unrelated changes, STOP and report them.

At the end:

- preserve the ablation measurements even if the Phase 1 512/0 baseline wins;
- retain only the selected production chunking strategy as the active
  Phase 3 choice;
- do not silently keep an inferior component because it was expensive to
  build;
- merge/cherry-pick results and selected implementation according to the
  current Git convention;
- do not create a Phase 3 completion tag.

---

# Stage 1/10 — Preflight and immutable-baseline verification

Print:

```text
[STAGE 1/10] Task 3.2 preflight
```

Verify:

1. Task 3.1 status is COMPLETE.
2. Phase 3 status is IN PROGRESS.
3. Task 3.2 is the next roadmap task.
4. row 0 exists exactly once.
5. row 0 is immutable/frozen.
6. row 0 points to a real Task 2.11 run.
7. row 0 question count is 89.
8. the frozen 89 question IDs and scope hash reproduce.
9. `doc_recall@10`, `doc_recall@50`, `doc_mrr`, and `doc_ndcg@10`
   reproduce from the stored row-0 per-query output or stored summary.
10. protected TEST remains unopened.
11. official TEST budget remains 0/3.
12. no paid generation is required.
13. Phase 1 normalized artifacts are available.
14. baseline BGE model is cached/available.
15. the existing exact-cosine vector index is readable.
16. baseline chunk-config identity is intact.
17. Task 2.10 canonical hashing is intact.
18. Task 2.11 run logging is intact.

Run before implementation:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Record exact counts.

---

# Stage 2/10 — Inspect the encoder length constraint

Print:

```text
[STAGE 2/10] Encoder-length compatibility audit
```

This is important because `PROJECT_EXECUTION.md` explicitly asks Task 3.2
to test **1024-token chunks**, while the frozen embedding model may have a
shorter maximum sequence length.

Inspect the actual installed/cached:

```text
BAAI/bge-small-en-v1.5
```

Record:

```text
model revision
tokenizer model_max_length
SentenceTransformer max_seq_length
actual passage truncation behavior
```

Do not assume.

If the effective passage-embedding limit is 512 tokens, do **not** change the
embedding model in Task 3.2.

Instead:

- still include the 1024-token chunk configuration because the roadmap asks
  for it;
- label it explicitly as something like:

```text
fixed_1024_overlap_0_encoder_truncates_at_512
```

- record that only the encoder-visible prefix contributes to the vector if
  that is the real behavior;
- preserve the full 1024-token chunk text in retrieval output;
- treat this as a real diagnostic of how 1024-token chunks behave under the
  frozen Phase 1 encoder;
- do not claim it is a lossless 1024-token embedding experiment;
- do not switch to a long-context embedding model to "make the test fair" —
  embedding-model changes belong to Task 3.3.

If current BGE configuration can actually embed all 1024 tokens without
truncation, record that instead.

Add a regression test proving the recorded length policy matches actual
model configuration where practical.

---

# Stage 3/10 — Freeze the controlled ablation grid

Print:

```text
[STAGE 3/10] Freeze chunking experiment grid
```

Use a staged grid to avoid an unnecessary combinatorial explosion.

## Round A — Window-size ablation, zero overlap

Required:

```text
A0  fixed 512 tokens, overlap 0   # existing row 0; reuse, do not rebuild
A1  fixed 256 tokens, overlap 0
A2  fixed 1024 tokens, overlap 0
```

A0 is the trusted baseline.

Do not rebuild A0 unless an integrity check proves its artifacts are corrupt.

## Round B — Overlap ablation on the best fixed window

After Round A metrics are complete, select the best fixed-window size using
the frozen decision rule later in this prompt.

Then compare:

```text
B0  winner window, overlap 0       # reuse Round A winner
B1  winner window, overlap 12.5%
B2  winner window, overlap 25%
```

Convert percentages deterministically to token counts:

```text
256  -> 32, 64
512  -> 64, 128
1024 -> 128, 256
```

The overlap implementation must be:

```text
stride = window_size - overlap_tokens
```

with the existing partial-final-window policy preserved.

Do not introduce a different overlap definition.

## Round C — Fixed vs section-aware

Take the winning window+overlap policy from Rounds A/B and compare:

```text
C0  fixed-window winner
C1  section-aware winner-window/overlap
```

For Task 3.2, define **section-aware** conservatively:

- use the already-normalized SEC Item headings / section boundaries;
- never allow a chunk to cross a filing Item boundary;
- within each section use the same tokenizer, window size, overlap, and
  final-partial-window policy as C0;
- do not use an LLM;
- do not reconstruct tables;
- do not rewrite text;
- do not inject summaries;
- do not prepend duplicated section titles to every continuation chunk
  unless the repository already has a frozen rule requiring that behavior;
- the primary goal is to isolate the effect of respecting section
  boundaries.

If the normalized representation cannot expose section boundaries
deterministically without changing normalization, STOP and report the issue.

## Freeze before expensive runs

Write the full staged experiment plan to a tracked config before launching
the first new embedding build, for example:

```text
configs/phase_3_2_chunking_ablation.json
```

Hash it with Task 2.10 canonical hashing.

The config should include:

```text
task
experiment_version
baseline_row_id
baseline_run_id
phase3_scope_hash
question_ids_hash
eval_set_version
split
question_count

normalizer identity
source corpus identity

embedding model
embedding revision
embedding max sequence length
embedding normalization
query convention
passage convention
vector dtype

retrieval backend
distance metric
candidate_k

round_a candidates
round_b policy
round_c policy

metric definitions
winner-selection policy
bootstrap seed
bootstrap iterations
```

No post-hoc grid edits after seeing results.

If the grid must change, version the experiment and preserve the prior
results rather than overwriting them.

---

# Stage 4/10 — Generalize chunking without breaking the baseline

Print:

```text
[STAGE 4/10] Implement experimental chunking configurations
```

Reuse the existing Task 1.3 chunking logic rather than writing unrelated
chunkers from scratch.

Refactor only as much as required to parameterize:

```text
window_size_tokens
overlap_tokens
split_mode = fixed | section_aware
```

Preserve existing deterministic text-slicing behavior.

For fixed-window candidates:

- same tokenizer family/revision as the frozen baseline chunker;
- `add_special_tokens=False`, unless repository truth says otherwise;
- full source-body coverage;
- deterministic ordinal order;
- deterministic chunk IDs/UIDs;
- partial last window retained;
- zero source-document loss;
- 7 historically empty Phase 1 documents remain handled according to the
  frozen policy;
- no content rewriting.

For overlap:

- overlapping text is expected by design;
- no gaps in token coverage;
- no duplicate *window start* positions;
- final window must not be emitted twice;
- overlap count must match config exactly.

For section-aware:

- no chunk crosses a section boundary;
- no source section silently disappears;
- section identity must be preserved where the current metadata schema
  supports it;
- do not fabricate section metadata.

## Metadata/schema

Re-read Task 2.9 and Task 3.1 before choosing the emitted schema.

Do not invent a new third chunk schema.

New Phase 3 artifacts must remain compatible with the current canonical
metadata/evaluation contracts.

Do not modify historical Phase 1 chunk artifacts in place.

Do not overwrite the row-0 chunk artifact.

Every candidate must receive its own content/config identity.

Use Task 2.10's canonical hash utility for the chunk configuration.

---

# Stage 5/10 — Build candidate chunks, embeddings, and exact indexes

Print:

```text
[STAGE 5/10] Build candidate artifacts
```

For every new candidate configuration:

```text
normalized corpus
    -> candidate chunks
    -> BGE passage embeddings
    -> exact LanceDB cosine table
```

Freeze everything except chunking.

## Embedding model

For every candidate use the same row-0 embedding model/revision:

```text
BAAI/bge-small-en-v1.5
```

Preserve:

- passage convention;
- query convention;
- `normalize_embeddings` policy;
- vector dtype;
- GPU/device policy;
- deterministic ordering;
- OOM handling policy already established by Phase 1.

Do not benchmark `bge-base`, Nomic, Qwen embeddings, commercial embeddings,
or anything else in Task 3.2.

That is Task 3.3.

## Index

Use the same Phase 1 exact-cosine vector-search semantics:

- LanceDB;
- no ANN index;
- no IVF_PQ;
- no binary quantization;
- no BM25/FTS;
- no reranker;
- no RRF;
- same distance metric;
- same retrieval result ordering contract.

Task 0.10 serving-spike indexes are unrelated feasibility artifacts and
must not replace the Task 3.2 exact-search evaluation index.

## Build measurements

For each configuration record:

```text
document_count
chunk_count
chunks_per_document:
  min
  median
  p95
  max

token_count_per_chunk:
  min
  median
  p95
  max

total_emitted_tokens
duplication_factor_due_to_overlap

chunk_artifact_size_bytes
embedding_artifact_size_bytes
index_size_bytes

chunk_build_seconds
embedding_build_seconds
embedding_chunks_per_second
index_build_seconds

peak_GPU_memory_if_already_available
```

Do not compare raw chunk counts without also reporting overlap duplication.

## Resumability

New embedding builds may take substantial time.

Reuse existing resumability/checkpoint conventions if available.

Do not discard a completed candidate because the next candidate fails.

Artifacts remain git-ignored.

---

# Stage 6/10 — Run each candidate on the exact frozen 89 questions

Print:

```text
[STAGE 6/10] Evaluate chunking candidates
```

For every candidate, use exactly the Task 3.1 frozen question set.

Retrieve **top 50 raw vector results** per question.

Generation stays disabled.

For every query save enough local/git-ignored diagnostics to compare
candidate behavior:

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
search_ms
total_retrieval_ms
```

Do not calculate document nDCG by treating multiple chunks from the same
gold document as multiple relevance gains.

Task 3.1 already found/fixed that class of bug.

Use the exact corrected Task 3.1 document-level relevance semantics.

## Required metrics for every row

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

Do not report only percentages.

## N/A metrics

Unless valid gold now exists under an already-approved contract:

```text
chunk_recall@10 = N/A
chunk_mrr       = N/A
faithfulness    = N/A
citation_grounding = N/A
generation metrics = N/A
```

N/A is not zero.

Do not manufacture chunk relevance by assuming "same document" means
"correct chunk."

---

# Stage 7/10 — Paired comparison and uncertainty

Print:

```text
[STAGE 7/10] Paired ablation analysis
```

The same 89 questions are used by every candidate, so compare them
**paired by question_id**.

For each candidate vs row 0, and for each staged-round candidate vs the
round winner, report:

```text
delta doc_recall@10
delta doc_recall@50
delta doc_mrr
delta doc_ndcg@10

hit@10:
  gained questions
  lost questions
  unchanged questions

hit@50:
  gained questions
  lost questions
  unchanged questions

first-hit rank:
  improved
  worsened
  unchanged
```

Because N=89 is small, do not present tiny decimal differences as strong
evidence.

Use a deterministic paired bootstrap:

```text
seed:        42
iterations:  10,000
unit:        question_id
```

Produce 95% bootstrap intervals for metric deltas:

```text
doc_recall@10 delta
doc_recall@50 delta
doc_mrr delta
doc_ndcg@10 delta
```

The bootstrap is a diagnostic, not a magical proof of significance.

Do not add p-hacking, threshold tuning, or post-hoc subset selection.

## Required per-question disagreement artifact

Create a small tracked summary of only IDs/ranks/deltas, without copying
full question/evidence payloads if repository policy discourages that.

For each candidate record notable cases such as:

```text
row0 miss@10 -> candidate hit@10
row0 hit@10 -> candidate miss@10
large rank improvement
large rank regression
```

This is for failure analysis, not for tuning the same candidate after the
results are seen.

---

# Stage 8/10 — Frozen winner-selection rule

Print:

```text
[STAGE 8/10] Select chunking winner
```

Apply this rule exactly as frozen in the experiment config **before** seeing
results.

## Primary quality priorities

Use:

1. `doc_recall@50`
2. `doc_mrr`
3. `doc_ndcg@10`
4. `doc_recall@10`

Why:

- Phase 3 later feeds candidate pools into hybrid retrieval/reranking;
- candidate-set recall is critical;
- MRR/nDCG capture ranking quality;
- doc_recall@10 remains an important baseline diagnostic.

## Small-N tie handling

Do not declare a meaningful winner from a trivial percentage difference.

Treat candidates as practically tied when all of the following hold:

- Recall@50 differs by at most **1 question out of 89**;
- paired MRR delta's 95% bootstrap interval includes 0;
- paired nDCG@10 delta's 95% bootstrap interval includes 0.

When quality is practically tied, prefer in this order:

1. fewer chunks / lower duplication;
2. smaller embedding artifact;
3. smaller index;
4. lower retrieval p95;
5. lower embedding/build cost;
6. simpler chunking policy.

This is a pre-frozen engineering tie-breaker, not a post-hoc excuse.

## Regression protection

A candidate must not be selected merely because it improves one metric while
materially damaging the others.

If a candidate raises Recall@50 but causes a clear MRR/nDCG regression,
report the trade-off explicitly and STOP for user decision unless the
pre-frozen rule resolves it unambiguously.

## Staged choice

Apply the same selection logic:

1. select Round A window size;
2. select Round B overlap;
3. select Round C fixed vs section-aware;
4. declare one final Task 3.2 chunking configuration.

If row-0 512/0 fixed remains the best choice, that is a valid negative
result.

Do not force a new chunker to win.

---

# Stage 9/10 — Update the Phase 3 ablation table

Print:

```text
[STAGE 9/10] Update Phase 3 ablation table
```

Preserve row 0 exactly.

Never overwrite it.

Append one row per **formally evaluated** configuration.

Use the existing column contract from Task 3.1.

At minimum every new row must retain:

```text
row_id
configuration
status
round
run_id
git_sha
phase3_config_hash
chunk_config_hash

eval_split
eval_scope_kind
eval_scope_sha256
question_count

split_mode
window_size_tokens
overlap_tokens
stride_tokens
encoder_visible_tokens
encoder_truncation_note

chunk_count
chunk_artifact_size_bytes
embedding_artifact_size_bytes
index_size_bytes

doc_recall_at_10
doc_recall_at_10_hits
doc_recall_at_50
doc_recall_at_50_hits
doc_mrr
doc_ndcg_at_10

delta_vs_row0_recall10
delta_vs_row0_recall50
delta_vs_row0_mrr
delta_vs_row0_ndcg10

retrieval_latency_p50_ms
retrieval_latency_p95_ms
query_embedding_latency_p50_ms
search_latency_p50_ms

winner
notes
```

If the current ablation table has a frozen schema, extend it only through
the repository's established backward-compatible policy.

Do not casually rewrite old rows.

## Result artifact

Create a tracked summary such as:

```text
results/phase_3_2_chunking_ablation.json
```

It should contain:

- experiment config hash;
- baseline row/run;
- frozen 89-question scope identity;
- all candidate configs;
- build/index statistics;
- metrics;
- paired deltas;
- bootstrap intervals;
- final winner;
- explicit rationale;
- limitations.

Do not commit full chunk/embedding/index artifacts.

---

# Stage 10/10 — Tests, documentation, Git, and stop

Print:

```text
[STAGE 10/10] Verify and close Task 3.2
```

## Required tests

Add deterministic tests covering at least:

1. configurable 256/512/1024 fixed windows;
2. exact overlap/stride behavior;
3. no token gaps for overlap=0;
4. expected token overlap for overlap>0;
5. no duplicate final window;
6. partial final window retained;
7. deterministic chunk IDs/UIDs;
8. deterministic chunk-config hash;
9. hash changes with window size;
10. hash changes with overlap;
11. hash changes with fixed vs section-aware;
12. section-aware chunks never cross Item boundaries;
13. source section coverage is complete;
14. empty-source documents remain handled under the frozen policy;
15. no text rewriting;
16. baseline 512/0 output compatibility regression;
17. 1024 encoder-truncation policy is recorded correctly;
18. Task 3.1 89-question scope cannot change;
19. candidate evaluator refuses an unexpected question ID;
20. candidate evaluator refuses missing expected question IDs;
21. candidate evaluator refuses TEST split;
22. protected TEST API/file is never touched;
23. candidate retrieval depth is exactly 50;
24. exact-cosine semantics remain unchanged;
25. BM25/reranker/router/CRAG are absent;
26. generation remains disabled;
27. document Recall@10 correctness;
28. document Recall@50 correctness;
29. MRR correctness;
30. nDCG deduplicates document relevance correctly;
31. N/A remains distinct from zero;
32. paired-delta calculations;
33. deterministic bootstrap with seed 42;
34. bootstrap operates on paired question IDs;
35. row 0 cannot be overwritten;
36. duplicate ablation row IDs/config hashes are rejected appropriately;
37. candidate result records run_id + git_sha + config hashes;
38. Task 2.11 DEV run-log provenance is valid;
39. portable tests make no network/model/API calls;
40. prior Phase 1/2/3.1 result artifacts remain unchanged.

Use tiny synthetic fixtures for portable tests.

Do not put real full-corpus embedding builds inside pytest.

## Full verification

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Report exact counts.

If Ollama-specific tests remain part of the repository and the server is not
running, preserve the repository's already-established skip policy; do not
start or alter Task 2.13 merely for Task 3.2.

## Documentation

Update:

```text
project_plan/PHASE3_CHUNKING_ABLATION.md
project_plan/REPOSITORY_STRUCTURE.md   # only where necessary
Progress.md
```

Also update the current Phase 3 ablation table and Task 3.2 result JSON.

Progress.md must include:

- exact experiment grid;
- exact 89-question scope identity;
- metrics for every evaluated config;
- raw hit counts;
- paired deltas;
- bootstrap intervals;
- artifact/index/build implications;
- 1024-token truncation limitation if applicable;
- winning configuration;
- why it won;
- negative results;
- TEST discipline;
- exact test counts;
- Git commit/merge outcome;
- next task.

## Git

Before staging:

```powershell
git status
git diff --stat
git add -n <specific files>
```

Run a secret scan and large-file scan.

Never stage:

```text
data/
artifacts/
*.duckdb
*.parquet
*.lance/
embeddings
indexes
model weights/cache
.env
logs
```

Commit tracked configs, tests, small results, docs, and reusable source code.

Do not commit generated chunk/embedding/index artifacts.

Suggested experiment commit messages may be split if the task takes more
than ~2 hours:

```text
Add configurable Phase 3 chunking ablation
Record fixed-window chunking comparison
Evaluate overlap and section-aware chunking
Select Phase 3 chunking strategy
```

Use coherent working commits; do not create fake history after the fact.

If a remote exists, push according to the repository convention.
If no remote exists, record push as deferred.

No Phase 3 exit tag.

---

# Visible progress requirements

The user must be able to see long operations advancing.

Do not hide multi-minute builds in a detached/background shell.

For chunking:

```text
[CHUNK 256/0]  250/1500 docs  16.7%  chunks=...  ETA ...
```

For embeddings:

```text
[EMBED 256/0]  25000/... chunks  ...%  ... chunks/s  ETA ...
```

For index build:

```text
[INDEX 256/0]  building ... 
```

For evaluation:

```text
[EVAL 256/0]  10/89  11.2%  hits@10=...  hits@50=...  ETA ...
```

Use unbuffered/flush-safe output.

If a command is long-running, give the exact foreground command.

Do not redirect formal run output to a hidden log.

If resumability exists, expose a read-only `--status` command where useful;
status must make zero model calls and must not mutate checkpoints.

---

# Suggested CLI shape

Reuse existing scripts where cleanly possible.

A reasonable interface is:

```powershell
# Show frozen plan / current state
python -u scripts/run_phase3_chunking_ablation.py --plan

# Build/evaluate staged experiment
python -u scripts/run_phase3_chunking_ablation.py --run --resume

# Read-only status
python -u scripts/run_phase3_chunking_ablation.py --status

# Final comparison after all required candidates are complete
python -u scripts/run_phase3_chunking_ablation.py --compare
```

This is guidance, not a requirement to create this exact script if the
repository already has a better orchestration interface.

Do not duplicate existing build/eval logic just to get a new CLI.

---

# Formal output at completion

Print a compact but complete summary:

```text
PHASE 3 — TASK 3.2 CHUNKING ABLATION
====================================

Evaluation:
  split:                       DEV
  scope:                       frozen Task 3.1 evaluable subset
  questions:                   89
  scope_sha256:                ...

Frozen components:
  embedding:                   BAAI/bge-small-en-v1.5
  embedding revision:          ...
  retrieval:                   vector-only exact cosine
  candidate depth:             50
  generation:                  OFF
  BM25/reranker/router/CRAG:   OFF

Round A — window size
--------------------------------------------------------------
Config             R@10       R@50       MRR        nDCG@10
512/0 baseline     82/89       85/89      0.805056   0.833208
256/0              ...         ...        ...        ...
1024/0             ...         ...        ...        ...
1024 encoder note: ...

Round A winner:
  ...

Round B — overlap
--------------------------------------------------------------
Config             R@10       R@50       MRR        nDCG@10
winner/0           ...
winner/12.5%       ...
winner/25%         ...

Round B winner:
  ...

Round C — boundary policy
--------------------------------------------------------------
Config             R@10       R@50       MRR        nDCG@10
fixed              ...
section-aware      ...

Final winner:
  split_mode:                   ...
  window_size_tokens:           ...
  overlap_tokens:               ...
  chunk_config_hash:            ...

Paired vs row 0:
  R@10 delta:                   ...
  R@50 delta:                   ...
  MRR delta:                    ...
  nDCG@10 delta:                ...
  gained/lost @10:              ... / ...
  gained/lost @50:              ... / ...
  bootstrap 95% intervals:      ...

Cost/index effect vs row 0:
  chunk count:                  ...
  embedding artifact:           ...
  index size:                   ...
  retrieval p50/p95:            ...
  build time:                   ...

Ablation table:
  row 0:                        UNCHANGED / FROZEN
  Task 3.2 rows appended:       ...
  selected chunk strategy:      FROZEN FOR TASK 3.3

Protected TEST:
  opened:                       NO
  official runs used:           0/3

FinanceBench:
  rerun for tuning:             NO

Paid generation/API calls:
  0

Tests:
  doctor:                       ...
  portable:                     ...
  full:                         ...

Git:
  experiment branch:            ablation/chunking
  commits:                      ...
  main integration:             ...
  push:                         ...
  Phase 3 tag:                  NOT CREATED

TASK 3.2 STATUS:
  COMPLETE

PHASE 3 STATUS:
  IN PROGRESS

NEXT:
  Task 3.3 — Embedding model benchmark
```

Then STOP.

Do not start Task 3.3 automatically.

---

# Hard stop conditions

STOP and report rather than guessing if:

1. Task 3.1 is not actually complete.
2. row 0 is missing, duplicated, or mutable.
3. the row-0 metrics/config/run identity do not match current repository
   truth.
4. the frozen 89-question scope cannot be reproduced exactly.
5. TEST would need to be opened.
6. an official TEST run would be consumed.
7. the normalizer/source corpus changed since row 0.
8. an experiment changes the distractor corpus.
9. a candidate uses a different embedding model/revision.
10. a candidate uses different query/passage conventions.
11. a candidate changes retrieval metric/backend/ranking semantics.
12. ANN/BM25/reranking/hybrid retrieval is introduced.
13. generation is required for the formal chunking comparison.
14. FinanceBench is proposed as the routine selection/tuning set.
15. chunk-level metrics are proposed without valid chunk-level gold.
16. section-aware splitting would require fabricated section metadata.
17. 1024-token chunks would silently trigger encoder truncation without
    recording it.
18. someone proposes changing to a long-context embedding model just to make
    1024 chunks work.
19. overlap semantics differ across candidates.
20. one candidate is evaluated on a different question set.
21. the experiment grid is edited after observing results without creating a
    new version.
22. row 0 would be overwritten rather than preserved.
23. a new hashing implementation duplicates Task 2.10.
24. a new run-log format duplicates Task 2.11.
25. a prior Phase 1/2/3.1 frozen artifact is modified unexpectedly.
26. generated data/index/model artifacts are about to be committed.
27. secret/API-key content is about to be committed.
28. a result winner depends on an unresolved quality-vs-cost tradeoff not
    covered by the frozen selection rule.

---

# Success criteria

Task 3.2 is complete only when:

- the exact Task 3.1 89-question DEV scope was used for every candidate;
- row 0 remained unchanged;
- fixed 256/512/1024 were compared;
- overlap was tested in a controlled second round;
- fixed vs section-aware was tested in a controlled third round;
- the frozen BGE model and exact-cosine retriever stayed constant;
- the 1024-token encoder-limit behavior was measured and documented;
- quality metrics and raw hit counts were recorded;
- paired per-question deltas were analyzed;
- build/index/latency implications were recorded;
- one chunking strategy was selected with a pre-frozen rule;
- negative results were preserved honestly;
- the selected chunking strategy is frozen for Task 3.3;
- TEST remained unopened at 0/3;
- no paid generation calls were made;
- regression tests pass;
- the ablation table contains the new rows;
- Task 3.2 is committed/documented;
- Task 3.3 has **not** started.
