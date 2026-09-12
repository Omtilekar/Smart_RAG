# Phase 3 Exit Audit

Run per `prompts/phase_3/task_3.99_phase3_autonomous_execution_loop.md`'s
own instruction: when the roadmap reports no remaining Phase 3 numbered
implementation tasks, do not immediately declare Phase 3 complete — run
a dedicated exit audit against `project_plan/PROJECT_EXECUTION.md`'s
actual exit criteria first.

## Numbered task completion

| Task | Title | Status | Evidence |
|---|---|---|---|
| 3.1 | Capture the trusted baseline | COMPLETE | `results/phase_3_1_trusted_baseline.json`, row `0` |
| 3.2 | Chunking ablation | COMPLETE | `chunk_config_hash=ba99e2f7...32b06` frozen, rows `A1/A2/B1/B2/C1` |
| 3.3 | Embedding model benchmark | COMPLETE | `Qwen/Qwen3-Embedding-0.6B` selected, rows `bge_small/bge_base/nomic_embed/qwen3_embedding` |
| 3.4 | LanceDB BM25/FTS sparse baseline | COMPLETE | row `bm25_fts` |
| 3.5 | RRF hybrid fusion | COMPLETE (negative) | row `hybrid_rrf`, dense-only selected |
| 3.6 | Cross-encoder reranking | COMPLETE (negative) | row `ce_minilm_l6`, `no_rerank` selected |
| 3.7 | CRAG-style confidence grading | COMPLETE | row `crag_confidence`, threshold=0.5531 (J=0.7644) |
| 3.8 | Rules-first router | COMPLETE | row `rules_router`, accuracy=85.82%, macro_f1=0.8871 |
| 3.9 | Metadata pre-filtering | COMPLETE (positive) | row `metadata_prefilter`, R@10 88→89/89 |
| 3.10 | Structured XBRL SQL path | COMPLETE | row `xbrl_sql_path`, trap_leak_rate=0.00% |
| 3.11 | Deterministic derived calculations | COMPLETE | row `derived_calculations` |
| 3.12 | Simple tree/section navigation | COMPLETE | row `tree_section_navigation`, scope_leak_rate=0.00% |
| 3.13 | Maintain the ablation table | COMPLETE (verification-only) | `project_plan/PHASE3_ABLATION_TABLE_MAINTENANCE.md` |
| 3.14 | Re-check against Phase 0 serving budget | COMPLETE | `results/phase_3_14_serving_recheck.json` |

All 14 numbered Phase 3 subtasks are complete. None deferred.

## Exit criteria (`project_plan/PROJECT_EXECUTION.md`'s own list)

| Exit criterion | Evidence | Status | Notes |
|---|---|---|---|
| Every retained component has a measured justification on DEV | 19-row ablation table, every row config-hash/git-sha reproducible (Task 3.13 audit) | PASS | |
| Final chunking strategy is selected | Task 3.2: `fixed/256/0`, `chunk_config_hash=ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06` | PASS | |
| Final embedding model is selected | Task 3.3: `Qwen/Qwen3-Embedding-0.6B`, 1024-dim, revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | PASS | |
| Hybrid retrieval is benchmarked | Task 3.5: RRF hybrid vs dense-only, paired bootstrap, practical tie on Recall@10 → dense-only retained | PASS | negative result, correctly retained not discarded |
| Reranking is benchmarked | Task 3.6: cross-encoder reranking vs no-rerank, 95% CIs entirely below 0 on MRR/nDCG@10/Recall@5 → `no_rerank` retained | PASS | negative result |
| CRAG thresholds are calibrated on DEV | Task 3.7: Youden's J threshold=0.5531 (J=0.7644) on `top1_score` | PASS | |
| Router accuracy is measured | Task 3.8: accuracy=85.82% (1658/1932), macro_f1=0.8871, scoped to 6/10 intents (4 have zero DEV examples, user-approved) | PASS | |
| SQL and narrative paths are separated correctly | Task 3.8 routes `xbrl_fact`→SQL (3.10)/`numeric_derived`,`cross_entity`→derived calc (3.11); Task 3.10's trap population (139 unanswerable-by-construction questions) never confidently answered: `trap_leak_rate=0.00%` | PASS | hard safety invariant verified at 0% |
| Selected components fit the serving budget measured in Phase 0 | Task 3.14: real stack (Qwen3-Embedding-0.6B dense-only, no reranker) warm p95=1163.0ms → "proceed but constrain reranker/pool" band (reranker constraint trivially met: none selected); Fargate remains the recommended target on the independent, un-overturned cold-start leg | PASS | re-checked, not assumed; decision documented in `project_plan/SERVING_FEASIBILITY.md` |
| Architecture is stable enough to scale once | Full 323,971-chunk / 1,493-document frozen corpus used throughout Tasks 3.2-3.14 (not a toy sample); every component (router, SQL, derived-calc, nav) built on frozen, reused Phase 2 primitives (`truth_contract`, `tag_registry`, canonical hashing) rather than one-off logic | PASS | qualitative judgment, not a numeric threshold in the roadmap |

**All 9 exit criteria PASS.**

## Controller invariants (`task_3.99`'s own checklist)

| Invariant | Status | Evidence |
|---|---|---|
| All numbered Phase 3 tasks complete or explicitly documented as deferred | PASS | 3.1-3.14, none deferred |
| Row 0 preserved | PASS | `row_id="0"`, `phase3_config_hash` unchanged since Task 3.1 |
| All ablation rows present | PASS | 19 rows: `0, A1, A2, B1, B2, C1, bge_small, bge_base, nomic_embed, qwen3_embedding, bm25_fts, hybrid_rrf, ce_minilm_l6, crag_confidence, rules_router, metadata_prefilter, xbrl_sql_path, derived_calculations, tree_section_navigation` |
| All selected winners frozen | PASS | chunking, embedding, retrieval mode, reranker decision, CRAG threshold, router, filter all recorded with config hash + git SHA |
| All negative results retained | PASS | `hybrid_rrf` and `ce_minilm_l6` rows carry their real (unfavorable) metrics, never deleted or overwritten |
| All required DEV metrics present | PASS | doc_recall@10/50, MRR, nDCG@10 present wherever ranking applies; task-specific metrics (accuracy, coverage, exact-match, leak rates) present for structural tasks; `N/A` (never `0`) where a metric genuinely does not apply |
| All config hashes/run IDs/Git SHAs present | PASS | Task 3.13's dedicated audit: 19/19 rows non-empty, 9/9 checked-in configs re-hash to their exact stored `phase3_config_hash`, all 19 `git_sha` values resolve to real commits |
| All regression tests pass | PASS | `scripts/dev.py doctor`: PASS; `test --portable`: 1867 passed, 30 deselected; `test` (full): 1897 passed, 0 skipped |
| Protected TEST discipline intact | PASS | `SELECT COUNT(*) FROM test_access_log WHERE kind='evaluation_access'` = 0; never opened, 0/3 official runs used across all of Phase 3 |
| No Phase 4 work started | PASS | `src/guards/__init__.py` and `src/api/__init__.py` are empty stubs; no FastAPI service, no guardrail logic implemented |

**All controller invariants PASS.**

## Known, honestly-documented gaps (not exit blockers)

- Router (3.8) scoped to 6/10 intents; `numeric_narrative`/`narrative`/`section_summary` have zero DEV examples anywhere in the 1,932-question corpus — user-approved scope decision, documented in `project_plan/PHASE3_RULES_FIRST_ROUTER.md`.
- Derived calculations (3.11) scoped to `difference`/`greater_than`; growth-rate and percentage-of-revenue have zero DEV examples — same pattern, documented in `project_plan/PHASE3_DERIVED_CALCULATIONS.md`.
- Tree/section navigation (3.12) has zero DEV question examples of its target query shape at all; evaluated instead against Task 2.8's own parsed structural corpus (990/1,493 documents) — documented in `project_plan/PHASE3_TREE_SECTION_NAVIGATION.md`.
- No quantization scheme was ever selected or applied to the production LanceDB index (flat/exact search throughout) — an honest gap against Task 3.14's "after the selected quantization" wording, documented in `project_plan/SERVING_FEASIBILITY.md`.
- Task 3.14's serving re-check did not re-measure cold-start latency; it reasoned from model-size comparison instead (documented explicitly as a limitation).

None of these gaps block any of the 9 stated exit criteria or the controller's 10 invariants above — each is scoped, measured where data exists, and documented rather than silently glossed over.

## Verdict

```text
PHASE 3 CONTROLLED EXECUTION LOOP
=================================

Controller status:
  PHASE 3 EXIT REACHED

Last completed task:
  3.14 — Re-check against the Phase 0 serving budget

Current task:
  none (Phase 3 exit audit)

Reason for stop:
  Phase 3 exit audit PASSED - all 14 numbered tasks complete, all 9
  roadmap exit criteria PASS, all 10 controller invariants PASS.

Frozen DEV scope:
  questions: 89
  scope_sha256: 78980d25fa4a0a4971fcc356449ec5453d425a52c9e43d63a88a2c3fae532f68

Selected stack so far:
  chunking: fixed/256/0 (chunk_config_hash=ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06)
  embedding: Qwen/Qwen3-Embedding-0.6B, 1024-dim, revision=97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
  retrieval: dense-only (Task 3.5 hybrid = negative result)
  reranker: none (Task 3.6 = negative result)
  CRAG: top1_score threshold=0.5531 (J=0.7644)
  router: rules-first, accuracy=85.82%, macro_f1=0.8871, 6/10 intents scoped
  metadata filter: cik+fiscal_year pre-filter, selected (positive result)
  SQL path: structured XBRL lookup, trap_leak_rate=0.00%
  derived calc: difference/greater_than, 100% exact-match once attempted
  nav: filing/section navigation, scope_leak_rate=0.00%
  serving target: Fargate/warm-compute preferred (cold-start leg)

Latest trusted metrics (qwen3_embedding, dense-only, frozen 89-question DEV scope):
  R@10: 0.9888 (88/89) baseline; 1.0000 (89/89) with metadata_prefilter
  R@50: 1.0000 (89/89)
  MRR: 0.9251 (dense-only); 1.0000 (metadata_prefilter)
  nDCG@10: 0.9407 (dense-only); 1.0000 (metadata_prefilter)

Protected TEST:
  opened: NO
  official runs used: 0/3

Tests:
  doctor: PASS
  portable: 1867 passed, 30 deselected
  full: 1897 passed, 0 skipped

Git:
  current branch: main
  latest commit: 0cf897b (Task 3.14)
  working tree: clean (Phase 3 work); untracked external supervisor/orchestration files present, not part of Phase 3 deliverables

Ablation table:
  rows: 19
  row 0 intact: YES

NEXT ACTION:
  Phase 4 has NOT been authorized to start by this audit. A human
  decision is required to begin Phase 4 - this controller's scope ends
  at Phase 3 exit.

PHASE 4:
  NOT STARTED
```
