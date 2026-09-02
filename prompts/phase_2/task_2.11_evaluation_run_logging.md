# Task 2.11 — Evaluation Run Logging

## Phase

**Phase 2 — Make the Numbers Trustworthy**

Current confirmed repository state:

```text
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
  2.10 Config Hashing & Artifact Versioning   — COMPLETE
  2.11 Evaluation Run Logging                 — CURRENT
```

Do not start the next roadmap task during this task.

At Task 2.11 exit, re-read the repository's **current local**
`project_plan/PROJECT_EXECUTION.md` and report the exact next task.

Do not assume from this prompt that Task 2.11 closes Phase 2.

---

# 1. Objective

Implement the repository-wide **evaluation run logging contract** so every
future experiment produces a small, immutable, inspectable record describing:

```text
what code ran
what artifacts/configuration it used
what evaluation split it used
what metrics it produced
when it ran
```

The exact Task 2.11 contract from `PROJECT_EXECUTION.md` requires every
experiment to record:

```text
run_id
git_sha
chunk_config_hash
embedding model
retrieval config
reranker config
generation model
split
eval_set_version
timestamp
metrics
```

Task 2.11 must turn those fields into a validated, reusable, tested
engineering contract.

The central principle is:

```text
A metric without provenance is not an experiment result.
```

After this task, future Phase 3 comparisons must not exist only as console
output, screenshots, or manually copied numbers.

---

# 2. Scope

Task 2.11 owns:

```text
evaluation-run record schema
run IDs
timestamp semantics
Git provenance
artifact/config identity references
retrieval/reranker/generation configuration logging
split/eval-set identity
metric logging
validation
immutable run-record persistence
safe tracked storage
read/load helpers
tests
documentation
```

Task 2.11 does NOT own:

```text
new retrieval algorithms
BM25
hybrid retrieval
reranking implementation
CRAG
routers
chunking ablations
embedding-model comparisons
generation-model comparisons
new evaluation metrics
LLM-as-judge
FinanceBench
Phase 3 baseline evaluation
TEST evaluation
```

Do not optimize anything.

---

# 3. Read Authoritative Sources First

Before changing code, inspect the real repository.

At minimum read:

1. `project_plan/PROJECT_EXECUTION.md`
2. `Progress.md`
3. `project_plan/PHASE2_ARTIFACT_VERSIONING.md`
4. `src/artifacts/versioning.py`
5. `results/phase_2_10_artifact_versioning.json`
6. `project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md`
7. `src/chunk/metadata_schema.py`
8. `project_plan/PHASE2_EVALUATION_SCHEMA.md`
9. `src/eval/evaluation_schema.py`
10. Task 2.3 evaluation-dataset config/summary
11. Task 2.4 split config/summary
12. Task 2.5 evaluation-schema config/summary
13. `src/eval/metrics.py` or actual metric module(s)
14. `scripts/run_baseline_metric.py`
15. `src/cli/phase1.py`
16. MS MARCO evaluation runner
17. existing SEC evaluation scripts, if any
18. `src/storage.py`
19. `project_plan/GIT_CONVENTIONS.md`
20. `project_plan/REPOSITORY_STRUCTURE.md`
21. `.gitignore`

Do not invent a second representation of identities Task 2.10 already
froze.

---

# 4. Establish Baseline

Before modifying anything:

```bash
git branch
git status --short
git log --oneline --decorate -15

python --version
python -c "import sys; print(sys.executable)"

python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Record:

```text
HEAD
working-tree state
portable-test count
full-test count
official SEC TEST runs consumed
```

Task 2.10's confirmed final full suite was:

```text
952 passed
```

Verify the actual current count rather than blindly copying it.

---

# 5. Verify Task 2.10 Before Building on It

Independently confirm the Task 2.10 contract exists.

At minimum verify:

```text
src/artifacts/versioning.py
ARTIFACT_MANIFEST_VERSION
ArtifactCompatibility
assert_artifact_compatible()
ArtifactCompatibilityError

chunk_config_hash
embedding_identity_hash
index_identity_hash
eval_set_version
```

Known current identities include:

```text
Phase 1 chunk_config_hash:
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

embedding identity hash:
b39a67c9eb6487fc98f266f23742afd0a30321d98067505802a1e219b27bec84

index identity hash:
ace70ee67d8e98e019d221f2a0215a5b88498a0fc5dcbe73ac7ef1277630b111

eval_set_version:
phase2-v1

split_version:
phase2-split-v1
```

Verify from real tracked files.

Do not hardcode these values as the Task 2.11 implementation.
They are historical/current values, not library constants.

---

# 6. Do Not Duplicate Artifact Identity Logic

Task 2.10 already owns:

```text
canonical JSON
semantic hashing
chunk_config_hash
embedding identity
index identity
artifact compatibility
eval_set_version binding
```

Task 2.11 should **consume** those identities.

Do not reimplement semantic identity hashing for artifacts.
Reuse Task 2.10 utilities.

A run record may have its own integrity hash, but that is distinct from
artifact/config hashes.

---

# 7. Recommended Module

Create a focused module such as:

```text
src/eval/run_logging.py
```

unless repository inspection reveals a clearly better existing location.

Suggested responsibilities:

```text
EvaluationRunRecord
RunLogError
RunLogValidationError

generate_run_id()
current_git_state()
build_run_record(...)
validate_run_record(...)
write_run_record(...)
load_run_record(...)
compute_run_record_sha256(...)
```

Keep the API small.

---

# 8. Run-Log Schema Version

Define an explicit run-record schema version.

Suggested:

```text
EVALUATION_RUN_SCHEMA_VERSION = 1
```

This is separate from:

```text
chunk_schema_version
artifact_manifest_version
eval_set_version
split_version
```

Do not overload those concepts.

---

# 9. Mandatory Task 2.11 Fields

Every run record must explicitly contain the roadmap-required fields:

```text
run_id
git_sha
chunk_config_hash
embedding_model
retrieval_config
reranker_config
generation_model
split
eval_set_version
timestamp
metrics
```

Do not make required roadmap fields disappear merely because their value is
not applicable.

When something genuinely does not apply, encode the absence explicitly.

Example:

```json
"generation_model": null
```

is preferable to silently omitting the key for a retrieval-only run.

---

# 10. Recommended Additional Provenance

Because Task 2.10 now has trustworthy artifact identities, strongly prefer
also recording:

```text
run_schema_version
chunk_schema_version
embedding_identity_hash
index_identity_hash
split_version
eval_dataset_sha256
split_sha256
git_dirty
run_record_sha256
```

Potentially useful:

```text
experiment_name
run_kind
notes
```

These extensions must remain clearly distinct from the mandatory roadmap
fields.

Do not turn the schema into a giant telemetry system.

---

# 11. run_id Contract

`run_id` identifies **one execution**, not one semantic configuration.

Therefore:

```text
same config run twice
    -> different run_id
```

Do not use configuration hash as `run_id`.

Recommended implementation:

```text
UUIDv4 using Python stdlib uuid.uuid4()
```

Requirements:

```text
unique
filename-safe
opaque
not semantically meaningful
not based on local machine path
```

Allow run ID injection in tests.

Do not use Python `hash()`.

---

# 12. Timestamp Contract

Freeze timestamps as:

```text
UTC
timezone-aware
ISO 8601
ending in Z
```

Example:

```text
2026-09-02T15:42:13.123456Z
```

Do not use local naive time, locale-formatted dates, or mtime as experiment
time.

Allow clock injection for tests.

---

# 13. Git Provenance

Every run must record:

```text
git_sha
```

Resolve with:

```bash
git rev-parse HEAD
```

Prefer the full commit SHA.

Also record:

```text
git_dirty: true/false
```

because same `git_sha` + uncommitted code is not truly the same source
state.

Do not refuse to log a dirty run automatically unless an existing project
policy explicitly requires that. Record it honestly.

---

# 14. git_sha Validation

Validate Git SHA shape.

For the normal current repository:

```text
40 lowercase hexadecimal characters
```

Do not silently accept `HEAD`, `main`, `latest`, or `unknown` for a normal
project experiment.

If Git provenance genuinely cannot be resolved, fail loudly rather than
pretending the run is reproducible.

---

# 15. chunk_config_hash

Use the exact Task 2.10/Phase 1 semantic chunk hash.

Validate:

```text
64 lowercase hexadecimal characters
```

Do not recompute it from a partial run config.
Do not let callers supply a chunk config hash inconsistent with the
artifact-compatibility snapshot.

---

# 16. embedding_model

The roadmap says `embedding model`.

Do not log only the repository name. Task 2.10 proved that a repository
name alone is insufficient.

Represent the embedding model using the existing Task 2.10 identity.

Recommended shape:

```json
{
  "repository": "BAAI/bge-small-en-v1.5",
  "revision": "...",
  "dimension": 384,
  "vector_dtype": "float32",
  "normalize_embeddings": true,
  "identity_hash": "..."
}
```

Use the actual existing identity field names where possible.

Do not create a competing embedding-identity schema.

---

# 17. retrieval_config

`retrieval_config` should be a structured JSON object, not an opaque string.

It should contain exactly the settings that define the retrieval behavior of
the run.

Examples may include:

```text
method
top_k
distance_metric
index_type
candidate_pool
metadata_filters
query convention
hybrid weights
```

Only include fields actually relevant to the implementation being run.

For the current Phase 1 baseline, likely values include:

```text
vector-only
exact flat search
cosine
k
```

Do not claim BM25/reranking/hybrid configuration exists when it does not.

---

# 18. retrieval_config Hash

Optionally compute:

```text
retrieval_config_hash
```

using Task 2.10's canonical semantic-hash utility.

This is useful for later ablation tables.

If implemented, semantic config only must be hashed.

Do not include:

```text
run_id
timestamp
git_sha
metrics
```

in retrieval_config_hash.

---

# 19. reranker_config

The roadmap requires the field even when no reranker exists.

Use an explicit contract such as:

```json
{
  "enabled": false
}
```

For a future enabled reranker:

```json
{
  "enabled": true,
  "model": "...",
  "revision": "...",
  "input_candidates": 50,
  "output_k": 10
}
```

Keep it machine-readable.

---

# 20. generation_model

For retrieval-only evaluations:

```json
"generation_model": null
```

For generation evaluations use a structured object such as:

```json
{
  "provider": "openrouter",
  "model": "openai/gpt-oss-20b"
}
```

Do not record API keys, Authorization headers, or raw provider requests.

If generation parameters such as temperature materially affect an
experiment, record them in a small generation config extension rather than
hiding them.

Do not make an API call during Task 2.11 merely to test logging.

---

# 21. split

The split must be explicit.

Examples:

```text
dev
ci
test
```

or existing repository-equivalent values.

Do not infer the split from filename, directory, or question count.

The run logger itself must NEVER load TEST to determine the split.
It receives split identity as metadata.

---

# 22. eval_set_version

Use the frozen Task 2.3/2.4 value.

Current expected value:

```text
phase2-v1
```

Verify it.

Do not create `phase2-v2` just because Task 2.11 is a new task.

---

# 23. split_version and Split Hash

Strongly prefer recording:

```text
split_version
split_sha256
```

For current Phase 2:

```text
split_version = phase2-split-v1
```

Resolve the appropriate digest from already-tracked Task 2.4 metadata:

```text
DEV run -> dev_sha256
CI run  -> ci_sha256
TEST run -> test_sha256
```

Do not open TEST question payloads just to obtain the hash.
The frozen TEST digest is already metadata.

---

# 24. metrics

`metrics` must be a machine-readable mapping.

Recommended initial contract:

```text
dict[str, int | float]
```

Rules:

```text
metric name non-empty
metric value finite
bool rejected as numeric metric
NaN rejected
Infinity rejected
```

Examples:

```json
{
  "doc_recall@10": 0.97
}
```

Do not store formatted values such as `"97%"` or `"0.97 (good)"` inside
`metrics`.

Explanatory text belongs in optional notes.

---

# 25. Unavailable Metrics

Do not invent `0.0` for metrics that are unavailable.

Task 2.8 currently has:

```text
gold_evidence_count = 0
chunk_recall@10 unavailable_for_current_gold
chunk_mrr unavailable_for_current_gold
```

Do not log unavailable metrics as zero.
Either omit them from `metrics` or explicitly use a separate status field.

The distinction between metric=0 and metric cannot currently be computed
must remain intact.

---

# 26. Artifact Compatibility Snapshot

For SEC retrieval experiments, the run record should bind to Task 2.10's
compatibility contract.

Prefer recording:

```text
chunk_schema_version
chunk_config_hash
embedding_identity_hash
index_identity_hash
eval_set_version
```

using `ArtifactCompatibility` or the repository's actual Task 2.10 API.

Before writing a SEC evaluation run record, verify its artifact identity is
internally compatible.

If incompatible, do not write a successful run record.
Raise the existing `ArtifactCompatibilityError` or a narrow wrapper
preserving the original cause.

Do not turn a compatibility failure into a warning.

---

# 27. Do Not Copy Whole Manifests Into Every Run

Task 2.10 sidecars already contain detailed artifact provenance.

A run record should reference identities, not duplicate hundreds of lines.

Good:

```text
chunk_config_hash
embedding_identity_hash
index_identity_hash
artifact manifest relative paths if useful
```

Avoid duplicating entire Parquet schemas, all manifest fields, or all source
file names.

Run logs should remain small.

---

# 28. Run Record Immutability

One run record represents one historical execution.

Once written:

```text
do not edit it in place
do not overwrite it with a later run
```

If the same experiment is repeated:

```text
new run_id
new run record
```

---

# 29. Recommended Storage Layout

Prefer small tracked JSON records:

```text
results/eval_runs/<run_id>.json
```

This fits the existing Git convention: small evaluation results are tracked,
large generated artifacts are ignored.

Before adopting the path:

```bash
git check-ignore -v results/eval_runs/example.json
```

If the existing `.gitignore` accidentally prevents tracking nested JSON
results, make only the minimum necessary exception.

Do not weaken protection on arbitrary generated artifacts.

Do not store run records under the top-level ignored `artifacts/` root if
that would make future experiment history disappear from Git.

---

# 30. Do Not Use One Giant Mutable JSON File

Avoid:

```text
results/evaluation_runs.json
```

with one continuously appended array if possible.

Prefer:

```text
one immutable JSON file per run
```

This naturally maps:

```text
run_id -> filename
```

---

# 31. JSON Output

Run records should be:

```text
UTF-8
valid JSON
human-readable
stable key ordering
one trailing newline
```

Use deterministic serialization for file writing where practical.

The file itself will differ between executions because run_id, timestamp,
metrics, and possibly git state are run-specific.

---

# 32. run_record_sha256

Strongly recommended:

```text
run_record_sha256
```

computed from the canonical JSON representation of the complete run record
excluding the `run_record_sha256` field itself.

Purpose:

```text
detect accidental record mutation
verify round trips
```

This is NOT a chunk config hash, retrieval config hash, or artifact identity.

---

# 33. Atomic / Exclusive Write

A run record must not be partially written.

Use a safe create-once strategy.

Requirements:

```text
parent directory created explicitly
target filename derived from validated run_id
existing target -> fail
partial write -> no valid-looking run record
```

Do not silently overwrite an existing run ID.

---

# 34. Validation Before Write

`write_run_record()` should validate the complete record first.

At minimum reject:

```text
missing mandatory field
empty run_id
malformed UUID
malformed git_sha
malformed chunk_config_hash
malformed identity hash
empty eval_set_version
empty split
naive timestamp
non-UTC timestamp
NaN/Infinity metric
boolean metric
non-JSON config
secret-looking fields
```

Do not write first and validate later.

---

# 35. Secret Safety

Run records are expected to be Git-trackable.

Therefore secret handling must be strict.

Reject configuration keys matching obvious credential patterns such as:

```text
api_key
apikey
password
secret
authorization
bearer
credential
token
```

case-insensitively.

Apply recursively through retrieval_config, reranker_config, generation
configuration, and other structured metadata.

Do not merely redact silently.
Fail the run-record write with a clear message so the caller fixes its
configuration.

Never log API keys, raw authorization headers, `.env` contents, or cloud
credentials.

---

# 36. Avoid Personal Absolute Paths

Do not put developer-specific absolute filesystem paths into tracked run
records.

Prefer repository-relative artifact references and semantic artifact IDs.

The same run schema must work on another machine.

---

# 37. Read API

Provide a validation-preserving read path.

Conceptually:

```python
load_run_record(path) -> EvaluationRunRecord
```

It must parse JSON, validate schema, verify `run_record_sha256` if present,
and reject malformed records.

---

# 38. Listing / Discovery

A small helper may list run records.

If implemented, sort deterministically.

Do not introduce implicit `latest run`, `current run`, or `newest successful
run` semantics.

Callers should select a run explicitly.

---

# 39. No Hidden Runtime State

Do not rely on global mutable variables such as:

```text
CURRENT_RUN_ID
CURRENT_EXPERIMENT
LAST_METRICS
```

A run record should be constructed from explicit inputs.

---

# 40. Existing Evaluation Runners

Inspect all existing evaluation entry points.

At minimum:

```text
scripts/run_baseline_metric.py
Phase 1 CLI evaluate command
MS MARCO harness runner
Phase 2 metric scripts
```

Determine whether a **single safe integration point already exists**.

If one exists, integrate Task 2.11 logging there narrowly without changing
metric semantics.

If no unified experiment runner exists:

```text
do NOT invent a fake evaluation run
do NOT start Phase 3
```

Instead expose the reusable logging API and document that future experiment
runners MUST call it.

Do not broadly refactor all historical scripts merely to retrofit run logs.

---

# 41. Historical Runs

Do not fabricate Task 2.11 run records for Tasks 1.x or 2.1–2.10 unless
every required field can be established from authoritative existing
metadata.

If historical import is useful and completely supported, it must say:

```text
record_origin: historical_import
```

and preserve the original run's Git SHA/timestamp where known.

Do NOT use today's git_sha/timestamp and pretend they describe an old
experiment.

Default recommendation:

```text
do not backfill historical runs unless provenance is complete
```

---

# 42. Do Not Create a Fake First Experiment

Task 2.11 does not need to manufacture a performance number merely so
`results/eval_runs/` is non-empty.

Portable tests may write synthetic run records under `tmp_path`.

If there is no honest real experiment to log without crossing into a later
task:

```text
leave the real run directory empty until the next actual experiment
```

An empty trusted ledger is better than a fake historical record.

---

# 43. Future Phase 3 Contract

Document explicitly that future Phase 3 experiments must follow:

```text
1. resolve configuration
2. assert artifact compatibility
3. run evaluation
4. calculate metrics
5. construct EvaluationRunRecord
6. validate
7. write immutable run record
8. report run_id
```

A Phase 3 result should therefore always be attributable to one `run_id`.

---

# 44. TEST Discipline

Task 2.11 has no reason to load TEST questions.

Do NOT open the TEST question dataset, call `load_test_set()`, run retrieval
on TEST, run generation on TEST, or increment TEST budget.

Reading already-tracked TEST metadata such as `test_sha256`, `split_version`,
and `eval_set_version` is allowed.

Official TEST evaluations must remain:

```text
0 / 3
```

The run logger itself should never load any dataset.
It receives split identity as metadata.

---

# 45. CI Split Safety

Task 2.4 created the CI subset from DEV.

Task 2.11 tests may use synthetic data, temporary records, and existing
metadata.

If one real integration run is truly needed, use CI/DEV only.

Do not use TEST.

---

# 46. No New Metric Semantics

Do not modify Recall@K, MRR, nDCG, exact match, refusal metrics, or any
other metric semantics.

Task 2.11 records metrics.
It does not redefine them.

---

# 47. No Automatic Metric Recalculation

The logging layer should not independently calculate metrics from raw
predictions.

Good separation:

```text
metric runner calculates metrics
logger records finalized metric mapping
```

---

# 48. No Raw Question/Answer Dumps

The canonical run record should contain aggregate provenance and metrics.

Do not store all questions, retrieved chunks, prompts, generated answers,
or per-query traces inside every run record.

Those may later belong in separately versioned artifacts if needed.

---

# 49. No Network / LLM / GPU Requirement

Task 2.11 itself should require:

```text
no network
no OpenRouter
no OpenAI
no Anthropic
no SEC request
no Hugging Face download
no AWS
no new model load
```

No API spend.
No new GPU requirement.

The new run-logging tests must be CPU-only and portable.

---

# 50. No Large Artifact Rebuilds

Do NOT rerun:

```text
Task 1.3 chunking
Task 1.4 embedding
Task 1.5 index build
MS MARCO full embedding/index build
Task 2.8 990-document parser
```

Task 2.11 should finish quickly.

---

# 51. Proposed Record Example

Use actual final field names chosen by the implementation, but the semantic
shape should resemble:

```json
{
  "run_schema_version": 1,
  "run_id": "c0a8012f-85bd-4ea3-9037-3127a75f34a2",

  "git_sha": "0123456789abcdef0123456789abcdef01234567",
  "git_dirty": false,

  "chunk_schema_version": 1,
  "chunk_config_hash": "f1dc...",

  "embedding_model": {
    "repository": "BAAI/bge-small-en-v1.5",
    "revision": "5c38...",
    "dimension": 384,
    "vector_dtype": "float32",
    "normalize_embeddings": true,
    "identity_hash": "b39a..."
  },

  "index_identity_hash": "ace7...",

  "retrieval_config": {
    "method": "vector",
    "index_type": "exact_flat",
    "distance_metric": "cosine",
    "top_k": 10
  },

  "reranker_config": {
    "enabled": false
  },

  "generation_model": null,

  "split": "dev",
  "eval_set_version": "phase2-v1",
  "split_version": "phase2-split-v1",
  "split_sha256": "...",

  "timestamp": "2026-09-02T15:42:13.123456Z",

  "metrics": {
    "doc_recall@10": 0.97
  },

  "run_record_sha256": "..."
}
```

This is illustrative.
Do not copy fake hashes or fake metrics into the real repository.

---

# 52. Validation API

Recommended pattern:

```python
record = build_run_record(...)
validate_run_record(record)
path = write_run_record(record)
loaded = load_run_record(path)
```

Tests should verify:

```text
loaded == written
hash verifies
```

---

# 53. Dataclass vs TypedDict

Use the repository's established Python style.

A frozen dataclass is reasonable.

Do not add Pydantic solely for Task 2.11 unless it is already the project's
standard for internal schemas.

No new dependency should be necessary.

---

# 54. Retrieval Config Canonicalization

When computing optional config fingerprints, use the Task 2.10 canonical
semantic hash utility.

Verify:

```text
same config different dict order -> same hash
different top_k -> different hash
different metric -> different hash
different index type -> different hash
```

---

# 55. Reranker Config Canonicalization

Verify:

```text
enabled=false
```

differs semantically from:

```text
enabled=true + model X
```

and model revision A differs from model revision B.

No reranker implementation is needed.

---

# 56. Generation Configuration

If generation is enabled in a future run, preserve at least:

```text
provider
model
```

Potentially temperature/max tokens when they affect experiment behavior.

Task 2.11 should define where those parameters belong without performing a
generation experiment.

Do not put secrets in the config.

---

# 57. Run Record Integrity Tests

Add tests that intentionally modify an already-written record.

Examples:

```text
metric changed
git_sha changed
chunk_config_hash changed
```

Loading should detect a `run_record_sha256` mismatch.

---

# 58. Duplicate Run ID Test

Write one record.
Attempt to write another record with the same `run_id`.

Expected:

```text
FAIL loudly
original file unchanged
```

Never overwrite.

---

# 59. Tests

Create:

```text
tests/test_evaluation_run_logging.py
```

or repository-equivalent.

At minimum test:

### Required fields

```text
all PROJECT_EXECUTION.md Task 2.11 fields present
missing required field rejected
```

### Run IDs

```text
UUIDv4 generated
different calls -> different IDs
injected ID preserved
malformed ID rejected
```

### Timestamp

```text
UTC Z form accepted
naive timestamp rejected
injected clock deterministic
```

### Git

```text
full SHA accepted
malformed SHA rejected
dirty flag retained
```

### Hashes

```text
chunk_config_hash validated
embedding identity hash validated
index identity hash validated
run_record_sha256 deterministic
tampering detected
```

### Embedding model

```text
repository/revision/dimension/normalization retained
missing revision rejected for a Task 2.10-backed SEC run
```

### Retrieval config

```text
structured mapping required
top-k change changes optional config hash
key order does not
```

### Reranker

```text
explicit disabled config accepted
invalid enabled config rejected if required fields absent
```

### Generation

```text
null accepted for retrieval-only
provider/model accepted when enabled
secret field rejected
```

### Split/eval version

```text
split required
eval_set_version required
split_version retained
split digest retained
```

### Metrics

```text
integer accepted
float accepted
zero accepted
negative value accepted if metric semantics permit generic numeric storage
bool rejected
NaN rejected
+Inf rejected
-Inf rejected
empty metric name rejected
```

### Persistence

```text
write/read round trip
one trailing newline
duplicate run ID rejected
invalid record never written
```

### Security

```text
api_key rejected recursively
authorization rejected recursively
password rejected recursively
token rejected recursively
no credential value appears in exception output
```

### Integrity

```text
record tampering detected
```

---

# 60. Task 2.10 Integration Test

Add at least one portable synthetic integration test using
`ArtifactCompatibility`.

Verify:

```text
compatible artifact snapshot -> run record can be built
chunk mismatch -> ArtifactCompatibilityError
embedding mismatch -> ArtifactCompatibilityError
index mismatch -> ArtifactCompatibilityError
eval version mismatch -> ArtifactCompatibilityError
```

Do not create duplicate compatibility logic.

---

# 61. Local-Data Test

A small `local_data` test may verify the real Phase 1 artifact identities can
populate a run record.

It should read manifests only, validate Task 2.10 compatibility, build a
record in `tmp_path`, and write/read it.

It must NOT load the embedding model, run retrieval, run evaluation, or
touch TEST.

---

# 62. Real Metadata Verification

Use actual Task 2.4 metadata read-only.

Confirm:

```text
eval_set_version = phase2-v1
split_version = phase2-split-v1
DEV hash exists
CI hash exists
TEST hash metadata exists
```

Do NOT load TEST questions.

Report:

```text
TEST payload opened: NO
official TEST evaluations: 0 / 3
```

---

# 63. Audit Script

Create a lightweight script such as:

```text
scripts/audit_evaluation_run_logging.py
```

It should verify:

```text
run schema
required fields
Task 2.10 compatibility integration
eval/split metadata availability
secret rejection
duplicate-ID behavior
tamper detection
tracked path behavior
TEST discipline
```

No actual retrieval evaluation is required.

Write:

```text
results/phase_2_11_evaluation_run_logging.json
```

with summary diagnostics.

Do not put fake performance metrics into the summary.

---

# 64. Optional CLI

If useful, provide a small inspection command such as:

```bash
python scripts/audit_evaluation_run_logging.py
```

Do not build a general experiment-management CLI.

---

# 65. Do Not Add MLflow / W&B

Do NOT introduce MLflow, Weights & Biases, Neptune, Comet, a database
server, or a cloud tracking service.

Tracked immutable JSON run records are sufficient.

No new account or external service should be required.

---

# 66. Result Summary

`results/phase_2_11_evaluation_run_logging.json` should include at minimum:

```text
run_schema_version
mandatory_field_count
mandatory_fields
storage_contract
task_2_10_integration
artifact_compatibility_enforced
eval_set_version
split_version
test_payload_accessed
official_test_runs_used
secret_rejection_tests
tamper_detection
duplicate_run_id_detection
new_test_count
portable_test_result
full_test_result
git_sha
created_at_utc
```

Do not confuse this Task-summary file with an actual experiment run record.

---

# 67. Documentation

Create:

```text
project_plan/PHASE2_EVALUATION_RUN_LOGGING.md
```

Document:

- purpose;
- run-record schema;
- required Task 2.11 fields;
- schema version;
- run ID semantics;
- timestamp semantics;
- Git provenance;
- dirty-tree semantics;
- chunk config identity;
- embedding identity;
- retrieval config;
- reranker config;
- generation model;
- split/eval-set identity;
- metrics contract;
- artifact compatibility;
- run-record integrity hash;
- persistence layout;
- immutability;
- secret policy;
- historical-run policy;
- TEST policy;
- example record using clearly fake values;
- future Phase 3 workflow.

Explicitly state:

```text
Task 2.10 answers:
"Are these artifacts compatible?"

Task 2.11 answers:
"What exactly produced this metric?"
```

---

# 68. Repository Structure

Update:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

narrowly.

Likely additions:

```text
src/eval/run_logging.py
scripts/audit_evaluation_run_logging.py
tests/test_evaluation_run_logging.py
results/phase_2_11_evaluation_run_logging.json
project_plan/PHASE2_EVALUATION_RUN_LOGGING.md
results/eval_runs/     # if adopted
```

Do not make unrelated tree changes.

---

# 69. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.11 Evaluation Run Logging
```

Include:

```text
Objective
Initial State
Authoritative Contract
Run Schema
Run ID Contract
Timestamp Contract
Git Provenance
Artifact Compatibility Integration
Embedding Model Contract
Retrieval Config
Reranker Config
Generation Model
Split / Eval-Set Identity
Metrics Contract
Persistence
Immutability
Run-Record Integrity
Security
TEST Discipline
Tests
Regression Gates
Frozen Data
Files Created/Modified
Git
Result
Phase Status
```

Do not rewrite historical task entries.

---

# 70. Regression Gate — Task 2.10

Verify:

```text
canonical hashing unchanged
historical chunk_config_hash unchanged
embedding identity hash unchanged
index identity hash unchanged
ArtifactCompatibility semantics unchanged
manifest semantics unchanged
```

Known current chain should remain:

```text
chunks:       162,357
embeddings:   162,357
index:        162,357
compatible:   PASS
```

Do not modify historical manifest identities.

---

# 71. Regression Gate — Task 2.9

Verify:

```text
CHUNK_SCHEMA_VERSION unchanged
canonical fields unchanged
chunk_uid algorithm unchanged
162,357 derived Phase 1 UIDs remain unique
```

No chunk schema modification is needed for run logging.

---

# 72. Regression Gate — Task 2.8

Preserve:

```text
990/990 parsed
0 parse failures
gold_evidence_count = 0
45,769 would-be-gold facts remain ineligible by frozen year window
```

Do not promote them.
Do not change evidence-metric availability.

---

# 73. Regression Gate — Evaluation

Do not change:

```text
Task 2.3 dataset
Task 2.4 DEV/TEST split
Task 2.5 schema
Task 2.6 metric semantics
Task 2.7 MS MARCO result
```

Task 2.11 only records evaluation outcomes.

---

# 74. Regression Gate — Phase 1

Do not change chunking, embeddings, index ranking, retriever behavior,
generation behavior, citation behavior, or Phase 1 smoke metric.

Historical Phase 1:

```text
200 questions
194 hits
doc_recall@10 = 0.970000
```

must remain historical fact.

Do not rerun it merely to create a Task 2.11 record unless repository
inspection proves an honest, necessary integration run is required.

---

# 75. Frozen Data

Verify unchanged:

```text
data/xbrl.duckdb
data/edgar_corpus/
data/raw/xbrl/
data/raw/primary/
data/msmarco/
```

Known `xbrl.duckdb` size:

```text
7,011,053,568 bytes
```

Task 2.11 requires no frozen-data write.

---

# 76. Full Test Gate

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Record exact counts.

All failures must be investigated.

---

# 77. Git Safety

Before commit:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Verify no data, artifact payloads, `.venv`, `.env`, DuckDB files, large
Parquet files, model weights, LanceDB payloads, or API credentials are
staged.

Verify actual run-record directory behavior if that location is used.

Run the repository's existing secret/personal-path scan.

---

# 78. Commit

Create one coherent Task 2.11 commit after all gates pass.

Suggested commit message:

```text
Add reproducible evaluation run logging
```

Do not create a Phase 2 completion tag automatically.

Whether Phase 2 closes after Task 2.11 must come from the **current local
PROJECT_EXECUTION.md**, not from assumptions in this prompt.

No push if no remote exists.

---

# 79. Stop Conditions

STOP and surface the issue if:

### A. Task 2.10 identities cannot be consumed cleanly

Do not create duplicate identity logic.

### B. Current eval_set_version cannot be established without reading TEST

Do not read TEST.

### C. Required historical provenance is missing

Do not fabricate old run records.

### D. A proposed run-log location would silently be Git-ignored

Fix the narrow tracking rule or choose another repository-approved location.

### E. Existing evaluation runner integration would change metric semantics

Do not alter the metric just to add logging.

### F. Run logging would require a real Phase 3 evaluation

Do not start Phase 3.

### G. A field would contain an API key or credential

Reject it.

### H. The local authoritative roadmap disagrees with assumptions about what
comes after 2.11

Report the exact local roadmap.
Do not guess.

---

# 80. Acceptance Criteria

Task 2.11 is complete only when:

```text
[ ] authoritative Task 2.11 contract verified from PROJECT_EXECUTION.md

[ ] evaluation run schema version defined
[ ] one canonical run-log implementation exists

[ ] run_id required
[ ] run_id unique per execution
[ ] run_id not a semantic/config hash

[ ] git_sha required
[ ] git_sha validated
[ ] dirty working-tree status recorded

[ ] chunk_config_hash required
[ ] Task 2.10 chunk identity reused

[ ] embedding model recorded
[ ] repository recorded
[ ] revision recorded
[ ] embedding identity hash reused

[ ] retrieval_config structured
[ ] retrieval semantics are machine-readable

[ ] reranker_config structured
[ ] disabled reranker explicitly represented

[ ] generation_model explicitly represented
[ ] retrieval-only run can represent generation_model=null

[ ] split required
[ ] eval_set_version required
[ ] split_version recorded
[ ] appropriate split hash supported

[ ] timestamp UTC and timezone-aware

[ ] metrics mapping validated
[ ] NaN/Inf rejected
[ ] bool metric rejected
[ ] unavailable metrics are not fabricated as 0

[ ] Task 2.10 artifact compatibility checked before SEC run logging
[ ] compatibility mismatch fails loudly

[ ] run records immutable
[ ] duplicate run ID cannot overwrite prior record
[ ] run records written safely
[ ] run records load/validate successfully

[ ] run_record_sha256 or equivalent integrity mechanism implemented if adopted
[ ] tampering detected

[ ] tracked run-record location established
[ ] run records are small
[ ] no raw questions/prompts/chunks dumped into canonical run record

[ ] secret-looking keys rejected recursively
[ ] no API credentials stored

[ ] no fake historical runs created
[ ] no fake first experiment created solely to populate the directory

[ ] tests are portable
[ ] Task 2.10 integration tests pass
[ ] local_data test, if implemented, performs no retrieval/model load

[ ] TEST question payload not opened
[ ] official TEST evaluations remain 0/3

[ ] no network
[ ] no LLM calls
[ ] no API spend
[ ] no new GPU dependency
[ ] no large artifact rebuild

[ ] Task 2.10 regression PASS
[ ] Task 2.9 regression PASS
[ ] Task 2.8 regression PASS
[ ] Task 2.1-2.7 regression PASS
[ ] Phase 1 regression PASS
[ ] frozen data unchanged

[ ] PHASE2_EVALUATION_RUN_LOGGING.md created
[ ] phase_2_11 summary written
[ ] repository structure updated
[ ] Progress.md appended
[ ] secret scan clean
[ ] Git dry-run safe
[ ] coherent Task 2.11 commit created

[ ] next roadmap task determined from current local PROJECT_EXECUTION.md
[ ] next task NOT started
```

---

# 81. Final Console Summary

Print:

```text
PHASE 2.11 — EVALUATION RUN LOGGING
===================================

Run schema:
  version:                          <version>
  implementation:                   <path>
  mandatory roadmap fields:         11 / 11
  validation:                       PASS

Run identity:
  run_id format:                    <format>
  unique per execution:             PASS
  immutable records:                PASS
  duplicate-ID overwrite blocked:   PASS

Git provenance:
  git_sha recorded:                 PASS
  dirty state recorded:             PASS

Artifacts:
  chunk_config_hash:                <verified hash>
  embedding identity hash:          <verified hash>
  index identity hash:              <verified hash>
  Task 2.10 compatibility:          PASS

Evaluation:
  eval_set_version:                 phase2-v1 / actual
  split_version:                    phase2-split-v1 / actual
  split hash support:               PASS
  TEST payload opened:              NO
  official TEST runs used:          0 / 3

Config logging:
  embedding model:                  PASS
  retrieval config:                 PASS
  reranker config:                  PASS
  generation model:                 PASS

Metrics:
  numeric validation:               PASS
  NaN/Inf rejection:                PASS
  unavailable-as-zero prevented:    PASS

Persistence:
  run-record location:              <path>
  write/read round trip:            PASS
  integrity verification:           PASS
  tamper detection:                 PASS

Security:
  recursive secret rejection:       PASS
  secrets found in records:         0
  personal absolute paths:          0

Historical policy:
  fabricated historical runs:       0
  fake performance runs:             0

Compute:
  network calls:                     0
  LLM calls:                         0
  API spend:                         $0
  new GPU requirement:               NO

Tests:
  new Task 2.11 tests:               <count>
  doctor:                            PASS
  portable:                          <result>
  full:                              <result>

Regression:
  Task 2.10:                         PASS
  Task 2.9:                          PASS
  Task 2.8:                          PASS
  Task 2.1-2.7:                      PASS
  Phase 1:                           PASS
  frozen data:                       PASS

Git:
  commit:                            <sha/message>
  phase-completion tag created:      NO unless authoritative exit review requires it

FINAL RESULT:
PASS / PASS WITH NOTE / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
<derive from current PROJECT_EXECUTION.md>

NEXT:
<exact next task from current PROJECT_EXECUTION.md>

DO NOT START THE NEXT TASK.
```

---

# Final Principle

Task 2.10 made artifact identity trustworthy.

Task 2.11 makes **experiment history** trustworthy.

A future table saying:

```text
Run A: nDCG@10 = 0.412
Run B: nDCG@10 = 0.438
```

is meaningless unless we can reconstruct:

```text
which code
which chunks
which embedding revision
which index
which retrieval settings
which reranker
which generation model
which split
which eval-set version
which timestamp
```

produced each number.

After Task 2.11:

```text
metric
+
configuration
+
artifact identity
+
code identity
+
evaluation identity
=
reproducible experiment
```

No orphan metrics.
No overwritten run records.
No implicit latest.
No fabricated historical provenance.
No secrets in tracked records.
No TEST access.
Every real experiment gets a run ID.
