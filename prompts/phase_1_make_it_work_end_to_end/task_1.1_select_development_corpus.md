# Task 1.1 — Select the Development Corpus

You are working inside my SEC RAG repository.

Task file:

task_1.1_select_development_corpus.md

We are executing:

Phase 1 — Make It Work End to End
Task 1.1 — Select the Development Corpus

Current project status:

Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
Phase 1 — Make It Work End to End — STARTING
  1.1 Select Development Corpus   — CURRENT

Phase 0 has been checkpointed in Git and tagged `phase-0-complete`.

This is the first Phase 1 engineering task.

---

# CRITICAL RULE — DO NOT ASSUME

This rule applies to the entire task.

If something required to make an implementation decision is not clearly
established by:

1. the current repository,
2. `PROJECT_EXECUTION.md`,
3. `DATA_READINESS_REPORT.md`,
4. current specialized project documentation,
5. reproducible inspection of the frozen datasets,

then:

STOP AND ASK ME.

Do not silently choose a reasonable-looking answer.

Do not fill gaps using general knowledge.

Do not infer a schema field's meaning from its name alone.

Do not choose a sampling strategy merely because it seems sensible.

Do not resolve contradictory documentation yourself.

When asking me a question:

- state exactly what is ambiguous,
- state what you observed,
- give the smallest useful set of options if applicable,
- explain what decision depends on the answer,
- do not continue implementation past that decision point.

Examples of questions that MUST be asked if repository evidence does not
resolve them:

- Which deterministic sampling rule should be used?
- Which row should represent a `(CIK, year)` if EDGAR has duplicates?
- Which XBRL submission should establish alignment if multiple candidates
  exist?
- Which manifest location should be authoritative if storage documentation
  does not define one?
- Which source field should be treated as document identity if more than
  one candidate exists?
- Whether a discrepancy from the frozen 5,646 aligned population is an
  expected schema evolution or a bug.

Inspection before asking is encouraged.

Assumption is not.

---

# AUTHORITATIVE TASK DEFINITION

The current `project_plan/PROJECT_EXECUTION.md` defines Task 1.1 as:

- build the eligible 2016–2020 aligned `(CIK, year)` population,
- select 1,500 filings reproducibly,
- use a deterministic seed or deterministic sampling rule,
- save the selected corpus manifest,
- record company/year distribution,
- ensure every selected filing can be traced back to source data.

The frozen execution facts include:

EDGAR-CORPUS filings:              91,086
EDGAR-CORPUS CIKs:                 25,937
EDGAR-CORPUS range:                1993–2020

XBRL facts:                        90,685,753
XBRL submissions:                 218,166

authoritative EDGAR↔XBRL
10-K alignment, 2016–2020:         5,646 / 6,950 = 81.24%

Phase 1 development corpus target: 1,500 filings

The 1,500 filings must be selected from the aligned 2016–2020 population,
not randomly from the full 91,086-filing EDGAR corpus.

---

# IMPORTANT HISTORICAL WARNING

Older validation material contains superseded alignment figures such as:

81.71%

Do NOT use those historical numbers as the Task 1.1 target.

The current authoritative alignment is:

5,646 / 6,950 = 81.24%

for EDGAR↔XBRL 10-K coverage in 2016–2020 under the corrected alignment
definition.

If your independent reconstruction does not reproduce the authoritative
population closely enough to explain exactly:

STOP.

Investigate first.

Do not simply select 1,500 from a differently defined population.

---

# PURPOSE

Task 1.1 creates the small, reproducible development corpus that all
remaining Phase 1 tasks will consume.

The flow is:

frozen EDGAR-CORPUS
        +
frozen XBRL metadata
        ↓
authoritative aligned 2016–2020 population
        ↓
deterministic selection
        ↓
1,500-filing development manifest
        ↓
Task 1.2 normalization

This task does NOT normalize filings.

This task selects them.

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. inspect the authoritative alignment methodology,
2. inspect the actual EDGAR and XBRL schemas,
3. independently reconstruct the eligible 2016–2020 population,
4. validate that population against the frozen 5,646 figure,
5. resolve document identity and duplicate semantics from existing evidence,
6. select exactly 1,500 filings using an explicitly reproducible rule,
7. create a traceable development-corpus manifest,
8. record population and selected-corpus distributions,
9. add automated tests for deterministic selection/invariants,
10. document the development-corpus contract,
11. update `Progress.md`,
12. commit the successful Task 1.1 work as one coherent Git commit.

Do NOT begin Task 1.2.

---

# STEP 1 — VERIFY PHASE 0 CHECKPOINT

Before modifying anything, inspect Git:

git status --short
git branch --show-current
git log --oneline --decorate -5
git tag --list

Verify:

- branch is the expected development branch, normally `main`,
- the Phase 0 checkpoint exists,
- `phase-0-complete` exists,
- no unexplained Phase 1 implementation is already present.

If the repository state materially differs from the Phase 0 checkpoint
described in `Progress.md`:

STOP AND ASK ME.

Do not stack Task 1.1 on unexplained changes.

---

# STEP 2 — VERIFY FOUNDATION

Activate `.venv`.

Run:

python scripts/dev.py doctor
python scripts/dev.py test --portable

Expected:

0 failures

Do not begin corpus-selection implementation on a broken foundation.

---

# STEP 3 — READ CURRENT AUTHORITATIVE DOCUMENTATION

Read before writing code:

project_plan/PROJECT_EXECUTION.md
DATA_READINESS_REPORT.md
Progress.md

project_plan/STORAGE.md
project_plan/CONFIGURATION.md
project_plan/REPOSITORY_STRUCTURE.md
project_plan/GIT_CONVENTIONS.md
project_plan/TESTING.md

Also inspect any documentation that specifically describes the corrected:

EDGAR-CORPUS ↔ XBRL 10-K 2016–2020 alignment

Do not use `PROJECT_SPEC.md` to override a newer corrected metric if it is
known to be stale.

---

# STEP 4 — FIND THE AUTHORITATIVE ALIGNMENT IMPLEMENTATION

Inspect existing code, especially:

src/ingest/audit_data.py
src/ingest/validate.py

Find the code that produced the final frozen:

5,646 / 6,950 = 81.24%

EDGAR↔XBRL 10-K alignment for 2016–2020.

Prefer reproducing the finalized audited methodology rather than inventing
a new join.

Document:

- EDGAR input fields used,
- XBRL input fields used,
- year field used,
- form filtering,
- CIK normalization,
- any deduplication,
- exact join grain.

The chosen semantic year alignment is expected to involve XBRL `fy`, but
verify this from the authoritative implementation/documentation.

Do not assume because an older script used another field.

---

# STEP 5 — INSPECT ACTUAL EDGAR-CORPUS SCHEMA

Read the Parquet schema directly.

Do not load all 5.77 GB into Python memory.

Use DuckDB/PyArrow metadata or similarly efficient inspection.

Record actual fields and types.

At minimum determine which fields provide:

- CIK,
- year,
- company name if available,
- source/document identity,
- source split,
- filename or equivalent source locator,
- filing text/sections.

Do not invent fields.

Do not rename schema concepts during this task unless necessary at the
manifest boundary.

---

# STEP 6 — INSPECT ACTUAL XBRL SUBMISSION SCHEMA

Inspect the schema of the relevant XBRL table(s), preferably read-only.

Determine actual fields available for:

- CIK,
- form,
- fiscal year,
- accession / `adsh`,
- filed date,
- period end if available.

Do not mutate:

data/xbrl.duckdb

Open read-only where possible.

---

# STEP 7 — REMEMBER THE ACCESSION LIMITATION

EDGAR-CORPUS does not provide a trustworthy SEC accession mapping in the
current frozen dataset.

Do NOT fabricate one.

Do NOT infer an EDGAR accession from XBRL merely because:

CIK + year

matches.

An XBRL `adsh` may be retained as:

alignment evidence

if the audited methodology supports it.

It must NOT be labeled as:

the EDGAR-CORPUS accession

unless the repository provides evidence establishing that mapping.

Source traceability must use the actual identity available in
EDGAR-CORPUS.

---

# STEP 8 — NORMALIZE JOIN TYPES EXPLICITLY

Historical validation found a silent type mismatch:

EDGAR CIK/year were strings
XBRL CIK was numeric

Do not rely on implicit conversion.

Explicitly normalize:

CIK -> integer-compatible representation
year -> integer-compatible representation

for joining.

Reject or report rows that cannot be converted.

Do not silently coerce malformed identifiers to arbitrary values.

---

# STEP 9 — DEFINE THE ELIGIBLE WINDOW

The candidate EDGAR population must be limited to:

2016
2017
2018
2019
2020

and to the filing semantics required by the authoritative 10-K alignment.

Do not include:

1993–2015
2021+
10-Qs
non-10-K XBRL forms

unless the audited alignment logic explicitly requires an intermediate row
for a documented reason.

The final eligible development population is the aligned 10-K population.

---

# STEP 10 — RECONSTRUCT THE ELIGIBLE POPULATION

Build the eligible population independently from frozen source data.

The target authoritative aligned population is:

5,646

aligned EDGAR company-year pairs.

Also preserve enough information to explain the denominator:

6,950

where the audited method makes it available.

Produce internal checks such as:

total EDGAR candidate company-year pairs
total matched company-year pairs
total unmatched company-year pairs
coverage percentage

Expected authoritative result:

5,646 / 6,950 = 81.24%

Do not merely hardcode these numbers.

Recompute them.

---

# STEP 11 — HANDLE DUPLICATES EXPLICITLY

Before selection, inspect the candidate grain.

Check whether there are duplicate EDGAR records for:

(CIK, year)

or whatever exact document grain the audited methodology requires.

Check whether XBRL produces multiple candidate 10-K submissions for the same
alignment key.

If duplicates exist, search the authoritative audit logic/documentation for
the already-approved resolution.

If no approved rule exists:

STOP AND ASK ME.

Do NOT choose:

first row
latest filing
earliest filing
largest filing
first accession
lexicographic accession

without an explicit project rule.

---

# STEP 12 — VALIDATE THE 5,646 POPULATION

Task 1.1 must not proceed to selection until the eligible population has
been validated.

Preferred outcome:

eligible aligned population = 5,646 unique development units

If you obtain a different count:

1. re-check types,
2. re-check form filtering,
3. re-check fiscal-year semantics,
4. re-check duplicates,
5. compare against the audited implementation.

If the discrepancy remains:

STOP AND ASK ME.

Report:

- observed count,
- expected count,
- exact query/method used,
- likely source of discrepancy if known.

Do not adjust filters until the number becomes 5,646 by coincidence.

---

# STEP 13 — DETERMINE THE DOCUMENT IDENTITY CONTRACT

Every selected filing must be traceable back to the exact source record.

Inspect available EDGAR metadata and establish the smallest stable source
identity.

Possible fields might include:

source split
source filename
row/document identifier
CIK
year

but use only fields that actually exist.

The manifest must not depend on:

row number after an unstable unordered scan

unless the row locator is proven stable under the actual source files.

If no stable EDGAR document identity is clearly available:

STOP AND ASK ME.

Do not invent one.

---

# STEP 14 — DETERMINE THE SAMPLING RULE

`PROJECT_EXECUTION.md` requires:

a deterministic seed OR deterministic sampling rule

but does not, by itself, specify which exact rule to use.

Search the repository for a previously frozen Phase 1 sampling rule.

If one exists:

use it.

If no exact rule exists:

STOP AND ASK ME BEFORE SELECTING THE 1,500.

Present concise options such as:

A. deterministic cryptographic-hash ordering over stable document identity,
   take first 1,500

B. fixed-seed pseudo-random sample over a canonically sorted eligible
   population

C. another selection rule already implied by discovered project constraints

Do not choose between A/B yourself if the repository does not already
resolve it.

This is a deliberate user decision because the manifest will become the
shared Phase 1 development corpus.

---

# STEP 15 — DO NOT STRATIFY UNLESS SPECIFIED

Do not automatically stratify the 1,500 selection by:

year
company
industry
source split
document length

unless the current project documentation explicitly requires it.

The plan says:

record company/year distribution

not:

force a balanced company/year distribution.

If you believe stratification is necessary for reproducibility or
representativeness and the project does not specify it:

ASK ME FIRST.

---

# STEP 16 — PREVENT ACCIDENTAL COMPANY DOMINATION

Even if the sampling rule is already defined, inspect selected-corpus
concentration after selection.

Report:

number of unique CIKs
filings per CIK distribution
maximum filings from one CIK

Do not alter the selection based on those statistics unless a rule says to.

If a pathological concentration appears and no policy defines whether it
is acceptable:

report it and ask before changing the selection.

---

# STEP 17 — SELECT EXACTLY 1,500

Only after the sampling rule is resolved:

select exactly:

1,500

eligible filings.

Assertions:

selected rows == 1,500
selected identities unique
every selected row belongs to eligible population
every year in [2016, 2020]
every selected unit satisfies the authoritative alignment definition

No replacement sampling.

---

# STEP 18 — MANIFEST LOCATION

Determine the intended manifest location from:

STORAGE.md
REPOSITORY_STRUCTURE.md
GIT_CONVENTIONS.md
PROJECT_EXECUTION.md

The manifest is:

small
reproducibility-critical
generated from frozen inputs
required by later Phase 1 tasks

Do not guess whether it belongs under:

artifacts/
results/
configs/
another documented location

If repository documentation does not clearly establish the authoritative
location:

STOP AND ASK ME.

If the design calls for both:

- ignored working artifact, and
- small tracked reproducibility manifest,

document the distinction clearly.

---

# STEP 19 — MANIFEST CONTENT

The manifest must contain only fields justified by actual source data and
alignment evidence.

At minimum it must support:

- stable development document identity,
- CIK,
- fiscal/alignment year,
- company name if actually available,
- EDGAR source identity/location,
- EDGAR source split if relevant,
- source = `edgar_corpus`,
- enough XBRL alignment evidence to reproduce eligibility, if appropriate.

Possible XBRL fields:

- `adsh`,
- XBRL form,
- XBRL `fy`,

may be included only if they are unambiguous under the authoritative join.

Again:

do NOT label XBRL `adsh` as the EDGAR accession.

---

# STEP 20 — MANIFEST TYPES

Where applicable:

CIK -> int64
year -> int32

These match the downstream Phase 1 normalization contract.

Do not downcast identifiers unsafely.

String source identifiers remain strings.

---

# STEP 21 — MANIFEST SORT ORDER

The final manifest must have a deterministic canonical ordering independent
of filesystem scan order.

The sort order must be documented.

Use an already-defined rule if one exists.

Otherwise choose a natural ordering only if it does not affect which rows
were sampled.

For example, selection may be done according to the approved deterministic
selection rule and the stored final manifest may then be canonically sorted
for readability.

If changing order could affect reproducibility of the selection algorithm,
make that distinction explicit.

---

# STEP 22 — RECORD ELIGIBLE POPULATION DISTRIBUTIONS

For the full eligible 5,646 population, report at least:

count
unique CIKs
count by year
percentage by year

Also inspect:

filings per CIK

Do not calculate expensive irrelevant statistics.

---

# STEP 23 — RECORD SELECTED CORPUS DISTRIBUTIONS

For the selected 1,500 report at minimum:

total filings
unique CIKs
count by year
percentage by year
filings-per-CIK:
  min
  median
  p95 or another clearly labeled high percentile
  max

If company names are available, report:

unique companies

Do not treat company-name uniqueness as stronger than CIK uniqueness.

CIK is the entity key.

---

# STEP 24 — COMPARE ELIGIBLE VS SELECTED DISTRIBUTIONS

Provide a small comparison table.

Example:

| Year | Eligible | Eligible % | Selected | Selected % |
|---|---:|---:|---:|---:|
| 2016 | ... | ... | ... | ... |
| ... | ... | ... | ... | ... |

Do not claim the selected set is statistically representative unless the
sampling method justifies that statement.

Say only what the numbers support.

---

# STEP 25 — PRESERVE SELECTION PROVENANCE

Store enough metadata alongside the manifest to reproduce it.

At minimum:

schema/version
creation timestamp
source datasets
eligible date window
alignment definition reference
eligible count
selection count
selection method
seed if one exists
sorting rule
relevant source file identifiers
code version / git SHA where useful
manifest checksum
selection configuration checksum if implemented

Do not introduce an elaborate experiment registry.

Keep it simple.

---

# STEP 26 — HASH THE FINAL MANIFEST

Compute a deterministic checksum over the canonical final manifest.

Prefer:

SHA-256

or another standard cryptographic hash already used in the project.

Document exactly:

- serialization used,
- column order,
- row order,
- hash algorithm.

This lets later tasks verify they are using exactly the same 1,500 filings.

Do not confuse this with:

chunk_config_hash

which belongs to later chunking configuration.

Use an explicit name such as:

development_manifest_sha256

---

# STEP 27 — IMPLEMENT THE SELECTION CODE IN AN APPROPRIATE LOCATION

Inspect repository conventions first.

A reasonable implementation may be a script such as:

scripts/select_development_corpus.py

or a small reusable module plus script.

But do not assume that exact location if repository conventions specify
another location.

The code must:

- read frozen data only,
- reconstruct eligibility,
- select deterministically,
- write only generated/tracked output locations,
- print a concise summary,
- exit non-zero on violated invariants.

Do NOT put selection logic into:

src/ingest/

Data ingestion is frozen.

---

# STEP 28 — DO NOT MUTATE DATA PREPARATION CODE

Preferred:

src/ingest/ unchanged

Do not modify:

fetch_*.py
validate.py
audit_data.py

merely to support Phase 1 selection.

You may import/reuse safe logic conceptually, but Data Preparation is
complete and historical audit code should remain intact.

If reuse requires changing it:

STOP AND ASK ME.

---

# STEP 29 — READ-ONLY DATA POLICY

Task 1.1 may read:

data/edgar_corpus/*.parquet
data/xbrl.duckdb
other frozen metadata only where the authoritative method requires it

Task 1.1 must never:

modify Parquet files
modify DuckDB tables
create XBRL indexes
rewrite data/
download replacement data
fetch from SEC
fetch from Hugging Face
change source records

All new output belongs outside frozen `data/` unless the current storage
contract explicitly says otherwise.

---

# STEP 30 — NO NETWORK ACCESS

This task requires no internet access.

Do not call:

SEC
Hugging Face
OpenAI
Anthropic
AWS
external APIs

All required source data already exists locally.

If you believe network access is necessary:

STOP AND ASK ME.

Explain what local information is missing.

---

# STEP 31 — DO NOT USE THE SERVING-SPIKE CORPUS

Task 0.10 built a disposable:

100,000-chunk serving-spike corpus

under:

artifacts/serving_spike/

Do NOT reuse its selection.

It was explicitly:

NOT THE PHASE 1 DEVELOPMENT CORPUS.

Task 1.1 must independently create the official 1,500-filing development
manifest from the authoritative aligned population.

---

# STEP 32 — DO NOT TOUCH THE 990 PRIMARY FILINGS

The 990 primary SEC HTML filings are not the Phase 1 narrative development
corpus for Task 1.1.

Do not substitute:

data/raw/primary/

for the EDGAR-CORPUS development corpus.

Those primary filings become important later, particularly for evidence
alignment/evaluation.

---

# STEP 33 — AUTOMATED TESTS

Add focused tests for Task 1.1.

Do not run the full 5.77 GB corpus repeatedly inside unit tests.

Separate pure deterministic logic from large-data integration checks where
helpful.

Tests should cover applicable invariants such as:

- canonical identifier normalization,
- selection determinism,
- same input + same config -> same 1,500 identities,
- different seed/config changes selection if a seeded rule is chosen,
- no duplicate selected identity,
- exactly 1,500 selected,
- selected set is subset of eligible set,
- year bounds 2016–2020,
- manifest canonical ordering,
- manifest checksum determinism,
- malformed identifiers rejected clearly.

Do not fabricate a test for an API that was not actually implemented.

---

# STEP 34 — LARGE-DATA INTEGRATION VERIFICATION

Run the real selection against the frozen data once.

Verify:

eligible aligned population: expected 5,646
selected filings:            exactly 1,500

If eligible population does not match:

DO NOT let a unit test fixture hide the discrepancy.

Stop according to the earlier rule.

---

# STEP 35 — MANUAL TRACEABILITY CHECK

Manually inspect a small number of selected rows, for example:

5–10

across multiple years.

For each verify:

manifest identity
→ source EDGAR record
→ CIK/year
→ alignment membership

If XBRL evidence is stored:

verify the corresponding XBRL row(s).

Do not claim accession-level EDGAR traceability where none exists.

---

# STEP 36 — VERIFY DETERMINISM IN A FRESH PROCESS

Run the selection twice from the same frozen inputs/config.

The resulting:

selected identities
manifest content
manifest checksum

must be identical.

If not:

Task 1.1 fails.

Do not accept "same approximate distribution."

This manifest is supposed to be frozen.

---

# STEP 37 — IDEMPOTENCY / OVERWRITE POLICY

Do not silently overwrite an existing official development manifest that
has a different checksum.

If an existing manifest is found:

1. inspect it,
2. compare its selection configuration/checksum,
3. if identical, reuse or regenerate safely according to the documented
   policy,
4. if different and no overwrite policy is documented:

STOP AND ASK ME.

Do not destroy a prior frozen Phase 1 manifest silently.

---

# STEP 38 — CREATE DOCUMENTATION

Create a focused document such as:

project_plan/PHASE1_DEVELOPMENT_CORPUS.md

if this naming/location is consistent with repository documentation.

If repository conventions specify another document name:

follow them.

Document:

- purpose,
- source datasets,
- authoritative alignment definition,
- eligible population,
- selection rule,
- selected count,
- manifest schema,
- manifest location,
- manifest checksum,
- year distribution,
- CIK/company distribution,
- source traceability contract,
- known limitations.

Explicitly note:

EDGAR-CORPUS does not provide a trustworthy accession mapping, so the
manifest does not fabricate one.

---

# STEP 39 — KEEP LIMITATIONS HONEST

Document relevant limitations such as:

- Phase 1 development corpus is only 1,500 filings.
- It is restricted to the 2016–2020 aligned region.
- EDGAR-CORPUS structured tables are absent.
- Some EDGAR sections are sparse.
- The corpus is for development/integration, not the final Phase 2
  benchmark.
- The Phase 1 corpus selection is not a locked TEST split.
- XBRL alignment establishes eligibility but does not create an EDGAR
  accession that the source does not provide.

Do not overstate representativeness.

---

# STEP 40 — DO NOT CREATE DEV/TEST SPLITS

Phase 2 owns the company-disjoint DEV/TEST evaluation split.

Task 1.1 creates:

the Phase 1 development corpus

only.

Do not split the 1,500 into:

train/dev/test

unless `PROJECT_EXECUTION.md` explicitly instructs it somewhere else.

If such a requirement appears in another document and conflicts:

ASK ME.

---

# STEP 41 — DO NOT GENERATE QUESTIONS

Do not create the Phase 1 ~200-question smoke evaluation.

That belongs to:

Task 1.9

Task 1.1 only establishes the document population that later tasks will
consume.

---

# STEP 42 — DO NOT NORMALIZE TEXT

Do not create:

Markdown filings
YAML frontmatter
chunks
embeddings
LanceDB indexes

Those belong to Tasks:

1.2+
1.3+
1.4+
1.5+

The selected manifest should point back to frozen source documents.

---

# STEP 43 — NO NEW DEPENDENCIES EXPECTED

Expected dependency changes:

none

Use existing:

DuckDB
PyArrow
stdlib hashing/JSON/path utilities
pytest

If a new package appears necessary:

STOP AND ASK ME BEFORE MODIFYING REQUIREMENTS.

---

# STEP 44 — RUN FOUNDATION TESTS AFTER IMPLEMENTATION

After Task 1.1 code/tests are complete:

python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test

Expected:

0 failures

Record actual test counts.

Do not hardcode the old 70-test total because Task 1.1 will add tests.

---

# STEP 45 — VERIFY FROZEN DATA INVARIANTS

Recheck lightweight invariants after selection.

At minimum:

data/xbrl.duckdb size unchanged
raw XBRL ZIP count unchanged
primary filing count unchanged
EDGAR source Parquet files unchanged in count/size where practical

No full hashing of 26 GB required.

---

# STEP 46 — GIT SAFETY

Run:

git status --short
git status --ignored --short
git add -n .
git diff

Verify no generated large data is accidentally stageable.

Especially ensure:

data/ ignored
artifacts/ ignored where applicable
.venv/ ignored
.tmp/ ignored
.env ignored
model weights ignored
logs ignored

The small official manifest may be trackable only if the repository's
resolved manifest policy says it should be.

---

# STEP 47 — SECRET / PERSONAL DATA SCAN

Inspect all newly trackable files for:

API keys
tokens
passwords
credentials
real SEC contact email
personal absolute paths

No secrets should be introduced.

No network credential is needed for this task.

---

# STEP 48 — UPDATE `Progress.md`

Preserve all existing history.

Append:

## YYYY-MM-DD — Phase 1.1 Select Development Corpus

using the current local date.

Include:

### Objective

Explain that the first Phase 1 task freezes the small 1,500-filing
development population used by the crude vertical slice.

### Initial State

Record:

Phase 0 checkpoint/tag
Phase 1 not previously implemented
no development manifest existed, if true

### Alignment Method

Record the exact authoritative reconstruction:

EDGAR fields
XBRL fields
join grain
form filter
year semantics
type normalization
duplicate handling

### Eligible Population

Report:

candidate denominator
aligned population
coverage

Expected:

5,646 / 6,950 = 81.24%

only if independently reproduced.

### Selection Rule

Record the exact user-approved or previously documented rule.

If seed-based:

record seed.

If hash-based:

record hash algorithm/key.

### Selected Corpus

Report:

1,500 filings
unique CIKs
year distribution
filings-per-CIK distribution
manifest checksum

### Traceability

Explain exactly how each manifest row maps back to EDGAR source data.

Explicitly state accession limitations.

### Files Created / Modified

List actual files only.

### Verification

Record:

determinism
manual traceability checks
tests
doctor
portable suite
full suite
frozen-data invariants

### Git

Record the planned/actual Task 1.1 commit.

### Result

Use exactly one:

PASS — 1,500-filing Phase 1 development corpus selected reproducibly

WARN — development corpus selected but one non-blocking issue remains

BLOCKED — authoritative development corpus could not be selected safely

### Phase Status

If PASS:

Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
Phase 1 — Make It Work End to End — IN PROGRESS
  1.1 Select Development Corpus   — COMPLETE
  1.2 Minimal Normalization       — NEXT

---

# STEP 49 — COMMIT THIS SUBTASK

Unlike the Phase 0 implementation tasks, Phase 1 now follows the project's
normal Git discipline.

After:

- implementation passes,
- tests pass,
- manifest is verified,
- `Progress.md` is updated,
- staged content is reviewed,

create one coherent Task 1.1 commit.

Preferred commit message:

Select reproducible Phase 1 development corpus

or another concise equivalent consistent with `GIT_CONVENTIONS.md`.

Do not include Task 1.2 work.

Do not tag the phase yet.

Phase tags belong at phase completion.

---

# STEP 50 — PUSH POLICY

Inspect:

git remote -v

If no remote is configured:

do not invent one.

Record:

push deferred — no remote configured

If a remote is already configured and `GIT_CONVENTIONS.md` instructs
pushing at session end, follow the existing repository policy.

If anything about push authorization is ambiguous:

ASK ME.

Never guess a remote or force-push.

---

# ACCEPTANCE CRITERIA

Task 1.1 is complete only if:

[ ] Phase 0 checkpoint exists
[ ] Phase 1 had not already started unexpectedly

[ ] current PROJECT_EXECUTION.md read
[ ] DATA_READINESS_REPORT.md read
[ ] authoritative alignment implementation inspected

[ ] actual EDGAR schema inspected
[ ] actual XBRL schema inspected

[ ] CIK types normalized explicitly
[ ] year types normalized explicitly

[ ] 2016–2020 window enforced
[ ] 10-K alignment semantics enforced

[ ] authoritative eligible population independently reconstructed
[ ] expected 5,646 aligned pairs reproduced
[ ] denominator/coverage explained

[ ] duplicate `(CIK, year)` behavior inspected
[ ] duplicate-resolution rule is documented, not assumed

[ ] stable EDGAR source identity established
[ ] no EDGAR accession fabricated
[ ] XBRL `adsh` not mislabeled as EDGAR accession

[ ] exact deterministic selection rule established
[ ] if repository did not specify that rule, user was asked before selection

[ ] exactly 1,500 filings selected
[ ] no selected duplicates
[ ] all selected filings belong to eligible population
[ ] all selected years are 2016–2020

[ ] manifest location follows documented storage/Git policy
[ ] if location was ambiguous, user was asked

[ ] manifest is deterministic
[ ] manifest is canonically ordered
[ ] manifest checksum recorded
[ ] repeat run produces identical checksum

[ ] eligible year distribution recorded
[ ] selected year distribution recorded
[ ] selected unique-CIK count recorded
[ ] filings-per-CIK distribution recorded

[ ] 5–10 manual traceability checks pass

[ ] no frozen source data modified
[ ] no network access used
[ ] no data download performed
[ ] serving-spike corpus not reused
[ ] primary-doc corpus not substituted

[ ] no normalization implemented
[ ] no chunking implemented
[ ] no embeddings implemented
[ ] no index implemented
[ ] no evaluation questions generated

[ ] focused automated tests added
[ ] doctor passes
[ ] portable tests have zero failures
[ ] full suite has zero failures

[ ] development-corpus documentation created
[ ] Progress.md updated

[ ] Git staged content reviewed
[ ] one Task 1.1 commit created
[ ] no Task 1.2 work included

[ ] no force-push