"""Task 1.7 - minimal grounded generation orchestrator.

Composes question -> Task 1.6 top-5 retrieval -> minimal grounded prompt ->
one provider call -> parsed citations -> GenerationResult. One retrieval
call and one provider call per answer() - no retries, no self-repair, no
multi-candidate generation (those are explicitly out of scope for the
Phase 1 baseline).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from src.guards.context import check_dense_context, format_evidence_block
from src.guards.output import check_dense_output

from .citations import parse_citations
from .provider import GenerationProvider, GenerationRequest, ProviderResponse

RETRIEVAL_K = 5

# Task 4.8 - the context guard's fixed abstention-safe outcome. Never a
# provider call, never a fabricated citation - matches this project's
# existing abstention shape (empty citations + a plain insufficiency
# statement), just triggered by the context guard instead of the model.
CONTEXT_GUARD_ABSTENTION_MESSAGE = (
    "The retrieved context did not pass the context-safety check and "
    "cannot be used to answer this question."
)

# Task 4.9 - the output guard's fixed abstention-safe outcome. The
# provider WAS called here (unlike the context-guard case above) - its
# real ProviderResponse (latency/token diagnostics) is still returned to
# _answer_with_diagnostics()'s caller; only the public GenerationResult's
# answer/citations are replaced, never the raw blocked text ("Preserve
# Diagnostic Separation": internal diagnostics may keep provider
# metadata, the public answer contract must not leak a blocked answer).
OUTPUT_GUARD_ABSTENTION_MESSAGE = (
    "The generated answer did not pass the output-safety check and "
    "cannot be released."
)

# Minimal grounded prompt contract (Task 1.7 Step 14) - deliberately no
# chain-of-thought, no tool/browsing instructions.
SYSTEM_PROMPT = (
    "Use only the supplied context to answer the question. Do not use outside knowledge.\n"
    "Answer the user's question directly.\n"
    "Cite every factual claim that relies on the supplied context using the format "
    "[chunk_id] (a literal chunk ID inside square brackets, nothing else inside the "
    "brackets), using only chunk IDs that appear in the supplied context.\n"
    "Citation format rules, all mandatory:\n"
    "1. Citation brackets must use the plain ASCII characters \"[\" and \"]\" only.\n"
    "2. Never use the fullwidth characters 【 and 】 for citations.\n"
    "3. Copy the complete Chunk ID exactly as shown in the supplied context - never "
    "shorten or truncate it and never drop the document_id prefix.\n"
    "4. Put nothing else inside the brackets - no labels, no prefixes, no extra words.\n"
    "Valid citation format: [1158114_2016.htm::chunk106]\n"
    "Invalid - fullwidth brackets: 【1158114_2016.htm::chunk106】\n"
    "Invalid - truncated: [chunk106]\n"
    "Invalid - extra text inside brackets: [chunk_id: 1158114_2016.htm::chunk106]\n"
    "These examples show formatting only - your actual citations must use only chunk "
    "IDs that appear in the supplied context.\n"
    "Before finishing your answer, check that every citation uses ASCII square "
    "brackets and contains an exact, complete Chunk ID copied from the supplied "
    "context.\n"
    "If the supplied context does not contain enough information to answer, say so "
    "directly in one or two sentences and do not invent an answer or a citation."
)


@dataclass(frozen=True)
class GenerationResult:
    """Public Phase 1 answer contract - deliberately minimal. Never
    includes the raw provider response, API key, full prompt, or
    retrieval vectors."""
    answer: str
    citations: list[str]


def _validate_question(question) -> None:
    if not isinstance(question, str):
        raise TypeError(f"question must be a str, got {type(question).__name__}")
    if not question.strip():
        raise ValueError("question must not be empty or whitespace-only")


def _format_context(retrieved_results) -> str:
    """One clearly-delimited block per retrieved chunk (Task 4.8 -
    "clearly delimit retrieved evidence", src.guards.context.
    format_evidence_block()): the exact chunk_id the model must cite
    verbatim, light provenance for grounding, then the chunk text,
    wrapped in explicit BEGIN/END boundary markers so retrieved
    (untrusted) content can never be confused with instructions or with
    a different chunk's boundary - even if the chunk's own text contains
    phrases shaped like markers or instructions.

    Deliberately does NOT wrap "Chunk ID:" in square brackets - an
    earlier version used "[chunk_id: X]" as the label, and the live smoke
    test (Task 1.7) showed the model imitating that exact bracketed label
    shape as its citation (e.g. "[chunk_id: 1425627_2018.htm::chunk9]")
    instead of the instructed bare "[X]" form. Removing brackets from the
    context label measurably reduced this - verified by re-running the
    same live smoke questions after this change - and
    format_evidence_block()'s own boundary markers were deliberately
    chosen to avoid reintroducing that exact shape."""
    blocks = [
        format_evidence_block(
            chunk_id=r.chunk_id, company=r.company, fiscal_year=r.fiscal_year,
            document_id=r.document_id, text=r.text,
        )
        for r in retrieved_results
    ]
    return "\n\n".join(blocks)


class MinimalGenerator:
    """Composes a Task 1.6 retriever with a GenerationProvider. Not
    coupled to generation or retrieval; retrieval always uses k=5
    (RETRIEVAL_K) and the vector-only path - no reranking, no routing."""

    def __init__(self, retriever, provider: GenerationProvider):
        self._retriever = retriever
        self._provider = provider

    def answer(self, question: str) -> GenerationResult:
        result, _provider_response, _retrieval_ms = self._answer_with_diagnostics(question)
        return result

    def _answer_with_diagnostics(self, question: str) -> tuple[GenerationResult, ProviderResponse | None, float]:
        """Same as answer(), but also returns the raw ProviderResponse
        (None if the Task 4.8 context guard rejected the retrieved
        evidence - see below) and retrieval latency (ms) for
        smoke-diagnostic reporting. Not part of the public Phase 1 answer
        contract - callers needing provenance (scripts/smoke_generation.py)
        use this directly; ordinary callers use answer()."""
        _validate_question(question)

        t0 = time.perf_counter()
        retrieved = self._retriever.retrieve(question, k=RETRIEVAL_K)
        retrieval_ms = (time.perf_counter() - t0) * 1000

        # Task 4.8 - the context guard: AFTER evidence acquisition, BEFORE
        # provider.generate(...). Never expected to reject with the real
        # frozen index (chunk_id/document_id/text are NOT NULL there,
        # Task 1.4/1.5's own schema) - this is defense-in-depth, tested
        # with synthetic malformed fixtures, not a live production path.
        context_decision = check_dense_context(retrieved)
        if not context_decision.allowed:
            result = GenerationResult(answer=CONTEXT_GUARD_ABSTENTION_MESSAGE, citations=[])
            return result, None, retrieval_ms

        user_prompt = f"Question: {question}\n\nContext:\n{_format_context(retrieved)}"
        request = GenerationRequest(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, temperature=0.0)
        provider_response = self._provider.generate(request)

        citations = parse_citations(provider_response.text)

        # Task 4.9 - the output guard: AFTER provider.generate(...) exists,
        # BEFORE the answer is released through the public GenerationResult.
        # The provider response itself (latency/token diagnostics) is still
        # returned below even on rejection - only the public answer/citations
        # are replaced, never the raw blocked text.
        supplied_chunk_ids = {r.chunk_id for r in retrieved}
        output_decision = check_dense_output(provider_response.text, citations, supplied_chunk_ids=supplied_chunk_ids)
        if not output_decision.allowed:
            result = GenerationResult(answer=OUTPUT_GUARD_ABSTENTION_MESSAGE, citations=[])
            return result, provider_response, retrieval_ms

        result = GenerationResult(answer=provider_response.text, citations=citations)
        return result, provider_response, retrieval_ms
