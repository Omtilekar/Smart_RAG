"""Task 1.7 - real end-to-end generation smoke: Task 1.6 retriever +
OpenRouter provider.

Requires GENERATION_PROVIDER=openrouter, an explicit GENERATION_MODEL, and
OPENROUTER_API_KEY, all from the process environment. Refuses to run (and
never invents a model choice) if any is missing. Sends only the question
and the top-5 retrieved chunk context to the provider - never the API key,
never more than the approved context, never raw filing text beyond those
5 chunks.
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import get_settings  # noqa: E402
from src.storage import get_storage  # noqa: E402
from src.logging_utils import configure_logging, get_logger, log_event  # noqa: E402
from src.embeddings.bge import load_model  # noqa: E402
from src.index.lancedb_index import open_database, open_chunk_table  # noqa: E402
from src.retrieval.baseline import BaselineRetriever  # noqa: E402
from src.generation.openrouter import OpenRouterProvider, API_KEY_ENV_VAR  # noqa: E402
from src.generation.minimal import MinimalGenerator  # noqa: E402

CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
MODEL_REPO = "BAAI/bge-small-en-v1.5"

SMOKE_QUESTIONS = [
    "What was the company's total revenue?",
    "What are the main risk factors described in this filing?",
    "What was net income for the fiscal year?",
    "How much did the company spend on research and development?",
    "Does this filing mention any information about employee stock purchase plans in ancient Rome?",
]

SUMMARY_RELATIVE_PATH = Path("results") / "phase_1_7_generation_summary.json"

log = get_logger(__name__)


def main() -> int:
    configure_logging()
    settings = get_settings()

    if (settings.generation_provider or "").strip().lower() != "openrouter":
        print(
            "FATAL: GENERATION_PROVIDER must be set to 'openrouter' for this smoke script.",
            file=sys.stderr,
        )
        return 1
    model = (settings.generation_model or "").strip()
    if not model:
        print("FATAL: GENERATION_MODEL is not set. Refusing to guess a model.", file=sys.stderr)
        return 1
    if not os.environ.get(API_KEY_ENV_VAR, "").strip():
        print(f"FATAL: {API_KEY_ENV_VAR} is not set.", file=sys.stderr)
        return 1

    storage = get_storage()
    db_path = storage.index_dir(CHUNK_CONFIG_HASH, MODEL_REPO)
    storage.require_dir(db_path)
    db = open_database(db_path)
    table = open_chunk_table(db)

    embed_model = load_model(device="cuda")
    retriever = BaselineRetriever(model=embed_model, table=table)
    provider = OpenRouterProvider(model=model)
    generator = MinimalGenerator(retriever, provider)

    log_event(log, logging.INFO, "generation_smoke_start", provider="openrouter", model=model,
              question_count=len(SMOKE_QUESTIONS))

    results = []
    retrieval_latencies, provider_latencies, total_latencies = [], [], []
    response_model = None
    total_prompt_tokens = total_completion_tokens = total_tokens = 0
    any_usage = False

    for q in SMOKE_QUESTIONS:
        t0 = time.perf_counter()
        gen_result, provider_response, retrieval_ms = generator._answer_with_diagnostics(q)
        total_ms = (time.perf_counter() - t0) * 1000

        if provider_response is None:
            # Task 4.8 - the context guard rejected this question's
            # retrieved evidence before any provider call was made. Never
            # expected with the real frozen index (chunk_id/document_id/
            # text are NOT NULL there), but handled defensively rather
            # than crashing on a None dereference below.
            log_event(log, logging.WARNING, "generation_smoke_context_guard_rejected", question_preview=q[:60])
            print(f"\nQ: {q}")
            print(f"A: {gen_result.answer} (context guard rejected - no provider call made)")
            results.append({"question": q, "answer": gen_result.answer, "citations": gen_result.citations, "abstained": True})
            continue

        retrieval_latencies.append(retrieval_ms)
        provider_latencies.append(provider_response.latency_ms)
        total_latencies.append(total_ms)
        response_model = provider_response.response_model or response_model
        if provider_response.total_tokens is not None:
            any_usage = True
            total_prompt_tokens += provider_response.prompt_tokens or 0
            total_completion_tokens += provider_response.completion_tokens or 0
            total_tokens += provider_response.total_tokens or 0

        # Best-effort heuristic for the smoke script's own informational
        # labeling only - not part of the public GenerationResult contract,
        # and not a claim that this reliably detects every abstention
        # phrasing the model might use.
        answer_lower = gen_result.answer.lower()
        abstained = not gen_result.citations and any(
            phrase in answer_lower for phrase in (
                "not enough information",
                "does not contain enough information",
                "does not provide",
                "insufficient information",
                "cannot be determined from",
            )
        )
        log_event(log, logging.INFO, "generation_smoke_answer", question_preview=q[:60],
                  citation_count=len(gen_result.citations), abstained=abstained,
                  elapsed_ms=round(total_ms, 1))

        results.append({
            "question": q,
            "answer": gen_result.answer,
            "citations": gen_result.citations,
            "abstained": abstained,
        })

        print(f"\nQ: {q}")
        print(f"A: {gen_result.answer}")
        print(f"Citations: {gen_result.citations}")

    def p50_p95(values):
        s = sorted(values)
        return {
            "p50_ms": round(statistics.median(s), 2),
            "p95_ms": round(s[int(0.95 * (len(s) - 1))], 2) if len(s) > 1 else round(s[0], 2),
        }

    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": "Phase 1 generation smoke diagnostic - NOT a production benchmark",
        "provider": "openrouter",
        "requested_model": model,
        "response_reported_model": response_model,
        "retriever_k": 5,
        "citation_format": "inline [chunk_id]",
        "abstention_policy": "concise natural-language insufficiency statement, citations=[]",
        "temperature_requested": 0.0,
        "live_smoke_performed": True,
        "live_smoke_count": len(SMOKE_QUESTIONS),
        "results": results,
        "retrieval_latency": p50_p95(retrieval_latencies),
        "provider_latency": p50_p95(provider_latencies),
        "total_latency": p50_p95(total_latencies),
        "token_usage": {
            "prompt_tokens": total_prompt_tokens, "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
        } if any_usage else None,
    }
    summary_path = storage.repo_root / SUMMARY_RELATIVE_PATH
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"\nRequested model: {model}  |  Response-reported model: {response_model}")
    print(f"Retrieval p50={summary['retrieval_latency']['p50_ms']}ms  "
          f"Provider p50={summary['provider_latency']['p50_ms']}ms  "
          f"Total p50={summary['total_latency']['p50_ms']}ms")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
