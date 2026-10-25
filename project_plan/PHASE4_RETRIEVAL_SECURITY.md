# Phase 4 Task 4.14 - Retrieval Security

Implements a deterministic retrieval-security layer for RAG poisoning and
indirect prompt injection in the dense route.

## Threat Model

This task defends the live dense RAG path against retrieved text that tries
to behave like instructions instead of evidence:

- direct instruction override text (`ignore previous instructions`)
- indirect prompt injection embedded in retrieved documents
- fake `SYSTEM:` / `DEVELOPER:` role impersonation
- prompt/system-message exfiltration requests
- tool/browser/shell instructions inside retrieved text
- Unicode and zero-width obfuscation
- hidden markup carrying instructions
- exact duplicate poisoning
- missing or untrusted provenance

This is defense-in-depth, not a universal claim that all possible RAG
poisoning is solved. The scanner is deterministic and local: no LLM
classifier, no external moderation API, no network call.

## Architecture

New package:

```text
src/security/models.py
src/security/normalization.py
src/security/poisoning.py
src/security/retrieval_guard.py
src/security/telemetry.py
src/security/evaluation.py
```

Runtime boundary:

```text
dense retriever or exact retrieval cache
-> RetrievalSecurityGuard
-> existing context guard
-> prompt construction
-> generation provider
-> existing output guard
```

Only `approved` candidates enter prompt construction. `suspicious` and
`blocked` candidates are excluded from generation. If all retrieved dense
candidates are excluded, `MinimalGenerator` uses the existing
context-guard abstention result and never calls the provider.

Normalization is inspection-only: `normalize_for_security()` creates a
normalized scanner view, but the original `RetrievalResult.text` is
preserved unchanged when a candidate is approved.

## Provenance And Sources

The query-time guard requires dense candidates to carry non-empty
`chunk_id`, `document_id`, `text`, and `source`. The live dense source
policy currently allows only `edgar_corpus`, matching the existing
`RetrievalResult.source` contract.

When artifact identity fields are present on a candidate
(`chunk_config_hash`, `normalization_build_sha256`,
`development_manifest_sha256`), they must also be non-empty. This keeps
the guard compatible with lightweight test doubles while enforcing the
real retrieval object's provenance fields.

## Cache Interaction

The guard sits after `retriever.retrieve(...)`, so both exact-cache HITs
and MISSes pass through security inspection. The Task 4.13 cache still
stores raw retrieval evidence only. It never stores final answers,
prompts, provider responses, citations, or security approvals.

## Structured XBRL

Structured XBRL facts are not forced through the dense-text poisoning
scanner. The XBRL route remains deterministic SQL with structured
provenance validation and no generation call, preserving Task 3.10/4.9
semantics.

## Telemetry

`GET /status` additively exposes `retrieval_security`:

```text
enabled
mode
scanner_version
policy_version
text_scan_scope
xbrl_policy
telemetry counters
```

Telemetry is aggregate-only and stores no raw query text, no retrieved SEC
text, no prompt, no provider response, and no answer.

## Synthetic Evaluation

Synthetic fixtures live under:

```text
tests/fixtures/rag_poisoning/
```

The offline smoke/audit command is:

```bash
python scripts/smoke_retrieval_security.py
```

Current result file:

```text
results/phase_4_14_retrieval_security_smoke.json
```

Current synthetic metrics:

```text
cases: 12
poison_detection_recall: 1.0
false_positive_rate: 0.0
malicious_context_acceptance_rate: 0.0
poison_retrieval_acceptance_rate: 0.0
clean_candidate_retention_rate: 1.0
high_confidence_poison_blocked_rate: 1.0
missing_provenance_blocked_rate: 1.0
```

Measured overhead on synthetic five-candidate lists:

```text
guarded_p50_ms: 0.1458
guarded_p95_ms: 0.1554
overhead_p50_ms: 0.1457
overhead_p95_ms: 0.1552
```

No protected TEST run, generation provider call, AWS access, full-corpus
scan, rebuild, re-embedding, or index rebuild was used.

## Regression

Task 4.14 preserves frozen retrieval/model/chunking decisions:

- no model selection changed
- no embedding model changed
- no chunking strategy changed
- no CRAG/reranking/BM25/hybrid decision changed
- no production artifact rebuilt
- exact retrieval cache semantics remain retrieval-evidence-only

The previous Task 4.8 delimiter guard remains in place behind the new
retrieval-security layer.
