"""Tests for src/guards/output.py (Task 4.9).

Portable, deterministic, no network/model/LLM anywhere. Covers every
guard category PROJECT_EXECUTION.md's Task 4.9 checklist requires,
translated into the collapsed rule set documented in the module's own
docstring (see that docstring for exactly which roadmap item maps to
which check).
"""

import pytest

from src.guards.output import OutputGuardDecision, REASON_CODES, check_dense_output, check_structured_numeric_output
from src.guards.context import check_xbrl_context
from src.sql.xbrl_lookup import XbrlLookupResult

SUPPLIED = {"doc0.htm::chunk0", "doc1.htm::chunk1", "doc2.htm::chunk2"}


# ------------------------------------------------------------- valid cases

def test_valid_cited_answer_allowed():
    d = check_dense_output("Revenue was $1M. [doc0.htm::chunk0]", ["doc0.htm::chunk0"], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is True
    assert d.reason_code is None


def test_valid_answer_citing_multiple_supplied_chunks_allowed():
    text = "Revenue was $1M [doc0.htm::chunk0] and net income was $200K [doc1.htm::chunk1]."
    d = check_dense_output(text, ["doc0.htm::chunk0", "doc1.htm::chunk1"], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is True


def test_zero_citation_abstention_allowed():
    # "do not require a citation for a legitimate abstention unless the
    # roadmap explicitly says otherwise" - it does not.
    text = "The supplied context does not contain enough information to answer this question."
    d = check_dense_output(text, [], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is True
    assert d.reason_code is None


def test_zero_citation_substantive_looking_answer_still_allowed():
    # Documented, deliberate limitation: this module cannot distinguish a
    # legitimate abstention from a hallucinated uncited claim without an
    # LLM judge (explicitly out of scope) - so it does not try, and never
    # blocks solely for the ABSENCE of a citation.
    text = "The company's revenue grew significantly last year."
    d = check_dense_output(text, [], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is True


# ------------------------------------------------------------- unknown citation

def test_citation_not_in_supplied_context_rejected():
    d = check_dense_output(
        "Revenue was $1M. [doc9.htm::chunk9]", ["doc9.htm::chunk9"], supplied_chunk_ids=SUPPLIED,
    )
    assert d.allowed is False
    assert d.reason_code == "unknown_citation"


def test_citation_valid_elsewhere_in_corpus_but_not_supplied_here_rejected():
    # Explicit roadmap instruction: "the relevant set is the evidence
    # supplied to the answer" - existence elsewhere in the corpus is
    # irrelevant. This test doesn't need real index access to prove that
    # - `supplied_chunk_ids` alone determines the outcome.
    d = check_dense_output(
        "Revenue was $1M. [doc0.htm::chunk0]", ["doc0.htm::chunk0"], supplied_chunk_ids={"doc1.htm::chunk1"},
    )
    assert d.allowed is False
    assert d.reason_code == "unknown_citation"


def test_one_bad_citation_among_valid_ones_fails_whole_answer():
    text = "Revenue was $1M [doc0.htm::chunk0] and X was Y [doc9.htm::chunk9]."
    d = check_dense_output(text, ["doc0.htm::chunk0", "doc9.htm::chunk9"], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is False
    assert d.reason_code == "unknown_citation"


# ------------------------------------------------------------- malformed citation

def test_fullwidth_bracket_citation_rejected():
    d = check_dense_output("Revenue was $1M. 【doc0.htm::chunk0】", [], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is False
    assert d.reason_code == "malformed_citation"


def test_truncated_chunk_id_citation_rejected():
    d = check_dense_output("Revenue was $1M. [chunk0]", [], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is False
    assert d.reason_code == "malformed_citation"


def test_context_label_imitation_citation_rejected():
    # Task 1.7a's documented historical failure form. Per Task 1.8's own
    # documented finding (src/eval/citation_integrity.py's module
    # docstring): "[chunk_id: X]" is syntactically STRICT-VALID by the
    # parser (it matches the whole bracket interior including the
    # "chunk_id: " prefix) - so it surfaces here as unknown_citation (the
    # literal string "chunk_id: doc0.htm::chunk0" is never a real
    # supplied chunk_id), not as malformed_citation. Still a hard
    # rejection either way.
    d = check_dense_output(
        "Revenue was $1M. [chunk_id: doc0.htm::chunk0]", ["chunk_id: doc0.htm::chunk0"], supplied_chunk_ids=SUPPLIED,
    )
    assert d.allowed is False
    assert d.reason_code == "unknown_citation"


def test_ordinary_markdown_brackets_not_treated_as_malformed():
    d = check_dense_output("See [Note 1] for details. [doc0.htm::chunk0]", ["doc0.htm::chunk0"], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is True


# ------------------------------------------------------------- unsupported advice

ADVICE_FIXTURES = [
    "This is a good time to invest in this company.",
    "This stock will beat earnings next quarter for sure.",
    "This is a better investment than its competitors.",
    "I have a confident prediction that this company will go bankrupt.",
]


@pytest.mark.parametrize("text", ADVICE_FIXTURES)
def test_unsupported_advice_in_output_rejected(text):
    d = check_dense_output(text, [], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is False
    assert d.reason_code == "unsupported_advice"


def test_known_limitation_second_person_advice_phrasing_not_caught():
    # Documented, deliberate limitation (see module docstring): reusing
    # src.router.rules.ADVICE_KEYWORDS verbatim - rather than inventing a
    # new, independently-decided output-specific keyword set - means
    # phrasings the list wasn't designed to catch (second-person "you
    # should..." advice, which the list's first-person "should i..."
    # entries don't match) slip through. Recorded here as an honest,
    # visible gap, not silently hidden.
    text = "You should definitely buy this stock right now."
    d = check_dense_output(text, [], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is True  # known gap, not a passing safety guarantee


def test_factual_stock_price_answer_not_advice():
    d = check_dense_output(
        "The closing stock price mentioned in the filing was $50. [doc0.htm::chunk0]",
        ["doc0.htm::chunk0"], supplied_chunk_ids=SUPPLIED,
    )
    assert d.reason_code != "unsupported_advice"
    assert d.allowed is True


def test_legitimate_filing_language_with_similar_vocabulary_not_rejected():
    text = (
        "The filing states the company's investment portfolio grew and its "
        "financial system was assessed as effective. [doc0.htm::chunk0]"
    )
    d = check_dense_output(text, ["doc0.htm::chunk0"], supplied_chunk_ids=SUPPLIED)
    assert d.allowed is True


# ------------------------------------------------------------- structured route re-export

def test_check_structured_numeric_output_is_check_xbrl_context():
    assert check_structured_numeric_output is check_xbrl_context


def test_check_structured_numeric_output_valid_found_result_allowed():
    result = XbrlLookupResult(outcome="found", cik=1000, fiscal_year=2019, tag="Assets",
                               value=100.0, unit="USD", adsh="0000320193-24-000123", company="ACME")
    d = check_structured_numeric_output(result)
    assert d.allowed is True


def test_check_structured_numeric_output_missing_provenance_rejected():
    result = XbrlLookupResult(outcome="found", cik=1000, fiscal_year=2019, tag="Assets",
                               value=100.0, unit="USD", adsh=None, company="ACME")
    d = check_structured_numeric_output(result)
    assert d.allowed is False
    assert d.reason_code == "missing_provenance"


# ------------------------------------------------------------- determinism

@pytest.mark.parametrize("text,citations", [
    ("Revenue was $1M. [doc0.htm::chunk0]", ["doc0.htm::chunk0"]),
    ("Revenue was $1M. [doc9.htm::chunk9]", ["doc9.htm::chunk9"]),
    ("Revenue was $1M. 【doc0.htm::chunk0】", []),
    ("You should buy this stock.", []),
    ("Not enough information to answer.", []),
])
def test_decision_is_deterministic(text, citations):
    first = check_dense_output(text, citations, supplied_chunk_ids=SUPPLIED)
    for _ in range(5):
        assert check_dense_output(text, citations, supplied_chunk_ids=SUPPLIED) == first


def test_stable_reason_codes_are_all_declared():
    fixtures = [
        ("Revenue. [doc9.htm::chunk9]", ["doc9.htm::chunk9"]),
        ("Revenue. 【doc0.htm::chunk0】", []),
        ("You should buy this stock.", []),
    ]
    for text, citations in fixtures:
        d = check_dense_output(text, citations, supplied_chunk_ids=SUPPLIED)
        if not d.allowed:
            assert d.reason_code in REASON_CODES


# ------------------------------------------------------------- no fabrication/mutation

def test_check_dense_output_never_mutates_inputs():
    text = "Revenue was $1M. [doc0.htm::chunk0]"
    citations = ["doc0.htm::chunk0"]
    supplied = set(SUPPLIED)
    check_dense_output(text, citations, supplied_chunk_ids=supplied)
    assert citations == ["doc0.htm::chunk0"]
    assert supplied == SUPPLIED


# ------------------------------------------------------------- logging

def test_logging_never_includes_raw_answer_text(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="src.guards.output")
    check_dense_output("Confidential internal figure was $999,999,999. [doc0.htm::chunk0]",
                        ["doc0.htm::chunk0"], supplied_chunk_ids=SUPPLIED)
    for record in caplog.records:
        assert "999,999,999" not in record.getMessage()


def test_logging_includes_decision_metadata(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="src.guards.output")
    check_dense_output("Revenue was $1M. [doc0.htm::chunk0]", ["doc0.htm::chunk0"], supplied_chunk_ids=SUPPLIED)
    messages = [r.getMessage() for r in caplog.records]
    assert any("output_guard_decision" in m and "allowed=true" in m for m in messages)
