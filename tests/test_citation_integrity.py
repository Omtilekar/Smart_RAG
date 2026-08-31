"""Tests for src/eval/citation_integrity.py.

Portable: fake supplied-context sets and exists_fn/metadata_fn resolvers
only - no GPU, no real LanceDB, no OpenRouter, no API key, no network.
Regression cases reproduce the exact malformed forms Task 1.7's real live
smoke observed.
"""

import pytest

from src.eval.citation_integrity import (
    RecordingRetriever,
    detect_citation_attempts,
    evaluate_citation_integrity,
)

REAL_ID = "1158114_2016.htm::chunk106"
OTHER_ID = "1425627_2018.htm::chunk9"
UNKNOWN_ID = "does-not-exist_2099.htm::chunk999999"


def _resolvers(known_ids: set[str]):
    def exists_fn(chunk_id):
        return chunk_id in known_ids

    def metadata_fn(chunk_id):
        return {"chunk_id": chunk_id, "document_id": chunk_id.split("::")[0]} if chunk_id in known_ids else None

    return exists_fn, metadata_fn


# ---------------------------------------------------- detect_citation_attempts

def test_detects_valid_ascii_marker():
    attempts = detect_citation_attempts(f"Revenue grew. [{REAL_ID}]")
    assert len(attempts) == 1
    assert attempts[0].strict_valid is True
    assert attempts[0].bracket_style == "ascii"


def test_detects_fullwidth_marker_as_invalid():
    attempts = detect_citation_attempts(f"Revenue grew. 【{REAL_ID}】")
    assert len(attempts) == 1
    assert attempts[0].strict_valid is False
    assert attempts[0].bracket_style == "fullwidth"
    assert attempts[0].raw == f"【{REAL_ID}】"


def test_detects_truncated_chunk63_as_invalid():
    attempts = detect_citation_attempts("R&D was $157.4M. [chunk63]")
    assert len(attempts) == 1
    assert attempts[0].strict_valid is False
    assert attempts[0].token == "chunk63"


def test_context_label_form_is_actually_strict_valid_with_wrong_content():
    # Documents the real discrepancy from the task's own framing: the
    # strict parser DOES accept "[chunk_id: X]" syntactically (its content
    # matches [^\[\]]+::chunk\d+), producing citation string
    # "chunk_id: X" - not rejected as malformed at the attempt-detection
    # stage. It fails downstream as unknown_chunk_id instead (see the
    # dedicated test below). Verified against the real Task 1.7 code, not
    # assumed.
    label_form = f"[chunk_id: {REAL_ID}]"
    attempts = detect_citation_attempts(f"See {label_form}")
    assert len(attempts) == 1
    assert attempts[0].strict_valid is True
    assert attempts[0].token == f"chunk_id: {REAL_ID}"


def test_ordinary_brackets_not_detected():
    attempts = detect_citation_attempts("See [note] for [2024] [revenue] details.")
    assert attempts == []


def test_multiple_attempts_mixed_validity():
    text = f"[{REAL_ID}] then 【{REAL_ID}】 then [chunk63]"
    attempts = detect_citation_attempts(text)
    assert len(attempts) == 3
    valid = [a for a in attempts if a.strict_valid]
    invalid = [a for a in attempts if not a.strict_valid]
    assert len(valid) == 1
    assert len(invalid) == 2


# ------------------------------------------------------- evaluate_citation_integrity

def test_valid_citation_exists_and_supplied_passes():
    exists_fn, metadata_fn = _resolvers({REAL_ID})
    result = evaluate_citation_integrity(
        answer=f"Revenue grew. [{REAL_ID}]",
        generation_citations=[REAL_ID],
        supplied_chunk_ids={REAL_ID},
        exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "PASS"
    assert result.failure_reasons == []
    assert result.citation_checks[0].exists_in_index is True
    assert result.citation_checks[0].was_supplied is True
    assert result.citation_checks[0].source_metadata is not None


def test_valid_citation_unknown_fails():
    exists_fn, metadata_fn = _resolvers(set())  # nothing exists
    result = evaluate_citation_integrity(
        answer=f"Answer. [{UNKNOWN_ID}]",
        generation_citations=[UNKNOWN_ID],
        supplied_chunk_ids=set(),
        exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "FAIL"
    assert "unknown_chunk_id" in result.failure_reasons
    assert result.citation_checks[0].exists_in_index is False
    assert result.citation_checks[0].source_metadata is None


def test_valid_citation_exists_but_not_supplied_fails_out_of_context():
    exists_fn, metadata_fn = _resolvers({REAL_ID})  # exists globally
    result = evaluate_citation_integrity(
        answer=f"Answer. [{REAL_ID}]",
        generation_citations=[REAL_ID],
        supplied_chunk_ids={OTHER_ID},  # but NOT supplied to this call
        exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "FAIL"
    assert result.failure_reasons == ["citation_not_in_supplied_context"]
    assert "unknown_chunk_id" not in result.failure_reasons
    assert result.citation_checks[0].exists_in_index is True
    assert result.citation_checks[0].was_supplied is False
    assert result.citation_checks[0].source_metadata is not None


def test_unknown_and_out_of_context_are_distinct_reason_codes():
    exists_fn, metadata_fn = _resolvers({REAL_ID})
    unknown_result = evaluate_citation_integrity(
        answer=f"[{UNKNOWN_ID}]", generation_citations=[UNKNOWN_ID],
        supplied_chunk_ids=set(), exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    out_of_context_result = evaluate_citation_integrity(
        answer=f"[{REAL_ID}]", generation_citations=[REAL_ID],
        supplied_chunk_ids={OTHER_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert unknown_result.failure_reasons != out_of_context_result.failure_reasons
    assert "unknown_chunk_id" in unknown_result.failure_reasons
    assert "citation_not_in_supplied_context" in out_of_context_result.failure_reasons


def test_fullwidth_citation_fails_malformed():
    exists_fn, metadata_fn = _resolvers({REAL_ID})
    result = evaluate_citation_integrity(
        answer=f"Revenue. 【{REAL_ID}】", generation_citations=[],  # strict parser found nothing
        supplied_chunk_ids={REAL_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "FAIL"
    assert "malformed_citation_attempt" in result.failure_reasons
    assert result.malformed_attempts[0].raw == f"【{REAL_ID}】"


def test_truncated_chunk63_fails_malformed():
    exists_fn, metadata_fn = _resolvers(set())
    result = evaluate_citation_integrity(
        answer="R&D was $157.4M. [chunk63]", generation_citations=[],
        supplied_chunk_ids=set(), exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "FAIL"
    assert "malformed_citation_attempt" in result.failure_reasons


def test_context_label_form_fails_as_unknown_not_malformed():
    # Real observed Task 1.7 regression - see the discrepancy note in
    # src/eval/citation_integrity.py's module docstring.
    exists_fn, metadata_fn = _resolvers({REAL_ID})  # the REAL id exists...
    garbled = f"chunk_id: {REAL_ID}"  # ...but the parsed citation string does not equal it
    result = evaluate_citation_integrity(
        answer=f"See [{garbled}]", generation_citations=[garbled],
        supplied_chunk_ids={REAL_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "FAIL"
    assert "unknown_chunk_id" in result.failure_reasons
    assert "malformed_citation_attempt" not in result.failure_reasons
    assert result.malformed_attempts == []


def test_ordinary_brackets_do_not_cause_false_failure():
    exists_fn, metadata_fn = _resolvers({REAL_ID})
    result = evaluate_citation_integrity(
        answer=f"See [note] for [2024] context. [{REAL_ID}]",
        generation_citations=[REAL_ID], supplied_chunk_ids={REAL_ID},
        exists_fn=exists_fn, metadata_fn=metadata_fn, abstention_expected=False,
    )
    assert result.status == "PASS"
    assert result.citation_attempts == [a for a in result.citation_attempts if a.strict_valid]


# ------------------------------------------------------- parsed_citation_mismatch

def test_matching_reparse_no_mismatch():
    exists_fn, metadata_fn = _resolvers({REAL_ID})
    result = evaluate_citation_integrity(
        answer=f"[{REAL_ID}]", generation_citations=[REAL_ID],
        supplied_chunk_ids={REAL_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.parsed_citation_mismatch is False
    assert "parsed_citation_mismatch" not in result.failure_reasons


def test_mismatched_generation_citations_fails():
    exists_fn, metadata_fn = _resolvers({REAL_ID})
    result = evaluate_citation_integrity(
        answer=f"[{REAL_ID}]", generation_citations=["something_else::chunk0"],
        supplied_chunk_ids={REAL_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "FAIL"
    assert "parsed_citation_mismatch" in result.failure_reasons


# ------------------------------------------------------------------- abstention

def test_non_abstaining_zero_citations_fails():
    exists_fn, metadata_fn = _resolvers(set())
    result = evaluate_citation_integrity(
        answer="Revenue grew significantly this year.", generation_citations=[],
        supplied_chunk_ids={REAL_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "FAIL"
    assert result.failure_reasons == ["missing_required_citation"]


def test_abstention_control_zero_citations_passes():
    exists_fn, metadata_fn = _resolvers(set())
    result = evaluate_citation_integrity(
        answer="The supplied context does not contain enough information to answer.",
        generation_citations=[], supplied_chunk_ids={REAL_ID},
        exists_fn=exists_fn, metadata_fn=metadata_fn, abstention_expected=True,
    )
    assert result.status == "PASS"
    assert result.failure_reasons == []


def test_abstention_with_unexpected_valid_citation_still_checked_mechanically():
    exists_fn, metadata_fn = _resolvers({REAL_ID})
    result = evaluate_citation_integrity(
        answer=f"Not enough information. [{REAL_ID}]", generation_citations=[REAL_ID],
        supplied_chunk_ids={REAL_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=True,
    )
    # zero-citation allowance doesn't apply (there IS a citation) - but a
    # valid+existing+supplied citation still passes normally, even on an
    # abstention-labeled case; no special-cased failure for "has a citation".
    assert result.status == "PASS"


# ----------------------------------------------------------------- multiple

def test_multiple_valid_citations_all_pass():
    exists_fn, metadata_fn = _resolvers({REAL_ID, OTHER_ID})
    result = evaluate_citation_integrity(
        answer=f"[{REAL_ID}] and [{OTHER_ID}]", generation_citations=[REAL_ID, OTHER_ID],
        supplied_chunk_ids={REAL_ID, OTHER_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "PASS"
    assert len(result.citation_checks) == 2


def test_one_valid_one_bad_fails_case():
    exists_fn, metadata_fn = _resolvers({REAL_ID})  # OTHER_ID does not exist
    result = evaluate_citation_integrity(
        answer=f"[{REAL_ID}] and [{OTHER_ID}]", generation_citations=[REAL_ID, OTHER_ID],
        supplied_chunk_ids={REAL_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "FAIL"
    assert "unknown_chunk_id" in result.failure_reasons


def test_duplicate_valid_citation_not_itself_a_failure():
    exists_fn, metadata_fn = _resolvers({REAL_ID})
    result = evaluate_citation_integrity(
        answer=f"[{REAL_ID}] ... [{REAL_ID}]", generation_citations=[REAL_ID],
        supplied_chunk_ids={REAL_ID}, exists_fn=exists_fn, metadata_fn=metadata_fn,
        abstention_expected=False,
    )
    assert result.status == "PASS"
    assert result.reparsed_citations == [REAL_ID]
    assert len(result.citation_checks) == 1


# ------------------------------------------------------------------ RecordingRetriever

class _FakeRetriever:
    def __init__(self, results):
        self._results = results
        self.calls = []

    def retrieve(self, question, k=5):
        self.calls.append((question, k))
        return self._results


def test_recording_retriever_passes_through_and_records():
    fake_results = ["r0", "r1", "r2"]
    inner = _FakeRetriever(fake_results)
    recorder = RecordingRetriever(inner)

    returned = recorder.retrieve("question", k=5)

    assert returned == fake_results
    assert recorder.last_results == fake_results
    assert inner.calls == [("question", 5)]


def test_recording_retriever_updates_on_each_call():
    inner = _FakeRetriever(["first"])
    recorder = RecordingRetriever(inner)
    recorder.retrieve("q1", k=5)
    assert recorder.last_results == ["first"]

    inner._results = ["second"]
    recorder.retrieve("q2", k=5)
    assert recorder.last_results == ["second"]
