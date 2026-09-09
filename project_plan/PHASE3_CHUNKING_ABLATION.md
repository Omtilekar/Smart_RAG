# Phase 3 Chunking Ablation

Established in Task 3.2. A controlled, DEV-only chunking ablation run
against Task 3.1's trusted baseline (row 0), evaluated over the exact
frozen 89-question `DEV/evaluable-subset` — never recomputed per
candidate. Only chunking (window size, overlap, fixed-vs-section-aware
splitting) varies; embedding model, retrieval backend, distance metric,
candidate depth, and every metric implementation stay identical to row 0.

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.2: benchmark 256/512/1024-token
windows, selected overlap values, and fixed-vs-section-aware splitting;
measure retrieval quality **and** index/build implications; select one
winning chunking strategy before Task 3.3's embedding-model benchmark.

## Frozen experiment

`configs/phase_3_2_chunking_ablation.json`
(`phase3_2_config_hash: f199c8817cf60485c3cacc4b26c39ef9d768ce2c632dc91b03134ab90e2ff94a`)
freezes the staged grid, the frozen 89-question scope identity
(`phase3_scope_hash: 78980d25fa4a...`, verified against
`results/phase_3_1_trusted_baseline.json`'s `question_ids` list before
every candidate run — never recomputed), the winner-selection policy, and
the bootstrap seed/iteration count (42 / 10,000), before any new embedding
build started.

## Stage 2 finding: encoder truncation at 512 tokens

`PROJECT_EXECUTION.md` asks for 1024-token chunks, but the frozen
embedding model (`BAAI/bge-small-en-v1.5`) has a verified 512-token
effective passage-embedding limit — `sentence_bert_config.json`'s
`max_seq_length`, `tokenizer_config.json`'s `model_max_length`, and the
underlying BERT's `max_position_embeddings` all read 512, checked
directly against the cached model, not assumed.

Empirically verified (not merely inferred from config): encoding a
>512-token passage through `SentenceTransformer.encode()` is **bit-
identical** to encoding just its first ~510 content tokens — cosine
similarity 1.0, not merely "close." So the 1024-token candidate (`A2`,
labeled `fixed_1024_overlap_0_encoder_truncates_at_512`) is **not** a
lossless 1024-token embedding experiment: only the truncated prefix
reaches the vector, though the full 1024-token chunk text is preserved in
the chunk artifact. No embedding-model change was made to "fix" this —
that is Task 3.3's decision, not Task 3.2's.

## Chunker generalization

`src/chunk/fixed_window.py`'s `build_chunk_config()` gained
`window_size_tokens` / `overlap_tokens` / `split_mode` parameters
(frozen Phase 1 defaults: 512 / 0 / `"fixed"`). `compute_token_windows()`
was already generic (`stride = window_size - overlap`). New
`split_body_into_sections()` splits a normalized document body into
ordered, non-overlapping `(section_id, section_title, char_start,
char_end)` spans on the already-rendered `"## Item ..."` headings
(`src.normalize.edgar_markdown.render_body()`'s own convention) — verified
against the real 1,493-document corpus with zero errors before any
section-aware build ran. Row 0's frozen `chunk_config_hash`
(`f1dc04d4b7...`) is unaffected: it is verified against the on-disk
`configs/chunk_development_corpus.json`, never recomputed through the
generalized function.

`src/eval/phase3_ablation.py` holds the pure Task 3.2 logic: the
candidate registry (Rounds A/B/C), evaluator guards (`assert_frozen_scope`,
`assert_dev_split` — DEV-only, exact 89-ID match, never imports
`test_access`), the paired bootstrap (`paired_bootstrap_delta_ci`, seed
42, 10,000 iterations, resamples question *indices* jointly across both
arms), and the frozen Stage 8 winner-selection rule
(`select_round_winner`).

## Build/orchestration

`scripts/run_phase3_chunking_ablation.py` builds each new candidate's
chunks/embeddings/LanceDB index (reusing Task 1.3-1.5 logic, generalized
off the single row-0 hash), evaluates it over the frozen 89 questions
(reusing Task 1.10/2.6/3.1 metric code unmodified), and never re-embeds a
candidate whose `chunk_config_hash` already has artifacts on disk — B0/C0
resolve to the *same* hash as A1 automatically (chunk identity depends
only on window/overlap/split_mode, not on row label), so they are reused,
never rebuilt, exactly like row 0 (A0).

Embedding is checkpointed every 50 batches (~6,400 chunks) to
`embeddings.checkpoint.npy`/`.json` under the candidate's embeddings
directory, resumable byte-for-byte (verified: a simulated mid-run failure
followed by resume produces vectors identical to an uninterrupted run,
max abs diff 0.0). This was added mid-task after an unrelated, large,
concurrently-running local job (`run_sensitivity_loyo`) repeatedly drove
the machine's available memory low enough that the harness killed the
background build — checkpointing turned each kill from "lose the whole
candidate" into "lose at most a few minutes."

## Results

```text
Row  Configuration                                    Chunks   R@10(hits)   R@50(hits)   MRR      nDCG@10
A0   fixed 512 / overlap 0            (row 0, reused)  162357   0.9213 (82)  0.9551 (85)  0.8051   0.8332
A1   fixed 256 / overlap 0                             323971   0.9326 (83)  0.9775 (87)  0.7984   0.8320
A2   fixed 1024 / overlap 0 (truncated at 512)           81551   0.8652 (77)  0.9326 (83)  0.7376   0.7683
B0   fixed 256 / overlap 0            (= A1, reused)    323971   0.9326 (83)  0.9775 (87)  0.7984   0.8320
B1   fixed 256 / overlap 32 (12.5%)                     369947   0.9101 (81)  0.9888 (88)  0.7638   0.7988
B2   fixed 256 / overlap 64 (25%)                       431210   0.8989 (80)  0.9775 (87)  0.7743   0.8044
C0   fixed 256 / overlap 0            (= B0, reused)    323971   0.9326 (83)  0.9775 (87)  0.7984   0.8320
C1   section-aware 256 / overlap 0                      341822   0.9326 (83)  0.9775 (87)  0.7782   0.8155
```

### Round A — window size

A1 (256 tokens) beats row 0 on the primary priority order (Recall@50
85→87, Recall@10 82→83) with no credible MRR/nDCG@10 regression — the
small negative point-estimate differences (MRR −0.0066, nDCG@10 −0.0012)
have 95% bootstrap CIs that comfortably include 0
(MRR: [−0.065, +0.052]). **Winner: A1.**

A2 (1024 tokens, encoder-truncated) is unambiguously worse on every
metric — the expected consequence of most of each 1024-token chunk being
invisible to the encoder.

### Round B — overlap

None of the overlap variants (12.5%, 25%) is a credible improvement over
B0 (zero overlap) — B1's Recall@50 edge (+1 hit) and every MRR/nDCG@10
delta fall inside the frozen practical-tie band (Recall@50 hit-delta ≤ 1
AND both bootstrap CIs include 0). All three candidates are practically
tied; the pre-frozen engineering tie-break (fewer chunks → smaller
embedding artifact → ...) selects **B0** — fewer chunks (323,971 vs
369,947/431,210), smaller embedding/index artifacts, lower retrieval
latency, zero duplication.

### Round C — fixed vs. section-aware

C1 (section-aware) reproduces C0's Recall@10/@50 *exactly* (83/87, both
metrics) — respecting Item boundaries neither helped nor hurt document-
level recall/rank-position on this scope — while showing a real, if
non-credible-by-CI, MRR/nDCG@10 dip (0.7984→0.7782, 0.8320→0.8155). Both
are practically tied; the tie-break (fewer chunks, simpler policy)
selects **C0** — fixed splitting produces fewer chunks (323,971 vs
341,822) and is the simpler policy by the frozen tie-break's own
definition (`fixed` ranked before `section_aware`).

## Final selected chunking strategy

```text
split_mode:          fixed
window_size_tokens:  256
overlap_tokens:      0
chunk_config_hash:   ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
```

Frozen for Task 3.3. This is a genuine, credible improvement over the
Phase 1 512-token baseline (Recall@50 +2 hits, Recall@10 +1 hit, no
credible MRR/nDCG@10 regression) at roughly double the chunk count and a
proportionally larger embedding/index artifact (see the ablation table's
`chunk_count`/`embedding_artifact_size_bytes`/`index_size_bytes` columns)
and roughly 1.5× the retrieval p50 latency (233ms → 352ms) — an honest
cost/quality trade Task 3.3 and later phases inherit.

## What this ablation does NOT establish

- Anything about full-DEV or TEST retrieval quality — still the same
  89-question, 4.9%-of-DEV evaluable subset inherited from Task 3.1.
- Comparative-question (year-over-year, cross-entity) retrieval quality —
  zero coverage in this scope, unchanged from Task 3.1.
- A lossless 1024-token embedding result (A2) — the encoder's 512-token
  limit means only the truncated prefix was ever measured.
- That overlap or section-awareness are *never* useful — only that
  neither cleared the frozen practical-tie bar at N=89 on this corpus/
  question set.
- Anything about embedding-model choice — Task 3.3's job, deliberately
  untouched here.

## New code

- `src/chunk/fixed_window.py` — generalized `build_chunk_config()`
  (window/overlap/split_mode parameters); `split_body_into_sections()`,
  `section_label_to_id()`.
- `src/eval/phase3_ablation.py` — pure candidate registry, evaluator
  guards, paired bootstrap, frozen winner-selection rule (no I/O, no
  `test_access` import — AST-verified).
- `scripts/run_phase3_chunking_ablation.py` — orchestration (`--plan`,
  `--run --resume`, `--status`, `--compare`); reuses Task 1.3-1.5 build
  logic and Task 1.10/2.6/3.1 metric logic unmodified; checkpointed
  embedding for resumability.
- `configs/phase_3_2_chunking_ablation.json` — frozen experiment config.
- `configs/phase_3_2_chunk_{A1,A2,B1,B2,C1}.json` — per-candidate frozen
  chunk configs (row 0/B0/C0 reuse existing configs, never rebuilt).
- `results/phase3_2/{row_id}.json` — per-candidate metrics, build stats,
  and compact per-question diagnostics (IDs/ranks/deltas only, no
  question/evidence text).
- `results/phase_3_2_round_decisions.json` — the three round-winner
  decisions with rationale.
- `results/phase_3_2_chunking_ablation.json` — the full tracked result:
  every candidate's config/metrics/build stats, paired comparisons vs
  row 0 and vs each round's winner (deltas, bootstrap CIs, gained/lost
  questions, notable rank moves), the final winner, rationale, and
  limitations.
- `results/phase_3_ablation_table.csv` — row 0 preserved exactly; five new
  rows (A1, A2, B1, B2, C1) — B0/C0 excluded as reused-artifact
  duplicates of A1, per the table's own duplicate-hash convention.
- `tests/test_fixed_window_chunker.py` (extended), `tests/test_phase3_ablation.py`,
  `tests/test_phase3_chunking_ablation_script.py` — portable, no GPU/model/network.

## Next

Task 3.3 — embedding-model benchmark, run against the frozen 256-token/
zero-overlap/fixed chunking strategy selected here.
