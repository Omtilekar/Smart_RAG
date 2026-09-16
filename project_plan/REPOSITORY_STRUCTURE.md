# Repository Structure

Established in Phase 0 Task 0.3. This document explains what each top-level
directory is for, which `src/` packages exist and why, and — critically for
anyone cloning this public repository — which paths are source-of-truth
tracked content versus generated/ignored local state.

A directory existing here does **not** mean the feature it's named for is
implemented. Most `src/` packages below contain only an empty `__init__.py`
at this point in the project. See `Progress.md` for what is actually
implemented versus planned.

## Tree

```text
SEC-RAG/
├── src/
│   ├── artifacts/       # IMPLEMENTED (Task 2.10) — versioning.py: canonical
│   │                     # config hashing, embedding/index identity, artifact
│   │                     # manifests, compatibility enforcement
│   ├── ingest/          # IMPLEMENTED — data acquisition + validation + audit
│   ├── normalize/       # IMPLEMENTED (Task 1.2) — EDGAR-CORPUS sections -> Markdown/frontmatter;
│   │                     # Task 4.1 added FULL_CORPUS_FRONTMATTER_KEYS + a
│   │                     # generalized render_frontmatter()/render_document()
│   │                     # (optional `keys`, None -> YAML null) and
│   │                     # is_all_sections_empty() - body rendering
│   │                     # (render_body/normalize_newlines/output_filename)
│   │                     # is byte-for-byte unchanged
│   ├── chunk/           # IMPLEMENTED (Task 1.3) — fixed-window tokenized chunks -> Parquet;
│   │                     # metadata_schema.py (Task 2.9) — canonical chunk record
│   │                     # schema (chunk_uid/chunk_local_id identity, field
│   │                     # types/nullability/enums), no new chunking pipeline;
│   │                     # Task 4.2 bumped CHUNK_SCHEMA_VERSION 1->2 (company
│   │                     # became nullable) and generalized fixed_window.py's
│   │                     # parse_normalized_document() with an optional
│   │                     # frontmatter_keys param + YAML null handling (every
│   │                     # existing call site unchanged - see
│   │                     # project_plan/PHASE4_FULL_CORPUS_CHUNKING.md)
│   ├── embeddings/      # IMPLEMENTED (Task 1.4) — BAAI/bge-small-en-v1.5 wrapper, batch GPU embedding;
│   │                     # model_registry.py (Task 3.3) — EmbeddingModelSpec/
│   │                     # generic load_model/encode_passages/encode_queries,
│   │                     # incl. the frozen QWEN3_EMBEDDING spec (Task 4.3's
│   │                     # production model)
│   ├── index/           # IMPLEMENTED (Task 1.5) — exact-cosine LanceDB vector index;
│   │                     # lancedb_index_full.py (Task 4.4) — companion module
│   │                     # for the full-corpus 24-column/10,487,096-row table
│   │                     # (own EXPECTED_COLUMNS/validate_chunk_table, plus
│   │                     # scalar BTree index build/validate for cik/
│   │                     # fiscal_year) - reuses lancedb_index's
│   │                     # exact_cosine_search()/exact_cosine_search_filtered()
│   │                     # unmodified; see
│   │                     # project_plan/PHASE4_FULL_CORPUS_VECTOR_INDEX.md
│   ├── retrieval/       # IMPLEMENTED (Task 1.6) — baseline natural-language vector retriever
│   ├── generation/      # IMPLEMENTED (Task 1.7) — minimal grounded generation, OpenRouter adapter
│   ├── eval/            # PARTIAL (Tasks 1.8-1.10, 2.1-2.2) — citation-integrity
│   │                     # smoke helper (Task 1.8), the deterministic Phase 1
│   │                     # smoke-dataset builder (Task 1.9), the doc_recall@10
│   │                     # baseline metric logic (Task 1.10), the XBRL
│   │                     # fact-eligibility truth contract (Task 2.1), and the
│   │                     # frozen 15-tag evaluation registry loader (Task 2.2);
│   │                     # question generation, DEV/TEST split, and evidence
│   │                     # alignment NOT yet implemented; run_logging.py
│   │                     # (Task 2.11) — immutable git-tracked per-run JSON
│   │                     # provenance records, consuming Task 2.10 identities;
│   │                     # financebench.py (Task 2.12) — isolated external-
│   │                     # benchmark validation logic (dataset audit, page-
│   │                     # bounded chunking, evidence alignment, retrieval
│   │                     # metrics), never touching the internal SEC schema;
│   │                     # llm_judge.py (Task 2.13) — local Ollama LLM-judge
│   │                     # client (binary faithfulness rubric, structured
│   │                     # output, judge_config_hash, agreement metrics),
│   │                     # zero paid API calls
│   ├── router/          # planned responsibility: query classification, path selection
│   ├── rerank/          # planned responsibility: cross-encoder reranking
│   ├── crag/            # planned responsibility: retrieval confidence / corrective decisions
│   ├── guards/          # planned responsibility: input/context/output protections
│   ├── api/             # planned responsibility: FastAPI-facing layer
│   └── cli/             # IMPLEMENTED (Task 1.11) — phase1.py, the Phase 1
│                         # local end-to-end CLI (answer / evaluate); no
│                         # FastAPI/production API implemented here
│
├── configs/             # implemented (partial): serving_spike.json (Task 0.10),
│                         # normalize_development_corpus.json (Task 1.2),
│                         # chunk_development_corpus.json (Task 1.3),
│                         # embed_development_corpus.json (Task 1.4),
│                         # build_vector_index.json (Task 1.5),
│                         # citation_integrity_smoke.json (Task 1.8),
│                         # phase_1_9_smoke_evaluation.json (Task 1.9),
│                         # phase_1_10_baseline_metric.json (Task 1.10),
│                         # eval_tags.yaml (Task 2.2),
│                         # phase_2_3_evaluation_dataset.json (Task 2.3),
│                         # phase_2_4_dev_test_split.json (Task 2.4),
│                         # phase_2_7_msmarco_harness.json (Task 2.7),
│                         # phase_2_8_primary_evidence.json (Task 2.8)
│                         # (no new config for Task 2.9 - it defines schema,
│                         # not a runnable pipeline; no new config for
│                         # Task 2.10 either - it hashes/validates existing
│                         # configs rather than introducing a new one),
│                         # phase_2_12_financebench_validation.json (Task 2.12),
│                         # phase_2_13_llm_judge.json (Task 2.13, frozen judge
│                         # identity/rubric/prompt/schema config),
│                         # phase_3_1_trusted_baseline.json (Task 3.1, frozen
│                         # Phase 3 DEV/evaluable-subset scope + every
│                         # referenced Phase 1 artifact identity),
│                         # phase_4_1_full_corpus_normalization.json (Task 4.1,
│                         # frozen full-corpus frontmatter/company-name-policy/
│                         # checkpoint contract + phase_4_1_config_hash),
│                         # phase_4_2_full_corpus_chunking.json (Task 4.2,
│                         # frozen full-corpus build identity - input Task 4.1
│                         # identities, chunk_schema_version, the reused
│                         # chunk_config_hash, tokenizer, shard policy,
│                         # Parquet compression - + phase_4_2_build_config_hash),
│                         # phase_4_4_full_corpus_vector_index.json (Task 4.4,
│                         # frozen full-corpus index identity - Task 4.1/4.2
│                         # identities, embedding/index identity hashes,
│                         # scalar-index/no-ANN/no-quantization/no-FTS policy),
│                         # phase_4_5_xbrl_serving_export.json (Task 4.5,
│                         # frozen XBRL serving-export identity - eval-tag-
│                         # registry hash, facts row-scope rule, partition
│                         # schemes for all 3 exported artifacts)
├── tests/               # implemented: Phase 0 foundation suite (Task 0.8),
│                         # see project_plan/TESTING.md
├── scripts/             # implemented: dev.py (Task 0.9), serving_spike.py (Task 0.10),
│                         # normalize_development_corpus.py (Task 1.2),
│                         # chunk_development_corpus.py (Task 1.3),
│                         # embed_development_corpus.py (Task 1.4),
│                         # build_vector_index.py (Task 1.5),
│                         # smoke_retrieval.py (Task 1.6),
│                         # smoke_generation.py (Task 1.7),
│                         # smoke_citation_integrity.py (Task 1.8),
│                         # build_smoke_evaluation.py (Task 1.9),
│                         # run_baseline_metric.py (Task 1.10, reused by
│                         # src/cli/phase1.py's evaluate subcommand),
│                         # build_truth_contract_summary.py (Task 2.1),
│                         # audit_eval_tag_registry.py (Task 2.2),
│                         # build_evaluation_dataset.py (Task 2.3),
│                         # build_dev_test_split.py (Task 2.4),
│                         # init_evaluation_schema.py (Task 2.5),
│                         # run_msmarco_harness.py (Task 2.7),
│                         # build_primary_evidence.py (Task 2.8),
│                         # audit_chunk_metadata_schema.py (Task 2.9, read-only
│                         # Phase 1 + Task 2.8 compatibility audit),
│                         # audit_artifact_compatibility.py (Task 2.10, read-only
│                         # chunk/embedding/index chain compatibility audit,
│                         # writes verified-historical manifest.json sidecars),
│                         # audit_evaluation_run_logging.py (Task 2.11, synthetic-
│                         # data run-record schema/security/persistence audit),
│                         # run_financebench_validation.py (Task 2.12, --download/
│                         # --dry-run/--pilot/--full FinanceBench validation runner),
│                         # prepare_llm_judge_calibration.py (Task 2.13, builds the
│                         # frozen 100-case calibration pack from Task 2.12's
│                         # evidence-aligned questions), label_llm_judge_calibration.py
│                         # (Task 2.13, blinded human labeling CLI, resumable),
│                         # run_llm_judge_validation.py (Task 2.13, --preflight/
│                         # --pilot/--full/--resume/--status/--watch judge runner
│                         # with per-case visible progress; --cross-model --full
│                         # runs the qwen3.5:9b vs gpt-oss:20b cross-model
│                         # agreement study that replaced human calibration -
│                         # see "Methodology change" in
│                         # project_plan/PHASE2_LLM_JUDGE_VALIDATION.md),
│                         # run_phase3_trusted_baseline.py (Task 3.1, `--run`
│                         # captures ablation row 0 - the unmodified Phase 1
│                         # architecture over the frozen 89-question DEV/
│                         # evaluable-subset; see project_plan/PHASE3_TRUSTED_BASELINE.md),
│                         # run_phase3_chunking_ablation.py (Task 3.2, `--plan`/
│                         # `--run --resume`/`--status`/`--compare` staged
│                         # window/overlap/fixed-vs-section-aware chunking
│                         # ablation against row 0; see
│                         # project_plan/PHASE3_CHUNKING_ABLATION.md),
│                         # run_phase3_embedding_benchmark.py (Task 3.3, `--plan`/
│                         # `--run --resume`/`--status`/`--compare` embedding-model
│                         # benchmark against the frozen 256/0/fixed chunk winner;
│                         # see project_plan/PHASE3_EMBEDDING_MODEL_BENCHMARK.md),
│                         # run_phase3_bm25_fts_baseline.py (Task 3.4, `--plan`/
│                         # `--build`/`--evaluate`/`--compare`/`--run`/`--status`
│                         # sparse-only LanceDB-native FTS baseline over the same
│                         # frozen chunks; see project_plan/PHASE3_BM25_FTS_BASELINE.md),
│                         # run_phase3_rrf_hybrid.py (Task 3.5, `--plan`/`--run`/
│                         # `--compare`/`--status` RRF fusion of the frozen dense
│                         # + sparse retrievers; see
│                         # project_plan/PHASE3_RRF_HYBRID_FUSION.md),
│                         # run_phase3_reranker.py (Task 3.6, `--plan`/`--run`/
│                         # `--compare`/`--status` cross-encoder reranking of the
│                         # dense-only candidate pool; see
│                         # project_plan/PHASE3_CROSS_ENCODER_RERANKING.md),
│                         # run_phase3_crag.py (Task 3.7, `--plan`/`--run`/
│                         # `--status` retrieval-confidence refusal-gate
│                         # calibration; see
│                         # project_plan/PHASE3_CRAG_CONFIDENCE_GRADING.md),
│                         # run_phase3_router.py (Task 3.8, `--plan`/`--run`/
│                         # `--status` rules-first intent classification over
│                         # the full DEV corpus; see
│                         # project_plan/PHASE3_RULES_FIRST_ROUTER.md),
│                         # run_phase3_filter.py (Task 3.9, `--plan`/`--run`/
│                         # `--compare`/`--status` CIK+fiscal_year metadata
│                         # pre-filtering; see
│                         # project_plan/PHASE3_METADATA_PREFILTERING.md),
│                         # run_phase3_sql.py (Task 3.10, `--plan`/`--run`/
│                         # `--status` structured XBRL fact lookup for
│                         # xbrl_fact-routed questions; see
│                         # project_plan/PHASE3_XBRL_SQL_PATH.md),
│                         # run_phase3_derived.py (Task 3.11, `--plan`/`--run`/
│                         # `--status` deterministic difference/greater_than
│                         # derived calculations over Task 3.10's fact index;
│                         # see project_plan/PHASE3_DERIVED_CALCULATIONS.md),
│                         # run_phase3_nav.py (Task 3.12, `--plan`/`--run`/
│                         # `--status` filing/section navigation over Task
│                         # 2.8's parsed structural corpus; see
│                         # project_plan/PHASE3_TREE_SECTION_NAVIGATION.md)
│                         # - see project_plan/DEVELOPER_COMMANDS.md, project_plan/SERVING_FEASIBILITY.md;
│                         # normalize_full_corpus.py (Task 4.1, `--plan`/
│                         # `--pilot`/`--run [--limit N]`/`--status`/
│                         # `--verify-sample` resumable full-EDGAR-CORPUS
│                         # normalization driver; see
│                         # project_plan/PHASE4_FULL_CORPUS_NORMALIZATION.md);
│                         # chunk_full_corpus.py (Task 4.2, `--plan`/`--pilot`/
│                         # `--run [--limit N]`/`--status`/`--verify-sample`
│                         # resumable full-corpus sharded-Parquet chunking
│                         # driver, reusing src/chunk/fixed_window.py's
│                         # tokenizer/window/offset logic and
│                         # src/chunk/metadata_schema.py's canonical schema
│                         # unmodified; see
│                         # project_plan/PHASE4_FULL_CORPUS_CHUNKING.md);
│                         # build_vector_index_full.py (Task 4.4, shard-level-
│                         # resumable full-corpus LanceDB build over Task 4.3's
│                         # frozen 54-shard embedding artifact - manifest/hash
│                         # re-verification, exact-cosine ingestion, scalar
│                         # cik/fiscal_year index build, self-retrieval/
│                         # search-latency validation; see
│                         # project_plan/PHASE4_FULL_CORPUS_VECTOR_INDEX.md);
│                         # export_xbrl_serving.py (Task 4.5, partitioned-
│                         # Parquet re-export of the 15-enabled-tag subset of
│                         # data/xbrl.duckdb's facts table - by tag and by
│                         # (cik, fiscal_year) - plus submissions by cik;
│                         # CIK-batched/checkpointed for the high-cardinality
│                         # layout, full-corpus fingerprint validation,
│                         # partition-pruning correctness + latency
│                         # benchmarking; see
│                         # project_plan/PHASE4_XBRL_SERVING_REPRESENTATION.md)
├── results/             # planned: small committed metrics/experiment summaries;
│                         # results/eval_runs/<run_id>.json — one immutable
│                         # git-tracked evaluation-run record per execution
│                         # (Task 2.11), intentionally empty until a real
│                         # experiment exists (Task 2.12 writes the first
│                         # real record here, for the FinanceBench full run)
├── infra/               # planned: deployment/infrastructure definitions
│
├── prompts/             # IMPLEMENTED — task prompts that drove this project, kept for
│                         # educational/reproducibility value (data_download.md,
│                         # data_validation*.md, phase_0_Foundation/task_*.md, ...)
├── project_plan/        # IMPLEMENTED — design/planning documents (this file's home)
├── data/                # frozen datasets — see "Tracked vs generated" below
├── artifacts/           # runtime-generated, git-ignored, not created by default
├── logs/                # runtime-generated, git-ignored, not created by default
│
├── DATA_READINESS_REPORT.md   # IMPLEMENTED — frozen Phase 1 data statistics
├── Progress.md                 # IMPLEMENTED — dated engineering log
├── phase1_data_audit.log       # IMPLEMENTED — audit run log
├── stage{1..5}_*.log           # IMPLEMENTED — per-stage acquisition logs
├── .python-version              # IMPLEMENTED — "3.11"
└── .gitignore                   # IMPLEMENTED
```

`.venv/` (project-local Python environment, Task 0.1) and `.tmp/` (orphaned
disk state, flagged for cleanup) also exist locally but are git-ignored and
intentionally omitted from the tree above.

## `src/` package responsibilities

| Package | Status | Will eventually contain |
|---|---|---|
| `artifacts/` | **implemented** | `versioning.py` — canonical config-hashing/semantic-hash primitive, embedding/index identity, chunk/embedding/index artifact manifests, `ArtifactCompatibility`/`assert_artifact_compatible` loud-mismatch enforcement (Task 2.10), see `project_plan/PHASE2_ARTIFACT_VERSIONING.md` |
| `ingest/` | **implemented** | MS MARCO / EDGAR-CORPUS / XBRL / primary-doc fetchers, `validate.py`, `audit_data.py` |
| `normalize/` | **implemented** | `edgar_markdown.py` — minimal EDGAR-CORPUS -> Markdown/YAML-frontmatter renderer (Task 1.2), see `project_plan/PHASE1_NORMALIZATION.md` |
| `chunk/` | **implemented** | `fixed_window.py` — minimal 512-token fixed-window chunker (Task 1.3), see `project_plan/PHASE1_CHUNKING.md`; `metadata_schema.py` — the canonical 23-field chunk record schema, `chunk_uid`/`chunk_local_id` identity algorithms, offset/section/date/accession semantics (Task 2.9), see `project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md`; later section-aware chunking pipeline (Phase 3.2) |
| `embeddings/` | **implemented** | `bge.py` — BAAI/bge-small-en-v1.5 wrapper, batch GPU embedding (Task 1.4), see `project_plan/PHASE1_EMBEDDINGS.md`; `embedding_identity()` — structured semantic identity (repository/revision/dimension/dtype/normalization/convention), Task 2.10 |
| `index/` | **implemented** | `lancedb_index.py` — exact-cosine LanceDB vector table (Task 1.5), see `project_plan/PHASE1_VECTOR_INDEX.md`; `index_identity()` — semantic identity binding chunk+embedding+distance-metric+index-type, Task 2.10, see `project_plan/PHASE2_ARTIFACT_VERSIONING.md`; `lancedb_fts.py` — LanceDB-native FTS/BM25 sparse index build/search primitives plus a sparse-only artifact identity that deliberately does not reuse `compute_index_identity()` (Task 3.4), see `project_plan/PHASE3_BM25_FTS_BASELINE.md`; `lancedb_index.py` also gained `exact_cosine_search_filtered()` (Task 3.9, additive - a scalar SQL pre-filter applied before the exact search, verified as LanceDB 0.37.1's true `prefilter=True` default), see `project_plan/PHASE3_METADATA_PREFILTERING.md`; `lancedb_index_full.py` — companion module for Task 4.4's full-corpus 24-column/10,487,096-row table (own `EXPECTED_COLUMNS`/`validate_chunk_table()`, plus scalar BTree index build/validate for `cik`/`fiscal_year` - reuses `lancedb_index`'s `exact_cosine_search()`/`exact_cosine_search_filtered()` unmodified), see `project_plan/PHASE4_FULL_CORPUS_VECTOR_INDEX.md`; later graph tables (Phase 5.4) |
| `retrieval/` | **implemented** | `baseline.py` — vector-only baseline retriever (Task 1.6), see `project_plan/PHASE1_RETRIEVER.md`; `sparse.py` — `SparseRetriever`, the sparse-only LanceDB FTS application boundary preserving the native `_score` faithfully as `sparse_score` (Task 3.4); `fusion.py` — pure Reciprocal Rank Fusion (`rrf_fuse()`, chunk-level, ranks only, never mixes raw dense/sparse scores) and `hybrid.py` — `HybridRetriever`, composing the dense + sparse retrievers (Task 3.5), see `project_plan/PHASE3_RRF_HYBRID_FUSION.md`; `reranked.py` — `RerankedRetriever`, composing a base retriever with Task 3.6's cross-encoder (reorders a fixed candidate pool only, never changes it), see `project_plan/PHASE3_CROSS_ENCODER_RERANKING.md`; `filtered.py` — `MetadataFilteredRetriever` + `build_predicate()` (CIK+fiscal_year scalar pre-filter built from validated ints only, immune to injection by construction) (Task 3.9), see `project_plan/PHASE3_METADATA_PREFILTERING.md` |
| `generation/` | **implemented** | `provider.py` (provider-neutral interface), `openrouter.py` (adapter), `minimal.py`, `citations.py` (Task 1.7), see `project_plan/PHASE1_GENERATION.md` |
| `eval/` | **partial** | `citation_integrity.py` — mechanical citation-integrity smoke check (Task 1.8), see `project_plan/PHASE1_CITATION_INTEGRITY.md`; `smoke_dataset.py` — deterministic 200-question document-level smoke dataset builder (Task 1.9), see `project_plan/PHASE1_SMOKE_EVALUATION.md`; `baseline_metrics.py` — pure doc_recall@10 metric logic (Task 1.10), see `project_plan/PHASE1_BASELINE_METRICS.md`; `truth_contract.py` — XBRL fact-eligibility contract (Task 2.1, refactored in Task 2.2 to consume the registry), see `project_plan/PHASE2_TRUTH_CONTRACT.md`; `tag_registry.py` — loader/validator for the frozen 15-tag `configs/eval_tags.yaml` (Task 2.2), see `project_plan/PHASE2_TAG_REGISTRY.md`; `evaluation_dataset.py` — record construction/hashing/duplicate+leakage checks for the 2,810-question Phase 2 evaluation dataset (Task 2.3), see `project_plan/PHASE2_EVALUATION_DATASET.md`; `dev_test_split.py` — company-disjoint DEV/TEST connected-component splitter (Task 2.4), see `project_plan/PHASE2_DEV_TEST_SPLIT.md`; `test_access.py` — controlled TEST-set loader with hash verification and a 3-run access budget (Task 2.4); `evaluation_schema.py` — the eval_runs/eval_question_results/eval_retrieved_items/eval_metrics/eval_stage_timings DuckDB schema, metric-definition registry, and schema-hash logic (Task 2.5); `eval_store.py` — the run-lifecycle storage API (start_run/record_*/complete_run/fail_run) all future experiments must use (Task 2.5; Task 2.6 added metric_definitions resync-on-reinit), see `project_plan/PHASE2_EVALUATION_SCHEMA.md`; `metrics.py` — hand-verified deterministic metric functions (recall/hit-at-k, MRR, binary nDCG@k, numeric_exact_match, correct_refusal, rate aggregation) reusing Task 1.10's frozen `doc_recall@10` hit semantics rather than reimplementing them (Task 2.6), see `project_plan/PHASE2_METRIC_TESTS.md`; `msmarco_harness.py` — MS MARCO benchmark-specific ID normalization/qrel grouping/multi-qrel recall+MRR+nDCG aggregation, reusing Task 2.6's metric primitives (Task 2.7), see `project_plan/PHASE2_MSMARCO_HARNESS.md`; primary-document evidence alignment implemented in the new `parse/` package (Task 2.8), see below; `run_logging.py` — the immutable, git-tracked `EvaluationRunRecord` schema/validation/persistence API (`build_run_record`/`validate_run_record`/`write_run_record`/`load_run_record`), binding a metric to Task 2.10's chunk/embedding/index identities plus Task 2.3/2.4's eval-set/split identity (Task 2.11, extended with `evaluation_source`/`benchmark_*` fields in Task 2.12), see `project_plan/PHASE2_EVALUATION_RUN_LOGGING.md`; `financebench.py` — isolated FinanceBench dataset validation, zero-indexed page/evidence alignment, page-bounded benchmark chunking, and adapted retrieval-metric math (Task 2.12), see `project_plan/PHASE2_FINANCEBENCH_VALIDATION.md`; `llm_judge.py` — local Ollama `OllamaJudge` client, binary faithfulness rubric/prompt, structured-output validation, retry policy, `judge_config_hash` (Task 2.10 canonical hashing), `agreement_rate`/`cohens_kappa` (human-vs-judge), and `cross_model_agreement`/`disagreement_direction` (neutral two-judge agreement, added for the Task 2.13 cross-model study that replaced human calibration) utilities, see `project_plan/PHASE2_LLM_JUDGE_VALIDATION.md`; `phase3_baseline.py` — pure DEV-scope/coverage-audit logic for Phase 3's trusted baseline: applicability classification, gold target-document derivation (single- and multi-document shapes), coverage auditing against the live Phase 1 index, the frozen Option A `phase3_dev_scope` selection/hashing, baseline-config building/hashing, artifact-identity verification, and ablation-table row-freeze/duplicate-protection (`upsert_row`, `ABLATION_TABLE_COLUMNS` now additively extended with Task 3.4's sparse columns) — never touches `test_access`/TEST (Task 3.1), see `project_plan/PHASE3_TRUSTED_BASELINE.md`; `phase3_ablation.py` — chunking-candidate registry and the frozen paired-bootstrap/practical-tie/winner-selection rule reused unmodified by every later Phase 3 ablation task (Task 3.2); `phase3_sparse.py` — sparse-config-hash wrapper, dense/sparse hit complementarity, first-hit-rank comparison, and the sparse ablation-table row, reusing `phase3_baseline`/`phase3_ablation`'s scope guards and paired bootstrap unmodified (Task 3.4); `phase3_hybrid.py` — hybrid-config-hash wrapper, hybrid-vs-dense/sparse gain/loss classification, first-gold-hit-rank movement, fusion-source composition, and the frozen Stage 9 selection rule (`select_hybrid_configuration`, with its own correctly-scoped `is_practical_tie_hybrid()` rather than reusing the Recall@50-keyed rule from `phase3_ablation`) (Task 3.5); `phase3_rerank.py` — rerank-config-hash wrapper, candidate-set-recall integrity assertion (reranking can only reorder a fixed pool), and the frozen selection rule (`select_rerank_configuration`, with its own Recall@5-keyed `is_practical_tie_rerank()`) (Task 3.6), see `project_plan/PHASE3_CROSS_ENCODER_RERANKING.md`; `phase3_crag.py` — CRAG-config-hash wrapper and rate aggregation (`crag_rates`, reusing Task 2.6's `aggregate_rate` unmodified) over the frozen should_answer (89-question)/should_refuse (113 not-applicable-shape) population (Task 3.7), see `project_plan/PHASE3_CRAG_CONFIDENCE_GRADING.md`; `phase3_router.py` — `build_confusion_matrix()`, `per_class_metrics()`, `overall_accuracy()`, `macro_f1()` (a new multi-class-classification metric family) and the router ablation row (Task 3.8), see `project_plan/PHASE3_RULES_FIRST_ROUTER.md`; `phase3_filter.py` — filter-config-hash wrapper and the filtering ablation row, reusing `phase3_ablation.select_round_winner`/`is_practical_tie`/`paired_bootstrap_delta_ci` completely unmodified (Task 3.9), see `project_plan/PHASE3_METADATA_PREFILTERING.md`; `phase3_sql.py` — SQL-path-config-hash wrapper and rate aggregation (`sql_rates`, reusing Task 2.6's `aggregate_rate` unmodified) over the xbrl_fact target/trap populations (Task 3.10), see `project_plan/PHASE3_XBRL_SQL_PATH.md`; `phase3_derived.py` — derived-calculation-config-hash wrapper, rate aggregation (`derived_rates`, reusing Task 2.6's `aggregate_rate` unmodified) over the difference/greater_than populations, and the derived-calculations ablation row (Task 3.11), see `project_plan/PHASE3_DERIVED_CALCULATIONS.md`; `phase3_nav.py` — navigation-config-hash wrapper, rate aggregation (`nav_rates`, reusing Task 2.6's `aggregate_rate` unmodified) over the filing-resolution/section-navigation populations, and the navigation ablation row (Task 3.12), see `project_plan/PHASE3_TREE_SECTION_NAVIGATION.md` |
| `parse/` | **implemented** | `source_identity.py` — deterministic `primary:{cik}:{accession}` identity for the 990 primary 10-K filings; `primary_html.py` — Docling-based structural parsing (sections/tables), source locators honestly scoped to Docling's own `self_ref`; `inline_xbrl.py` — raw namespace-aware inline-XBRL DOM extraction (contexts/units/divide-units/continuations/numeric normalization), independent of Docling; `evidence_alignment.py` — fact-to-node alignment reusing Task 2.1's truth contract and Task 2.2's tag registry unmodified (Task 2.8), see `project_plan/PHASE2_PRIMARY_EVIDENCE.md` |
| `router/` | **implemented** | `rules.py` — `CompanyGazetteer`, `extract_fiscal_years()`, `extract_form_type()`, `resolve_xbrl_concept()`, and `classify_intent()` (deterministic keyword/regex/gazetteer cascade over 6 intents - the roadmap's other 4 have zero DEV examples) (Task 3.8), see `project_plan/PHASE3_RULES_FIRST_ROUTER.md` |
| `rerank/` | **implemented** | `cross_encoder.py` — `RerankerModelSpec` + generic `load_model()`/`score_pairs()`/`validate_scores()`, mirroring `src.embeddings.model_registry`'s spec/adapter pattern (Task 3.6), see `project_plan/PHASE3_CROSS_ENCODER_RERANKING.md` |
| `crag/` | **implemented** | `confidence.py` — `compute_confidence_features()`, `should_refuse()`, `classify_outcome()`, and `calibrate_threshold_youden_j()` (deterministic non-parametric threshold sweep) (Task 3.7), see `project_plan/PHASE3_CRAG_CONFIDENCE_GRADING.md` |
| `sql/` | **implemented** | `xbrl_lookup.py` — `XbrlFactIndex`, a `(tag,cik,fiscal_year) -> facts` index built from Task 2.1/2.2's frozen `eligible_facts()` (one query per tag, never per question); `.lookup()` returns `found`/`not_found`/`ambiguous`/`unsupported_tag` (Task 3.10), see `project_plan/PHASE3_XBRL_SQL_PATH.md`; `derived.py` — `compute_difference()`/`compute_greater_than()`, deterministic arithmetic over pairs of `XbrlLookupResult` operands (Task 3.11), see `project_plan/PHASE3_DERIVED_CALCULATIONS.md` |
| `nav/` | **implemented** | `section_navigation.py` — `extract_item_reference()` (text-only canonical-Item extraction, reuses Task 2.8's `_CANONICAL_ITEMS`), `resolve_filing_document_id()` (found/filing_not_found/ambiguous_filing via the frozen `submissions` table), `navigate_to_section()` (loads exactly one Task 2.8 parsed document, filters to the requested `section_id`) (Task 3.12), see `project_plan/PHASE3_TREE_SECTION_NAVIGATION.md` |
| `guards/` | structure only | Input/context/output guardrails (Phase 4.7–4.9) |
| `api/` | structure only | FastAPI service (Phase 4.10) |
| `cli/` | **implemented** | `phase1.py` — one-command demo (`answer`) and smoke-eval entry point (`evaluate`) (Task 1.11), see `project_plan/PHASE1_END_TO_END.md`; no FastAPI/production API |

`src/config.py` (Task 0.5 — implemented, see `project_plan/CONFIGURATION.md`),
`src/logging_utils.py` (Task 0.6 — implemented, see
`project_plan/LOGGING.md`), and `src/storage.py` (Task 0.7 — implemented,
see `project_plan/STORAGE.md`) were deliberately not stubbed out in
Task 0.3, so an empty
file never got mistaken for a completed feature ahead of time.

## Top-level directories

- **`configs/`** — versioned experiment/system configuration (e.g. chunk
  configs, `configs/eval_tags.yaml`). Contains `serving_spike.json` (Task
  0.10, see `project_plan/SERVING_FEASIBILITY.md`) as of this task; still
  otherwise empty pending Phase 1+.
- **`tests/`** — Phase 0 foundation suite implemented in Task 0.8 (66
  portable tests as of Task 0.10: config/logging/storage/dependency/
  ingest-import/LanceDB/serving-spike-helper portable tests, plus
  `local_data`/`gpu`/`model`-marked local capability smoke tests). See
  `project_plan/TESTING.md`. The injection-resistance test and other
  Phase 2+ tests don't exist yet — added when those features do.
- **`scripts/`** — `dev.py`, the developer command interface implemented
  in Task 0.9 (`doctor`/`test`/`test --portable`/`data`/`gpu`/`smoke`). See
  `project_plan/DEVELOPER_COMMANDS.md`. Also `serving_spike.py` (Task
  0.10), throwaway feasibility-benchmark code — not a `dev.py` subcommand,
  invoked directly. See `project_plan/SERVING_FEASIBILITY.md`.
- **`results/`** — small, human-readable experiment outputs meant to be
  public (`.csv`/`.json`/`.md`). The directory itself is tracked
  (`results/.gitkeep`); its contents are ignored by default except those
  three extensions — see `.gitignore`.
- **`infra/`** — deployment/infrastructure definitions (Phase 4.11). Empty
  as of Task 0.3.
- **`artifacts/`, `logs/`** — runtime-generated locations for build
  artifacts and (future) log files. Task 0.6 established the application
  logging convention (`src/logging_utils.py`) as console/stderr-only —
  `logs/` stays unused until a file or cloud sink is actually justified.
  `artifacts/` layout and creation policy (`normalized/`, `chunks/`,
  `indexes/`, `eval/`) are owned by `src/storage.py` (Task 0.7), see
  `project_plan/STORAGE.md`. Both are git-ignored and are *not* created as empty
  directories by default — they appear only when something actually writes
  to them.

## Tracked vs generated/ignored

### Tracked (source of truth)

```text
src/                    (including the empty __init__.py placeholders above)
infra/                  (currently just .gitkeep)
configs/                (serving_spike.json, Task 0.10; otherwise just .gitkeep)
scripts/                (implemented — dev.py Task 0.9, serving_spike.py Task 0.10)
tests/                  (implemented — conftest.py + 10 test_*.py, Tasks 0.8/0.10)
results/*.csv, results/*.json, results/*.md   (results/.gitkeep tracked too)
project_plan/
prompts/
Progress.md
DATA_READINESS_REPORT.md
phase1_data_audit.log, stage{1..5}_*.log
.python-version
.gitignore
pytest.ini              (Task 0.8)
requirements.txt, requirements-gpu.txt, requirements-dev.txt   (Task 0.4)
.env.example             (Task 0.5)
```

### Local/generated and git-ignored

```text
data/*                  (everything except data/.gitkeep — see DATA_READINESS_REPORT.md)
.venv/                  (Task 0.1 — project-local Python environment)
.tmp/                   (orphaned DuckDB spill — flagged for cleanup, not deleted yet)
artifacts/, logs/       (not created by default; ignored when they do appear)
*.duckdb, *.duckdb.wal, *.parquet, *.zip, *.idx, *.part, *.lance/
models/, .cache/, **/.huggingface/, *.onnx, *.safetensors, *.bin
.env* (except .env.example), *.pem, *.key, credentials*, secrets*
__pycache__/, *.py[cod], .pytest_cache/, .ipynb_checkpoints/
.claude/                (local coding-assistant tooling state)
results/* other than the tracked exceptions above
```

Full detail: `.gitignore` at the repository root.
