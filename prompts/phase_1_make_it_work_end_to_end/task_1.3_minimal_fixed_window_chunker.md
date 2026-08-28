# Task 1.3 — Minimal Fixed-Window Chunker

You are working inside my SEC RAG repository.

Task file:

`task_1.3_minimal_fixed_window_chunker.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.3 — Minimal Fixed-Window Chunker
```

Current intended status:

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE, CORRECTION MUST BE VERIFIED
  1.3 Minimal Fixed-Window Chunker — CURRENT
```

Task 1.1 froze the 1,500-filing development corpus.

Task 1.2 normalized those 1,500 filings.

The normalizer-version correction is explicitly approved:

```text
normalizer_version = "phase1-minimal-v1"
```

The corrected artifact location must be:

```text
artifacts/normalized/phase1-minimal-v1/
```

Do NOT use the previously implemented generic `v1` location.

---

# HARD PRECONDITION — VERIFY TASK 1.2 CORRECTION

Before implementing any Task 1.3 code, inspect:

```text
configs/normalize_development_corpus.json
results/phase_1_2_normalization_summary.json
project_plan/PHASE1_NORMALIZATION.md
Progress.md
artifacts/normalized/
git log --oneline --decorate -5
git status --short
```

Required corrected state:

```text
normalizer_version = "phase1-minimal-v1"
artifacts/normalized/phase1-minimal-v1/
```

Verify any Task 1.2 config, summary, documentation, and provenance that
previously said `v1` now says `phase1-minimal-v1`.

Do not assume the old normalization checksum remains valid. Verify the
corrected normalization build using Task 1.2's documented checksum
procedure.

If the repository still uses `v1`, STOP and report:

```text
BLOCKED — Task 1.2 normalizer-version correction has not been applied
```

Do NOT repair Task 1.2 inside Task 1.3.

Task 1.2 must be corrected, committed, and the working tree must be clean
before chunking begins.

---

# CRITICAL RULE — DO NOT ASSUME

If an implementation decision is not clearly resolved by the repository,
current project documentation, or direct inspection of the corrected
artifacts, STOP AND ASK ME.

Do not choose a common default merely because it seems reasonable.

Do not infer semantics from a library default.

Do not copy Task 0.10 serving-spike behavior unless Phase 1 documentation
explicitly requires it.

When asking:

1. state exactly what is ambiguous,
2. state what evidence you found,
3. give the smallest useful set of options,
4. explain what output changes depending on the decision,
5. wait for my answer.

Likely ambiguity points include:

```text
tokenizer identity
tokenizer revision
special-token semantics
overlap / stride
final partial-window handling
whether YAML frontmatter is chunk text or metadata-only
whether Markdown Item headings are treated specially
persisted Parquet schema
chunk_id format
Parquet file/dataset layout
handling of the 7 frontmatter-only empty-source documents
artifact overwrite/rebuild behavior
```

Inspection first. Assumption never.

---

# PURPOSE

Task 1.3 creates the first deliberately simple Phase 1 chunk representation:

```text
Task 1.1 frozen manifest
        ↓
Task 1.2 corrected normalized Markdown
        ↓
Task 1.3 deterministic 512-token fixed windows
        ↓
Parquet chunk artifact
        ↓
Task 1.4 baseline embedding pipeline
```

This is a crude baseline.

Do NOT optimize retrieval quality here.

Do NOT implement section-aware chunking.

Do NOT perform chunk-size ablations.

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. verify the corrected Task 1.2 input,
2. read the exact Task 1.3 requirements in `PROJECT_EXECUTION.md`,
3. resolve all undefined chunking semantics before implementation,
4. implement deterministic fixed-window chunking,
5. create 512-token windows,
6. preserve approved document metadata,
7. generate deterministic chunk IDs,
8. compute a deterministic `chunk_config_hash`,
9. persist chunks as Parquet via the storage abstraction,
10. validate the complete real chunk corpus,
11. record chunk statistics,
12. verify deterministic rebuilds,
13. add focused tests,
14. document the chunking contract,
15. update `Progress.md`,
16. commit Task 1.3 as one coherent commit.

Do NOT begin Task 1.4.

---

# 1 — VERIFY GIT AND FOUNDATION

Run:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -5
git tag --list

python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Required:

```text
Task 1.1 committed
corrected Task 1.2 committed
no unexplained working-tree changes
0 portable-test failures
```

If not, STOP AND ASK ME.

---

# 2 — READ CURRENT AUTHORITATIVE MATERIAL

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_DEVELOPMENT_CORPUS.md
project_plan/PHASE1_NORMALIZATION.md
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
src/chunk/
src/normalize/edgar_markdown.py
scripts/normalize_development_corpus.py
configs/normalize_development_corpus.json
results/phase_1_2_normalization_summary.json
artifacts/normalized/phase1-minimal-v1/
```

Actual repository behavior wins over old prompt examples.

---

# 3 — VERIFY INPUT PROVENANCE

Verify:

```text
normalized document count = 1,500
normalizer_version = phase1-minimal-v1
```

Read and validate the current:

```text
development_manifest_sha256
normalization_build_sha256
```

Do not hardcode the old pre-correction normalization checksum from historical
Progress text.

Confirm all 1,500 normalized document identities are unique.

---

# 4 — VERIFY THE 7 EMPTY-SOURCE DOCUMENTS

Task 1.2 established that 7 selected filings have valid frontmatter but no
source body because every EDGAR `section_*` value was empty.

Verify this condition from the current corrected Task 1.2 artifacts.

Do not invent text.
Do not substitute filings.
Do not create placeholder sentences.

If current project documentation does not explicitly define how these 7
documents behave in chunking:

**STOP AND ASK ME.**

Do not assume zero chunks without approval.

Record their final approved handling in Task 1.3 documentation and results.

---

# 5 — FREEZE TOKENIZER SEMANTICS BEFORE IMPLEMENTATION

A token-defined chunker requires an explicit tokenizer contract.

Search the repo for the exact Phase 1 tokenizer rule.

The later baseline embedding model is expected to be
`BAAI/bge-small-en-v1.5`, but do not assume that its tokenizer defines
Task 1.3 boundaries unless the current plan says so.

If tokenizer identity is not explicitly frozen:

**STOP AND ASK ME.**

The resolved contract must include:

```text
tokenizer repository/model
revision if relevant
offline/local-only loading policy
special-token behavior
```

Do not silently switch tokenizers.

Do not silently download tokenizer/model assets.

If required cached tokenizer assets are missing, STOP AND ASK ME.

---

# 6 — WINDOW SIZE

Verify directly from `PROJECT_EXECUTION.md`:

```text
window_size_tokens = 512
```

Do not change it.

Do not run 256/1024 experiments.

---

# 7 — RESOLVE OVERLAP / STRIDE

Search for a frozen overlap/stride rule.

Do not assume:

```text
0 overlap
stride=512
50-token overlap
10% overlap
```

If no rule exists:

**STOP AND ASK ME.**

The approved value must be part of the chunk configuration and
`chunk_config_hash`.

---

# 8 — RESOLVE FINAL PARTIAL WINDOW

Determine the approved treatment of trailing content shorter than 512 tokens:

```text
keep
drop
merge
```

If the repo does not define this:

**STOP AND ASK ME.**

Do not silently drop document tails.

---

# 9 — RESOLVE SPECIAL-TOKEN COUNTING

Determine whether the 512-token limit means:

```text
content tokens only
```

or:

```text
model input length including tokenizer-added special tokens
```

If not explicitly defined:

**STOP AND ASK ME.**

Record the exact tokenizer options used.

---

# 10 — RESOLVE WHAT TEXT IS CHUNKED

Normalized Markdown contains:

```text
YAML frontmatter
+
Markdown body
```

Determine whether Task 1.3 chunks:

```text
A. the entire Markdown file
B. body only, with frontmatter parsed into metadata
C. another explicitly documented representation
```

If not resolved by current docs:

**STOP AND ASK ME.**

This choice changes retrieval text and chunk boundaries.

---

# 11 — FIXED WINDOW MEANS NO SECTION-AWARE SPLITTING

Do not introduce:

```text
split-by-Item
reset windows at Item boundaries
repeat headings into every chunk
semantic paragraph merging
table-aware chunking
recursive text splitting
```

unless current Task 1.3 documentation explicitly requires one of those.

If Item headings are part of approved chunkable body text, they may appear
naturally inside fixed windows as ordinary text.

Do not invent section metadata from fixed windows.

---

# 12 — VERIFY TOKEN ROUND-TRIP / TEXT PRESERVATION

Inspect tokenizer behavior on representative Markdown containing:

```text
Unicode
headings
newlines
punctuation
long SEC prose
```

If token slicing + decode materially changes text in an unexpected way,
do not silently accept it.

If the choice between:

```text
token-id slicing + decode
original-text slicing via tokenizer offset mappings
```

is material and not already defined:

**STOP AND ASK ME.**

The persisted chunk text must be deterministic and defensible.

---

# 13 — RESOLVE THE PHASE 1 CHUNK SCHEMA

The Parquet schema becomes an interface for Tasks 1.4–1.6.

Search current docs for an exact Task 1.3 schema.

If no exact Phase 1 schema is defined:

**STOP AND ASK ME BEFORE PERSISTING IT.**

Do not silently promote the later Phase 2 frozen schema into Task 1.3.

At minimum, evaluate which approved fields are needed for downstream
traceability, potentially including:

```text
chunk_id
document_id
cik
company
form_type
fiscal_year
source
source_filename
source_split
ordinal
text
token_count
chunk_config_hash
normalizer_version
normalization_build_sha256
development_manifest_sha256
```

This is a candidate concept list, not permission to add every field.

Do not fabricate:

```text
accession
section_id
section_title
table_id
```

when Task 1.3 does not actually know them.

Preserve:

```text
cik -> int64
fiscal_year -> int32
```

---

# 14 — RESOLVE CHUNK ORDINAL AND CHUNK ID

Every chunk needs a deterministic stable ID for later retrieval/citation.

Search for an approved Phase 1 convention.

Do not invent one.

If no rule exists:

**STOP AND ASK ME.**

Possible options may include:

```text
document_id + ordinal
config-hash-prefixed document_id + ordinal
cryptographic hash
```

The final rule must be:

```text
deterministic
globally unique
reproducible
stable for the same input/config
```

Also resolve whether ordinal is zero-based or one-based if not already
defined.

---

# 15 — CREATE THE CHUNK CONFIG

Create a small deterministic tracked config under the existing `configs/`
convention.

It must capture every decision that affects chunk identity or text.

Conceptually:

```text
schema_version
input_normalizer_version
input_normalization_build_sha256
development_manifest_sha256
tokenizer identity/revision
window_size_tokens
overlap_tokens / stride
special-token policy
final-partial-window policy
frontmatter/body policy
decode/offset policy
chunk schema version
chunk_id policy
```

Use only actual resolved fields.

Do not include timestamps in the hashed configuration.

---

# 16 — COMPUTE `chunk_config_hash`

Task 0.7 intentionally made:

```text
storage.chunks_dir(chunk_config_hash)
```

consume a hash computed elsewhere.

Task 1.3 is the appropriate place to compute it.

Use a deterministic canonical representation.

Do NOT use Python's built-in:

```python
hash(...)
```

for durable identity.

If the exact canonicalization/hash representation is not already defined
and freezing it would create a durable cross-task contract:

**STOP AND ASK ME.**

---

# 17 — OUTPUT LOCATION

Use `src.storage`.

Expected conceptual output:

```text
artifacts/chunks/<chunk_config_hash>/
```

Do not hardcode artifact paths.

Do not write the large chunk corpus into:

```text
data/
results/
configs/
```

`results/` is for small tracked summaries, not the Parquet corpus.

---

# 18 — RESOLVE PARQUET LAYOUT

Task 1.3 must persist Parquet.

Determine whether current docs define:

```text
one Parquet file
multiple deterministic shards
partitioned Parquet dataset
```

Do not overengineer, but do not silently choose if later tasks depend on the
layout.

If undefined:

**STOP AND ASK ME.**

Whatever is chosen must be deterministic and documented.

---

# 19 — IMPLEMENTATION LOCATION

Implement real Phase 1 chunking under:

```text
src/chunk/
```

Prefer a small reusable module such as:

```text
src/chunk/fixed_window.py
```

for pure logic, with a thin script such as:

```text
scripts/chunk_development_corpus.py
```

for orchestration.

Use existing conventions if actual repository naming differs.

Do not put the chunker in:

```text
src/normalize/
src/ingest/
scripts/serving_spike.py
```

---

# 20 — USE FOUNDATION BOUNDARIES

Use:

```text
src.config
src.storage
src.logging_utils
```

where applicable.

Do not add direct:

```text
os.getenv("STORAGE_ROOT")
Path("artifacts/...")
logging.basicConfig(...)
```

inside the new Phase 1 implementation.

---

# 21 — CPU / OFFLINE ONLY

Task 1.3 is tokenizer/text-processing work.

Do not:

```text
compute embeddings
perform CUDA inference
build LanceDB
perform vector search
```

Tokenizer loading is allowed only under the approved offline tokenizer
contract.

No network access.

---

# 22 — DETERMINISTIC DOCUMENT ORDER

Enumerate normalized files in a canonical order.

Do not depend on filesystem iteration order.

The same normalized corpus + same config must yield:

```text
same chunk order
same chunk IDs
same chunk text
same token counts
same metadata
```

---

# 23 — VALIDATE FRONTMATTER

For every normalized document, verify the expected Task 1.2 frontmatter
contract before chunking.

If parsing frontmatter requires a new dependency and the repo does not
already provide an approved parser:

**STOP AND ASK ME.**

Do not silently add PyYAML.

Do not chunk malformed Markdown as raw text.

---

# 24 — CHUNK VALIDATION

For every emitted chunk verify:

```text
chunk_id present
chunk_id globally unique
source document identity present
ordinal valid
text non-empty
token_count > 0
token_count respects approved 512-token semantics
chunk_config_hash matches config
metadata types correct
```

Do not emit zero-token chunks.

---

# 25 — DOCUMENT COVERAGE

After the real build report:

```text
normalized documents total
documents with >=1 chunk
documents with 0 chunks
unexpected missing documents
```

Any zero-chunk document not explicitly covered by the approved empty-source
policy is a failure.

---

# 26 — TOKEN COVERAGE

Verify the fixed windows cover the approved chunkable text exactly according
to the resolved:

```text
window size
stride/overlap
partial-window rule
```

Do not silently skip middle or trailing content.

If overlap is nonzero, distinguish:

```text
unique source tokens
emitted tokens including overlap
```

where practical.

---

# 27 — REAL BUILD STATISTICS

For the complete 1,500-document build record:

```text
chunk count
documents with chunks
documents without chunks

chunks/document:
  min
  median
  p95
  max

tokens/chunk:
  min
  median
  p95
  max

full 512-token chunks
partial chunks
total emitted tokens
Parquet artifact size
build runtime
```

Do not report retrieval quality.

---

# 28 — MANUAL INSPECTION

Inspect at least 10 source documents across multiple years.

Include:

```text
a long filing
a sparse filing
an approved empty-source filing
```

Trace:

```text
normalized Markdown
→ chunks
```

Verify:

```text
metadata correct
order correct
boundaries correct
no invented text
no unexplained missing text
chunk IDs map correctly
```

---

# 29 — DETERMINISM

Run the real build twice from fresh processes.

Required:

```text
same chunk_config_hash
same chunk count
same logical row order
same chunk IDs
same chunk text
same metadata
```

Do not require identical physical Parquet bytes unless the selected writer
contract guarantees that.

If you add a separate logical chunk-build checksum, document exactly what it
hashes and do not confuse it with `chunk_config_hash`.

If introducing such a checksum is itself an undefined durable contract:

ASK ME FIRST.

---

# 30 — EXISTING ARTIFACT SAFETY

If:

```text
artifacts/chunks/<chunk_config_hash>/
```

already exists, inspect its provenance.

If it matches, verify/reuse according to current policy.

If it conflicts, do not overwrite or delete silently.

If overwrite/rebuild behavior is undefined:

**STOP AND ASK ME.**

Never delete the whole chunks root.

---

# 31 — SMALL TRACKED SUMMARY

Create a small tracked Task 1.3 result under the existing `results/`
convention.

A reasonable conceptual filename is:

```text
results/phase_1_3_chunking_summary.json
```

Use the actual repository naming convention.

Record at minimum:

```text
schema_version
input_normalizer_version
input_normalization_build_sha256
development_manifest_sha256
chunk_config_hash
tokenizer identity
window size
overlap/stride
partial-window policy
frontmatter/body policy
chunk count
document coverage
token statistics
artifact path
created_at_utc
```

This is provenance only.

Do not put the full chunks into `results/`.

---

# 32 — DOCUMENTATION

Create:

```text
project_plan/PHASE1_CHUNKING.md
```

unless the current repository explicitly uses another name.

Document:

```text
purpose
corrected Task 1.2 input
tokenizer identity/revision/offline policy
512-token semantics
overlap/stride
partial-window rule
frontmatter/body policy
heading behavior
decode/offset strategy
exact Parquet schema
chunk ID rule
chunk_config_hash construction
Parquet layout
artifact location
empty-source handling
known limitations
next consumer: Task 1.4
```

State clearly:

```text
Phase 1 baseline chunking contract
```

Do not claim it is the final Phase 2 production/evaluation schema unless the
repository explicitly says so.

Update `project_plan/REPOSITORY_STRUCTURE.md` only where necessary to mark
`src/chunk/` implemented.

---

# 33 — TESTS

Add focused tests such as:

```text
tests/test_fixed_window_chunker.py
```

Use tiny deterministic fixtures.

Cover the actually approved semantics for:

```text
exact full window
multiple windows
partial final window
overlap/stride
empty body
Unicode
Markdown headings
frontmatter/body policy
token counts
metadata preservation
ordinal behavior
chunk ID determinism/uniqueness
chunk_config_hash determinism
config change -> hash change
```

Do not encode an unanswered assumption into a test.

Do not rebuild the full 1,500-document corpus inside every ordinary pytest
run.

Keep the real corpus build as an explicit Task 1.3 command.

---

# 34 — BUILD COMMAND

Provide one documented command, for example:

```bash
python scripts/chunk_development_corpus.py
```

Use the actual final interface.

It must:

1. validate corrected Task 1.2 provenance,
2. load the frozen chunk config,
3. load the approved tokenizer offline,
4. enumerate normalized documents deterministically,
5. build fixed windows,
6. validate all chunks,
7. write Parquet beneath `artifacts/chunks/<chunk_config_hash>/`,
8. write the small tracked summary,
9. print concise statistics,
10. exit nonzero on invariant failure.

No embedding.

---

# 35 — SAFETY

Task 1.3 must not modify:

```text
data/
artifacts/normalized/phase1-minimal-v1/
```

The normalized corpus is an input.

The chunker must not rewrite it.

Do not call:

```text
SEC
OpenAI
Anthropic
AWS
Hugging Face network endpoints
```

No new dependency is expected.

If one appears necessary:

**STOP AND ASK ME before editing requirements.**

---

# 36 — RUN THE REAL BUILD

Execute Task 1.3 against all 1,500 corrected normalized documents.

Record actual:

```text
chunk_config_hash
artifact path
Parquet layout
chunk count
document coverage
token statistics
artifact size
runtime
```

No estimates.

Then run the determinism verification.

---

# 37 — RUN FOUNDATION TESTS

After implementation:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Required:

```text
0 failures
```

Use actual current test counts.

---

# 38 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Verify the large Parquet chunk artifact is ignored.

Track only small source/config/test/result/doc files.

No generated chunk Parquet should be staged.

Perform the usual secret/personal-path scan.

---

# 39 — UPDATE `Progress.md`

Append:

```markdown
## YYYY-MM-DD — Phase 1.3 Minimal Fixed-Window Chunker
```

Preserve all prior history.

Include:

```text
Objective
Initial State
Task 1.2 corrected provenance
User Decisions / Clarifications
Tokenizer Contract
Chunking Contract
Chunk Schema
Chunk ID Contract
chunk_config_hash
Output / Parquet Layout
Chunk Statistics
Empty-Source Handling
Determinism
Manual Inspection
Tests
Safety
Files Created / Modified
Git
Result
Phase Status
```

Use exactly one result:

```text
PASS — Phase 1 development corpus chunked deterministically into 512-token fixed windows

WARN — chunking completed with one documented non-blocking issue

BLOCKED — fixed-window chunk corpus could not be established safely
```

If PASS:

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE
  1.3 Minimal Fixed-Window Chunker — COMPLETE
  1.4 Baseline Embedding Pipeline  — NEXT
```

---

# 40 — COMMIT TASK 1.3

After:

```text
real build passes
determinism passes
tests pass
generated Parquet confirmed ignored
tracked changes reviewed
Progress.md updated
```

create one coherent Task 1.3 commit.

Preferred message:

```text
Add minimal fixed-window chunker
```

Do not include Task 1.4 work.

Do not tag Phase 1 yet.

Inspect `git remote -v`.

If no remote exists, record:

```text
push deferred — no remote configured
```

If push authorization is ambiguous:

**ASK ME.**

Never force-push.

---

# ACCEPTANCE CRITERIA

Task 1.3 is complete only if:

```text
[ ] Task 1.2 correction verified
[ ] normalizer_version == phase1-minimal-v1
[ ] corrected Task 1.2 state committed
[ ] corrected normalization provenance verified
[ ] exactly 1,500 normalized inputs confirmed

[ ] 7 empty-source documents verified
[ ] their chunking behavior explicitly approved if not already documented
[ ] no placeholder text invented

[ ] exact tokenizer identity resolved
[ ] tokenizer offline behavior resolved
[ ] special-token semantics resolved
[ ] 512-token rule verified from current execution plan
[ ] overlap/stride explicitly resolved
[ ] partial-window rule explicitly resolved
[ ] frontmatter/body policy explicitly resolved
[ ] heading behavior explicitly resolved
[ ] text-preservation/decode policy explicitly resolved where material

[ ] Phase 1 Parquet schema explicitly resolved
[ ] no unsupported accession/section/table metadata fabricated
[ ] CIK int64 preserved
[ ] fiscal_year int32 preserved

[ ] deterministic ordinal rule established
[ ] deterministic chunk ID rule established
[ ] chunk IDs globally unique

[ ] deterministic chunk config created
[ ] chunk_config_hash computed canonically
[ ] Python built-in hash() not used for durable identity

[ ] chunks written through src.storage
[ ] artifacts/chunks/<chunk_config_hash>/ used
[ ] Parquet layout explicitly resolved
[ ] generated Parquet ignored by Git

[ ] all emitted chunks non-empty
[ ] token_count > 0
[ ] token limit respected
[ ] document coverage validated
[ ] no unexplained zero-chunk documents

[ ] real 1,500-document build completed
[ ] statistics recorded
[ ] manual inspection passed
[ ] deterministic rebuild passed

[ ] focused Task 1.3 tests added
[ ] doctor passes
[ ] portable tests have zero failures
[ ] full tests have zero failures

[ ] no embeddings generated
[ ] no LanceDB index built
[ ] no retrieval implemented
[ ] no network download used
[ ] frozen data unchanged
[ ] normalized input Markdown unchanged

[ ] PHASE1_CHUNKING.md created
[ ] REPOSITORY_STRUCTURE.md updated where needed
[ ] Progress.md updated

[ ] staged content reviewed
[ ] one coherent Task 1.3 commit created
[ ] no Task 1.4 work included
[ ] no force-push
```

---

# STOP CONDITIONS

STOP AND ASK ME instead of assuming if:

```text
Task 1.2 still uses v1
corrected Task 1.2 provenance is inconsistent
empty-source chunk behavior is undefined
tokenizer identity is undefined
special-token behavior is undefined
overlap/stride is undefined
partial-window behavior is undefined
frontmatter/body behavior is undefined
text-preservation strategy is materially ambiguous
Phase 1 chunk schema is undefined
chunk_id convention is undefined
Parquet layout is undefined
chunk-config hashing contract is undefined
existing chunk artifacts conflict
a new dependency appears necessary
repository documents materially conflict
Git push authorization is unclear
```

---

# IMPORTANT NON-GOALS

Task 1.3 does NOT:

```text
change the 1,500-document manifest
substitute empty filings
recover missing EDGAR text
parse primary HTML
reconstruct tables
perform section-aware chunking
run chunk-size ablations
run overlap ablations
compute embeddings
use GPU embedding inference
build LanceDB
implement retrieval
call an LLM
generate evaluation questions
implement citations
```

The desired result is only:

```text
corrected Task 1.2 Markdown corpus
             ↓
approved tokenizer semantics
             ↓
deterministic 512-token fixed windows
             ↓
Parquet chunks
             ↓
Task 1.4
```

---

# FINAL RESPONSE TO ME

Return:

## Task

```text
task_1.3_minimal_fixed_window_chunker.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Input

```text
normalizer_version
normalized artifact path
normalization_build_sha256
development_manifest_sha256
normalized document count
empty-source document count
```

## User Decisions

List every clarification you asked and the approved answer.

## Tokenizer

```text
tokenizer identity
revision if applicable
offline/local-only status
special-token semantics
```

## Chunking Contract

```text
window size
overlap/stride
partial-window rule
frontmatter/body policy
heading behavior
decode/offset policy
```

## Chunk Schema

List exact Parquet columns/types.

State explicitly whether it is a Phase 1 baseline schema.

## IDs / Versioning

```text
ordinal rule
chunk_id rule
chunk_config_hash algorithm
chunk_config_hash
```

## Output

```text
artifact path
Parquet layout
chunk count
Parquet size
runtime
```

## Statistics

```text
documents with >=1 chunk
documents with 0 chunks
chunks/document min/median/p95/max
tokens/chunk min/median/p95/max
full-size chunks
partial chunks
total emitted tokens
```

## Empty-Source Filings

Report the approved behavior and count.

## Determinism

```text
run 1 chunk_config_hash
run 2 chunk_config_hash
logical dataset identical: YES/NO
chunk IDs identical: YES/NO
```

## Manual Inspection

```text
documents inspected
chunks inspected
result
```

## Tests

```text
new Task 1.3 tests
portable passed/failed/skipped
full passed/failed/skipped
doctor PASS/FAIL
```

## Safety

Confirm:

```text
data/ unchanged
normalized Markdown unchanged
no network downloads
chunk Parquet ignored
no embeddings created
no index created
```

## Files Modified

List actual tracked/project files only.

## Git

```text
commit created: YES/NO
commit hash
commit message
remote status
push performed: YES/NO
```

## Progress.md

Confirm the Phase 1.3 entry was appended.

## Next Task

If PASS:

```text
task_1.4_baseline_embedding_pipeline.md
```

Do not start it.

Finally state:

```text
No Task 1.4 work started.
```

Stop and wait for my approval.
