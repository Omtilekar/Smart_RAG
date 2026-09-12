# Phase 3 Ablation Table Maintenance

Task 3.13. `project_plan/PROJECT_EXECUTION.md`'s requirement is
maintenance, not a new experiment: "Every row must be reproducible from
config + git SHA." This audit verifies that invariant holds across all
19 rows accumulated by Tasks 3.1-3.12, and presents the roadmap's own
example summary structure populated with real numbers.

## Reproducibility audit (this task's verification)

- **git_sha**: every row's `git_sha` was checked with `git cat-file -e
  <sha>` against the live repository history - all 19 resolve to a real
  commit.
- **config hash**: for every row with a checked-in `configs/phase_3_*.json`
  contract (Tasks 3.4-3.12; earlier rows 0/A/B/C and the four Task 3.3
  embedding candidates predate the one-config-file-per-task convention
  and instead hash their chunk/embedding identity directly), the
  config file was re-hashed with the same canonical
  `src.artifacts.versioning.semantic_hash()` (Task 2.10) used to build
  the row, and the result was compared against the row's own
  `phase3_config_hash`:

```text
bm25_fts                match
hybrid_rrf               match
ce_minilm_l6             match
crag_confidence          match
rules_router             match
metadata_prefilter       match
xbrl_sql_path            match
derived_calculations     match
tree_section_navigation  match
```

- Every row's `row_id`, `phase3_config_hash`, `run_id`, and `git_sha`
  fields are non-empty (checked programmatically over all 19 rows).
- Row 0 and every prior task's row remain byte-for-byte unchanged in
  their pre-existing columns as of this audit (verified continuously at
  the close of every task since Task 3.4; re-confirmed here for the
  full 19-row table).

No code changed for this task - it is a verification-only checkpoint.

## Roadmap's example structure, populated

The roadmap's example table names a `Configuration` progression through
the core retrieval stack. Populated with the single most representative
row per stage (dense-only baseline through the router/filtering stage):

| Configuration | Recall@50 | MRR | nDCG@10 | Precision@5 | Refusal metric | Latency (p50 ms) |
|---|---:|---:|---:|---:|---:|---:|
| Vector baseline (row `0`, Task 3.1) | 0.9551 | 0.8051 | 0.8332 | N/A | N/A | 233.3 |
| + better chunks/embed (row `qwen3_embedding`, Task 3.3) | 1.0000 | 0.9251 | 0.9407 | N/A | N/A | 588.5 |
| + BM25/RRF (row `hybrid_rrf`, Task 3.5 - **negative result**, dense-only selected) | 1.0000 | 0.9457 | 0.9566 | N/A | N/A | 613.8 |
| + reranker (row `ce_minilm_l6`, Task 3.6 - **negative result**, no_rerank selected) | 1.0000 | 0.6580 | 0.7074 | 0.1551 | N/A | 686.4 |
| + CRAG (row `crag_confidence`, Task 3.7) | N/A | N/A | N/A | N/A | 0.1681 (missed_failure_rate) | 595.0 |
| + router/filtering (row `metadata_prefilter`, Task 3.9) | 1.0000 | 1.0000 | 1.0000 | N/A | N/A | 573.5 |

Notes on reading this table:

- Rows are independent experiments against the frozen 89-question DEV
  scope, not a literally-stacked pipeline - e.g. `ce_minilm_l6` reranks
  the dense-only candidate pool, not the hybrid pool, because Task 3.5's
  hybrid result was a negative result and dense-only remained the
  frozen upstream winner for Task 3.6. This matches the ablation
  table's actual selection history; see each task's own
  `project_plan/PHASE3_*.md` for the exact frozen upstream inputs.
  `metadata_prefilter`'s ranking metrics look "perfect" because its
  candidate pool is restricted to one document's own chunks (see
  `project_plan/PHASE3_METADATA_PREFILTERING.md`), not because it
  strictly dominates every other row on a shared candidate pool.
  `ce_minilm_l6`'s MRR/nDCG@10 look worse than the dense-only baseline
  precisely because the negative result means reranking hurt these
  metrics on this 89-question scope - the table is intentionally
  honest about this, not filtered to only show wins.
  `crag_confidence` has no ranking metrics (retrieval columns `N/A`)
  because it studies a refusal-decision layer, not retrieval ranking;
  its meaningful column is `missed_failure_rate` (the `refusal_metric`
  alias).
- `rules_router` (classification-only, Task 3.8), `xbrl_sql_path`
  (Task 3.10), `derived_calculations` (Task 3.11), and
  `tree_section_navigation` (Task 3.12) are all structural/no-retrieval
  paths and are correctly `N/A` across every ranking column - they are
  not part of this dense-retrieval progression table by design.

## Full table

The authoritative, complete 19-row x 118-column table lives at
`results/phase_3_ablation_table.csv` and is the source of truth this
document summarizes - never the reverse. Load it directly for any
column not shown in the summary above.

## Regression gates

Read-only audit: no source changed, no new evaluation run, no new
config, no ablation-table row appended. `scripts/dev.py doctor`/
`test --portable`/`test` all re-verified green immediately before this
audit (Task 3.12's own closeout); protected TEST remains at 0/3.

## Next roadmap task

Phase 3, Task 3.14 - re-check against the Phase 0 serving budget (per
`project_plan/PROJECT_EXECUTION.md`'s exact numbered contract).
