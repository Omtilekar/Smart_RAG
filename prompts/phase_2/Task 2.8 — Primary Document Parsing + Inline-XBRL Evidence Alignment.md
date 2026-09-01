# Task 2.8 — Primary Document Parsing + Inline-XBRL Evidence Alignment

## Phase

**Phase 2 — Make the Numbers Trustworthy**

Task 2.8 is the final planned engineering task of Phase 2.

Expected repository state before beginning:

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
  2.7 MS MARCO Harness Validation             — MUST BE COMPLETE
  2.8 Primary Document Evidence Alignment     — CURRENT
```

Historical notes must remain visible:

```text
Phase 1:
Task 1.7a citation-format compliance = 8/10

Phase 2:
50 narrative questions remain pending_review.
They are not gold.

Task 2.6 deferred:
numeric_tolerance_match
citation_grounding
faithfulness
```

Do not erase, rewrite, or silently "resolve" these historical notes.

---

# 0. HARD PRECONDITION — VERIFY TASK 2.7 FIRST

Do not trust the task prompt or an externally supplied Progress copy.

Inspect the actual repository.

Read:

```text
Progress.md
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE2_MSMARCO_HARNESS.md
results/phase_2_7_msmarco_harness.json
```

if those files exist.

Also inspect:

```bash
git status --short
git log --oneline --decorate -20
```

Task 2.8 may begin only if the actual repository establishes that:

```text
Task 2.7 MS MARCO Harness Validation = COMPLETE
```

and its required tests/regression gates passed.

If Task 2.7 is:

```text
NEXT
IN PROGRESS
FAIL
BLOCKED
```

or its result is absent/ambiguous:

```text
STOP.
```

Report:

```text
TASK 2.8 NOT STARTED
Reason: Task 2.7 completion could not be verified.
```

Do not implement Task 2.7 inside this task.

---

# 1. Read the Authoritative Task 2.8 Contract

Before changing code, read in this order:

1. `project_plan/PROJECT_EXECUTION.md`
2. `project_plan/REVIEW_RESOLUTIONS.md`
3. `DATA_READINESS_REPORT.md`
4. `project_plan/PROJECT_SPEC.md`
5. `project_plan/PHASE2_TRUTH_CONTRACT.md`
6. `project_plan/PHASE2_TAG_REGISTRY.md`
7. `project_plan/PHASE2_EVALUATION_DATASET.md`
8. `project_plan/PHASE2_DEV_TEST_SPLIT.md`
9. `project_plan/PHASE2_EVALUATION_SCHEMA.md`
10. `project_plan/PHASE2_METRIC_TESTS.md`
11. Task 2.7 documentation
12. `project_plan/REPOSITORY_STRUCTURE.md`
13. `Progress.md`

Inspect the existing implementations:

```text
src/eval/truth_contract.py
src/eval/tag_registry.py
src/eval/evaluation_dataset.py
src/eval/evaluation_schema.py
src/eval/eval_store.py
src/eval/metrics.py

src/normalize/
src/chunk/
src/storage.py
src/config.py
```

and any existing parser package.

The exact Task 2.8 section of `PROJECT_EXECUTION.md` is authoritative.

If its scope materially differs from this prompt:

```text
PROJECT_EXECUTION.md WINS.
```

Document the difference in `Progress.md`.

Do not silently broaden the task.

---

# 2. Objective

Implement the project's trustworthy primary-document evidence layer.

Task 2.8 has two tightly connected responsibilities:

```text
A. Parse the 990 raw primary 10-K HTML filings
   while preserving document structure and tables.

B. Align inline-XBRL facts back to deterministic
   parsed structural units/chunks so the project can
   obtain real chunk-level evidence labels.
```

Conceptually:

```text
raw primary 10-K HTML
        |
        +-------------------------------+
        |                               |
        v                               v
structural parser                 inline-XBRL extractor
        |                               |
        v                               v
paragraphs / headings / tables     ix facts + contexts + units
        |                               |
        +---------------+---------------+
                        |
                        v
             deterministic alignment
                        |
                        v
           chunk-level evidence labels
                        |
                        v
            retrieval/eval gold layer
```

The most important result is NOT attractive Markdown.

The most important result is:

```text
For a trustworthy eligible XBRL fact,
we can identify exactly which parsed evidence unit
in the original primary filing contains that fact.
```

---

# 3. Why Task 2.8 Exists

EDGAR-CORPUS is useful for large-scale narrative retrieval but its structured tables were stripped.

The primary 10-K documents are different:

```text
990 primary 10-K HTML filings
tables intact
inline XBRL intact
```

They have three jobs:

```text
1. Table extraction/retrieval
2. Chunk-level evidence labels
3. Real HTML / multi-format ingestion validation
```

The key Phase 2 contribution is:

```text
inline XBRL
    ↓
exact source evidence
    ↓
chunk-level gold
```

This unlocks trustworthy evaluation of chunk-level retrieval later.

---

# 4. Scope Discipline

Task 2.8 IS about:

```text
HTML parsing
document structure
section structure
table preservation
inline-XBRL extraction
XBRL contexts
XBRL units
fact normalization
source-element identity
fact-to-evidence alignment
chunk/evidence labels
alignment quality validation
reproducible derived artifacts
```

Task 2.8 is NOT about:

```text
BM25 implementation
hybrid retrieval
reranking
CRAG
router
metadata filtering
full-corpus embedding
embedding-model comparison
table retrieval optimization
generation-model comparison
guardrails
FastAPI
deployment
graph retrieval
Phase 3 tuning
```

Do not begin Phase 3.

---

# 5. Frozen Source Safety

Treat all source data as immutable.

Especially:

```text
data/raw/primary/
data/xbrl.duckdb
data/edgar_corpus/
data/msmarco/
```

Task 2.8 must never modify those files.

Derived primary-document data belongs under the project's artifact/derived-data convention.

Prefer something like:

```text
artifacts/primary_docs/
```

rather than writing generated data back into:

```text
data/
```

unless the authoritative storage abstraction explicitly defines another safe generated-artifact root.

---

# 6. Establish Initial State

Before modification:

```bash
git branch
git status --short
git log --oneline --decorate -20

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

primary source file count
primary source total size

Phase 2.7 status
Phase 2.7 result hash if applicable

truth_contract_version/hash
tag_registry_version/hash
evaluation_schema_version/hash

full-test baseline
portable-test baseline

official SEC TEST evaluations consumed
```

Do not copy these from old documentation.

Measure them from the repository.

---

# 7. Independently Verify the Primary Corpus

Enumerate:

```text
data/raw/primary/{cik}/{accession}.htm
```

Verify:

```text
file count
unique CIK count
unique accession count
zero duplicate canonical paths
zero zero-byte files
size distribution
total bytes
```

Expected historical count:

```text
990 primary filings
```

but do not force it.

If the real corpus differs unexpectedly:

```text
STOP and investigate.
```

---

# 8. Verify Source Identity Before Parsing

Every source filing must get a deterministic source record.

At minimum:

```text
source_document_id
cik
accession
source_path
source_sha256
source_size_bytes
```

Do not use filesystem modification time as identity.

The canonical identity should be based on immutable source fields.

For example conceptually:

```text
primary:{cik}:{accession}
```

Do not invent a second incompatible document-ID scheme if the repository already has one.

---

# 9. Parser Architecture

Primary-document parsing should have its own clear package boundary.

Prefer the existing designated package if one already exists.

Otherwise likely:

```text
src/parse/
    __init__.py
    primary_html.py
```

Do NOT put parsing logic inside:

```text
scripts/
tests/
src/eval/
src/retrieval/
```

Scripts should orchestrate.

Library code should implement.

---

# 10. Docling Contract

The project design specifies:

```text
Primary HTML
    ↓
Docling
    ↓
structured Markdown / document representation
```

Use Docling according to the exact repository plan.

However:

```text
Docling output is NOT the authoritative source
for inline-XBRL identity.
```

The raw HTML is.

Do not depend on Docling preserving:

```text
ix:nonFraction
ix:nonNumeric
contextRef
unitRef
decimals
scale
sign
namespace-qualified concept names
```

through Markdown conversion.

Therefore use a dual-path design:

```text
raw HTML
 ├─ structural/document parser
 └─ raw inline-XBRL DOM extractor
```

then align them explicitly.

---

# 11. Do Not Use OCR

These are HTML documents.

Do not:

```text
render pages
OCR screenshots
OCR tables
OCR text
```

for normal parsing.

HTML/DOM structure is more precise than OCR.

Only use a fallback if the authoritative task explicitly documents a genuinely non-HTML edge case.

---

# 12. Structural Representation

Before immediately flattening a filing to plain Markdown, preserve a deterministic structural representation.

Each structural node should contain appropriate fields such as:

```text
document_id
node_id
parent_node_id

node_type
section_id
section_title

source_order
source_locator

text

content_type
table_id
```

Possible node types:

```text
heading
paragraph
list
table
table_row
other
```

Do not depend only on generated Markdown line numbers as source identity.

Markdown line numbers can change when parser formatting changes.

---

# 13. Stable Node IDs

Node IDs must be deterministic.

Running the same parser with the same configuration on the same source must reproduce the same IDs.

Use stable inputs such as:

```text
document_id
structural position
node type
canonical content/config
```

Do not use:

```python
uuid.uuid4()
```

or:

```python
hash()
```

for persistent identity.

Python's built-in `hash()` is process salted and is not reproducible.

---

# 14. Source Locators

Each parsed node should preserve enough information to trace back to the original HTML.

Use a deterministic locator appropriate for the DOM/parser.

Possible examples:

```text
DOM XPath
element path
source element index
HTML byte/character span
stable structural locator
```

Do not claim an "exact source locator" if the parser cannot reproduce it.

Document the locator semantics honestly.

---

# 15. Section Detection

Preserve SEC filing structure where reliably detectable.

Examples:

```text
Item 1
Item 1A
Item 7
Item 7A
Item 8
...
```

Use canonical section identifiers when possible.

Do not infer a section when the source evidence is ambiguous.

Prefer:

```text
section_id = null
```

or explicit uncertainty to assigning the wrong Item.

---

# 16. Tables Must Survive Parsing

A successful text extraction that destroys tables is a Task 2.8 failure.

For every parsed document, preserve:

```text
table identity
row order
cell content
header relationships where recoverable
table order within document
surrounding structural context
```

Validate against raw HTML.

Do not treat:

```text
all table cells concatenated into one paragraph
```

as table preservation.

---

# 17. Table Atomicity

The approved table semantics require:

```text
A TABLE IS AN ATOMIC STRUCTURAL UNIT.
```

Do not split tables arbitrarily at the parser stage.

Later chunking may split a large table by row groups, but never:

```text
mid-row
mid-cell
without headers
```

---

# 18. Small Table Semantics

If the existing Task 2.8 contract owns table chunk construction and a table fits the chunk budget:

```text
one table chunk
content_type = "table"
```

Include preceding context where required by the approved table contract.

Do not add arbitrary prose into the raw table representation.

---

# 19. Large Table Semantics

If Task 2.8 owns table chunk construction:

split large tables:

```text
by row groups
```

and repeat headers in each part.

All parts must share:

```text
table_id
```

and have deterministic:

```text
table_part
```

ordering.

A large table must be reconstructable from its parts.

---

# 20. Table Context Prefix

Where the approved table contract requires it, preserve contextual identity such as:

```text
{company}
{form_type}
{fiscal_year}
{section_title}
{table_caption}
```

This contextual metadata should be stored separately from the raw table data where practical.

Do not destroy provenance by merging metadata irreversibly into the table text.

---

# 21. Table Serialization

Do not perform a Phase 3 table-format ablation during Task 2.8.

If the roadmap defines a canonical baseline table serialization for Task 2.8:

use it.

If not:

select the explicitly approved baseline from the planning documents and record the choice.

Possible later ablation formats include:

```text
Markdown
HTML
CSV
key-value rows
```

Task 2.8 needs one reproducible baseline, not a model-selection experiment.

---

# 22. Table Summaries

The design documents discuss later `table_summary` chunks.

Do not use an LLM-generated table summary as ground truth.

If Task 2.8 does not explicitly require summary generation:

```text
DEFER IT.
```

If it does explicitly require them:

store summaries as:

```text
derived retrieval metadata
```

not:

```text
source evidence
```

and preserve the raw table as the authoritative evidence.

Never align XBRL facts to an LLM summary instead of the actual table/cell.

---

# 23. Inline-XBRL Extraction

Parse raw HTML for inline-XBRL elements.

At minimum inspect/support relevant elements such as:

```text
ix:nonFraction
ix:nonNumeric
```

and supporting context/unit structures.

Do not assume tag names are case-sensitive or namespace prefixes are identical across every filing.

Use namespace-aware DOM parsing.

---

# 24. Preserve Raw Inline-XBRL Attributes

For each extracted inline fact preserve enough source information to reconstruct its meaning.

Relevant fields may include:

```text
concept QName
local concept name
namespace
contextRef
unitRef
decimals
precision where present
scale
sign
format
id
continuedAt
raw displayed text
source locator
```

Do not normalize first and discard the original attributes.

Store:

```text
raw
+
normalized
```

where appropriate.

---

# 25. Continuations

Inline XBRL can use continuation elements.

Handle:

```text
continuedAt
ix:continuation
```

correctly where present.

Do not treat only the first visible fragment as the complete value.

Create tests for continuation handling if encountered in the corpus.

---

# 26. Context Extraction

Parse all referenced contexts needed by inline facts.

For each context preserve relevant fields such as:

```text
context_id
entity identifier
instant
start_date
end_date
dimensions / segment information
```

Do not infer fiscal period solely from nearby visible prose when an XBRL context exists.

---

# 27. Unit Extraction

Parse referenced XBRL units.

Preserve:

```text
unit_id
measure(s)
numerator/denominator where applicable
```

Map units to the project's canonical truth-contract representation only through explicit rules.

Do not convert currencies.

---

# 28. Numeric Normalization

For `ix:nonFraction`:

correctly handle relevant presentation attributes such as:

```text
sign
scale
format
decimals
```

The visible number:

```text
1,234
```

may not necessarily mean canonical:

```text
1234
```

if scale/sign formatting applies.

Write hand-constructed unit tests for all normalization behavior used.

Do not use floating-point string hacks where exact decimal arithmetic is safer.

---

# 29. Text Facts

Do not force every inline-XBRL item through numeric normalization.

`ix:nonNumeric` values require separate handling.

Task 2.8's chunk-level evidence layer can preserve them even if current Phase 2 gold focuses primarily on numeric supported tags.

Keep:

```text
extracted
```

distinct from:

```text
eligible_for_current_gold
```

---

# 30. Extracted ≠ Gold

This distinction is critical.

A fact appearing inline in a document does NOT automatically make it valid Phase 2 gold.

Maintain three states conceptually:

```text
EXTRACTED
TRUTH-CONTRACT ELIGIBLE
EVIDENCE-ALIGNED GOLD
```

Do not collapse them.

---

# 31. Reuse the Task 2.1 Truth Contract

Do not reimplement XBRL eligibility inside Task 2.8.

Use:

```text
src/eval/truth_contract.py
```

for the authoritative truth rules.

Eligibility decisions must continue to cover the existing policy around:

```text
form
year/window
coreg
segments
period
supported semantics
canonical row selection
```

as defined there.

Task 2.8 may add source evidence.

It must not create a competing truth contract.

---

# 32. Reuse the Task 2.2 Tag Registry

Do not hard-code another list of:

```text
Assets
Revenues
NetIncomeLoss
EPS
...
```

inside the parser/alignment implementation.

Use:

```text
src/eval/tag_registry.py
configs/eval_tags.yaml
```

or the current authoritative interfaces.

A fact can be:

```text
valid XBRL
```

but still:

```text
outside current supported eval registry
```

Preserve that distinction.

---

# 33. Primary Docs Are a Separate Evidence Population

The primary filings are not automatically members of the existing 2016–2020 EDGAR-CORPUS DEV/TEST dataset.

Do NOT:

```text
rewrite Task 2.3 questions
replace Task 2.4 DEV/TEST
inject 2021–2024 primary docs into the frozen SEC split
change existing question IDs
```

Create a separate:

```text
primary-document evidence dataset / manifest
```

unless the authoritative Task 2.8 contract explicitly specifies integration.

This avoids contaminating the already frozen evaluation split.

---

# 34. Match by Accession First

Evidence alignment must never search globally for:

```text
same number
same tag
same company
```

and call that a match.

The filing identity must be constrained first.

Prefer:

```text
accession
```

as the strongest filing-level key.

Then use:

```text
concept
context/period
unit
canonical value
dimensions
```

as required.

Cross-accession matches are invalid for source-evidence alignment.

---

# 35. Fact Identity

Define a documented canonical identity for candidate fact alignment.

It may involve fields such as:

```text
adsh/accession
tag
ddate
qtrs
uom
value
coreg
segments
```

according to the Task 2.1 truth contract.

Do not invent a looser identity just to increase alignment coverage.

---

# 36. Inline Context → Truth Contract Period

Do not match only:

```text
tag + value
```

because the same value can appear multiple times.

Convert inline context periods into the same semantic fields used by the truth contract.

Examples:

```text
instant
duration
fiscal period
qtrs
ddate
```

Any mapping must be explicit and unit-tested.

---

# 37. Dimensions

If an inline fact contains dimensional/segment context:

preserve it.

Do not silently strip dimensions before determining eligibility.

If the Task 2.1 contract excludes segmented facts from current gold:

mark:

```text
extracted = true
eligible_for_gold = false
```

rather than pretending the dimension never existed.

---

# 38. Canonical Value Verification

Before promoting an inline fact to evidence gold:

verify its normalized value against the authoritative XBRL truth row.

Required match dimensions should include all fields defined by the truth contract.

Do not accept a fact merely because the visible value is "close".

No tolerance matching unless a tolerance policy has actually been frozen.

---

# 39. Evidence Unit

Define what counts as one evidence unit.

Use the smallest stable structural unit that still preserves enough meaning.

Examples:

```text
paragraph node
table node
table row-group part
```

Do not define evidence as an arbitrary character span if the retrieval system cannot retrieve that same unit later.

Evidence labels and retrieval units must eventually be compatible.

---

# 40. Alignment Target

For every eligible aligned fact produce something conceptually like:

```text
fact_id
    ↓
source document
    ↓
section
    ↓
structural node/table
    ↓
future chunk/evidence ID
```

The label must be deterministic and auditable.

---

# 41. Evidence Label Schema

Create a versioned schema.

Potential fields:

```text
evidence_schema_version
evidence_id

document_id
cik
accession
fiscal_year

source_sha256
source_locator

section_id
section_title

node_id
content_type

table_id
table_part

concept_name
concept_namespace

context_ref
unit_ref

raw_display_value
normalized_value
canonical_unit

truth_fact_identity

alignment_method
alignment_status

truth_contract_version
truth_contract_hash
tag_registry_version
tag_registry_hash

parser_config_hash
```

Use exact fields appropriate to the implementation.

Do not add fields simply to imitate this list.

---

# 42. Alignment Status Must Be Explicit

Use explicit statuses rather than a fabricated confidence probability.

For example:

```text
exact
ambiguous
unmatched
ineligible
unsupported_tag
parse_error
```

If probabilistic alignment is not used:

do not invent:

```text
confidence = 0.97
```

because it looks scientific.

---

# 43. Gold Promotion Rule

Only:

```text
exactly aligned
+
truth-contract eligible
+
supported tag
```

records should become current chunk-level evidence gold.

Ambiguous matches remain diagnostic records.

Never resolve ambiguity by arbitrary first-match selection.

---

# 44. Multiple Visible Occurrences

The same XBRL fact may appear more than once in a filing.

Example:

```text
summary table
financial statement
footnote
```

Do not assume exactly one source location.

Your evidence schema must deliberately support either:

```text
one fact → multiple valid evidence nodes
```

or the authoritative project's chosen primary-evidence policy.

Do not silently discard duplicate valid evidence occurrences.

---

# 45. Fact Embedded in Table Cell

This is one of the most important cases.

For inline-XBRL facts inside a table:

the evidence label must point to:

```text
table/table-part containing the fact
```

and, if feasible:

```text
row/cell locator
```

Do not align only to the entire document.

That would not create meaningful chunk-level gold.

---

# 46. Fact Embedded in Narrative Text

For facts embedded in prose:

align to the containing:

```text
paragraph / semantic node
```

and preserve its section.

Do not merge unrelated neighboring paragraphs simply to make alignment easier.

---

# 47. Parser Config

Create a versioned configuration, likely:

```text
configs/phase_2_8_primary_evidence.json
```

Include result-affecting settings such as:

```text
parser name/version
HTML parser
Docling settings
table serialization
section-detection policy
node-ID version
inline-XBRL extraction version
numeric-normalization version
alignment version
truth-contract identity
tag-registry identity
```

Calculate:

```text
parser_config_hash
```

deterministically.

Exclude runtime-only information.

---

# 48. Reproducibility

Running Task 2.8 twice on the same source + config must produce:

```text
same source-document identities
same structural node IDs
same inline-fact IDs
same evidence IDs
same gold labels
same canonical result hash
```

Order output canonically before hashing.

Do not hash arbitrary dictionary/set iteration order.

---

# 49. Artifact Layout

Prefer an organization such as:

```text
artifacts/primary_docs/
    parsed/
    manifests/
    inline_xbrl/
    evidence/
    failures/
```

Exact layout should follow repository conventions.

Large generated artifacts must remain Git-ignored.

Do not create millions of tiny tracked files.

---

# 50. Parsed Document Format

If a persisted normalized Markdown layer is owned by Task 2.8, preserve metadata such as:

```yaml
cik:
company:
form_type:
fiscal_year:
accession:
source: primary
```

and structural sections.

However:

```text
Markdown is a derived representation.
```

The raw HTML remains authoritative for inline-XBRL source evidence.

---

# 51. Avoid Re-parsing for Every Experiment

Persist parsed outputs so later table/chunking experiments do not re-run expensive parsing.

Derived parser artifacts should be versioned by:

```text
source hash
+
parser config hash
```

If either changes:

rebuild.

Otherwise:

reuse.

---

# 52. Resume Support

Task 2.8 processes 990 relatively large HTML filings.

The run must be resumable.

For each source document track:

```text
pending
success
failed
```

and config/source identity.

A restart must not blindly parse all 990 again.

Validate existing output before reuse.

---

# 53. Atomic Writes

Write derived artifacts atomically.

Use:

```text
temporary file
    ↓
validation
    ↓
atomic rename
```

where practical.

A crash must not leave a truncated artifact that a later run mistakes for success.

---

# 54. Failure Manifest

Every failed source document must be recorded.

At minimum:

```text
document_id
cik
accession
source_path
error_type
short error
stage
```

No source document may disappear silently from the denominator.

---

# 55. Pilot First

Do NOT immediately run all 990 filings.

Create a deterministic pilot subset.

Include diversity such as:

```text
small document
large document
table-heavy document
many inline facts
few inline facts
multiple contexts
different units
narrative inline facts
numeric table facts
```

Prefer 10–30 filings depending on runtime.

Record selection method.

Do not cherry-pick only easy filings.

---

# 56. Pilot Exit Gate

Before the full run verify:

```text
source IDs stable
Docling parse succeeds
sections preserved
tables preserved
inline facts extracted
contexts resolved
units resolved
numeric normalization works
fact-to-XBRL matching works
fact-to-node alignment works
evidence IDs reproducible
artifact resume works
```

If pilot alignment is fundamentally unreliable:

```text
STOP.
```

Do not scale a broken method to 990 files.

---

# 57. Manual Pilot Validation

Manually inspect a deterministic sample.

Include:

```text
narrative fact examples
table fact examples
EPS/share-unit examples if present
negative values
scaled values
multiple-period tables
```

For each verify:

```text
raw HTML fact
visible source text/cell
parsed structural node
normalized fact
matched XBRL truth row
generated evidence label
```

Record examples in documentation.

---

# 58. No Cherry-Picking

Choose manual samples deterministically.

For example:

```text
first N exact alignments by evidence_id
first N table alignments
first N narrative alignments
first N unmatched records
```

Do not select only successful attractive examples.

---

# 59. Full Run

Only after pilot PASS:

process the full primary corpus.

Report:

```text
source documents
parsed successfully
parse failures

tables extracted
inline facts extracted

contexts extracted
units extracted

supported-tag facts
truth-contract eligible facts

exact alignments
ambiguous alignments
unmatched facts
ineligible facts

gold evidence labels
```

Do not hide denominators.

---

# 60. Coverage Metrics

Calculate useful alignment coverage separately.

Examples:

```text
parse_coverage =
parsed_documents / source_documents

fact_alignment_coverage =
exact_aligned_eligible_facts / eligible_inline_facts

document_evidence_coverage =
documents_with_at_least_one_gold_evidence /
parsed_documents
```

Do not combine these into one vague "accuracy" number.

---

# 61. Coverage by Content Type

Report separately for:

```text
table
narrative
other
```

if available.

A high overall alignment rate can conceal poor table alignment.

---

# 62. Coverage by Tag

Report exact alignment coverage for every supported evaluation tag represented in primary docs.

At minimum:

```text
tag
eligible inline facts
exact aligned
ambiguous
unmatched
coverage
```

This helps detect one broken concept family.

---

# 63. Coverage by Unit

Where useful, diagnose:

```text
USD
shares
USD/shares
pure
other supported units
```

A parser can appear correct overall while failing EPS because compound units were mishandled.

---

# 64. Alignment Ambiguity Audit

For ambiguous cases, classify causes.

Examples:

```text
same fact displayed twice
duplicate candidate XBRL rows
period ambiguity
unit ambiguity
parser lost source position
table spans/merged cells
continuation chain issue
unsupported transform
```

Do not force ambiguous records into gold.

---

# 65. Unmatched Audit

Inspect deterministic unmatched samples.

Determine whether failures come from:

```text
truth-contract filtering
unsupported tags
parser loss
context mapping
unit mapping
transform normalization
source/XBRL discrepancy
```

Do not simply report a percentage.

Task 2.8 is specifically about understanding these mismatches.

---

# 66. Table Preservation Test

For a deterministic source sample:

compare raw HTML table counts with parsed tables.

Do not require exact 1:1 count blindly if the parser intentionally merges/splits tables.

Instead establish a documented mapping and verify content preservation.

Manually validate several table-heavy filings.

---

# 67. Inline-XBRL Preservation Test

For a deterministic sample:

count source inline-XBRL facts directly from raw HTML.

Compare to the extractor output.

Expected:

```text
no silent loss
```

If supported ix elements are omitted:

identify exactly why.

---

# 68. Numeric Normalization Hand Tests

Before trusting real data, add hand-built HTML fixtures covering:

```text
plain integer
comma-separated number
decimal
negative/sign
scale
zero
shares
USD
USD/share if relevant
nil/missing value if present
continuation if relevant
```

Expected canonical results must be manually specified.

Never generate expected outputs using the implementation under test.

---

# 69. HTML Fixture Tests

Create small local HTML fixtures representing:

```text
paragraph inline fact
table-cell inline fact
multiple contexts
multiple units
same fact displayed twice
nested formatting tags
continuation
malformed but recoverable HTML
```

No network required.

---

# 70. Parser Tests Must Be Portable

Ordinary unit tests must NOT process:

```text
4.48 GB
990 filings
```

Use small fixture HTML.

Tests requiring real primary data should use:

```text
local_data
```

or the existing repository convention.

---

# 71. Full Parse Is Not CI

The 990-document parse should require an explicit command.

For example:

```bash
python scripts/build_primary_evidence.py --dry-run
python scripts/build_primary_evidence.py --pilot
python scripts/build_primary_evidence.py --full
```

Use repository conventions if another CLI pattern already exists.

Do not trigger the full parse from normal `pytest`.

---

# 72. Dry Run

`--dry-run` should inspect without parsing everything.

Print:

```text
source count
source bytes
parser configuration
parser version
output root
available disk
truth-contract identity
tag-registry identity
expected artifact layout
existing resumable outputs
```

---

# 73. Full-Run Resume

Provide something such as:

```text
--resume
```

or automatic safe resume.

Reuse requires matching:

```text
source_sha256
parser_config_hash
evidence_schema_version
```

Never reuse output solely because a filename exists.

---

# 74. No Network Requirement

The primary filings are already downloaded.

Task 2.8 should not call:

```text
SEC website
Hugging Face datasets API
OpenRouter
OpenAI
Anthropic
```

for source data.

All required evidence comes from local files.

---

# 75. GPU Policy

HTML parsing and inline-XBRL extraction should not require GPU.

Do not introduce GPU dependence merely because one is available.

If Docling unexpectedly invokes a model requiring accelerator resources:

document it explicitly and verify deterministic behavior.

OCR is not justified for normal HTML.

---

# 76. LLM Policy

Ground-truth evidence alignment must require:

```text
0 LLM calls
```

Do not ask an LLM:

```text
"Which chunk contains this fact?"
```

That would defeat the purpose of deterministic evidence labels.

LLM-generated table summaries, if ever required, must remain separate derived retrieval artifacts and never determine gold evidence.

---

# 77. Existing Task 2.3 Dataset Must Stay Frozen

Do not modify:

```text
results/phase_2_3_evaluation_dataset.json
```

or its question IDs/gold.

Primary evidence labels are a new linked/subset artifact.

If later work wants to add evidence IDs to existing questions:

that must follow the explicit versioning/migration policy.

Do not silently rewrite the dataset.

---

# 78. Existing Task 2.4 Split Must Stay Frozen

Do not regenerate:

```text
DEV
TEST
CI
```

Task 2.8 primary documents are a separate evidence population unless explicitly specified otherwise.

Protected SEC TEST access count must remain:

```text
0 / 3
```

unless Task 2.8's authoritative roadmap explicitly requires a TEST evaluation—which should not be necessary for parsing/alignment.

---

# 79. Chunk Metrics Availability

Task 2.6 currently has real implementations for:

```text
chunk_recall@10
chunk_mrr
```

but no current chunk-level gold was available.

Task 2.8 may change that reality.

After genuine chunk-level gold exists:

inspect the Task 2.5 metric-registry semantics.

Only if justified update:

```text
available_for_current_gold
```

for chunk-level metrics.

Do NOT change the flag simply because Task 2.8 ran.

It changes only if the produced evidence labels satisfy the registry's definition of usable current gold.

---

# 80. Citation Grounding

Task 2.6 deferred:

```text
citation_grounding
```

because no evidence-level gold existed.

Task 2.8 may provide the missing GOLD prerequisite.

That does NOT automatically mean:

```text
citation_grounding implemented = true
```

If no metric implementation exists:

keep:

```text
implemented = false
```

even if:

```text
gold availability = true
```

if that matches the registry semantics.

Do not implement a new grounding judge unless Task 2.8 explicitly owns it.

---

# 81. Faithfulness

Do not implement:

```text
faithfulness
```

during Task 2.8.

Its LLM-judge dependency remains separate.

Chunk evidence labels do not magically implement faithfulness scoring.

---

# 82. Numeric Tolerance

Do not introduce a numeric tolerance policy here.

Fact alignment should use the authoritative canonical value semantics.

Task 2.6 explicitly deferred numeric tolerance because no policy was frozen.

Leave that unchanged.

---

# 83. Evidence Dataset Artifact

Create a tracked compact summary such as:

```text
results/phase_2_8_primary_evidence_summary.json
```

Large evidence records should remain under ignored artifacts.

Optionally create a small tracked manifest/index if project conventions allow.

Summary should contain:

```text
evidence_schema_version
parser_config_hash

source_document_count
parsed_document_count
parse_failure_count

table_count
inline_fact_count

eligible_fact_count
exact_alignment_count
ambiguous_count
unmatched_count
gold_evidence_count

coverage metrics

truth_contract_version/hash
tag_registry_version/hash

large_artifact_sha256
canonical evidence hash
```

---

# 84. Documentation

Create:

```text
project_plan/PHASE2_PRIMARY_EVIDENCE.md
```

Document:

- objective;
- primary-document role;
- source counts;
- parser choice;
- raw HTML vs parsed representation;
- structural node schema;
- table semantics;
- inline-XBRL extraction;
- contexts;
- units;
- numeric normalization;
- truth-contract reuse;
- tag-registry reuse;
- fact identity;
- alignment algorithm;
- alignment statuses;
- evidence schema;
- pilot;
- full-run counts;
- coverage;
- table coverage;
- tag coverage;
- unmatched/ambiguous analysis;
- deterministic validation;
- known limitations;
- exact reproduction commands;
- artifact locations/hashes.

---

# 85. Repository Structure Documentation

Update:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

narrowly.

Document any new:

```text
src/parse/
src/eval/...alignment...
scripts/
configs/
results/
artifact layout
```

Do not rewrite unrelated sections.

---

# 86. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.8 Primary Document Parsing + Inline-XBRL Evidence Alignment
```

Include:

```text
Objective
Precondition / Task 2.7 Verification
Initial State
Authoritative Sources
Frozen Source Verification
Parser Design
Parser Configuration
Structural Schema
Table Handling
Inline-XBRL Extraction
Context / Unit Handling
Numeric Normalization
Truth-Contract Integration
Tag-Registry Integration
Evidence Schema
Alignment Algorithm
Pilot
Pilot Manual Audit
Full Run
Coverage
Table Coverage
Tag Coverage
Ambiguous Cases
Unmatched Cases
Reproducibility
Metric Registry Impact
TEST Discipline
Regression Gates
Tests
Files Created/Modified
Git
Result
Phase 2 Exit Review
Phase Status
```

Append only.

Do not rewrite historical entries.

---

# 87. Task 2.7 Regression Gate

Re-run Task 2.7's lightweight tests/harness regression checks.

Do not automatically rebuild a full 8.8M-passage MS MARCO index unless its own reproducibility contract explicitly requires it.

Verify Task 2.8 did not alter:

```text
MS MARCO source data
benchmark config
benchmark result summary
benchmark metric semantics
```

---

# 88. Task 2.6 Regression Gate

Run:

```text
tests/test_metrics.py
tests/test_evaluation_schema.py
tests/test_eval_store.py
```

Verify all metric arithmetic still passes.

Any registry availability update must be explicitly justified.

---

# 89. Task 2.5 Regression Gate

Verify:

```text
evaluation schema initializes
eval store works
test_access_log unchanged
```

If metric registry metadata legitimately changes because chunk gold now exists:

regenerate the Task 2.5 schema snapshot according to its established policy.

Record before/after:

```text
evaluation_schema_version
evaluation_schema_hash
```

Do not allow unexplained schema drift.

---

# 90. Task 2.4 Regression Gate

Without loading protected TEST content verify:

```text
DEV = 1,932
TEST = 828
CI = 200

DEV/TEST company overlap = 0

pending narrative:
35 DEV
15 TEST

official TEST evaluations = 0 / 3
```

Do not regenerate the split.

---

# 91. Tasks 2.1–2.3 Regression Gate

Verify no semantic changes to:

```text
truth contract
tag registry
evaluation question dataset
question IDs
gold values
gold behavior
```

Task 2.8 consumes those contracts.

It does not redefine them.

---

# 92. Phase 1 Regression Gate

Do not alter:

```text
Phase 1 development corpus
normalizer
fixed-window chunker
BGE embeddings
SEC LanceDB baseline index
baseline retriever
generation layer
citation validator
Phase 1 metrics/results
```

Primary-document parsing is a new source path.

---

# 93. Frozen Data Verification

Before and after full Task 2.8 execution verify critical frozen source identity.

At minimum:

```text
data/raw/primary/ source hashes/count unchanged
data/xbrl.duckdb unchanged
data/edgar_corpus unchanged
data/msmarco unchanged
protected TEST artifact unchanged
```

Do not hash 26 GB repeatedly if the repository has a cheaper established frozen-data invariant.

Use the existing project convention.

---

# 94. Tests

Add comprehensive tests for the new implementation.

Likely:

```text
tests/test_primary_html_parser.py
tests/test_inline_xbrl.py
tests/test_primary_evidence_alignment.py
```

or the repository-equivalent layout.

Cover:

```text
source identity
stable node IDs
sections
tables
table IDs
table row order
inline numeric facts
inline text facts
contexts
units
sign
scale
decimals
continuations
numeric normalization
truth-contract filtering
registry filtering
fact identity
exact alignment
ambiguous alignment
unmatched alignment
multiple visible occurrences
table-cell evidence
paragraph evidence
evidence ID stability
config hashing
resume safety
atomic-output safety
```

Use hand-constructed expected results.

---

# 95. Full Test Gate

After Task 2.8:

```text
doctor = PASS
portable suite = PASS
full suite = PASS
```

No existing test may be removed or xfailed simply to make the suite green.

---

# 96. Performance Reporting

Task 2.8 is correctness-first.

Still record:

```text
pilot runtime
full parse runtime
documents/sec
peak memory if practical
artifact size
```

Do not call these production serving benchmarks.

Parsing is an offline build operation.

---

# 97. Resource Safety

Before the full 990-document run print:

```text
source size
free disk
estimated derived artifact size
existing resumable artifacts
```

If actual required storage is unexpectedly >2× the reasonable preflight estimate:

```text
STOP and report.
```

Follow the project's existing resource-safety convention.

---

# 98. Secret / Personal Data Safety

No credentials should be needed.

Before commit scan for:

```text
.env
API keys
tokens
personal SEC_USER_AGENT values
absolute personal machine paths
```

Do not commit local user paths.

---

# 99. Git Safety

Before commit:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Large derived artifacts must not be staged.

Specifically verify no:

```text
data/raw/primary/
artifacts/primary_docs/
*.parquet large evidence outputs
*.duckdb
.venv/
model cache
.env
credentials
```

would be committed.

Tracked output should be limited to:

```text
source
tests
configs
small result summaries
documentation
Progress.md
```

---

# 100. Commit

After Task 2.8 passes all gates create one coherent commit.

Suggested message:

```text
Add primary document evidence alignment
```

or:

```text
Parse primary filings and align XBRL evidence
```

Choose the message that best reflects the actual implementation.

Do not push if no remote exists.

---

# 101. Phase 2 Exit Review

Because Task 2.8 is the final planned Phase 2 task:

perform a dedicated Phase 2 exit review after Task 2.8 itself passes.

Verify:

```text
2.1 XBRL Truth Contract
2.2 Supported Tag Registry
2.3 Evaluation Dataset
2.4 DEV/TEST Split
2.5 Evaluation Schema
2.6 Metric Unit Tests
2.7 MS MARCO Harness Validation
2.8 Primary Evidence Alignment
```

for each print:

```text
COMPLETE
COMPLETE WITH NOTE
COMPLETE WITH WARN
FAIL
BLOCKED
```

Do not flatten historical notes into plain COMPLETE.

---

# 102. Phase 2 Exit Criteria

Phase 2 can close only if the repository establishes that:

```text
[ ] truth contract is frozen and tested
[ ] supported tag registry is frozen and tested
[ ] evaluation dataset is deterministic
[ ] pending narrative rows remain honestly marked non-gold

[ ] DEV/TEST split is frozen and company-disjoint
[ ] TEST protections still work
[ ] TEST evaluation budget is intact

[ ] evaluation schema is valid
[ ] metric definitions are versioned

[ ] core deterministic metrics have hand-verified tests

[ ] MS MARCO harness validation passed

[ ] primary HTML parsing is reproducible
[ ] tables survive parsing
[ ] inline XBRL extraction is deterministic
[ ] eligible facts can be aligned to source evidence
[ ] chunk/evidence labels are versioned and auditable

[ ] all regression tests pass
[ ] frozen source data is unchanged
```

---

# 103. Phase 2 Status

Do NOT automatically print:

```text
PHASE 2 COMPLETE
```

merely because Task 2.8 code finished.

Choose the status from evidence.

Possible outcomes:

```text
COMPLETE
COMPLETE WITH NOTE
COMPLETE WITH WARN
INCOMPLETE
BLOCKED
```

Existing pending narrative questions may justify:

```text
COMPLETE WITH NOTE
```

if the roadmap permits them to remain pending.

A serious evidence-alignment limitation may justify:

```text
COMPLETE WITH WARN
```

or:

```text
INCOMPLETE
```

Use the actual exit criteria.

---

# 104. Phase Tag

Read:

```text
project_plan/GIT_CONVENTIONS.md
```

If Phase 2 legitimately passes its exit review and the convention requires a phase tag:

create the appropriate Phase 2 tag.

If:

```text
status is ambiguous
major WARN remains
exit criteria fail
```

do not invent tag semantics.

Document why no tag was created.

---

# 105. Do Not Start Phase 3

After Task 2.8 and Phase 2 exit review:

```text
STOP.
```

Do not implement:

```text
BM25
hybrid retrieval
section-aware chunking experiment
embedding model benchmark
reranker
CRAG
router
```

even if Phase 3 is now ready.

Only print the exact next task from `PROJECT_EXECUTION.md`.

---

# 106. Stop Conditions

STOP rather than guessing if:

### A. Task 2.7 is not verifiably complete

Do not start 2.8.

### B. Task 2.8 roadmap differs materially from this prompt

Follow `PROJECT_EXECUTION.md`.

### C. Primary source count unexpectedly differs

Investigate.

### D. Docling destroys tables or source structure

Do not scale the parser.

### E. Inline-XBRL extraction loses supported source facts

Fix before full run.

### F. Numeric normalization semantics are unclear

Do not invent them.

### G. Fact alignment requires fuzzy/global numeric matching

The method is not trustworthy enough for gold.

### H. Ambiguous matches would need arbitrary first-match selection

Keep them non-gold.

### I. A new truth rule appears necessary

Do not modify Task 2.1 casually.

Surface the conflict.

### J. A new tag/unit rule appears necessary

Do not bypass Task 2.2.

### K. Existing Task 2.3/2.4 frozen artifacts would need modification

Stop and explain why.

### L. Protected TEST access appears necessary

It should not be.

### M. LLM is required to decide evidence alignment

Stop.

Gold evidence must be deterministic.

### N. Resource requirements exceed estimate by >2×

Stop before continuing.

---

# 107. Acceptance Criteria

Task 2.8 is complete only when:

```text
PRECONDITION
[ ] Task 2.7 independently verified COMPLETE
[ ] Task 2.7 regression remains PASS

SOURCE
[ ] 990 expected primary filings independently verified or discrepancy resolved
[ ] source identities deterministic
[ ] source files remain immutable
[ ] source SHA/provenance preserved

PARSER
[ ] parser architecture documented
[ ] raw HTML remains authoritative
[ ] Docling/approved parser used according to roadmap
[ ] no OCR used for normal HTML
[ ] structural nodes deterministic
[ ] node IDs stable
[ ] source locators preserved
[ ] sections preserved where confidently detectable

TABLES
[ ] tables remain structured
[ ] row order preserved
[ ] table IDs deterministic
[ ] small-table semantics correct if owned
[ ] large-table row-group semantics correct if owned
[ ] headers repeated where required
[ ] table context preserved

INLINE XBRL
[ ] ix facts extracted from raw HTML
[ ] concepts preserved
[ ] contextRef preserved/resolved
[ ] unitRef preserved/resolved
[ ] sign/scale handled
[ ] continuations handled where present
[ ] raw and normalized values both auditable

TRUTH
[ ] Task 2.1 truth contract reused
[ ] no duplicate truth-contract implementation
[ ] Task 2.2 registry reused
[ ] no duplicate supported-tag registry

ALIGNMENT
[ ] match restricted to correct filing/accession
[ ] period semantics explicit
[ ] unit semantics explicit
[ ] canonical value verified
[ ] dimensions preserved
[ ] exact/ambiguous/unmatched statuses explicit
[ ] ambiguous records never promoted to gold
[ ] multiple valid evidence occurrences handled deliberately

EVIDENCE
[ ] deterministic evidence schema created
[ ] evidence IDs stable
[ ] paragraph evidence supported
[ ] table evidence supported
[ ] gold evidence requires exact + eligible + supported
[ ] primary evidence population remains separate from frozen 2016-2020 DEV/TEST unless explicitly authorized

QUALITY
[ ] deterministic pilot run passes
[ ] pilot manual audit passes
[ ] full run completes/resumes safely
[ ] every failed document is recorded
[ ] coverage denominators are explicit
[ ] coverage by content type reported
[ ] coverage by supported tag reported
[ ] ambiguous cases diagnosed
[ ] unmatched cases diagnosed

REPRODUCIBILITY
[ ] config versioned
[ ] config hash deterministic
[ ] same input/config reproduces same IDs
[ ] same input/config reproduces same evidence hash
[ ] large artifacts hashed
[ ] outputs written atomically
[ ] resume validates source/config compatibility

METRICS
[ ] chunk metric availability reviewed honestly
[ ] no metric marked available without real usable gold
[ ] citation_grounding not falsely marked implemented
[ ] faithfulness remains deferred unless separately implemented
[ ] numeric tolerance remains deferred

TEST DISCIPLINE
[ ] Task 2.3 dataset unchanged
[ ] Task 2.4 split unchanged
[ ] official TEST evaluations remain 0/3
[ ] no protected TEST evaluation run consumed

REGRESSION
[ ] Task 2.7 PASS
[ ] Task 2.6 PASS
[ ] Task 2.5 PASS
[ ] Task 2.4 PASS
[ ] Task 2.1-2.3 PASS
[ ] Phase 1 PASS

COMPUTE
[ ] no unnecessary GPU dependence
[ ] no network source retrieval
[ ] no LLM evidence decisions
[ ] API spend = $0

TESTS
[ ] parser unit tests pass
[ ] inline-XBRL unit tests pass
[ ] alignment unit tests pass
[ ] portable tests pass
[ ] full suite passes

SAFETY
[ ] frozen data unchanged
[ ] secret scan clean
[ ] no large artifacts stageable
[ ] git dry-run safe

DOCUMENTATION
[ ] PHASE2_PRIMARY_EVIDENCE.md created
[ ] repository structure updated narrowly
[ ] Progress.md appended
[ ] result summary written
[ ] one coherent Task 2.8 commit created

PHASE EXIT
[ ] Phase 2 exit review completed
[ ] final Phase 2 status evidence-based
[ ] phase tag created only if conventions + status justify it
[ ] Phase 3 NOT started
```

---

# 108. Final Console Summary

Print:

```text
PHASE 2.8 — PRIMARY DOCUMENT EVIDENCE ALIGNMENT
===============================================

Precondition:
  Task 2.7 status:                       COMPLETE
  Task 2.7 regression:                   PASS

Primary corpus:
  source documents:                     <count>
  source bytes:                         <bytes>
  unique CIKs:                          <count>
  unique accessions:                    <count>
  source mutation:                      NO

Parser:
  parser:                               <name/version>
  parser config hash:                   <hash>
  parsed documents:                     <count>/<total>
  parse failures:                       <count>
  tables extracted:                     <count>

Inline XBRL:
  inline facts extracted:               <count>
  contexts resolved:                    <count>/<count>
  units resolved:                       <count>/<count>

Truth:
  truth contract:                       <version/hash>
  tag registry:                         <version/hash>
  eligible supported facts:             <count>

Alignment:
  exact:                                <count>
  ambiguous:                            <count>
  unmatched:                            <count>
  exact eligible alignment coverage:    <percent>

Evidence:
  gold evidence labels:                 <count>
  documents with evidence:              <count>
  table evidence labels:                <count>
  narrative evidence labels:            <count>
  evidence schema version:              <version>
  canonical evidence hash:              <hash>

Metric registry:
  chunk_recall@10 implemented:           YES
  chunk_recall@10 gold available:        YES / NO
  chunk_mrr implemented:                 YES
  chunk_mrr gold available:              YES / NO
  citation_grounding implemented:        NO / <actual>
  citation_grounding gold available:     YES / NO
  faithfulness:                          DEFERRED
  numeric_tolerance_match:               DEFERRED

TEST discipline:
  SEC DEV evaluation run:                NO
  SEC TEST evaluation run:               NO
  official TEST runs consumed:           0 / 3
  frozen DEV/TEST changed:               NO

Compute:
  network source calls:                  0
  LLM evidence calls:                    0
  API spend:                             $0

Tests:
  new Task 2.8 tests:                    <count>
  doctor:                                PASS
  portable:                              <result>
  full:                                  <result>

Regression:
  Task 2.7:                              PASS
  Task 2.6:                              PASS
  Task 2.5:                              PASS
  Task 2.4:                              PASS
  Task 2.1-2.3:                          PASS
  Phase 1:                               PASS

Task 2.8 result:
PASS / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 EXIT REVIEW
===================

2.1 XBRL Truth Contract:                  <status>
2.2 Supported Tag Registry:               <status>
2.3 Evaluation Dataset:                   <status>
2.4 DEV/TEST Split:                       <status>
2.5 Evaluation Schema:                    <status>
2.6 Metric Unit Tests:                    <status>
2.7 MS MARCO Harness Validation:          <status>
2.8 Primary Evidence Alignment:           <status>

Historical notes:
  citation format:                        8/10
  narrative pending_review:               50
  numeric tolerance:                      deferred
  faithfulness:                           deferred

PHASE 2 FINAL STATUS:
COMPLETE / COMPLETE WITH NOTE / COMPLETE WITH WARN / INCOMPLETE / BLOCKED

Phase tag:
<created / not created + reason>

NEXT:
<exact next task from PROJECT_EXECUTION.md>

DO NOT START PHASE 3.
```

---

# Final Principle

Task 2.8 is successful only if the project can prove:

```text
This XBRL fact
      ↓
came from this exact filing
      ↓
is valid under our frozen truth contract
      ↓
appears in this exact source element/table
      ↓
survived parsing into this deterministic evidence unit
      ↓
and can therefore serve as real chunk-level gold.
```

Not:

```text
"The number appears somewhere in the document."
```

Not:

```text
"An LLM thinks this chunk probably supports it."
```

Not:

```text
"This was the closest numeric match."
```

The evidence chain must be deterministic, source-traceable, versioned, and reproducible.

That is what turns later `chunk_recall@k` from a plausible number into a trustworthy measurement.