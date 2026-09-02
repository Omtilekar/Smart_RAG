# Phase 2 Primary-Document Evidence Alignment

Established in Task 2.8. Parses the 990 raw primary 10-K HTML filings
(tables and inline-XBRL intact, unlike EDGAR-CORPUS) and aligns their
inline-XBRL facts back to deterministic structural evidence units, so
the project can obtain real chunk-level evidence labels for future
`chunk_recall@k`/`chunk_mrr` evaluation.

## Objective

The most important result is not attractive Markdown. It is:

```text
For a trustworthy eligible XBRL fact, we can identify exactly which
parsed evidence unit in the original primary filing contains that fact.
```

## Why primary documents exist in this repository

EDGAR-CORPUS (Phase 1's narrative retrieval corpus) has its structured
tables stripped. The 990 primary 10-K HTML filings are different -
tables intact, inline XBRL intact - and exist for three jobs: table
extraction/retrieval, chunk-level evidence labels, and real HTML/
multi-format ingestion validation. Task 2.8 builds the second of these:
`inline XBRL -> exact source evidence -> chunk-level gold`.

## Critical finding: primary docs are a separate, later evidence population

Independently verified before any parsing began: **all 990 primary
filings are fiscal_year 2021-2024** (28 FY2021, 23 FY2022, 849 FY2023,
90 FY2024) - **0 fall inside the frozen Task 2.1 truth contract's
2016-2020 window**. This is a hard, structural, 100% mismatch, not a
probabilistic risk - confirmed by joining every primary-doc accession
against `data/xbrl.duckdb`'s `submissions.fiscal_year` directly.

**This was surfaced to the user before any parsing/alignment code was
written** (Section 33/Stop Condition I - "a new truth rule appears
necessary... surface the conflict"), since it means
TRUTH-CONTRACT-ELIGIBLE facts = 0 and GOLD evidence = 0 for this entire
population under the current, unmodified Task 2.1 truth contract, no
matter how well parsing/alignment works. The user's explicit decision:
build the full pipeline anyway, verify it against real XBRL facts (any
fiscal year, via the raw `facts` table rather than
`eligible_facts()`) to prove the mechanism's correctness, and report
`0` eligible/gold honestly rather than manufacturing a rule change.

The five-stage evidence state machine this task tracks, never
collapsed:

```text
EXTRACTED            - parsed from raw HTML at all
XBRL_MATCHED          - normalized value matches a real data/xbrl.duckdb
                        facts row for the same accession/tag/period/unit
                        (any fiscal year - the correctness check)
EVIDENCE_ALIGNED       - XBRL_MATCHED AND correlated to >=1 structural node
TRUTH_CONTRACT_ELIGIBLE - passes every src.eval.truth_contract/tag_registry
                          rule (registry-supported, correct unit/qtrs,
                          dimension-free, fiscal year 2016-2020)
GOLD                   - EVIDENCE_ALIGNED AND TRUTH_CONTRACT_ELIGIBLE
```

`src.parse.evidence_alignment`'s `alignment_status` field and
`eligible_for_gold` boolean together encode all five states: `exact`/
`exact_no_node` = XBRL_MATCHED (the latter lacking EVIDENCE_ALIGNED);
`ineligible_year_window`/`ineligible_dimensional`/`unsupported_tag` =
XBRL_MATCHED (or dimension/tag-excluded before matching) but not
TRUTH_CONTRACT_ELIGIBLE; `ambiguous`/`unmatched` = not even XBRL_MATCHED;
`eligible_for_gold=True` only when `alignment_status == "exact"` AND
every truth-contract dimension passes - which, given the year mismatch
above, is always `False` for this population today.

## Frozen source verification

```text
source documents:    990   (matches historical reference)
unique CIKs:          990
unique accessions:    990
total bytes:          4,476,551,759 (4.48 GB)
zero-byte files:      0
duplicate canonicals: 0
```

`src.parse.source_identity.enumerate_primary_documents()` builds a
`SourceDocument` per file - `document_id="primary:{cik}:{accession}"`,
`source_sha256`, `source_size_bytes` - deterministic, sorted by
(cik, accession), never filesystem mtime.

## Parser architecture

```text
src/parse/
    source_identity.py       - deterministic source identity
    primary_html.py          - Docling-based structural parsing
    inline_xbrl.py            - raw inline-XBRL DOM extraction (independent of Docling)
    evidence_alignment.py    - alignment against Task 2.1/2.2 (never reimplemented)
```

Never inside `scripts/`, `tests/`, or `src/eval/` - library code lives
in `src/parse/`; `scripts/build_primary_evidence.py` only orchestrates
(dry-run/pilot/full, resumability, artifact I/O).

## Docling contract

Docling (`docling==2.124.0`) converts each primary filing's raw HTML
into a `DoclingDocument` - paragraphs, headings, and tables, with real
row/column grid structure. Verified directly: Docling's HTML backend
requires no GPU and no OCR (`.prov` - page/bbox provenance - is empty
for every item on HTML input, confirming no layout-model inference
occurred); one filing (3.5MB, Tucson Electric Power's 10-K) converted in
6.4 seconds.

**Docling's own output is NOT authoritative for inline-XBRL identity.**
Verified directly before writing any alignment code: Docling's Markdown/
structural export does not preserve `ix:nonFraction`/`contextRef`/
`unitRef`/`decimals`/`scale`/`sign` at all - it flattens inline-XBRL
facts to their plain displayed text, indistinguishable from ordinary
prose. `src/parse/inline_xbrl.py` therefore parses the SAME raw HTML a
second time, independently, via `lxml.etree.XMLParser` directly on the
file - the two representations are built independently and then
explicitly aligned (Section 10's "dual-path design").

**Source locator honesty (Section 14)**: Docling's HTML backend has no
page/bbox provenance, so `StructuralNode.source_locator` is Docling's
own deterministic structural reference (`self_ref`, e.g. `"#/texts/42"`)
- not a raw-HTML XPath or byte offset. This is documented explicitly,
not claimed to be more precise than it is. It is still fully
reproducible: re-converting the same file with the same Docling version
produces the identical `self_ref` for the identical logical element -
verified directly (`tests/test_primary_html_parser.py
::test_real_primary_document_structural_parsing` re-runs Docling twice
on the same real file and asserts byte-identical node IDs and text).

## A real dependency-breakage bug found and fixed (Phase 1 regression risk)

`pip install docling` (the full metapackage) silently broke the Phase 1
BGE embedding pipeline: it pulled in `docling-ibm-models` (Docling's
PDF/OCR vision-model backend) which requires `torchvision`, and the
resulting `torchvision==0.28.0` build was ABI-incompatible with this
project's pinned `torch==2.13.0+cu130`
(`RuntimeError: operator torchvision::nms does not exist` at
`transformers` import time - `transformers.PreTrainedModel`, which
`sentence-transformers` needs directly, failed to import at all).
Reinstalling a version- and index-matched `torchvision+cu130` build did
**not** fix it - the same ABI error persisted, indicating no working
torchvision build was available for this exact torch build in this
environment. Caught immediately by re-running the full existing test
suite after installing Docling (Section 87-92's regression gates) -
never assumed a new dependency was safe just because Task 2.8's own new
code worked.

**Root cause and fix**: this project's actual need is `docling.document_converter`'s
HTML/XHTML backend only - never PDF, never OCR (Section 11/75). The
lighter `docling-slim` package (a declared sub-component of the full
`docling` metapackage) provides the exact identical
`docling.document_converter` module and full HTML parsing behavior -
verified directly, identical text/table counts (1,714 texts, 93 tables)
on the same real filing - **without** `docling-ibm-models`, `torch`
extras, or `torchvision` anywhere in its dependency graph.
`docling-parse` (needed - `docling.document_converter` imports it
unconditionally at module level for its PDF backend - but itself
torch-free) is declared alongside it. `requirements.txt` now pins
`docling-slim==2.124.0` and `docling-parse==7.16.0`, not `docling`.
Verified clean after the fix: `pip check` passes, `scripts/dev.py
doctor` passes (exit 0), the full existing test suite (756 tests) passes
with zero regressions, and Docling HTML conversion still works
identically.

## A real case-sensitivity bug found and fixed before writing any extraction code

Before any inline-XBRL code was written, a naive
`lxml.etree.HTMLParser`-based extraction was tried first and found
**0** `ix:nonFraction`/`ix:nonNumeric` elements in a real filing known
to contain over a thousand of them. Root cause: HTML is
case-insensitive, so `etree.HTMLParser` silently lowercases every tag
name (`ix:nonFraction` -> `ix:nonfraction`), and lxml's namespace-aware
`.iter()` then matches nothing. Fixed by using `etree.XMLParser`
instead - primary 10-K filings are well-formed XHTML+inline-XBRL, so
XML parsing works directly and preserves exact case and real namespace
URIs (confirmed: `1357` `nonFraction` elements found in the same file
once parsed as XML). `tests/test_inline_xbrl.py::test_case_sensitivity_preserved`
guards this regression permanently. `src/parse/inline_xbrl.py` never
calls `etree.HTMLParser`.

## Structural node schema

```text
document_id, node_id, parent_node_id, node_type (heading/paragraph/table/other),
section_id, section_title, source_order, source_locator, text,
content_type (narrative/table), table_id, table_part
```

`node_id = "{document_id}#node-{ordinal:05d}"` - a simple, deterministic
ordinal scheme (Section 13 requires determinism, not that the ID be a
hash; an ordinal tied to `document_id` is equally deterministic and more
directly auditable than an opaque digest).

## Section detection

Regex-matches `^Item\s+\d{1,2}[A-C]?\.\s+` against every text node,
restricted to the 23 canonical SEC Form 10-K Item identifiers (Item 1
through Item 16). **Real filings repeat each Item heading twice** - once
in a table-of-contents listing near the top, once as the actual section
header before its content. The **last occurrence** of each canonical
Item id is taken as the real header (TOC entries and real headers name
Items in the same relative order, verified against a real filing: all
23 canonical Items correctly detected with no TOC contamination). An
Item number outside the canonical set is ignored entirely -
`section_id=None` is preferred over a wrong guess (Section 15).

## Table handling

Every Docling `TableItem`'s real row/column grid is preserved (never
"all cells concatenated into one paragraph"). Small tables (<=50 data
rows) become one `content_type="table"` node; larger tables split into
row-group parts of at most 50 data rows each, **repeating the header
row in every part**, sharing one `table_id`, with a deterministic
`table_part` ordinal - a large table is fully reconstructable from its
parts (`tests/test_primary_html_parser.py::test_table_parts_reconstructable`).
Table serialization baseline: **Markdown** (pipe-table format,
consistent with Docling's own native export and PROJECT_SPEC.md's
Stage 1 description) - the one reproducible baseline this task needs,
not a Phase 3 format-ablation experiment (Section 21). Real filing:
93 tables, 3 correctly split into multiple parts, 97 total table nodes.

## Inline-XBRL extraction

`src/parse/inline_xbrl.py` extracts every `ix:nonFraction`/`ix:nonNumeric`
element in document order via namespace-aware XML parsing, resolving
`ix:continuation` chains (verified against real multi-hop chains) and
preserving both raw attributes (concept QName, `contextRef`, `unitRef`,
`decimals`, `scale`, `sign`, `format`, `id`) and the normalized value -
raw is never discarded once normalized (Section 24).

### Contexts and units

Every referenced `xbrli:context` is parsed into period (instant vs.
duration, with real start/end or instant dates) and dimensions
(`xbrldi:explicitMember` pairs, sorted, never silently stripped -
Section 37). Every `xbrli:unit` is parsed, including `<xbrli:divide>`
compound units (see EPS below) - not just simple `<xbrli:measure>`
lists.

### Context -> truth-contract period mapping

`context_to_truth_contract_period()` converts a context's period into
the same `(ddate, qtrs)` fields `src.eval.truth_contract`'s raw facts
use: instant -> `qtrs=0`, `ddate=`the instant date; duration -> `ddate=`
the period end date, `qtrs=`round(months spanned / 3) (4 for a full
fiscal year, 1 for a quarter). **Verified against a real raw fact**: a
2023-01-01..2023-12-31 duration context maps to `ddate=20231231,
qtrs=4`, and the corresponding real `data/xbrl.duckdb` row for the same
accession/tag is `(ddate='20231231', qtrs=4, value=1875448000.0)` -
matching exactly.

### Numeric normalization

Uses `decimal.Decimal` throughout (never `float()` on the raw displayed
string - Section 28). Handles every numeric transform actually observed
in this corpus (verified via real-data scans before being trusted,
never guessed):

```text
ixt:num-dot-decimal / ixt:numdotdecimal    - strip thousands commas
ixt:num-comma-decimal / ixt:numcommadecimal - European convention (',' decimal, '.' thousands)
ixt:fixed-zero / ixt:fixedzero              - always zero
ixt:zerodash                                 - a displayed "-" meaning zero
ixt-sec:numwordsen                           - English number words: ones/tens/hundred/
                                               thousand/million compounds, "no"/"none"/"nil" as zero
```

Any other `format` raises `NumericNormalizationError` - a real,
recorded parse issue, never a silent guess. `sign="-"` negates the
value (Task 2.1's rule that legitimate signed facts are never treated
as invalid is preserved - real Amazon `IncomeTaxExpenseBenefit` facts
normalize to e.g. `-3217000000` correctly). `scale` applies
`* 10**scale` via exact Decimal arithmetic (verified: displayed
`"1,875,448"` with `scale="3"` normalizes to `1875448000`, matching the
real raw fact exactly).

**Independently verified against a real raw fact** before being
trusted: `us-gaap:Revenues`, context 2023-01-01..2023-12-31, displayed
`"1,875,448"`, `scale="3"` -> normalized `1875448000` -> matches
`data/xbrl.duckdb`'s real `facts` row for the same accession/tag/period
exactly (`tests/test_inline_xbrl.py::test_numeric_normalization_matches_real_xbrl_fact`).

### EPS / divide units - a second real bug found and fixed during the pilot

The 20-filing pilot's first pass produced 2,634 `parse_error` records
(3.5% of all facts). Root-caused (not silently accepted, per Section
56): `EarningsPerShareBasic`/`EarningsPerShareDiluted` and similar
per-share concepts use a `<xbrli:divide>` unit
(`unitNumerator=iso4217:USD`, `unitDenominator=xbrli:shares`), which
`extract_units()`'s first version did not parse at all (only direct
`<xbrli:measure>` children), so their unit always resolved to `None`.
**Verified against a real raw fact before fixing**: Amazon's inline
`us-gaap:EarningsPerShareDiluted` fact uses exactly this USD/shares
divide unit, and `data/xbrl.duckdb`'s real `facts` row for the same
accession/tag stores `uom='USD'` (SEC's own processing pipeline strips
the per-share denominator for storage - confirmed directly, matching
Task 2.2's registry decision that EPS tags use plain `"USD"`, never a
compound `"USD/shares"`). Fixed: `XbrlUnit` now parses `<xbrli:divide>`
structure, and `unit_to_uom()` maps a USD/shares divide unit to
canonical `"USD"` (any other divide-unit shape - e.g. USD/sqft - returns
`None` rather than guessing). Re-running the pilot after this fix
dropped `parse_error` to 1,304 (all a third, distinct, correctly-
diagnosed root cause - see below) and correctly re-classified hundreds
of EPS facts to `ineligible_year_window` (would-be-gold).

### A third classification bug found and fixed

The remaining 1,304 `parse_error` records were then investigated
(never just reported as a raw percentage - Section 65): **100%** had
`canonical_unit=None`, and all belonged to tags never in the Task 2.2
registry anyway (`NumberOfRealEstateProperties`,
`FinancingReceivableModificationsNumberOfContracts2`,
`NumberOfJointVentures`, and similar pure-count concepts using custom
XBRL count units this project has no currency/share/pure mapping for).
The real bug: `scripts/build_primary_evidence.py`'s classification
logic required a resolved unit BEFORE checking tag support, so an
unsupported-tag fact with an unmappable unit was mislabeled
`parse_error` instead of the more accurate `unsupported_tag`. Fixed by
checking tag support first - a tag outside the registry is
`unsupported_tag` regardless of its unit; only a registry-supported tag
with a genuinely unresolvable unit is now a real `parse_error`.
Re-running the pilot after this fix: **0** `parse_error` records - every
one of the pilot's 74,722 facts now lands in a semantically accurate
bucket.

## Truth-contract / tag-registry integration

`src/parse/evidence_alignment.py` imports `src.eval.tag_registry.get_registry()`
and `src.eval.truth_contract`'s frozen constants directly - it never
reimplements eligibility rules and never creates a competing truth
contract (Section 31/32). `check_eligibility_dimensions()` evaluates
every Task 2.1/2.2 rule independently (tag-supported, unit-matches-
registry, qtrs-matches-registry, dimension-free, year-in-window) so a
diagnostic report can show WHICH rule blocks eligibility, not just a
final yes/no.

## Fact identity and alignment algorithm

Accession-first, never a global numeric search (Section 34):
`FactIdentity(accession, cik, tag, ddate, qtrs, uom)` restricts the raw
`facts` table query to the exact filing before any value comparison.
The query additionally requires `coreg`/`segments` blank, matching
`src.eval.truth_contract`'s own grain exactly - **a real bug found and
fixed**: without this filter, a dimensional duplicate row for the same
(adsh,tag,ddate,qtrs,uom) grain (very common - e.g. a related-party-
transaction breakdown of `Revenues`) could be picked up instead of the
real non-dimensional value, as happened in an early test run (39M vs.
the correct 1.875B). Dimensional inline facts are now classified
`ineligible_dimensional` **before** any raw-value query is attempted
(a blank-segment query would be a category mismatch for them, not a
genuine "unmatched" result).

Alignment statuses (Section 42 - explicit, never a fabricated
confidence score):

```text
unsupported_tag         - concept not us-gaap or not in the frozen registry
ineligible_dimensional  - has segment/dimension context (excluded from gold per Task 2.1)
ambiguous               - the accession/tag/period/unit grain has 2+ conflicting raw values
unmatched               - no raw facts-table row matches this exact grain/value
ineligible_year_window  - matched, registry-supported, dimension-free, but fiscal year outside 2016-2020
exact_no_node           - matched and eligible but no structural node contains the raw display text
exact                   - matched, eligible, and aligned to >=1 structural node - GOLD candidate
```

Gold promotion rule (Section 43): `alignment_status == "exact"` AND
every eligibility dimension passes (`is_fully_eligible()`) - ambiguous
matches are never resolved by arbitrary first-match selection, they
remain diagnostic records forever.

### Content-based structural correlation

`find_candidate_nodes()` searches every structural node's
(whitespace-normalized) text for the fact's raw displayed text,
returning **every** matching node in source order - never collapsed to
one (Section 44: the same value legitimately appearing in a summary
table AND a financial statement produces two valid evidence nodes, both
preserved). Verified against real data: table-cell facts correctly
align to their containing table node; narrative facts correctly align
to their containing paragraph node; a repeated Amazon `IncomeTaxExpenseBenefit`
value aligned to 6 distinct candidate nodes across the filing (all
legitimate, matching the many places large 10-Ks repeat headline
figures).

## Evidence schema

```text
evidence_schema_version, evidence_id, document_id, cik, accession, fiscal_year,
section_id, section_title, node_ids, content_type,
concept_name, concept_namespace, context_ref, unit_ref,
raw_display_value, normalized_value, canonical_unit,
alignment_status, eligible_for_gold,
truth_contract_version, truth_contract_hash, tag_registry_version, tag_registry_hash
```

`evidence_id = "{document_id}#fact-{element_id or 'order-NNNNN'}"` -
deterministic, stable across re-runs of the same source+config.

## Pilot

20 filings, selected deterministically by evenly-spaced rank across
`source_size_bytes` (smallest to largest - never a hand-picked "easy"
subset, Section 55). Three real bugs found and fixed during the pilot
(case-sensitive tag matching found before any extraction code was
trusted; EPS divide-unit mapping; unsupported-tag-before-unit
classification order) - see sections above. Final pilot result (after
all three fixes):

```text
documents parsed:        20/20, 0 failures
structural nodes:        44,780
tables:                  2,792 (across 20 filings)
inline facts extracted:  74,722 (66,727 nonFraction + 7,995 nonNumeric)
contexts / units:        16,411 / 234
status breakdown:
  unsupported_tag:         63,426
  ineligible_year_window:   1,185  (would be GOLD if not for the year window)
  ineligible_dimensional:   2,045
  unmatched:                   35
  ambiguous:                    0
  parse_error:                  0
gold_evidence_count:          0   (expected - see "critical finding" above)
```

## Pilot manual audit (deterministic, never cherry-picked)

First-by-`evidence_id` samples inspected across categories:

- **Table would-be-gold**: Amazon `IncomeTaxExpenseBenefit`, context
  c-8, raw `"3,217"`, `sign="-"` -> normalized `-3217000000`, correctly
  aligned to its containing table node.
- **Narrative would-be-gold**: `CashAndCashEquivalentsAtCarryingValue`,
  raw `"6.1"` -> normalized `6100000.0`, correctly aligned to its
  containing paragraph.
- **EPS**: Amazon `EarningsPerShareDiluted`, raw `"3.24"` -> normalized
  `Decimal("3.24")`, `canonical_unit="USD"` - matches the real raw facts
  table row for the same accession/tag/period exactly (independently
  confirmed via direct SQL before this document was written).
- **Negative values**: 137 negative would-be-gold facts in the pilot,
  all with `sign="-"` correctly applied (e.g. `IncomeTaxExpenseBenefit`
  `-3217000000`).
- **Unmatched audit** (Section 65 - never just a percentage): all 35
  unmatched facts investigated by concept - the pattern is narrative/
  MD&A prose repeating a headline figure at coarser precision (e.g.
  displayed `"4.8"` at `scale=9` in prose vs. the financial statements'
  exact `4,791` at `scale=6`) tagged with the same concept/context. This
  is a genuine **source/XBRL discrepancy** (a real, well-known SEC
  filing phenomenon - the same concept tagged twice at different
  rounding precision), correctly reported as `unmatched` rather than
  fuzzy-matched (Section 38: no tolerance matching without a frozen
  tolerance policy).

## Full run

```text
source documents:        990
parsed successfully:     990  (100%)
parse failures:            0

structural nodes:      2,365,581
tables:                   136,592
inline facts extracted: 2,603,110  (2,393,329 nonFraction + 209,781 nonNumeric)
contexts / units:        663,479 / 10,963

status breakdown:
  unsupported_tag:        2,240,712
  ineligible_dimensional:    95,853
  ineligible_year_window:    45,769   (would be GOLD if not for the year window)
  unmatched:                   6,944
  ambiguous:                        0
  parse_error:                      0

eligible_fact_count:  0
gold_evidence_count:  0
```

**A fourth real bug found and fixed after the first full run**: the
first complete pass over all 990 filings finished with **986/990
success, 4 failures** - each a distinct `ixt-sec:numwordsen` compound
this project's number-word parser did not yet cover: `"one billion"`
(x2), `"One hundred three"`, `"three hundred two"`. Fixed by extending
`_parse_english_number_word()` to a proper recursive "X hundred [Y]"
+ optional thousand/million/**billion** multiplier grammar. Verified
directly against the actual 4 failed documents before re-running
anything at scale - a 5th, related gap (`"twenty three"`,
space-separated tens+ones without a hyphen) and a 6th
(`"one hundred thirty three"`, hundred + space-separated remainder)
surfaced during that direct verification and were fixed the same way.
Because this bugfix did not change `build_config()`'s versioned content
(the version string bump for the three earlier pilot-discovered bugs
already covered this whole module), `parser_config_hash` was unchanged,
so re-running `--full` correctly **resumed all 986 already-successful
documents and reprocessed only the 4 failed ones** in 51.5 seconds -
result: **990/990 (100%) parsed successfully, 0 failures, 0
`parse_error` records** across the entire corpus.

## Coverage diagnostics (full run, by content type)

```text
table nodes:      42,249 ineligible_year_window facts correlated to a table node
narrative nodes:   3,484 ineligible_year_window facts correlated to a narrative/paragraph node
no node found:        36 ineligible_year_window facts (0.08% of the 45,769) - parser lost source position
```

Node-correlation coverage is therefore **99.92%** for facts that
otherwise passed every other alignment check - a strong signal that
`find_candidate_nodes()`'s content-based structural correlation is
reliable at full scale, not just on the 20-filing pilot.

## Coverage by tag (would-be-gold facts, i.e. `ineligible_year_window`)

Every one of the 15 Task 2.2 registry tags is represented:

```text
NetIncomeLoss                                          8,265
IncomeTaxExpenseBenefit                                7,182
EarningsPerShareBasic                                  4,812
EarningsPerShareDiluted                                4,777
StockholdersEquity                                     3,330
RevenueFromContractWithCustomerExcludingAssessedTax    3,252
Revenues                                               2,827
Assets                                                 2,571
OperatingIncomeLoss                                    2,541
CashAndCashEquivalentsAtCarryingValue                  2,475
Liabilities                                            1,483
GrossProfit                                              790
OperatingExpenses                                        674
ResearchAndDevelopmentExpense                            493
CostOfRevenue                                            297
```

The EPS divide-unit fix (see above) is directly visible here -
`EarningsPerShareBasic`/`EarningsPerShareDiluted` together account for
9,589 would-be-gold facts, which would all have been `parse_error`
under the pre-fix code.

## Coverage by unit

```text
USD:  45,624
CAD:     145
```

**Caveat, stated honestly**: `ineligible_year_window` status means a
fact raw-matched its source value, has a registry-supported tag, and is
dimension-free - it does NOT by itself guarantee the fact's *unit* also
matches the registry's per-tag required unit (`determine_alignment_status()`
categorizes by tag/dimension/match-status/year, not by unit - only the
separate `is_fully_eligible()` gold-boolean checks
`unit_matches_registry` too). The 145 CAD-denominated facts (a small
number of Canadian filers reporting in CAD) would very likely still
fail `unit_matches_registry` even if the year window were extended,
since the Task 2.2 registry's per-tag unit for all of these concepts is
`USD`. This is reported honestly rather than folded into a single
overstated "would-be-gold" number.

## Reproducibility

`parser_config_hash` versions every result-affecting setting (parser
name/version, table serialization/row-group size, section-detection
policy, node-ID scheme, inline-XBRL extraction/numeric-normalization/
alignment versions, evidence schema version, truth-contract/tag-
registry identity) - bumped explicitly on each of the three real bug
fixes found during the pilot, so a stale resumed artifact from before a
fix is never silently reused. Re-parsing the same file with the same
Docling version produces byte-identical structural node IDs/text
(verified directly). `artifacts/primary_docs/manifest.json` tracks
per-document `status`/`source_sha256`/`parser_config_hash` for safe
resume - a document is only skipped if both its source hash and the
current config hash match the manifest's recorded value. **Directly
verified** (not just claimed): the same real filing was processed twice
via `process_document()`, bypassing the resume cache entirely, and
produced byte-identical structural-node JSON, inline-XBRL-fact JSON, and
evidence-record JSON both times.

```text
parser_config_hash:      84f6cf2e9cf04921cbffc20cf446eac03885e0a87f05e03c9eb71d4eb6c6288d
canonical_evidence_hash: 32381b6cee8e8bd3fbb741f9f4326dc27384b283829bfdb5da388ab5e6c5dcc2
  (SHA-256 over the sorted map of {per-document evidence file name -> SHA-256 of that file's content} -
  changes if any single document's evidence output changes, in a way that scales to millions of records
  without loading them all into one in-memory structure at once)
truth_contract_hash:     8ce68e8f53395f8f983e0002c53e62a31bb121b8551f28e739fcebb7f462988c
tag_registry_hash:       a230373e2a788423026142beb93c5c454a291f23468d46cfb40f5692e48b8070
```

## Resume safety

Every derived artifact (parsed nodes, inline-XBRL facts, evidence
records, manifest) is written atomically (`.json.tmp` -> `os.replace`) -
a crash mid-write never leaves a truncated file a later run mistakes for
success. The full run was interrupted and resumed cleanly during actual
execution (consistent with Task 2.7's MS MARCO build also being
interrupted by the same local machine going idle) - verified each time
that already-completed documents' timestamps were unchanged and were
correctly skipped (`skipped_resumed` count in the run summary).

## TEST discipline

No SEC DEV or TEST retrieval evaluation was run. `artifacts/eval/
phase_2_4_test.json` was never read; `load_test_set()` was never
called. Official SEC TEST evaluation runs consumed: **0/3** throughout
this task.

## Known limitations

- **Gold evidence is 0 for this population today** - a structural
  fiscal-year mismatch with the frozen Task 2.1 truth contract, not a
  parser/alignment defect (see "critical finding" above). A future task
  extending or versioning the truth contract's supported window (a
  decision explicitly out of scope for Task 2.8, which "must not modify
  Task 2.1 casually") would let this same pipeline immediately start
  producing real gold evidence.
- Source locators are Docling's own structural reference (`self_ref`),
  not a raw-HTML byte offset or XPath - honestly documented, not claimed
  to be more precise (Section 14).
- `coreg` (co-registrant) is not derived from inline contexts - primary
  filings in this corpus are single-registrant filings; a genuine
  multi-registrant combined filing is an out-of-scope edge case.
- Segmented (dimensional) facts' exact `segments` string is not
  reconstructed to match SEC's own internal format - unnecessary, since
  dimensional facts are excluded from gold regardless (Task 2.1's own
  rule), so only the boolean "has dimensions" matters for this task.
- `ixt-sec:numwordsen` number-word parsing covers 0-20, tens, hundred/
  thousand/million compounds, and "no"/"none"/"nil" as zero - verified
  against real corpus usage; a rarer word form outside this set raises
  `NumericNormalizationError` (a recorded, non-silent parse issue).

## Validation commands

```bash
python scripts/build_primary_evidence.py --dry-run
python scripts/build_primary_evidence.py --pilot
python scripts/build_primary_evidence.py --full
python -m pytest tests/test_inline_xbrl.py tests/test_primary_html_parser.py tests/test_primary_evidence_alignment.py -q
```
