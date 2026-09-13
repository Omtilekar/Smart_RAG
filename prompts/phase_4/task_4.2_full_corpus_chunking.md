# Phase 4 — Task 4.2: Full-Corpus Chunking

## Objective

Apply the **already-selected Phase 3 chunking strategy** to the complete
Task 4.1 normalized EDGAR-CORPUS and produce a deterministic, versioned,
resumable, sharded Parquet chunk corpus suitable for Task 4.3 full-corpus
embedding.

This is a scale-out task, **not a new chunking experiment**.

Do not re-open the Phase 3 chunking decision. Do not optimize quality. Do not
benchmark alternate window sizes. Do not embed. Do not build an index. Do not
run protected TEST.

The task ends after the complete production chunk corpus is built, validated,
documented, and committed. **STOP before Task 4.3.**

---

# Authoritative repository order

Before changing anything, re-read the live repository in this order:

1. `project_plan/PROJECT_EXECUTION.md`
2. `Progress.md`
3. `project_plan/GIT_CONVENTIONS.md`
4. `project_plan/PHASE4_FULL_CORPUS_NORMALIZATION.md`
5. `project_plan/PHASE3_CHUNKING_ABLATION.md`
6. `project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md`
7. `project_plan/PHASE2_ARTIFACT_VERSIONING.md` or the current Task 2.10
   artifact-versioning documentation
8. `project_plan/STORAGE.md`
9. `project_plan/PHASE1_CHUNKING.md`
10. live implementations:
    - `src/chunk/fixed_window.py`
    - `src/chunk/metadata_schema.py`
    - `src/artifacts/versioning.py`
    - `src/storage.py`
11. live configs/results for:
    - Task 3.2 selected chunking winner
    - Task 4.1 full-corpus normalization

Repository truth wins over stale prose in this prompt.

If the live repository materially contradicts any frozen identity below,
STOP and report the discrepancy rather than silently rebuilding under a
different contract.

---

# Verified entry state

Task 4.1 is COMPLETE.

The latest Task 4.1 result is:

```text
source rows:                    91,086
normalized non-empty bodies:    90,239
valid empty-source documents:      847
unexplained failures:                0

normalizer_version:
  phase1-minimal-v1

phase_4_1_config_hash:
  754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f

build_manifest_sha256:
  3ca76cfd6e789811012c60adb7ba7aa9c8c3d002547fbc5310da47481342f3f9

artifact:
  artifacts/normalized_full/
  754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f/

artifact size:
  13,175,754,341 bytes (~12.27 GiB)

Task 4.1 company policy:
  nullable company
  when multiple historical names exist for a CIK, use the approved
  Task 4.1 most-recently-filed-name tie-break

Task 4.1 resume state:
  append-only build_state.jsonl
  config/source-identity bound
  completed content hashes revalidated on resume
  atomic per-document writes
```

Task 4.1's complete build was verified to have:

```text
missing source documents: 0
extra source documents:   0
duplicate identities:     0
unexplained failures:     0
```

Do not bypass its build manifest by blindly globbing a directory and assuming
every file belongs to the current build.

---

# Frozen Phase 3 chunking decision

Task 3.2 selected:

```text
split mode:             fixed
window size:            256 content tokens
overlap:                0 tokens
stride:                 256 tokens
section-aware:          NO
partial final window:   KEEP
frontmatter:            metadata only; chunk body text, not YAML frontmatter
special-token counting: use the frozen Task 3.2 convention
text extraction:        use the frozen Task 3.2 offset-mapping convention

chunk_config_hash:
  ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
```

This winner was selected after the controlled 256/512/1024, overlap, and
section-aware ablation. It must not be changed in Task 4.2.

## Critical tokenizer rule

Task 3.2's chunk boundaries were created using the tokenizer/config frozen
by Task 3.2. Task 3.3 later selected `Qwen/Qwen3-Embedding-0.6B` as the
embedding winner.

**Do not switch the chunking tokenizer to Qwen merely because Qwen is the
Task 4.3 embedding model.**

Read the checked-in Task 3.2 winner config and use exactly its tokenizer
repository, revision, special-token policy, offset policy, and window
semantics.

Before the full build, independently recompute the Task 3.2 semantic chunk
config hash using Task 2.10's canonical hashing implementation and require:

```text
recomputed chunk_config_hash
==
ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
```

If it does not match, STOP.

Do not create a new chunk semantic hash just because this build has a
different corpus size or Parquet shard layout. Sharding/build provenance is
separate from chunk semantics.

---

# Frozen canonical chunk schema

Task 2.9 froze one canonical 23-field schema in:

```text
src/chunk/metadata_schema.py
```

The canonical fields are:

```text
chunk_schema_version
chunk_uid
chunk_local_id
document_id
accession
cik
company
form_type
fiscal_year
period_end
filed_date
sic
section_id
section_title
ordinal
char_start
char_end
content_type
table_id
source
text
token_count
chunk_config_hash
```

Use the live `CANONICAL_FIELDS`/canonical PyArrow schema as the executable
source of truth. Do not maintain a second hand-written schema in the build
script.

For EDGAR-CORPUS, Task 2.9 already froze the non-fabrication policy:

```text
accession:    NULL
period_end:   NULL
filed_date:   NULL
sic:          NULL
source:       edgar_corpus
content_type: prose
table_id:     NULL
```

`company` may be NULL under the Task 4.1 approved policy.

Do not fabricate unavailable fields.

## IDs

Use Task 2.9's existing helpers:

```text
build_chunk_local_id(...)
build_chunk_uid(...)
```

Do not revert to the old Phase 1 string-only identity
`"{document_id}::chunk{ordinal}"` as the canonical production ID.

Task 2.9 defined `chunk_uid` as SHA-256 over the canonical identity-bearing
ingredients:

```text
chunk_schema_version
source
document_id
chunk_config_hash
chunk_local_id
```

Reuse that code unchanged unless the repository already contains a later
approved revision.

---

# Offset and section metadata policy

The production chunk text must use the exact Task 3.2 fixed-window boundary
semantics.

`char_start` / `char_end` should be populated only when they can be defended
as the exact zero-based, half-open `[start, end)` span in the normalized
**body text that was actually tokenized**.

For any populated offset, require the round-trip invariant:

```python
normalized_body[char_start:char_end] == chunk_text
```

Never estimate offsets.

Task 3.2 selected **fixed, non-section-aware splitting**. Do not alter chunk
boundaries to make section metadata easier.

For `section_id` / `section_title`:

- if existing repository utilities can assign them unambiguously without
  changing chunk boundaries, use the frozen canonical semantics;
- if a fixed chunk crosses sections, both must be NULL;
- if there is no existing unambiguous mapping utility for this production
  path, leave both NULL and document that honestly;
- do **not** add a new section-aware splitter or change the selected split
  mode in Task 4.2.

---

# Separate semantic identity from build identity

There are two different identities in this task.

## Semantic chunk identity

Must remain the frozen Task 3.2 hash:

```text
chunk_config_hash =
ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
```

## Task 4.2 build identity

Create a tracked config such as:

```text
configs/phase_4_2_full_corpus_chunking.json
```

and compute a separate:

```text
phase_4_2_build_config_hash
```

using the repository's Task 2.10 canonical semantic hashing utility.

The Task 4.2 build identity should bind at least:

```text
task
input phase_4_1_config_hash
input build_manifest_sha256
normalizer_version
chunk_schema_version
selected chunk_config_hash
tokenizer repository
tokenizer revision
output format
shard policy
manifest schema version
```

Do not include non-semantic run noise such as timestamp, machine name, or
current free disk in the semantic build hash unless repository conventions
explicitly require it.

---

# Do not collide with Phase 1/3 chunk artifacts

The repository already contains development/ablation chunk artifacts keyed by
the same Task 3.2 `chunk_config_hash`.

Do **not** write the 91,086-filing corpus into a path that can overwrite or
be mistaken for the existing 1,500-filing / Phase 3 development chunk
artifact.

Use an additive full-corpus namespace keyed by BOTH:

```text
Task 4.1 input/build identity
Task 3.2 chunk semantic identity
```

For example, if no existing production convention already exists:

```text
artifacts/chunks_full/
  <phase_4_1_config_hash>/
    <chunk_config_hash>/
      ...
```

or add an equivalent narrowly-scoped `src.storage` helper.

The exact path may follow a stronger existing repository convention, but it
must satisfy:

```text
full-corpus artifact cannot collide with dev artifact
input normalization identity is recoverable from the path/manifest
chunk semantic identity is recoverable from the path/manifest
```

Do not move, delete, or rewrite any existing development chunk artifact.

---

# Overnight execution requirement

The user intends to leave the laptop running overnight.

Design the build so it can run unattended after the preflight/pilot succeeds.

The long run must:

- require no interactive prompts after launch;
- stream visible progress;
- show ETA;
- checkpoint safely;
- resume after interruption;
- never restart completed shards unnecessarily;
- never silently skip a document;
- never keep the entire corpus or all chunks in RAM;
- never require GPU;
- never require network/API access.

Do not use loop engineering or automatically start Task 4.3.

---

# Stage 1/11 — Preflight

Print:

```text
[STAGE 1/11] Task 4.2 preflight
```

Run and record:

```powershell
git status
git branch --show-current
git log -5 --oneline --decorate

python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Verify:

1. Task 4.1 is COMPLETE.
2. Task 4.2 is the current next roadmap task.
3. working tree has no unexplained tracked modifications;
4. Task 4.1 artifact exists;
5. Task 4.1 manifest hash recomputes to the recorded value;
6. Task 4.1 document count = 91,086;
7. Task 4.1 valid empty count = 847;
8. Task 4.1 failures = 0;
9. Task 3.2 selected chunk config recomputes to the exact frozen hash;
10. Task 2.9 canonical schema module imports cleanly;
11. selected tokenizer files are locally available;
12. protected TEST remains unopened, official TEST usage 0/3;
13. no API credential is needed;
14. sufficient disk is available for:
    - complete sharded output,
    - checkpoint/manifest state,
    - at least one temporary shard,
    - validation overhead.

Do not begin the full run if projected disk usage would leave an unsafe
margin.

Record actual free disk before starting.

---

# Stage 2/11 — Bind to the exact Task 4.1 build

Print:

```text
[STAGE 2/11] Validate Task 4.1 input identity
```

Read the Task 4.1 build manifest as the authoritative document inventory.

Require exactly:

```text
91,086 manifest document outcomes
90,239 non-empty normalized documents
847 valid empty-source documents
0 unexplained failures
```

For every non-empty document:

- relative artifact path exists;
- document_id matches manifest;
- content hash matches manifest;
- no duplicate document_id;
- path cannot escape the Task 4.1 artifact root.

For every valid empty-source document:

- preserve the document in the Task 4.2 per-document manifest;
- expected chunk count = 0;
- do not manufacture a placeholder chunk.

Do not scan raw EDGAR Parquet to reconstruct Task 4.1 outputs unless needed
for an explicit validation check. Task 4.2 consumes the frozen Task 4.1
normalized build.

---

# Stage 3/11 — Reproduce the Phase 3 winner exactly

Print:

```text
[STAGE 3/11] Reproduce frozen chunk semantics
```

Load the exact selected Task 3.2 candidate config.

Validate:

```text
window_size_tokens = 256
overlap_tokens     = 0
stride_tokens      = 256
split_mode         = fixed
partial final      = kept
body only          = true
```

Validate tokenizer identity and offline availability.

Use the existing fast-tokenizer / offset-mapping implementation.

No network download should be needed. Prefer the repository's established
offline/cache-precheck behavior.

If the exact frozen tokenizer revision is missing locally, STOP rather than
silently downloading a newer revision during the formal production build.

Recompute:

```text
chunk_config_hash =
ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
```

Then run a deterministic regression sample from the Task 3.2 development
corpus and prove that the same normalized inputs generate the same chunk
boundaries/text/ordinals as the frozen Task 3.2 artifact.

Do not start the full corpus until that regression passes.

---

# Stage 4/11 — Implement production sharding + resume

Print:

```text
[STAGE 4/11] Implement resumable sharded Parquet build
```

Reuse `src/chunk/fixed_window.py` for chunk semantics. Do not copy/paste the
token-window logic into a Phase 4 script.

A reasonable orchestration entry point is:

```text
scripts/chunk_full_corpus.py
```

but follow the repository's current naming conventions.

## Output format

Write versioned **Parquet shards**, not one giant file.

Unless a stronger existing production convention already exists, use:

```text
target ~200,000 chunk rows per shard
```

with shard boundaries only **between documents**, never splitting one
document's chunk sequence across shards just to hit the target exactly.

Example:

```text
artifacts/chunks_full/<phase4.1-hash>/<chunk-hash>/
  shards/
    part-00000.parquet
    part-00001.parquet
    ...
  build_state.jsonl
  document_manifest.parquet
  shard_manifest.json
```

The exact filenames may follow repository conventions.

Why this matters:

- makes overnight resume cheap;
- keeps memory bounded;
- prepares Task 4.3 for local or Colab embedding;
- avoids one monolithic multi-GB Parquet file;
- allows independent per-shard hashing and validation.

## Compression

Use the repository's existing Parquet compression convention if one exists.
If none exists, choose a normal deterministic analytics default supported by
the pinned PyArrow version and record it in the Task 4.2 config.

Compression choice is a storage/build parameter, not a reason to change
`chunk_config_hash`.

## Atomic shard publication

For each shard:

1. write to a temporary path under the same filesystem;
2. close/fsync as appropriate;
3. validate row count/schema/basic invariants;
4. compute SHA-256;
5. atomically rename/replace to the final shard path;
6. append a completed checkpoint record only after publication succeeds.

A partially-written shard must never look COMPLETE after a crash.

---

# Stage 5/11 — Checkpoint contract

Print:

```text
[STAGE 5/11] Validate restart/resume behavior
```

Bind checkpoint state to:

```text
phase_4_1_config_hash
Task 4.1 build_manifest_sha256
phase_4_2_build_config_hash
chunk_schema_version
chunk_config_hash
```

A mismatch in any identity must reject resume.

Checkpoint state must be sufficient to answer:

```text
which Task 4.1 documents are complete
which shard each completed document belongs to
how many chunks each document emitted
which shards are finalized
per-shard row count
per-shard SHA-256
```

On resume:

- verify finalized shard hashes before trusting them;
- skip only validated completed work;
- restart the first incomplete/corrupt shard from its deterministic document
  start;
- never append duplicate chunks;
- never silently accept a stale checkpoint.

Create a simulated interruption test on a small synthetic/pilot input before
trusting this on the full corpus.

---

# Stage 6/11 — Pilot and resource estimate

Print:

```text
[STAGE 6/11] Pilot chunking and estimate overnight run
```

Use a deterministic stratified pilot that includes:

- early / middle / late years;
- all source splits;
- largest normalized documents;
- small documents;
- at least several of the 847 empty-source documents;
- documents with Unicode/punctuation;
- documents with many Item headings.

Measure:

```text
documents/sec
MiB input/sec
chunks/sec
tokens/sec
output bytes/chunk
peak RSS
```

Estimate:

```text
full chunk count
full Parquet size
full elapsed time
temporary-space peak
```

This estimate is advisory only; do not assert an expected final chunk count
as a correctness condition.

The real full-corpus count is an output of Task 4.2.

If the projected build cannot safely fit available disk, STOP before the
full run and report the measured estimate.

## Pilot correctness

For pilot documents prove:

```text
all content-token windows are <= 256 tokens
zero token overlap
partial final window kept
ordinals start at 0 and are contiguous
chunk_local_id deterministic
chunk_uid deterministic
char offsets round-trip when populated
metadata conforms to Task 2.9 schema
empty source -> 0 chunks
```

---

# Stage 7/11 — Full overnight build

Print:

```text
[STAGE 7/11] Build complete production chunk corpus
```

Run in the foreground with progress visible.

At least every ~60 seconds or each meaningful batch, print:

```text
[CHUNK]
documents:      12,500 / 91,086  (13.72%)
nonempty docs:  ...
empty docs:     ...
chunks:         ...
shards:         ...
input GiB:      ...
output GiB:     ...
docs/sec:       ...
chunks/sec:     ...
elapsed:        ...
ETA:            ...
failures:       0
```

No interactive prompt after formal launch.

## Failure policy

Each Task 4.1 document must end in exactly one production state:

```text
CHUNKED
VALID_EMPTY_SOURCE
FAILED
```

No silent skip.

A failed record must include:

```text
document_id
input relative path
exception class
safe error summary
checkpoint position
```

The formal Task 4.2 run is not COMPLETE while unexplained FAILED documents
remain.

If a deterministic code bug is discovered:

1. stop the build;
2. preserve evidence;
3. fix the bug;
4. add a regression test;
5. decide whether the Task 4.2 build identity must change;
6. never mix shards produced under incompatible semantics.

---

# Stage 8/11 — Full-corpus validation

Print:

```text
[STAGE 8/11] Validate full chunk corpus
```

Validate globally:

```text
Task 4.1 source documents:        91,086
documents accounted for:          91,086
expected valid-empty documents:      847
valid-empty documents in 4.2:        847
unexpected zero-chunk docs:             0
failed documents:                       0

chunk_uid duplicates:                   0
(document_id, chunk_local_id)
duplicates:                              0

wrong chunk_config_hash rows:           0
wrong schema version rows:              0
wrong source rows:                      0
token_count > 256:                      0
token_count <= 0:                       0
non-contiguous ordinals:                0
```

Also verify:

- every non-empty Task 4.1 document appears in the document manifest with
  positive chunk_count;
- every valid-empty Task 4.1 document appears with chunk_count=0;
- every chunk document_id resolves to exactly one Task 4.1 manifest entry;
- no extra document_id exists;
- every shard schema is byte/logically identical;
- every shard hash matches its manifest;
- sum(shard row_count) equals global chunk_count;
- sum(document chunk_count) equals global chunk_count.

## Token coverage

For a deterministic representative sample, verify the exact Task 3.2
zero-overlap coverage behavior from first token through the final partial
window.

Do not claim character-contiguous reconstruction where tokenizer offset
behavior intentionally omits pure inter-token whitespace; use the same
correctness definition Task 1.3/3.2 already established.

---

# Stage 9/11 — Sample quality inspection

Print:

```text
[STAGE 9/11] Sample-check production chunk quality
```

Inspect a deterministic sample spanning:

```text
1990s
2000s
2010s
2020
all source splits
largest documents
small documents
nullable-company documents
documents with company populated
documents around Item-heading boundaries
empty documents
```

For each inspected non-empty document trace:

```text
Task 4.1 manifest entry
  ->
normalized file/body
  ->
selected chunk rows
  ->
chunk_local_id / chunk_uid
  ->
char offsets (when populated)
  ->
Task 4.2 document manifest
  ->
shard manifest
```

Record sample IDs and results in the Task 4.2 summary so the validation is
reproducible.

---

# Stage 10/11 — Freeze manifests + Task 4.3 handoff

Print:

```text
[STAGE 10/11] Freeze Task 4.2 build identity
```

Create a tracked small result:

```text
results/phase_4_2_full_corpus_chunking.json
```

and appropriate git-ignored full manifests under the artifact directory.

The tracked result must contain at least:

```text
task
status
git_sha

input:
  phase_4_1_config_hash
  phase_4_1_build_manifest_sha256
  normalizer_version
  source_document_count
  normalized_nonempty_count
  valid_empty_source_count

chunking:
  chunk_schema_version
  chunk_config_hash
  split_mode
  window_size_tokens
  overlap_tokens
  stride_tokens
  tokenizer_repository
  tokenizer_revision

build:
  phase_4_2_build_config_hash
  artifact_root
  shard_count
  target_rows_per_shard
  parquet_compression
  document_manifest_sha256
  shard_manifest_sha256
  total_chunk_count
  documents_with_chunks
  documents_without_chunks
  failed_document_count
  total_output_bytes
  elapsed_seconds
  documents_per_second
  chunks_per_second
  peak_rss_bytes

validation:
  duplicate_chunk_uid_count
  missing_document_count
  extra_document_count
  unexpected_zero_chunk_document_count
  token_count_violation_count
  schema_violation_count
  shard_hash_mismatch_count
  sample_check_count
  sample_check_failures

protected_test:
  opened
  official_runs_used

paid_api_calls
gpu_used
```

## Task 4.3 handoff manifest

Task 4.3 may run on this laptop or on Colab/H100 later.

Therefore the Task 4.2 shard manifest must make each shard independently
verifiable and transferable.

For every shard include at least:

```text
shard_id
relative_path
row_count
sha256
first_document_id
last_document_id
chunk_config_hash
chunk_schema_version
```

If cheap and useful, also include min/max `chunk_uid` or another deterministic
diagnostic, but do not depend on lexical ordering of SHA-256 IDs as semantic
meaning.

Task 4.3 must be able to take one shard, verify its hash and schema, embed it,
and checkpoint independently.

---

# Stage 11/11 — Regression tests, docs, Git, stop

Print:

```text
[STAGE 11/11] Close Task 4.2
```

## Required tests

Add deterministic tests covering at least:

1. exact Task 3.2 config hash reproduction;
2. 256-token window and zero-overlap semantics;
3. final partial window kept;
4. frontmatter excluded from chunk body;
5. tokenizer revision identity is frozen;
6. canonical 23-field schema used from Task 2.9;
7. Task 2.9 `chunk_local_id` reuse;
8. Task 2.9 `chunk_uid` reuse;
9. nullable company accepted;
10. unavailable accession/date/SIC not fabricated;
11. char offsets half-open and exact when populated;
12. crossed/ambiguous section metadata does not get fabricated;
13. empty Task 4.1 document emits zero chunks;
14. non-empty document emits positive chunks;
15. deterministic shard assignment/order;
16. one document is never split across shard files;
17. atomic shard publication;
18. checkpoint identity mismatch rejection;
19. stale Task 4.1 manifest mismatch rejection;
20. corrupted shard hash rejection on resume;
21. simulated interruption + resume without duplicate chunks;
22. document manifest completeness;
23. shard-manifest hash determinism;
24. no duplicate chunk_uid;
25. Task 3.2 regression sample reproduces frozen boundaries/text;
26. production output namespace cannot collide with dev chunk artifact;
27. no embedding model loaded;
28. no vector generated;
29. no LanceDB index built;
30. no generation/API call;
31. no protected TEST access;
32. source `data/` not written;
33. Task 4.1 normalized artifact not rewritten.

Portable tests use tiny synthetic fixtures. Do not chunk all 91,086
documents inside pytest.

## Final commands

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Report exact counts.

GPU availability is **not** a Task 4.2 completion requirement.

## Documentation

Create/update as appropriate:

```text
project_plan/PHASE4_FULL_CORPUS_CHUNKING.md
project_plan/REPOSITORY_STRUCTURE.md
project_plan/STORAGE.md
Progress.md
```

`Progress.md` must record the real Task 4.2 values, including:

```text
input Task 4.1 identities
frozen chunk_config_hash
chunk schema version
total chunk count
documents with chunks
zero-chunk documents
shard count
artifact size
manifest hashes
elapsed time
throughput
peak RSS
resume behavior
sample checks
test counts
protected TEST status
Git commit
next task
```

## Git

Follow `project_plan/GIT_CONVENTIONS.md`.

Before staging:

```powershell
git status
git diff --stat
git add -n <specific tracked files>
```

Never commit:

```text
full chunk Parquet shards
full document manifest if large
checkpoint journals
artifacts/
data/
normalized full corpus
model/tokenizer cache
.env
logs
temporary shard files
```

Commit only the small tracked implementation/config/result/tests/docs.

Use the repository's normal task branch/commit discipline. A coherent commit
message is:

```text
Scale chunking to full EDGAR corpus
```

Do not fabricate history.

---

# Formal completion display

At the end print:

```text
PHASE 4 — TASK 4.2 FULL-CORPUS CHUNKING
========================================

Input:
  Task 4.1 config hash:          754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f
  Task 4.1 manifest hash:        3ca76cfd6e789811012c60adb7ba7aa9c8c3d002547fbc5310da47481342f3f9
  source documents:              91,086
  non-empty documents:           90,239
  valid empty documents:            847

Chunk semantics:
  split mode:                    fixed
  window:                        256
  overlap:                       0
  chunk_config_hash:             ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
  chunk schema version:          ...
  tokenizer:                     ...
  tokenizer revision:            ...
  GPU used:                      NO

Output:
  total chunks:                  ...
  documents with chunks:         ...
  zero-chunk documents:          847
  unexpected zero-chunk docs:    0
  shard count:                   ...
  output size:                   ...
  document manifest SHA-256:     ...
  shard manifest SHA-256:        ...
  Task 4.2 build config hash:     ...

Validation:
  missing documents:             0
  extra documents:               0
  failed documents:              0
  duplicate chunk_uid:           0
  token-count violations:        0
  shard hash mismatches:         0
  Task 3.2 regression:           PASS
  sample quality checks:         PASS
  resume simulation:             PASS

Performance:
  elapsed:                       ...
  docs/sec:                      ...
  chunks/sec:                    ...
  peak RSS:                      ...

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

TASK 4.2 STATUS:
  COMPLETE

PHASE 4 STATUS:
  IN PROGRESS

NEXT ROADMAP TASK:
  4.3 Full-corpus embedding

STOP.
Do not start Task 4.3.
```

---

# Hard stop conditions

STOP rather than guessing if:

1. Task 4.1 is not actually complete.
2. Task 4.1 manifest does not recompute to
   `3ca76cfd6e789811012c60adb7ba7aa9c8c3d002547fbc5310da47481342f3f9`.
3. Task 4.1 config identity differs from the recorded hash.
4. Task 4.1 no longer contains exactly 91,086 accounted documents.
5. Task 4.1 no longer has exactly 847 valid empty-source documents.
6. Task 3.2 winner cannot be reproduced exactly.
7. selected semantic `chunk_config_hash` differs from
   `ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06`.
8. the exact Task 3.2 tokenizer revision is unavailable and the only proposed
   workaround is silently using another revision.
9. a proposal changes tokenizer merely because Task 4.3 will use Qwen.
10. a proposal changes 256/0/fixed semantics.
11. production output would overwrite/collide with dev/Phase 3 chunks.
12. frozen Task 2.9 schema is contradicted by implementation and no
    documented evolution exists.
13. unavailable EDGAR metadata would be fabricated.
14. company NULLs are treated as errors despite Task 4.1's approved policy.
15. valid-empty Task 4.1 documents would be dropped instead of represented
    with chunk_count=0 in the document manifest.
16. any non-empty document silently produces zero chunks.
17. checkpoint/source/build identity does not match.
18. finalized shard hash fails.
19. resume would append duplicate chunks.
20. full build would load all chunks into RAM.
21. available disk is unsafe for projected output + temp overhead.
22. GPU/model inference is proposed as required.
23. embeddings are created.
24. LanceDB/vector/FTS index is created.
25. generation/LLM/API is called.
26. protected TEST would be opened.
27. an official TEST run would be consumed.
28. frozen `data/` would be mutated.
29. Task 4.1 normalized artifact would be rewritten.
30. large generated artifacts are about to be committed.
31. regression tests fail.
32. unexplained tracked working-tree changes exist.

---

# Success criteria

Task 4.2 is complete only when:

- all 91,086 Task 4.1 documents are accounted for;
- all 90,239 non-empty normalized documents produce chunks;
- all 847 valid empty-source documents are represented with chunk_count=0;
- there are zero unexplained failures;
- the exact Phase 3 winner (256/0/fixed) is used;
- the exact frozen Task 3.2 tokenizer semantics are used;
- `chunk_config_hash` remains exactly
  `ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06`;
- Task 2.9 canonical schema and deterministic chunk IDs are used;
- production chunks cannot collide with development artifacts;
- Parquet output is sharded and independently hash-verifiable;
- the build is resumable without duplicating completed chunks;
- global/document/shard counts reconcile exactly;
- sample quality checks pass;
- Task 3.2 regression sample reproduces exactly;
- no embedding, index, generation, API, or TEST work occurs;
- doctor, portable tests, and full tests pass;
- Task 4.2 is documented and committed;
- Task 4.3 has **not** started.
