"""Tests for src/generation/minimal.py and src/generation/citations.py.

Fake retriever/provider objects only - no network, no real model, no real
API key. Mirrors tests/test_baseline_retriever.py's fake-injection style.
"""

import pytest

from src.generation.citations import parse_citations
from src.generation.minimal import MinimalGenerator, GenerationResult, SYSTEM_PROMPT
from src.generation.provider import GenerationError, GenerationRequest, ProviderResponse
from src.retrieval.baseline import RetrievalResult


def _make_result(i: int) -> RetrievalResult:
    return RetrievalResult(
        rank=i + 1, score=0.9 - i * 0.05, distance=0.1 + i * 0.05,
        chunk_id=f"doc{i}.htm::chunk{i}", document_id=f"doc{i}.htm",
        text=f"chunk text number {i} about revenue.", cik=1000 + i,
        company=f"COMPANY {i}", form_type="10-K", fiscal_year=2018 + i,
        source="edgar_corpus", source_filename=f"doc{i}.htm", source_split="train",
        ordinal=i, token_count=10, chunk_config_hash="abc123",
        normalizer_version="phase1-minimal-v1",
        normalization_build_sha256="x" * 64, development_manifest_sha256="y" * 64,
    )


class FakeRetriever:
    def __init__(self, results=None):
        self.calls = []
        self._results = results if results is not None else [_make_result(i) for i in range(5)]

    def retrieve(self, question, k=5):
        self.calls.append({"question": question, "k": k})
        return self._results


class FakeProvider:
    def __init__(self, text="Revenue grew. [doc0.htm::chunk0]"):
        self.calls = []
        self._text = text

    def generate(self, request: GenerationRequest) -> ProviderResponse:
        self.calls.append(request)
        return ProviderResponse(
            text=self._text, requested_model="fake/model", response_model="fake/model-v1",
            provider_name="fake", response_provider=None, prompt_tokens=100,
            completion_tokens=20, total_tokens=120, temperature_requested=request.temperature,
            latency_ms=1.0,
        )


class ErroringProvider:
    def generate(self, request):
        raise GenerationError("simulated provider failure")


# ------------------------------------------------------------------ retrieval

def test_retriever_called_with_k_5():
    retriever = FakeRetriever()
    gen = MinimalGenerator(retriever, FakeProvider())
    gen.answer("what was revenue")
    assert retriever.calls == [{"question": "what was revenue", "k": 5}]


def test_provider_called_exactly_once():
    provider = FakeProvider()
    gen = MinimalGenerator(FakeRetriever(), provider)
    gen.answer("what was revenue")
    assert len(provider.calls) == 1


def test_question_included_in_prompt():
    provider = FakeProvider()
    gen = MinimalGenerator(FakeRetriever(), provider)
    gen.answer("what was revenue in 2020")
    assert "what was revenue in 2020" in provider.calls[0].user_prompt


def test_all_five_chunk_ids_in_prompt():
    provider = FakeProvider()
    gen = MinimalGenerator(FakeRetriever(), provider)
    gen.answer("question")
    prompt = provider.calls[0].user_prompt
    for i in range(5):
        assert f"doc{i}.htm::chunk{i}" in prompt


def test_all_five_chunk_texts_in_prompt():
    provider = FakeProvider()
    gen = MinimalGenerator(FakeRetriever(), provider)
    gen.answer("question")
    prompt = provider.calls[0].user_prompt
    for i in range(5):
        assert f"chunk text number {i} about revenue." in prompt


# ------------------------------------------------------------------- prompt

def test_grounding_instruction_present():
    assert "only the supplied context" in SYSTEM_PROMPT.lower()


def test_outside_knowledge_prohibition_present():
    assert "outside knowledge" in SYSTEM_PROMPT.lower()


def test_citation_instruction_present():
    assert "[chunk_id]" in SYSTEM_PROMPT


def test_abstention_instruction_present():
    assert "not enough information" in SYSTEM_PROMPT.lower() or "not contain enough information" in SYSTEM_PROMPT.lower()


def test_no_chain_of_thought_instruction():
    lowered = SYSTEM_PROMPT.lower()
    assert "step by step" not in lowered
    assert "reasoning" not in lowered


# -------------------------------------------------------------------- result

def test_generation_result_has_answer_and_citations():
    gen = MinimalGenerator(FakeRetriever(), FakeProvider(text="Revenue grew. [doc0.htm::chunk0]"))
    result = gen.answer("question")
    assert isinstance(result, GenerationResult)
    assert result.answer == "Revenue grew. [doc0.htm::chunk0]"
    assert result.citations == ["doc0.htm::chunk0"]


def test_citation_parsing_multiple():
    gen = MinimalGenerator(FakeRetriever(), FakeProvider(
        text="A. [doc0.htm::chunk0] B. [doc1.htm::chunk1]"
    ))
    result = gen.answer("question")
    assert result.citations == ["doc0.htm::chunk0", "doc1.htm::chunk1"]


def test_citation_duplicate_deduplication_first_occurrence_order():
    gen = MinimalGenerator(FakeRetriever(), FakeProvider(
        text="A. [doc1.htm::chunk1] B. [doc0.htm::chunk0] C. [doc1.htm::chunk1]"
    ))
    result = gen.answer("question")
    assert result.citations == ["doc1.htm::chunk1", "doc0.htm::chunk0"]


def test_abstention_returns_empty_citations():
    gen = MinimalGenerator(FakeRetriever(), FakeProvider(
        text="The provided context does not contain enough information to answer."
    ))
    result = gen.answer("unanswerable question")
    assert result.citations == []
    assert result.answer


def test_no_vector_in_result_or_prompt():
    result = GenerationResult(answer="x", citations=[])
    assert not hasattr(result, "vector")
    provider = FakeProvider()
    gen = MinimalGenerator(FakeRetriever(), provider)
    gen.answer("question")
    assert "vector" not in provider.calls[0].user_prompt.lower()


# --------------------------------------------------------------------- input

def test_empty_question_rejected():
    gen = MinimalGenerator(FakeRetriever(), FakeProvider())
    with pytest.raises(ValueError):
        gen.answer("")


def test_whitespace_question_rejected():
    gen = MinimalGenerator(FakeRetriever(), FakeProvider())
    with pytest.raises(ValueError):
        gen.answer("   ")


def test_non_string_question_rejected():
    gen = MinimalGenerator(FakeRetriever(), FakeProvider())
    with pytest.raises(TypeError):
        gen.answer(123)


# -------------------------------------------------------------- provider errors

def test_provider_error_propagates():
    gen = MinimalGenerator(FakeRetriever(), ErroringProvider())
    with pytest.raises(GenerationError):
        gen.answer("question")


# --------------------------------------------------------------- citation parser

def test_parse_citations_single():
    assert parse_citations("Revenue rose. [doc.htm::chunk1]") == ["doc.htm::chunk1"]


def test_parse_citations_multiple_in_order():
    text = "A. [doc.htm::chunk1] B. [doc.htm::chunk2]"
    assert parse_citations(text) == ["doc.htm::chunk1", "doc.htm::chunk2"]


def test_parse_citations_dedup_first_occurrence():
    text = "A. [doc.htm::chunk1] B. [doc.htm::chunk1]"
    assert parse_citations(text) == ["doc.htm::chunk1"]


def test_parse_citations_ignores_unrelated_brackets():
    text = "See [Note 1] and [this link](http://example.com) for details. [doc.htm::chunk3]"
    assert parse_citations(text) == ["doc.htm::chunk3"]


def test_parse_citations_no_citations_returns_empty_list():
    assert parse_citations("No citations here.") == []


def test_parse_citations_does_not_parse_markdown_links():
    text = "[markdown link](http://example.com/page::chunknope)"
    assert parse_citations(text) == []


def test_parse_citations_requires_chunk_suffix_with_digits():
    # bracket contains "::chunk" but no trailing digits - must not match
    text = "See [doc.htm::chunk] for details."
    assert parse_citations(text) == []
