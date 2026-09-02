# Task 2.10 — Config Hashing and Artifact Versioning

## Phase

Phase 2 — Make the Numbers Trustworthy

Current confirmed state:

Data Preparation                              — COMPLETE
Phase 0 — Foundation                          — COMPLETE
Phase 1 — Make It Work End to End             — COMPLETE WITH WARN
Phase 2 — Make the Numbers Trustworthy        — IN PROGRESS

  2.1 XBRL Truth Contract                     — COMPLETE
  2.2 Freeze Supported Tag Registry           — COMPLETE
  2.3 Build Full Evaluation Dataset           — COMPLETE WITH NOTE
  2.4 DEV/TEST Split                          — COMPLETE
  2.5 Evaluation Schema                       — COMPLETE
  2.6 Metric Unit Tests                       — COMPLETE
  2.7 MS MARCO Harness Validation             — COMPLETE
  2.8 Primary Evidence Alignment              — COMPLETE WITH NOTE
  2.9 Freeze Chunk Metadata Schema            — COMPLETE
  2.10 Config Hashing & Artifact Versioning   — CURRENT

Do NOT start Task 2.11.

---

# 1. Objective

Implement and freeze the repository-wide configuration/artifact identity
contract required to make later retrieval experiments reproducible and to
make stale or incompatible artifacts fail loudly rather than being reused
silently.

Task 2.10 must satisfy the exact PROJECT_EXECUTION.md requirements:

- hash chunking configuration;
- version chunk directories;
- version index directories;
- store embedding-model identity;
- store eval-set version;
- prevent stale-index / new-config mismatches;
- add CI assertions for artifact compatibility.

The central rule is:

    Configuration determines artifact identity.
    Artifact provenance must be inspectable.
    Incompatible artifacts must never be silently reused.

This task is about provenance, compatibility, and deterministic identity.

It is NOT a chunking ablation.
It is NOT an embedding benchmark.
It is NOT an indexing experiment.
It is NOT a retrieval evaluation.
It is NOT evaluation-run logging; Task 2.11 owns that.

---

# 2. Read Authoritative Sources First

Before implementation, inspect the actual repository.

At minimum read:

1. project_plan/PROJECT_EXECUTION.md
2. project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md
3. src/chunk/metadata_schema.py
4. scripts/audit_chunk_metadata_schema.py
5. results/phase_2_9_chunk_metadata_schema.json
6. src/chunk/fixed_window.py
7. scripts/chunk_development_corpus.py
8. configs/chunk_development_corpus.json
9. results/phase_1_3_chunking_summary.json
10. src/embeddings/bge.py
11. scripts/embed_development_corpus.py
12. configs/embed_development_corpus.json
13. results/phase_1_4_embedding_summary.json
14. src/index/lancedb_index.py
15. scripts/build_vector_index.py
16. configs/build_vector_index.json
17. results/phase_1_5_vector_index_summary.json
18. src/storage.py
19. project_plan/STORAGE.md
20. project_plan/PHASE1_CHUNKING.md
21. project_plan/PHASE1_EMBEDDINGS.md
22. project_plan/PHASE1_VECTOR_INDEX.md
23. Task 2.3/2.4 eval dataset + split metadata
24. src/eval/evaluation_schema.py
25. project_plan/PHASE2_EVALUATION_SCHEMA.md
26. Progress.md

Do not rely only on planning prose.

Verify the real implemented behavior.

If repository implementation and planning docs conflict, surface the
conflict rather than silently choosing a new convention.

---

# 3. Baseline Before Changes

Record:

    git branch
    git status --short
    git log --oneline --decorate -15
    python --version
    python -c "import sys; print(sys.executable)"

Run:

    python scripts/dev.py doctor
    python scripts/dev.py test --portable

Record current HEAD and test counts.

Verify Task 2.9 is committed and working tree is clean except for this
task prompt if applicable.

Record the currently frozen identities at minimum:

    CHUNK_SCHEMA_VERSION
    Phase 1 chunk_config_hash
    embedding model repository
    embedding model revision
    embedding dimension
    normalization policy
    Phase 2 eval_set_version
    Phase 2 split version
    DEV hash
    TEST hash
    CI hash

Known historical Phase 1 chunk_config_hash:

    f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

Do not trust that value blindly; independently verify it from the current
config using the repository's existing hashing semantics.

---

# 4. Preserve Task 2.9 Identity Semantics

Task 2.9 froze chunk identity.

Do NOT redefine:

    chunk_uid
    chunk_local_id
    chunk_schema_version

Task 2.9's global UID depends on chunk_config_hash.

Therefore Task 2.10 must make chunk_config_hash a stable, reproducible,
well-defined semantic contract.

Changing the chunk_config_hash algorithm casually would change canonical
chunk identities.

Any change that would invalidate historical Task 2.9 identities is a STOP
condition unless there is a demonstrated correctness defect.

---

# 5. Existing Phase 1 Hash Is Real Historical Identity

Phase 1 already computes:

    SHA-256(canonical JSON chunk configuration)

using deterministic JSON serialization.

Task 2.10 must inspect the exact implementation and decide whether it is
already suitable as the canonical chunk-config hashing primitive.

Default expectation:

    preserve it if correct;
    centralize it;
    test it;
    prevent duplicated independent implementations.

Do NOT create a new hash solely because this is a new task.

If the existing implementation is incomplete, fix it carefully while
providing explicit compatibility handling for the historical Phase 1
hash.

---

# 6. One Canonical Hashing Utility

Create one authoritative hashing utility.

Recommended location:

    src/artifacts/versioning.py

or, if current repository organization strongly favors another location:

    src/config_hashing.py

Choose one clean home after inspecting the repository.

Do not maintain several handwritten copies of:

    json.dumps(... sort_keys=True ...)
    hashlib.sha256(...)

throughout scripts.

Expose focused functions conceptually like:

    canonical_json_bytes(...)
    semantic_hash(...)
    compute_chunk_config_hash(...)
    compute_embedding_identity(...)
    compute_index_identity(...)
    validate_artifact_manifest(...)
    assert_artifact_compatible(...)

Exact names should follow repository conventions.

---

# 7. Canonical Serialization Contract

Freeze canonical serialization explicitly.

At minimum define behavior for:

    mappings
    arrays
    strings
    integers
    floats
    booleans
    null
    nested structures

Canonical hashing must be independent of dictionary insertion order.

Recommended convention if consistent with existing code:

    json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

Do not hash:

    repr(dict)
    Python hash()
    pickle
    filesystem absolute paths
    timestamps
    Git SHA
    hostnames
    usernames

Semantic config identity must be machine-independent.

---

# 8. Reject Non-Canonical Values

The hash utility must reject configuration values that cannot be
reliably serialized.

At minimum reject:

    NaN
    +Infinity
    -Infinity
    arbitrary Python objects
    sets
    Path objects unless explicitly normalized
    callables

Do not silently stringify arbitrary objects.

If Path values legitimately belong to configuration identity, convert them
to an explicit portable logical form first.

Absolute machine paths should normally NOT be hash inputs.

---

# 9. Separate Semantic Configuration From Provenance

Do not mix these concepts.

Semantic configuration affects behavior and therefore identity.

Examples:

    tokenizer/model identity
    chunk size
    overlap
    partial-window policy
    section-aware strategy
    content types
    embedding normalization
    distance metric
    index type/config

Provenance explains when/where an artifact was built.

Examples:

    created_at_utc
    git_sha
    hostname
    build duration

Provenance must NOT change semantic hashes.

Two builds with identical semantic configuration should produce the same
config identity even on different machines and dates.

---

# 10. Chunk Config Contract

Freeze which fields constitute chunk_config_hash.

Inspect the Phase 1 config first.

At minimum ensure the hash captures every parameter that could change chunk
boundaries, content, IDs, or token counts.

Likely examples:

    chunker type
    window size
    stride / overlap
    tokenizer repository
    tokenizer revision
    special-token policy
    partial-window policy
    frontmatter/body policy
    section behavior where applicable
    table serialization policy where applicable
    normalizer/source representation identity where semantically required

Do not include unrelated runtime values such as:

    batch size for embedding
    output path
    created_at
    GPU name
    Git SHA

Task 2.10 must document the final exact input contract.

---

# 11. Legacy Hash Compatibility

Independently recompute the Phase 1 hash from its frozen config.

Required result:

    recomputed Phase 1 chunk_config_hash
        ==
    stored Phase 1 chunk_config_hash

If the new centralized utility reproduces:

    f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

then explicitly record:

    legacy compatibility: PASS

If not:

STOP.

Do not rewrite:

    chunks.parquet
    embeddings.parquet
    LanceDB index
    Task 2.9 chunk UIDs

until the discrepancy is understood.

---

# 12. Chunk Directory Versioning

PROJECT_EXECUTION.md requires versioned chunk directories.

Current Phase 1 already uses:

    artifacts/chunks/<chunk_config_hash>/

Formalize this as the canonical chunk-artifact location contract unless
repository evidence shows a correctness problem.

Required properties:

    same chunk config -> same directory identity
    different chunk config -> different directory
    no accidental overwrite between configs
    path construction centralized
    config hash validated before use

Do not rebuild the Phase 1 chunks.

---

# 13. Chunk Artifact Manifest

Add a small machine-readable manifest alongside a versioned chunk artifact.

Recommended conceptual location:

    artifacts/chunks/<chunk_config_hash>/manifest.json

or another clearly repository-standard name.

The manifest should contain enough provenance to validate compatibility,
for example:

    artifact_manifest_version
    artifact_type = "chunks"

    chunk_schema_version
    chunk_config_hash
    chunk_config
    source/corpus identity where relevant

    row_count
    canonical schema identity/fingerprint if Task 2.9 exposes one

    created_at_utc
    git_sha

Do not place large data in the manifest.

Semantic hashes must not include created_at/git_sha.

---

# 14. Historical Artifact Policy

The existing Phase 1 chunk directory may predate the new Task 2.10
manifest.

Do NOT modify or regenerate the underlying Parquet merely to add
provenance.

Allowed:

    create a verified sidecar manifest

only after independently validating the real existing artifact against the
stored Phase 1 config/hash/schema.

Clearly label such a manifest:

    verified historical artifact provenance

rather than implying it existed at original build time.

---

# 15. Embedding Model Identity

PROJECT_EXECUTION.md explicitly requires storing embedding-model identity.

A model name alone is insufficient.

Freeze a structured identity including at minimum:

    provider/repository
    resolved revision
    embedding dimension
    vector dtype
    normalize_embeddings
    passage/query encoding convention where relevant

For the Phase 1 BGE baseline, inspect actual existing values rather than
assuming them.

Known historical model:

    BAAI/bge-small-en-v1.5

Known historical resolved revision from prior tasks:

    5c38ec7c405ec4b44b94cc5a9bb96e735b38267a

Verify directly from the existing tracked summaries/code.

---

# 16. Embedding Identity Hash/Key

Create a deterministic semantic identity for embedding artifacts.

The representation should distinguish, for example:

    same repository + different revision
    normalize_embeddings true vs false
    384-dim vs another dimension
    passage convention changes

Do not use only:

    BAAI--bge-small-en-v1.5

as the complete semantic identity.

That existing sanitized string is a useful filesystem label but not
sufficient provenance by itself.

A deterministic embedding_config_hash or embedding_identity_hash is
appropriate if consistent with the architecture.

Document the exact input fields.

---

# 17. Embedding Artifact Manifest

Formalize compatibility metadata for embedding artifacts.

At minimum:

    artifact_type = "embeddings"
    artifact_manifest_version

    chunk_schema_version
    chunk_config_hash

    embedding model repository
    embedding model revision
    embedding dimension
    dtype
    normalization policy
    embedding identity/hash

    row_count

    created_at_utc
    git_sha

The embedding artifact must state exactly which chunk artifact/config it
was created from.

---

# 18. Index Versioning

PROJECT_EXECUTION.md explicitly requires versioned index directories.

Current Phase 1 path is conceptually:

    artifacts/indexes/<chunk_config_hash>/<embedding_model_key>/

Inspect the real storage implementation.

The Task 2.10 contract must prevent collisions where the same model
repository name is reused with:

    different revision
    different dimensions
    different normalization
    different index configuration

Do not silently overwrite a valid old index.

---

# 19. Index Identity

Define the semantic index identity.

It should bind the index to at least:

    chunk_schema_version
    chunk_config_hash
    embedding identity
    distance metric
    index/table configuration

For the Phase 1 baseline this includes:

    exact search
    cosine
    LanceDB table name = chunks
    no ANN index

Later Phase 3 may introduce:

    IVF_PQ
    FTS
    hybrid
    other index parameters

Task 2.10 should establish an extensible identity contract now without
implementing those later features.

---

# 20. Do Not Confuse Artifact Type Hashes

Keep these distinct:

    chunk_config_hash
    embedding_identity/hash
    index_config_hash or index identity
    eval_set_version
    chunk_schema_version
    artifact manifest version

Do not overload one "config_hash" to mean all of them.

Each identifier should answer a clear question.

Example:

    chunk_config_hash
      "How were chunks generated?"

    embedding identity
      "Which exact embedding semantics produced vectors?"

    index identity
      "Which chunk/vector/index configuration produced this searchable index?"

    eval_set_version
      "Which benchmark version is being evaluated?"

---

# 21. Index Artifact Manifest

Create/define a sidecar manifest for indexes.

At minimum:

    artifact_type = "index"
    artifact_manifest_version

    chunk_schema_version
    chunk_config_hash

    embedding identity
    embedding model repository
    embedding revision
    dimension

    index identity/hash
    distance metric
    index type
    table name

    source row count

    created_at_utc
    git_sha

For the historical Phase 1 index, validate:

    162,357 rows
    exact search
    cosine
    0 ANN indexes
    expected table/schema

before creating any verified historical manifest.

Do not rebuild it.

---

# 22. Eval-Set Version

PROJECT_EXECUTION.md explicitly requires storing eval-set version.

Use the authoritative Task 2.3/2.4 eval contracts.

Do not create a second independent eval version.

Read the real values from frozen evaluation artifacts.

Compatibility metadata should distinguish at minimum:

    eval_set_version
    split version
    dataset hash
    DEV hash
    TEST hash
    CI hash

where appropriate.

Do not open protected TEST question payloads merely to derive metadata if
the required frozen metadata already exists elsewhere.

TEST access discipline remains 0/3.

---

# 23. Artifact Compatibility Object

Define a small typed compatibility/provenance object representing the
identity of artifacts a retrieval/evaluation run will need.

Conceptually:

    ArtifactCompatibility(
        chunk_schema_version,
        chunk_config_hash,
        embedding_identity,
        index_identity,
        eval_set_version,
        ...
    )

Do not include Task 2.11 run-level fields such as:

    run_id
    timestamp
    metrics

Task 2.11 owns experiment logging.

Task 2.10 owns whether artifacts are compatible before a run begins.

---

# 24. Loud Mismatch Failure

Introduce a dedicated exception, e.g.:

    ArtifactCompatibilityError

Mismatch errors must be explicit.

Examples:

    index expects chunk hash A, current config computes B

    index expects model revision X, configured revision is Y

    index dimension=384, query encoder dimension=768

    artifact schema version=1, loader requires unsupported version=2

    eval artifact says eval_set_version=v1, requested=v2

Do NOT:

    warn and continue
    silently rebuild
    silently choose the newest directory
    pick any matching model-name directory
    fall back to another artifact

The task exists specifically to prevent stale-index/new-config bugs.

---

# 25. Validate Before Loading Expensive Components

Where practical, check artifact manifests before:

    loading embedding models
    loading large indexes
    performing retrieval
    allocating GPU memory

A cheap manifest incompatibility should fail early.

Do not require a GPU to discover that artifact metadata is incompatible.

---

# 26. No Implicit "Latest"

Do not create semantics such as:

    artifacts/chunks/latest
    newest directory by timestamp
    highest lexical hash
    newest modified file

unless explicitly required by existing architecture.

Consumers must request identity explicitly or derive it deterministically
from configuration.

"Latest" is not reproducible.

---

# 27. Storage Abstraction Integration

Update src/storage.py only as narrowly necessary.

Centralize versioned paths.

Potential conceptual API:

    chunks_dir(chunk_config_hash)

    embeddings_dir(
        chunk_config_hash,
        embedding_identity,
    )

    index_dir(
        chunk_config_hash,
        embedding_identity,
        index_identity,
    )

Do not blindly adopt this exact signature if it would unnecessarily break
existing Phase 1 callers.

Backward-compatible wrappers may be appropriate.

The important requirement is:

    new artifact creation cannot collide across semantic configurations.

Historical Phase 1 paths must remain readable.

---

# 28. Backward Compatibility

Task 2.10 must not break the existing Phase 1 baseline merely because its
directories use the older simplified model-key path.

Provide one of:

A. compatibility resolver for existing Phase 1 artifacts;

or

B. verified historical manifests mapped to the existing locations;

or

C. another narrow backward-compatible mechanism.

Do NOT:

    move ~hundreds of MB of artifacts unnecessarily
    regenerate embeddings
    rebuild LanceDB
    rewrite Phase 1 paths in history
    change baseline metrics

---

# 29. Compatibility Check Script

Create a deterministic audit script, for example:

    scripts/audit_artifact_compatibility.py

It should inspect existing Phase 1/Phase 2 metadata and report:

    chunk config hash recomputation
    chunk directory identity
    chunk schema version

    embedding identity
    embedding artifact compatibility

    index identity
    index artifact compatibility

    eval_set_version
    split metadata availability

    stale/mismatch detection tests

    official TEST runs consumed

Write a small tracked result:

    results/phase_2_10_artifact_versioning.json

Do not put artifact payloads in results/.

---

# 30. Real Phase 1 Compatibility Audit

Use real local artifacts read-only.

Verify the chain:

    chunk config
        ↓
    chunk_config_hash
        ↓
    chunks artifact
        ↓
    embedding artifact
        ↓
    embedding identity
        ↓
    LanceDB index
        ↓
    index identity

All must be mutually compatible.

At minimum verify:

    chunks rows = 162,357
    embeddings rows = 162,357
    index rows = 162,357

and their stored/reconstructed provenance agrees.

Do not run retrieval quality evaluation.

---

# 31. Negative Compatibility Tests

Create synthetic copies/manifests and prove failure for at least:

1. changed chunk window size
2. changed overlap
3. changed tokenizer revision
4. changed embedding repository
5. changed embedding revision
6. changed embedding dimension
7. changed normalize_embeddings
8. changed distance metric
9. changed index type
10. changed chunk schema version
11. changed eval_set_version
12. malformed hash
13. missing required manifest field
14. wrong artifact type
15. row-count mismatch where row count is part of validation

Each should fail loudly.

Do not alter the real artifacts to create negative cases.

---

# 32. Determinism Tests

Verify in fresh processes:

    same semantic config
        -> same hash

    dict-key order changes
        -> same hash

    provenance timestamp changes
        -> same semantic hash

    Git SHA changes
        -> same semantic hash

    one true semantic parameter changes
        -> different hash

Include Unicode config values.

Include nested configuration.

---

# 33. Hash Validation

Where the project uses SHA-256, validate the physical representation:

    lowercase hex
    exactly 64 characters

Reject malformed hashes.

Do not silently lowercase arbitrary invalid input and continue.

---

# 34. Manifest Versioning

Define:

    artifact_manifest_version

separately from:

    chunk_schema_version

Initial value may be:

    1

if no existing repository convention contradicts it.

Changing manifest serialization/layout does not necessarily mean chunk
schema semantics changed.

Keep these concepts separate.

---

# 35. Manifest Serialization

Tracked/generated manifests should be deterministic except for explicitly
non-semantic provenance fields such as:

    created_at_utc
    git_sha

If calculating a manifest semantic fingerprint, explicitly exclude those
non-semantic fields.

Avoid byte-for-byte determinism claims for files containing timestamps
unless you deliberately separate semantic and provenance sections.

---

# 36. CI Assertions

PROJECT_EXECUTION.md explicitly requires CI assertions for artifact
compatibility.

Add fast portable tests that do not require the real 26 GB dataset.

CI must catch at minimum:

    config hash algorithm drift
    canonical serialization drift
    unsupported manifest version
    chunk-schema mismatch
    chunk-hash mismatch
    embedding identity mismatch
    index identity mismatch
    eval-version mismatch

Portable CI should use tiny synthetic manifests/configs.

Real local-artifact validation should be marked:

    local_data

Do not make CI need the Phase 1 Parquet/index artifacts.

---

# 37. Existing Consumers

Inspect consumers of:

    chunks_dir()
    embeddings_dir()
    index_dir()
    chunk_config_hash

especially:

    Phase 1 chunk build
    embedding build
    vector-index build
    baseline retriever
    MS MARCO harness where relevant
    Phase 2 schema/audit code

Do not leave some components using the new contract and others bypassing it.

However, avoid broad refactoring.

Integrate only where needed to enforce compatibility.

---

# 38. Retriever Compatibility Gate

The existing baseline retriever is allowed to remain behaviorally
unchanged.

But before using a configured index, provide a way to assert:

    current chunk config
    current embedding identity
    index manifest

are compatible.

Do not change ranking, score semantics, top-k, query prefix, or generation.

Task 2.10 is provenance enforcement, not retrieval behavior.

---

# 39. No Evaluation Run Logging Yet

Do NOT implement the full Task 2.11 fields:

    run_id
    retrieval config logging
    reranker config logging
    generation-model run records
    timestamps + metrics per experiment

Task 2.10 may expose artifact identities that Task 2.11 will consume.

Do not implement the experiment-run database/log layer early.

---

# 40. No TEST Evaluation

Do not load the protected TEST question corpus.

Do not call the TEST evaluator.

Official TEST evaluations must remain:

    0 / 3

Reading already-public/frozen split metadata such as version/hash is allowed
if the repository already exposes it without materializing TEST questions.

Record that distinction explicitly.

---

# 41. No Network / API / LLM

Task 2.10 should perform no:

    SEC downloads
    Hugging Face downloads
    OpenRouter calls
    OpenAI calls
    Anthropic calls
    AWS calls

No LLM required.

No API spend.

GPU is not required for Task 2.10 itself.

Existing regression tests may exercise already-established local GPU/model
smokes, but the new implementation must remain CPU/portable.

---

# 42. Do Not Rebuild Large Artifacts

Do NOT:

    rechunk 1,500 filings
    re-embed 162,357 chunks
    rebuild the LanceDB index
    rebuild MS MARCO
    rerun Task 2.8's 990-document parser

unless a truly unavoidable correctness issue is found.

Use existing artifacts read-only.

Task 2.10 is primarily metadata/provenance enforcement.

---

# 43. Files Likely to Add

Use repository conventions, but likely files include:

    src/artifacts/__init__.py
    src/artifacts/versioning.py

or equivalent existing package placement.

Also likely:

    scripts/audit_artifact_compatibility.py
    tests/test_artifact_versioning.py
    results/phase_2_10_artifact_versioning.json
    project_plan/PHASE2_ARTIFACT_VERSIONING.md

Potential narrow updates:

    src/storage.py
    tests/test_storage.py
    scripts/chunk_development_corpus.py
    scripts/embed_development_corpus.py
    scripts/build_vector_index.py
    relevant existing tests
    project_plan/REPOSITORY_STRUCTURE.md
    Progress.md

Do not create files merely to match this list.

Follow actual architecture.

---

# 44. Documentation

Create:

    project_plan/PHASE2_ARTIFACT_VERSIONING.md

Document:

    objective
    canonical serialization
    semantic vs provenance fields
    chunk-config hashing
    historical Phase 1 hash compatibility
    chunk artifact versioning
    embedding identity
    embedding artifact versioning
    index identity
    index artifact versioning
    eval-set version binding
    manifest schema
    compatibility rules
    mismatch behavior
    storage layout
    historical Phase 1 compatibility
    CI assertions
    TEST discipline
    Task 2.11 boundary
    schema evolution

Explicitly state:

    Task 2.9 freezes chunk-record semantics.
    Task 2.10 freezes artifact/config identity and compatibility.
    Task 2.11 records experiment runs using those identities.

---

# 45. Progress.md

Append a new section only:

    ## YYYY-MM-DD — Phase 2.10 Config Hashing and Artifact Versioning

Include:

    Objective
    Initial State
    Authoritative Contract
    Existing Hash Audit
    Canonical Serialization
    Chunk Config Hash
    Legacy Compatibility
    Chunk Artifact Versioning
    Embedding Identity
    Index Identity
    Eval-Set Version
    Manifest Contract
    Compatibility Enforcement
    Negative Mismatch Validation
    CI Assertions
    Real Phase 1 Audit
    TEST Discipline
    Regression Gates
    Tests
    Frozen Data
    Files Created/Modified
    Git
    Result
    Phase Status

Do not rewrite prior historical entries.

---

# 46. Regression Gates

Verify no semantic regression to Task 2.9:

    CHUNK_SCHEMA_VERSION unchanged unless an actual defect requires change
    CANONICAL_FIELDS unchanged
    chunk_uid semantics unchanged
    all 162,357 Phase 1 derived UIDs still unique

Verify Task 2.8 remains:

    990/990 parsed
    gold_evidence_count = 0
    no promoted would-be-gold evidence

Verify Task 2.1–2.7 unchanged.

Verify Phase 1 baseline behavior unchanged:

    chunk count
    embeddings
    index row count
    exact cosine semantics
    retriever result contract
    generation
    baseline metrics

Do not rerun expensive builds merely to prove that.

Use tests/artifact checks.

---

# 47. Frozen Data Safety

Verify unchanged:

    data/xbrl.duckdb
    data/edgar_corpus/
    data/raw/xbrl/
    data/raw/primary/
    data/msmarco/

At minimum preserve the known xbrl.duckdb size:

    7,011,053,568 bytes

No frozen-data writes.

---

# 48. Tests

Add focused tests covering at minimum:

Canonical serialization:
- key-order independence
- nested structures
- Unicode
- NaN/Infinity rejection
- unsupported-object rejection

Chunk config:
- deterministic hash
- semantic change changes hash
- provenance change does not change hash
- historical Phase 1 hash reproduces exactly

Embedding identity:
- deterministic
- revision-sensitive
- dimension-sensitive
- normalization-sensitive

Index identity:
- deterministic
- chunk-sensitive
- embedding-sensitive
- metric-sensitive
- index-type-sensitive

Manifest:
- required fields
- artifact type
- manifest version
- malformed hash rejection
- serialization round trip

Compatibility:
- valid chain passes
- stale chunk hash fails
- stale model revision fails
- dimension mismatch fails
- wrong metric fails
- schema-version mismatch fails
- eval-set mismatch fails
- failure is ArtifactCompatibilityError or repository-equivalent

Storage:
- different chunk configs -> different paths
- different embedding identities -> different artifact locations
- different index identities -> different index locations
- traversal protections remain intact
- legacy Phase 1 location still resolves

Local-data:
- Phase 1 chunk artifact compatible
- Phase 1 embedding artifact compatible
- Phase 1 LanceDB index compatible
- row counts remain 162,357
- no artifact mutation

---

# 49. Full Test Gate

Run:

    python scripts/dev.py doctor
    python scripts/dev.py test --portable
    python scripts/dev.py test

All failures must be investigated.

Do not dismiss a regression as unrelated without reproducing and proving
that conclusion.

Record exact final counts.

---

# 50. Acceptance Criteria

Task 2.10 is complete only when:

[ ] authoritative PROJECT_EXECUTION.md Task 2.10 contract verified

[ ] one canonical semantic-hash implementation exists
[ ] canonical serialization is deterministic
[ ] semantic/provenance fields are explicitly separated
[ ] NaN/Infinity/unsupported inputs fail loudly

[ ] chunk configuration hashing is centralized
[ ] existing Phase 1 hash reproduces exactly
[ ] Task 2.9 chunk UID behavior remains unchanged

[ ] chunk directories are versioned by semantic config identity
[ ] chunk artifact manifest contract exists

[ ] embedding-model identity includes repository + revision
[ ] embedding dimension stored
[ ] normalization/vector semantics stored
[ ] embedding artifacts bind to exact chunk config

[ ] index identity is explicit
[ ] index directories cannot collide across incompatible identities
[ ] index artifacts bind to chunk + embedding identity
[ ] distance/index configuration is recorded

[ ] eval_set_version is stored/reused from the authoritative Phase 2 eval
[ ] no duplicate eval-version convention introduced

[ ] stale-index/new-config mismatch fails loudly
[ ] embedding revision mismatch fails loudly
[ ] dimension mismatch fails loudly
[ ] schema-version mismatch fails loudly
[ ] eval-version mismatch fails loudly

[ ] no implicit "latest" artifact behavior exists

[ ] historical Phase 1 artifacts remain usable
[ ] historical Phase 1 artifacts are not rebuilt or rewritten
[ ] 162,357 chunk/embedding/index row chain validates

[ ] portable CI assertions cover artifact compatibility
[ ] real artifact checks are isolated behind local_data

[ ] TEST questions not loaded
[ ] official TEST runs remain 0/3

[ ] no network
[ ] no LLM
[ ] no API spend
[ ] no new GPU dependency

[ ] Task 2.9 regression passes
[ ] Task 2.8 regression passes
[ ] Task 2.1-2.7 regressions pass
[ ] Phase 1 regression passes
[ ] frozen data unchanged

[ ] project_plan/PHASE2_ARTIFACT_VERSIONING.md created
[ ] result summary written
[ ] repository structure updated narrowly
[ ] Progress.md appended
[ ] secret scan clean
[ ] git dry-run safe

[ ] one coherent Task 2.10 commit created
[ ] no Phase 2 completion tag created
[ ] Task 2.11 NOT started

---

# 51. Git

Before committing:

    git status --short
    git diff
    git diff --stat
    git add -n .

Confirm no:

    data/
    artifacts payloads
    .venv/
    .env
    *.duckdb
    model weights
    large Parquet artifacts
    LanceDB files

are staged.

Run the existing secret/personal-path checks.

Suggested commit message:

    Enforce artifact config compatibility

No Phase 2 tag.

No push if no remote exists.

---

# 52. Stop Conditions

STOP and surface the issue if:

A. The centralized hash cannot reproduce the frozen Phase 1 hash.

B. Implementing Task 2.10 would alter Task 2.9 chunk_uid identity.

C. The existing Phase 1 index cannot be associated unambiguously with its
embedding revision/config.

D. The current index path would cause two genuinely incompatible
configurations to collide and no backward-compatible resolution is clear.

E. The authoritative eval_set_version cannot be determined without opening
protected TEST question data.

F. Artifact compatibility requires inventing provenance that was never
recorded.

G. A historical artifact would need destructive migration.

H. A new rule belongs to Task 2.11 rather than artifact compatibility.

Never hide one of these by inventing a reasonable-looking value.

---

# 53. Final Console Summary

Print:

PHASE 2.10 — CONFIG HASHING & ARTIFACT VERSIONING
=================================================

Canonical hashing:
  implementation:                     <path>
  algorithm:                          SHA-256 / actual
  canonical serialization:           <description>
  deterministic:                     PASS

Chunk config:
  historical Phase 1 hash:           <hash>
  independently recomputed:          <hash>
  legacy compatibility:              PASS
  chunk schema version:              <version>

Chunk artifacts:
  versioned path contract:           <description>
  manifest contract:                 PASS
  historical artifact modified:      NO

Embedding identity:
  repository:                        <repo>
  revision:                          <revision>
  dimension:                         <dimension>
  normalize_embeddings:              <value>
  identity/hash:                     <value>

Index:
  versioned path contract:           <description>
  index identity:                    <value>
  metric:                            <metric>
  index type:                        <type>
  historical index modified:         NO

Eval:
  eval_set_version:                  <value>
  split version:                     <value>
  TEST loaded:                       NO
  official TEST runs used:           0 / 3

Compatibility checks:
  valid chain:                       PASS
  stale chunk config rejected:       PASS
  stale embedding rejected:          PASS
  dimension mismatch rejected:       PASS
  index-config mismatch rejected:    PASS
  schema mismatch rejected:          PASS
  eval-version mismatch rejected:    PASS

Real Phase 1 audit:
  chunks:                            162,357
  embeddings:                        162,357
  index rows:                        162,357
  chain compatible:                  PASS

Compute:
  network calls:                     0
  LLM calls:                         0
  API spend:                         $0
  new GPU requirement:               NO

Tests:
  new Task 2.10 tests:               <count>
  doctor:                            PASS
  portable:                          <result>
  full:                              <result>

Regression:
  Task 2.9:                          PASS
  Task 2.8:                          PASS
  Task 2.1-2.7:                      PASS
  Phase 1:                           PASS
  frozen data:                       PASS

Git:
  commit:                            <sha/message>
  Phase 2 tag created:               NO

FINAL RESULT:
PASS / PASS WITH NOTE / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
Task 2.11 — Evaluation run logging

DO NOT START TASK 2.11.

---

# Final Principle

A file existing at a plausible path is not proof that it is the correct
artifact.

After Task 2.10, every artifact consumer must be able to answer:

    Which chunk semantics created this?
    Which exact embedding semantics created these vectors?
    Which index configuration created this searchable index?
    Which evaluation version is this compatible with?

and must fail before evaluation if those identities disagree.

No silent stale artifacts.
No implicit latest version.
No model-name-only provenance.
No timestamp-based semantic identity.
No destructive migration of the Phase 1 baseline.
No TEST access.

Freeze compatibility before optimizing quality.