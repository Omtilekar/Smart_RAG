"""Task 2.5 - the authoritative Phase 2 evaluation-result schema: pure
schema/metric definitions, DDL generation, and validation logic (no I/O,
no DB connection opened here - see src/eval/eval_store.py for that).

This module is the single source of truth for:

    - the DuckDB table definitions eval_store.py creates in
      artifacts/eval/eval.duckdb (alongside Task 2.4's pre-existing
      test_access_log, which this module never touches);
    - the metric-definition registry (which metrics are DEFINED,
      IMPLEMENTED, and AVAILABLE_FOR_CURRENT_GOLD - see
      project_plan/PHASE2_EVALUATION_SCHEMA.md for what those mean);
    - the deterministic `evaluation_schema_hash`, computed from this
      module's own data structures (never from DDL string formatting or
      a timestamp), so a semantic schema/metric change always changes
      the hash and a formatting-only change never does;
    - small validation helpers (split values, run status values,
      question-result status values, metric-value ranges) reused by both
      eval_store.py and its tests.

Document-level and chunk/evidence-level relevance are never conflated
anywhere in this schema - see EVAL_QUESTION_RESULTS columns
`doc_first_hit_rank` vs `chunk_first_hit_rank`, and the metric registry's
`chunk_recall@10` entry (`available_for_current_gold=False` - no
chunk-level gold labels exist in this project yet).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

EVALUATION_SCHEMA_VERSION = 1

VALID_SPLITS = ("dev", "test", "ci")
VALID_RUN_STATUSES = ("running", "complete", "failed", "partial", "aborted")
VALID_QUESTION_RESULT_STATUSES = (
    "success",
    "retrieval_error",
    "generation_error",
    "judge_error",
    "timeout",
    "invalid_output",
    "schema_error",
)
VALID_STAGES = ("routing", "embedding", "retrieval", "reranking", "generation", "guard", "total")

# Metrics with a mathematically bounded range - enforced by
# validate_metric_value(); metrics like absolute_error/latency/cost are
# deliberately absent here and never range-checked (Section 51).
_UNIT_INTERVAL_METRIC_PREFIXES = ("doc_recall", "chunk_recall", "doc_mrr", "chunk_mrr", "ndcg", "correct_refusal_rate", "behavior_match_rate")


class SchemaValidationError(ValueError):
    """Raised by this module's validation helpers on malformed evaluation
    evidence (invalid split/status/rank/metric range/etc.)."""


def validate_split(split: str) -> None:
    if split not in VALID_SPLITS:
        raise SchemaValidationError(f"invalid split {split!r}; expected one of {VALID_SPLITS}")


def validate_run_status(status: str) -> None:
    if status not in VALID_RUN_STATUSES:
        raise SchemaValidationError(f"invalid run status {status!r}; expected one of {VALID_RUN_STATUSES}")


def validate_question_result_status(status: str) -> None:
    if status not in VALID_QUESTION_RESULT_STATUSES:
        raise SchemaValidationError(f"invalid question-result status {status!r}; expected one of {VALID_QUESTION_RESULT_STATUSES}")


def validate_stage(stage: str) -> None:
    if stage not in VALID_STAGES:
        raise SchemaValidationError(f"invalid stage {stage!r}; expected one of {VALID_STAGES}")


def validate_rank(rank: int) -> None:
    if not isinstance(rank, int) or rank < 1:
        raise SchemaValidationError(f"rank must be a positive integer >= 1, got {rank!r}")


def validate_metric_value(metric_name: str, value: float | None) -> None:
    if value is None:
        return
    if any(metric_name == p or metric_name.startswith(p + "@") for p in _UNIT_INTERVAL_METRIC_PREFIXES):
        if not (0.0 <= value <= 1.0):
            raise SchemaValidationError(f"metric {metric_name!r} must be in [0,1], got {value!r}")


# --------------------------------------------------------------- table DDL

@dataclass(frozen=True)
class Column:
    name: str
    sql_type: str
    nullable: bool = True
    check: str | None = None


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    primary_key: tuple[str, ...]

    def create_sql(self) -> str:
        lines = []
        for c in self.columns:
            parts = [c.name, c.sql_type]
            if not c.nullable:
                parts.append("NOT NULL")
            if c.check:
                parts.append(f"CHECK ({c.check})")
            lines.append(" ".join(parts))
        pk = f",\n    PRIMARY KEY ({', '.join(self.primary_key)})" if self.primary_key else ""
        body = ",\n    ".join(lines)
        return f"CREATE TABLE IF NOT EXISTS {self.name} (\n    {body}{pk}\n)"


EVAL_SCHEMA_METADATA = Table(
    "eval_schema_metadata",
    (
        Column("schema_version", "INTEGER", nullable=False),
        Column("created_at_utc", "VARCHAR", nullable=False),
        Column("migration_version", "INTEGER", nullable=False),
    ),
    primary_key=("schema_version",),
)

EVAL_RUNS = Table(
    "eval_runs",
    (
        Column("run_id", "VARCHAR", nullable=False),
        Column("timestamp_utc", "VARCHAR", nullable=False),
        Column("git_sha", "VARCHAR"),
        Column("split", "VARCHAR", nullable=False, check=f"split IN {VALID_SPLITS}"),
        Column("eval_set_version", "VARCHAR", nullable=False),
        Column("source_dataset_sha256", "VARCHAR", nullable=False),
        Column("split_version", "VARCHAR", nullable=False),
        Column("split_assignment_sha256", "VARCHAR", nullable=False),
        Column("question_set_sha256", "VARCHAR", nullable=False),
        Column("question_count", "INTEGER", nullable=False),
        Column("expected_question_count", "INTEGER", nullable=False),
        Column("chunk_config_hash", "VARCHAR"),
        Column("index_config_hash", "VARCHAR"),
        Column("retrieval_config_hash", "VARCHAR"),
        Column("embed_model", "VARCHAR"),
        Column("embed_model_revision", "VARCHAR"),
        Column("rerank_model", "VARCHAR"),
        Column("rerank_model_revision", "VARCHAR"),
        Column("rerank_config_hash", "VARCHAR"),
        Column("rerank_k", "INTEGER"),
        Column("generation_provider", "VARCHAR"),
        Column("generation_requested_model", "VARCHAR"),
        Column("generation_response_model", "VARCHAR"),
        Column("generation_prompt_version", "VARCHAR"),
        Column("generation_temperature", "DOUBLE"),
        Column("router_version", "VARCHAR"),
        Column("router_config_hash", "VARCHAR"),
        Column("crag_enabled", "BOOLEAN"),
        Column("crag_config_hash", "VARCHAR"),
        Column("metric_schema_version", "INTEGER", nullable=False),
        Column("test_access_id", "VARCHAR"),
        Column("status", "VARCHAR", nullable=False, check=f"status IN {VALID_RUN_STATUSES}"),
        Column("error_type", "VARCHAR"),
        Column("error_message", "VARCHAR"),
        Column("completed_at_utc", "VARCHAR"),
    ),
    primary_key=("run_id",),
)

EVAL_QUESTION_RESULTS = Table(
    "eval_question_results",
    (
        Column("run_id", "VARCHAR", nullable=False),
        Column("question_id", "VARCHAR", nullable=False),
        Column("category", "VARCHAR", nullable=False),
        Column("subtype", "VARCHAR"),
        Column("answer_type", "VARCHAR"),
        Column("status", "VARCHAR", nullable=False, check=f"status IN {VALID_QUESTION_RESULT_STATUSES}"),
        Column("retrieval_status", "VARCHAR"),
        Column("generation_status", "VARCHAR"),
        Column("latency_ms", "DOUBLE"),
        Column("doc_first_hit_rank", "INTEGER"),
        Column("chunk_first_hit_rank", "INTEGER"),
        Column("retrieved_count", "INTEGER"),
        Column("expected_value", "VARCHAR"),
        Column("expected_unit", "VARCHAR"),
        Column("predicted_value", "VARCHAR"),
        Column("predicted_unit", "VARCHAR"),
        Column("numeric_parse_status", "VARCHAR"),
        Column("absolute_error", "DOUBLE"),
        Column("relative_error", "DOUBLE"),
        Column("exact_match", "BOOLEAN"),
        Column("tolerance_match", "BOOLEAN"),
        Column("expected_behavior", "VARCHAR"),
        Column("observed_behavior", "VARCHAR"),
        Column("correct_refusal", "BOOLEAN"),
        Column("guard_triggered", "BOOLEAN"),
        Column("refusal_observed", "BOOLEAN"),
        Column("behavior_match", "BOOLEAN"),
        Column("answer_text", "VARCHAR"),
        Column("citation_count", "INTEGER"),
        Column("input_tokens", "INTEGER"),
        Column("cached_input_tokens", "INTEGER"),
        Column("output_tokens", "INTEGER"),
        Column("total_tokens", "INTEGER"),
        Column("provider_cost_usd", "DOUBLE"),
        Column("judge_provider", "VARCHAR"),
        Column("judge_model", "VARCHAR"),
        Column("judge_model_revision", "VARCHAR"),
        Column("judge_prompt_version", "VARCHAR"),
        Column("judge_temperature", "DOUBLE"),
        Column("judge_raw_result_ref", "VARCHAR"),
    ),
    primary_key=("run_id", "question_id"),
)

EVAL_RETRIEVED_ITEMS = Table(
    "eval_retrieved_items",
    (
        Column("run_id", "VARCHAR", nullable=False),
        Column("question_id", "VARCHAR", nullable=False),
        Column("rank", "INTEGER", nullable=False, check="rank >= 1"),
        Column("chunk_id", "VARCHAR"),
        Column("document_id", "VARCHAR"),
        Column("cik", "BIGINT"),
        Column("retrieval_score", "DOUBLE"),
        Column("rerank_score", "DOUBLE"),
        Column("retrieval_source", "VARCHAR"),
    ),
    primary_key=("run_id", "question_id", "rank"),
)

EVAL_METRICS = Table(
    "eval_metrics",
    (
        Column("metric_id", "VARCHAR", nullable=False),
        Column("run_id", "VARCHAR", nullable=False),
        Column("metric_name", "VARCHAR", nullable=False),
        Column("metric_version", "VARCHAR", nullable=False),
        Column("scope", "VARCHAR", nullable=False, check="scope IN ('overall', 'category', 'subtype', 'tag', 'year', 'intent')"),
        Column("category", "VARCHAR"),
        Column("subtype", "VARCHAR"),
        Column("tag", "VARCHAR"),
        Column("year", "INTEGER"),
        Column("intent", "VARCHAR"),
        Column("k", "INTEGER"),
        Column("value", "DOUBLE"),
        Column("numerator", "INTEGER"),
        Column("denominator", "INTEGER"),
        Column("notes", "VARCHAR"),
    ),
    primary_key=("metric_id",),
)

EVAL_STAGE_TIMINGS = Table(
    "eval_stage_timings",
    (
        Column("run_id", "VARCHAR", nullable=False),
        Column("question_id", "VARCHAR", nullable=False),
        Column("stage", "VARCHAR", nullable=False, check=f"stage IN {VALID_STAGES}"),
        Column("latency_ms", "DOUBLE", nullable=False, check="latency_ms >= 0"),
    ),
    primary_key=("run_id", "question_id", "stage"),
)

METRIC_DEFINITIONS_TABLE = Table(
    "metric_definitions",
    (
        Column("metric_name", "VARCHAR", nullable=False),
        Column("metric_version", "VARCHAR", nullable=False),
        Column("level", "VARCHAR", nullable=False),
        Column("description", "VARCHAR", nullable=False),
        Column("higher_is_better", "BOOLEAN", nullable=False),
        Column("required_gold_type", "VARCHAR"),
        Column("applicable_categories", "VARCHAR", nullable=False),
        Column("parameters", "VARCHAR"),
        Column("implemented", "BOOLEAN", nullable=False),
        Column("available_for_current_gold", "BOOLEAN", nullable=False),
    ),
    primary_key=("metric_name", "metric_version"),
)

ALL_TABLES: tuple[Table, ...] = (
    EVAL_SCHEMA_METADATA,
    EVAL_RUNS,
    EVAL_QUESTION_RESULTS,
    EVAL_RETRIEVED_ITEMS,
    EVAL_METRICS,
    EVAL_STAGE_TIMINGS,
    METRIC_DEFINITIONS_TABLE,
)


# --------------------------------------------------------------- metric registry
#
# `implemented`: real scoring code exists elsewhere in this repository
# TODAY that computes this metric (not "the schema can store it").
# `available_for_current_gold`: the gold labels this metric needs
# actually exist in the current Task 2.3/2.4 evaluation set TODAY.
# A metric can be available_for_current_gold=True and implemented=False
# (gold exists, scoring code not written yet - e.g. numeric_exact_match)
# or implemented=True and available_for_current_gold=True simultaneously
# (doc_recall@10 - Task 1.10 already computes it against Task 1.9's
# document-level smoke gold). No metric here is marked implemented=True
# unless real code already computes it in this repository.

@dataclass(frozen=True)
class MetricDefinition:
    metric_name: str
    metric_version: str
    level: str
    description: str
    higher_is_better: bool
    required_gold_type: str | None
    applicable_categories: tuple[str, ...]
    parameters: dict = field(default_factory=dict)
    implemented: bool = False
    available_for_current_gold: bool = False

    def as_row(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "metric_version": self.metric_version,
            "level": self.level,
            "description": self.description,
            "higher_is_better": self.higher_is_better,
            "required_gold_type": self.required_gold_type,
            "applicable_categories": ",".join(self.applicable_categories),
            "parameters": json.dumps(self.parameters, sort_keys=True, separators=(",", ":")),
            "implemented": self.implemented,
            "available_for_current_gold": self.available_for_current_gold,
        }


METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        "doc_recall@10", "1.0", "document",
        "Fraction of questions where the gold source document appears anywhere in the top-10 retrieved results.",
        True, "document-level gold (Task 1.9 smoke set)", ("numeric", "comparative", "narrative", "unanswerable"),
        {"k": 10}, implemented=True, available_for_current_gold=True,
    ),
    MetricDefinition(
        "chunk_recall@10", "1.0", "chunk",
        "Fraction of questions where a gold-labeled evidence chunk appears anywhere in the top-10 retrieved chunks.",
        True, "chunk/evidence-level gold (not yet created)", ("numeric", "comparative", "narrative", "unanswerable"),
        {"k": 10}, implemented=True, available_for_current_gold=False,
    ),
    MetricDefinition(
        "doc_mrr", "1.0", "document",
        "Mean reciprocal rank of the first retrieved result whose source document matches the gold document.",
        True, "document-level gold (Task 1.9 smoke set)", ("numeric", "comparative", "narrative", "unanswerable"),
        {}, implemented=True, available_for_current_gold=True,
    ),
    MetricDefinition(
        "chunk_mrr", "1.0", "chunk",
        "Mean reciprocal rank of the first retrieved chunk matching a gold evidence chunk.",
        True, "chunk/evidence-level gold (not yet created)", ("numeric", "comparative", "narrative", "unanswerable"),
        {}, implemented=True, available_for_current_gold=False,
    ),
    MetricDefinition(
        "doc_ndcg@10", "1.0", "document",
        "Normalized discounted cumulative gain (binary relevance) over document-level relevance in the top-10 retrieved results.",
        True, "document-level gold (Task 1.9 smoke set)", ("numeric", "comparative", "narrative", "unanswerable"),
        {"k": 10}, implemented=True, available_for_current_gold=True,
    ),
    MetricDefinition(
        "numeric_exact_match", "1.0", "answer",
        "Exact match (canonical parsed value + unit) between the system's predicted numeric value/unit and the Task 2.3 gold expected_value/expected_unit.",
        True, "Task 2.3 numeric/comparative gold", ("numeric", "comparative"),
        {}, implemented=True, available_for_current_gold=True,
    ),
    MetricDefinition(
        "numeric_tolerance_match", "1.0", "answer",
        "Match between predicted and gold numeric value within a defined relative tolerance.",
        True, "Task 2.3 numeric/comparative gold", ("numeric", "comparative"),
        {}, implemented=False, available_for_current_gold=True,
    ),
    MetricDefinition(
        "correct_refusal_rate", "1.0", "behavior",
        "Fraction of unanswerable/adversarial questions where the system's observed behavior matches the Task 2.3 expected_behavior.",
        True, "Task 2.3 unanswerable/adversarial expected_behavior", ("unanswerable", "adversarial"),
        {}, implemented=True, available_for_current_gold=True,
    ),
    MetricDefinition(
        "citation_format_compliance", "1.0", "answer",
        "Fraction of generated answers whose citation markers match the required format (Task 1.7a/1.8).",
        True, None, ("numeric", "comparative", "narrative"),
        {}, implemented=True, available_for_current_gold=True,
    ),
    MetricDefinition(
        "citation_grounding", "1.0", "answer",
        "Fraction of cited claims verifiably supported by the actual text of the cited chunk.",
        True, "chunk/evidence-level gold (not yet created)", ("numeric", "comparative", "narrative"),
        {}, implemented=False, available_for_current_gold=False,
    ),
    MetricDefinition(
        "faithfulness", "1.0", "narrative",
        "LLM-judge score of whether a narrative answer is faithful to its retrieved context.",
        True, "human-reviewed narrative gold (not yet created - Task 2.3 narrative is pending_review)",
        ("narrative",), {}, implemented=False, available_for_current_gold=False,
    ),
)


def metric_definitions_rows() -> list[dict]:
    return [m.as_row() for m in METRIC_DEFINITIONS]


# --------------------------------------------------------------- schema hash

def canonical_schema_dict() -> dict:
    tables = {}
    for t in ALL_TABLES:
        tables[t.name] = {
            "columns": [
                {"name": c.name, "type": c.sql_type, "nullable": c.nullable, "check": c.check}
                for c in t.columns
            ],
            "primary_key": list(t.primary_key),
        }
    return {
        "evaluation_schema_version": EVALUATION_SCHEMA_VERSION,
        "tables": tables,
        "metric_definitions": [m.as_row() for m in METRIC_DEFINITIONS],
        "valid_splits": list(VALID_SPLITS),
        "valid_run_statuses": list(VALID_RUN_STATUSES),
        "valid_question_result_statuses": list(VALID_QUESTION_RESULT_STATUSES),
        "valid_stages": list(VALID_STAGES),
    }


def compute_evaluation_schema_hash() -> str:
    payload = json.dumps(canonical_schema_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
