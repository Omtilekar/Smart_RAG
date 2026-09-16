"""Task 1.11 - Phase 1 end-to-end local CLI. No FastAPI, no server.

    python -m src.cli.phase1 answer --question "..."
    python -m src.cli.phase1 evaluate

`answer` composes the existing Task 1.6 retriever (k=5, MinimalGenerator's
own frozen generation-context default - never Task 1.10's k=10) with Task
1.7/1.7a's MinimalGenerator + OpenRouterProvider. No retrieval or
generation logic is reimplemented here.

`evaluate` delegates to Task 1.10's scripts.run_baseline_metric.run() -
the frozen doc_recall@10 implementation is not duplicated.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import get_settings  # noqa: E402
from src.storage import get_storage  # noqa: E402
from src.embeddings.bge import load_model  # noqa: E402
from src.index.lancedb_index import open_database, open_chunk_table  # noqa: E402
from src.retrieval.baseline import BaselineRetriever  # noqa: E402
from src.generation.openrouter import OpenRouterProvider, API_KEY_ENV_VAR  # noqa: E402
from src.generation.provider import GenerationError  # noqa: E402
from src.generation.minimal import MinimalGenerator  # noqa: E402
from src.guards.input import check_input_with_settings  # noqa: E402
from src.eval.citation_integrity import (  # noqa: E402
    RecordingRetriever,
    LanceDBResolvers,
    evaluate_citation_integrity,
)

CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
MODEL_REPO = "BAAI/bge-small-en-v1.5"
EVALUATE_RESULT_RELATIVE_PATH = Path("results") / "phase_1_11_smoke_evaluation.json"


def _construct_generator(settings, *, record_context: bool):
    """Composes the real Task 1.5/1.6/1.7 stack. Never reimplements
    retrieval or generation - just wires already-tested classes together,
    the same way scripts/smoke_generation.py and
    scripts/smoke_citation_integrity.py already do. Returns
    (generator, recorder_or_None, table) - `recorder` is populated only
    when `record_context` is True (Task 1.8's RecordingRetriever, reused
    exactly, never reimplemented)."""
    storage = get_storage()
    db_path = storage.index_dir(CHUNK_CONFIG_HASH, MODEL_REPO)
    storage.require_dir(db_path)
    db = open_database(db_path)
    table = open_chunk_table(db)
    embed_model = load_model(device="cuda")
    real_retriever = BaselineRetriever(model=embed_model, table=table)
    recorder = RecordingRetriever(real_retriever) if record_context else None
    provider = OpenRouterProvider(model=settings.generation_model)
    generator = MinimalGenerator(recorder if recorder is not None else real_retriever, provider)
    return generator, recorder, table


def cmd_answer(question: str, *, generator=None, dump_context_path: str | None = None) -> int:
    """Task 1.11 `answer` subcommand body. `generator` is an injectable
    seam for portable tests (fakes) - real invocations build it from the
    live stack. `dump_context_path` is diagnostic-only (mirrors
    MinimalGenerator._answer_with_diagnostics's own precedent of a
    non-public diagnostic path, PHASE1_GENERATION.md) - not part of the
    documented Phase 1 answer contract, and defaults to off. When set, it
    wraps retrieval with Task 1.8's RecordingRetriever (never a second
    provider call) so the exact supplied top-5 chunk IDs for this same
    generation call can be written out for mechanical citation-integrity
    verification (used for Task 1.11's own one-time live demo check)."""
    # Task 4.7 - the input-guardrail boundary. Runs before ANY downstream
    # work (generator construction included - that loads the embedding
    # model and opens LanceDB) so a rejected question never reaches
    # routing/retrieval/generation. Supersedes the old inline
    # type/empty-only check - GuardDecision.reason_code now covers that
    # case (and five more) with a stable, machine-readable code.
    decision = check_input_with_settings(question)
    if not decision.allowed:
        print(f"error: input rejected ({decision.reason_code}): {decision.detail}", file=sys.stderr)
        return 2

    recorder = None
    table = None
    if generator is None:
        settings = get_settings()
        provider_name = (settings.generation_provider or "").strip().lower()
        if provider_name != "openrouter":
            print(f"error: unsupported GENERATION_PROVIDER: {settings.generation_provider!r}", file=sys.stderr)
            return 1
        model = (settings.generation_model or "").strip()
        if not model:
            print("error: GENERATION_MODEL is not set", file=sys.stderr)
            return 1
        if not os.environ.get(API_KEY_ENV_VAR, "").strip():
            print(f"error: {API_KEY_ENV_VAR} is not set in the environment", file=sys.stderr)
            return 1
        try:
            generator, recorder, table = _construct_generator(settings, record_context=bool(dump_context_path))
        except Exception as e:
            print(f"error: failed to initialize retriever/generator: {e}", file=sys.stderr)
            return 1

    try:
        result = generator.answer(question)
    except GenerationError as e:
        print(f"error: generation failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print("Answer:")
    print(result.answer)
    print()
    print("Citations:")
    if result.citations:
        for chunk_id in result.citations:
            print(f"- {chunk_id}")
    else:
        print("(none)")

    if dump_context_path and recorder is not None and table is not None:
        supplied = recorder.last_results or []
        resolvers = LanceDBResolvers(table)
        check = evaluate_citation_integrity(
            answer=result.answer,
            generation_citations=result.citations,
            supplied_chunk_ids={r.chunk_id for r in supplied},
            exists_fn=resolvers.exists,
            metadata_fn=resolvers.metadata,
            abstention_expected=False,
        )
        payload = {
            "question": question,
            "answer": result.answer,
            "parsed_citations": result.citations,
            "supplied_chunk_ids": sorted(r.chunk_id for r in supplied),
            "case_status": check.status,
            "failure_reasons": check.failure_reasons,
            "malformed_citation_attempts": [a.raw for a in check.malformed_attempts],
        }
        Path(dump_context_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    return 0


def cmd_evaluate() -> int:
    from scripts.run_baseline_metric import run as run_baseline_metric
    result = run_baseline_metric(result_relative_path=EVALUATE_RESULT_RELATIVE_PATH)
    print(f"question_count: {result['question_count']}")
    print(f"hit_count: {result['hit_count']}")
    print(f"doc_recall@10: {result['doc_recall_at_10']:.6f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli.phase1",
        description="Phase 1 SEC RAG - one-command answer and 200-question evaluation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    answer_parser = sub.add_parser(
        "answer", help="Answer a question: Task 1.6 vector retrieval (k=5) + Task 1.7a generation.",
    )
    answer_parser.add_argument("--question", required=True, help="Natural-language question.")
    answer_parser.add_argument("--dump-context", default=None, metavar="PATH", help=argparse.SUPPRESS)

    sub.add_parser(
        "evaluate", help="Run the frozen Task 1.9/1.10 200-question doc_recall@10 evaluation.",
    )

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "answer":
        return cmd_answer(args.question, dump_context_path=args.dump_context)
    if args.command == "evaluate":
        return cmd_evaluate()
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
