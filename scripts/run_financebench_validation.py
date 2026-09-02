"""Task 2.12 - independent benchmark validation (FinanceBench).

Acquires the official open-source 150-question FinanceBench sample and
its 84 referenced source PDFs (frozen HF dataset revision + frozen
GitHub commit for the PDFs), parses/chunks/embeds/indexes them in an
isolated benchmark namespace (never touching the internal SEC corpus),
runs the frozen Phase 1 baseline retrieval configuration against the
complete benchmark corpus (never gold-document-prefiltered), scores
retrieval deterministically, and writes one Task 2.11 run record for the
real full-benchmark run.

    python scripts/run_financebench_validation.py --download
    python scripts/run_financebench_validation.py --dry-run
    python scripts/run_financebench_validation.py --pilot
    python scripts/run_financebench_validation.py --full

No LLM call, no generation, no OpenRouter/OpenAI/Anthropic call anywhere
in this script - PROJECT_EXECUTION.md's Task 2.12 checklist requires
only retrieval-metric validation ("Report FinanceBench metrics alongside
the internal set"), not answer generation/scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "0")  # this script's --download step needs network; everything else is offline

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.artifacts.versioning import (  # noqa: E402
    ArtifactCompatibilityError,
    validate_sha256,
)
from src.chunk.metadata_schema import CHUNK_SCHEMA_VERSION  # noqa: E402
from src.eval import financebench as fb  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402
from src.embeddings.bge import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    embedding_identity,
    encode_passages,
    encode_queries,
    load_model,
)
from src.index.lancedb_index import (  # noqa: E402
    DISTANCE_METRIC,
    TABLE_NAME,
    index_identity,
    open_database,
)
from src.storage import get_storage  # noqa: E402

# ---- frozen official source identity (Section 7) ----
HF_DATASET_REPO = "PatronusAI/financebench"
HF_DATASET_REVISION = "e04404e3a97f69f79c14d42f24981a1c9c3bcd18"
HF_DATASET_FILE = "financebench_merged.jsonl"
GITHUB_REPO = "patronus-ai/financebench"
GITHUB_PDF_COMMIT = "cc39aeb4afdf33909ee1412188bf89035950c2eb"
LICENSE = "CC BY-NC 4.0 (evaluation use only, no redistribution)"

BENCHMARK_NAME = fb.BENCHMARK_NAME
EVIDENCE_ALIGNMENT_VERSION = "1.0"
PARSER_VERSION = "pdfplumber-0.11.10"

CONFIG_RELATIVE_PATH = Path("configs") / "phase_2_12_financebench_validation.json"
RESULT_RELATIVE_PATH = Path("results") / "phase_2_12_financebench_validation.json"

TOP_K = 10


def git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------- acquisition

def cmd_download() -> int:
    storage = get_storage()
    root = storage.financebench_root
    root.mkdir(parents=True, exist_ok=True)
    pdf_dir = root / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = root / HF_DATASET_FILE
    if not jsonl_path.exists():
        url = f"https://huggingface.co/datasets/{HF_DATASET_REPO}/resolve/{HF_DATASET_REVISION}/{HF_DATASET_FILE}"
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, jsonl_path)
    dataset_file_sha256 = sha256_file(jsonl_path)
    print(f"{HF_DATASET_FILE}: {jsonl_path.stat().st_size:,} bytes, sha256={dataset_file_sha256}")

    rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    audit = fb.audit_financebench_dataset(rows)
    if audit.row_count != fb.EXPECTED_ROW_COUNT or audit.unique_doc_name_count != fb.EXPECTED_UNIQUE_DOC_COUNT:
        raise SystemExit(
            f"STOP: official open-source source no longer matches the expected population "
            f"(row_count={audit.row_count} expected {fb.EXPECTED_ROW_COUNT}, "
            f"unique_doc_name_count={audit.unique_doc_name_count} expected {fb.EXPECTED_UNIQUE_DOC_COUNT})"
        )

    doc_names = sorted({r["doc_name"] for r in rows})
    doc_hashes: dict[str, str] = {}
    missing_docs: list[str] = []
    for i, doc_name in enumerate(doc_names, start=1):
        pdf_path = pdf_dir / f"{doc_name}.pdf"
        if not pdf_path.exists():
            url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_PDF_COMMIT}/pdfs/{doc_name}.pdf"
            print(f"[{i}/{len(doc_names)}] downloading {doc_name}.pdf")
            try:
                urllib.request.urlretrieve(url, pdf_path)
            except Exception as exc:
                print(f"  FAILED: {exc}", file=sys.stderr)
                missing_docs.append(doc_name)
                continue
        doc_hashes[doc_name] = sha256_file(pdf_path)

    document_manifest = {
        "documents": {name: {"sha256": h, "size_bytes": (pdf_dir / f'{name}.pdf').stat().st_size}
                      for name, h in sorted(doc_hashes.items())},
        "missing_documents": missing_docs,
    }
    document_manifest_sha256 = fb.compute_benchmark_config_hash(document_manifest["documents"])

    source_manifest = {
        "hf_dataset_repo": HF_DATASET_REPO,
        "hf_dataset_revision": HF_DATASET_REVISION,
        "hf_dataset_file": HF_DATASET_FILE,
        "dataset_file_sha256": dataset_file_sha256,
        "github_repo": GITHUB_REPO,
        "github_pdf_commit": GITHUB_PDF_COMMIT,
        "license": LICENSE,
        "retrieval_date_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": audit.row_count,
        "unique_doc_name_count": audit.unique_doc_name_count,
        "documents_acquired": len(doc_hashes),
        "documents_missing": len(missing_docs),
        "missing_documents": missing_docs,
        "document_manifest_sha256": document_manifest_sha256,
    }
    (root / "source_manifest.json").write_text(json.dumps(source_manifest, indent=2) + "\n", encoding="utf-8")
    (root / "document_manifest.json").write_text(json.dumps(document_manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Documents acquired: {len(doc_hashes)}/{len(doc_names)}, missing: {missing_docs}")
    print(f"document_manifest_sha256: {document_manifest_sha256}")
    return 0


def load_source(storage) -> tuple[list[dict], dict, dict]:
    root = storage.financebench_root
    jsonl_path = root / HF_DATASET_FILE
    manifest_path = root / "source_manifest.json"
    doc_manifest_path = root / "document_manifest.json"
    if not jsonl_path.exists() or not manifest_path.exists():
        raise SystemExit("STOP: FinanceBench source not found locally - run with --download first")
    rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    document_manifest = json.loads(doc_manifest_path.read_text(encoding="utf-8")) if doc_manifest_path.exists() else {"documents": {}}
    return rows, source_manifest, document_manifest


def build_benchmark_config(source_manifest: dict, document_manifest: dict) -> dict:
    return {
        "benchmark_name": BENCHMARK_NAME,
        "hf_dataset_repo": HF_DATASET_REPO,
        "hf_dataset_revision": HF_DATASET_REVISION,
        "dataset_file_sha256": source_manifest["dataset_file_sha256"],
        "document_manifest_sha256": source_manifest["document_manifest_sha256"],
        "question_population": "open_source_150",
        "parser": PARSER_VERSION,
        "page_number_convention": fb.PAGE_NUMBER_CONVENTION,
        "chunking": {
            "window_size_tokens": fb.WINDOW_SIZE_TOKENS, "stride_tokens": fb.STRIDE_TOKENS,
            "overlap_tokens": 0, "partial_window_policy": "keep", "page_boundary_policy": "never_cross",
            "tokenizer_repo": "BAAI/bge-small-en-v1.5", "tokenizer_revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        },
        "table_serialization": "pipe_delimited_rows_newline_joined",
        "evidence_alignment_version": EVIDENCE_ALIGNMENT_VERSION,
        "retrieval": {"method": "vector", "index_type": "exact_flat", "distance_metric": "cosine", "top_k": TOP_K},
    }


# --------------------------------------------------------------- parsing

def parse_document(pdf_path: Path) -> list[fb.PageNode]:
    import pdfplumber
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = tuple(
                tuple(tuple((c or "") for c in row) for row in table)
                for table in page.extract_tables()
            )
            pages.append(fb.PageNode(doc_name=pdf_path.stem, page_number=i, text=text, tables=tables))
    return pages


def parsed_doc_path(parsed_dir: Path, doc_name: str) -> Path:
    return parsed_dir / f"{doc_name}.json"


def page_node_to_json(page: fb.PageNode) -> dict:
    return {"doc_name": page.doc_name, "page_number": page.page_number, "text": page.text,
            "tables": [[list(row) for row in table] for table in page.tables]}


def page_node_from_json(d: dict) -> fb.PageNode:
    return fb.PageNode(doc_name=d["doc_name"], page_number=d["page_number"], text=d["text"],
                        tables=tuple(tuple(tuple(row) for row in table) for table in d["tables"]))


def ensure_parsed(doc_names: list[str], pdf_dir: Path, parsed_dir: Path) -> dict[str, str]:
    """Resumable per-document parsing - reuses an already-parsed doc file
    unmodified; never reparses a document that already succeeded."""
    parsed_dir.mkdir(parents=True, exist_ok=True)
    status: dict[str, str] = {}
    for i, doc_name in enumerate(doc_names, start=1):
        out_path = parsed_doc_path(parsed_dir, doc_name)
        if out_path.exists():
            status[doc_name] = "reused"
            continue
        pdf_path = pdf_dir / f"{doc_name}.pdf"
        if not pdf_path.exists():
            status[doc_name] = "document_missing"
            continue
        print(f"[{i}/{len(doc_names)}] parsing {doc_name}")
        t0 = time.monotonic()
        try:
            pages = parse_document(pdf_path)
        except Exception as exc:
            print(f"  parse_failure: {exc}", file=sys.stderr)
            status[doc_name] = "parse_failure"
            continue
        payload = {"doc_name": doc_name, "page_count": len(pages), "pages": [page_node_to_json(p) for p in pages]}
        tmp_path = out_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp_path, out_path)
        status[doc_name] = "parsed"
        print(f"  {len(pages)} pages in {time.monotonic() - t0:.1f}s")
    return status


def load_parsed(doc_name: str, parsed_dir: Path) -> list[fb.PageNode] | None:
    path = parsed_doc_path(parsed_dir, doc_name)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [page_node_from_json(p) for p in payload["pages"]]


# --------------------------------------------------------------- pilot selection

FINANCEBENCH_CHUNK_COLUMNS: tuple[str, ...] = (
    "chunk_id", "doc_name", "page_number", "ordinal", "text", "token_count", "benchmark_config_hash",
)


def load_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(
        "BAAI/bge-small-en-v1.5", revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a", local_files_only=True,
    )


def build_all_chunks(doc_names: list[str], parsed_dir: Path, tokenizer, config_hash: str) -> tuple[list, dict]:
    """Returns (all_chunks, pages_by_doc) - pages_by_doc keyed by
    doc_name -> {page_number: PageNode}, needed later for evidence
    alignment against the exact same parsed pages the chunks came from."""
    all_chunks = []
    pages_by_doc: dict[str, dict[int, fb.PageNode]] = {}
    for doc_name in doc_names:
        pages = load_parsed(doc_name, parsed_dir)
        if pages is None:
            continue
        pages_by_doc[doc_name] = {p.page_number: p for p in pages}
        for page in pages:
            all_chunks.extend(fb.build_page_chunks(page, tokenizer=tokenizer, benchmark_config_hash=config_hash))
    return all_chunks, pages_by_doc


def build_lancedb_table(chunks: list, vectors, db_path: Path):
    import pyarrow as pa

    from src.index.lancedb_index import create_chunk_table, open_database

    from src.embeddings.bge import EMBEDDING_DIMENSION
    vector_array = pa.FixedSizeListArray.from_arrays(
        pa.array(vectors.reshape(-1), type=pa.float32()), EMBEDDING_DIMENSION,
    )
    schema = pa.schema([
        pa.field("chunk_id", pa.string()), pa.field("doc_name", pa.string()),
        pa.field("page_number", pa.int32()), pa.field("ordinal", pa.int32()),
        pa.field("text", pa.string()), pa.field("token_count", pa.int32()),
        pa.field("benchmark_config_hash", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIMENSION)),
    ])
    columns = {
        "chunk_id": [c.chunk_id for c in chunks], "doc_name": [c.doc_name for c in chunks],
        "page_number": [c.page_number for c in chunks], "ordinal": [c.ordinal for c in chunks],
        "text": [c.text for c in chunks], "token_count": [c.token_count for c in chunks],
        "benchmark_config_hash": [c.benchmark_config_hash for c in chunks], "vector": vector_array,
    }
    table = pa.table(columns, schema=schema)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = open_database(db_path)
    if db.list_tables().tables == [TABLE_NAME]:
        db.drop_table(TABLE_NAME)
    return create_chunk_table(db, table), db


def evaluate_questions(rows: list[dict], pages_by_doc: dict, all_chunks: list, model, table, *, label: str) -> tuple[list, list]:
    """Runs global retrieval (never gold-doc-prefiltered) for every
    question and computes per-question retrieval results. Returns
    (question_results, evidence_diagnostics)."""
    from src.index.lancedb_index import exact_cosine_search

    chunks_by_doc_page: dict[tuple[str, int], list] = {}
    for c in all_chunks:
        chunks_by_doc_page.setdefault((c.doc_name, c.page_number), []).append(c)

    results = []
    diagnostics = []
    for i, row in enumerate(rows, start=1):
        fbid = row["financebench_id"]
        if row["doc_name"] not in pages_by_doc:
            results.append(fb.QuestionRetrievalResult(
                financebench_id=fbid, doc_recall_hit=False, doc_first_hit_rank=None,
                evidence_relevant_chunk_ids=(), evidence_hits_in_top_k=0, evidence_first_hit_rank=None,
                status="blocked_document_missing",
            ))
            continue

        gold_chunk_ids: list[str] = []
        alignment_statuses = []
        for ev in row["evidence"]:
            pages_by_number = pages_by_doc.get(ev["doc_name"], {})
            alignment = fb.align_evidence_item(ev["evidence_page_num"], ev["evidence_text"], pages_by_number)
            alignment_statuses.append(alignment.status)
            if alignment.status in ("exact", "normalized_exact"):
                chunks_on_page = chunks_by_doc_page.get((ev["doc_name"], alignment.page_number), [])
                gold_chunk_ids.extend(fb.gold_chunk_ids_for_alignment(alignment, ev["evidence_text"], chunks_on_page))

        query_vec = encode_queries(model, [row["question"]], batch_size=1)[0]
        search_result = exact_cosine_search(table, query_vec, limit=TOP_K)
        retrieved_doc_names = search_result.column("doc_name").to_pylist()
        retrieved_chunk_ids = search_result.column("chunk_id").to_pylist()

        if not gold_chunk_ids:
            status = "blocked_evidence_unmatched"
        else:
            status = "evaluated"

        qr = fb.evaluate_financebench_question(
            financebench_id=fbid, retrieved_doc_names=retrieved_doc_names, retrieved_chunk_ids=retrieved_chunk_ids,
            gold_doc_name=row["doc_name"], gold_chunk_ids=tuple(dict.fromkeys(gold_chunk_ids)), k=TOP_K,
        )
        qr = fb.QuestionRetrievalResult(**{**qr.__dict__, "status": status})
        results.append(qr)
        diagnostics.append({
            "financebench_id": fbid, "doc_name": row["doc_name"], "gold_chunk_ids": list(gold_chunk_ids),
            "alignment_statuses": alignment_statuses, "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieved_doc_names": retrieved_doc_names, "status": status,
        })
        if i % 25 == 0:
            print(f"[{label}] evaluated {i}/{len(rows)}")
    return results, diagnostics


def select_pilot_ids(rows: list[dict], n: int = 15) -> list[str]:
    """Deterministic pilot spanning multiple companies/doc_types/question_types
    (Section 35) - evenly spaced by financebench_id after sorting, never
    the first N rows."""
    by_type: dict[str, list[dict]] = {}
    for r in rows:
        by_type.setdefault(r["question_type"], []).append(r)
    per_type = max(1, n // len(by_type))
    selected = []
    for qtype, group in sorted(by_type.items()):
        group_sorted = sorted(group, key=lambda r: r["financebench_id"])
        step = max(1, len(group_sorted) // per_type)
        selected.extend(group_sorted[::step][:per_type])
    return sorted({r["financebench_id"] for r in selected})[:n]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    if args.download:
        return cmd_download()

    storage = get_storage()

    if args.dry_run:
        root = storage.financebench_root
        present = (root / HF_DATASET_FILE).exists()
        print(f"benchmark source present: {present}")
        if present:
            rows, source_manifest, document_manifest = load_source(storage)
            print(f"source revision: {source_manifest['hf_dataset_revision']}")
            print(f"dataset_file_sha256: {source_manifest['dataset_file_sha256']}")
            print(f"license: {source_manifest['license']}")
            print(f"question count: {len(rows)}")
            print(f"documents acquired: {source_manifest['documents_acquired']}, missing: {source_manifest['documents_missing']}")
            config = build_benchmark_config(source_manifest, document_manifest)
            config_hash = fb.compute_benchmark_config_hash(config)
            print(f"benchmark config hash: {config_hash}")
            bench_dir = storage.benchmark_artifacts_dir(BENCHMARK_NAME, config_hash)
            print(f"artifact dir: {bench_dir}")
            print(f"artifacts exist: {bench_dir.exists()}")
        print("embedding model cache availability: (checked at build time, not dry-run)")
        print("run-logging compatibility: EVALUATION_RUN_SCHEMA_VERSION="
              f"{rl.EVALUATION_RUN_SCHEMA_VERSION}, evaluation_source='external_benchmark' supported")
        print("protected TEST budget: not touched by this script")
        return 0

    if not (args.pilot or args.full):
        parser.error("one of --download, --dry-run, --pilot, --full is required")

    rows, source_manifest, document_manifest = load_source(storage)
    config = build_benchmark_config(source_manifest, document_manifest)
    config_hash = fb.compute_benchmark_config_hash(config)
    bench_dir = storage.benchmark_artifacts_dir(BENCHMARK_NAME, config_hash)
    parsed_dir = bench_dir / "parsed"
    pdf_dir = storage.financebench_root / "pdfs"

    if args.pilot:
        pilot_ids = select_pilot_ids(rows, n=15)
        pilot_rows = [r for r in rows if r["financebench_id"] in pilot_ids]
        doc_names = sorted({r["doc_name"] for r in pilot_rows})
        print(f"=== PILOT ONLY ({len(pilot_rows)} questions, {len(doc_names)} documents) ===")
        status = ensure_parsed(doc_names, pdf_dir, parsed_dir)
        print(json.dumps(status, indent=2))

        tokenizer = load_tokenizer()
        all_chunks, pages_by_doc = build_all_chunks(doc_names, parsed_dir, tokenizer, config_hash)
        print(f"[PILOT ONLY] {len(all_chunks)} chunks across {len(pages_by_doc)} documents")

        model = load_model(device="cuda")
        texts = [c.text for c in all_chunks]
        vectors = encode_passages(model, texts, batch_size=DEFAULT_BATCH_SIZE)

        db_path = bench_dir / "pilot_index"
        table, _ = build_lancedb_table(all_chunks, vectors, db_path)
        print(f"[PILOT ONLY] index built: {table.count_rows()} rows")

        results, diagnostics = evaluate_questions(pilot_rows, pages_by_doc, all_chunks, model, table, label="PILOT ONLY")
        for name, count in _status_counts(results).items():
            print(f"[PILOT ONLY] status[{name}] = {count}")
        evaluated = [r for r in results if r.status == "evaluated"]
        if evaluated:
            agg = fb.aggregate_financebench_results(results, k=TOP_K)
            print(f"[PILOT ONLY] doc_recall@{TOP_K} = {agg.doc_recall_at_k:.4f} ({agg.doc_hit_count}/{agg.evaluated_count})")
            print(f"[PILOT ONLY] evidence_recall@{TOP_K} = {agg.evidence_recall_at_k:.4f} (questions_with_gold={agg.evidence_questions_with_gold})")
        print("[PILOT ONLY] manual audit trace:")
        for d in diagnostics[:5]:
            print(f"  {d['financebench_id']} doc={d['doc_name']} alignment={d['alignment_statuses']} "
                  f"gold_chunks={len(d['gold_chunk_ids'])} status={d['status']}")
        return 0

    print(f"=== FULL BENCHMARK ({len(rows)} questions) ===")
    doc_names = sorted({r["doc_name"] for r in rows})
    status = ensure_parsed(doc_names, pdf_dir, parsed_dir)
    parse_counts = _status_counts_dict(status)
    print("Parse status:", parse_counts)

    documents_referenced = len(doc_names)
    documents_missing = sum(1 for v in status.values() if v == "document_missing")
    documents_parse_failed = sum(1 for v in status.values() if v == "parse_failure")
    documents_acquired_parsed = documents_referenced - documents_missing - documents_parse_failed

    tokenizer = load_tokenizer()
    all_chunks, pages_by_doc = build_all_chunks(doc_names, parsed_dir, tokenizer, config_hash)
    print(f"Total benchmark chunks: {len(all_chunks)} across {len(pages_by_doc)} parsed documents")

    model = load_model(device="cuda")
    emb_identity = embedding_identity()
    from src.artifacts.versioning import embedding_identity_hash as _embedding_identity_hash
    emb_identity_hash = _embedding_identity_hash(emb_identity)

    texts = [c.text for c in all_chunks]
    embed_start = time.monotonic()
    vectors = encode_passages(model, texts, batch_size=DEFAULT_BATCH_SIZE)
    print(f"Embedded {len(texts)} chunks in {time.monotonic() - embed_start:.1f}s")

    db_path = bench_dir / "index"
    table, _ = build_lancedb_table(all_chunks, vectors, db_path)
    idx_identity = index_identity(chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=config_hash,
                                   embedding_identity_hash_value=emb_identity_hash)
    idx_identity_hash = fb.compute_benchmark_config_hash(idx_identity)
    print(f"Index built: {table.count_rows()} rows, identity_hash={idx_identity_hash}")

    results, diagnostics = evaluate_questions(rows, pages_by_doc, all_chunks, model, table, label="FULL")
    status_counts = _status_counts(results)
    print("Status counts:", status_counts)

    evaluated = [r for r in results if r.status == "evaluated"]
    if not evaluated:
        raise SystemExit("STOP: zero evaluated questions - cannot compute aggregate metrics")
    agg = fb.aggregate_financebench_results(results, k=TOP_K)
    print(f"doc_recall@{TOP_K} = {agg.doc_recall_at_k:.4f} ({agg.doc_hit_count}/{agg.evaluated_count})")
    print(f"doc_mrr = {agg.doc_mrr:.4f}")
    print(f"evidence_recall@{TOP_K} = {agg.evidence_recall_at_k:.4f} (questions_with_gold={agg.evidence_questions_with_gold})")
    print(f"evidence_mrr = {agg.evidence_mrr:.4f}")

    # Independent recomputation (Section 40) - recompute doc_recall@10 from
    # raw diagnostics without calling aggregate_financebench_results again.
    independent_hits = sum(1 for d in diagnostics if d["status"] == "evaluated" and
                            any(name == next(r2["doc_name"] for r2 in [d]) for name in d["retrieved_doc_names"][:TOP_K]))
    independent_doc_recall = independent_hits / len(evaluated)
    recompute_match = abs(independent_doc_recall - agg.doc_recall_at_k) < 1e-9
    print(f"independent doc_recall@{TOP_K} recomputation: {independent_doc_recall:.6f} "
          f"(production: {agg.doc_recall_at_k:.6f}, match: {recompute_match})")
    if not recompute_match:
        raise SystemExit("STOP: independent metric recomputation disagrees with production aggregate")

    diagnostics_path = bench_dir / "per_question_results.json"
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    diagnostics_sha256 = sha256_file(diagnostics_path)

    benchmark_identity = fb.build_benchmark_identity(
        dataset_revision=HF_DATASET_REVISION, dataset_file_sha256=source_manifest["dataset_file_sha256"],
        document_manifest_sha256=source_manifest["document_manifest_sha256"],
        evidence_alignment_version=EVIDENCE_ALIGNMENT_VERSION,
    )
    benchmark_version = "financebench-open-source-150-v1"

    run_record = rl.build_run_record(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=config_hash,
        embedding_model={**emb_identity, "identity_hash": emb_identity_hash},
        retrieval_config=config["retrieval"], reranker_config={"enabled": False}, generation_model=None,
        split="open_source_150", eval_set_version=benchmark_version, split_version=benchmark_version,
        metrics={
            "doc_recall@10": round(agg.doc_recall_at_k, 6), "doc_mrr": round(agg.doc_mrr, 6),
            "evidence_recall@10": round(agg.evidence_recall_at_k, 6), "evidence_mrr": round(agg.evidence_mrr, 6),
            "evaluated_count": agg.evaluated_count,
        },
        index_identity_hash=idx_identity_hash, evaluation_source="external_benchmark",
        benchmark_name=BENCHMARK_NAME, benchmark_version=benchmark_version,
        benchmark_source_hash=fb.compute_benchmark_config_hash(benchmark_identity),
        run_kind="financebench_full_retrieval_validation",
    )
    run_path = rl.write_run_record(run_record)
    print(f"Run record written: {run_path} (run_id={run_record.run_id})")

    config_path = REPO_ROOT / CONFIG_RELATIVE_PATH
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    summary = {
        "benchmark_name": BENCHMARK_NAME, "benchmark_version": benchmark_version,
        "source": {"hf_dataset_repo": HF_DATASET_REPO, "hf_dataset_revision": HF_DATASET_REVISION,
                   "dataset_file_sha256": source_manifest["dataset_file_sha256"], "license": LICENSE},
        "question_count": len(rows), "documents_referenced": documents_referenced,
        "documents_acquired_parsed": documents_acquired_parsed, "documents_missing": documents_missing,
        "documents_parse_failed": documents_parse_failed,
        "benchmark_config_hash": config_hash,
        "retrieval_configuration": config["retrieval"],
        "embedding_identity_hash": emb_identity_hash, "index_identity_hash": idx_identity_hash,
        "status_counts": status_counts,
        "retrieval_metrics": {
            "doc_recall@10": agg.doc_recall_at_k, "doc_mrr": agg.doc_mrr,
            "evidence_recall@10": agg.evidence_recall_at_k, "evidence_mrr": agg.evidence_mrr,
            "evaluated_count": agg.evaluated_count, "evidence_questions_with_gold": agg.evidence_questions_with_gold,
        },
        "generation": {"required": False, "llm_calls": 0, "api_spend_usd": 0,
                       "semantic_answer_accuracy": "DEFERRED TO TASK 2.13"},
        "published_comparison": {
            "apples_to_apples": "NOT COMPARABLE",
            "note": "FinanceBench paper accuracy figures were human-reviewed for specific model+context configurations; this run reports only deterministic retrieval metrics, never a claimed reproduction of the paper's human-reviewed accuracy.",
        },
        "run_id": run_record.run_id, "run_record_path": str(run_path.resolve().relative_to(REPO_ROOT).as_posix()),
        "per_question_diagnostics_sha256": diagnostics_sha256,
        "independent_recomputation_match": recompute_match,
        "test_budget_status": "0/3 (untouched - FinanceBench is external, never internal SEC TEST)",
        "final_verdict": "PASS",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
    }
    result_path = REPO_ROOT / RESULT_RELATIVE_PATH
    result_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Summary written: {result_path}")
    return 0


def _status_counts(results: list) -> dict:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts


def _status_counts_dict(status: dict) -> dict:
    counts: dict[str, int] = {}
    for v in status.values():
        counts[v] = counts.get(v, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
