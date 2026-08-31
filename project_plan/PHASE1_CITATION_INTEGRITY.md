# Phase 1 Citation Integrity Smoke Check

**Mechanical structural citation integrity only.** Established in Task
1.8. Confirms every cited chunk ID exists in the real Task 1.5 `chunks`
table and was actually among the exact chunks supplied to that specific
generation call. This is **not** an answer-quality evaluator, **not** an
entailment/support grader, and **not** Task 1.9's ~200-question
evaluation.

## Purpose

```text
Task 1.7 generated answer
        ↓
strict answer-text citation inspection (independent of GenerationResult.citations)
        ↓
does every citation exist?  was every citation actually supplied?
are there malformed citation attempts?  does a substantive answer cite at all?
        ↓
small traceable PASS/FAIL smoke report
```

## Valid citation syntax

Reused exactly from `src.generation.citations.parse_citations()` — no
second, possibly-incompatible grammar was defined. Conceptual shape:
`[<document_id>::chunk<ordinal>]`, e.g. `[1158114_2016.htm::chunk106]`.

## A real discrepancy from this task's own framing (documented, not hidden)

The task prompt listed three "must fail" malformed examples: fullwidth
`【...】`, truncated `[chunk63]`, and `[chunk_id: 1158114_2016.htm::chunk106]`.
**Empirically verified against the actual committed Task 1.7 parser**
(`src/generation/citations.py`'s regex `\[([^\[\]]+::chunk\d+)\]`), only
the first two are rejected by the strict parser outright. The third is
**not** rejected — its content (`chunk_id: 1158114_2016.htm::chunk106`)
matches the strict grammar exactly (arbitrary text + `::chunk<digits>`),
so `parse_citations()` returns it as a citation string with the literal
`"chunk_id: "` prefix baked in. It therefore surfaces here as
`unknown_chunk_id` at the **existence-check** stage (since
`"chunk_id: 1158114_2016.htm::chunk106"` is not a real chunk_id), not as
`malformed_citation_attempt` at the attempt-detection stage. Both are
still hard failures — only the specific reason code differs from what the
task's framing assumed. Per Step 8's explicit instruction to follow actual
code over a recorded description, this was verified directly (see the
regression test `test_context_label_form_fails_as_unknown_not_malformed`
in `tests/test_citation_integrity.py`) rather than silently corrected to
match the framing.

## Integrity rules

| Condition | Result |
|---|---|
| Malformed citation attempt detected (fullwidth `【】`, or an ASCII `[...]` whose content isn't strict-valid) | FAIL — `malformed_citation_attempt` |
| `parse_citations(answer)` disagrees with `GenerationResult.citations` | FAIL — `parsed_citation_mismatch` |
| Valid-syntax citation not found in the real `chunks` table | FAIL — `unknown_chunk_id` |
| Valid-syntax citation exists but wasn't in this call's exact supplied top-5 | FAIL — `citation_not_in_supplied_context` |
| Non-abstaining case with zero valid citations | FAIL — `missing_required_citation` |
| Abstention-control case with zero valid citations | Allowed — eligible to PASS |
| Duplicate valid citation (same ID cited twice) | Not itself a failure — `parse_citations()` already dedups |

One bad citation fails the whole case — no majority vote across multiple
citations.

## Malformed-attempt detection

`src/eval/citation_integrity.py`'s `detect_citation_attempts()` is
deliberately **broader** than the strict parser (so it catches what the
strict parser silently drops) but still narrow: it scans for ASCII `[...]`
and fullwidth `【...】` bracket pairs, then only treats the bracket content
as a citation *attempt* if it contains a chunk-like token
(`chunk\d+` or the literal substring `chunk_id`) — so ordinary markdown
brackets (`[see note]`, `[2024]`, `[revenue]`) never false-positive
(verified directly, `test_ordinary_brackets_not_detected`). Each detected
attempt is then classified `strict_valid` by calling
`parse_citations(f"[{content}]") == [content]` — reusing the real parser
function itself, not a re-derived regex, so the two can never silently
drift apart.

Regression tests cover all three real Task 1.7 observed forms
(`tests/test_citation_integrity.py`): fullwidth `【...】` → malformed;
truncated `[chunk63]` → malformed; `[chunk_id: ...]` → strict-valid syntax
with wrong content → `unknown_chunk_id` (see discrepancy note above).

## Existence source

The real Task 1.5 `chunks` table (162,357 rows), via a new, narrow,
non-breaking helper added to `src/index/lancedb_index.py`:

```python
def get_chunk_by_id(table, chunk_id: str) -> pa.Table:
    escaped = chunk_id.replace("'", "''")
    return table.search().where(f"chunk_id = '{escaped}'").to_arrow()
```

Verified directly this is a pure scalar-filter scan, not a vector search —
`table.search()` with no vector argument, `.where(...)` applying a SQL
predicate. No embedding, no fuzzy matching, no document_id-only fallback.
Existing Task 1.5 functions (`exact_cosine_search`, `validate_chunk_table`,
etc.) are unmodified.

## Supplied-context source

The **exact** top-5 `RetrievalResult` objects from the same generation
call — never a second, independent retrieval assumed identical.
`src/eval/citation_integrity.py`'s `RecordingRetriever` wraps the real
Task 1.6 `BaselineRetriever` (duck-typed — `MinimalGenerator` only
requires `.retrieve(question, k)`, so no Task 1.6/1.7 public contract
changed), delegates every call to it, and records the returned objects on
`.last_results`. The smoke script passes a `RecordingRetriever` into
`MinimalGenerator` and reads `recorder.last_results` immediately after
`generator._answer_with_diagnostics(question)` returns — the identical
objects `MinimalGenerator` itself used to build the prompt.

Supplied-context invariants verified per live case (Step 13): exactly 5
chunks, 5 unique `chunk_id`s, every `chunk_id`/`document_id`/`text`
non-empty — enforced with a hard `SystemExit` if violated, not a soft
warning.

## Manual inspection metadata

For every reparsed citation (valid syntax, regardless of existence),
`CitationCheck` records `chunk_id`, `exists_in_index`, `was_supplied`, and
`source_metadata` (`None` only when `exists_in_index` is `False` — never
fabricated). When it exists, `source_metadata` carries the 13 static
index-stored fields (`document_id`, `company`, `form_type`, `fiscal_year`,
`source`, `source_filename`, `source_split`, `ordinal`, `token_count`,
`chunk_config_hash`, `normalizer_version`, `normalization_build_sha256`,
`development_manifest_sha256`); the smoke script additionally merges in
`retrieval_rank`/`retrieval_score`/`retrieval_distance` from the recorded
supplied context when the citation was actually supplied (those three
fields don't exist as persisted index columns — they're per-query
retrieval facts, only meaningful when the chunk was part of *this*
question's top-5). No `accession`/`section_id`/`section_title` is ever
fabricated — the Phase 1 chunk schema doesn't contain them.

## Live smoke (real, 10 cases)

```text
provider:                 openrouter
requested model:            openai/gpt-oss-20b
response-reported model:      openai/gpt-oss-20b (echoed back exactly)
total cases:                    10 (8 answer-expected + 2 abstention controls)
passed:                           3
failed:                             7
```

| case_id | expected | status | reason(s) |
|---|---|---|---|
| citation-smoke-01 | answer | FAIL | malformed_citation_attempt, missing_required_citation (`【1158114_2016.htm::chunk106】`) |
| citation-smoke-02 | answer | **PASS** | — |
| citation-smoke-03 | answer | FAIL | malformed_citation_attempt, missing_required_citation (`【chunk72】` — compounded: wrong bracket *and* truncated ID) |
| citation-smoke-04 | answer | FAIL | malformed_citation_attempt, missing_required_citation (`[chunk63]`) |
| citation-smoke-05 | answer | FAIL | malformed_citation_attempt, missing_required_citation (`【898174_2020.htm::chunk160】`) |
| citation-smoke-06 | answer | FAIL | malformed_citation_attempt, missing_required_citation (`【857737_2018.htm::chunk52】`) |
| citation-smoke-07 | answer | FAIL | malformed_citation_attempt, missing_required_citation (`【1696898_2019.htm::chunk9】`) |
| citation-smoke-08 | answer | FAIL | malformed_citation_attempt, missing_required_citation (`【1580905_2020.htm::chunk11】`) |
| citation-smoke-09 | abstain | **PASS** | — |
| citation-smoke-10 | abstain | **PASS** | — |

```text
cases_with_valid_citations:        1
cases_with_malformed_attempts:       7
cases_with_unknown_ids:                0
cases_with_out_of_context_ids:           0
cases_missing_required_citation:           7
total_valid_citations:                       1
valid_citations_existing:                      1
valid_citations_supplied:                        1
```

Every single failure this run was the same root cause: `openai/gpt-oss-20b`
overwhelmingly prefers fullwidth `【】` brackets over the instructed ASCII
`[]` (6 of 7 failures), plus one genuine truncated-ID case. **Zero**
`unknown_chunk_id` or `citation_not_in_supplied_context` failures occurred
— every citation attempt that *was* syntactically valid pointed to a real,
correctly-supplied chunk. This means the underlying retrieval → prompt →
model pipeline is grounding correctly; the failure mode is narrowly a
bracket-character-choice compliance problem with this specific model, not
a hallucinated or out-of-context citation problem.

## Manual inspection

All 10 live cases were manually inspected (this is a 10-case smoke, not a
statistical sample). For both abstention controls (citation-smoke-09,
citation-smoke-10), the generated answer text was read directly and
confirmed to actually be an insufficiency/abstention response — no
machine-readable `abstained: bool` exists on `GenerationResult`, and none
was invented; `expected_behavior` is a property of the pre-configured
question (`configs/citation_integrity_smoke.json`), never inferred from
the model's own text by an automated phrase classifier. citation-smoke-02
was confirmed to have 8 repeated identical valid citations, correctly
deduplicated to 1 by the strict parser and correctly passing (Step 22).

## Result meaning

```text
PASS  — integrity checker is correct AND the 10-case live smoke passes
WARN  — integrity checker is correct, tests pass, but the live model
        emits one or more correctly-detected citation-compliance failures
BLOCKED — the checker cannot reliably determine existence/supplied-context
        membership, or required infrastructure is broken
```

**This run: WARN.** The checker implementation is correct — every failure
above was independently, manually confirmed to be a real citation-format
problem, not a false positive. Per this task's explicit rule, a live-model
compliance failure does not convert to PASS, and the implementation is not
BLOCKED merely because it successfully found real problems. **Phase 1
citation compliance remains an open, documented issue** — not silently
declared satisfied. See `Progress.md`'s Task 1.8 entry for the explicit
stop-for-decision before Task 1.9.

## Known limitations

- Does not prove cited text supports the answer (no entailment/NLI, no
  LLM-as-judge) — purely structural: exists + was-supplied + well-formed.
- Does not prove answer correctness.
- Does not require every individual factual clause to carry its own
  citation — only that a substantive answer has at least one valid
  citation overall.
- Does not evaluate retrieval relevance.
- Does not perform citation repair, regeneration, or retry — one
  generation call per case, failures are recorded, not fixed.
- Only a 10-case smoke, not a statistically powered benchmark.
- Generation provider/model can change later (OpenRouter is a Phase 1
  testing provider only) — this run's specific 【】-bracket failure mode is
  a property of `openai/gpt-oss-20b`'s output habits, not necessarily of
  every future model.

## Next task

Task 1.9 — ~200-question smoke evaluation (pending the user's decision on
how to proceed given this WARN — see `Progress.md`).
