# Phase 4 — Task 4.1: Full-Corpus Normalization

## Objective

Scale the already-selected normalization pipeline from the Phase 1 development
corpus to the **complete EDGAR-CORPUS** and produce a deterministic,
versioned, validated normalization artifact that Task 4.2 can consume.

This task is deliberately narrow:

- normalize the complete EDGAR-CORPUS;
- preserve deterministic document identity;
- preserve the current/frozen metadata contract needed downstream;
- produce a config hash and build manifest;
- validate completeness and determinism;
- record real throughput, artifact size, failures, and resource usage.

This task does **not** chunk, tokenize for production chunking, embed, build an
index, run retrieval, call an LLM, open protected TEST, or start Task 4.2.

Task 4.1 is a **CPU + disk I/O task**. Do not require or use the GPU.

---

# Authoritative repository precedence

Before changing anything, re-read the live repository in this order:

1. `project_plan/PROJECT_EXECUTION.md`
2. `Progress.md`
3. `project_plan/GIT_CONVENTIONS.md`
4. `project_plan/PHASE3_EXIT_AUDIT.md`
5. `project_plan/PHASE1_NORMALIZATION.md`
6. `project_plan/REPOSITORY_STRUCTURE.md`
7. `project_plan/STORAGE.md`
8. `project_plan/CONFIGURATION.md`
9. Task 2.9 canonical metadata/chunk-schema documentation and implementation
10. Task 2.10 canonical hashing / `semantic_hash()` implementation
11. current normalization source:
    - `src/normalize/edgar_markdown.py`
    - `scripts/normalize_development_corpus.py`
12. current normalization config/result:
    - `configs/normalize_development_corpus.json`
    - `results/phase_1_2_normalization_summary.json`
13. any current Phase 4 config/result conventions already present

Repository truth wins over stale values in this prompt.

If the current repository materially contradicts this prompt, STOP and report
the contradiction instead of silently choosing a new design.

---

# Verified state entering Task 4.1

Phase 3 has completed its exit audit and Phase 4 has not yet started.

The roadmap defines Task 4.1 as:

```text
Full-corpus normalization

- Apply the selected normalization pipeline to the complete EDGAR-CORPUS.
- Preserve deterministic IDs.
- Preserve frozen metadata schema.
- Record config hash and build manifest.
```

The raw EDGAR-CORPUS contains:

```text
91,086 filings
25,937 distinct CIKs
year range: 1993–2020
```

The selected normalization implementation originated in Task 1.2 and was
corrected to:

```text
normalizer_version:
phase1-minimal-v1
```

The Phase 1 normalization contract was intentionally conservative:

```text
CRLF / CR -> LF
strip leading/trailing whitespace per section
omit null/empty/whitespace-only sections
emit SEC Item headings
preserve text rather than semantically rewrite it
YAML frontmatter
UTF-8
exactly one trailing newline
no OCR
no LLM cleanup
no table reconstruction
no boilerplate rewriting
```

Do not silently redesign normalization now merely because the corpus is larger.

---

# Important distinction: normalization vs later Phase 4 work

Task 4.1 must not perform work belonging to later tasks.

Do NOT:

```text
apply the Phase 3 256-token chunker       # Task 4.2
load Qwen3-Embedding-0.6B                 # Task 4.3
create embeddings                          # Task 4.3
build LanceDB vector/FTS indexes           # Task 4.4
export serving XBRL                        # Task 4.5
call a generation model                    # Task 4.6
add production guardrails                  # Tasks 4.7–4.9
build FastAPI                               # Task 4.10
deploy                                      # Task 4.11
run locked TEST                             # Task 4.14
```

No GPU work is required in this task.

---

# Git policy

This is no longer loop engineering.

Execute **Task 4.1 only**.

Before work:

```powershell
git status
git branch --show-current
git log -5 --oneline --decorate
```

Follow `project_plan/GIT_CONVENTIONS.md`.

Prefer a dedicated branch if the repository convention uses task branches,
for example:

```text
phase4/full-corpus-normalization
```

Do not invent a branch convention if the repository specifies another one.

The working tree must be clean except for explicitly understood local,
git-ignored controller/supervisor files.

If tracked unexplained modifications exist, STOP.

At the end, commit Task 4.1 coherently, then STOP before Task 4.2.

---

# Stage 1/10 — Preflight and provenance audit

Print:

```text
[STAGE 1/10] Task 4.1 preflight
```

Verify:

1. Phase 3 exit audit = PASSED.
2. Phase 4 has not already started.
3. Task 4.1 is the next roadmap task.
4. EDGAR-CORPUS source files exist and remain frozen/read-only.
5. The source corpus reproduces the expected total of 91,086 filings.
6. `src/normalize/edgar_markdown.py` is the selected normalizer implementation
   unless current repository docs say otherwise.
7. `normalizer_version` still resolves to `phase1-minimal-v1` unless an
   explicit later repository decision superseded it.
8. Phase 1 normalization fixtures/results are still present.
9. Task 2.9 frozen metadata schema is available.
10. Task 2.10 canonical hashing is available.
11. protected TEST is unopened.
12. official TEST usage is still 0/3.
13. no generation/API credential is required.
14. free disk is sufficient for a full normalization artifact plus safe
    temporary/checkpoint overhead.

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Record exact counts.

Do not run GPU/model smoke tests merely because this machine has a GPU.

---

# Stage 2/10 — Audit source schema and full-corpus identity

Print:

```text
[STAGE 2/10] Audit full EDGAR-CORPUS identity
```

Inspect all source Parquet files directly and record:

```text
source files
row counts per split
total rows
unique document IDs
unique CIKs
year min/max
section columns
null/empty identity fields
duplicate document IDs
duplicate (cik, year) pairs
```

Expected headline total:

```text
91,086 filings
```

Do not assume all source rows are suitable merely because Task 1.1 selected
a clean 1,500-row aligned subset.

## Deterministic source identity

Reuse the repository's established EDGAR document identity convention.

Task 1 used the source `filename`/`document_id`, e.g.:

```text
1005817_2016.htm
```

If the current repository still defines that as canonical EDGAR-CORPUS
document identity, keep it exactly.

Do not switch to:

- row number;
- array position;
- random UUID;
- a newly invented accession;
- a hash-only ID;

unless the current canonical schema explicitly requires a derived UID in
addition to the source identity.

Every source filing must map deterministically to exactly one normalized
output record/document.

If duplicate source identity exists in the 91,086-row corpus, STOP before
building and report it.

---

# Stage 3/10 — Resolve the production normalization metadata contract

Print:

```text
[STAGE 3/10] Freeze full-corpus normalization contract
```

This stage is important because the Phase 1 1,500-document manifest had
alignment-derived metadata that may not exist for all 91,086 EDGAR-CORPUS
rows.

Re-read:

- Task 1.2 frontmatter contract;
- Task 2.9 frozen canonical metadata/chunk schema;
- the current Task 4.2 expectations.

Create a tracked Task 4.1 config, for example:

```text
configs/phase_4_1_full_corpus_normalization.json
```

Use Task 2.10 `semantic_hash()` / canonical hashing. Do not create a second
hashing convention.

The config should freeze at least:

```text
task
normalizer_version
source_dataset
source_file_set / source identity
expected_source_document_count
section ordering policy
newline policy
empty-section policy
empty-document policy
frontmatter/document metadata fields
document-id policy
output format/layout
build-manifest schema version
```

## Metadata rule

Preserve all authoritative source metadata needed by downstream Task 4.2.

Do not fabricate values that EDGAR-CORPUS does not contain.

In particular, do not invent:

```text
accession/adsh
company name
period_end
filed_date
sic
section metadata
```

from filename patterns or guesses.

If current downstream canonical metadata requires fields that are unavailable
for some/all historical EDGAR-CORPUS rows, use the repository's already-frozen
nullable/missing-value policy.

If there is no such policy and Task 4.2 cannot proceed without a decision,
STOP here and report:

```text
field
source availability
coverage
possible policy choices
recommended non-fabricating policy
```

Do not silently enrich 1993–2020 filings by making an unreliable XBRL join.

---

# Stage 4/10 — Preserve Task 1.2 semantics with regression fixtures

Print:

```text
[STAGE 4/10] Prove normalization compatibility
```

Before the full 91,086-document build, rerun the current normalizer against
a deterministic regression sample from the original Task 1.2 corpus.

At minimum include:

```text
normal document
sparse document
known empty-source document
Unicode/punctuation case
multiline case
CRLF case
documents from multiple years/splits
```

For documents that existed in the original Phase 1 normalized corpus,
the normalized body bytes must remain identical unless a later explicitly
approved normalization revision changed the contract.

Do not let the scaling driver alter textual normalization semantics.

If the Task 4.1 metadata envelope differs because the full-corpus schema has
been expanded, compare the normalized body separately and document the
metadata-only difference.

---

# Stage 5/10 — Implement a resumable full-corpus driver

Print:

```text
[STAGE 5/10] Implement full-corpus normalization driver
```

Reuse the existing normalizer rather than copy/pasting normalization logic.

A reasonable entry point is:

```text
scripts/normalize_full_corpus.py
```

but follow current repository conventions.

The full-corpus driver must support safe restart/resume.

## Why resume is required

91,086 documents is approximately 60.7× the original 1,500-document
normalization run.

The Phase 1 normalized artifact was about 430.7 MB for 1,500 filings, so a
simple linear size extrapolation is roughly **26 GB** for 91,086 filings.
This is only a planning estimate; record the real Task 4.1 size.

Do not build the entire output into RAM.

## Resume/checkpoint contract

Use deterministic checkpointing/sharding.

A defensible design could be:

```text
artifacts/normalized/<full-corpus-config-hash>/
  shards/
    ...
  build_state.json
  manifest...
```

or another layout already supported by the repository.

Requirements:

- checkpoint state must identify the exact Task 4.1 config hash;
- completed units must not be recomputed silently on resume;
- partial writes must be atomic;
- config/source identity mismatch must refuse resume;
- corrupted/incomplete units must be detected, not accepted;
- restart must continue from the first incomplete deterministic unit;
- no source row may be silently skipped after an exception.

Do not create one huge in-memory `list` of all normalized document contents.

---

# Stage 6/10 — Pilot before full build

Print:

```text
[STAGE 6/10] Pilot full-corpus normalization
```

Run a deterministic small pilot across varied source regions, not simply the
first N rows.

Include examples from:

```text
early years
middle years
late years
all source splits
large documents
small/sparse documents
empty-source documents if present
```

Validate:

```text
document ID
metadata
section ordering
newline normalization
empty-section omission
UTF-8 output
output path safety
checkpoint state
resume behavior
```

Measure pilot:

```text
documents/sec
MB/sec
CPU utilization if readily available
peak RSS if readily available
output bytes/document
```

Estimate full runtime and disk usage from the pilot.

If projected full artifact or temporary space threatens available disk, STOP
before the full run.

Do not introduce GPU processing to improve normalization throughput.

---

# Stage 7/10 — Full 91,086-document normalization run

Print:

```text
[STAGE 7/10] Normalize complete EDGAR-CORPUS
```

Run in the foreground with visible progress.

Example progress:

```text
[NORMALIZE]  5,000 / 91,086   5.49%   docs/s=...   written_GB=...   failures=0
[NORMALIZE] 10,000 / 91,086  10.98%   docs/s=...   written_GB=...   failures=0
```

Progress must show at least:

```text
processed
total
percent
elapsed
docs/sec
bytes written
failure count
```

Do not hide a many-hour run in an opaque detached process.

If interrupted, resume from the validated checkpoint.

## Failure policy

For every source row, outcome must be one of:

```text
NORMALIZED
VALID_EMPTY_SOURCE
FAILED
```

No fourth state such as silently skipped.

A failed document must record:

```text
document_id
source split/file
exception class
safe error summary
```

Do not include secrets or giant source text dumps.

The formal Task 4.1 build cannot be called complete with unexplained failed
documents.

If failures are caused by a reproducible normalization bug:

1. stop;
2. fix the deterministic bug;
3. add a regression test;
4. bump/change the Task 4.1 config identity if output semantics changed;
5. resume/rebuild only what the new identity permits.

---

# Stage 8/10 — Full-corpus validation

Print:

```text
[STAGE 8/10] Validate normalized corpus
```

At minimum validate:

## Completeness

```text
source rows = 91,086
unique source document IDs = expected
normalized outcomes = source rows
missing source IDs = 0
extra normalized IDs = 0
duplicate normalized IDs = 0
unexplained failures = 0
```

## Text / formatting

For every normalized document or via deterministic streaming checks where
appropriate:

```text
valid UTF-8
exactly one trailing newline
frontmatter/schema valid
document_id matches source identity
section headings only for non-empty source sections
no invented sections
```

## Source immutability

Re-verify frozen source invariants, including at least:

```text
EDGAR-CORPUS source file count
EDGAR-CORPUS row count
data/xbrl.duckdb size/invariant already used by project
raw XBRL ZIP count
primary filing count
```

Task 4.1 is read-only with respect to `data/`.

## Deterministic sample trace

Select a deterministic sample across years/splits and trace:

```text
source parquet row
   ->
normalized metadata/frontmatter
   ->
normalized body
   ->
manifest entry
```

Manually inspect enough examples to cover:

```text
1990s
2000s
2010s
2020
sparse filing
large filing
empty filing
```

---

# Stage 9/10 — Determinism and build manifest

Print:

```text
[STAGE 9/10] Freeze build identity
```

Create a tracked summary such as:

```text
results/phase_4_1_full_corpus_normalization.json
```

and a git-ignored/full artifact manifest under the normalization artifact
directory if the per-document listing is too large for Git.

The tracked result must contain at least:

```text
task
status
git_sha
source dataset identity
source row count
unique document count
CIK count
year range

normalizer_version
normalization config
phase_4_1_config_hash

output location logical key
output format/layout
normalized document count
valid empty-source count
failed count

total normalized bytes
build elapsed seconds
documents/sec
peak RSS if measured

build_manifest_sha256
determinism verification method
sample trace results

protected TEST status
paid API calls
```

## Build manifest

The build manifest must allow Task 4.2 to prove that it is chunking exactly
this Task 4.1 corpus.

Include deterministic per-output identity such as:

```text
document_id
source split
source identity
relative output path
content hash
status
```

Do not include giant full document text in the manifest.

## Determinism verification

Do not perform an unnecessary second 26 GB full duplicate build merely to
claim determinism.

Use a defensible combination of:

- deterministic config hash;
- deterministic source ordering;
- per-document content hashes;
- manifest hash;
- rerun of a deterministic representative subset;
- idempotent resume/reopen validation.

If a full second run is cheap enough and the implementation naturally
reuses/verifies existing output rather than duplicating it, that is fine.

---

# Stage 10/10 — Tests, documentation, Git, and stop

Print:

```text
[STAGE 10/10] Verify and close Task 4.1
```

## Required tests

Add deterministic tests covering at least:

1. full-corpus config hash determinism;
2. config hash changes when normalization semantics change;
3. source document ID determinism;
4. duplicate source identity rejection;
5. metadata type normalization;
6. unavailable metadata is not fabricated;
7. section ordering preservation;
8. empty-section omission;
9. empty-document handling;
10. CRLF/CR normalization;
11. Unicode preservation;
12. exactly one trailing newline;
13. deterministic output path;
14. path traversal rejection where applicable;
15. checkpoint config mismatch rejection;
16. checkpoint/source mismatch rejection;
17. resume skips only validated completed units;
18. atomic partial-write behavior;
19. corrupt checkpoint/unit rejection;
20. failed source rows cannot disappear silently;
21. manifest includes every source document exactly once;
22. manifest hash determinism;
23. content hash determinism;
24. Task 1.2 regression fixture body compatibility;
25. no chunking occurs;
26. no embedding/model load occurs;
27. no LanceDB index creation occurs;
28. no generation/API call occurs;
29. no protected TEST access occurs;
30. source `data/` is never written.

Portable tests must use tiny synthetic fixtures.

Do not normalize 91,086 filings inside pytest.

## Verification commands

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Report exact counts.

GPU is not a completion requirement for this task.

## Documentation

Create/update as appropriate:

```text
project_plan/PHASE4_FULL_CORPUS_NORMALIZATION.md
project_plan/REPOSITORY_STRUCTURE.md
project_plan/STORAGE.md
Progress.md
```

`Progress.md` must record:

```text
source count
normalized count
empty count
failure count
normalizer version
config hash
build-manifest hash
artifact location
artifact size
elapsed time
throughput
resume/checkpoint behavior
sample validation
tests
Git commit
protected TEST status
next task
```

## Git safety

Before staging:

```powershell
git status
git diff --stat
git add -n <specific files>
```

Run secret and large-file scans.

Never commit:

```text
full normalized corpus
data/
artifacts/
checkpoints
temporary shards
*.duckdb
*.parquet unless explicitly small tracked result artifact
model weights/cache
.env
API keys
large logs
```

Commit only small tracked Task 4.1 deliverables:

```text
source/driver changes
tests
config
small result summary
documentation
Progress.md
```

Use a coherent commit such as:

```text
Scale normalization to full EDGAR corpus
```

Follow actual repository commit conventions.

---

# Formal completion display

At completion print:

```text
PHASE 4 — TASK 4.1 FULL-CORPUS NORMALIZATION
=============================================

Source:
  dataset:                       EDGAR-CORPUS
  source filings:                91,086
  unique document IDs:           ...
  unique CIKs:                   ...
  year range:                    ...

Normalization:
  normalizer version:            ...
  config hash:                   ...
  text semantics changed:        NO
  GPU used:                      NO

Output:
  normalized documents:          ...
  valid empty-source documents:  ...
  unexplained failures:          0
  total size:                    ...
  build manifest hash:           ...
  artifact location:             ...

Build:
  elapsed:                       ...
  throughput docs/sec:           ...
  peak RSS:                      ...
  resume/checkpoint validated:   YES

Validation:
  missing document IDs:          0
  extra document IDs:            0
  duplicate document IDs:        0
  Task 1.2 regression sample:    PASS
  deterministic manifest:        PASS
  frozen data unchanged:         PASS

Protected TEST:
  opened:                        NO
  official runs used:            0/3

Paid API calls:
  0

Tests:
  doctor:                        ...
  portable:                      ...
  full:                          ...

Git:
  branch:                        ...
  commit:                        ...
  working tree:                  ...

TASK 4.1 STATUS:
  COMPLETE

PHASE 4 STATUS:
  IN PROGRESS

NEXT ROADMAP TASK:
  4.2 Full-corpus chunking

STOP.
Do not start Task 4.2.
```

---

# Hard stop conditions

STOP and report rather than guessing if:

1. Phase 3 exit audit is not actually passed.
2. Task 4.1 is not the current next roadmap task.
3. source corpus no longer reproduces 91,086 rows.
4. source document IDs are not unique.
5. the selected normalizer contract is ambiguous.
6. a later repository decision changed normalization semantics and is not
   reflected consistently in docs/code/config.
7. Task 2.9 frozen metadata requirements conflict with what full EDGAR-CORPUS
   can actually provide and no nullable/missing-value policy exists.
8. accession/company/SIC/date metadata would need to be fabricated.
9. the implementation would mutate frozen `data/`.
10. the implementation would silently drop empty or failed filings.
11. a source row fails and no explicit failure record is created.
12. resume/checkpoint identity does not match the current config/source.
13. checkpoint state appears corrupt.
14. expected artifact size threatens available disk.
15. output semantics change after the formal build has started without a new
    config identity.
16. chunking is proposed in Task 4.1.
17. embeddings/model inference are proposed in Task 4.1.
18. GPU use is proposed as a requirement for Task 4.1.
19. indexing/FTS is proposed in Task 4.1.
20. an LLM/API call is proposed.
21. protected TEST would be opened.
22. an official TEST run would be consumed.
23. large generated normalization artifacts are about to be committed.
24. secrets are about to be committed.
25. doctor/portable/full regression gates fail.
26. prior Phase 3 frozen results are modified unexpectedly.

---

# Success criteria

Task 4.1 is complete only when:

- the complete 91,086-filing EDGAR-CORPUS has a deterministic normalization
  outcome;
- every source document is represented exactly once in the build manifest;
- no document is silently dropped;
- the selected normalization semantics remain unchanged;
- deterministic source IDs are preserved;
- the current frozen metadata contract is respected without fabrication;
- a Task 4.1 config hash is recorded;
- a deterministic build-manifest hash is recorded;
- the output is resumable/recoverable;
- full-corpus counts and artifact size are measured;
- Task 1.2 compatibility is regression-tested;
- frozen `data/` remains unchanged;
- protected TEST remains unopened at 0/3;
- no paid API calls occur;
- doctor, portable tests, and full tests pass;
- Task 4.1 is documented and committed;
- Task 4.2 has not started.
