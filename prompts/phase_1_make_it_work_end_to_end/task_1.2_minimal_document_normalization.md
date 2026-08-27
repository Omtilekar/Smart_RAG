# Task 1.2 — Minimal Document Normalization

You are working inside my SEC RAG repository.

**Task file:** `task_1.2_minimal_document_normalization.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.2 — Minimal Document Normalization
```

Current status:

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
Phase 1 — Make It Work End to End — IN PROGRESS
  1.1 Select Development Corpus   — COMPLETE
  1.2 Minimal Normalization       — CURRENT
```

Task 1.1 froze the official Phase 1 development corpus:

```text
selected filings: 1,500
eligible population: 5,646
selection method: SHA-256(document_id), ascending, first 1,500
manifest: results/phase_1_1_development_corpus.json
development_manifest_sha256:
d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b
```

Task 1.2 must consume this exact manifest.

Do **not** independently reselect filings. Do **not** regenerate the Task 1.1 population.

---

# CRITICAL RULE — DO NOT ASSUME

This rule applies throughout the task.

If an implementation decision is not clearly resolved by:

1. the current repository,
2. `project_plan/PROJECT_EXECUTION.md`,
3. `DATA_READINESS_REPORT.md`,
4. Task 1.1's frozen manifest/documentation,
5. current specialized project documentation,
6. direct inspection of the frozen source data,

then **STOP AND ASK ME**.

Do not silently choose a reasonable-looking default. Do not infer semantics from a field name when inspection can establish them. Do not resolve contradictory documentation yourself. Do not introduce a new convention merely because it is convenient.

When asking me:

- state exactly what is ambiguous,
- state what repository/data evidence you found,
- give the smallest useful set of options,
- explain what downstream behavior depends on the decision,
- wait for my answer before continuing past that decision point.

This is especially important for:

- normalizer version naming,
- artifact location if the existing storage abstraction is unclear,
- treatment of unexpected source values,
- section ordering if source/documentation disagree,
- overwrite/rebuild behavior,
- metadata provenance,
- any new dependency,
- Git remote/push behavior.

Inspection first. Assumption never.

---

# AUTHORITATIVE TASK DEFINITION

Read the current `project_plan/PROJECT_EXECUTION.md` before implementing.

Task 1.2 should:

- convert the selected EDGAR-CORPUS records into one normalized Markdown representation per filing,
- add YAML frontmatter containing available metadata,
- preserve source identity,
- normalize CIK to an integer-compatible `int64` value,
- normalize year/fiscal year to an integer-compatible `int32` value,
- avoid sophisticated cleaning.

Minimum frontmatter expected by the plan:

```yaml
---
cik:
company:
form_type: "10-K"
fiscal_year:
source: "edgar_corpus"
source_filename:
---
```

Phase 1 is intentionally crude. This task is about making the pipeline work end to end, not building the final document-normalization layer.

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. verify the Task 1.1 Git checkpoint and manifest,
2. independently verify the frozen manifest checksum,
3. inspect the actual EDGAR-CORPUS schema and section columns,
4. resolve exactly the selected 1,500 source records,
5. define the smallest deterministic normalization contract,
6. render one deterministic Markdown document per filing,
7. add deterministic YAML frontmatter,
8. preserve exact source identity and provenance,
9. write generated documents under the existing storage abstraction,
10. produce exactly 1,500 normalized documents,
11. compute normalization provenance/checksums,
12. add focused automated tests,
13. verify a second run is byte-deterministic,
14. document the normalization contract,
15. update `Progress.md`,
16. create one coherent Task 1.2 Git commit.

Do **not** start Task 1.3.

---

# STEP 1 — VERIFY GIT STATE

Run:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -5
git tag --list
```

Verify the Phase 0 checkpoint and Task 1.1 commit exist and that there are no unexplained uncommitted changes.

If unexplained working-tree changes exist, **STOP AND ASK ME**. Do not mix unrelated work into Task 1.2.

---

# STEP 2 — VERIFY FOUNDATION

Activate `.venv` and run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Expected: zero failures.

Do not normalize on top of a broken foundation.

---

# STEP 3 — READ CURRENT IMPLEMENTATION/DOCUMENTATION

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_DEVELOPMENT_CORPUS.md
project_plan/STORAGE.md
project_plan/REPOSITORY_STRUCTURE.md
project_plan/CONFIGURATION.md
project_plan/TESTING.md
project_plan/GIT_CONVENTIONS.md
Progress.md
```

Inspect:

```text
src/storage.py
src/config.py
src/logging_utils.py
src/normalize/
scripts/select_development_corpus.py
results/phase_1_1_development_corpus.json
```

Use actual implemented APIs, not assumptions from this prompt if the repository differs.

---

# STEP 4 — VERIFY THE TASK 1.1 MANIFEST

Load:

```text
results/phase_1_1_development_corpus.json
```

Verify:

```text
row count = 1,500
development_manifest_sha256 =
d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b
```

Do not merely trust the checksum stored inside the file. Recompute it using Task 1.1's documented canonical checksum procedure.

Verify all 1,500 identities are unique.

If the checksum differs, stop with:

```text
BLOCKED — Task 1.1 development manifest changed unexpectedly
```

Do not normalize a different population.

---

# STEP 5 — INSPECT MANIFEST METADATA

Record the actual manifest fields and determine which are appropriate for frontmatter/provenance.

Use actual fields only. Do not invent missing metadata.

Important Task 1.1 contract:

- `document_id` is the stable EDGAR-CORPUS source identity,
- CIK is the entity key,
- fiscal year is the aligned EDGAR year,
- company name, if present, is informational provenance and may originate from XBRL,
- EDGAR-CORPUS has no trustworthy accession mapping,
- XBRL `adsh` is not the EDGAR accession,
- 29 aligned `(CIK, fiscal_year)` pairs had multiple XBRL 10-K candidates,
- Task 1.1 intentionally did not choose a canonical `adsh`.

Task 1.2 must preserve those semantics.

Do not add an `accession` field or arbitrary `adsh` to normalized documents.

---

# STEP 6 — INSPECT ACTUAL EDGAR-CORPUS SCHEMA

Inspect efficiently:

```text
data/edgar_corpus/train.parquet
data/edgar_corpus/test.parquet
data/edgar_corpus/validation.parquet
```

Use DuckDB/PyArrow schema inspection. Do not load the entire 5.77 GB dataset into Python memory.

Determine actual fields/types and all actual `section_*` columns.

---

# STEP 7 — DETERMINE SECTION ORDER

The normalized Markdown must have deterministic SEC-item ordering.

Use actual source column identifiers. For ordinary names such as:

```text
section_1
section_1A
section_1B
section_2
section_7
section_7A
```

render them in natural SEC Item order:

```text
Item 1
Item 1A
Item 1B
Item 2
...
Item 7
Item 7A
```

Do not invent descriptive titles such as `Item 7 — Management's Discussion...` unless an authoritative repository mapping actually provides those titles.

If actual section identifiers cannot be ordered safely, **STOP AND ASK ME**.

---

# STEP 8 — LOAD EXACTLY THE SELECTED 1,500 RECORDS

Use the Task 1.1 manifest as the filter. Prefer an efficient join/filter against the three Parquet files.

Expected invariant:

```text
1,500 manifest records
→ 1,500 exact EDGAR source records
```

For every selected record verify:

- source filename/document identity matches,
- CIK matches,
- EDGAR year matches manifest fiscal year,
- source split matches if present in the manifest.

Use explicit integer normalization for CIK/year.

If any manifest row maps to zero or more than one EDGAR source row, **STOP AND ASK ME**.

---

# STEP 9 — INSPECT TEXT CHARACTERISTICS

Inspect a deterministic sample spanning multiple years and check for:

- null sections,
- empty/whitespace-only sections,
- multiline text,
- tabs,
- Unicode,
- HTML fragments,
- flattened numeric/table-like text,
- unusually large sections.

Do not infer cleaning policy from one sample.

---

# STEP 10 — CHECK FOR COMPLETELY EMPTY FILINGS

For each selected filing, count non-empty section fields.

If any selected filing has zero usable text sections, **STOP AND ASK ME**.

Do not silently remove or replace it, create an empty document, or substitute a primary HTML filing. The Task 1.1 corpus is frozen.

---

# STEP 11 — MINIMAL NORMALIZATION CONTRACT

Allowed baseline transformations:

```text
normalize CRLF/CR line endings to \n
strip leading/trailing whitespace around each section
omit null/empty/whitespace-only sections
render deterministic Markdown item headings
use deterministic YAML frontmatter
write UTF-8
ensure exactly one final newline
```

If you collapse repeated blank lines, document the exact deterministic rule.

Do not perform:

```text
LLM rewriting
semantic cleaning
OCR
de-hyphenation inference
header/footer detection
boilerplate removal
duplicate-paragraph inference
HTML recovery
table reconstruction
numeric restructuring
section-boundary inference
summarization
```

The goal is conservative normalization only.

---

# STEP 12 — MARKDOWN BODY FORMAT

Conceptually:

```markdown
## Item 1

<exact normalized source section text>

## Item 1A

<exact normalized source section text>
```

Only non-empty source sections should produce headings/body text.

Do not create empty headings for missing sections unless the current project documentation explicitly requires it.

Do not add prose that is absent from the source.

---

# STEP 13 — YAML FRONTMATTER

Every document must begin with deterministic YAML frontmatter.

Required minimum concepts:

```yaml
---
cik: 123456
company: "..."
form_type: "10-K"
fiscal_year: 2020
source: "edgar_corpus"
source_filename: "123456_2020.htm"
document_id: "123456_2020.htm"
source_split: "validation"
development_manifest_sha256: "d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b"
---
```

Use only fields actually supported by the manifest/source. If a listed optional field does not exist, do not invent it.

Semantics:

```text
cik: integer, int64-compatible
fiscal_year: integer, int32-compatible
form_type: exactly "10-K"
source: exactly "edgar_corpus"
source_filename: exact EDGAR source identity
document_id: exact Task 1.1 identity if distinct/present
company: provenance-backed value only
```

No fabricated accession.

---

# STEP 14 — YAML SERIALIZATION

Do not add a new dependency unless necessary.

For this constrained schema, JSON-style quoted strings are valid YAML and can be emitted safely using stdlib `json` escaping.

Do not hand-roll unsafe quoting that breaks on `:`, `#`, quotes, newlines, or Unicode.

If you believe PyYAML or another dependency is necessary, **STOP AND ASK ME** before modifying requirements.

---

# STEP 15 — OUTPUT LOCATION

Use `src.storage` and the Task 0.7 contract:

```text
artifacts/normalized/<normalizer_version>/
```

Do not hardcode `Path("artifacts/...")` when the storage abstraction already owns this mapping.

Do not write normalized Markdown to `data/`, `results/`, or `configs/`.

The Markdown corpus is generated pipeline state and must remain Git-ignored.

---

# STEP 16 — NORMALIZER VERSION

Inspect the repository for an already-defined Phase 1 normalization version/name.

Do not silently invent `v1`, `phase1`, or `minimal-v1`.

If no naming convention exists, **STOP AND ASK ME** before creating the artifact directory/config.

Explain the options and that this value becomes part of the artifact identity under `artifacts/normalized/<version>/`.

---

# STEP 17 — NORMALIZED FILE IDENTITY

Prefer a deterministic one-to-one mapping from source filename/document ID, e.g.:

```text
1005817_2016.htm -> 1005817_2016.md
```

Before using it, assert all 1,500 resulting Markdown filenames are unique.

If collisions exist, **STOP AND ASK ME**. Do not invent arbitrary counters.

---

# STEP 18 — IMPLEMENTATION LOCATION

Task 1.2 should make `src/normalize/` a real implemented package.

A reasonable structure is:

```text
src/normalize/edgar_markdown.py
scripts/normalize_development_corpus.py
```

Keep reusable/pure logic in `src/normalize/`; keep orchestration in `scripts/`.

Do not modify `src/ingest/` unless a clearly documented need exists. If reuse would require changing frozen ingestion code, **STOP AND ASK ME**.

---

# STEP 19 — USE EXISTING FOUNDATION BOUNDARIES

Use:

```text
src.config
src.storage
src.logging_utils
```

Do not introduce new scattered environment/path/logging logic.

Do not use `logging.basicConfig()` in the new application code.

Do not log filing contents.

---

# STEP 20 — CONFIG / PROVENANCE

Create a small tracked normalization config under the repository's existing `configs/` convention if that convention clearly applies.

It should capture at least:

```text
schema_version
normalizer_version
input_manifest
input development_manifest_sha256
source = edgar_corpus
section ordering policy
empty-section policy
newline policy
frontmatter schema/version
```

Do not include timestamps in anything that determines normalized document bytes.

If config naming/location is genuinely ambiguous, **ASK ME**.

---

# STEP 21 — NORMALIZATION BUILD HASH

Create a deterministic SHA-256 for the generated corpus.

A defensible procedure:

1. sort normalized relative paths,
2. hash exact UTF-8 bytes of each file,
3. combine relative path + file hash deterministically,
4. hash the combined stream to produce `normalization_build_sha256`.

Document the exact procedure.

Do not call it `chunk_config_hash`.

---

# STEP 22 — UTF-8 / BYTE DETERMINISM

Write files explicitly as UTF-8 with `\n` newlines.

The same manifest + source + config must produce byte-identical Markdown across runs.

Do not put runtime timestamps inside normalized Markdown.

---

# STEP 23 — OUTPUT COUNT INVARIANT

After the real build:

```text
manifest rows       = 1,500
source rows resolved = 1,500
Markdown documents  = 1,500
```

No drops, extras, duplicates, replacements, or silent skips.

---

# STEP 24 — VALIDATE ALL 1,500 OUTPUTS

For every Markdown file verify:

```text
frontmatter delimiters valid
required metadata present
cik integer-compatible
fiscal_year integer-compatible
form_type == "10-K"
source == "edgar_corpus"
source_filename/document_id matches manifest
body non-empty
at least one Item heading rendered
UTF-8 readable
```

Do not only sample structural validation.

---

# STEP 25 — CORPUS STATISTICS

Report for the normalized 1,500 documents:

```text
document count
total normalized bytes
character count min / median / p95 / max
non-empty section count min / median / p95 / max
```

Also report per-section presence:

```text
Item/section
number of documents present
percentage present
```

Known sparse sections are descriptive findings, not normalization failures.

Do not tokenize yet. Token statistics belong to Task 1.3.

---

# STEP 26 — MANUAL QUALITY INSPECTION

Inspect at least 10 deterministic samples across multiple years.

For each compare:

```text
Task 1.1 manifest
→ raw EDGAR source row
→ normalized Markdown
```

Verify metadata, section order, text preservation, source identity, and absence of invented content.

Include at least one sparse-section filing if available.

---

# STEP 27 — DETERMINISM

Run the production normalization twice in fresh processes or perform an equivalent independent rebuild verification.

Required:

```text
same file count
same relative filenames
same exact Markdown bytes
same normalization_build_sha256
```

If this fails, Task 1.2 fails.

---

# STEP 28 — EXISTING ARTIFACT / OVERWRITE POLICY

If `artifacts/normalized/<normalizer_version>/` already exists:

- inspect provenance/checksum,
- reuse/verify only if it clearly matches,
- do not silently overwrite a conflicting build,
- do not broadly delete artifact directories.

If existing behavior is not documented clearly, **STOP AND ASK ME**.

---

# STEP 29 — TRACKED SUMMARY

Create a small tracked summary, preferably:

```text
results/phase_1_2_normalization_summary.json
```

if consistent with current repository conventions.

Include:

```text
schema_version
normalizer_version
input manifest path
development_manifest_sha256
document_count
section coverage
document-size statistics
normalization_build_sha256
generated artifact relative path
created_at_utc
```

The summary is tracked provenance. The 1,500 Markdown documents remain ignored under `artifacts/`.

If this location conflicts with current repository policy, **ASK ME**.

---

# STEP 30 — HARD NON-GOALS

Do not:

```text
change the Task 1.1 manifest
select/replace filings
use the serving-spike corpus
use primary HTML to fill missing sections
fabricate accessions
reconstruct tables
perform advanced cleaning
tokenize documents
create chunks
assign chunk IDs
compute chunk offsets
load bge-small
use CUDA
embed text
build LanceDB
implement retrieval
call an LLM
generate evaluation questions
```

Task 1.2 outputs whole normalized filings only.

---

# STEP 31 — NETWORK / DEPENDENCY POLICY

Task 1.2 must be offline.

No calls to SEC, Hugging Face, OpenAI, Anthropic, AWS, or any external API.

Expected new dependencies: **none**.

If a new dependency appears necessary, **STOP AND ASK ME** before editing requirements.

---

# STEP 32 — TESTS

Add focused tests, e.g. `tests/test_document_normalization.py`.

Cover at minimum:

- SEC section ordering,
- empty-section omission,
- multiline/Unicode text preservation,
- safe YAML/frontmatter serialization,
- integer CIK/year semantics,
- exact identity preservation,
- deterministic Markdown rendering,
- deterministic output filename mapping,
- deterministic normalization build checksum,
- checksum changes when content changes.

Keep unit tests small and independent of the full 5.77 GB dataset.

A small `local_data` integration test is acceptable if useful, but normal pytest should remain practical.

---

# STEP 33 — BUILD COMMAND

Provide one documented command, preferably something like:

```bash
python scripts/normalize_development_corpus.py
```

It should:

1. verify the frozen Task 1.1 manifest checksum,
2. resolve exactly the 1,500 EDGAR records,
3. normalize/write the Markdown corpus,
4. validate all outputs,
5. compute/write provenance summary,
6. print a concise summary,
7. return non-zero on invariant failure.

Do not add Task 1.3 behavior.

---

# STEP 34 — DOCUMENTATION

Create `project_plan/PHASE1_NORMALIZATION.md` unless current repo convention clearly specifies another name.

Document:

- purpose,
- input manifest + checksum,
- EDGAR-CORPUS source,
- exact normalization transformations,
- section ordering,
- frontmatter schema/provenance,
- output location/version,
- checksum/determinism contract,
- known limitations,
- next consumer: Task 1.3.

Known limitations must include:

- simple Phase 1 cleaning only,
- no structured tables,
- sparse source sections remain sparse,
- no trustworthy EDGAR accession,
- no primary-document enrichment,
- no tokenization/chunking.

Update `project_plan/REPOSITORY_STRUCTURE.md` only as necessary to mark `src/normalize/` implemented.

---

# STEP 35 — RUN REAL BUILD AND VERIFICATION

Run the real 1,500-document build twice.

Verify:

```text
manifest = 1,500
source rows = 1,500
normalized docs = 1,500
run1 normalization_build_sha256 == run2 normalization_build_sha256
```

Then run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Expected: zero failures.

Do not hardcode the old test count; report the new actual count.

---

# STEP 36 — FROZEN DATA SAFETY

Verify lightweight invariants before/after:

```text
data/xbrl.duckdb size unchanged
36 raw XBRL ZIPs
990 primary filings
3 EDGAR Parquet files
```

Do not rewrite `data/`.

---

# STEP 37 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Confirm all generated Markdown under `artifacts/normalized/` is ignored.

Expected trackable files may include:

```text
src/normalize/...
scripts/normalize_development_corpus.py
tests/test_document_normalization.py
configs/<Task 1.2 config>.json
results/phase_1_2_normalization_summary.json
project_plan/PHASE1_NORMALIZATION.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
prompt file if prompts are tracked
```

No normalized Markdown corpus files should be staged.

Scan new trackable files for secrets, real SEC contact details, and personal absolute paths.

---

# STEP 38 — UPDATE PROGRESS.MD

Append, preserving all history:

```markdown
## YYYY-MM-DD — Phase 1.2 Minimal Document Normalization
```

Include:

## Objective

Task 1.2 converts the frozen 1,500-document Task 1.1 corpus into the first deterministic Markdown representation consumed by Task 1.3.

## Initial State

Record Task 1.1 commit, manifest path, manifest SHA-256, 1,500 selected filings, and that the normalizer was not previously implemented.

## Input Verification

Record manifest checksum, row count, source rows resolved, and identity mismatch count.

## Normalization Contract

Record exact implemented transformations.

## Metadata Contract

Record final frontmatter keys/provenance and state explicitly:

```text
fabricated accession: NONE
```

## Output

Record normalizer version, generated artifact path, document count, total size, and `normalization_build_sha256`.

## Corpus Statistics

Record character stats, non-empty-section stats, and section coverage.

## Determinism

Record run 1/run 2 checksum equality.

## Manual Inspection

Record inspected sample count/years/result.

## Tests

Record new Task 1.2 tests, portable suite, full suite, and doctor status.

## Frozen Data

Confirm `data/` unchanged.

## Files Created / Modified

List actual tracked/project files only.

## Git

Record Task 1.2 commit details.

## Result

Use exactly one:

```text
PASS — 1,500 development filings normalized deterministically to Markdown

WARN — normalization completed with one documented non-blocking issue

BLOCKED — development corpus could not be normalized safely
```

## Phase Status

If PASS:

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
Phase 1 — Make It Work End to End — IN PROGRESS
  1.1 Select Development Corpus   — COMPLETE
  1.2 Minimal Normalization       — COMPLETE
  1.3 Fixed-Window Chunker        — NEXT
```

---

# STEP 39 — COMMIT TASK 1.2

After build/determinism/tests/Git safety all pass and `Progress.md` is updated, create one coherent Task 1.2 commit.

Preferred message:

```text
Add minimal Markdown normalization
```

Do not include Task 1.3 work. Do not tag Phase 1 yet.

Inspect `git remote -v` before push behavior. If no remote exists, record push deferred. If push authorization/policy is ambiguous, **ASK ME**. Never force-push.

---

# ACCEPTANCE CRITERIA

Task 1.2 is complete only if:

```text
[ ] Task 1.1 commit/manifest verified
[ ] manifest checksum independently matches frozen value
[ ] exactly 1,500 manifest entries

[ ] actual EDGAR schema inspected
[ ] actual section columns inspected
[ ] section ordering deterministic and evidence-based

[ ] exactly 1,500 EDGAR rows resolved
[ ] no missing source rows
[ ] no duplicate source matches
[ ] CIK/year/source identity match manifest

[ ] zero-text filings checked
[ ] any ambiguous case triggered user clarification

[ ] minimal conservative normalization implemented
[ ] no advanced cleaning / LLM rewriting
[ ] no invented text
[ ] missing sections stay missing

[ ] exactly 1,500 deterministic Markdown files
[ ] unique deterministic output filenames
[ ] UTF-8 + deterministic newline policy

[ ] YAML frontmatter on every document
[ ] CIK/fiscal_year integer semantics
[ ] source identity preserved
[ ] company provenance honest
[ ] form_type == 10-K
[ ] source == edgar_corpus
[ ] no accession fabricated

[ ] generated files under storage abstraction
[ ] normalized corpus under artifacts/normalized/<version>
[ ] unresolved version convention triggered a question

[ ] normalization_build_sha256 computed/documented
[ ] second run is byte-identical

[ ] section coverage recorded
[ ] document statistics recorded
[ ] >=10 manual source-to-Markdown inspections pass

[ ] small tracked summary created
[ ] Markdown corpus remains Git-ignored

[ ] focused normalization tests added
[ ] doctor passes
[ ] portable tests: zero failures
[ ] full tests: zero failures

[ ] frozen data unchanged
[ ] no network access
[ ] no unapproved dependency

[ ] PHASE1_NORMALIZATION.md created
[ ] REPOSITORY_STRUCTURE.md updated if needed
[ ] Progress.md updated

[ ] staged content reviewed
[ ] one coherent Task 1.2 commit created
[ ] no Task 1.3 work included
[ ] no force-push
```

---

# STOP CONDITIONS

**STOP AND ASK ME** rather than guessing if:

```text
Task 1.1 manifest checksum differs
manifest row cannot map to exactly one EDGAR row
selected filing has zero usable text
section schema/order is ambiguous
company/metadata provenance is unclear
normalizer version is not defined
artifact location conflicts with storage contract
existing normalized artifact conflicts with current config/build
new dependency appears necessary
documentation contradicts itself on normalization semantics
Git remote/push behavior is unclear
any implementation decision otherwise requires guessing
```

---

# FINAL RESPONSE TO ME

Return:

## Task

```text
task_1.2_minimal_document_normalization.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Input

Report:

```text
manifest path
manifest row count
development_manifest_sha256
source rows resolved
identity mismatches
```

## Normalization Contract

List exact transformations applied.

## Frontmatter

List final YAML keys and provenance.

Explicitly report:

```text
fabricated accession fields: NONE
```

## Output

Report:

```text
normalizer_version
normalized artifact path
Markdown document count
total normalized size
normalization_build_sha256
```

## Section Coverage

Report per-section counts/percentages.

## Document Statistics

Report:

```text
character count min/median/p95/max
non-empty sections min/median/p95/max
```

## Determinism

Report:

```text
run 1 checksum
run 2 checksum
identical files: YES/NO
```

## Manual Inspection

Report inspected documents, years represented, and result.

## Tests

Report new Task 1.2 tests, portable/full passed/failed/skipped counts, and doctor status.

## Frozen Data

Confirm:

```text
data/ unchanged
```

## Files Modified

List actual tracked/project files only. Do not list all 1,500 ignored Markdown files.

## Git

Report:

```text
commit created: YES/NO
commit hash
commit message
remote status
push performed: YES/NO
```

## Progress.md

Confirm the Phase 1.2 entry was appended.

## Next Task

If PASS:

```text
task_1.3_minimal_fixed_window_chunker.md
```

Do not start it.

Finally state:

```text
No Task 1.3 work started.
```

Stop and wait for my approval.
