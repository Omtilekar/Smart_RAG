"""Task 2.8 - deterministic source-document identity for the 990 primary
10-K HTML filings under data/raw/primary/{cik}/{accession}.htm.

Identity is derived entirely from immutable source fields (never
filesystem mtime, never a random UUID) - `document_id` is stable across
re-runs and machines as long as the frozen source files are unchanged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceDocument:
    document_id: str
    cik: int
    accession: str
    source_path: str
    source_sha256: str
    source_size_bytes: int


def document_id(cik: int, accession: str) -> str:
    return f"primary:{cik}:{accession}"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def enumerate_primary_documents(primary_docs_root: Path) -> list[SourceDocument]:
    """Deterministic (sorted by cik, then accession) enumeration of every
    `{cik}/{accession}.htm` file under `primary_docs_root`. Raises
    ValueError on a zero-byte file or a duplicate canonical
    (cik, accession) pair - never silently skips a malformed entry."""
    seen: set[tuple[int, str]] = set()
    docs: list[SourceDocument] = []
    for cik_dir in sorted(primary_docs_root.iterdir(), key=lambda p: p.name):
        if not cik_dir.is_dir():
            continue
        cik = int(cik_dir.name)
        for htm_file in sorted(cik_dir.glob("*.htm")):
            accession = htm_file.stem
            key = (cik, accession)
            if key in seen:
                raise ValueError(f"duplicate canonical source (cik={cik}, accession={accession!r})")
            seen.add(key)
            size = htm_file.stat().st_size
            if size == 0:
                raise ValueError(f"zero-byte source file: {htm_file}")
            docs.append(SourceDocument(
                document_id=document_id(cik, accession),
                cik=cik,
                accession=accession,
                source_path=str(htm_file),
                source_sha256=_sha256_file(htm_file),
                source_size_bytes=size,
            ))
    return docs
