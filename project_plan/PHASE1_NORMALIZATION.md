# Phase 1 Document Normalization

Established in Task 1.2. Converts the frozen 1,500-filing Task 1.1
development corpus into one deterministic Markdown document per filing —
the input format Task 1.3's fixed-window chunker will consume. Deliberately
crude, per `PROJECT_EXECUTION.md`'s Phase 1 framing: no semantic cleaning,
no invented text, no table reconstruction.

## Purpose

Task 1.1 selected *which* 1,500 filings. Task 1.2 renders *what they look
like* as text: EDGAR-CORPUS's 20 raw `section_*` columns become one
Markdown file per filing, with deterministic YAML frontmatter carrying the
provenance every later Phase 1 task needs (`cik`, `fiscal_year`, source
identity) without re-deriving it from the manifest each time.

## Input manifest

```text
manifest:                       results/phase_1_1_development_corpus.json
development_manifest_sha256:    d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b
```

Independently recomputed (not trusted from the stored value) using Task
1.1's documented procedure — `sha256(json.dumps(filings, sort_keys=True,
separators=(",", ":")))` — and matched exactly before any normalization
code ran. `scripts/normalize_development_corpus.py` recomputes and asserts
this checksum on every run; it refuses to proceed (`BLOCKED`) if the
manifest ever changes.

## EDGAR-CORPUS source

`data/edgar_corpus/{train,test,validation}.parquet`, frozen, read-only.
20 `section_*` columns, confirmed via direct schema inspection to already
be stored in natural SEC 10-K Item order:

```text
section_1, section_1A, section_1B, section_2, section_3, section_4,
section_5, section_6, section_7, section_7A, section_8, section_9,
section_9A, section_9B, section_10, section_11, section_12, section_13,
section_14, section_15
```

This order is used directly (`src/normalize/edgar_markdown.py`,
`SECTION_COLUMNS`) — not inferred or re-derived, since the source parquet
already encodes it correctly.

## Source resolution

All 1,500 manifest `document_id`s resolved against the union of the three
EDGAR-CORPUS splits: **1,500/1,500 resolved, 0 duplicates, 0 identity
mismatches** (`cik`/`year`/`source_split` all confirmed equal to the
manifest's values via a single set-based DuckDB join, not a per-row
Python loop).

## Known-empty filings (user-approved handling)

7 of the 1,500 selected filings have **all 20** `section_*` columns present
but empty-string in EDGAR-CORPUS itself — verified directly against the
live source data, not a resolution bug:

```text
18498_2018.htm     GENESCO INC
1324424_2018.htm   EXPEDIA GROUP, INC.
71691_2016.htm     NEW YORK TIMES CO
1388410_2016.htm   PARALLAX HEALTH SCIENCES, INC.
1388410_2018.htm   PARALLAX HEALTH SCIENCES, INC.  (same company, other year)
883241_2017.htm    SYNOPSYS INC
1110803_2019.htm   ILLUMINA, INC.
```

**User-approved decision** (asked before implementation, since Task 1.1's
manifest is frozen and must not be reselected/substituted, and this wasn't
covered by any existing rule): normalize these as **frontmatter-only
documents** — valid YAML frontmatter, empty body, zero `## Item` headings.
This is an explicit, documented exception to the normal "at least one
heading rendered" output check
(`scripts/normalize_development_corpus.py`'s `KNOWN_EMPTY_BODY_DOCUMENT_IDS`
constant), not a silent pass. The manifest stays at exactly 1,500 rows and
the normalized corpus stays at exactly 1,500 documents.

## Normalization contract (conservative transformations only)

```text
CRLF/CR line endings          -> normalized to \n
leading/trailing whitespace   -> stripped per section
null/empty/whitespace-only    -> section omitted entirely (no heading, no body)
Markdown item headings        -> "## Item {N|N-letter}", exactly the SEC item
                                  number/letter encoded in the source column
                                  name - no invented titles (e.g. no
                                  "Item 7 — Management's Discussion...")
YAML frontmatter              -> deterministic, fixed key order
encoding                       -> UTF-8
final newline                  -> exactly one, always
```

Explicitly **not** performed: LLM rewriting, semantic cleaning, OCR,
de-hyphenation inference, header/footer detection, boilerplate removal,
duplicate-paragraph inference, HTML recovery, table reconstruction, numeric
restructuring, section-boundary inference, summarization.

**Observed but deliberately not corrected**: several source sections begin
with their own embedded item label inside the raw text itself (e.g.
`section_1` literally starting with `"Item 1. Business\n..."`), which reads
as slightly redundant against the rendered `## Item 1` Markdown heading
above it. This is exactly what EDGAR-CORPUS's own extraction produced —
"boilerplate removal" is explicitly out of scope for Task 1.2, so it is
left as-is and noted here rather than silently stripped.

## Frontmatter schema

```yaml
---
cik: 1005817
company: "TOMPKINS FINANCIAL CORP"
form_type: "10-K"
fiscal_year: 2016
source: "edgar_corpus"
source_filename: "1005817_2016.htm"
document_id: "1005817_2016.htm"
source_split: "validation"
development_manifest_sha256: "d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b"
---
```

Fixed key order, independent of any input dict ordering. String values are
quoted via stdlib `json.dumps(value, ensure_ascii=False)` — safe against
colons, `#`, quotes, newlines, and Unicode without hand-rolled escaping and
without a new dependency (a JSON double-quoted string is a valid YAML flow
scalar). Integers are emitted unquoted.

```text
fabricated accession fields: NONE
```

`company` is informational provenance from XBRL (via the Task 1.1
manifest), not from EDGAR-CORPUS itself, which has no company-name field —
present for all 1,500 rows (0 missing). No `adsh`/accession field appears
anywhere in the frontmatter; `document_id`/`source_filename` are EDGAR-CORPUS's
own `filename`, the only trustworthy source identity that exists.

## Output location and normalizer version

```text
normalizer_version:  phase1-minimal-v1   (user-approved; src/storage.py's
                                           normalized_dir(version) was a path
                                           helper only, never previously
                                           given a value)
artifact path:         artifacts/normalized/phase1-minimal-v1/
```

**Correction note**: originally built and committed as `normalizer_version
= "v1"` (Task 1.2's own version-naming question offered "phase1-minimal-v1"
as the recommended option, but `"v1"` was the answer actually approved and
built at the time). Before Task 1.3 began, this was revisited as a genuine
follow-up decision and corrected to `phase1-minimal-v1` — see `Progress.md`,
"Phase 1.2 Correction". The correction only moves the artifact directory and
updates the `normalizer_version` string in tracked config/summary/docs;
`normalizer_version` was never part of any document's frontmatter or
filename, so `normalization_build_sha256` is unchanged
(`fd0abad26111412d792033373e02a0a6a3fb1d0d7a47dbad6063e98c2272244b`) —
verified by byte-diffing the old and new artifact directories before
deleting the old one.

Written via `src.storage.get_storage().normalized_dir("phase1-minimal-v1")`
+ `ensure_dir()` — the existing Task 0.7 storage contract, not a hardcoded
path. Git-ignored generated pipeline state, per `STORAGE.md`; only a small
tracked summary (`results/phase_1_2_normalization_summary.json`) and config
(`configs/normalize_development_corpus.json`) are committed.

Output filename mapping is deterministic and 1:1:
`1005817_2016.htm -> 1005817_2016.md` (extension replaced only). Verified
unique across all 1,500 outputs.

## Build checksum and determinism

`normalization_build_sha256` (not to be confused with the later, unrelated
`chunk_config_hash`): sort output filenames ascending; SHA-256 the exact
UTF-8 bytes of each file; concatenate `"{filename}:{filehash}\n"` lines in
that sorted order; SHA-256 the combined stream.

```text
normalization_build_sha256: fd0abad26111412d792033373e02a0a6a3fb1d0d7a47dbad6063e98c2272244b
```

Verified in two independent fresh-process runs: identical
`normalization_build_sha256`, identical file count (1,500), identical
filenames, byte-for-byte identical content (`diff -rq` on both output
directories reported no differences). No timestamp or other non-reproducible
value is embedded in any normalized document's bytes — `created_at_utc`
exists only in the tracked summary file, never inside a `.md` file.

Re-running the build is idempotent: it recomputes the same 1,500 files and
refuses (`FATAL`, does not silently overwrite) if `artifacts/normalized/phase1-minimal-v1/`
already contains files that aren't part of the current expected output set.

## Corpus statistics (real build)

```text
document count:        1,500
total normalized size:  430,712,686 bytes  (~410.8 MiB)
character count:        min=282  median=271,065  p95=543,714  max=2,364,857
non-empty sections:      min=0  median=20  p95=20  max=20
known-empty documents:   7 (see above)
```

Per-section presence (of 1,500 selected documents):

| Item | Present | % |
|---|---:|---:|
| 1 | 1,427 | 95.13% |
| 1A | 1,420 | 94.67% |
| 1B | 1,416 | 94.40% |
| 2 | 1,427 | 95.13% |
| 3 | 1,485 | 99.00% |
| 4 | 1,458 | 97.20% |
| 5 | 1,485 | 99.00% |
| 6 | 1,458 | 97.20% |
| 7 | 1,482 | 98.80% |
| 7A | 1,431 | 95.40% |
| 8 | 1,478 | 98.53% |
| 9 | 1,471 | 98.07% |
| 9A | 1,470 | 98.00% |
| 9B | 1,428 | 95.20% |
| 10 | 1,460 | 97.33% |
| 11 | 1,409 | 93.93% |
| 12 | 1,450 | 96.67% |
| 13 | 1,451 | 96.73% |
| 14 | 1,461 | 97.40% |
| 15 | 1,476 | 98.40% |

**Notably higher fill rates than the full EDGAR-CORPUS population.**
`DATA_READINESS_REPORT.md` reports Item 1A at only 25.6% across all 91,086
filings; the Phase 1 development corpus shows 94.67%. This is expected, not
a discrepancy: Task 1.1's selection is restricted to the 2016-2020
XBRL-aligned population, which skews toward larger, more consistently
XBRL-tagged filers whose EDGAR-CORPUS extraction is also more complete —
the sparse-section problem documented for the full corpus is a much smaller
issue for this specific 1,500-filing development subset.

## Manual verification

11 documents manually traced (2 per year across 2016-2020, plus one
known-empty filing) through the full chain: Task 1.1 manifest row → raw
EDGAR-CORPUS source row → normalized Markdown. All 11/11 passed — correct
frontmatter, correct section order, real sparse-section case included
(`1004702_2020.md`, 16/20 sections, missing Item 1/1A), and the known-empty
case (`18498_2018.md`, 0 body characters, 0 headings, valid frontmatter)
confirmed to match the approved policy exactly.

## Known limitations

- Simple Phase 1 cleaning only — CRLF normalization and whitespace
  stripping, nothing more. Not a production-quality normalizer.
- No structured tables — EDGAR-CORPUS never had them (confirmed in Data
  Preparation); this task cannot recover what the source never had.
- Sparse source sections remain sparse. 7 filings have zero source text at
  all and are output as frontmatter-only documents by design (see above).
- No trustworthy EDGAR accession number exists in EDGAR-CORPUS, and none is
  fabricated anywhere in this normalizer or its output.
- No primary-document (990-filing HTML corpus) enrichment — Task 1.2 works
  from EDGAR-CORPUS text only, per the task's explicit non-goals.
- No tokenization or chunking — whole normalized filings only. Token
  statistics and chunk boundaries are Task 1.3's job.

## Next consumer

Task 1.3 (Minimal Fixed-Window Chunker) reads
`artifacts/normalized/phase1-minimal-v1/*.md`, tokenizes, and splits into fixed 512-token
chunks.

## Reproducing this build

```bash
python scripts/normalize_development_corpus.py
```

Reads `results/phase_1_1_development_corpus.json` and
`data/edgar_corpus/*.parquet` read-only, performs no network access, writes
only `artifacts/normalized/phase1-minimal-v1/*.md` (git-ignored),
`results/phase_1_2_normalization_summary.json`, and
`configs/normalize_development_corpus.json` (both tracked). Verified to
reproduce an identical `normalization_build_sha256` across independent
fresh-process runs.
