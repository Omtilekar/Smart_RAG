# Phase 3 — Task 3.5: RRF Hybrid Fusion

## Objective

Add and evaluate **Reciprocal Rank Fusion (RRF)** over the two retrieval
components already frozen by Tasks 3.3 and 3.4:

- dense: Task 3.3 winner `Qwen/Qwen3-Embedding-0.6B`
- sparse: Task 3.4 LanceDB-native BM25/FTS baseline

This task changes **fusion only**.

The purpose is to determine whether rank-only dense+sparse fusion improves
the retrieval ranking while preserving the strong candidate-set recall
already achieved by the dense model.

Do not change:

- chunking;
- embedding model;
- sparse analyzer/index;
- dense vector index;
- source corpus;
- evaluation scope;
- metadata filtering;
- reranking;
- routing;
- CRAG;
- generation;
- TEST.

Do not start the next roadmap task automatically.

---

# Authoritative repository precedence

Before changing anything, re-read the current repository in this order:

1. `project_plan/PROJECT_EXECUTION.md`
2. `Progress.md`
3. `project_plan/GIT_CONVENTIONS.md`
4. `project_plan/PHASE3_TRUSTED_BASELINE.md`
5. `project_plan/PHASE3_CHUNKING_ABLATION.md`
6. `project_plan/PHASE3_EMBEDDING_MODEL_BENCHMARK.md`
7. `project_plan/PHASE3_BM25_FTS_BASELINE.md`
8. `results/phase_3_1_trusted_baseline.json`
9. `results/phase_3_2_chunking_ablation.json`
10. `results/phase_3_3_embedding_model_benchmark.json`
11. `results/phase_3_4_bm25_fts_baseline.json`
12. `results/phase_3_ablation_table.csv`
13. `configs/phase_3_2_chunking_ablation.json`
14. `configs/phase_3_3_embedding_model_benchmark.json`
15. `configs/phase_3_4_bm25_fts_baseline.json`
16. Task 2.10 canonical hashing code
17. Task 2.11 run-log code
18. current dense/sparse retriever implementations and tests

Repository truth wins over any stale value written in this prompt.

If the CURRENT `PROJECT_EXECUTION.md` defines a more specific Task 3.5
fusion grid, RRF constant, candidate depth, selection rule, or output
contract, use the roadmap exactly.

STOP on a material contradiction rather than silently choosing a different
experiment.

---

# Verified state entering Task 3.5

Task 3.4 is COMPLETE.

The frozen Task 3.2 chunking winner is:

```text
split_mode:          fixed
window_size_tokens:  256
overlap_tokens:      0
stride_tokens:       256

chunk_config_hash:
ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
```

The frozen Task 3.3 dense winner is:

```text
model:
Qwen/Qwen3-Embedding-0.6B

revision:
97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3

dimension:
1024
```

Task 3.3 dense metrics on the frozen 89-question DEV scope:

```text
doc_recall@10:  88/89 = 0.9888
doc_recall@50:  89/89 = 1.0000
doc_mrr:        0.9251
doc_ndcg@10:    0.9407
```

The frozen Task 3.4 sparse baseline is LanceDB-native FTS/BM25-style
retrieval over the same Task 3.2 chunks.

Task 3.4 sparse metrics:

```text
doc_recall@10:  86/89 = 0.9663
doc_recall@50:  88/89 = 0.9888
doc_mrr:        0.8830
doc_ndcg@10:    0.9028
```

Task 3.4 complementarity:

```text
hit@10:
  both:         85
  dense_only:    3
  sparse_only:   1
  neither:       0

hit@50:
  both:         88
  dense_only:    1
  sparse_only:   0
  neither:       0
```

Re-read the real result files and STOP if these values differ materially.

Important consequence:

```text
dense doc_recall@50 is already 89/89 = 1.0000
```

Therefore hybrid fusion cannot improve Recall@50 on this frozen scope.
Task 3.5 must treat preservation of the 89/89 candidate-set ceiling as a
hard quality guard while looking for ranking improvements at smaller ranks.

Do not manufacture a "Recall@50 improvement" where mathematical improvement
is impossible.

---

# Critical evaluation-scope rule

Every formal Task 3.5 run must use the exact same frozen Task 3.1
`DEV/evaluable-subset`:

```text
question count: 89
```

Use the existing frozen question-ID artifact/hash.

Do not:

- regenerate the 89 IDs;
- recompute corpus coverage;
- add newly coverable questions;
- remove difficult questions;
- use FinanceBench for tuning;
- use protected TEST;
- use a different question subset for dense, sparse, or hybrid.

If the exact scope cannot be reproduced hash-for-hash, STOP.

---

# Protected TEST discipline

Throughout Task 3.5:

```text
protected SEC TEST opened:       NO
official SEC TEST runs consumed: 0/3
```

Do not load TEST.
Do not inspect TEST IDs.
Do not write TEST-access records for DEV experiments.
Do not run a "sanity check" on TEST.

---

# Experimental principle

Task 3.5 changes **fusion only**.

Freeze:

```text
source corpus
normalized corpus
Task 3.2 chunks
Task 3.2 chunk_config_hash

Task 3.3 dense model/revision
Task 3.3 dense query convention
Task 3.3 dense index
dense exact-cosine semantics

Task 3.4 sparse index
Task 3.4 native FTS query sanitization
Task 3.4 sparse ranking semantics

89-question DEV scope
metric implementations
document-level relevance semantics
generation = OFF
reranker = OFF
metadata pre-filter = OFF
router = OFF
CRAG = OFF
```

No component may be retrained, rebuilt, or retuned merely because hybrid
results are disappointing.

---

# Git / branch policy

Create a dedicated Phase 3 ablation branch unless current
`GIT_CONVENTIONS.md` says otherwise:

```text
ablation/hybrid-rrf
```

Before branching:

```powershell
git status
git branch --show-current
git log -5 --oneline --decorate
```

Task 3.4 must already be committed/integrated according to repository
convention.

If unrelated working-tree changes exist, STOP and report them.

Do not create a Phase 3 completion tag.

---

# Stage 1/10 — Preflight and frozen-component verification

Print:

```text
[STAGE 1/10] Task 3.5 preflight
```

Verify:

1. Task 3.4 status = COMPLETE.
2. Task 3.5 is the current next roadmap task.
3. row 0 exists exactly once and is unchanged.
4. all Task 3.2 rows are unchanged.
5. all Task 3.3 rows are unchanged.
6. Task 3.4 sparse row is present and unchanged.
7. Task 3.2 chunk hash matches:
   `ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06`.
8. the Qwen dense identity/revision matches Task 3.3.
9. the dense index is present and valid.
10. the sparse FTS artifact is present and valid.
11. the 89-question scope reproduces exactly.
12. protected TEST remains unopened.
13. official TEST runs remain 0/3.
14. no paid API is required.
15. Task 2.10 canonical hashing is available.
16. Task 2.11 run logging is available.

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Record exact pre-task counts.

---

# Stage 2/10 — Verify the two parent retrieval streams

Print:

```text
[STAGE 2/10] Verify dense and sparse parent streams
```

Before implementing fusion, prove both parent rankings still reproduce.

For the exact frozen 89 questions:

## Dense

Use the frozen Task 3.3 Qwen path.

Retrieve top 50.

Recompute or validate:

```text
R@10 = 88/89
R@50 = 89/89
MRR  = 0.9251
nDCG@10 = 0.9407
```

## Sparse

Use the frozen Task 3.4 LanceDB-native FTS path.

Retrieve top 50.

Recompute or validate:

```text
R@10 = 86/89
R@50 = 88/89
MRR  = 0.8830
nDCG@10 = 0.9028
```

Do not proceed if either parent ranking has drifted.

## Reuse policy

If Tasks 3.3/3.4 persisted full top-50 per-query ranked result artifacts
with sufficient provenance:

- validate their scope/config identities;
- reuse them for pure fusion analysis.

If full ranked results were not persisted or provenance is insufficient:

- rerun **retrieval only** for the 89 DEV questions;
- do not rebuild embeddings;
- do not rebuild the dense index;
- do not rebuild FTS;
- do not modify parent result files.

Whichever route is used must be documented.

---

# Stage 3/10 — Freeze the RRF contract before formal evaluation

Print:

```text
[STAGE 3/10] Freeze RRF contract
```

Create a tracked config such as:

```text
configs/phase_3_5_rrf_hybrid_fusion.json
```

Use Task 2.10 canonical `semantic_hash()`.

Do not invent another hashing implementation.

## RRF definition

Unless CURRENT `PROJECT_EXECUTION.md` explicitly defines another value,
freeze the standard untuned baseline:

```text
rrf_k = 60
```

No RRF-constant sweep in this task unless the roadmap explicitly requires
one.

For a chunk `d`:

```text
RRF(d) =
    dense contribution +
    sparse contribution

dense contribution =
    1 / (rrf_k + dense_rank(d))
    if d appears in the dense candidate list,
    otherwise 0

sparse contribution =
    1 / (rrf_k + sparse_rank(d))
    if d appears in the sparse candidate list,
    otherwise 0
```

Ranks are **1-based**.

RRF uses ranks only.

Do not normalize, min-max scale, z-score, or otherwise mix:

- dense cosine scores/distances;
- sparse `_score` values.

## Candidate pools

Unless the roadmap says otherwise:

```text
dense candidate depth:   50
sparse candidate depth:  50
fusion union key:        chunk_id
final hybrid depth:      50
```

The union may contain up to 100 unique chunks before final truncation.

## Duplicate handling

Within each parent stream:

- a `chunk_id` must be unique;
- duplicate `chunk_id` inside one stream is an error, not something to
  silently collapse.

Across streams:

- the same `chunk_id` is one fused candidate;
- it receives both RRF contributions.

Do not fuse by document ID.
Fusion happens at the **chunk level**.

Document deduplication belongs only to the evaluation metric logic already
frozen in Tasks 3.1/2.6.

## Deterministic tie-break

Freeze a deterministic tie-break before seeing formal results.

Unless the roadmap already defines one, sort by:

1. higher `rrf_score`;
2. lower `best_parent_rank = min(dense_rank, sparse_rank)`;
3. lower dense rank, with missing dense rank treated as infinity;
4. lower sparse rank, with missing sparse rank treated as infinity;
5. lexical `chunk_id` ascending.

This tie-break changes only exact-score ties.

Document it in config and tests.

---

# Stage 4/10 — Implement a reusable RRF fusion primitive

Print:

```text
[STAGE 4/10] Implement RRF fusion
```

Prefer a small pure module, for example:

```text
src/retrieval/fusion.py
```

with a pure function or small class such as:

```text
rrf_fuse(dense_results, sparse_results, *, rrf_k=60, limit=50)
```

Follow existing repository conventions.

The fusion primitive must:

- validate `rrf_k` as a positive integer;
- reject bools as integers;
- validate `limit` as a positive integer;
- validate parent ranks;
- require unique `chunk_id` per parent stream;
- preserve provenance metadata;
- never call a model;
- never call LanceDB itself;
- never mutate parent result objects;
- produce deterministic output.

Recommended fused result fields:

```text
rank
chunk_id
document_id
text
rrf_score

dense_rank
dense_distance
dense_score if already part of parent schema

sparse_rank
sparse_score

in_dense
in_sparse

cik
company
form_type
fiscal_year
source
source_filename
source_split
ordinal
token_count
chunk_config_hash
```

Do not invent a fake cross-modal "similarity score."

`rrf_score` is a rank-fusion score only.

---

# Stage 5/10 — Implement the hybrid retriever boundary

Print:

```text
[STAGE 5/10] Implement hybrid retriever
```

Add a reusable retrieval boundary rather than putting all composition logic
inside the benchmark script.

A reasonable design may be:

```text
HybridRetriever(
    dense_retriever=...,
    sparse_retriever=...,
    rrf_k=60,
    dense_k=50,
    sparse_k=50,
)

.retrieve(question, k=50)
```

but follow repository patterns.

Requirements:

1. validate the user question once;
2. call the dense retriever exactly once;
3. call the sparse retriever exactly once;
4. request the frozen parent candidate depths;
5. fuse the parent results using the pure RRF implementation;
6. return the requested hybrid limit;
7. do not rerank;
8. do not call generation;
9. do not pre-filter metadata;
10. do not modify either parent index.

## Parent failure behavior

Do not silently degrade to one retrieval arm in the formal benchmark.

If dense retrieval fails or sparse retrieval fails:

- fail the formal query/run clearly;
- record the error;
- do not call the result "hybrid."

Production fallback behavior can be designed in a later task.

---

# Stage 6/10 — Synthetic and real smoke validation

Print:

```text
[STAGE 6/10] Validate RRF behavior
```

Before formal 89-question evaluation, validate the algorithm with
hand-checkable synthetic rankings.

Examples must cover:

```text
same chunk rank 1 in both streams
dense-only chunk
sparse-only chunk
opposite rank orders
exact RRF-score tie
duplicate chunk in one parent stream -> error
missing parent contribution -> zero
```

Manually calculate expected scores for a small example and assert exact or
tight-tolerance agreement.

Example for `rrf_k=60`:

```text
dense:
  A rank 1
  B rank 2

sparse:
  B rank 1
  C rank 2

A = 1/(60+1)
B = 1/(60+2) + 1/(60+1)
C = 1/(60+2)
```

Therefore:

```text
B > A > C
```

Also run several real DEV questions and print:

```text
dense top ranks
sparse top ranks
fused top ranks
RRF contributions
```

This is a correctness smoke only.

Do not tune RRF parameters based on these examples.

---

# Stage 7/10 — Formal hybrid evaluation on the frozen 89 questions

Print:

```text
[STAGE 7/10] Evaluate RRF hybrid retrieval
```

Run exactly the frozen 89 DEV questions.

For each query:

```text
dense top 50
+
sparse top 50
->
RRF union
->
hybrid top 50
```

Generation remains OFF.

Reranking remains OFF.

For each query persist git-ignored diagnostics containing at least:

```text
question_id
gold_document_ids

dense ranked chunk_ids 1..50
sparse ranked chunk_ids 1..50

hybrid ranked chunk_ids 1..50
hybrid ranked document_ids 1..50

per fused chunk:
  rrf_score
  dense_rank or null
  sparse_rank or null
  in_dense
  in_sparse

first gold-document hit rank
hit@10
hit@50
reciprocal_rank
ndcg@10

dense_retrieval_ms
sparse_retrieval_ms
fusion_ms
total_hybrid_retrieval_ms
```

Use the exact corrected document-level metric semantics from Task 3.1.

Do not count multiple chunks from the same relevant document as repeated
relevance gain.

## Required metrics

```text
doc_recall@10
doc_recall@50
doc_mrr
doc_ndcg@10
```

Also record:

```text
hits@10 / 89
hits@50 / 89
misses@10
misses@50
```

## Hard candidate-recall guard

Because dense already achieves:

```text
doc_recall@50 = 89/89
```

the formal hybrid candidate must preserve:

```text
doc_recall@50 = 89/89
```

If hybrid drops below 89/89:

- do not select it as the Phase 3 retrieval winner;
- diagnose which question fell out and why;
- do not tune on that question after the fact;
- preserve the result as a negative ablation.

## N/A metrics

Without valid chunk gold:

```text
chunk_recall@10 = N/A
chunk_mrr       = N/A
```

With generation disabled:

```text
numeric_exact_match        = N/A
correct_refusal_rate       = N/A
citation_format_compliance = N/A
citation_grounding         = N/A
faithfulness               = N/A
```

N/A is not zero.

## Run logging

Create a Task 2.11 DEV run record using a kind such as:

```text
phase3_rrf_hybrid_retrieval
```

Record:

```text
run_id
git_sha
dirty state
DEV scope identity
question count
chunk_config_hash
dense model/revision/identity
dense index identity
sparse config/artifact identity
RRF config hash
rrf_k
dense_k
sparse_k
final_k
metrics
latencies
timestamp
```

No TEST linkage.

---

# Stage 8/10 — Paired analysis against dense and sparse parents

Print:

```text
[STAGE 8/10] Analyze hybrid deltas
```

The primary comparison is:

```text
hybrid vs Task 3.3 dense winner
```

Also report:

```text
hybrid vs Task 3.4 sparse baseline
```

For each comparison report:

```text
delta doc_recall@10
delta doc_recall@50
delta doc_mrr
delta doc_ndcg@10
```

Use raw hit-count changes as well as percentages.

## Per-question movement

Hybrid vs dense:

```text
hit@10:
  gained
  lost
  unchanged

hit@50:
  gained
  lost
  unchanged

first gold-document rank:
  improved
  worsened
  unchanged
```

Because dense is already 88/89 at R@10 and 89/89 at R@50, identify the
exact counts honestly.

Do not exaggerate tiny changes.

## Paired bootstrap

Use the existing Phase 3 convention unless current roadmap overrides it:

```text
seed:        42
iterations:  10,000
unit:        question_id
```

Report 95% paired bootstrap intervals for:

```text
delta R@10
delta R@50
delta MRR
delta nDCG@10
```

## Fusion-source composition

Report for hybrid top 10 and top 50:

```text
candidates present in both parents
dense-only candidates
sparse-only candidates
```

Also report how many final top-k results received:

```text
two-arm RRF contribution
dense-only contribution
sparse-only contribution
```

This gives a direct explanation of whether hybrid is actually using sparse
evidence or merely reproducing the dense order.

---

# Stage 9/10 — Frozen selection rule and ablation-table update

Print:

```text
[STAGE 9/10] Select hybrid retrieval configuration
```

First apply any exact rule in CURRENT `PROJECT_EXECUTION.md`.

If the roadmap does not define a more specific rule, use this pre-frozen
decision rule:

## Gate 1 — Preserve candidate recall

Hybrid is eligible only if:

```text
doc_recall@50 = 89/89
```

A hybrid result that loses the dense model's only-perfect candidate-set
recall is not selected.

## Gate 2 — Prefer ranking improvement

Among eligible configurations, compare against Qwen dense on:

1. `doc_mrr`
2. `doc_ndcg@10`
3. `doc_recall@10`

Since Recall@50 is already at ceiling, do not pretend it can distinguish
an improvement.

## Practical tie

Treat hybrid and dense as practically tied when:

- R@10 differs by at most 1 question out of 89;
- MRR paired-bootstrap 95% CI includes 0;
- nDCG@10 paired-bootstrap 95% CI includes 0.

If practically tied, prefer **dense-only** because it is simpler and avoids
a second retrieval path at query time.

Hybrid must earn its extra complexity.

## Trade-off requiring user decision

STOP for user decision if hybrid:

- preserves R@50;
- clearly improves one important ranking metric;
- clearly regresses another important ranking metric;
- and the frozen rule does not resolve the trade-off.

Do not retune RRF after seeing the result simply to make hybrid win.

A negative result where dense-only remains the selected retrieval mode is
fully valid.

---

# Ablation table

Preserve all earlier rows exactly.

Append the Task 3.5 hybrid row.

Recommended fields:

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

dense_embedding_model
dense_embedding_revision
dense_embedding_dimension
dense_index_identity

sparse_backend
sparse_config_hash

retrieval_mode
fusion_method
rrf_k
dense_candidate_k
sparse_candidate_k
final_candidate_k

doc_recall_at_10
doc_recall_at_10_hits
doc_recall_at_50
doc_recall_at_50_hits
doc_mrr
doc_ndcg_at_10

delta_vs_dense_recall10
delta_vs_dense_recall50
delta_vs_dense_mrr
delta_vs_dense_ndcg10

hit10_gained_vs_dense
hit10_lost_vs_dense
hit50_gained_vs_dense
hit50_lost_vs_dense

hybrid_both_parent_top10
hybrid_dense_only_top10
hybrid_sparse_only_top10

hybrid_both_parent_top50
hybrid_dense_only_top50
hybrid_sparse_only_top50

dense_latency_p50_ms
sparse_latency_p50_ms
fusion_latency_p50_ms
hybrid_latency_p50_ms
hybrid_latency_p95_ms

selected
notes
```

Do not rewrite historical rows.

---

# Task 3.5 result artifact

Create:

```text
results/phase_3_5_rrf_hybrid_fusion.json
```

Include:

```text
experiment/config hash
frozen 89-question scope identity

Task 3.2 chunk identity

Task 3.3 dense model/revision/index identity
Task 3.3 dense reference metrics

Task 3.4 sparse artifact/config identity
Task 3.4 sparse reference metrics

RRF definition
rrf_k
candidate depths
deterministic tie-break

hybrid metrics
raw hit counts

paired deltas vs dense
paired deltas vs sparse
bootstrap intervals

per-question gain/loss counts
fusion-source composition
latency breakdown

selected retrieval mode for next task
selection rationale
limitations
```

Do not include protected TEST content.

---

# Stage 10/10 — Tests, docs, Git, and stop

Print:

```text
[STAGE 10/10] Verify and close Task 3.5
```

## Required tests

Add deterministic tests covering at least:

1. RRF uses 1-based ranks.
2. exact RRF formula.
3. missing dense candidate contributes zero.
4. missing sparse candidate contributes zero.
5. same chunk in both streams receives both contributions.
6. fusion key is `chunk_id`, not `document_id`.
7. duplicate `chunk_id` inside dense stream rejected.
8. duplicate `chunk_id` inside sparse stream rejected.
9. positive integer validation for `rrf_k`.
10. bool `rrf_k` rejected.
11. positive integer validation for `limit`.
12. deterministic tie-break.
13. parent input order does not change fused result when parent ranks are
    explicitly supplied.
14. parent result objects are not mutated.
15. full provenance metadata is preserved.
16. RRF score is not called cosine/BM25 probability.
17. dense and sparse raw scores are not numerically normalized or added.
18. dense retriever called exactly once per hybrid query.
19. sparse retriever called exactly once per hybrid query.
20. parent failure does not silently degrade formal hybrid to one arm.
21. candidate depth = frozen value.
22. final hybrid depth = frozen value.
23. exact 89-question scope is required.
24. unexpected question ID rejected.
25. missing expected question ID rejected.
26. TEST split rejected.
27. no generation call.
28. no reranker call.
29. no metadata pre-filter.
30. no router/CRAG call.
31. document Recall@10 correctness.
32. document Recall@50 correctness.
33. MRR correctness.
34. document nDCG deduplication correctness.
35. N/A remains distinct from zero.
36. paired delta calculations.
37. deterministic paired bootstrap seed 42.
38. fusion-source composition counts.
39. R@50 selection guard.
40. practical-tie selection behavior.
41. Task 2.11 DEV run provenance.
42. row 0 cannot be overwritten.
43. Task 3.2 rows cannot be rewritten.
44. Task 3.3 rows cannot be rewritten.
45. Task 3.4 row cannot be rewritten.
46. Task 3.5 row contains run/config/Git identities.
47. protected TEST access code is never imported by Task 3.5 runner.
48. portable tests perform no model/API/network calls.
49. prior Phase 1/2/3.1–3.4 tracked result artifacts remain unchanged.

Use tiny synthetic parent-ranking fixtures for portable tests.

Do not require the full Qwen model or real FTS artifact in portable tests.

A separately marked local integration test may exercise the real 89-query
pipeline if appropriate.

## Verification

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Report exact counts.

## Documentation

Create/update as appropriate:

```text
project_plan/PHASE3_RRF_HYBRID_FUSION.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Progress must record:

- exact parent identities;
- RRF formula;
- `rrf_k`;
- candidate depths;
- tie-break;
- hybrid metrics;
- raw hit counts;
- paired deltas;
- bootstrap intervals;
- gain/loss counts;
- fusion-source composition;
- latency;
- whether hybrid or dense-only is selected for the next task;
- protected TEST status;
- exact test counts;
- Git outcome;
- exact next roadmap task.

## Git safety

Before staging:

```powershell
git status
git diff --stat
git add -n <specific files>
```

Run secret and large-file scans.

Never commit:

```text
data/
artifacts/
embedding arrays
LanceDB data
FTS index data
model weights/cache
*.duckdb
*.parquet
.env
API keys
large logs
```

Commit only small:

```text
source
tests
config
result JSON/CSV
documentation
Progress.md
```

Suggested coherent commit names:

```text
Add deterministic RRF hybrid retrieval
Evaluate Phase 3 RRF hybrid fusion
```

Use real working history.

No Phase 3 completion tag.

---

# Visible progress requirements

Formal evaluation must remain visible.

Examples:

```text
[HYBRID] validating dense parent...
[HYBRID] validating sparse parent...
[HYBRID] parents reproduce frozen metrics

[HYBRID EVAL]  10/89  11.2%  R10_hits=... R50_hits=... avg_ms=...
[HYBRID EVAL]  20/89  22.5%  R10_hits=... R50_hits=... avg_ms=...
```

Do not hide formal work in an opaque detached/background process.

If read-only status support exists, it must not mutate artifacts or issue
additional model calls.

---

# Suggested CLI shape

Reuse the Phase 3 experiment-runner style already established.

A reasonable interface is:

```powershell
python -u scripts/run_phase3_rrf_hybrid.py --plan
python -u scripts/run_phase3_rrf_hybrid.py --run
python -u scripts/run_phase3_rrf_hybrid.py --compare
```

or one idempotent:

```powershell
python -u scripts/run_phase3_rrf_hybrid.py --run
```

Do not create a redundant CLI if the repository already has a clean shared
orchestration pattern.

---

# Formal completion display

At completion print:

```text
PHASE 3 — TASK 3.5 RRF HYBRID FUSION
====================================

Evaluation:
  split:                         DEV
  scope:                         frozen Task 3.1 evaluable subset
  questions:                     89
  scope_sha256:                  ...

Frozen chunks:
  split_mode:                    fixed
  window_size_tokens:            256
  overlap_tokens:                0
  chunk_config_hash:             ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06

Dense parent:
  model:                         Qwen/Qwen3-Embedding-0.6B
  revision:                      97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
  candidate_k:                   50

Sparse parent:
  backend:                       LanceDB-native FTS
  candidate_k:                   50

Fusion:
  method:                        Reciprocal Rank Fusion
  rrf_k:                         60
  union key:                     chunk_id
  final_k:                       50
  tie-break:                     ...

Metrics:
-------------------------------------------------------------------
Mode                  R@10       R@50       MRR       nDCG@10
Dense Qwen            88/89      89/89      0.9251    0.9407
Sparse FTS            86/89      88/89      0.8830    0.9028
RRF hybrid            ...        ...        ...       ...

Hybrid vs dense:
  delta R@10:                    ...
  delta R@50:                    ...
  delta MRR:                     ...
  delta nDCG@10:                 ...
  hit@10 gained/lost:            ... / ...
  hit@50 gained/lost:            ... / ...
  95% bootstrap intervals:       ...

Fusion composition:
  top10 both/dense-only/sparse-only: ...
  top50 both/dense-only/sparse-only: ...

Latency:
  dense p50:                     ...
  sparse p50:                    ...
  fusion p50:                    ...
  hybrid total p50/p95:          ... / ...

Selection:
  selected retrieval mode:       ...
  reason:                        ...

Ablation table:
  prior rows:                    UNCHANGED
  Task 3.5 row:                  APPENDED

Protected TEST:
  opened:                        NO
  official runs used:            0/3

FinanceBench:
  rerun for tuning:              NO

Paid API/generation calls:
  0

Tests:
  doctor:                        ...
  portable:                      ...
  full:                          ...

Git:
  experiment branch:             ablation/hybrid-rrf
  commits:                       ...
  integration outcome:           ...
  Phase 3 tag:                   NOT CREATED

TASK 3.5 STATUS:
  COMPLETE

PHASE 3 STATUS:
  IN PROGRESS

NEXT ROADMAP TASK:
  <read exact next task number/title from current PROJECT_EXECUTION.md>
```

Then STOP.

Do not implement the next task automatically.

---

# Hard stop conditions

STOP and report rather than guessing if:

1. Task 3.4 is not actually complete.
2. Task 3.2 chunk identity changed.
3. Task 3.3 dense model/revision/index identity changed.
4. Task 3.4 sparse index/config identity changed.
5. dense parent no longer reproduces its frozen metrics.
6. sparse parent no longer reproduces its frozen metrics.
7. the exact 89-question scope cannot be reproduced.
8. row 0 changed unexpectedly.
9. Task 3.2/3.3/3.4 historical rows changed unexpectedly.
10. CURRENT roadmap specifies an RRF contract that conflicts with this
    prompt.
11. candidate-depth policy differs between parent runs.
12. someone proposes changing the embedding model.
13. someone proposes rechunking.
14. someone proposes rebuilding/tuning sparse analysis.
15. someone proposes score normalization or weighted score addition instead
    of RRF.
16. someone proposes an RRF parameter sweep not authorized by the roadmap.
17. someone proposes reranking in Task 3.5.
18. someone proposes metadata pre-filtering in Task 3.5.
19. someone proposes generation in Task 3.5.
20. someone proposes FinanceBench as the tuning set.
21. TEST would need to be opened.
22. an official TEST run would be consumed.
23. chunk metrics are proposed without chunk gold.
24. N/A would be encoded as zero.
25. hybrid silently degrades to one parent after a parent error.
26. fusion happens by document ID rather than chunk ID.
27. a new hashing implementation duplicates Task 2.10.
28. a new run-log format duplicates Task 2.11.
29. hybrid uses a different question set than the parent baselines.
30. hybrid result loses 89/89 R@50 but is about to be selected anyway.
31. RRF is post-hoc tuned after seeing failures without a versioned new
    experiment.
32. large generated artifacts are about to be committed.
33. secrets/API keys are about to be committed.
34. prior frozen Phase 1/2/3 result artifacts are modified unexpectedly.

---

# Success criteria

Task 3.5 is complete only when:

- Task 3.2 fixed 256/0 chunking remains frozen;
- Task 3.3 Qwen dense retrieval remains frozen;
- Task 3.4 LanceDB FTS sparse retrieval remains frozen;
- both parent rankings reproduce before fusion;
- the exact same 89 DEV questions are used;
- a deterministic RRF contract is frozen before the formal run;
- fusion occurs at chunk level;
- no dense/sparse raw-score normalization is used;
- top-50 hybrid results are evaluated;
- R@10, R@50, MRR, and nDCG@10 are recorded with raw hit counts;
- paired deltas and bootstrap intervals are reported;
- fusion-source composition is reported;
- query latency and fusion overhead are measured;
- hybrid preserves 89/89 R@50 if it is selected;
- the selection rule honestly decides hybrid vs dense-only;
- negative results are retained;
- all earlier ablation rows remain unchanged;
- a Task 3.5 row is appended;
- TEST remains unopened at 0/3;
- no paid API/generation calls are made;
- all regression tests pass;
- Task 3.5 is documented and committed;
- the next roadmap task has not started.
