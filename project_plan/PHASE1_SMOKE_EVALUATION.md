# Phase 1 200-Question Smoke Evaluation

**NOT THE FINAL BENCHMARK.** Established in Task 1.9. Builds a crude,
deterministic, document-level "which filing should this question retrieve"
dataset from the frozen Task 1.1 development corpus. This is Phase 1's
integration smoke set — it exists to catch pipeline failures early, not to
measure retrieval or answer quality. Phase 2's truth-contract-backed
~3,000-question benchmark (`PROJECT_EXECUTION.md` Task 2.1–2.3) is the
actual measurement instrument; these 200 questions are discarded there, not
carried forward.

## Purpose

```text
Task 1.1 aligned development corpus (1,500 filings)
        ↓
verify assigned EDGAR-CORPUS section is non-empty
        ↓
deterministically choose 200 unique target filings (40/category, 5 categories)
        ↓
render one document-targeted question per filing from a fixed template
        ↓
store provenance + document-level label
        ↓
Task 1.10 computes doc_recall@10 (not built here)
```

## Accepted Task 1.7a warning

Task 1.7a's prompt-only citation-format correction improved the frozen
Task 1.8 smoke from 3/10 to 8/10, with two residual fullwidth `【】`
citation failures and zero unknown/out-of-context citation failures. The
user explicitly approved proceeding to Task 1.9 with that limitation
documented — see `PHASE1_CITATION_INTEGRITY.md` and `Progress.md`'s Task
1.7a entry. **This is not resolved by Task 1.9** and Task 1.9 does not call
generation at all, so it cannot re-exercise or fix that warning.

## Five categories and section mapping

```text
business                -> section_1
risk_factors            -> section_1A
mdna                    -> section_7
market_risk             -> section_7A
financial_statements    -> section_8
```

40 questions per category, fixed category order for both selection and
final question-ID assignment: `business, risk_factors, mdna, market_risk,
financial_statements`.

## Eligibility

A Task 1.1 filing is an eligible candidate for a category only when its
assigned EDGAR-CORPUS section column is a non-null, non-empty,
non-whitespace-only string (`src.eval.smoke_dataset.is_eligible_section`).
This naturally excludes the 7 known Task 1.2 empty-source filings from
every category, without any special-case code — verified directly, none
of the 7 appear in the real 200 (`tests/test_smoke_evaluation_dataset.py`'s
`test_real_smoke_evaluation_dataset`, and see "Real build" below).

## Question templates (fixed, no LLM)

```text
business:              What does {company} report about its business in its fiscal year {fiscal_year} 10-K?
risk_factors:          What risk factors does {company} report in its fiscal year {fiscal_year} 10-K?
mdna:                  What does {company} report in Management's Discussion and Analysis for fiscal year {fiscal_year}?
market_risk:           What does {company} report about quantitative and qualitative market risk in its fiscal year {fiscal_year} 10-K?
financial_statements:  What financial statements and related information does {company} report for fiscal year {fiscal_year}?
```

`company`/`fiscal_year` come from the verified Task 1.1 manifest row. No
amount, product, risk, subsidiary, market, or accounting fact is invented.
The target `document_id` is never exposed in the rendered question text.

## Deterministic selection (no PRNG)

```text
selection_key = SHA-256(category + "\0" + document_id), hex digest, ascending
```

Never Python's built-in `hash()` (process/`PYTHONHASHSEED`-dependent, not
reproducible). For each category, in fixed order: build the eligible
candidate pool, sort by ascending `selection_key`, skip any `document_id`
already selected by an earlier category (global cross-category
uniqueness), take the first 40.
`src.eval.smoke_dataset.select_all_categories` raises `ValueError` — never
silently rebalances categories or relaxes uniqueness — if any category
cannot supply 40 unused eligible candidates.

## Document-level ground truth only

```text
label_granularity = "document"
retrieval_metric  = "doc_recall@10"
```

Task 1.3's fixed 512-token chunker has no section-aware gold labels, so
**true chunk evidence is unavailable for Task 1.9.** No `target_chunk_id`
is claimed, no chunk is manufactured by searching for headings or by
picking a retrieved chunk. Task 1.10 must evaluate document recall only.
No `accession` is fabricated — EDGAR-CORPUS carries no accession field
(see `PHASE1_DEVELOPMENT_CORPUS.md`). No `expected_answer`/`answer_span`/
XBRL fact value is included.

## Question record schema

Per question (`results/phase_1_9_smoke_evaluation.json`'s `questions`
array):

```text
question_id                    "phase1-smoke-0001".."phase1-smoke-0200"
question
category
template_id                    == category (one template per category)
source_section_column

target_document_id
target_cik
target_company
target_form_type               "10-K" (fixed — guaranteed by Task 1.1's
                                XBRL form='10-K' alignment filter)
target_fiscal_year
target_source_filename
target_source_split

label_granularity               "document"
retrieval_metric                "doc_recall@10"

development_manifest_sha256     Task 1.1 provenance
normalizer_version               Task 1.2 provenance (sourced from the
                                 tracked results/phase_1_2_normalization_summary.json,
                                 never recomputed from the git-ignored
                                 artifacts/normalized/ directory, so the
                                 build works on a fresh clone)
normalization_build_sha256       Task 1.2 provenance (same source)
source_section_sha256            SHA-256 over the exact UTF-8 raw
                                 EDGAR-CORPUS section-column string used
                                 for eligibility — provenance only, not
                                 chunk-level ground truth
```

`question_id` ordering: category order, then `target_document_id`
ascending within each category — independent of the SHA-256 selection
order, which only decides *which* documents are chosen.

## Dataset hash

```text
smoke_eval_sha256 = SHA-256(canonical JSON of the 200 question records)
```

Canonical form: `json.dumps(records, sort_keys=True, separators=(",",
":"))`, UTF-8 — the same convention already used for
`development_manifest_sha256`/`normalization_build_sha256`/
`chunk_config_hash`. No timestamp is part of the hashed payload (the
per-record schema above has none; `created_at_utc` exists only at the
top level of the dataset file, outside the hashed `questions` array).

## Real build

```text
manifest:                       results/phase_1_1_development_corpus.json
development_manifest_sha256:    d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b (verified)
```

| Category | Candidates | Selected |
|---|---:|---:|
| business | 1,427 | 40 |
| risk_factors | 1,420 | 40 |
| mdna | 1,482 | 40 |
| market_risk | 1,431 | 40 |
| financial_statements | 1,478 | 40 |

```text
question_count:               200
unique question IDs:            200
unique question text:             200
unique target documents:            200
smoke_eval_sha256:                    0b2c25dcbde141cafb5694ae748c5131d556d543195158aa3794dec325657a27
year distribution:                      2016:52  2017:36  2018:30  2019:42  2020:40
unique target CIKs:                        198
unique target companies:                    198
max questions per CIK:                        2
```

Independently re-verified (not trusted from the build script's own
validation) by a fresh DuckDB query joining all 200 targets' assigned
section columns directly against the live `data/edgar_corpus/*.parquet`
files: 200/200 non-empty, 0/200 are one of the 7 known-empty-source
filings.

## Determinism

Built twice, independent processes: identical `smoke_eval_sha256`
(`0b2c25dcbde141cafb5694ae748c5131d556d543195158aa3794dec325657a27` both
runs), identical question IDs/questions/categories/targets/provenance. The
build script's idempotent-rewrite policy (matching Task 1.3's chunk
artifact convention) treats a rebuild with an identical `smoke_eval_sha256`
as a safe rewrite and refuses (does not silently overwrite) a rebuild that
would produce a *different* hash against an existing dataset file.

## Manual inspection

15 questions inspected (3 per category, all 5 categories) directly from
the real build. All 15 confirmed: correct frozen-template wording, correct
company name and fiscal year matched against the manifest, target
document ID never leaked into the question text, assigned source section
non-empty, and a defensible document-level target (the question's topic
matches the section actually assigned to that filing).

## No generation, no doc_recall@10 here

Task 1.9 does not call OpenRouter, does not run 200 generations, does not
score answers, and does not inspect citations. It also does not calculate
`doc_recall@10` — that is Task 1.10's job entirely (hit counting, recall
computation, run-metadata logging, printed output). A 3–5-question
`k=10` retriever sanity check was considered (Step 25 of the task prompt)
but skipped as redundant: Task 1.6's own retriever smoke
(`PHASE1_RETRIEVER.md`) already demonstrates the retriever consumes
natural-language questions and returns ranked chunks correctly, and Task
1.9's dataset schema was validated structurally (traceability, uniqueness,
category balance) without needing a live retrieval call.

## Known limitations

- Document-level target only — no chunk-level, span-level, or exact-answer
  ground truth. `doc_recall@10` (Task 1.10) is explicitly a crude Phase 1
  proxy metric, not a final benchmark metric.
- No stratification by year/company/SIC beyond what unbiased hash-order
  selection with cross-category uniqueness naturally produces (year
  distribution above is not forced to match the eligible population's
  distribution).
- Selection draws only from the 1,500-filing Task 1.1 development corpus,
  not the full 91,086-filing EDGAR-CORPUS.
- Not a locked DEV/TEST split — Phase 2 (Task 2.4) owns that.
- These 200 questions are discarded in Phase 2, not carried forward — some
  will be semantically imprecise (a section may discuss the target topic
  only partially), adequate for detecting integration failures and
  inadequate as final ground truth.
- Task 1.7a's citation-format compliance (8/10 on the frozen Task 1.8
  smoke, 2 residual fullwidth-bracket failures) remains an open, documented
  Phase 1 limitation, unaffected by this task.

## Next consumer

Task 1.10 (Baseline Metric Runner) reads
`results/phase_1_9_smoke_evaluation.json`, runs Task 1.6's retriever with
`k=10` for each of the 200 questions, checks whether `target_document_id`
appears among the top-10 retrieved chunks' `document_id`s, and reports
`doc_recall@10`.

## Reproducing this build

```bash
python scripts/build_smoke_evaluation.py
```

Reads `results/phase_1_1_development_corpus.json`,
`results/phase_1_2_normalization_summary.json`, and
`data/edgar_corpus/*.parquet` read-only, performs no network access, no
GPU, no LLM call, and writes only
`results/phase_1_9_smoke_evaluation.json`,
`results/phase_1_9_smoke_evaluation_summary.json`, and
`configs/phase_1_9_smoke_evaluation.json` (all tracked). Verified to
reproduce an identical `smoke_eval_sha256` across independent
fresh-process runs.
