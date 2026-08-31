# Phase 1 End-to-End Commands

Established in Task 1.11, the final numbered Phase 1 task. Gives
`src/cli/` its first real purpose: two thin local commands that
orchestrate the already-built Phase 1 stack. **No FastAPI, no server, no
new retrieval/generation logic** — this is integration/orchestration only.

## Commands

```bash
python -m src.cli.phase1 answer --question "..."
python -m src.cli.phase1 evaluate
```

```bash
python -m src.cli.phase1 --help
```

lists both subcommands.

## Answer path

```text
question
  → Task 1.6 BaselineRetriever.retrieve(question, k=5)
  → Task 1.7a MinimalGenerator + OpenRouterProvider
  → answer + strict-parsed [chunk_id] citations
  → printed to console
```

`src/cli/phase1.py` reuses `BaselineRetriever`, `MinimalGenerator`, and
`OpenRouterProvider` exactly as built in Tasks 1.6/1.7/1.7a — no
retrieval or generation logic is reimplemented. Output:

```text
Answer:
<generated answer, printed verbatim - never repaired/normalized>

Citations:
- <chunk_id>
- <chunk_id>
```

or, when the strict parser found zero citations:

```text
Citations:
(none)
```

Malformed citation attempts (e.g. fullwidth `【...】`) are never converted
or hidden — the printed answer is exactly what the model returned, and the
printed citation list is exactly Task 1.7's strict `parse_citations()`
output.

**Generation-context `k` stays 5**, unchanged from Task 1.7 — never
switched to Task 1.10's retrieval-evaluation `k=10`. These are
deliberately different numbers for different purposes:

```text
generation context k = 5   (Task 1.7's frozen prompt-context size)
retrieval evaluation k = 10  (Task 1.10's frozen doc_recall@10 cutoff)
```

### Error handling

Missing/invalid `GENERATION_PROVIDER`, missing `GENERATION_MODEL`, missing
`OPENROUTER_API_KEY`, retriever/model-load failure, or a provider error
all print a concise message to stderr and exit non-zero — never a raw
traceback, never the API key.

### Diagnostic-only `--dump-context` flag

`answer` also accepts a hidden (`argparse.SUPPRESS`ed from `--help`)
`--dump-context PATH` flag, used once during this task to mechanically
verify the live demo's citations without a second OpenRouter call. When
set, it wraps retrieval with Task 1.8's `RecordingRetriever` (never a new
mechanism) and writes the exact supplied top-5 chunk IDs plus a
`src.eval.citation_integrity.evaluate_citation_integrity()` result to that
path. This mirrors `MinimalGenerator._answer_with_diagnostics`'s own
already-established precedent (documented in `PHASE1_GENERATION.md` as
"diagnostic-only, not part of the public Phase 1 answer contract") — it is
not part of the documented two-subcommand contract above.

## Evaluate path

```text
Task 1.9 frozen 200 questions
  → Task 1.6 BaselineRetriever.retrieve(question, k=10)
  → Task 1.10 doc_recall@10 (hit if any of the 10 chunk results'
    document_id == target_document_id)
  → printed + saved
```

`cmd_evaluate()` in `src/cli/phase1.py` imports and calls
`scripts.run_baseline_metric.run()` directly — the exact same function
`scripts/run_baseline_metric.py`'s own `main()` calls, refactored (Task
1.11) into a reusable, zero-semantic-change function that accepts an
optional output path. **The doc_recall@10 arithmetic exists in exactly one
place**, `src/eval/baseline_metrics.py` — this CLI command does not
duplicate hit-counting, first-hit-rank, or category-aggregation logic.

To preserve Task 1.10's historical baseline artifact
(`results/phase_1_10_baseline_metric.json`), the CLI's `evaluate`
subcommand writes its own rerun to a separate tracked path,
`results/phase_1_11_smoke_evaluation.json`, via `run()`'s
`result_relative_path` parameter (default unchanged for direct script
invocation).

## Configuration

`answer` requires:

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=openai/gpt-oss-20b   (the frozen Phase 1 smoke model)
OPENROUTER_API_KEY                    (process environment or local
                                       git-ignored .env)
```

Provider and model remain architecturally replaceable — OpenRouter is
Phase 1's *testing* provider only (see `PHASE1_GENERATION.md`); nothing
here hardcodes a permanent production choice.

`evaluate` requires **no API key** — it never calls generation.

## Outputs (actual, from the one real run each)

```bash
$ python -m src.cli.phase1 evaluate
question_count: 200
hit_count: 194
doc_recall@10: 0.970000
...
Result written to: .../results/phase_1_11_smoke_evaluation.json
```

```bash
$ python -m src.cli.phase1 answer --question "What are the main risk factors described in this filing?"
Answer:
The filing lists several key risk factors ... [1425627_2018.htm::chunk9]

Citations:
- 1425627_2018.htm::chunk9
```

## Known warning

**Task 1.7a's general citation-format compliance remains 8/10** on the
frozen 10-case Task 1.8 smoke (2 residual fullwidth-bracket failures, 0
unknown/out-of-context failures). Task 1.11's one live answer demo (see
below) happened to produce a strict-valid citation with no malformed
attempt — **this single successful case does not supersede or resolve
that 8/10 diagnostic**, which was measured across 10 cases and remains the
governing evidence of general citation-format compliance.

## Live demo (the one paid call this task performed)

Per the task's frozen selection rule, the demo question was chosen
deterministically from tracked prior evidence — the lowest `case_id` among
Task 1.8's `expected_behavior: "answer"` cases that PASSed Task 1.7a's
rerun (`configs/citation_integrity_smoke.json` ∩
`results/phase_1_7a_citation_format_correction_rerun.json`):

```text
selected case_id: citation-smoke-02
selected question: "What are the main risk factors described in this filing?"
```

Run exactly once, no retry:

```text
provider:            openrouter
requested model:        openai/gpt-oss-20b
retrieval k:                5
answer non-empty:              YES
parsed citations:                  1 (1425627_2018.htm::chunk9)
malformed citation attempts:          0
citation exists in index:                YES
citation was in supplied top-5:            YES
citation-integrity status:                     PASS
```

Mechanically verified via `src.eval.citation_integrity.evaluate_citation_integrity()`
against the real Task 1.5 index and the exact recorded top-5 supplied
context for this same generation call (Task 1.8's `RecordingRetriever`
mechanism, reused via the `--dump-context` diagnostic flag) — no second
OpenRouter call was made.

## Non-goals

No FastAPI, no HTTP endpoint, no streaming, no Docker/AWS deployment, no
BM25/hybrid search, no metadata filtering, no reranker, no CRAG, no
router, no guardrail framework, no Phase 2 truth contract. Phase 4 owns
serving; Phase 3 owns retrieval improvement.

## Phase 1 exit review

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | One command accepts a question and returns an answer | PASS | the live demo run returned a non-empty answer |
| 2 | The answer contains valid source citations | PASS | 1 strict-valid citation, 0 malformed attempts, on the one live demo |
| 3 | Every citation resolves back to a stored source chunk | PASS | mechanically verified: exists in index, was in the exact supplied top-5 |
| 4 | A 200-question evaluation runs end to end | PASS | `python -m src.cli.phase1 evaluate` completed successfully |
| 5 | `doc_recall@10` is printed and saved | PASS | 194/200 = 0.970000 printed; saved with `metric_result_sha256` identical to Task 1.10's |
| 6 | Integration bugs found during the vertical slice are documented | PASS | Task 1.7/1.8 citation-format issue and Task 1.7a's 8/10 residual remain documented; no new bug found in Task 1.11 |
| 7 | No advanced retrieval component has been added prematurely | PASS | `git diff` confirms no BM25/hybrid/reranker/CRAG/router/filter code added |

**All 7 official Phase 1 exit criteria are demonstrated on real evidence.**
Phase 1 closes as **COMPLETE WITH WARN** — the known Task 1.7a 8/10
citation-format compliance limitation remains open and is carried forward
as a documented Phase 1 limitation, not silently resolved by this one
successful demo case.

## Next

Phase 2 — Make the Numbers Trustworthy (not started by this task).
