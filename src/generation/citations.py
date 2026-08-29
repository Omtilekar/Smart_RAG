"""Task 1.7 - deterministic inline [chunk_id] citation parser.

Never invokes an LLM. Never normalizes/rewrites chunk IDs - a citation
must match the exact ID as generated. Chunk IDs follow Task 1.6's format
(document_id::chunk{ordinal}, e.g. "1158114_2016.htm::chunk106") - the
parser requires the literal "::chunk<digits>" shape inside brackets so
arbitrary markdown links or unrelated bracketed text are never mistaken
for citations.

Duplicate policy (user-approved, Decision 2's recommended default):
first-occurrence order preserved, repeated identical chunk IDs
deduplicated.
"""

from __future__ import annotations

import re

_CITATION_RE = re.compile(r"\[([^\[\]]+::chunk\d+)\]")


def parse_citations(answer_text: str) -> list[str]:
    """Returns chunk IDs found as [chunk_id] markers in `answer_text`, in
    first-occurrence order, with duplicates removed."""
    seen: set[str] = set()
    result: list[str] = []
    for match in _CITATION_RE.finditer(answer_text):
        chunk_id = match.group(1)
        if chunk_id not in seen:
            seen.add(chunk_id)
            result.append(chunk_id)
    return result
