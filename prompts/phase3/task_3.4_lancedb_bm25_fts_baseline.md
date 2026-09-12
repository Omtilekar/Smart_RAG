# Phase 3 — Task 3.4: LanceDB-Native BM25 / FTS Sparse Retrieval Baseline

## Objective

Add and benchmark the first **sparse lexical retrieval baseline** for Phase 3 using **LanceDB-native full-text search / BM25-style ranking** over the frozen Task 3.2 chunk corpus.

This task is intentionally narrow:

- keep Task 3.2 chunking frozen;
- keep Task 3.3's selected dense embedding model frozen for future hybrid work;
- add a **sparse-only** LanceDB FTS retrieval path;
- evaluate it on the exact same frozen 89-question DEV scope;
- measure retrieval quality, latency, build time, and index size;
- append the Task 3.4 result to the Phase 3 ablation table;
- freeze the sparse baseline contract for the next hybrid-retrieval task.

This is **not** the hybrid-retrieval task.

Do not combine dense + sparse scores.
Do not implement RRF.
Do not rerank.
Do not add CRAG, routing, metadata pre-filtering, SQL retrieval, graph retrieval, generation, or TEST evaluation.

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
7. `results/phase_3_1_trusted_baseline.json`
8. `results/phase_3_2_chunking_ablation.json`
9. `results/phase_3_3_embedding_model_benchmark.json`
10. `results/phase_3_ablation_table.csv`
11. `configs/phase_3_2_chunking_ablation.json`
12. `configs/phase_3_3_embedding_model_benchmark.json`
13. Task 2.10 canonical hashing code
14. Task 2.11 run-log code
15. current LanceDB/index/retrieval/evaluation implementations and tests

Repository truth wins over stale values written in this prompt.

If `PROJECT_EXECUTION.md` gives a more specific Task 3.4 contract, follow it.

STOP on a material contradiction instead of silently choosing a different design.

---

# Verified Phase 3 state entering Task 3.4

Task 3.3 is complete.

The frozen Task 3.2 chunking winner is:

```text
split_mode:          fixed
window_size_tokens:  256
overlap_tokens:      0
stride_tokens:       256

chunk_config_hash:
ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
```

The frozen Task 3.3 dense embedding winner is:

```text
model:
Qwen/Qwen3-Embedding-0.6B

revision:
97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3

embedding dimension:
1024
```

Task 3.3 winner retrieval metrics were:

```text
questions:       89
doc_recall@10:   88/89
doc_recall@50:   89/89
doc_mrr:         0.9251
doc_ndcg@10:     0.9407
```

Re-read the real Task 3.3 result before relying on these values.

Task 3.4 does **not** change this dense winner.

The Qwen dense stack remains frozen and available for the later hybrid task.

---

# Critical evaluation-scope rule

Every formal Task 3.4 run must use the exact same frozen Task 3.1 DEV/evaluable scope:

```text
question count: 89
```

Use the already-frozen question-ID artifact/hash.

Do not:

- regenerate the 89 IDs;
- re-intersect the corpus;
- add newly coverable questions;
- remove lexical-hard questions;
- tune on FinanceBench;
- use protected TEST;
- score a different subset for sparse retrieval.

The sparse candidate must be evaluated on exactly the same question IDs used by Tasks 3.1, 3.2, and 3.3.

If the scope hash or exact IDs cannot be reproduced, STOP.

---

# Protected TEST discipline

Throughout Task 3.4:

```text
protected SEC TEST opened:       NO
official SEC TEST runs consumed: 0/3
```

Do not load the TEST payload.
Do not inspect TEST IDs.
Do not create a TEST access record.
Do not run a "quick sanity check" on TEST.

All experimentation remains DEV-only.

---

# Experimental principle

Task 3.4 changes **retrieval modality only**:

```text
dense-only -> sparse-only
```

Freeze everything else that can reasonably remain fixed:

```text
source corpus
normalized corpus
Task 3.2 fixed 256/0 chunk artifact
chunk_config_hash
document/chunk metadata
89-question DEV scope
evaluation metric implementations
document-level relevance semantics
candidate depth = 50
generation = OFF
reranker = OFF
CRAG = OFF
router = OFF
metadata pre-filtering = OFF
```

The dense Qwen model is not used to compute sparse query scores, but its frozen identity must remain recorded as the current selected dense model for the next task.

Do not rebuild or modify Qwen embeddings merely to add FTS.

---

# Git / branch policy

Create a dedicated experiment branch unless current `GIT_CONVENTIONS.md` says otherwise:

```text
ablation/bm25-fts
```

Before branching:

```powershell
git status
git branch --show-current
git log -5 --oneline --decorate
```

Task 3.3 must already be committed/integrated according to repository convention.

If unrelated working-tree changes exist, STOP and report them.

Do not create a Phase 3 completion tag.

---

# Stage 1/10 — Preflight

Print:

```text
[STAGE 1/10] Task 3.4 preflight
```

Verify:

1. Task 3.3 status = COMPLETE.
2. Task 3.4 is the current next roadmap task.
3. Task 3.2 winner chunk hash matches:
   `ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06`.
4. The frozen 256/0 chunk artifact exists and is complete.
5. Its chunk row count matches the Task 3.2/3.3 recorded corpus size.
6. The exact 89-question scope reproduces.
7. Row 0 remains unchanged.
8. All Task 3.2 rows remain unchanged.
9. All Task 3.3 rows remain unchanged.
10. The Qwen dense winner identity remains frozen.
11. Protected TEST remains unopened.
12. Official TEST usage remains 0/3.
13. LanceDB version matches the project's pinned/runtime version.
14. Task 2.10 hashing code is available.
15. Task 2.11 run logging is available.
16. Existing evaluation metric implementations are available.
17. No paid API is required.

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Record exact counts before implementation.

---

# Stage 2/10 — Audit the installed LanceDB FTS API

Print:

```text
[STAGE 2/10] Audit LanceDB-native FTS behavior
```

Do not code against memory or a different LanceDB version.

Inspect the **installed project version** and the repository's current LanceDB usage.

Before touching the real corpus, build a tiny disposable synthetic table under a temp/artifact path and verify the actual installed API for:

```text
FTS index creation
indexed text column
index replacement behavior
search invocation
query syntax
top-k limit
returned score field name
score direction
result ordering
index-list introspection
index persistence after reopen
```

Use only the installed LanceDB API.

Do not add a second search engine such as Elasticsearch, OpenSearch, Whoosh, SQLite FTS, Tantivy directly, or a custom BM25 package.

Task 3.4 specifically establishes the **LanceDB-native** sparse baseline.

## Required synthetic ranking probe

Create tiny documents where expected lexical ranking is hand-checkable.

For example:

```text
A: "revenue revenue revenue increased"
B: "revenue increased"
C: "net income decreased"
D: "risk factors cybersecurity"
```

Run queries such as:

```text
revenue
revenue increased
cybersecurity
```

Record:

```text
returned field containing sparse score
whether larger or smaller score is better
actual rank order
whether exact query terms are matched
```

Do not assume the score is named `_score`, `_distance`, or anything else until verified.

If LanceDB's native FTS does not expose enough information to build a stable sparse baseline in the installed version, STOP and report the exact limitation.

---

# Stage 3/10 — Freeze the sparse retrieval contract

Print:

```text
[STAGE 3/10] Freeze sparse retrieval contract
```

Create a tracked config such as:

```text
configs/phase_3_4_bm25_fts_baseline.json
```

Use Task 2.10 canonical hashing / `semantic_hash()`.

Do not invent a new hash implementation.

The formal sparse contract should be intentionally simple and untuned.

At minimum freeze:

```text
task
experiment_version

eval_split
eval_scope_kind
eval_scope_sha256
question_count
question_ids_sha256

chunk_config_hash
split_mode
window_size_tokens
overlap_tokens
chunk_count

sparse_backend:
  lancedb_native_fts

lancedb_version
table_name
indexed_column
fts_index_name if applicable

analyzer/tokenizer policy if exposed by the installed API
stemming policy if exposed
stopword policy if exposed
case-normalization policy if exposed

query_transform:
  raw user question unless roadmap explicitly says otherwise

candidate_k:
  50

generation_enabled:
  false

reranker_enabled:
  false

metadata_prefilter_enabled:
  false

metric_schema_version
winner/comparison policy if applicable
```

## No lexical tuning in Task 3.4

Use the simplest documented/default LanceDB-native FTS configuration unless the CURRENT roadmap explicitly requires a specific analyzer.

Do not tune:

- stopword lists;
- stemming language;
- field boosts;
- query expansion;
- synonyms;
- acronym dictionaries;
- phrase boosts;
- SEC-specific keyword dictionaries;
- BM25 `k1`/`b` if the native API does not expose them as part of a frozen roadmap contract.

The purpose is a defensible **initial sparse baseline**, not lexical optimization.

If the installed API exposes a required parameter whose value is genuinely ambiguous and the roadmap does not resolve it, STOP before the formal real-corpus build and report the options.

---

# Stage 4/10 — Build the FTS index on the frozen Task 3.2 chunks

Print:

```text
[STAGE 4/10] Build LanceDB FTS index
```

The FTS corpus must be the exact Task 3.2 winner chunk corpus:

```text
fixed 256 tokens
overlap 0
same chunk IDs
same document IDs
same text
same metadata
```

Do not regenerate text with a different normalizer.

Do not rechunk.

Do not index Task 3.1's 512-token chunks.

Do not index Task 3.3 embedding output as the textual source when the canonical chunk artifact is available.

## Table strategy

Inspect the current storage/index conventions and choose the least destructive compatible strategy.

Valid examples include:

- add an FTS index to a dedicated copy/table of the frozen chunk corpus; or
- create a dedicated sparse-index LanceDB artifact keyed by the Task 3.2 chunk identity.

Do **not** mutate the trusted Task 3.3 dense artifact in place if that risks changing its identity or invalidating prior results.

Prefer a separate sparse artifact identity unless the repository already has an established immutable-safe multi-index convention.

Record exactly what was done.

## Sparse artifact identity

Its identity must include at least:

```text
chunk_config_hash
LanceDB version
FTS backend/config
indexed column
table/index name
```

Use canonical Task 2.10 hashing for the config identity.

## Build validation

After index creation, verify:

```text
source chunk count == searchable row count
unique chunk IDs preserved
document IDs preserved
text preserved exactly
metadata preserved
FTS index exists
expected text column is indexed
artifact reopens successfully in a fresh process
```

Also record:

```text
FTS build time
artifact size before FTS if measurable
artifact size after FTS
incremental FTS index size if measurable
peak RAM/RSS if already available
```

Do not commit the large index artifact.

---

# Stage 5/10 — Implement a sparse retriever boundary

Print:

```text
[STAGE 5/10] Implement sparse retriever
```

Add a small reusable retrieval boundary rather than putting all logic in the benchmark script.

A reasonable design could be:

```text
src/retrieval/sparse.py
```

with something like:

```text
SparseRetriever.retrieve(question, k=50)
```

but follow existing repository patterns.

Requirements:

- validate non-empty string question;
- validate positive integer `k`;
- use only the frozen native FTS query path;
- preserve native sparse ranking order;
- expose a stable application-level result schema;
- return chunk/document metadata needed by evaluation;
- do not return internal full index objects;
- do not run dense embedding;
- do not call an LLM;
- do not rerank.

## Score contract

Because the native FTS score field/direction must be discovered in Stage 2:

- preserve the native score faithfully;
- document whether higher or lower is better;
- do not rename it to "cosine score";
- do not convert it into a fake probability;
- do not normalize scores across queries;
- do not combine it with dense scores in Task 3.4.

If a generic retrieval result schema needs a normalized field name, use a semantically honest name such as:

```text
sparse_score
```

while documenting the native source field.

---

# Stage 6/10 — Query robustness smoke tests before formal evaluation

Print:

```text
[STAGE 6/10] Sparse-query robustness smoke
```

Before the 89-question formal run, test representative query shapes using the real sparse artifact:

```text
normal sentence
mixed uppercase/lowercase
punctuation
percent sign
currency symbol
year / number
hyphenated term
slash
parentheses
Unicode punctuation
SEC terms such as "Item 1A", "10-K", "R&D"
```

Also test malformed/edge inputs:

```text
empty string
whitespace only
non-string
k=0
negative k
boolean k
```

The application retriever should reject malformed inputs clearly.

Do not modify the query based on smoke-result quality.

This stage is API correctness, not tuning.

If the native FTS parser has syntax-sensitive characters that cause ordinary natural-language SEC questions to error, implement only the minimum deterministic escaping/sanitization required for safe literal natural-language search.

If such escaping is needed:

1. document the exact rule;
2. test it heavily;
3. freeze it before formal evaluation;
4. do not add semantic query expansion.

---

# Stage 7/10 — Formal sparse-only evaluation on the frozen 89 questions

Print:

```text
[STAGE 7/10] Evaluate sparse-only baseline
```

Run exactly the frozen 89 DEV questions.

Retrieve top 50 sparse chunks for every retrieval-applicable question.

Generation remains OFF.

Dense retrieval remains OFF for the formal sparse-only row.

For every query save git-ignored diagnostics:

```text
question_id
gold_document_ids

ranked chunk_ids 1..50
ranked document_ids 1..50
native sparse scores 1..50

first gold-document hit rank
hit@10
hit@50
reciprocal_rank
ndcg@10

fts_search_ms
total_retrieval_ms
```

Use the same corrected document-level metric semantics established in Task 3.1:

- repeated chunks from the same relevant document do not create repeated relevance gain;
- ranking is derived from the returned chunk sequence;
- first gold-document hit controls MRR;
- document relevance must be deduplicated correctly for nDCG.

## Required metrics

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

## N/A metrics

Without valid chunk-level gold:

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

Do not encode N/A as zero.

## Task 2.11 run provenance

Create a normal DEV run record through the existing Task 2.11 run logger.

Use a clear run kind such as:

```text
phase3_bm25_fts_sparse_baseline
```

Record at least:

```text
run_id
git_sha
dirty state
eval set/split identity
scope hash
question count
chunk_config_hash
sparse config hash
LanceDB version
FTS configuration
candidate_k
metrics
timings
timestamp
```

No TEST linkage for a DEV run.

---

# Stage 8/10 — Compare sparse vs dense without creating hybrid retrieval

Print:

```text
[STAGE 8/10] Dense-vs-sparse comparison
```

Compare Task 3.4 sparse-only results against the frozen Task 3.3 Qwen dense winner.

This is an **analysis only**.

Do not fuse result sets.

Use paired comparison on the same 89 IDs.

Report:

```text
Sparse vs Qwen dense:

delta doc_recall@10
delta doc_recall@50
delta doc_mrr
delta doc_ndcg@10
```

Also classify per-question complementarity:

```text
both hit@10
dense-only hit@10
sparse-only hit@10
neither hit@10

both hit@50
dense-only hit@50
sparse-only hit@50
neither hit@50
```

This complementarity table is extremely important because it provides evidence for whether a later hybrid task is likely to add value.

Also record first-hit-rank comparison:

```text
sparse better
dense better
same
```

## Paired uncertainty

Use the existing Phase 3 paired-bootstrap convention if still authoritative:

```text
seed:        42
iterations:  10,000
unit:        question_id
```

Report 95% paired bootstrap intervals for metric deltas.

Do not call sparse "better" or "worse" solely from a tiny decimal difference.

## Important interpretation rule

Task 3.4 does **not** need sparse-only to beat Qwen dense retrieval.

A valid successful outcome is:

```text
dense is stronger overall,
but sparse uniquely recovers some dense misses
```

That would be valuable evidence for Task 3.5 hybrid retrieval.

Do not discard sparse merely because its standalone aggregate MRR is lower.

Do not force a winner if Task 3.4's roadmap goal is baseline establishment rather than component elimination.

---

# Stage 9/10 — Ablation table and result artifact

Print:

```text
[STAGE 9/10] Record Task 3.4 result
```

Preserve:

- row 0 unchanged;
- all Task 3.2 rows unchanged;
- all Task 3.3 rows unchanged.

Append the Task 3.4 sparse-only row.

Recommended row fields:

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

dense_embedding_model
dense_embedding_revision
dense_embedding_dimension
dense_used_in_this_row

retrieval_mode
sparse_backend
lancedb_version
fts_indexed_column
candidate_k

doc_recall_at_10
doc_recall_at_10_hits
doc_recall_at_50
doc_recall_at_50_hits
doc_mrr
doc_ndcg_at_10

delta_vs_qwen_dense_recall10
delta_vs_qwen_dense_recall50
delta_vs_qwen_dense_mrr
delta_vs_qwen_dense_ndcg10

dense_only_hits_at_10
sparse_only_hits_at_10
dense_only_hits_at_50
sparse_only_hits_at_50

fts_build_seconds
fts_index_size_bytes
fts_search_latency_p50_ms
fts_search_latency_p95_ms
retrieval_latency_p50_ms
retrieval_latency_p95_ms

notes
```

For `dense_used_in_this_row`:

```text
false
```

but keep the frozen dense model identity for provenance/future comparison.

## Result JSON

Create:

```text
results/phase_3_4_bm25_fts_baseline.json
```

Include:

```text
experiment/config identity
frozen 89-question scope identity
Task 3.2 chunk identity
Task 3.3 dense winner identity
LanceDB version
native FTS contract
index/build statistics
sparse metrics
raw hit counts
latencies
paired sparse-vs-dense deltas
bootstrap intervals
complementarity counts
notable dense-only / sparse-only question IDs
limitations
next-task readiness
```

Do not store protected TEST data.

Do not copy full question/evidence payloads into tracked result files unless the repository already permits it.

---

# Stage 10/10 — Tests, documentation, Git, and stop

Print:

```text
[STAGE 10/10] Verify and close Task 3.4
```

## Required tests

Add deterministic tests covering at least:

1. FTS config hash determinism.
2. Config hash changes when indexed column/backend semantics change.
3. Frozen Task 3.2 chunk hash is required.
4. Frozen 89-question scope is required.
5. Sparse artifact row count matches source chunk count.
6. Chunk IDs preserved.
7. Document IDs preserved.
8. Text preserved.
9. FTS index existence verification.
10. FTS index persistence after reopen.
11. Native score field handling.
12. Native score direction handling.
13. Ranking order preserved.
14. `k` positive integer validation.
15. empty/whitespace query rejection.
16. non-string query rejection.
17. punctuation query safety.
18. numeric/year query safety.
19. Unicode query safety.
20. special SEC lexical forms such as `10-K`, `Item 1A`, and `R&D`.
21. no dense embedding call in sparse retriever.
22. no generation call.
23. no reranker call.
24. no router/CRAG call.
25. no metadata pre-filter.
26. candidate depth = 50.
27. document Recall@10 correctness.
28. document Recall@50 correctness.
29. MRR correctness.
30. document nDCG deduplication correctness.
31. N/A distinct from zero.
32. Task 2.11 run provenance valid.
33. paired sparse-vs-dense comparison correctness.
34. dense-only/sparse-only complementarity classification correctness.
35. deterministic bootstrap with seed 42.
36. row 0 cannot be overwritten.
37. Task 3.2 rows cannot be rewritten.
38. Task 3.3 rows cannot be rewritten.
39. Task 3.4 row contains config/run/Git identities.
40. TEST split is rejected.
41. protected TEST access module/file is never touched by the Task 3.4 runner.
42. portable tests perform no network/API calls.
43. prior Phase 1/2/3.1/3.2/3.3 tracked result artifacts remain unchanged.

Use tiny synthetic fixtures for portable tests.

Do not build the full real FTS index inside pytest.

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
project_plan/PHASE3_BM25_FTS_BASELINE.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

`Progress.md` must record:

- exact LanceDB version;
- actual installed FTS API behavior;
- indexed field;
- tokenizer/analyzer defaults actually used;
- FTS config hash;
- chunk count;
- FTS build time;
- sparse index size;
- R@10, R@50, MRR, nDCG@10;
- raw hit counts;
- p50/p95 sparse latency;
- paired deltas vs Qwen dense;
- dense-only / sparse-only complementarity;
- limitations;
- protected TEST status;
- test counts;
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
LanceDB data files
FTS index files
embedding arrays
model weights/cache
*.duckdb
*.parquet
.env
API keys
large logs
```

Commit only:

```text
source
tests
config
small result JSON/CSV
documentation
Progress.md
```

Suggested coherent commit names:

```text
Add LanceDB sparse retrieval baseline
Evaluate Phase 3 BM25 FTS baseline
```

Use honest history.

No Phase 3 completion tag.

---

# Visible progress requirements

Long operations must run in the foreground with visible progress.

For FTS build:

```text
[FTS] preparing table...
[FTS] rows=323971
[FTS] creating native full-text index on text...
[FTS] build complete elapsed=... size=...
```

For evaluation:

```text
[SPARSE EVAL]  10/89  11.2%  hits@10=... hits@50=... p50_ms=...
[SPARSE EVAL]  20/89  22.5%  hits@10=... hits@50=... p50_ms=...
```

Do not hide formal work in a detached/background shell.

Do not redirect all useful output to a hidden log.

If the runner supports `--status`, status must be read-only and must not mutate artifacts.

---

# Suggested CLI shape

Reuse existing Phase 3 orchestration patterns where practical.

A reasonable interface is:

```powershell
python -u scripts/run_phase3_bm25_fts_baseline.py --plan
python -u scripts/run_phase3_bm25_fts_baseline.py --build
python -u scripts/run_phase3_bm25_fts_baseline.py --evaluate
python -u scripts/run_phase3_bm25_fts_baseline.py --compare
```

or:

```powershell
python -u scripts/run_phase3_bm25_fts_baseline.py --run
```

Do not create redundant orchestration if the repository already has a clean shared experiment runner.

---

# Formal completion display

At completion print:

```text
PHASE 3 — TASK 3.4 LANCEDB BM25 / FTS BASELINE
===============================================

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
  chunk_count:                   ...

Frozen dense winner:
  model:                         Qwen/Qwen3-Embedding-0.6B
  revision:                      97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
  dimension:                     1024
  used for sparse scoring:       NO

Sparse baseline:
  backend:                       LanceDB-native FTS
  LanceDB version:               ...
  indexed column:                text
  analyzer/tokenizer:            ...
  score field:                   ...
  score direction:               ...
  candidate depth:               50
  sparse config hash:            ...

Sparse quality:
  doc_recall@10:                 .../89 = ...
  doc_recall@50:                 .../89 = ...
  doc_mrr:                       ...
  doc_ndcg@10:                   ...

Qwen dense reference:
  doc_recall@10:                 88/89
  doc_recall@50:                 89/89
  doc_mrr:                       0.9251
  doc_ndcg@10:                   0.9407

Paired sparse vs dense:
  delta R@10:                    ...
  delta R@50:                    ...
  delta MRR:                     ...
  delta nDCG@10:                 ...
  95% bootstrap intervals:       ...

Complementarity:
  dense-only hit@10:             ...
  sparse-only hit@10:            ...
  both hit@10:                   ...
  neither hit@10:                ...

  dense-only hit@50:             ...
  sparse-only hit@50:            ...
  both hit@50:                   ...
  neither hit@50:                ...

Sparse engineering:
  FTS build time:                ...
  FTS/index size:                ...
  search latency p50:            ...
  search latency p95:            ...

Ablation table:
  row 0:                         UNCHANGED
  Task 3.2 rows:                 UNCHANGED
  Task 3.3 rows:                 UNCHANGED
  Task 3.4 sparse row:           APPENDED

Protected TEST:
  opened:                        NO
  official runs used:            0/3

FinanceBench:
  rerun for tuning:              NO

Paid API calls:
  0

Tests:
  doctor:                        ...
  portable:                      ...
  full:                          ...

Git:
  experiment branch:             ablation/bm25-fts
  commits:                       ...
  integration outcome:           ...
  Phase 3 tag:                   NOT CREATED

TASK 3.4 STATUS:
  COMPLETE

PHASE 3 STATUS:
  IN PROGRESS

NEXT ROADMAP TASK:
  <read exact next task number/title from current PROJECT_EXECUTION.md>
```

Then STOP.

Do not start the next task automatically.

---

# Hard stop conditions

STOP and report rather than guessing if:

1. Task 3.3 is not actually complete.
2. Task 3.2 chunk winner identity changed.
3. the 256/0 chunk artifact is missing or inconsistent.
4. the 89-question scope cannot be reproduced.
5. row 0 changed unexpectedly.
6. Task 3.2 rows changed unexpectedly.
7. Task 3.3 rows changed unexpectedly.
8. the Qwen dense winner identity changed unexpectedly.
9. the installed LanceDB version lacks a usable native FTS path.
10. native FTS ranking/score semantics cannot be verified.
11. building FTS would require changing chunk text.
12. building FTS would require rechunking.
13. a separate external sparse-search package is proposed.
14. BM25 hyperparameter tuning is proposed without roadmap authorization.
15. query expansion/synonyms/SEC dictionaries are proposed.
16. hybrid fusion/RRF is introduced.
17. dense and sparse scores are combined in Task 3.4.
18. reranking is introduced.
19. metadata pre-filtering is introduced.
20. generation is introduced.
21. FinanceBench is proposed as the tuning set.
22. TEST would need to be opened.
23. an official TEST run would be consumed.
24. chunk metrics are proposed without chunk gold.
25. N/A metrics would be converted to zero.
26. a new hash implementation duplicates Task 2.10.
27. a new run-log format duplicates Task 2.11.
28. the formal sparse run uses a different question set than Tasks 3.1–3.3.
29. the FTS artifact would overwrite the trusted dense artifact in a way that changes prior provenance.
30. large FTS/LanceDB artifacts are about to be committed.
31. secrets/API keys are about to be committed.
32. prior frozen Phase 1/2/3 results are modified unexpectedly.

---

# Success criteria

Task 3.4 is complete only when:

- Task 3.2 fixed 256/0 chunks remain frozen;
- Task 3.3 Qwen dense winner remains frozen;
- LanceDB-native FTS behavior is verified against the installed version;
- a simple untuned sparse contract is frozen;
- the exact frozen chunk corpus is indexed;
- the exact same 89 DEV questions are evaluated;
- top-50 sparse results are produced;
- R@10, R@50, MRR, and nDCG@10 are recorded with raw counts;
- latency/build/index-size measurements are recorded;
- dense-vs-sparse paired deltas are reported;
- dense-only and sparse-only complementary hits are reported;
- no hybrid fusion has been implemented yet;
- the Task 3.4 row is appended without altering earlier rows;
- TEST remains unopened at 0/3;
- no paid API calls are made;
- all regression tests pass;
- Task 3.4 is documented and committed;
- the next roadmap task has not started.
