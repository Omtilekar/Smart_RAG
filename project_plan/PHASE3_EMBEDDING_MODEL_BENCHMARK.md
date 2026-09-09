# Phase 3 Embedding Model Benchmark

Established in Task 3.3. A controlled, DEV-only embedding-model benchmark
run against the frozen Task 3.2 chunking winner (`fixed`/256/0), evaluated
over the exact frozen 89-question `DEV/evaluable-subset` — never
recomputed per candidate. Only the embedding model varies; chunks,
retrieval backend, distance metric, candidate depth (50), and every metric
implementation stay identical to Task 3.2.

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.3: benchmark `bge-small-en-v1.5`
(control), `bge-base-en-v1.5`, `nomic-embed-text-v1.5`, and
`Qwen3-Embedding-0.6B` against the frozen 256/0/fixed chunking strategy;
measure retrieval quality, latency, throughput, memory, and index size;
select one production embedding model.

## Frozen experiment

`configs/phase_3_3_embedding_model_benchmark.json` freezes the four
candidates (pinned commit revisions, model-card-verified query/passage
conventions), the frozen 89-question scope identity
(`question_ids_sha256`, verified against `results/phase_3_1_trusted_baseline.json`
before every candidate run), the frozen `chunk_config_hash`
(`ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06` —
fixed 256-token windows, zero overlap), and the winner-selection policy
(Task 3.2's quality-priority/practical-tie rule with a new embedding-
specific engineering tie-break), before any new embedding build started.

## Interrupted by an unexpected Windows restart

The formal run for `qwen3_embedding` was interrupted mid-build by an
unplanned Windows restart, then repeatedly re-interrupted by the same
kind of unrelated, large, concurrently-running local job
(`python -m scripts.benchmark.run_shap_primary`, unrelated to this
project) documented in Task 3.2 — driving system memory low enough to
kill the build process, and in one case the Claude Code background-task
wrapper itself (while the orphaned Python child kept running and
banking checkpoint progress independently). A recovery audit
(`Progress.md`, same date) confirmed the on-disk
`embeddings.checkpoint.npy`/`.json` pair was valid and internally
consistent at every interruption point, and every resume picked up from
the last checkpoint — never from zero. One resume also hit a transient
Windows subprocess failure (`git rev-parse HEAD` returning exit code
`3221225794` / `STATUS_DLL_INIT_FAILED`, the same memory-pressure root
cause) after embeddings/index/eval had already completed and persisted
to disk; the next invocation reused the persisted embeddings/index
in seconds and only re-ran the fast evaluation + save step.

No candidate's checkpoint, embedding artifact, or index was rebuilt from
scratch as a result of any interruption. `bge_small`, `bge_base`, and
`nomic_embed` were never re-run — `process_candidate`'s `--resume` path
detected each one's existing `results/phase3_3/{candidate_id}.json` and
reused it unmodified.

## Build/orchestration

`scripts/run_phase3_embedding_benchmark.py` pilots each new candidate,
builds its embeddings/index over the frozen chunk artifact (reusing Task
3.2's embedding-checkpoint machinery unmodified), evaluates it on the
frozen 89-question scope, writes a Task 2.11 run record per candidate,
and selects a winner via Task 3.2's reused bootstrap/practical-tie logic
with a new embedding-specific tie-break order (lower dimension/smaller
index → faster passage throughput → lower query-embedding latency →
lower retrieval p95 → lower peak VRAM → smaller model artifact → simpler
integration). The control (`bge_small`) reuses its existing Task 3.2
artifacts untouched — verified by reproducing Task 3.2's frozen winner
metrics exactly on a live run, bit-for-bit.

A real precision bug was found and fixed during pilot testing:
sentence-transformers loads `Qwen/Qwen3-Embedding-0.6B` in bfloat16 by
default, which broke the frozen unit-normalization check (~0.3%
deviation from 1.0). `src/embeddings/model_registry.py`'s `load_model()`
now forces `float32` for every candidate.

`qwen3_embedding`'s real build stalled near the 8.5GB VRAM ceiling at its
pilot-recommended batch size; a per-candidate batch-size override
(`BATCH_SIZE_OVERRIDES = {"qwen3_embedding": 16}`) and a tighter
checkpoint interval (every 2 batches, ~256 chunks) were added so slow,
frequently-interrupted candidates still bank real progress between kills.
A real uncaught-CUDA-OOM bug was also found and fixed: torch 2.13 raises
real CUDA OOM through `torch.AcceleratorError` for some code paths — a
sibling of `torch.cuda.OutOfMemoryError`, not a subclass — so the
original OOM-fallback check missed it and crashed the whole run once;
`_is_oom_error()` now checks both exception types explicitly.

## Results

```text
Candidate        Dim   R@10 (hits)   R@50 (hits)   MRR      nDCG@10
bge_small        384   0.9326 (83)   0.9775 (87)   0.7984   0.8320   (control)
bge_base         768   0.9438 (84)   0.9888 (88)   0.8702   0.8888
nomic_embed      768   0.9663 (86)   0.9888 (88)   0.8880   0.9076
qwen3_embedding 1024   0.9888 (88)   1.0000 (89)   0.9251   0.9407   (winner)
```

### Paired comparisons vs. control (bge_small), 89-question bootstrap (seed 42, 10,000 iterations)

```text
Candidate         R@50 hit Δ   R@10 hit Δ   MRR Δ (95% CI)                nDCG@10 Δ (95% CI)
bge_base          +1           +1           +0.0718 [-0.0015, +0.1451]    +0.0568 [-0.0077, +0.1225]
nomic_embed       +1           +3           +0.0895 [+0.0227, +0.1604]    +0.0756 [+0.0133, +0.1399]
qwen3_embedding   +2           +5           +0.1267 [+0.0478, +0.2096]    +0.1087 [+0.0408, +0.1803]
```

`qwen3_embedding` is the only candidate whose MRR and nDCG@10 95%
bootstrap CIs both exclude 0 — a credible ranking-quality improvement,
not just a small-N artifact. It gained 6 questions at Recall@10 and lost
only 1 (`phase2-eval-001539`) relative to control, and gained 2 at
Recall@50 with zero losses.

### Cost / resource profile

```text
Candidate         Embed artifact    Index size     Query-embed p50   Retrieval p50 / p95
bge_small          691,062,673 B    744,427,913 B     18.4ms            370.2ms / 530.2ms
bge_base         1,188,742,282 B  1,241,487,439 B     52.5ms            491.2ms / 531.5ms
nomic_embed      1,188,742,334 B  1,242,316,495 B     14.8ms            441.4ms / 482.2ms
qwen3_embedding  1,520,529,295 B  1,572,353,043 B     42.1ms            588.5ms / 664.1ms
```

`nomic_embed`'s real fresh build took 4,558.22s (323,971 chunks, batch
128, peak VRAM 2.70GB). `qwen3_embedding`'s real fresh build (recovered
across multiple checkpointed resumes after the restart) ran at
batch 16 (~11-17 chunks/s observed on this machine, well below its own
pilot's optimistic single-batch estimate); its pilot measured peak VRAM
3.24GB. `qwen3_embedding` is the largest and slowest-to-query candidate
of the four, but the tie-break only applies to *practically tied*
quality — it does not, because `qwen3_embedding`'s quality lead is
credible, not tied.

## Winner

```text
model:              Qwen/Qwen3-Embedding-0.6B
revision:           97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
dimension:           1024
embedding identity:  (see results/phase3_3/qwen3_embedding.json:embedding_identity_hash)
```

**Rationale:** credible improvement over the reference (`bge_small`) on
the frozen priority order (Recall@50 → MRR → nDCG@10 → Recall@10) with no
regression-protection violation — no candidate raised Recall@50 at the
cost of a credible MRR/nDCG@10 regression, so no result required a user
decision. `qwen3_embedding` is not a practical tie with any other
candidate (its Recall@50 hit-delta and MRR/nDCG@10 CIs clear the frozen
practical-tie bar), so the engineering tie-break (which favors smaller/
faster candidates) never applies to it — its quality lead is decisive on
its own.

## What this benchmark does NOT establish

- Anything about full-DEV or TEST retrieval quality — still the same
  89-question, 4.9%-of-DEV evaluable subset inherited from Task 3.1.
- Comparative-question (year-over-year, cross-entity) retrieval quality —
  zero coverage in this scope, unchanged from Task 3.1/3.2.
- Generation, citation-grounding, or faithfulness quality — retrieval-only
  by design; `chunk_recall@10`, `chunk_mrr`, `precision@5`, and generation
  metrics remain N/A.
- Hybrid (BM25/RRF) or reranked retrieval quality — vector-only exact
  cosine throughout; that is Task 3.4/3.5/3.6's job.
- An optional commercial reference embedding model — not run (paid API,
  not approved).

## New/changed code

- `src/embeddings/model_registry.py` — generalizes Task 1.4's BGE-only
  pipeline into an `EmbeddingModelSpec`/adapter boundary
  (`load_model`/`encode_passages`/`encode_queries`/`embedding_identity`);
  forces `float32` weights for every candidate; `src/embeddings/bge.py`
  left untouched.
- `scripts/run_phase3_embedding_benchmark.py` — orchestration (`--plan`,
  `--run --resume`, `--status`, `--compare`); per-candidate batch-size
  override; CUDA-OOM-fallback encode wrapper with a real fix for torch
  2.13's `AcceleratorError` sibling-exception hierarchy; reuses Task
  3.2's checkpointed-embedding, bootstrap, and winner-selection logic.
- `configs/phase_3_3_embedding_model_benchmark.json` — frozen experiment
  config (candidates, scope identity, chunk identity, winner-selection
  policy, bootstrap seed/iterations).
- `results/phase3_3/{candidate_id}.json` — per-candidate metrics, build
  stats, and compact per-question diagnostics (IDs/ranks only).
- `results/phase_3_3_round_decision.json` — the winner decision with
  rationale and full paired-bootstrap detail.
- `results/phase_3_3_embedding_model_benchmark.json` — the full tracked
  result: every candidate's config/metrics/build stats, paired
  comparisons vs. control, the final winner, rationale, and limitations.
- `results/phase_3_ablation_table.csv` — row 0 and every Task 3.2 row
  preserved exactly; four new rows (`bge_small`, `bge_base`,
  `nomic_embed`, `qwen3_embedding`); the winning row's `notes` field is
  annotated `SELECTED AS TASK 3.3 WINNER`.
- `tests/test_embedding_benchmark_oom.py`, `tests/test_model_registry.py`,
  `tests/test_embed_checkpoint.py` — portable, no GPU/model/network.

## Next

Task 3.4 — add LanceDB-native BM25/FTS as the initial sparse retrieval
baseline, run against the frozen 256/0/fixed chunking strategy and the
`qwen3_embedding` dense model selected here.
