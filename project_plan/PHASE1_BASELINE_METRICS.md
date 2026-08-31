# Phase 1 Baseline Retrieval Metric

**Phase 1 smoke baseline. NOT the final benchmark. NOT a trustworthy
research result.** Established in Task 1.10. This is the first retrieval
metric computed over the Task 1.9 200-question smoke set — a crude,
document-level number meant to prove the vector-only baseline retriever
works end to end, not to make a quality claim. Task 1.9's ground truth is
only document-level (Task 1.3's fixed-window chunker has no chunk-level
gold labels), so Phase 2's truth-contract-backed evaluation is the
methodology that will actually be trustworthy.

## Purpose

```text
200 frozen Task 1.9 questions
        ↓
Task 1.6 BaselineRetriever.retrieve(question, k=10) — exact vector search
        ↓
exactly 10 ranked CHUNK results per question
        ↓
hit if any result.document_id == target_document_id (exact string equality)
        ↓
hit_count / 200
        ↓
doc_recall@10
```

## Metric definition

```text
doc_recall@10 = (number of questions whose target_document_id occurs in
  any of the first 10 retrieved chunk results) / total questions
```

Explicit, frozen semantics:

- The top 10 results are **chunk** results, not deduplicated to distinct
  documents before the cutoff — a question could receive fewer than 10
  distinct documents among its 10 chunks, and the metric never compensates
  for that.
- A hit requires exact string equality between a result's `document_id`
  and the question's `target_document_id` — never CIK, company name,
  fiscal year, filename prefix, filing family, or fuzzy similarity.
- A document occupying multiple of the 10 chunk slots still counts as
  exactly one hit for that question.
- `first_hit_rank` (the minimum rank among matching chunks, `null` if no
  hit) is recorded as a diagnostic only — not part of `doc_recall@10`, and
  never converted into MRR in this task.
- Primary metric name is frozen as exactly `doc_recall@10` — never
  `recall@10`, `chunk_recall@10`, `hit_rate@10`, `accuracy@10`, or MRR.

## Dataset

```text
dataset:               results/phase_1_9_smoke_evaluation.json
question_count:            200
smoke_eval_sha256:            0b2c25dcbde141cafb5694ae748c5131d556d543195158aa3794dec325657a27
                             (independently recomputed before this run, matched)
label_granularity:                document (all 200)
retrieval_metric label:              doc_recall@10 (all 200)
```

## Retriever provenance (unchanged from Task 1.6)

```text
module:              src.retrieval.baseline.BaselineRetriever
k:                       10 (explicit, Task 1.6's own default is 5)
embedding model:            BAAI/bge-small-en-v1.5
embedding revision:            5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
chunk_config_hash:                f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
index table:                        chunks, 162,357 rows, 0 ANN indexes (re-verified)
search mode:                            exact (flat brute-force cosine scan)
distance metric:                            cosine
```

No BM25, no hybrid search, no reranking, no metadata filtering, no CRAG,
no routing, no generation — the deliberately crude Phase 1 vector-only
baseline, unmodified.

## Real run

```text
question_count:      200
hit_count:               194
doc_recall@10:               0.970000
metric_run_config_hash:          d429b0b971d1fdf68eeb93cd526208754842181ee373b7b8fdec5ef085437e5d
metric_result_sha256:                64438c1c5ee0769763a274af8cafd200472116889cbd5ee4b045f37557907328
```

A high recall is expected here and is not itself evidence of a strong
system: Task 1.9's questions are broad, template-generated summaries of
the exact section the target document's own text discusses (e.g. "What
does {company} report about its business...?" targets the filing whose
`section_1` was just used to build that question), so the retriever
mainly has to find *a* semantically on-topic chunk from the right filing
among 10 slots — not resolve any real ambiguity between similar
companies/years. This says the vector-only baseline plumbing works; it
says nothing about retrieval quality on a harder, adversarial, or
fact-specific question distribution. Phase 2's truth-contract-backed
question set is the number that should actually inform architecture
decisions.

## Category diagnostics

| Category | Questions | Hits | doc_recall@10 |
|---|---:|---:|---:|
| business | 40 | 38 | 0.950000 |
| risk_factors | 40 | 37 | 0.925000 |
| mdna | 40 | 39 | 0.975000 |
| market_risk | 40 | 40 | 1.000000 |
| financial_statements | 40 | 40 | 1.000000 |

Descriptive only — not a claim that any category is intrinsically harder
in general; sample size per category is 40, not statistically powered.

## First-hit-rank distribution (descriptive only, not MRR)

| Rank | Count |
|---|---:|
| 1 | 167 |
| 2 | 16 |
| 3 | 5 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 2 |
| 8 | 1 |
| 9 | 0 |
| 10 | 0 |

167 of the 194 hits (86%) land at rank 1 — most hits are found immediately,
consistent with the broad, on-topic nature of Task 1.9's questions.

## Hand checks

10 deterministic cases inspected directly from the written result file:
the first 5 hit cases and first 5 miss cases, ordered by `question_id`
ascending (the sampling rule specified by the task — no cherry-picking).
For each, `target_document_id`, the 10 `retrieved_document_ids`, the
stored `hit`, and the stored `first_hit_rank` were manually re-derived by
inspection and compared against the stored values.

```text
cases checked: 10 (5 hits: phase1-smoke-0001..0005; 5 misses:
  phase1-smoke-0034, 0039, 0042, 0060, 0077)
result: 10/10 PASS - exact target membership and first_hit_rank both
  matched manual re-derivation in every case
```

## Independent aggregate cross-check

After the result file was written, `hit_count` and `doc_recall@10` were
independently recomputed by a separate one-off calculation reading the
written `questions` array directly — never calling
`summarize_doc_recall()` a second time:

```text
independent_hit_count:  194  (matches stored hit_count: 194)
independent_recall:        0.97  (matches stored doc_recall_at_10: 0.97)
```

## Determinism

The full 200-question run was executed twice in independent fresh
processes. Identical: question count, hit count, `doc_recall@10`,
per-question `hit`/`first_hit_rank`, retrieved chunk-ID order, retrieved
document-ID order, and `metric_result_sha256`
(`64438c1c5ee0769763a274af8cafd200472116889cbd5ee4b045f37557907328` both
runs). `metric_result_sha256` deliberately excludes per-question
`question`/`category` text, `retrieved_scores`/`retrieved_distances`, and
all timestamp/runtime fields — only `question_id`, `target_document_id`,
`hit`, `first_hit_rank`, `retrieved_chunk_ids`, and `retrieved_document_ids`
are hashed, so it is robust to any (unobserved here) GPU floating-point
score noise while still being a meaningful identity check on retrieval
results themselves.

## Performance

```text
label:                       Phase 1 evaluation-run diagnostic - NOT a production benchmark
run_seconds:                    26.426 (200 questions, one retrieval call each)
retrieval latency p50:              129.585 ms
retrieval latency p95:                  153.013 ms
```

Consistent with Task 1.6's own retriever smoke diagnostic (~132-154 ms p50)
and Task 1.5's brute-force exact-scan baseline (~143-165 ms p50/p95) —
this is the same unindexed 162,357-row exact cosine scan, not a new or
different workload, and not compared against Task 0.10's separate,
non-binding IVF_PQ serving-spike numbers.

## Limitations

- Document-level target only — no chunk-level gold evidence exists for
  Task 1.9 (Task 1.3's fixed-window chunker has no section-aware labels).
- Template-generated, broad questions — not adversarial, not
  fact-specific, not designed to stress retrieval precision.
- Vector-only exact baseline — no BM25, no metadata filters, no
  reranker, no hybrid fusion.
- No answer-correctness or citation-quality evaluation of any kind — this
  is retrieval only; Task 1.10 never calls generation.
- Task 1.7a's citation-format compliance warning (8/10 on the frozen Task
  1.8 smoke, 2 residual fullwidth-bracket failures) remains open and
  unresolved — Task 1.10 does not exercise generation, so it neither fixes
  nor re-tests that issue.
- Only 40 questions per category — not statistically powered category
  comparisons.
- **Not the final benchmark.** Phase 2's truth-contract-backed ~3,000-
  question evaluation (`PROJECT_EXECUTION.md` Task 2.1–2.6) is the
  methodology intended to produce trustworthy numbers; these 200 questions
  are discarded there, not carried forward.

## Next task

Task 1.11 — one documented end-to-end command (question in, cited answer
out) and one command that runs the 200-question smoke evaluation.

## Reproducing this run

```bash
python scripts/run_baseline_metric.py
```

Reads `results/phase_1_9_smoke_evaluation.json` and the real Task 1.5
LanceDB index read-only, loads `BAAI/bge-small-en-v1.5` offline from local
cache, performs no network access, no generation call, and writes only
`results/phase_1_10_baseline_metric.json` and
`configs/phase_1_10_baseline_metric.json` (both tracked). Verified to
reproduce an identical `metric_result_sha256` across independent
fresh-process runs; refuses to silently overwrite an existing result file
whose `metric_result_sha256` differs.
