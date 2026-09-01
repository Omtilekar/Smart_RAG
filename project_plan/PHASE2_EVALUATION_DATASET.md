# Phase 2 Evaluation Dataset

Established in Task 2.3. Builds the project's authoritative Phase 2
evaluation dataset from the frozen `[[PHASE2_TRUTH_CONTRACT]]` (Task 2.1)
and frozen `[[PHASE2_TAG_REGISTRY]]` (Task 2.2), plus the frozen SEC
source data. This dataset is **not** DEV/TEST split — Task 2.4 owns the
company-disjoint split. This document is the authoritative reference for
what the dataset is, how it was built, and what its guarantees are (and
are not).

## Objective

A future developer should be able to open
`results/phase_2_3_evaluation_dataset.json` and know: exactly how each
question's gold label was derived, whether that derivation is
byte-reproducible, and which registry/truth-contract version it is tied
to — without re-reading the generator code.

## Files

- `src/eval/evaluation_dataset.py` — pure logic: record construction,
  question-ID assignment, canonical hashing, duplicate/leakage checks.
  No I/O, no DB access, no network calls.
- `scripts/build_evaluation_dataset.py` — I/O layer: opens
  `data/xbrl.duckdb`, calls `src/eval/tag_registry.py` and
  `src/eval/truth_contract.py`, calls OpenRouter for the narrative
  category, writes the three output artifacts below.
- `results/phase_2_3_evaluation_dataset.json` — the dataset itself:
  2,810 question records plus header metadata (`dataset_sha256`,
  `registry_hash`, `truth_contract_hash`, `git_sha`, `created_at_utc`).
- `results/phase_2_3_evaluation_dataset_summary.json` — counts by
  category/subtype/tag/year/answer_type, unique CIK/accession counts,
  `build_config_hash`.
- `configs/phase_2_3_evaluation_dataset.json` — the build configuration
  (category targets, year window, selection rules, arithmetic rule,
  materiality policy) as a machine-readable, hashable record. JSON, not
  YAML — this file is generated, not hand-curated (`configs/eval_tags.yaml`
  is the one deliberate exception, per Task 2.2).
- `tests/test_evaluation_dataset.py` — 42 tests: 41 portable (synthetic
  fixtures), 1 `local_data`-marked (validates the real, built dataset
  file end-to-end: schema, provenance, independent hash recompute,
  leakage/duplicate re-check).

## Category breakdown (2,810 total)

| Category | Subtype | Count | Gold-label source |
|---|---|---:|---|
| numeric | xbrl_fact | 2,000 | Raw XBRL fact via `eligible_facts()` |
| comparative | year_over_year_difference | 350 | Two raw XBRL facts, Python float64 subtraction |
| comparative | cross_entity_comparison | 150 | Two raw XBRL facts, direct comparison |
| narrative | llm_generated | 50 | **LLM-generated, `status="pending_review"` — not gold** |
| unanswerable | year_outside_window | 100 | Structurally provable: year outside `[2016,2020]` |
| unanswerable | unsupported_tag | 100 | Structurally provable: tag not in `configs/eval_tags.yaml` |
| adversarial | prompt_injection | 20 | Hand-written deterministic template |
| adversarial | financial_advice | 20 | Hand-written deterministic template, real company names |
| adversarial | off_scope | 20 | Hand-written deterministic template |

Historical design target was ~3,000 (200 narrative, 100 adversarial).
Two deliberate reductions from that target, both documented here rather
than silently applied:

1. **Narrative: 200 → 50.** Explicit user decision (see below).
2. **Adversarial: 100 → 60.** Self-directed reduction — 20 hand-written,
   reviewed templates per subtype is a defensible fixed set; padding to
   100 would mean either duplicating templates with cosmetic variation
   (no real coverage gain) or writing 40 more templates purely to hit a
   round number, which the task's own Core Rule (don't optimize for
   count) argues against.

## The narrative-category decision (explicit, user-directed)

Narrative questions historically require LLM generation followed by
genuine human review before being labeled gold. The task's own rules
forbid labeling unreviewed LLM output as gold, and forbid using the same
LLM as both generator and judge. No human-review pipeline exists in this
project. Rather than silently pick a resolution, this was raised to the
user directly. Two decisions were made, both binding on this dataset:

1. **Generate narrative questions via LLM, mark them `pending_review`**
   (not `accepted`) — chosen over the alternative of shipping only the
   4 deterministic categories (~2,760 questions).
2. **Generate exactly 50**, not the historical 200 — chosen after being
   told the cost: one live OpenRouter call per question, same
   provider/model as Phase 1 (`openai/gpt-oss-20b`).

Every narrative record carries `status: "pending_review"`,
`generation_provider`, `generation_requested_model`,
`generation_response_model`, `generation_prompt_version`, and
`source_section_sha256` (hash of the full EDGAR-CORPUS section text the
question was generated from, not just the 3,000-character excerpt sent
to the model). No narrative record is, or should be treated as, gold
until a genuine human review pass happens in a future task. **Downstream
consumers of this dataset must filter or weight narrative questions
accordingly** — they are evaluable for "does the system attempt a
grounded, on-topic narrative answer" but not for exact-answer scoring.

The real build made 54 OpenRouter calls to produce 50 accepted
questions (4 candidates skipped for empty/malformed responses).

## Determinism and reproducibility

**2,760 of 2,810 records (all except narrative) are byte-reproducible.**
Verified by two independent fresh-process builds of the deterministic
categories producing an identical `dataset_sha256` and identical
question-ID ordering.

**The 50 narrative records are NOT byte-reproducible.** LLM output is
not byte-stable even at `temperature=0.0` (established already in
Phase 1's own generation documentation). A rerun of `build_narrative()`
will very likely produce different question text, a different
`dataset_sha256` for the full dataset, and will trip the script's own
overwrite-refusal guard against the existing dataset file. This is
expected and correct behavior, not a bug — the guard exists precisely so
a second, different narrative batch cannot silently replace the first.
**Do not claim full-dataset reproducibility; only the 2,760-record
deterministic core is a reproducibility guarantee.**

Selection is via `selection_key()` (SHA-256 over NUL-joined UTF-8 parts,
the same convention as Tasks 1.9/2.1/2.2) — never Python's built-in
`hash()`, which is salted per-process and not reproducible across runs.

## Traceability and leakage prevention

Every record carries `registry_version`/`registry_hash`/
`truth_contract_version`/`truth_contract_hash`, so any question can be
traced to exactly which tag-registry semantics and truth-contract code
produced it.

`check_no_leakage()` verifies, programmatically (not just by
convention), that no question text contains: the accession/adsh, the
internal XBRL tag name, the expected numeric value, any registry/truth-
contract/section hash, or (for comparative questions) any operand's
accession. `check_no_duplicate_questions()` rejects both literal
question-text duplicates and semantic duplicates, with subtype-aware
identity keys (`cross_entity_comparison` keys on
`(tag, fiscal_year, sorted(operand_ciks))`;
`year_over_year_difference` keys on `(cik, tag, operand fiscal_years)`;
everything else keys on `(category, subtype, cik, accession, tag,
operation, fiscal_year)`). Both checks ran against the real 2,810-record
set and passed.

## Retrieval independence

No gold label in this dataset was derived from, or checked against, the
current retriever/generator/router's own output. Numeric and comparative
labels come from `eligible_facts()` reading `data/xbrl.duckdb` directly.
Unanswerable labels are structurally provable from source metadata alone
(year window, registry membership) — never from "the retriever found
nothing." Narrative questions are generated from EDGAR-CORPUS source
text directly, independent of any retrieval step, and are explicitly
not gold-scored pending human review.

## Independent verification performed

- Recomputed `dataset_sha256` independently from the dataset file's own
  question list and compared to the stored value — match.
- Re-ran `check_no_leakage()` and `check_no_duplicate_questions()`
  against the real 2,810-record set — both pass.
- Cross-checked a random sample (15 numeric, 10 year-over-year, 10
  cross-entity) against raw XBRL facts via `eligible_facts()` — all
  matched.
- Manually inspected 55 questions (15 numeric, 10 comparative, 10
  narrative, 10 unanswerable, 10 adversarial) for natural wording,
  absence of leakage, and semantic correctness — no issues found.

## Distribution notes

- **Fiscal year concentration**: 2016 accounts for ~44% of numeric
  questions (1,243 of 2,810 total across all categories). This follows
  from the numeric-selection rule (one fact per (tag, cik), lowest
  `adsh`, deterministically ordered) combined with 2016 being the first
  year of the supported window and many companies' earliest eligible
  filing — not a construction bug. Downstream evaluation should be aware
  of this skew if reporting per-year breakdowns.
- **Company/accession concentration**: max 4 questions per CIK, max 4
  per accession, across 2,185 unique CIKs and 1,831 unique accessions.
  No hard cap was enforced beyond the natural 1-per-(cik,tag) numeric
  rule and 1-per-(cik,year-pair,tag) comparative rule; measured
  concentration is low.
- Question length: 30–248 characters, median 95.
- Numeric magnitude: spans 0.0 to ~$895B, reflecting the real range of
  company sizes in the corpus.

## Evidence granularity

Only **document-level** evidence exists for narrative questions
(`target_document_id`, `source_section_column`, `source_section_sha256`)
— there is no chunk-level span annotation. This is consistent with
Phase 1's chunking design (chunks are a retrieval-time construct, not a
property of the source document) and means narrative gold evaluation,
once a review pipeline exists, will be document-level, not span-level.

## What this task did not do

- Did not create a DEV/TEST split — that is Task 2.4.
- Did not perform human review of narrative questions — none are gold.
- Did not modify `src/eval/truth_contract.py`, `configs/eval_tags.yaml`,
  or any Phase 1 module.
