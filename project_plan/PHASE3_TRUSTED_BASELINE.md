# Phase 3 Trusted Baseline

Established in Task 3.1. Captures row 0 of the Phase 3 ablation table: the
untouched Phase 1 retrieval architecture, evaluated through the now-trusted
Phase 2 evaluation harness, before any optimization begins.

**This is a baseline-capture task, not an optimization task.** Nothing about
chunking, embeddings, retrieval, reranking, routing, or filtering was
changed to produce this result.

## Objective

Task 3.1 answers exactly what `PROJECT_EXECUTION.md` asks: run the Phase 1
architecture through the trusted Phase 2 evaluation harness, store baseline
DEV results, and freeze them as row 0 of the ablation table so every later
Phase 3 change can be measured against a fixed reference point.

The historical Phase 1 200-question smoke result (`doc_recall@10 = 0.97`) is
explicitly **not** this baseline - that question set was discarded in Phase 2
because it predates the XBRL truth contract.

## Stage 2 finding: DEV/index coverage mismatch (2026-09-08)

The Phase 1 development corpus (1,500 filings, 1,493 embedded documents) was
selected independently of Task 2.3's ~2,810-question evaluation set (built
from the full 10,757-CIK XBRL population). Auditing every retrieval-
applicable DEV question's gold target document(s) against the live Phase 1
index found:

```text
DEV total questions:                1,932
retrieval-applicable:                1,819
  fully covered by Phase 1 index:       89   (4.9%)
  partially covered (multi-doc):        35
  not covered:                       1,695
not applicable (adversarial /
  unanswerable/year_outside_window):    113

Coverage by (category, subtype):
  numeric / xbrl_fact:                    81 / 1,402 full
  unanswerable / unsupported_tag:          8 /    68 full
  comparative / year_over_year_difference:  0 /   244 full (23 partial)
  comparative / cross_entity_comparison:    0 /   105 full (12 partial)

Distinct target documents required for full DEV: 1,987
Already present in the 1,493-document Phase 1 index: 112
Missing: 1,875
```

1,875 missing documents exceed the entire existing 1,500-filing dev corpus -
building an evaluation-only corpus to cover them ("Option B") would not be
"small development scale," would take hours of unattended GPU/parsing work,
and risks selecting a corpus specifically shaped around the eval targets.

**User decision (2026-09-08): Option A.** Freeze
`DEV INTERSECT {questions fully covered by the current Phase 1 index}` as an
immutable, deterministic 89-question scope, labeled `DEV/evaluable-subset` -
never presented as full DEV. Comparative questions (YoY, cross-entity) have
**zero** full coverage and are therefore absent from row 0; their MRR/nDCG
cannot be measured until a corpus expansion is explicitly undertaken.

## Frozen scope

```text
phase3_dev_scope_kind:     fixed_evaluable_subset_v1
question_count:            89
  numeric/xbrl_fact:           81
  unanswerable/unsupported_tag: 8
phase3_dev_scope_sha256:   78980d25fa4a0a4971fcc356449ec5453d425a52c9e43d63a88a2c3fae532f68
```

Selection logic lives in `src/eval/phase3_baseline.py` (`select_phase3_dev_scope`) -
pure, deterministic, sorted by `question_id`, never insertion order. Every
question in this scope has exactly one gold target document (numeric/
unsupported_tag shapes only - the only shapes that achieved full coverage),
so Task 1.10's `evaluate_question`/`summarize_doc_recall` single-target
semantics apply directly, unmodified.

## Architecture (unmodified Phase 1)

```text
chunking:      fixed 512 tokens, zero overlap, no section-awareness, no tables
embedding:     BAAI/bge-small-en-v1.5, revision 5c38ec7c...
retrieval:     vector-only, exact cosine (no ANN index)
BM25/hybrid:   NO
reranker:      NO
CRAG:          NO
router:        NO
metadata pre-filter: NO
generation:    disabled for this formal run (retrieval baseline only,
               to avoid hundreds of paid OpenRouter calls for a metric
               that doesn't need them)
```

Frozen artifact identities (verified directly against the live artifacts,
matching Task 2.10's canonical `semantic_hash()`, never assumed):

```text
chunk_config_hash:        f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
embedding_identity_hash:  b39a67c9eb6487fc98f266f23742afd0a30321d98067505802a1e219b27bec84
index_identity_hash:      ace70ee67d8e98e019d221f2a0215a5b88498a0fc5dcbe73ac7ef1277630b111
index row count:          162,357
index document count:     1,493
```

## Bug found and fixed during Task 3.1: nDCG double-counting

The first formal run computed `doc_ndcg@10 = 2.28` - impossible, nDCG is
bounded `[0, 1]`. Root cause: retrieval ranks **chunks**, and the same gold
document can supply more than one chunk inside the top-10 window. The
initial relevance-vector construction marked every occurrence of the target
document relevant, so a single relevant document could be credited more
than once against an IDCG computed for exactly one relevant item.

Fixed via `src.eval.phase3_baseline.document_relevances_at_k()` - marks only
the **first** occurrence of the target document relevant (mirroring Task
1.10's own "one hit maximum" document-hit definition and
`first_hit_rank()`'s minimum-matching-rank convention). Three regression
tests added, including a direct reproduction of the exact ranked-list shape
that produced 2.28. Fixed in a separate commit before the formal run, so the
run's recorded `git_sha` correctly points at the commit that produced its
numbers.

## Formal result (2026-09-08)

```text
Questions evaluated:       89  (DEV/evaluable-subset, Option A)

doc_recall@10:             0.921348   (82/89)
doc_recall@50:             0.955056   (85/89, Phase 3 diagnostic)
doc_mrr:                   0.805056
doc_ndcg@10:               0.833208

chunk_recall@10:           N/A - no internal chunk gold (Task 2.8)
chunk_mrr:                 N/A - no internal chunk gold
precision@5:               N/A - not yet frozen/implemented
refusal metric:            N/A - generation disabled

Retrieval latency p50/p95: 233.3 / 268.6 ms
Query embedding p50:       25.0 ms
Vector search p50:         206.2 ms

run_id:              28547fec-af47-43f4-b995-e02af858b20d
git_sha:             f052b7d506f7cc00cf594e5c2374368382f41543
phase3_config_hash:  18acae71fab0e7ffa4209da2530f26904cecc9dcb9b2c5e32cd791e5fd4a26e4
```

Full detail: `results/phase_3_1_trusted_baseline.json`,
`results/eval_runs/28547fec-af47-43f4-b995-e02af858b20d.json` (Task 2.11
provenance record), `results/phase_3_ablation_table.csv` (row 0).

**Read this number carefully**: 92.1% doc_recall@10 is measured over the
89-question evaluable subset, not full DEV. It says the Phase 1 retriever
finds the right document 92% of the time *when that document is actually in
the corpus* - it says nothing about the other 95.1% of DEV whose target
documents were never embedded. Do not quote this figure as "Phase 1 recall
on Phase 2 DEV" without the scope qualifier.

## What this baseline does NOT establish

- Comparative-question retrieval quality (YoY, cross-entity) - zero full
  coverage, not measured here.
- Full-DEV retrieval quality - only 4.9% of DEV is in scope.
- Answer/citation/faithfulness quality - generation was disabled for this
  run by design (Task 3.1 is a retrieval-only capture).
- Anything about chunk-level relevance - Task 2.8's internal gold evidence
  remains unavailable (`gold_evidence_count = 0`), unchanged by this task.

## New code

- `src/eval/phase3_baseline.py` - pure DEV-scope/coverage-audit/config-hash/
  ablation-table logic (no I/O, no TEST access anywhere - verified by an
  AST-based test, not a substring scan).
- `scripts/run_phase3_trusted_baseline.py` - orchestration; reuses Task
  1.4-1.6's retrieval components and Task 1.10/2.6's metric implementations
  unmodified; writes a Task 2.11 run record, the tracked result JSON, and
  freezes ablation row 0.
- `configs/phase_3_1_trusted_baseline.json` - frozen baseline config
  (Task 2.10 `semantic_hash()`-based identity, `git_sha` excluded from the
  hash per the existing provenance-exclusion convention).
- `results/phase_3_ablation_table.csv` - the Phase 3 ablation table itself;
  row 0 is now frozen and cannot be silently overwritten with a different
  configuration (`src.eval.phase3_baseline.upsert_row`) - a later task may
  only append new rows.
- `tests/test_phase3_trusted_baseline.py` - 63 portable tests plus one
  gated `local_data`/`gpu`/`model` integration test verifying the real
  scope is exactly 89 questions.

## Next

Task 3.2 - chunking ablation, benchmarked against this row-0 reference.
Comparative-category coverage (currently 0%) is an open gap a future task
could close by building the Option B evaluation-only corpus, if the roadmap
decides that investment is worth it before Phase 3 concludes.
