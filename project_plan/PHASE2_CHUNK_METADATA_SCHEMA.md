# Phase 2 Chunk Metadata Schema

Established in Task 2.9. Freezes the canonical chunk-record schema every
future chunker, index, retriever, and evidence-labeling component must
produce/consume. Task 2.9 freezes SCHEMA SEMANTICS only - it builds no
new chunking pipeline, rechunks nothing, re-embeds nothing, re-indexes
nothing, and promotes zero records to gold.

## Objective

A future developer building Phase 3's chunker (or any component that
reads/writes a chunk record) should be able to open this document, call
`src.chunk.metadata_schema`, and know exactly what a chunk record must
contain, what each field means, when a field is legitimately NULL, and
how chunk identity is computed - without inventing an ad-hoc shape or
silently reusing Phase 1's document-embedded local-id pattern.

## Relationship to `PROJECT_EXECUTION.md`'s Task 2.9 section

`PROJECT_EXECUTION.md`'s Task 2.9 section matches this task's own prompt
field list exactly. No discrepancy was found; nothing required stopping
or overriding.

## Schema version

```text
chunk_schema_version:  1
```

`chunk_schema_version` identifies what a chunk record's fields MEAN.
It is deliberately distinct from `chunk_config_hash`, which identifies
HOW a specific chunk was generated (chunking strategy, chunk size,
overlap, tokenizer, normalization version, etc.) - owned formally by
the not-yet-started Task 2.10. Task 2.9 validates `chunk_config_hash`
only as an opaque, non-null, lowercase 64-hex-character SHA-256-shaped
string; it does not define how that hash is computed or matched across
artifacts.

A schema-semantics change (add/remove/retype a field, change a
nullability rule, change the `chunk_uid`/`chunk_local_id` algorithm)
increments `chunk_schema_version`. A chunking-configuration change
(different chunk size, different tokenizer, ...) changes
`chunk_config_hash` instead, and therefore changes `chunk_uid` (see
below) without touching `chunk_schema_version`.

## Canonical schema source

`src/chunk/metadata_schema.py` is the ONE authoritative definition.
The PyArrow schema (`canonical_pyarrow_schema()`), this document's field
table, and `results/phase_2_9_chunk_metadata_schema.json` are all
derived from `CANONICAL_FIELDS` - never independently maintained.

## Field table

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `chunk_schema_version` | int32 | No | Schema-semantics version (this document's version number). |
| `chunk_uid` | string | No | Globally unique, deterministic chunk identity. SHA-256 over canonical JSON of `{chunk_schema_version, source, document_id, chunk_config_hash, chunk_local_id}`. |
| `chunk_local_id` | string | No | Deterministic identity of the chunk inside its source document, for one chunking configuration. Computable from purely local information - no cross-document lookup. |
| `document_id` | string | No | Canonical source-document identity. Source-specific format (see below). `source` + `document_id` together unambiguously identify the source document. |
| `accession` | string | Yes | SEC accession, hyphenated `NNNNNNNNNN-NN-NNNNNN`. NULL for `edgar_corpus` (no reliable accession linkage exists) - never fabricated. |
| `cik` | int64 | No | SEC Central Index Key, canonical integer (never zero-padded string). |
| `company` | string | No | Display company name. Never used as identity. |
| `form_type` | string | No | SEC filing type (e.g. `"10-K"`). |
| `fiscal_year` | int32 | No | Fiscal year - never conflated with filing year. |
| `period_end` | date32 | Yes | Reporting-period end date, where authoritatively known (e.g. a submission's `period`). NULL, never manufactured. |
| `filed_date` | date32 | Yes | Actual SEC filing date, where authoritatively known. NULL, never inferred from `fiscal_year` + an offset. |
| `sic` | int32 | Yes | SIC code, where available from frozen raw SEC metadata. NULL, never guessed from company name. |
| `section_id` | string | Yes | Stable machine-readable section identity (e.g. `"item_7"`). NULL when a chunk spans/crosses sections or identity is genuinely ambiguous. |
| `section_title` | string | Yes | Human-readable section title, where confidently available. NULL rather than synthesized. |
| `ordinal` | int32 | No | Zero-based canonical chunk order within the document - never a Parquet/LanceDB physical row number. |
| `char_start` | int64 | Yes | Zero-based, half-open `[char_start, char_end)` start offset into the canonical document text consumed by the chunker. |
| `char_end` | int64 | Yes | Half-open interval end (exclusive). |
| `content_type` | string enum | No | One of `prose \| table \| table_summary`. |
| `table_id` | string | Yes | Deterministic table identity (reuses Task 2.8's contract where available). Required when `content_type` is `table`/`table_summary`; NULL for prose. |
| `source` | string enum | No | One of `edgar_corpus \| primary`. MS MARCO is never a value here - it is a separate benchmark track. |
| `text` | string | No | The actual retrieval text. Never the embedding vector, never the full source document, never metadata appended into the string. |
| `token_count` | int32 | No | Token count per the chunking configuration's own tokenizer. |
| `chunk_config_hash` | string | No | Opaque SHA-256-hex identity of the chunking configuration. Task 2.10 owns computation/matching. |

23 fields total.

## Document identity (`source` + `document_id`)

- `edgar_corpus`: `document_id` reuses Phase 1's existing document
  identity convention as-is (no accession linkage exists for this
  source).
- `primary`: `document_id` reuses Task 2.8's `f"primary:{cik}:{accession}"`
  convention.

`source` is required precisely so the same `document_id` string can
never be ambiguous, and so that reusing a `document_id` across two
different sources never collides on `chunk_uid` (verified directly -
`tests/test_chunk_metadata_schema.py::TestChunkUid::test_cross_source_isolation_same_document_id`).

## Accession policy

`accession` is populated only where authoritatively known:

- `edgar_corpus`: always NULL. EDGAR-CORPUS carries no reliable
  accession linkage; one is never guessed from filename/CIK/year.
- `primary`: populated directly from Task 2.8's source identity
  (`primary:{cik}:{accession}`), which is itself derived from the real
  filing directory structure, never invented.

Format is validated as hyphenated `NNNNNNNNNN-NN-NNNNNN`
(`ACCESSION_RE`), matching the convention already used consistently
across Tasks 1.9/2.1/2.3/2.4/2.8.

## `chunk_local_id`

```text
build_chunk_local_id(ordinal, section_id=None)
  -> "chunk{ordinal:06d}"                    (no section_id)
  -> "{section_id}:chunk{ordinal:06d}"       (with section_id)
```

Deliberately NOT Phase 1's `"{document_id}::chunk{ordinal}"` pattern.
That format embeds global (document-identifying) information inside
what is supposed to be a purely document-local identifier, which
defeats the purpose of separating "local position within a document"
from "global chunk identity" (`chunk_uid` composes both explicitly
instead). `chunk_local_id` is stable across re-runs of the same
chunking configuration on the same document and requires no
cross-document lookup to compute.

## `chunk_uid`

```text
chunk_uid = SHA256(canonical_json({
    "chunk_schema_version": ...,
    "source": ...,
    "document_id": ...,
    "chunk_config_hash": ...,
    "chunk_local_id": ...,
}))
```

Canonical JSON = `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
Never Python's built-in `hash()` (process-salted, non-reproducible),
never a random UUID.

Central invariant (verified by `TestChunkUid` and the real-artifact
compatibility tests): same source + same document + same chunking
semantics + same local position -> same `chunk_uid`, always; changing
ANY of the five ingredients -> a different `chunk_uid`, always. In
particular, changing chunking configuration (`chunk_config_hash`)
necessarily changes global chunk identity even for what a human would
call "the same chunk" of "the same document."

## Offset semantics

`char_start`/`char_end` describe a zero-based, half-open
`[char_start, char_end)` interval into the canonical document text the
chunker consumed. Both fields are NULL together, or both populated
together - never one-sided. NULL is the correct representation whenever
no defensible contiguous character span exists for a structural object
(e.g. a serialized/reflowed table) - never an approximate or
source-format-dependent offset. `validate_offsets()` additionally
supports an optional round-trip check
(`source_text[char_start:char_end] == chunk_text`) when both texts are
supplied.

## Section semantics

`section_id` is a stable, machine-readable identity (e.g. `"item_7"`);
`section_title` is the human-readable counterpart. Both are NULL when a
chunk spans or crosses section boundaries, or when section identity is
genuinely ambiguous - never defaulted to "the first heading seen."

## Content types

`prose | table | table_summary` only (`CONTENT_TYPES`). Deliberately
small - no chart/image/pdf/other value without an actual current
requirement. `table_id` is required (non-NULL) whenever `content_type`
is `table` or `table_summary`; NULL is normal and expected for `prose`.

## Date / SIC semantics

`period_end`, `filed_date`, and `sic` are populated only where an
authoritative source is directly available:

- `primary`: `period_end`/`filed_date` come from `data/xbrl.duckdb`'s
  `submissions` table (`period`, `filed` columns, keyed by accession) -
  confirmed real and accession-keyed (Task 2.9 baseline audit, e.g.
  accession `0000100122-24-000002` -> `period='20231231'`,
  `filed='20240209'`). `sic` comes from the frozen raw SEC quarterly
  `sub.txt` datasets (same source Task 2.4's DEV/TEST split already
  reads), keyed by accession.
- `edgar_corpus`: all three stay NULL - no accession linkage exists to
  key any of these authoritative lookups against.

None of the three is ever inferred, estimated, or defaulted (e.g. no
"Dec 31 of fiscal_year" for `period_end`, no company-name-based SIC
guess).

## Extension metadata policy

`validate_chunk_record()`/`validate_chunk_table()` permit and ignore
unknown extra dict keys beyond `CANONICAL_FIELDS`. A source-specific
component may attach additional metadata to a chunk record without
violating the canonical contract, as long as every `CANONICAL_FIELDS`
field is present, correctly typed, and satisfies the documented
nullability/enum/cross-field rules above.

## Schema evolution policy

- A **schema-semantics** change (field added/removed/retyped, a
  nullability/enum rule changes, the `chunk_uid`/`chunk_local_id`
  algorithm changes) requires incrementing `CHUNK_SCHEMA_VERSION`.
  Because `chunk_schema_version` is one of the five `chunk_uid`
  ingredients, this automatically changes every derived `chunk_uid`.
- A **chunking-configuration** change (chunk size, overlap, tokenizer,
  table-serialization strategy, ...) is Task 2.10's `chunk_config_hash`
  responsibility, not a schema version bump - it changes `chunk_uid`
  only because `chunk_config_hash` is itself one of the five
  ingredients.
- Historical chunk records are never silently reinterpreted under a new
  schema version; a version bump is a breaking, explicit change.

## Phase 1 compatibility audit

`scripts/audit_chunk_metadata_schema.py` maps all 162,357 real rows of
`artifacts/chunks/f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd/chunks.parquet`
into the canonical schema, read-only (the frozen Parquet artifact is
never rewritten):

```text
source            <- "edgar_corpus"                (constant)
accession         <- None                          (no accession linkage exists)
period_end        <- None
filed_date        <- None
sic               <- None
section_id        <- None                          (fixed-window chunking is section-oblivious)
section_title     <- None
char_start        <- None                          (see below)
char_end          <- None
content_type      <- "prose"                       (Phase 1 baseline has no tables)
table_id          <- None
chunk_local_id    <- build_chunk_local_id(ordinal)  (newly computed)
chunk_uid         <- build_chunk_uid(...)           (newly computed)
everything else   <- existing chunks.parquet columns, unchanged
```

**On `char_start`/`char_end`**: `src/chunk/fixed_window.py` computes
offsets transiently, via tokenizer offset-mapping, purely to slice the
correct substring for each chunk's `text` field
(`slice_chunk_text()`). Those offsets were never added to the
persisted output schema - the real `chunks.parquet` has exactly 16
columns, none named `char_start`/`char_end`. Because the frozen
artifact itself never carried this information, the honest mapping is
NULL, not a retroactive recomputation by re-running the chunker (which
would also risk producing offsets that silently drift from whatever the
original run actually did, and would violate the "never rewrite Phase 1
artifacts" constraint in any case).

Result (`results/phase_2_9_chunk_metadata_schema.json`,
`phase1_compatibility`):

```text
rows_audited:       162357
unique_chunk_uids:  162357
all_uids_unique:    true
```

All 162,357 derived `chunk_uid`s are unique; `(document_id,
chunk_config_hash, chunk_local_id)` is unique within every document.

## Task 2.8 primary-document compatibility sample

Rather than building a full new primary-document chunk corpus (out of
scope for Task 2.9 - see boundary statement below), the audit takes a
deterministic 10-node sample (5 narrative + 5 table structural nodes,
in `source_order`) from one real Task 2.8 parsed artifact
(`artifacts/primary_docs/parsed/primary-100122-0000100122-24-000002.json`,
accession `0000100122-24-000002`) and maps it into the canonical
schema:

```text
source          <- "primary"
document_id     <- "primary:100122:0000100122-24-000002"       (Task 2.8's own identity)
accession       <- "0000100122-24-000002"                      (known)
cik             <- 100122                                      (known)
company         <- submissions.name lookup                     (known, real)
form_type       <- submissions.form lookup                     (known, real)
fiscal_year     <- submissions.fiscal_year lookup               (known, real)
period_end      <- submissions.period lookup, ISO-formatted     (known, real)
filed_date      <- submissions.filed lookup, ISO-formatted      (known, real)
sic             <- frozen sub.txt lookup by accession            (known, real)
section_id      <- StructuralNode.section_id                   (Task 2.8, real)
section_title   <- StructuralNode.section_title                (Task 2.8, real)
ordinal         <- StructuralNode.source_order                 (Task 2.8, real)
content_type    <- "prose" (narrative) | "table" (table)        (mapped from Task 2.8's own enum)
table_id        <- StructuralNode.table_id                     (Task 2.8, real; NULL for prose)
char_start/end  <- None                                        (see limitation below)
```

This demonstrates - against real, already-produced Task 2.8 data, not
synthetic values - that `accession`, `period_end`, `filed_date`, `sic`,
`section_id`, and `section_title` CAN be legitimately, non-fabricated
populated for the `primary` source, unlike `edgar_corpus`. Two fields
in this sample are explicitly audit-only placeholders, not a real
Phase 3 chunking result, and are labeled as such in the result JSON:

- `chunk_config_hash`: a synthetic SHA-256 (`sha256("task-2.9-primary-compatibility-audit-v1")`),
  since Task 2.9 builds no real chunking configuration to hash.
- `token_count`: an approximate whitespace-token count of the node
  text, since no real Phase 3 tokenizer pipeline exists yet.

**On `char_start`/`char_end`**: Docling's HTML backend (used by Task
2.8's parser) provides no byte/char-offset source provenance for a
structural node - only a structural locator (`self_ref`). NULL is the
correct, honest representation here as well.

Result (`results/phase_2_9_chunk_metadata_schema.json`,
`primary_compatibility`): 10/10 samples validate, all `chunk_uid`s
unique, `accession_populated`/`period_end_populated`/`filed_date_populated`/`sic_populated`
all `true`.

## Gold-evidence status unchanged

Task 2.9 promotes zero records to gold. `gold_evidence_count` remains 0
(Task 2.8's frozen result), and the evaluation-schema metric flags
`chunk_recall@10`/`chunk_mrr`'s `available_for_current_gold` remain
`false` (Task 2.5/2.6 registry, unchanged by this task).

## Determinism

`build_chunk_local_id`, `build_chunk_uid`, and
`canonical_pyarrow_schema` are pure functions of their inputs -
re-running the Phase 1 and primary-sample audits produces byte-identical
`chunk_uid`s every time (verified: the audit script and its test-suite
equivalents were run independently and agree).

## Known limitations

- Phase 1 (`edgar_corpus`) chunk records carry no `accession`,
  `period_end`, `filed_date`, `sic`, `section_id`, `section_title`,
  `char_start`, or `char_end` - none of these are recoverable from the
  frozen artifact without fabrication, so they are honestly NULL. This
  is Phase 1 missing metadata, not a Task 2.9 defect (Task 2.9's own
  prompt: "Phase 1 Missing Metadata Is Not a Failure").
- Primary-document `char_start`/`char_end` are NULL for the same
  structural reason documented in Task 2.8: Docling's HTML backend
  carries no byte/char provenance.
- The primary-document sample's `chunk_config_hash` and `token_count`
  are audit-only placeholders. A real primary-document chunking
  pipeline (Task 2.10+) must compute both from an actual chunking
  configuration and tokenizer, not reuse these placeholder values.

## Schema v2 (Task 4.2, 2026-09-13)

`company` became **nullable**. `CHUNK_SCHEMA_VERSION` incremented 1 -> 2 per
this document's own schema-evolution policy above (a nullability rule
changed).

Rationale: Task 4.1's approved full-corpus normalization policy leaves
`company` genuinely `NULL` for 65.91% of the complete 91,086-filing
EDGAR-CORPUS (no XBRL CIK->name submission match exists for that CIK - see
`project_plan/PHASE4_FULL_CORPUS_NORMALIZATION.md`). The v1 schema's
`company` non-nullable constraint was only ever satisfiable because Task
1.1's 1,500-filing dev corpus was deliberately pre-filtered to the
XBRL-aligned population (100% company coverage there, by construction) -
the full corpus has no such pre-filter.

No other field's nullability, type, or the `chunk_uid`/`chunk_local_id`
algorithms changed.

**Historical v1 data is unaffected, not silently reinterpreted**: the
frozen 162,357-row Task 1.2/2.9 dev-corpus audit and every Phase 3
ablation-table chunk (`chunk_config_hash` family rooted at
`f1dc04d4b7...`/`ba99e2f786...`) were built with `chunk_schema_version=1`
pinned as an explicit literal in their own producing code
(`scripts/run_phase3_trusted_baseline.py`'s `CHUNK_SCHEMA_VERSION = 1`,
`scripts/audit_chunk_metadata_schema.py`'s
`HISTORICAL_CHUNK_SCHEMA_VERSION = 1`) - neither reads this module's
"current" `CHUNK_SCHEMA_VERSION` default, so bumping it to 2 changes
nothing about any already-computed historical `chunk_uid`. None of that
historical data ever had a NULL `company` value in the first place, so
the widened nullability rule would not have changed its validity even if
it had been re-validated.

Task 4.2's full-corpus production chunks are the first real data to use
`chunk_schema_version=2`.

## Task 2.9 / Task 2.10 boundary

Task 2.9 freezes what a chunk record MEANS: field set, types,
nullability, enums, `chunk_uid`/`chunk_local_id` identity algorithms,
and the offset/section/date/accession semantics above. It does not:

- Define how `chunk_config_hash` is computed from a chunking
  configuration (chunk size, overlap, tokenizer, table-serialization
  strategy, normalization version, ...) - Task 2.10's responsibility.
- Build, run, or freeze any new chunking pipeline for either source.
- Rechunk, re-embed, or re-index Phase 1's corpus.
- Chunk any Task 2.8 primary document beyond the deterministic
  10-node compatibility sample above.
- Change `gold_evidence_count` or any evaluation-metric availability
  flag.
