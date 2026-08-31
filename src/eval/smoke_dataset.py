"""Task 1.9 - deterministic Phase 1 smoke-evaluation dataset builder (pure logic).

Builds a 200-question, document-level "which filing should this question
retrieve" smoke set from the frozen Task 1.1 development corpus. This is
NOT the final benchmark, NOT chunk-level ground truth, and NOT an XBRL
truth contract - see project_plan/PHASE1_SMOKE_EVALUATION.md.

Deliberately offline and deterministic: fixed question templates, no LLM,
no randomness. Selection uses SHA-256 over (category, document_id) - never
Python's built-in hash() (unstable across processes/versions), never a
PRNG (unreproducible without recording a seed).

This module contains no I/O and no dependency on DuckDB/EDGAR-CORPUS
parquet directly - callers (scripts/build_smoke_evaluation.py) resolve raw
source rows and pass them in as plain dicts, so every function here is
testable with small synthetic fixtures and no local data.
"""

from __future__ import annotations

import hashlib
import json

CATEGORY_ORDER: tuple[str, ...] = (
    "business",
    "risk_factors",
    "mdna",
    "market_risk",
    "financial_statements",
)

CATEGORY_SECTION_COLUMN: dict[str, str] = {
    "business": "section_1",
    "risk_factors": "section_1A",
    "mdna": "section_7",
    "market_risk": "section_7A",
    "financial_statements": "section_8",
}

# One template per category (template_id == category name - no second
# template variant exists per category in this Phase 1 baseline).
QUESTION_TEMPLATES: dict[str, str] = {
    "business": "What does {company} report about its business in its fiscal year {fiscal_year} 10-K?",
    "risk_factors": "What risk factors does {company} report in its fiscal year {fiscal_year} 10-K?",
    "mdna": "What does {company} report in Management's Discussion and Analysis for fiscal year {fiscal_year}?",
    "market_risk": "What does {company} report about quantitative and qualitative market risk in its fiscal year {fiscal_year} 10-K?",
    "financial_statements": "What financial statements and related information does {company} report for fiscal year {fiscal_year}?",
}

QUESTIONS_PER_CATEGORY = 40
TARGET_QUESTION_COUNT = 200
QUESTION_ID_PREFIX = "phase1-smoke-"
LABEL_GRANULARITY = "document"
RETRIEVAL_METRIC = "doc_recall@10"
TARGET_FORM_TYPE = "10-K"


def is_eligible_section(value) -> bool:
    """A source section is eligible only when it is a non-null, non-empty,
    non-whitespace-only string. Never coerces None/other types."""
    return isinstance(value, str) and value.strip() != ""


def selection_key(category: str, document_id: str) -> str:
    """SHA-256 hex digest over "{category}\\0{document_id}" (UTF-8). Never
    Python's built-in hash() - that is process/PYTHONHASHSEED-dependent and
    not reproducible across runs or machines."""
    payload = (category + "\0" + document_id).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_source_section_sha256(section_text: str) -> str:
    """SHA-256 over the exact UTF-8 source-section string used for
    eligibility - provenance only, not chunk-level ground truth."""
    return hashlib.sha256(section_text.encode("utf-8")).hexdigest()


def render_question(category: str, company: str, fiscal_year) -> str:
    """Renders the frozen template for `category`. Never paraphrased by an
    LLM; never exposes the target document ID in the question text."""
    template = QUESTION_TEMPLATES[category]
    return template.format(company=company, fiscal_year=fiscal_year)


def build_category_candidates(category: str, filings: list[dict], source_rows: dict[str, dict]) -> list[dict]:
    """Returns the subset of `filings` (Task 1.1 manifest rows) eligible for
    `category`: the assigned EDGAR-CORPUS section column, resolved via
    `source_rows[document_id][section_column]`, must be a non-empty string.
    Preserves input (manifest) order - selection order is decided
    separately by `selection_key`."""
    section_col = CATEGORY_SECTION_COLUMN[category]
    candidates = []
    for row in filings:
        section_text = source_rows[row["document_id"]][section_col]
        if is_eligible_section(section_text):
            candidates.append(row)
    return candidates


def select_for_category(
    category: str, candidates: list[dict], used_document_ids: set[str], per_category: int = QUESTIONS_PER_CATEGORY,
) -> list[dict]:
    """Sorts `candidates` by ascending `selection_key(category, document_id)`,
    skips any document_id already in `used_document_ids` (cross-category
    uniqueness), and takes the first `per_category`. Returns fewer than
    `per_category` rows if the pool is exhausted - callers must check the
    returned length rather than assume success."""
    ordered = sorted(candidates, key=lambda r: selection_key(category, r["document_id"]))
    selected: list[dict] = []
    for row in ordered:
        if row["document_id"] in used_document_ids:
            continue
        selected.append(row)
        if len(selected) == per_category:
            break
    return selected


def select_all_categories(
    filings: list[dict],
    source_rows: dict[str, dict],
    category_order: tuple[str, ...] = CATEGORY_ORDER,
    per_category: int = QUESTIONS_PER_CATEGORY,
) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Processes categories in `category_order`, maintaining one running
    `used_document_ids` set so the same filing is never selected for two
    categories. Returns (selected_by_category, candidate_counts) where
    candidate_counts records the *pre-selection* eligible-pool size per
    category (Step 9's required diagnostic), before cross-category
    exclusion is applied.

    Raises ValueError - never silently rebalances categories or relaxes
    uniqueness - if any category cannot supply `per_category` unused
    eligible candidates."""
    candidate_counts: dict[str, int] = {}
    selected_by_category: dict[str, list[dict]] = {}
    used: set[str] = set()
    for category in category_order:
        candidates = build_category_candidates(category, filings, source_rows)
        candidate_counts[category] = len(candidates)
        selected = select_for_category(category, candidates, used, per_category)
        if len(selected) < per_category:
            raise ValueError(
                f"category {category!r} produced only {len(selected)} unused eligible candidate(s), "
                f"needs {per_category} (eligible pool size {len(candidates)}, "
                f"{len(used)} document(s) already used by earlier categories)"
            )
        used.update(row["document_id"] for row in selected)
        selected_by_category[category] = selected
    return selected_by_category, candidate_counts


def build_question_record(
    category: str,
    row: dict,
    source_rows: dict[str, dict],
    *,
    development_manifest_sha256: str,
    normalizer_version: str,
    normalization_build_sha256: str,
) -> dict:
    """Builds one Step-13-schema question record (without `question_id` -
    assigned globally afterward by `assign_question_ids`). Never adds
    target_chunk_id, accession, expected_answer, or answer_span."""
    section_col = CATEGORY_SECTION_COLUMN[category]
    section_text = source_rows[row["document_id"]][section_col]
    question = render_question(category, row["company_name"], row["year"])
    return {
        "question": question,
        "category": category,
        "template_id": category,
        "source_section_column": section_col,
        "target_document_id": row["document_id"],
        "target_cik": row["cik"],
        "target_company": row["company_name"],
        "target_form_type": TARGET_FORM_TYPE,
        "target_fiscal_year": row["year"],
        "target_source_filename": row["source_filename"],
        "target_source_split": row["source_split"],
        "label_granularity": LABEL_GRANULARITY,
        "retrieval_metric": RETRIEVAL_METRIC,
        "development_manifest_sha256": development_manifest_sha256,
        "normalizer_version": normalizer_version,
        "normalization_build_sha256": normalization_build_sha256,
        "source_section_sha256": compute_source_section_sha256(section_text),
    }


def assign_question_ids(records: list[dict], category_order: tuple[str, ...] = CATEGORY_ORDER) -> list[dict]:
    """Orders `records` by (category order, target_document_id ascending)
    and assigns question_id = "phase1-smoke-0001".."phase1-smoke-0200".
    Returns new dicts with question_id as the first key (cosmetic only -
    JSON object key order is not semantically significant)."""
    category_rank = {c: i for i, c in enumerate(category_order)}
    ordered = sorted(records, key=lambda r: (category_rank[r["category"]], r["target_document_id"]))
    out = []
    for i, record in enumerate(ordered, start=1):
        question_id = f"{QUESTION_ID_PREFIX}{i:04d}"
        out.append({"question_id": question_id, **record})
    return out


def canonical_records_json(records: list[dict]) -> bytes:
    """Canonical UTF-8 JSON of the logical question records only - sorted
    keys, stable separators, no timestamps. Same convention already used
    for development_manifest_sha256/normalization_build_sha256/
    chunk_config_hash."""
    return json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_smoke_eval_sha256(records: list[dict]) -> str:
    return hashlib.sha256(canonical_records_json(records)).hexdigest()
