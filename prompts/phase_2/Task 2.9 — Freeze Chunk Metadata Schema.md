# Task 2.9 — Freeze Chunk Metadata Schema

## Phase

**Phase 2 — Make the Numbers Trustworthy**

Current repository state:

```text
Data Preparation                              — COMPLETE
Phase 0 — Foundation                          — COMPLETE
Phase 1 — Make It Work End to End             — COMPLETE WITH WARN

Phase 2 — Make the Numbers Trustworthy        — IN PROGRESS
  2.1 XBRL Truth Contract                     — COMPLETE
  2.2 Freeze Supported Tag Registry           — COMPLETE
  2.3 Build the Full Evaluation Dataset       — COMPLETE WITH NOTE
  2.4 DEV/TEST Split                          — COMPLETE
  2.5 Evaluation Schema                       — COMPLETE
  2.6 Metric Unit Tests                       — COMPLETE
  2.7 MS MARCO Harness Validation             — COMPLETE
  2.8 Primary Document Evidence Alignment     — COMPLETE WITH NOTE
  2.9 Freeze Chunk Metadata Schema            — CURRENT
```

Known notes/warnings remain:

```text
Phase 1:
Task 1.7a citation-format compliance remains 8/10.

Task 2.3:
50 narrative questions remain pending_review, not gold.

Task 2.6:
numeric_tolerance_match
citation_grounding
faithfulness
remain deferred.

Task 2.8:
primary filings are FY2021–2024 while the frozen truth contract is
FY2016–2020.

eligible_fact_count = 0
gold_evidence_count = 0

This is a structural scope mismatch, not a parser/alignment failure.
```

Do not modify those historical outcomes during Task 2.9.

---

# 1. Objective

Freeze the **canonical chunk metadata schema** that all later SEC chunking,
indexing, retrieval, evidence-labeling, and Phase 3 experiments must use.

The purpose is to prevent every future chunker/index from inventing slightly
different metadata and identifiers.

Task 2.9 answers:

```text
What exactly is a chunk record?

Which fields are required?

What does each field mean?

Which fields may be null?

What are the canonical types?

How is a globally unique chunk identified?

How is a chunk identified locally inside one document?

What coordinate system do char_start / char_end use?

How are prose and table chunks represented?

How do EDGAR-CORPUS and primary-document chunks fit the same contract?
```

This task freezes **schema semantics**.

It does NOT yet implement Phase 3 chunking improvements or full-corpus
indexing.

---

# 2. Authoritative Task Contract

Read first:

1. `project_plan/PROJECT_EXECUTION.md`
2. `project_plan/PHASE1_CHUNKING.md`
3. `src/chunk/fixed_window.py`
4. `configs/chunk_development_corpus.json`
5. `results/phase_1_3_chunking_summary.json`
6. `project_plan/PHASE2_PRIMARY_EVIDENCE.md`
7. `src/parse/source_identity.py`
8. `src/parse/primary_html.py`
9. `src/parse/evidence_alignment.py`
10. `results/phase_2_8_primary_evidence_summary.json`
11. `project_plan/PHASE2_EVALUATION_SCHEMA.md`
12. `src/eval/evaluation_schema.py`
13. `src/storage.py`
14. `project_plan/REPOSITORY_STRUCTURE.md`
15. `Progress.md`

The exact Task 2.9 contract from `PROJECT_EXECUTION.md` is:

```text
Freeze the canonical fields before large-scale indexing.

At minimum:

chunk_uid
chunk_local_id
accession/document identity
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

Treat those as mandatory semantic requirements.

---

# 3. Important Boundary With Task 2.10

Task 2.10 separately owns:

```text
Config hashing and artifact versioning
```

including:

```text
hash chunking configuration
version chunk directories
version index directories
store embedding-model identity
prevent stale-index / new-config mismatches
CI artifact-compatibility assertions
```

Therefore Task 2.9 must NOT prematurely implement the full Task 2.10
artifact-versioning system.

Task 2.9 may:

```text
define chunk_config_hash as a required field
validate its syntax
preserve existing Phase 1 values
document its semantic role
```

but must NOT redesign the entire artifact path/versioning architecture.

The desired sequence is:

```text
2.9  freeze what a chunk record means
        ↓
2.10 freeze how configurations/artifacts are identified and matched
```

---

# 4. Establish Baseline

Before modifying anything:

```bash
git branch
git status --short
git log --oneline --decorate -15

python --version
python -c "import sys; print(sys.executable)"
```

Run:

```text
doctor
portable tests
```

Record:

```text
HEAD
working-tree state
portable-test baseline
full-test baseline

Phase 1 chunk row count
Phase 1 chunk_config_hash

Task 2.8 parser_config_hash
Task 2.8 canonical_evidence_hash

official SEC TEST evaluations consumed
```

Historical reference state:

```text
Phase 1 chunks:
162,357

Phase 1 chunk_config_hash:
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

Task 2.8 parser_config_hash:
84f6cf2e9cf04921cbffc20cf446eac03885e0a87f05e03c9eb71d4eb6c6288d

Task 2.8 canonical_evidence_hash:
32381b6cee8e8bd3fbb741f9f4326dc27384b283829bfdb5da388ab5e6c5dcc2

Task 2.8 tests:
portable = 740 passed, 23 deselected
full     = 763 passed, 0 failed

official SEC TEST evaluations:
0 / 3
```

These are historical references.

Verify actual current values.

---

# 5. Do Not Treat the Phase 1 Schema as Canonical

Task 1.3 currently has the baseline schema:

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

That schema was explicitly documented as:

```text
Phase 1 baseline schema
NOT the final Phase 2 canonical chunk schema
```

Do not simply rename that schema and call Task 2.9 complete.

Task 2.9 must deliberately reconcile:

```text
Phase 1 fixed-window chunks
+
Task 2.8 structural primary-document evidence
+
future section/table-aware chunks
```

into one stable contract.

---

# 6. Do Not Rewrite Phase 1 Artifacts

Do NOT modify:

```text
artifacts/chunks/<phase1-hash>/chunks.parquet
artifacts/embeddings/
artifacts/indexes/
```

Do not regenerate the Phase 1 baseline merely to make it use the new schema.

Task 2.9 freezes the contract for future artifacts.

Existing Phase 1 artifacts remain historical baseline artifacts.

A compatibility adapter may be created for validation.

Do not perform destructive migration.

---

# 7. Canonical Schema Version

Define an explicit:

```text
chunk_schema_version
```

Suggested initial value:

```text
1
```

or repository-equivalent.

This version identifies the meaning of the chunk record schema.

Do not confuse:

```text
chunk_schema_version
```

with:

```text
chunk_config_hash
```

They represent different things.

`chunk_schema_version`:

```text
what fields mean
```

`chunk_config_hash`:

```text
how the chunk was generated
```

Task 2.10 will strengthen config/artifact hashing later.

---

# 8. One Source of Truth

Create exactly one authoritative schema definition.

Recommended architecture:

```text
src/chunk/metadata_schema.py
```

with a canonical schema specification and validators.

If a tracked declarative schema file is useful, use something like:

```text
configs/phase_2_9_chunk_metadata_schema.json
```

but avoid manually maintaining two competing definitions.

Preferred pattern:

```text
one authoritative schema definition
        ↓
Python/PyArrow schema derived from it
        ↓
documentation/result snapshot generated from it
```

Do not maintain field names/types independently in several files.

---

# 9. Required Canonical Fields

At minimum freeze explicit fields corresponding to the roadmap.

Recommended canonical field set:

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

The roadmap's phrase:

```text
accession/document identity
```

must not become one ambiguous overloaded field.

Prefer:

```text
document_id     required canonical document identity
accession       nullable SEC accession where genuinely known
```

unless an existing repository contract establishes a better equivalent.

---

# 10. Never Fabricate Accessions

This repository already established an important limitation:

```text
EDGAR-CORPUS does not provide a reliable accession number.
```

Therefore:

```text
accession = NULL
```

is correct for EDGAR-CORPUS records where no accession is genuinely known.

Do NOT derive an accession from:

```text
filename
CIK + year
XBRL candidate accession
nearest submission
```

unless an exact authoritative mapping exists.

For primary documents, the accession is known from source identity and
should be populated.

---

# 11. document_id Semantics

Freeze `document_id` as the canonical identity of the source document.

It must be:

- deterministic;
- stable;
- source-traceable;
- non-null;
- independent of filesystem absolute paths.

Existing examples include:

```text
EDGAR-CORPUS:
1005817_2016.htm

primary:
primary:{cik}:{accession}
```

Do not force both sources to use an identical physical identifier format if
that would destroy source identity.

Instead:

```text
source + document_id
```

must unambiguously identify the source document.

Document exact semantics.

---

# 12. chunk_local_id Semantics

Freeze `chunk_local_id` as:

```text
the deterministic identity of the chunk inside its source document
for one specific chunking configuration
```

It must not need global information to compute.

It should remain readable/debuggable where practical.

Possible representation:

```text
chunk000123
```

or:

```text
item_7:000123
```

depending on the approved chunking architecture.

Do not automatically reuse the Phase 1:

```text
{document_id}::chunk{ordinal}
```

because that is not truly a document-local identifier.

If the repository contains no established final format, select and document
one deterministic format based on the canonical semantics.

---

# 13. chunk_uid Semantics

Freeze `chunk_uid` as the globally unique canonical chunk identity.

Required properties:

```text
deterministic
globally unique across supported SEC sources
stable across rebuilds with identical semantic inputs
changes when chunk semantics/configuration changes
independent of physical row order
independent of artifact path
independent of Git SHA
independent of timestamps
```

Recommended semantic ingredients:

```text
chunk_schema_version
source
document_id
chunk_config_hash
chunk_local_id
```

A deterministic SHA-256 over canonical JSON of those fields is a reasonable
implementation if no existing repository contract contradicts it.

For example conceptually:

```text
chunk_uid =
SHA256(
  canonical_json({
    schema_version,
    source,
    document_id,
    chunk_config_hash,
    chunk_local_id
  })
)
```

Do not use Python's built-in:

```python
hash()
```

Do not use random UUIDs.

---

# 14. chunk_uid Must Change With Chunk Configuration

If the same filing is chunked:

```text
512 tokens / zero overlap
```

and later:

```text
1024 tokens / section-aware
```

those are different chunks.

Therefore globally identifying them solely as:

```text
document + ordinal
```

is unsafe.

The identity must incorporate or otherwise be bound to the chunking
configuration.

Do not rely on artifact-directory paths for this distinction.

---

# 15. ordinal Semantics

Freeze:

```text
ordinal
```

as a non-negative integer.

Recommended semantics:

```text
zero-based canonical chunk order within the document
```

unless the repository already defines otherwise.

This ordering should be sufficient to reconstruct document chunk sequence
without depending on database row order.

Do not use:

```text
Parquet row number
LanceDB row number
```

as ordinal.

---

# 16. Character Offset Contract

`char_start` and `char_end` are meaningless unless the coordinate system is
frozen.

Define explicitly:

```text
zero-based
half-open interval
[char_start, char_end)
```

such that:

```python
canonical_document_text[char_start:char_end] == chunk_source_span
```

for chunks represented by one contiguous text span.

Boundary rules:

```text
0 <= char_start <= char_end
```

For non-empty contiguous prose:

```text
char_end > char_start
```

Do not use inclusive `char_end`.

---

# 17. Freeze the Offset Coordinate Space

Do NOT let:

```text
char_start / char_end
```

mean:

```text
raw HTML offsets for primary docs
normalized Markdown offsets for EDGAR
Docling node offsets for another source
```

depending on the row.

One field must have one semantic meaning.

Define the offsets relative to the **canonical document text representation
consumed by the chunker**.

If the current architecture cannot create a meaningful contiguous span for a
particular structural object such as a serialized table:

```text
char_start = NULL
char_end   = NULL
```

is preferable to approximate or source-dependent offsets.

If an additional minimal field such as:

```text
offset_basis
```

is genuinely required to keep semantics unambiguous, surface and justify
that decision rather than silently overloading the fields.

---

# 18. Offset Validation

Test:

```text
start = 0
normal span
end-of-document span
Unicode text
CRLF-normalized source
zero-width invalid span
negative offset
end < start
end > source length
```

For records with populated offsets, verify the slice against the canonical
source text.

Do not trust metadata without round-trip validation.

---

# 19. section_id

Freeze `section_id` as the stable machine-readable section identity.

Examples might include:

```text
item_1
item_1a
item_7
item_7a
item_8
```

Use the repository's established normalization where it exists.

Do not derive section IDs differently in multiple chunkers.

If a Phase 1 fixed-window chunk crosses section boundaries and therefore
does not have one defensible section:

```text
section_id = NULL
```

is correct.

Do not assign whichever heading happened to occur first.

---

# 20. section_title

`section_title` is the human-readable section title where confidently
available.

Keep it distinct from:

```text
section_id
```

Examples:

```text
section_id:    item_7
section_title: Management's Discussion and Analysis...
```

Do not synthesize titles when the source parser does not reliably provide
one.

Nullable is acceptable.

---

# 21. content_type

Freeze a small explicit enum.

Unless current authoritative repository semantics contradict it, use the
minimal initial set:

```text
prose
table
table_summary
```

Semantics:

```text
prose
  canonical source prose/list/heading content used directly as retrieval text

table
  serialized content representing authoritative source table rows/cells

table_summary
  derived table representation, never authoritative source evidence
```

Do not add:

```text
chart
image
pdf
other
```

without an actual current requirement.

Schema stability benefits from a small taxonomy.

---

# 22. table_id

`table_id` is nullable.

Rules:

```text
content_type = prose
    table_id normally NULL

content_type = table
    table_id required

content_type = table_summary
    table_id required
```

All chunks derived from the same original table must share the same
`table_id`.

Do not derive `table_id` from physical row position alone.

Use the deterministic Task 2.8 table identity contract where available.

---

# 23. Table Source vs Summary

Do not allow:

```text
table_summary
```

to masquerade as source evidence.

If table-summary chunks are supported by the schema:

```text
content_type = table_summary
```

must make their derived nature explicit.

Inline-XBRL evidence labels should point to authoritative:

```text
table
```

or source structural evidence, not an LLM-generated summary.

Task 2.9 does not generate table summaries.

---

# 24. source

Freeze source semantics.

For the SEC project corpus, expected values are likely:

```text
edgar_corpus
primary
```

Use exact repository-established names.

Do not put MS MARCO benchmark passages into the SEC canonical chunk schema
unless `PROJECT_EXECUTION.md` explicitly requires that.

MS MARCO remains a benchmark track.

---

# 25. cik

Freeze:

```text
cik: int64
```

where applicable to SEC chunks.

Do not store CIK as arbitrary strings with zero-padding differences.

If serialized to JSON:

```text
320193
```

not:

```text
"0000320193"
```

unless the repository has explicitly frozen another representation.

Canonical identity formatting can separately zero-pad when necessary.

---

# 26. fiscal_year

Freeze:

```text
fiscal_year: int32
```

Do not treat filing year as fiscal year.

The project has already made that distinction repeatedly.

No implicit coercion from malformed strings.

---

# 27. period_end

Freeze:

```text
period_end: date / nullable
```

It should represent the filing's reporting-period end where authoritatively
known.

For primary filings/XBRL submissions this can often be resolved from source
metadata.

For EDGAR-CORPUS where exact accession/submission linkage is unavailable:

```text
NULL
```

may be correct.

Do not manufacture:

```text
December 31 of fiscal_year
```

for every company.

---

# 28. filed_date

Freeze:

```text
filed_date: date / nullable
```

Populate only from authoritative filing metadata.

Do not infer:

```text
fiscal_year + 90 days
```

or another approximate date.

---

# 29. SIC

Freeze:

```text
sic: int32 / nullable
```

The repository has already established that SIC exists in raw SEC metadata
but is not necessarily persisted in `xbrl.duckdb`.

Task 2.9 may validate/reuse an existing read-only SIC mapping.

Do NOT:

```text
alter data/xbrl.duckdb
download new SEC metadata
guess industry from company name
```

If unavailable for a chunk:

```text
sic = NULL
```

---

# 30. company

Freeze `company` as the display company name associated with the source
document.

Do not use company name as identity.

Identity remains:

```text
CIK / document_id / accession
```

Names can change and can have formatting variants.

---

# 31. form_type

Freeze:

```text
form_type
```

as the SEC filing type where applicable.

For the current project chunks it is normally:

```text
10-K
```

Do not silently normalize amendments or other forms into `10-K` if they are
not actually 10-K.

---

# 32. text

`text` is the actual retrieval text for the chunk.

It must be:

```text
string
non-empty for emitted chunks
UTF-8-compatible
```

Do not store the embedding vector here.

Do not store the full source document here.

Do not append invisible metadata to the string merely to satisfy the schema.

---

# 33. token_count

Freeze:

```text
token_count: int32
```

and document which tokenizer/config defines it.

For current/future BGE-based chunking, token counting must follow the
chunking configuration rather than an unrelated whitespace count.

Do not recompute token_count with a different tokenizer during validation.

Task 2.10 owns broader configuration identity.

---

# 34. chunk_config_hash

Freeze the field as:

```text
string
non-null
semantic identity of the chunking configuration
```

For existing Phase 1 chunks:

```text
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
```

is already present.

Task 2.9 should validate:

```text
type
non-empty
expected SHA-256 format if that remains the project convention
```

Do not redesign the hashing algorithm here unless the current repository
proves it is invalid.

Task 2.10 will formally enforce config/artifact hashing.

---

# 35. Nullability Must Be Frozen

For every field explicitly declare:

```text
type
nullable?
semantic meaning
validation rule
source availability
```

Create a matrix similar to:

| Field | Type | Nullable | Meaning |
|---|---|---:|---|
| chunk_uid | string | No | global chunk identity |
| chunk_local_id | string | No | document-local chunk identity |
| document_id | string | No | canonical source-document identity |
| accession | string | Yes | SEC accession when authoritatively known |
| cik | int64 | No for SEC | SEC company identity |
| fiscal_year | int32 | No for current SEC chunks | fiscal year |
| period_end | date32 | Yes | reporting-period end |
| filed_date | date32 | Yes | filing date |
| sic | int32 | Yes | SEC SIC |
| section_id | string | Yes | machine section identity |
| section_title | string | Yes | human section title |
| ordinal | int32 | No | zero-based document chunk order |
| char_start | int64/int32 | Yes | start in canonical document text |
| char_end | int64/int32 | Yes | exclusive end |
| content_type | enum/string | No | prose/table/table_summary |
| table_id | string | Yes | deterministic table identity |
| source | enum/string | No | source corpus |
| text | string | No | retrieval text |
| token_count | int32 | No | configured tokenizer count |
| chunk_config_hash | string | No | chunk-config identity |

Use the actual final types selected after repository inspection.

---

# 36. Additional Fields

Do not automatically discard useful Phase 1 provenance such as:

```text
normalizer_version
normalization_build_sha256
development_manifest_sha256
source_filename
source_split
```

but distinguish:

```text
canonical required fields
```

from:

```text
source/build-specific extension metadata
```

Task 2.9 should decide whether these become:

A. optional canonical fields,

B. source-specific extension metadata,

or

C. historical Phase 1-only fields.

Do not stuff every historical field into the canonical schema merely to
avoid making a decision.

---

# 37. Prefer a Stable Core + Explicit Extensions

A good architecture may be:

```text
canonical chunk core
+
optional provenance extensions
```

rather than a 50-column record where half the fields are meaningful only
for one source.

However, the minimum Task 2.9 fields remain mandatory schema concepts.

Document extension policy explicitly.

---

# 38. PyArrow Schema

Because current chunk artifacts use Parquet, expose a canonical PyArrow
schema or equivalent typed schema.

Verify important physical types such as:

```text
cik          int64
fiscal_year  int32
ordinal      int32
char_start   int64 or selected canonical integer type
char_end     same type
token_count  int32
period_end   date32
filed_date   date32
text         string
```

Do not rely on pandas type inference.

---

# 39. Validation API

Implement narrow validation helpers, conceptually:

```python
validate_chunk_record(record)
validate_chunk_table(table)
build_chunk_uid(...)
validate_chunk_uid(...)
```

Exact names may follow repository conventions.

Validation should fail loudly for invalid canonical metadata.

Do not silently coerce malformed values.

---

# 40. Cross-Field Invariants

Validate relationships, not just individual types.

At minimum:

```text
ordinal >= 0
token_count > 0

char_start and char_end:
  both NULL
  OR
  both populated

if populated:
  0 <= char_start < char_end

content_type=table:
  table_id != NULL

content_type=table_summary:
  table_id != NULL

content_type=prose:
  table_id normally NULL

accession:
  valid canonical format when populated

chunk_uid:
  matches deterministic identity inputs

chunk_local_id:
  unique inside document + chunk config

chunk_uid:
  globally unique
```

---

# 41. Accession Validation

When accession is populated, normalize/validate SEC accession formatting.

Use one canonical representation.

Do not allow both:

```text
0000320193-24-000123
```

and:

```text
000032019324000123
```

to represent separate identities unless the schema explicitly defines one
as normalized and one as raw.

Prefer the hyphenated SEC accession already used throughout the project if
that matches current repository conventions.

---

# 42. Existing Phase 1 Compatibility Audit

Create a non-destructive adapter/audit for:

```text
artifacts/chunks/<phase1-hash>/chunks.parquet
```

Map every existing Phase 1 row into the new schema **where semantics are
defensible**.

Expected examples:

```text
source         <- edgar_corpus
document_id    <- existing document_id
cik            <- existing cik
company        <- existing company
form_type      <- existing form_type
fiscal_year    <- existing fiscal_year
ordinal        <- existing ordinal
text           <- existing text
token_count    <- existing token_count
chunk_config_hash <- existing hash
```

Fields that cannot be established correctly must remain NULL.

Do not infer them merely to make completeness look better.

---

# 43. Phase 1 Missing Metadata Is Not a Failure

The Phase 1 baseline intentionally ignored:

```text
sections
tables
filed dates
period end
SIC
accessions
```

in several places.

Therefore an audit showing NULL for those fields is not automatically a
Task 2.9 failure.

The purpose is to verify:

```text
the canonical schema can represent the baseline honestly
```

not:

```text
retroactively pretend Phase 1 contained information it did not.
```

---

# 44. Primary-Document Compatibility Audit

Use Task 2.8 artifacts to confirm the canonical schema can represent future
primary-document chunks.

Validate a deterministic sample of:

```text
paragraph/prose nodes
table nodes
known accession
known section
known structural source locator
known XBRL-correlated evidence
```

Do NOT need to create a full new primary-document chunk corpus.

Task 2.8 already processed the 990 filings.

Task 2.9 only proves schema compatibility.

---

# 45. Do Not Promote Would-Be-Gold Evidence

Task 2.8 has:

```text
45,769 facts matching every truth rule except year window
```

and:

```text
gold_evidence_count = 0
```

Task 2.9 must preserve that.

Do not use the new chunk schema to relabel those records as current gold.

Do not modify:

```text
chunk_recall@10 available_for_current_gold
chunk_mrr available_for_current_gold
```

They remain false.

---

# 46. Schema Compatibility Summary

Create a small tracked result:

```text
results/phase_2_9_chunk_metadata_schema.json
```

Include at minimum:

```text
chunk_schema_version
canonical_fields
types
nullability
enums

chunk_uid algorithm/contract
chunk_local_id contract
offset contract

phase1_rows_audited
phase1_compatibility
phase1_nullability_by_field

primary_samples_audited
primary_compatibility

known limitations

created_at_utc
git_sha
```

Do not include large chunk payloads.

---

# 47. Do Not Hash the Whole Artifact Yet

Task 2.10 owns artifact/config versioning.

Task 2.9 may report:

```text
schema version
```

and existing `chunk_config_hash` identities.

Do not prematurely create a complex artifact-manifest/hash hierarchy unless
the current Task 2.9 execution plan explicitly requires it.

If you compute a small schema fingerprint purely for verification, clearly
label it:

```text
schema fingerprint
```

not:

```text
chunk_config_hash
artifact hash
```

and do not replace Task 2.10.

---

# 48. Determinism

Verify:

```text
same identity inputs
    -> same chunk_local_id

same identity inputs
    -> same chunk_uid
```

across fresh processes.

Changing any identity-bearing field such as:

```text
source
document_id
chunk_config_hash
chunk_local_id
```

must produce a different global `chunk_uid`.

Ordering of unrelated metadata must not affect it.

---

# 49. Collision Checks

Against all:

```text
162,357 Phase 1 chunks
```

derive canonical `chunk_uid` values and verify:

```text
162,357 rows
162,357 unique chunk_uid
```

Do not rewrite the source Parquet.

This is an in-memory/read-only compatibility audit.

---

# 50. Local-ID Checks

For every Phase 1 document verify:

```text
(chunk_local_id, chunk_config_hash)
```

is unique inside that document.

Also verify ordinals are:

```text
0 .. n-1
```

with no duplicates/gaps unless the existing baseline intentionally defines a
different valid behavior.

---

# 51. Source-Agnostic Global IDs

Create synthetic tests proving that:

```text
source=edgar_corpus
document_id=X
```

and:

```text
source=primary
document_id=X
```

cannot produce the same `chunk_uid`.

Source identity must participate in global identity.

---

# 52. Offset Round-Trip Tests

Use hand-built canonical text:

```text
0123456789...
```

and realistic Unicode/SEC text.

Verify:

```text
text[start:end]
```

exactly reproduces the intended source span.

Include:

```text
Unicode punctuation
multi-byte UTF-8 characters
newlines
Markdown headings
```

Offsets are Python/Unicode code-point character offsets unless another
explicit repository-wide convention is selected.

Do not confuse byte offsets with character offsets.

---

# 53. Table Tests

Use synthetic table metadata to verify:

```text
same original table
multiple table chunks
same table_id
different chunk_local_id
different chunk_uid
```

If table summary is supported:

```text
table source chunk != table-summary chunk UID
```

even when tied to the same table.

---

# 54. Schema Evolution Rule

Document how future schema changes work.

Recommended:

```text
adding a backward-compatible nullable extension:
evaluate whether schema version changes according to frozen policy

changing meaning/type/nullability of canonical field:
increment chunk_schema_version

changing ID derivation:
increment chunk_schema_version

changing chunking behavior:
new chunk_config_hash, not necessarily new schema version
```

Do not leave evolution undefined.

---

# 55. No Full Rechunking

Do NOT:

```text
rechunk 91,086 EDGAR filings
rechunk the 1,500 Phase 1 corpus
embed anything
build an index
```

unless a tiny temporary fixture is needed for schema validation.

Task 2.9 freezes metadata.

It does not produce the Phase 3 corpus.

---

# 56. No Retrieval Evaluation

Do NOT run:

```text
vector retrieval
BM25
hybrid
reranker
CRAG
router
generation
```

against DEV or TEST.

No new performance metric should come from Task 2.9.

---

# 57. TEST Discipline

Do not load:

```text
artifacts/eval/phase_2_4_test.json
```

Do not call:

```text
load_test_set()
```

Task 2.9 has no reason to inspect protected TEST questions.

Official TEST evaluation accesses must remain:

```text
0 / 3
```

---

# 58. No Network / LLM / GPU Requirement

Task 2.9 should require:

```text
no OpenRouter
no OpenAI
no Anthropic
no SEC requests
no Hugging Face downloads
no LLM calls
```

Schema engineering is CPU-only.

Existing full regression tests may exercise the already-established GPU
smokes on this machine, but Task 2.9 itself must not introduce GPU
dependence.

API spend:

```text
$0
```

---

# 59. Tests

Add:

```text
tests/test_chunk_metadata_schema.py
```

or repository-equivalent.

At minimum cover:

### Schema fields

```text
all mandatory Task 2.9 fields present
types exact
nullability exact
field order deterministic if order is part of contract
```

### IDs

```text
chunk_uid deterministic
chunk_uid global uniqueness
different source -> different UID
different document -> different UID
different chunk config -> different UID
different local ID -> different UID
no Python hash()
```

### Local IDs

```text
stable
document-local
unique within document/config
```

### Accessions

```text
valid accession accepted
malformed accession rejected
NULL allowed for EDGAR-CORPUS
no accession fabrication
```

### Offsets

```text
half-open semantics
round-trip text slice
both-null rule
invalid negative offsets rejected
end-before-start rejected
out-of-range rejected when source supplied
```

### Content type

```text
prose accepted
table accepted
table_summary accepted if frozen
unknown type rejected

table -> table_id required
table_summary -> table_id required
```

### Numeric metadata

```text
CIK type
fiscal year type
SIC nullable/int
ordinal nonnegative
token_count positive
```

### Dates

```text
period_end date or NULL
filed_date date or NULL
invalid date rejected
```

### Config hash

```text
existing SHA-256 accepted
malformed hash rejected if canonical contract requires SHA-256
```

### Phase 1 integration

```text
real Phase 1 chunk artifact maps read-only
all 162,357 UIDs unique
existing metadata preserved
unsupported metadata remains NULL
```

### Task 2.8 integration

```text
primary sample can populate accession
primary sample can populate source/document identity
table/prose compatibility
no gold-status mutation
```

---

# 60. Portable vs Local-Data Tests

Keep ordinary schema tests fully synthetic and portable.

Use:

```text
local_data
```

only for:

```text
real Phase 1 Parquet compatibility
real Task 2.8 artifact compatibility
```

Do not make portable CI depend on hundreds of MB of generated artifacts.

---

# 61. Validation Script

Create a narrow script such as:

```text
scripts/audit_chunk_metadata_schema.py
```

It should:

```text
load canonical schema
validate Phase 1 compatibility
validate Task 2.8 sample compatibility
check UID uniqueness
check local-ID uniqueness
report field coverage/nullability
write the Task 2.9 summary
```

It must NOT:

```text
rechunk
embed
index
retrieve
```

---

# 62. Field Coverage Report

For Phase 1 compatibility report, per field:

```text
populated rows
NULL rows
population %
```

This makes missing legacy metadata visible.

Do not interpret expected historical NULLs as errors unless the canonical
schema declares that field mandatory for that source.

---

# 63. Source-Specific Applicability

Document a matrix such as:

| Field | EDGAR-CORPUS | Primary |
|---|---|---|
| document_id | required | required |
| accession | usually unavailable | required |
| cik | required | required |
| fiscal_year | required | required |
| period_end | nullable | available where authoritative |
| filed_date | nullable | available where authoritative |
| sic | nullable | nullable/available |
| section_id | nullable for Phase 1 baseline | available structurally |
| table_id | unavailable in EDGAR baseline | available for tables |

Use actual audited reality.

Do not assume every source can populate every field.

---

# 64. Documentation

Create:

```text
project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md
```

Document:

- purpose;
- schema version;
- complete field table;
- types;
- nullability;
- field semantics;
- `document_id`;
- accession policy;
- `chunk_local_id`;
- `chunk_uid`;
- global identity algorithm;
- character-offset coordinate system;
- section semantics;
- content-type enum;
- table identity;
- source taxonomy;
- date semantics;
- SIC semantics;
- token-count semantics;
- `chunk_config_hash` role;
- Phase 1 compatibility;
- Task 2.8 compatibility;
- extension-field policy;
- schema-evolution policy;
- known limitations;
- Task 2.10 boundary.

Explicitly state:

```text
Task 2.9 freezes schema semantics.

Task 2.10 freezes/enforces configuration and artifact versioning.
```

---

# 65. Repository Structure

Update:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

narrowly for Task 2.9 files.

Likely:

```text
src/chunk/metadata_schema.py
scripts/audit_chunk_metadata_schema.py
tests/test_chunk_metadata_schema.py
configs/phase_2_9_chunk_metadata_schema.json
results/phase_2_9_chunk_metadata_schema.json
project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md
```

Use actual implemented names.

---

# 66. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.9 Freeze Chunk Metadata Schema
```

Include:

```text
Objective
Initial State
Authoritative Contract
Phase 1 Baseline Schema Audit
Task 2.8 Compatibility Audit
Canonical Schema
Field Types
Nullability
Document Identity
Accession Policy
chunk_local_id
chunk_uid
Offset Semantics
Section Semantics
Content Types
Table Identity
Date/SIC Semantics
Extension Metadata Policy
Schema Evolution
Phase 1 Compatibility Result
Primary Compatibility Result
Determinism
Tests
TEST Discipline
Regression Gates
Files Created/Modified
Git
Result
Phase Status
```

Do not rewrite earlier entries.

---

# 67. Regression Gate — Task 2.8

Verify no semantic changes to:

```text
src/parse/
scripts/build_primary_evidence.py
configs/phase_2_8_primary_evidence.json
results/phase_2_8_primary_evidence_summary.json
```

Expected historical status remains:

```text
990/990 parsed
0 parse errors
0 ambiguous matches
45,769 ineligible-year-window would-be-gold facts
gold = 0
```

Do not change its evidence classifications.

---

# 68. Regression Gate — Tasks 2.1–2.7

Verify no semantic modifications to:

```text
truth contract
tag registry
evaluation dataset
DEV/TEST split
TEST access
evaluation schema
metrics
MS MARCO harness
```

Task 2.9 only freezes chunk metadata.

---

# 69. Regression Gate — Phase 1

Do not modify Phase 1 baseline semantics.

Especially:

```text
src/chunk/fixed_window.py
Phase 1 chunks.parquet
Phase 1 embeddings
Phase 1 LanceDB index
baseline retriever
generation
baseline metrics
```

The new schema may expose an adapter.

It must not retroactively alter the baseline.

---

# 70. Frozen Data Safety

Verify:

```text
data/xbrl.duckdb
data/edgar_corpus/
data/raw/primary/
data/msmarco/
```

remain unchanged.

Task 2.9 should perform read-only compatibility checks only.

---

# 71. Git Safety

Before commit:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Verify no:

```text
data/
artifacts/
.venv/
.env
*.duckdb
large Parquet
model weights
```

will be staged.

Run the existing secret/personal-path scan.

---

# 72. Commit

After all gates pass, create one coherent Task 2.9 commit.

Suggested message:

```text
Freeze canonical chunk metadata schema
```

Do not tag Phase 2 complete.

Tasks 2.10+ remain.

Do not push if no remote exists.

---

# 73. Stop Conditions

STOP rather than inventing semantics if:

### A. Existing repository defines a conflicting canonical ID contract

Surface the conflict.

### B. `chunk_uid` cannot be made globally deterministic

Do not use random UUIDs as a shortcut.

### C. Offset coordinate system cannot be defined consistently

Do not overload `char_start`/`char_end` with source-dependent meanings.

### D. EDGAR accession is unavailable

Use NULL.

Do not fabricate one.

### E. period_end / filed_date cannot be authoritatively resolved

Use NULL.

Do not infer them.

### F. SIC cannot be established

Use NULL.

Do not guess.

### G. Phase 1 chunks cannot populate newer fields

Document the compatibility gap.

Do not rewrite the historical artifact.

### H. Task 2.8 would-be-gold records would need promotion

Do not promote them.

### I. Task 2.10 functionality becomes necessary

Stop at the Task 2.9 schema boundary and document what 2.10 must implement.

---

# 74. Acceptance Criteria

Task 2.9 is complete only when:

```text
[ ] exact Task 2.9 contract confirmed from PROJECT_EXECUTION.md

[ ] canonical chunk schema version defined
[ ] one authoritative schema source exists

[ ] chunk_uid defined
[ ] chunk_uid deterministic
[ ] chunk_uid globally unique
[ ] chunk_uid config-sensitive

[ ] chunk_local_id defined
[ ] chunk_local_id deterministic
[ ] chunk_local_id document-local

[ ] document_id semantics frozen
[ ] accession policy frozen
[ ] no EDGAR accession fabrication

[ ] cik type frozen
[ ] company semantics frozen
[ ] form_type semantics frozen
[ ] fiscal_year semantics frozen
[ ] period_end semantics frozen
[ ] filed_date semantics frozen
[ ] sic semantics frozen

[ ] section_id semantics frozen
[ ] section_title semantics frozen

[ ] ordinal semantics frozen

[ ] char_start/char_end coordinate system frozen
[ ] offsets use half-open intervals
[ ] populated offsets round-trip against source representation
[ ] non-contiguous structures may use NULL rather than fake offsets

[ ] content_type enum frozen
[ ] table_id contract frozen
[ ] table/table-summary distinction explicit

[ ] source taxonomy frozen
[ ] text semantics frozen
[ ] token_count semantics frozen
[ ] chunk_config_hash field semantics frozen

[ ] field types explicit
[ ] nullability explicit
[ ] cross-field validation implemented

[ ] Phase 1 compatibility audit passes
[ ] all 162,357 Phase 1 derived chunk_uids unique
[ ] historical Phase 1 artifacts unchanged

[ ] Task 2.8 primary compatibility audit passes
[ ] primary accession/table/prose representation demonstrated
[ ] Task 2.8 gold count remains 0
[ ] chunk metrics remain unavailable for current gold

[ ] schema determinism tests pass
[ ] synthetic unit tests pass
[ ] local-data integration tests pass

[ ] TEST not loaded
[ ] official TEST evaluations remain 0/3

[ ] no retrieval evaluation
[ ] no embedding build
[ ] no index build
[ ] no LLM calls
[ ] no network
[ ] API spend = $0

[ ] Task 2.8 regression passes
[ ] Task 2.1-2.7 regression passes
[ ] Phase 1 regression passes
[ ] frozen data unchanged

[ ] documentation created
[ ] repository structure updated
[ ] Progress.md appended
[ ] secret scan clean
[ ] git staging dry-run safe
[ ] coherent Task 2.9 commit created

[ ] Task 2.10 NOT started
```

---

# 75. Final Console Summary

Print:

```text
PHASE 2.9 — FREEZE CHUNK METADATA SCHEMA
========================================

Schema:
  version:                         <version>
  canonical fields:               <count>
  required fields:                <count>
  nullable fields:                <count>

Identity:
  chunk_uid algorithm:             <description>
  chunk_uid deterministic:         PASS
  chunk_uid global uniqueness:     PASS
  chunk_local_id contract:         <description>

Offsets:
  coordinate space:                <description>
  interval convention:             [start, end)
  round-trip validation:           PASS

Content:
  content types:                   <values>
  table identity:                  FROZEN
  table-summary distinction:       FROZEN

Phase 1 compatibility:
  rows audited:                    162,357
  unique derived chunk_uids:       162,357
  source artifact modified:        NO
  expected legacy NULLs:           <summary>

Primary compatibility:
  samples audited:                 <count>
  accession support:               PASS
  prose support:                   PASS
  table support:                   PASS
  source artifacts modified:       NO

Task 2.8:
  pipeline regression:             PASS
  gold evidence count:             0
  gold promoted by Task 2.9:       0

TEST discipline:
  TEST loaded:                     NO
  official TEST runs used:         0 / 3

Compute:
  LLM calls:                       0
  network calls:                   0
  API spend:                       $0
  new GPU requirement:             NO

Tests:
  new Task 2.9 tests:              <count>
  doctor:                          PASS
  portable:                        <result>
  full:                            <result>

Regression:
  Task 2.8:                        PASS
  Task 2.1-2.7:                    PASS
  Phase 1:                         PASS
  frozen data:                     PASS

FINAL RESULT:
PASS / PASS WITH NOTE / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
Task 2.10 — Config hashing and artifact versioning

DO NOT START TASK 2.10.
```

---

# Final Principle

Task 2.9 freezes the language every future retrieval component uses when it
says:

```text
"this is a chunk"
```

After this task, two different chunkers should not disagree about what:

```text
chunk identity
document identity
section identity
character offsets
table identity
source
fiscal metadata
```

mean.

The central invariant is:

```text
Same source + same chunking semantics
    -> same canonical chunk identity.

Different chunking semantics
    -> different canonical chunk identity.
```

And missing metadata must remain honestly missing:

```text
NULL is better than invented provenance.
```

Do not fabricate accessions.

Do not infer filing dates.

Do not guess SIC.

Do not invent offsets.

Do not rewrite Phase 1.

Do not promote Task 2.8 would-be-gold evidence.

Freeze the schema first.

Task 2.10 will then freeze how artifacts/configurations carrying that schema
are versioned and matched.