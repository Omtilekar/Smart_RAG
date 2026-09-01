"""Task 2.3 - build the full Phase 2 evaluation dataset.

Composes exactly two already-frozen sources - Task 2.1's
`src.eval.truth_contract.eligible_facts()` and Task 2.2's
`configs/eval_tags.yaml` registry - into five question categories
(numeric, comparative, narrative, unanswerable, adversarial). Never asks
the current retriever/generator "what can you answer" - see
src/eval/evaluation_dataset.py's module docstring and
project_plan/PHASE2_EVALUATION_DATASET.md for the full design rationale.

The narrative category makes real, paid OpenRouter calls (one per
narrative question) using the same provider/model as Phase 1
(GENERATION_PROVIDER=openrouter, GENERATION_MODEL). Every other category
is fully deterministic and local - no network, no LLM.

Narrative questions are written with status="pending_review", never
"accepted" - no genuine human review step exists in this pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import get_settings  # noqa: E402
from src.eval.tag_registry import get_registry  # noqa: E402
from src.eval.truth_contract import (  # noqa: E402
    eligible_facts,
    build_contract_config,
    compute_contract_config_hash,
    SUPPORTED_FISCAL_YEAR_MIN,
    SUPPORTED_FISCAL_YEAR_MAX,
)
from src.eval import evaluation_dataset as ed  # noqa: E402
from src.eval.evaluation_dataset import Provenance  # noqa: E402

SCHEMA_VERSION = "1.0"
XBRL_DB_PATH = Path("data") / "xbrl.duckdb"
MANIFEST_RELATIVE_PATH = Path("results") / "phase_1_1_development_corpus.json"
DATASET_RELATIVE_PATH = Path("results") / "phase_2_3_evaluation_dataset.json"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_2_3_evaluation_dataset_summary.json"
CONFIG_RELATIVE_PATH = Path("configs") / "phase_2_3_evaluation_dataset.json"
NARRATIVE_PROMPT_VERSION = "1.0"

CATEGORY_ORDER = ed.CATEGORY_ORDER
NARRATIVE_SECTIONS = ("section_1", "section_1A", "section_7", "section_7A")

OUT_OF_WINDOW_YEARS = (2014, 2022, 2013, 2023)


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def _split_quota(total: int, n_buckets: int) -> list[int]:
    """Deterministic remainder distribution: first (total % n_buckets)
    buckets get one extra, in the caller's own fixed bucket order."""
    base = total // n_buckets
    remainder = total % n_buckets
    return [base + 1 if i < remainder else base for i in range(n_buckets)]


# --------------------------------------------------------------- numeric

def build_numeric(con, registry, prov: Provenance) -> list[dict]:
    tags = registry.supported_tags()
    quotas = dict(zip(tags, _split_quota(ed.NUMERIC_TOTAL, len(tags))))
    records = []
    for tag in tags:
        spec = registry.get(tag)
        facts = eligible_facts(con, [tag])
        by_cik: dict[int, list] = {}
        for f in facts:
            by_cik.setdefault(f.cik, []).append(f)
        representative = []
        for cik, group in by_cik.items():
            group.sort(key=lambda f: f.adsh)
            representative.append(group[0])
        representative.sort(key=lambda f: ed.selection_key(tag, str(f.cik)))
        selected = representative[: quotas[tag]]
        for f in selected:
            records.append(ed.build_numeric_record(fact=f, label=spec.label, period_type=spec.period_type, prov=prov))
    return records


# ----------------------------------------------------------- comparative

def build_comparative_yoy(con, registry, prov: Provenance) -> list[dict]:
    tags = registry.supported_tags()
    quotas = dict(zip(tags, _split_quota(ed.COMPARATIVE_YOY_TOTAL, len(tags))))
    years = list(range(SUPPORTED_FISCAL_YEAR_MIN, SUPPORTED_FISCAL_YEAR_MAX + 1))
    records = []
    for tag in tags:
        spec = registry.get(tag)
        facts = eligible_facts(con, [tag])
        by_cik_year: dict[int, dict[int, object]] = {}
        for f in facts:
            by_cik_year.setdefault(f.cik, {})[f.fiscal_year] = f
        candidates = []
        for cik, year_map in by_cik_year.items():
            for y in years[:-1]:
                if y in year_map and (y + 1) in year_map:
                    candidates.append((ed.selection_key(tag, str(cik), str(y)), cik, y, year_map[y], year_map[y + 1]))
        candidates.sort(key=lambda c: c[0])
        for _, cik, y, fact_a, fact_b in candidates[: quotas[tag]]:
            records.append(ed.build_yoy_record(
                tag=tag, label=spec.label, company=fact_a.company, cik=cik,
                fact_a=fact_a, fact_b=fact_b, prov=prov,
            ))
    return records


def build_comparative_cross_entity(con, registry, prov: Provenance) -> list[dict]:
    tags = registry.supported_tags()
    quotas = dict(zip(tags, _split_quota(ed.COMPARATIVE_CROSS_ENTITY_TOTAL, len(tags))))
    years = list(range(SUPPORTED_FISCAL_YEAR_MIN, SUPPORTED_FISCAL_YEAR_MAX + 1))
    records = []
    for tag in tags:
        spec = registry.get(tag)
        facts = eligible_facts(con, [tag])
        by_year: dict[int, list] = {}
        for f in facts:
            by_year.setdefault(f.fiscal_year, []).append(f)
        pairs = []
        for y in years:
            group = by_year.get(y, [])
            if len(group) < 2:
                continue
            group_sorted = sorted(group, key=lambda f: ed.selection_key(tag, str(y), str(f.cik)))
            for i in range(0, len(group_sorted) - 1, 2):
                pairs.append((ed.selection_key(tag, str(y), str(group_sorted[i].cik)), group_sorted[i], group_sorted[i + 1]))
        pairs.sort(key=lambda p: p[0])
        for _, fact_a, fact_b in pairs[: quotas[tag]]:
            records.append(ed.build_cross_entity_record(tag=tag, label=spec.label, fact_a=fact_a, fact_b=fact_b, prov=prov))
    return records


# --------------------------------------------------------------- unanswerable

def build_unanswerable_year(con, registry, prov: Provenance) -> list[dict]:
    tags = registry.supported_tags()
    quotas = dict(zip(tags, _split_quota(ed.UNANSWERABLE_YEAR_TOTAL, len(tags))))
    records = []
    for idx, tag in enumerate(tags):
        spec = registry.get(tag)
        facts = eligible_facts(con, [tag])
        by_cik: dict[int, object] = {}
        for f in facts:
            if f.cik not in by_cik:
                by_cik[f.cik] = f
        candidates = sorted(by_cik.values(), key=lambda f: ed.selection_key("unans_year", tag, str(f.cik)))
        for i, f in enumerate(candidates[: quotas[tag]]):
            year = OUT_OF_WINDOW_YEARS[(idx + i) % len(OUT_OF_WINDOW_YEARS)]
            records.append(ed.build_unanswerable_year_record(
                tag=tag, label=spec.label, period_type=spec.period_type,
                company=f.company, cik=f.cik, out_of_window_year=year, prov=prov,
            ))
    return records


def build_unanswerable_tag(con, registry, prov: Provenance) -> list[dict]:
    per_unsupported = ed.UNANSWERABLE_TAG_TOTAL // len(ed.UNSUPPORTED_TAG_CANDIDATES)
    # use Assets (near-universal coverage) as the source of real companies
    facts = eligible_facts(con, ["Assets"])
    by_cik: dict[int, object] = {}
    for f in facts:
        if f.cik not in by_cik:
            by_cik[f.cik] = f
    records = []
    for unsupported_tag, phrase in ed.UNSUPPORTED_TAG_CANDIDATES:
        candidates = sorted(by_cik.values(), key=lambda f: ed.selection_key("unans_tag", unsupported_tag, str(f.cik)))
        for f in candidates[:per_unsupported]:
            records.append(ed.build_unanswerable_tag_record(
                unsupported_tag=unsupported_tag, phrase=phrase, company=f.company,
                cik=f.cik, fiscal_year=f.fiscal_year, prov=prov,
            ))
    return records


# ---------------------------------------------------------------- adversarial

def build_adversarial(con, registry, prov: Provenance) -> list[dict]:
    facts = eligible_facts(con, ["Assets"])
    by_cik: dict[int, object] = {}
    for f in facts:
        if f.cik not in by_cik:
            by_cik[f.cik] = f
    companies_sorted = sorted(by_cik.values(), key=lambda f: ed.selection_key("adversarial_company", str(f.cik)))

    records = []
    templates = ed.ADVERSARIAL_TEMPLATES["prompt_injection"][: ed.ADVERSARIAL_PROMPT_INJECTION_TOTAL]
    for t in templates:
        records.append(ed.build_adversarial_record(subtype="prompt_injection", template=t, company=None, prov=prov))

    templates = ed.ADVERSARIAL_TEMPLATES["off_scope"][: ed.ADVERSARIAL_OFF_SCOPE_TOTAL]
    for t in templates:
        records.append(ed.build_adversarial_record(subtype="off_scope", template=t, company=None, prov=prov))

    templates = ed.ADVERSARIAL_TEMPLATES["financial_advice"][: ed.ADVERSARIAL_FINANCIAL_ADVICE_TOTAL]
    for i, t in enumerate(templates):
        company = companies_sorted[i % len(companies_sorted)].company
        records.append(ed.build_adversarial_record(subtype="financial_advice", template=t, company=company, prov=prov))

    return records


# ----------------------------------------------------------------- narrative

def build_narrative(storage_repo_root: Path, prov: Provenance) -> list[dict]:
    from src.generation.openrouter import OpenRouterProvider, API_KEY_ENV_VAR
    from src.generation.provider import GenerationRequest, GenerationError

    settings = get_settings()
    provider_name = (settings.generation_provider or "").strip().lower()
    model = (settings.generation_model or "").strip()
    if provider_name != "openrouter" or not model or not os.environ.get(API_KEY_ENV_VAR, "").strip():
        print("WARNING: narrative generation skipped - GENERATION_PROVIDER/GENERATION_MODEL/"
              f"{API_KEY_ENV_VAR} not fully configured. 0 narrative questions produced.", file=sys.stderr)
        return []

    manifest_path = storage_repo_root / MANIFEST_RELATIVE_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filings = manifest["filings"]

    con = duckdb.connect()
    con.execute("PRAGMA disable_progress_bar")
    edgar_root = storage_repo_root / "data" / "edgar_corpus"
    splits = {s: edgar_root / f"{s}.parquet" for s in ("train", "test", "validation")}
    existing = {s: p for s, p in splits.items() if p.exists()}
    union_sql = " UNION ALL ".join(
        f"SELECT '{s}' AS split, * FROM read_parquet('{p.as_posix()}')" for s, p in existing.items()
    )
    con.execute(f"CREATE TEMP TABLE edgar AS SELECT * FROM ({union_sql})")

    candidates = []
    for filing in filings:
        doc_id = filing["document_id"]
        for section in NARRATIVE_SECTIONS:
            candidates.append((ed.selection_key("narrative", doc_id, section), filing, section))
    candidates.sort(key=lambda c: c[0])

    provider = OpenRouterProvider(model=model)
    system_prompt = (
        "You are given an excerpt from a company's SEC 10-K filing. Write exactly ONE specific, "
        "factual question that a reader could answer using ONLY the information in this excerpt. "
        "Do not include the answer. Do not mention that this is an excerpt or a filing. Output only "
        "the question text, nothing else - no preamble, no quotation marks."
    )

    records = []
    attempts = 0
    for _, filing, section in candidates:
        if len(records) >= ed.NARRATIVE_TOTAL:
            break
        attempts += 1
        doc_id = filing["document_id"]
        row = con.execute(f"SELECT {section} FROM edgar WHERE filename = ?", [doc_id]).fetchone()
        if row is None or not row[0] or not row[0].strip():
            continue
        text = row[0].strip()
        excerpt = text[:3000]
        section_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        user_prompt = f"Filing excerpt:\n\n{excerpt}"
        try:
            response = provider.generate(GenerationRequest(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0))
        except GenerationError as e:
            print(f"WARNING: narrative generation call failed for {doc_id}/{section}: {e}", file=sys.stderr)
            continue
        question = response.text.strip().strip('"')
        if not question or len(question) > 400 or "\n" in question:
            continue

        records.append(ed.build_narrative_record(
            question=question, cik=filing["cik"], company=filing["company_name"],
            fiscal_year=filing["year"], document_id=doc_id, source_section_column=section,
            source_section_sha256=section_hash, provider="openrouter", requested_model=model,
            response_model=response.response_model, prompt_version=NARRATIVE_PROMPT_VERSION, prov=prov,
        ))

    con.close()
    print(f"narrative: {len(records)} questions generated from {attempts} attempted OpenRouter calls")
    return records


def main() -> int:
    db_path = REPO_ROOT / XBRL_DB_PATH
    if not db_path.is_file():
        raise SystemExit(f"FATAL: XBRL database not found at {db_path}")

    registry = get_registry()
    supported = registry.supported_tags()
    contract_config = build_contract_config(supported)
    truth_contract_hash = compute_contract_config_hash(contract_config)
    from src.eval.tag_registry import compute_registry_hash
    prov = Provenance(
        registry_version=registry.version,
        registry_hash=compute_registry_hash(registry),
        truth_contract_version=contract_config["contract_version"],
        truth_contract_hash=truth_contract_hash,
    )

    con = duckdb.connect(str(db_path), read_only=True)

    t0 = time.perf_counter()
    numeric = build_numeric(con, registry, prov)
    comparative = build_comparative_yoy(con, registry, prov) + build_comparative_cross_entity(con, registry, prov)
    unanswerable = build_unanswerable_year(con, registry, prov) + build_unanswerable_tag(con, registry, prov)
    adversarial = build_adversarial(con, registry, prov)
    narrative = build_narrative(REPO_ROOT, prov)
    build_seconds = time.perf_counter() - t0

    con.close()

    all_records = numeric + comparative + narrative + unanswerable + adversarial
    records_with_ids = ed.assign_question_ids(all_records)
    ed.check_no_leakage(records_with_ids)
    ed.check_no_duplicate_questions(records_with_ids)

    dataset_sha256 = ed.compute_dataset_sha256(records_with_ids)

    dataset = {
        "schema_version": SCHEMA_VERSION,
        "eval_set_version": ed.EVAL_SET_VERSION,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "dataset_sha256": dataset_sha256,
        "registry_version": prov.registry_version,
        "registry_hash": prov.registry_hash,
        "truth_contract_version": prov.truth_contract_version,
        "truth_contract_hash": prov.truth_contract_hash,
        "question_count": len(records_with_ids),
        "questions": records_with_ids,
    }

    dataset_path = REPO_ROOT / DATASET_RELATIVE_PATH
    if dataset_path.exists():
        existing = json.loads(dataset_path.read_text(encoding="utf-8"))
        if existing.get("dataset_sha256") != dataset_sha256:
            raise SystemExit(
                f"FATAL: {dataset_path} already exists with a different dataset_sha256 "
                f"({existing.get('dataset_sha256')} != {dataset_sha256}) - refusing to silently "
                f"overwrite a conflicting Task 2.3 dataset. STOP AND ASK before proceeding."
            )
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")

    # --------------------------------------------------------------- summary
    def counts_by(field):
        out: dict[str, int] = {}
        for r in records_with_ids:
            key = str(r.get(field))
            out[key] = out.get(key, 0) + 1
        return out

    unique_ciks = {r["cik"] for r in records_with_ids if r.get("cik") is not None}
    unique_companies = {r["company"] for r in records_with_ids if r.get("company") is not None}
    unique_accessions = {r["accession"] for r in records_with_ids if r.get("accession")}
    per_cik_counts: dict[int, int] = {}
    per_accession_counts: dict[str, int] = {}
    for r in records_with_ids:
        if r.get("cik") is not None:
            per_cik_counts[r["cik"]] = per_cik_counts.get(r["cik"], 0) + 1
        if r.get("accession"):
            per_accession_counts[r["accession"]] = per_accession_counts.get(r["accession"], 0) + 1

    narrative_accepted = sum(1 for r in records_with_ids if r["category"] == "narrative" and r.get("status") == "accepted")
    narrative_pending = sum(1 for r in records_with_ids if r["category"] == "narrative" and r.get("status") == "pending_review")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "eval_set_version": ed.EVAL_SET_VERSION,
        "created_at_utc": dataset["created_at_utc"],
        "git_sha": dataset["git_sha"],
        "dataset_sha256": dataset_sha256,
        "question_count": len(records_with_ids),
        "counts_by_category": counts_by("category"),
        "counts_by_subtype": counts_by("subtype"),
        "counts_by_year": counts_by("fiscal_year"),
        "counts_by_tag": counts_by("tag"),
        "counts_by_answer_type": counts_by("answer_type"),
        "narrative_accepted_count": narrative_accepted,
        "narrative_pending_review_count": narrative_pending,
        "unique_ciks": len(unique_ciks),
        "unique_companies": len(unique_companies),
        "unique_accessions": len(unique_accessions),
        "max_questions_per_cik": max(per_cik_counts.values()) if per_cik_counts else 0,
        "max_questions_per_accession": max(per_accession_counts.values()) if per_accession_counts else 0,
        "registry_version": prov.registry_version,
        "registry_hash": prov.registry_hash,
        "truth_contract_version": prov.truth_contract_version,
        "truth_contract_hash": prov.truth_contract_hash,
        "build_config_hash": None,  # filled in below once config is written
        "template_version": ed.GENERATOR_VERSION,
        "build_seconds": round(build_seconds, 3),
    }

    # ---------------------------------------------------------------- config
    build_config = {
        "eval_set_version": ed.EVAL_SET_VERSION,
        "category_targets": {
            "numeric": ed.NUMERIC_TOTAL,
            "comparative_year_over_year": ed.COMPARATIVE_YOY_TOTAL,
            "comparative_cross_entity": ed.COMPARATIVE_CROSS_ENTITY_TOTAL,
            "narrative": ed.NARRATIVE_TOTAL,
            "unanswerable_year_outside_window": ed.UNANSWERABLE_YEAR_TOTAL,
            "unanswerable_unsupported_tag": ed.UNANSWERABLE_TAG_TOTAL,
            "adversarial_prompt_injection": ed.ADVERSARIAL_PROMPT_INJECTION_TOTAL,
            "adversarial_financial_advice": ed.ADVERSARIAL_FINANCIAL_ADVICE_TOTAL,
            "adversarial_off_scope": ed.ADVERSARIAL_OFF_SCOPE_TOTAL,
        },
        "year_window": [SUPPORTED_FISCAL_YEAR_MIN, SUPPORTED_FISCAL_YEAR_MAX],
        "selection_key_format": "sha256(purpose + '\\0' + ...identifying parts), ascending",
        "numeric_selection_rule": "one fact per (tag, cik) [lowest adsh], sorted by selection_key(tag, cik), first N per tag",
        "comparative_yoy_rule": "same (cik, tag) with both fiscal_year Y and Y+1 eligible; difference = value(Y+1) - value(Y)",
        "comparative_cross_entity_rule": "two distinct CIKs, same tag and fiscal_year, both eligible; expected_answer = company with the greater value",
        "unanswerable_year_rule": f"a real eligible company, asked about a fiscal year outside [{SUPPORTED_FISCAL_YEAR_MIN}, {SUPPORTED_FISCAL_YEAR_MAX}]",
        "unanswerable_tag_rule": "a real eligible company, asked about a real XBRL concept not in configs/eval_tags.yaml",
        "adversarial_rule": "deterministic hand-reviewed templates; financial_advice templates reused across real companies",
        "narrative_rule": (
            "LLM-assisted (OpenRouter, same provider/model as Phase 1), one call per question, "
            "from real EDGAR-CORPUS section_1/1A/7/7A text; status=pending_review always, never accepted"
        ),
        "arithmetic_rule": "Python float64 (matches source XBRL DOUBLE column); exact value serialized via repr() for deterministic round-trip; difference = later_year - earlier_year, no rounding",
        "materiality_policy": "none applied - Task 2.1's exclusion of materiality from truth validity is preserved; Task 2.3 does not introduce a magnitude/sampling filter",
        "no_dev_test_split": "PROJECT_EXECUTION.md Task 2.4 owns the company-disjoint DEV/TEST split; this dataset is split-ready (cik/fiscal_year/category/tag preserved) but not split",
    }
    config_path = REPO_ROOT / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    build_config_hash = hashlib.sha256(
        json.dumps(build_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    build_config_with_hash = {**build_config, "build_config_hash": build_config_hash}
    config_path.write_text(json.dumps(build_config_with_hash, indent=2) + "\n", encoding="utf-8")
    summary["build_config_hash"] = build_config_hash

    summary_path = REPO_ROOT / SUMMARY_RELATIVE_PATH
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"question_count: {len(records_with_ids)}")
    for cat in CATEGORY_ORDER:
        print(f"  {cat}: {summary['counts_by_category'].get(cat, 0)}")
    print(f"unique CIKs: {len(unique_ciks)}  unique accessions: {len(unique_accessions)}")
    print(f"dataset_sha256: {dataset_sha256}")
    print(f"build_config_hash: {build_config_hash}")
    print(f"Dataset written to: {dataset_path}")
    print(f"Config written to: {config_path}")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
