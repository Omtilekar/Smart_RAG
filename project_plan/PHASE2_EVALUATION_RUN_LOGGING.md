# Phase 2 Evaluation Run Logging

Established in Task 2.11. Freezes the repository-wide evaluation-run
record contract: one small, immutable, git-tracked JSON file per
execution, binding a metric to the exact code, artifacts, configuration,
and evaluation identity that produced it.

## Objective

A future developer reading a Phase 3 comparison table should be able to
take any single metric value, find its `run_id`, open
`results/eval_runs/<run_id>.json`, and answer with certainty: which
code, which chunk semantics, which embedding revision, which index,
which retrieval settings, which reranker, which generation model, which
split, which eval-set version, and when.

## Task 2.10 / 2.11 boundary

```text
Task 2.10 answers: "Are these artifacts compatible?"
Task 2.11 answers: "What exactly produced this metric?"
```

Task 2.11 **consumes** Task 2.10's identities (`chunk_config_hash`,
embedding identity, index identity, `ArtifactCompatibility`); it never
recomputes them independently (`src/artifacts/versioning.py` is
untouched by this task).

## Relationship to `src.eval.eval_store` (Task 2.5)

Real repository inspection surfaced a genuine overlap worth stating
explicitly rather than silently ignoring: Task 2.5 already built an
`eval_runs` DuckDB table (`artifacts/eval/eval.duckdb`, columns include
`run_id`, `git_sha`, `split`, `eval_set_version`, `chunk_config_hash`,
`embed_model`, `rerank_model`, `generation_*`, ...) with a full
`start_run`/`record_metric`/`complete_run` lifecycle API
(`src/eval/eval_store.py`). This is a real, working run-logging system -
but it lives entirely inside a file `.gitignore`d since Task 2.4
(`artifacts/eval/eval.duckdb`), invisible to a bare `git clone` and gone
if that local file is ever deleted.

Task 2.11's records are the complementary artifact type: one small,
individually **immutable**, **git-tracked** JSON file per execution -
durable and citable indefinitely, readable years later even without the
local DuckDB. The two systems are not duplicative:

| | `eval_store.py` (Task 2.5) | `run_logging.py` (Task 2.11) |
|---|---|---|
| Storage | DuckDB, `artifacts/eval/eval.duckdb` | one JSON file per run |
| Git-tracked | No (gitignored) | Yes |
| Best for | iterative local querying across many runs | a durable, citable, individually-verifiable provenance record |
| Mutability | rows update as a run progresses (`start_run` -> `complete_run`) | one file, written once, never edited |

Task 2.11 does not modify `src/eval/eval_store.py` or
`src/eval/evaluation_schema.py`. A future Phase 3 runner may write to
both (record row-level detail in the DuckDB store during a run, then
write one Task 2.11 record summarizing the finished, successful run) -
that integration is left to whichever task builds the actual Phase 3
runner, not invented here.

## Run-record schema version

```text
EVALUATION_RUN_SCHEMA_VERSION = 2   (bumped from 1 by Task 2.12)
```

Distinct from `chunk_schema_version` (Task 2.9), `artifact_manifest_version`
(Task 2.10), `eval_set_version`/`split_version` (Task 2.3/2.4) - a
run-record layout change bumps this version alone.

**Task 2.12 update**: version 2 added `evaluation_source`/`benchmark_name`/
`benchmark_version`/`benchmark_source_hash` to represent an external
benchmark (e.g. FinanceBench) honestly, without forcing it through
`VALID_SPLITS` or lying about the protected internal `test` split. Full
detail in `project_plan/PHASE2_FINANCEBENCH_VALIDATION.md`'s "Run
logging - external-benchmark extension" section. Version 1 records
remain fully readable (`SUPPORTED_RUN_SCHEMA_VERSIONS = (1, 2)`); every
field/rule documented below for `evaluation_source="internal_phase2"`
(the only value that existed before Task 2.12) is unchanged.

## Mandatory Task 2.11 fields (PROJECT_EXECUTION.md, verbatim, 11/11)

```text
run_id, git_sha, chunk_config_hash, embedding_model, retrieval_config,
reranker_config, generation_model, split, eval_set_version, timestamp,
metrics
```

Every one of these keys is always present in a written record, even when
a value is genuinely not applicable - `"generation_model": null` for a
retrieval-only run, never a silently omitted key.

## Run ID semantics

`generate_run_id()` returns a fresh `uuid.uuid4()` string. `run_id`
identifies one **execution**, never a semantic configuration - running
the identical config twice produces two different `run_id`s and two
separate record files. Never Python's `hash()`, never derived from a
local machine path. Injectable in `build_run_record(run_id=...)` for
deterministic tests.

## Timestamp semantics

`current_utc_timestamp()` -> `"2026-09-02T15:42:13.123456Z"` - UTC,
timezone-aware, ISO 8601, always ending in `Z`. A naive timestamp, a
non-UTC offset, or a locale-formatted date is rejected by
`validate_timestamp()`. Injectable via `build_run_record(timestamp=...)`.

## Git provenance

`current_git_state()` resolves the real `git rev-parse HEAD` (validated:
40 lowercase hex characters - `HEAD`/`main`/`latest`/`unknown` are
rejected outright, never silently accepted) and `git status --porcelain`
for `git_dirty` (true if anything staged, unstaged, or untracked is
present). If Git provenance cannot be resolved at all, `current_git_state()`
raises `RunLogError` rather than pretending the run is reproducible.
Injectable via `build_run_record(git_state={"git_sha": ..., "git_dirty": ...})`
for deterministic tests. A dirty run is recorded honestly, never refused
automatically - Task 2.11 introduces no new policy forbidding dirty-tree
experiments.

## Chunk config identity

`chunk_config_hash` is validated (64 lowercase hex) but never
recomputed - callers pass the exact Task 2.10
`compute_chunk_config_hash()` value for the chunk artifact actually
used. `chunk_schema_version` (Task 2.9's `CHUNK_SCHEMA_VERSION`) is
recorded alongside it as recommended additional provenance (Section 10).

## Embedding model

Uses Task 2.10's own field names directly (`compute_embedding_identity()`'s
dict shape), not a competing schema: `model_repository`, `model_revision`,
`embedding_dimension`, `vector_dtype`, `normalize_embeddings`, plus
`identity_hash` (the identity dict itself does not carry the hash - it
is computed separately via `embedding_identity_hash()` and added by the
caller, exactly as `scripts/audit_artifact_compatibility.py` already
does). A repository name alone (`"BAAI/bge-small-en-v1.5"`) is
insufficient by itself - Task 2.10 already established this.

## Retrieval config

A plain structured mapping - only the fields that actually define the
run's retrieval behavior (`method`, `top_k`, `distance_metric`,
`index_type`, ...). Never claims BM25/hybrid/reranking configuration
that does not exist. An optional semantic fingerprint,
`compute_config_semantic_hash(retrieval_config)`, reuses Task 2.10's
`semantic_hash()` directly (never a second hashing implementation) -
useful for a later ablation table, never included in the hash:
`run_id`, `timestamp`, `git_sha`, `metrics`.

## Reranker config

Always present, even when no reranker exists:

```json
{"enabled": false}
```

or, once a reranker is implemented:

```json
{"enabled": true, "model": "...", "revision": "...", "input_candidates": 50, "output_k": 10}
```

`validate_reranker_config()` requires `model`/`revision` whenever
`enabled=true`. No reranker is implemented by this task.

## Generation model

`null` for a retrieval-only evaluation. A structured object
(`{"provider": "openrouter", "model": "openai/gpt-oss-20b"}`) when
generation is part of the run. No API key, Authorization header, or raw
provider request is ever recorded - enforced generically by the recursive
secret scan (below), not merely by convention.

## Split / eval-set identity

`split` must be one of Task 2.5's own already-frozen `VALID_SPLITS =
("dev", "test", "ci")` (`src.eval.evaluation_schema.VALID_SPLITS`,
reused directly, never redefined). `eval_set_version` and `split_version`
are reused, never recomputed, from Task 2.3/2.4's frozen result files:
current values `phase2-v1` / `phase2-split-v1`. `split_sha256` is the
appropriate frozen digest for the run's split (`dev_sha256` for a DEV
run, `ci_sha256` for a CI run, `test_sha256` for an official TEST run) -
already-tracked metadata from `results/phase_2_4_split_summary.json`;
reading it never opens the protected TEST question payload. The run
logger itself never loads any dataset - it receives split identity as
plain metadata from its caller.

## Metrics contract

`dict[str, int | float]`. Rejected: non-string/empty metric name, `bool`
(explicitly checked before the general `int` check, since `bool` is a
Python `int` subclass), `NaN`, `+-Infinity`. An unavailable metric (e.g.
Task 2.8's `chunk_recall@10`, currently `available_for_current_gold=False`)
is simply **absent** from the mapping - never fabricated as `0.0`. The
distinction between "metric = 0" and "metric cannot currently be
computed" is preserved by omission, not a sentinel value.

## Artifact compatibility

`build_run_record(..., artifact_compatibility=ArtifactCompatibility(...))`
is optional but strongly recommended for any real SEC evaluation run.
When supplied, it is checked against the record's own
`chunk_schema_version`/`chunk_config_hash`/`embedding_model.identity_hash`/
`index_identity_hash`/`eval_set_version` **before** the record is
constructed - a mismatch raises Task 2.10's own
`ArtifactCompatibilityError` (never a new wrapper, never a warning, never
a record written anyway).

## Run-record integrity

`run_record_sha256` = `semantic_hash()` (Task 2.10's canonical primitive)
over the complete record with `run_record_sha256` itself excluded.
Detects accidental mutation on load; `load_run_record()`/
`validate_run_record()` recompute and compare, raising
`RunRecordIntegrityError` on any mismatch. Not a chunk-config hash, a
retrieval-config hash, or an artifact identity - purely a tamper/
round-trip check on the record file itself.

## Persistence

```text
results/eval_runs/<run_id>.json
```

One immutable JSON file per run - never a single continuously-appended
array file. `write_run_record()` validates the complete record first,
then creates the target file with Python's exclusive-create mode
(`open(path, "x")`), which fails outright (`RunRecordExistsError`) if a
file with that `run_id` already exists - a duplicate `run_id` can never
silently overwrite a prior record; the original file is verified
byte-unchanged on a rejected duplicate attempt. Every write is UTF-8,
valid JSON, indented for human readability, with exactly one trailing
newline. Key order is the dataclass's declared field order - stable
across every write, though the file's actual byte content necessarily
differs run-to-run (`run_id`, `timestamp`, `metrics`, and possibly
`git_dirty` are run-specific by design).

**`.gitignore` fix**: `results/*` (Task 0.x's "keep small result files"
rule) blocks git from even inspecting a nested directory's own
un-ignore patterns - a known Git limitation where a parent-directory
match short-circuits child-pattern evaluation. `results/eval_runs/`
would have been silently swallowed by this rule despite the existing
`!results/*.json` exception (which only covers files directly inside
`results/`, not a subdirectory). Fixed with the minimum necessary
addition:

```gitignore
!results/eval_runs/
!results/eval_runs/*.json
```

Verified directly (`scripts/audit_evaluation_run_logging.py`'s
`audit_tracked_path_behavior()`, via `git add -n`, not
`git check-ignore`'s exit code - see the script's own docstring for why)
that `results/eval_runs/*.json` is now genuinely trackable. No other
`.gitignore` protection was weakened.

## Immutability

One run record represents one historical execution. Once written, it is
never edited in place and never overwritten by a later run - a repeated
experiment gets a new `run_id` and a new file, full stop.

## Secret safety

`_check_no_secrets()` recursively walks the entire record (dicts and
lists) and rejects, case-insensitively and separator-insensitively, any
key matching: `api_key`, `apikey`, `password`, `secret`, `authorization`,
`bearer`, `credential`, `token`. This is a hard failure
(`RunLogValidationError`) on the field's **path**, not a value - never a
silent redaction, and the credential's actual value never appears in the
raised exception message. Verified directly that legitimate field names
(`top_k`, `distance_metric`, `index_type`, `model_revision`) never
collide with any of these patterns.

## Historical-run policy

No Task 1.x/2.1-2.10 run record was fabricated. None of those tasks'
own results carry a complete Task 2.11-shaped provenance chain (a real
`run_id`, a real per-run `ArtifactCompatibility` binding, etc.) that
could be honestly reconstructed without inventing values. Per Section
41's default recommendation, no historical backfill was performed.
`record_origin` (default `"live"`) exists in the schema precisely so a
future, fully-provenanced historical import could set
`record_origin="historical_import"` and preserve the original run's real
Git SHA/timestamp - but no such import happens in this task.

## TEST policy

The run logger never loads any dataset - `split` is passed in as
metadata by the caller. Task 2.11 opened no TEST question payload;
`results/phase_2_4_split_summary.json`'s already-frozen `test_sha256`
was read (a digest, not a payload). Official TEST evaluations remain
**0/3** (verified directly against `artifacts/eval/eval.duckdb`'s
`test_access_log`).

## No fake first experiment

`results/eval_runs/` is intentionally left empty. Task 2.11 builds and
tests the logging contract exhaustively with synthetic data
(`tests/test_evaluation_run_logging.py`,
`scripts/audit_evaluation_run_logging.py`) but performs no real SEC
retrieval evaluation - there is no honest experiment to log yet without
starting Phase 3, which this task explicitly does not do. An empty
trusted ledger is better than a fabricated historical record.

## Example record (illustrative - fake values only)

```json
{
  "run_schema_version": 1,
  "run_id": "c0a8012f-85bd-4ea3-9037-3127a75f34a2",
  "git_sha": "0123456789abcdef0123456789abcdef01234567",
  "git_dirty": false,
  "chunk_schema_version": 1,
  "chunk_config_hash": "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd",
  "embedding_model": {
    "embedding_identity_version": 1,
    "model_repository": "BAAI/bge-small-en-v1.5",
    "model_revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    "embedding_dimension": 384,
    "vector_dtype": "float32",
    "normalize_embeddings": true,
    "passage_convention": "raw_text_no_instruction",
    "query_convention": "prepend:...",
    "identity_hash": "b39a67c9eb6487fc98f266f23742afd0a30321d98067505802a1e219b27bec84"
  },
  "index_identity_hash": "ace70ee67d8e98e019d221f2a0215a5b88498a0fc5dcbe73ac7ef1277630b111",
  "retrieval_config": {"method": "vector", "index_type": "exact_flat", "distance_metric": "cosine", "top_k": 10},
  "reranker_config": {"enabled": false},
  "generation_model": null,
  "split": "dev",
  "eval_set_version": "phase2-v1",
  "split_version": "phase2-split-v1",
  "split_sha256": "2818e6a07f8a465a648bd9e10c78642fec6e8d20f07ca379ef790a190c0c96ee",
  "timestamp": "2026-09-02T15:42:13.123456Z",
  "metrics": {"doc_recall@10": 0.97},
  "experiment_name": null,
  "run_kind": null,
  "notes": null,
  "record_origin": "live",
  "run_record_sha256": "<computed - not shown here as a real value>"
}
```

## Future Phase 3 workflow

```text
1. resolve configuration
2. assert artifact compatibility (src.artifacts.versioning)
3. run evaluation
4. calculate metrics (existing metric functions - unmodified)
5. construct EvaluationRunRecord (src.eval.run_logging.build_run_record)
6. validate (validate_run_record, or automatically inside write_run_record)
7. write immutable run record (write_run_record)
8. report run_id
```

Every real Phase 3 result must be attributable to exactly one `run_id`.

## Known limitations / scope decisions

- `eval_dataset_sha256` (Section 10's "potentially useful" list) was not
  added as a separate top-level field - `split_version` + `split_sha256`
  already pin the exact question set the split was built from (Task
  2.4's own split was itself built from one specific `dataset_sha256`,
  recorded in `phase_2_4_split_summary.json`); adding a second,
  redundant top-level hash for the same underlying fact would move
  toward "a giant telemetry system" (Section 10's own warning) without a
  concrete need.
- No existing Phase 1/2 evaluation entry point (`scripts/run_baseline_metric.py`,
  `src/cli/phase1.py`, the MS MARCO harness runner) was modified to call
  `build_run_record()`/`write_run_record()`. None of them evaluates
  against Task 2.3/2.4's `phase2-v1` eval set with a `dev`/`ci`/`test`
  split - `run_baseline_metric.py` is Phase 1's own frozen 200-question
  smoke metric (`split="smoke"`, no `eval_set_version`, no reranker/
  generation concept), and the MS MARCO harness is a separate benchmark
  track entirely (Section 24: MS MARCO is never a `source`/`split` value
  here). No single existing "safe integration point" exists for a real
  Task 2.3/2.4-shaped SEC evaluation run; per Section 40, the reusable
  API is exposed and documented instead of retrofitting a mismatched
  historical script or inventing a fake evaluation run.
