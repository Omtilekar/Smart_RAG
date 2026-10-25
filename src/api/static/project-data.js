// Task 4.12 - curated, source-cited showcase facts.
//
// Every entry traces to a committed repository artifact via source_path
// (and source_key where practical). Nothing here is estimated. Numbers
// that could not be verified against a repository artifact were omitted
// rather than guessed - see the Task 4.12 report for the omission list.
//
// Live runtime values (service readiness, generation provider/model,
// dense index row count) are fetched from /status at page load instead
// of being duplicated here - see app.js's refreshLiveStatus().

export const PROJECT_DATA = {
  meta: {
    github_url: "https://github.com/Omtilekar/Smart_RAG",
  },

  datasets: [
    {
      label: "MS MARCO passage corpus",
      value: "8,841,823",
      unit: "passages",
      context: "Retrieval benchmark used to validate the embedding pipeline before touching the SEC corpus.",
      source_path: "results/phase_2_7_msmarco_harness.json",
      source_key: "corpus_count",
      status_type: "frozen",
    },
    {
      label: "MS MARCO dev-small queries",
      value: "6,980",
      unit: "queries / 7,437 qrels",
      context: "Standard dev-small benchmark split, measured nDCG@10 = 0.4082 (consistent with BGE-small's published BEIR reference of 0.408).",
      source_path: "results/phase_2_7_msmarco_harness.json",
      source_key: "measured_metrics.passage_ndcg@10",
      status_type: "frozen",
    },
    {
      label: "EDGAR-CORPUS full-corpus filings",
      value: "91,086",
      unit: "source filings",
      context: "90,239 normalized documents across 25,937 unique CIKs (Task 4.1).",
      source_path: "results/phase_4_1_full_corpus_normalization.json",
      source_key: "source_row_count",
      status_type: "frozen",
    },
    {
      label: "Development corpus (Phase 1-3)",
      value: "1,500",
      unit: "filings / 1,376 CIKs",
      context: "The frozen 2016-2020 development sample every Phase 1-3 experiment and ablation ran against.",
      source_path: "results/phase_1_1_development_corpus.json",
      source_key: "selected_corpus_distribution.count",
      status_type: "frozen",
    },
    {
      label: "XBRL numeric facts",
      value: "90,685,753",
      unit: "facts",
      context: "Filtered 10-K/10-Q numeric facts across 218,166 submissions and 10,757 CIKs.",
      source_path: "DATA_READINESS_REPORT.md",
      source_key: "Derived tables in xbrl.duckdb",
      status_type: "frozen",
    },
    {
      label: "XBRL serving export (15-tag subset)",
      value: "15,852,990",
      unit: "rows",
      context: "Partitioned Parquet re-export of the 15 evaluable tags for production serving (Task 4.5).",
      source_path: "results/phase_4_5_xbrl_serving_export_summary.json",
      source_key: "source_facts_row_count",
      status_type: "frozen",
    },
    {
      label: "Primary filings (Docling-parsed)",
      value: "990",
      unit: "filings",
      context: "136,592 tables and 2,603,110 inline-XBRL facts extracted for fact-to-evidence alignment (Task 2.8).",
      source_path: "results/phase_2_8_primary_evidence_summary.json",
      source_key: "source_document_count",
      status_type: "frozen",
    },
    {
      label: "Full-corpus chunks",
      value: "10,487,096",
      unit: "chunks / 54 shards",
      context: "The complete production chunk set (Task 4.2), built from the Phase 3-winning 256-token fixed-window config.",
      source_path: "results/phase_4_2_full_corpus_chunking.json",
      source_key: "build.total_chunk_count",
      status_type: "frozen",
    },
    {
      label: "Full-corpus embeddings",
      value: "10,487,096",
      unit: "vectors × 1024-dim",
      context: "Qwen/Qwen3-Embedding-0.6B, float32, cosine distance - the Phase 3-winning embedding model.",
      source_path: "results/phase_4_4_full_corpus_vector_index_summary.json",
      source_key: "vector_count / vector_dimension",
      status_type: "frozen",
    },
  ],

  buildStages: [
    {
      label: "1. Normalize",
      value: "90,239",
      unit: "documents",
      context: "91,086 source filings → normalized Markdown/YAML frontmatter (847 valid-empty sources, not failures).",
      source_path: "results/phase_4_1_full_corpus_normalization.json",
      source_key: "normalized_document_count",
      status_type: "frozen",
    },
    {
      label: "2. Chunk",
      value: "10,487,096",
      unit: "chunks",
      context: "54 shards, Phase 3-winning fixed-window config (256 tokens, 0 overlap, stride 256).",
      source_path: "results/phase_4_2_full_corpus_chunking.json",
      source_key: "build.total_chunk_count",
      status_type: "frozen",
    },
    {
      label: "3. Embed",
      value: "10,487,096",
      unit: "vectors, 1024-dim",
      context: "Qwen/Qwen3-Embedding-0.6B @ pinned revision, manifest sha256 a4d1421b...",
      source_path: "results/phase_4_4_full_corpus_vector_index_summary.json",
      source_key: "task_4_3_manifest_sha256",
      status_type: "frozen",
    },
    {
      label: "4. Index",
      value: "51.1",
      unit: "GB, exact cosine",
      context: "LanceDB flat/exact index, scalar indexes on cik and fiscal_year.",
      source_path: "results/phase_4_4_full_corpus_vector_index_summary.json",
      source_key: "database_size_bytes",
      status_type: "frozen",
    },
    {
      label: "5. Serve (XBRL)",
      value: "15,852,990",
      unit: "rows exported",
      context: "Partitioned Parquet re-export of facts + 218,166 submissions for production query patterns.",
      source_path: "results/phase_4_5_xbrl_serving_export_summary.json",
      source_key: "source_facts_row_count",
      status_type: "frozen",
    },
  ],

  integrationGap: {
    liveRuntime: [
      {
        label: "Live dense index rows",
        value: "10,487,096",
        unit: "chunks",
        context: "The frozen full-corpus production LanceDB index, verified live through /status (Task 4.A).",
        source_path: "results/phase_4a_production_dense_smoke.json",
        source_key: "row_count",
        status_type: "live-runtime",
      },
      {
        label: "Live chunking config",
        value: "256-token window",
        unit: "stride 256, overlap 0",
        context: "The Phase 3-selected chunking config (fixed/256/0) the production index was built from.",
        source_path: "results/phase_4_2_full_corpus_chunking.json",
        source_key: "chunk_config_hash",
        status_type: "live-runtime",
      },
      {
        label: "Live embedding model",
        value: "Qwen/Qwen3-Embedding-0.6B",
        unit: "1024-dim, normalized",
        context: "The model Phase 3's benchmark selected, now the live query encoder. The Phase 1 BGE dev index is an explicit DENSE_RETRIEVER_MODE=dev opt-in only.",
        source_path: "src/retrieval/production.py",
        source_key: "ProductionDenseRetriever",
        status_type: "live-runtime",
      },
      {
        label: "Retrieval cache",
        value: "LIVE",
        unit: "exact-query LRU + TTL",
        context: "In-process memory cache around dense retrieval evidence only. It is not a semantic cache, not shared across workers, and is keyed to the production index identity, so it can never serve dev-index results.",
        source_path: "src/retrieval/cache.py",
        source_key: "ExactRetrievalCache",
        status_type: "live-runtime",
      },
    ],
    productionArtifact: [
      {
        label: "Production chunk count",
        value: "10,487,096",
        unit: "chunks",
        context: "Built from the actual Phase 3-winning 256-token config.",
        source_path: "results/phase_4_2_full_corpus_chunking.json",
        source_key: "build.total_chunk_count",
        status_type: "current-build",
      },
      {
        label: "Production embedding model",
        value: "Qwen/Qwen3-Embedding-0.6B",
        unit: "1024-dim",
        context: "The Phase 3-selected model — already embedded and indexed, just not reachable from the live dense route yet.",
        source_path: "results/phase_4_4_full_corpus_vector_index_summary.json",
        source_key: "embedding_model",
        status_type: "current-build",
      },
      {
        label: "Schema compatibility",
        value: "Incompatible",
        context: "chunk_uid replaces chunk_id, and several dev-only provenance fields were dropped — the current retriever can't read the production table as-is.",
        source_path: "src/api/dependencies.py",
        source_key: "module docstring",
        status_type: "current-build",
      },
    ],
  },

  experiments: [
    {
      title: "1. Chunking ablation",
      status_type: "frozen",
      outcome: "selected",
      summary: "Eight fixed-window and overlap variants were compared by document-level recall/MRR/nDCG over the frozen development set, across three practical-tie rounds (A, B, C).",
      candidates: [
        { label: "A0 — 512 tokens (baseline)", value: 0.9551 },
        { label: "A2 — 1024 tokens", value: 0.9326 },
        { label: "B1 — 256 tokens + 32 overlap", value: 0.9888 },
        { label: "C1 — 256 tokens, section-aware", value: 0.9775 },
        { label: "C0 — 256 tokens, fixed (selected)", value: 0.9775 },
      ],
      unit: "doc_recall@50",
      winnerLabel: "C0 — 256 tokens, fixed (selected)",
      detail: "Selected: 256-token fixed window, 0 overlap, stride 256 (doc_recall@50 0.9775, doc_mrr 0.7984, doc_ndcg@10 0.8320). B1 scored slightly higher on doc_recall@50 alone (0.9888) but was a practical tie once MRR/nDCG@10 confidence intervals were checked (95% CIs include zero) — the frozen tie-break rule keeps the simpler configuration rather than chasing one metric.",
      source_path: "results/phase_3_2_chunking_ablation.json",
      source_key: "final_winner",
    },
    {
      title: "2. Embedding-model benchmark",
      status_type: "frozen",
      outcome: "selected",
      summary: "Four embedding models were benchmarked on the winning chunk config; the challenger showed a credible, non-regressing improvement over the BGE-small reference.",
      candidates: [
        { label: "bge_small (reference)", value: 0.9326 },
        { label: "bge_base", value: 0.9438 },
        { label: "nomic_embed", value: 0.9663 },
        { label: "qwen3_embedding (selected)", value: 0.9888 },
      ],
      unit: "doc_recall@10",
      winnerLabel: "qwen3_embedding (selected)",
      detail: "Selected: Qwen/Qwen3-Embedding-0.6B, 1024 dimensions (doc_recall@10 0.9888, doc_recall@50 1.0, doc_mrr 0.9251) — a credible improvement over the bge_small reference with no regression on the frozen priority metric order.",
      source_path: "results/phase_3_3_embedding_model_benchmark.json",
      source_key: "final selection",
    },
    {
      title: "3. Sparse retrieval baseline",
      status_type: "frozen",
      outcome: "evaluated",
      summary: "A BM25/FTS sparse baseline was measured against the same dense pipeline to check whether sparse retrieval alone was competitive.",
      candidates: [
        { label: "Dense (Qwen3)", value: 0.9251 },
        { label: "Sparse (BM25/FTS)", value: 0.8830 },
      ],
      unit: "MRR",
      winnerLabel: "Dense (Qwen3)",
      detail: "Dense retrieval outperformed sparse on every measured metric (recall@10, recall@50, MRR, nDCG@10).",
      source_path: "results/phase_3_4_bm25_fts_baseline.json",
      source_key: "measured_metrics",
    },
    {
      title: "4. RRF hybrid fusion",
      status_type: "frozen",
      outcome: "rejected",
      summary: "Reciprocal rank fusion of dense + sparse was tested. It improved MRR slightly, but the gain was a practical tie under the project's frozen tie rule — not worth the added complexity.",
      candidates: [
        { label: "Dense only", value: 0.9251 },
        { label: "RRF hybrid", value: 0.9457 },
      ],
      unit: "MRR",
      detail: "Recall@10 hit delta = 0, 95% CIs include zero — dense-only selected as the simpler, equally-effective option.",
      source_path: "results/phase_3_5_rrf_hybrid_fusion.json",
      source_key: "selection.selected",
    },
    {
      title: "5. Cross-encoder reranking",
      status_type: "frozen",
      outcome: "rejected",
      summary: "A cross-encoder reranker was applied on top of dense retrieval. The result was a large, unambiguous regression, not a marginal one.",
      candidates: [
        { label: "No rerank", value: 0.9251 },
        { label: "Cross-encoder rerank", value: 0.6580 },
      ],
      unit: "MRR",
      winnerLabel: "No rerank",
      detail: "MRR dropped from 0.9251 to 0.6580 and nDCG@10 from 0.9407 to 0.7074 — reranking was rejected outright.",
      source_path: "results/phase_3_6_cross_encoder_reranking.json",
      source_key: "selection.selected",
    },
    {
      title: "6. CRAG confidence grading",
      status_type: "frozen",
      outcome: "selected",
      summary: "A single global confidence threshold on the top-1 retrieval score decides whether the system answers or refuses, calibrated by Youden's J statistic over should-answer / should-refuse populations.",
      detail: "Frozen threshold: 0.5531 (top1_score). Measured true-refusal rate 83.19%, false-refusal rate 6.74%.",
      source_path: "results/phase_3_7_crag_confidence_grading.json",
      source_key: "threshold",
    },
    {
      title: "7. Rules-first router",
      status_type: "frozen",
      outcome: "selected",
      summary: "A deterministic keyword/regex/gazetteer router classifies each question into one of 6 supported intents (of the roadmap's 10 — 4 have zero development examples).",
      detail: "Accuracy 85.82% (1,658/1,932), macro-F1 0.8871 over the frozen development question set.",
      source_path: "results/phase_3_8_rules_first_router.json",
      source_key: "accuracy / macro_f1",
    },
    {
      title: "8. Metadata pre-filtering",
      status_type: "frozen",
      outcome: "selected",
      summary: "A scalar (CIK, fiscal_year) pre-filter applied before exact search was measured against the unfiltered baseline.",
      detail: "Credible improvement over the reference baseline with no regression — selected into the production stack.",
      source_path: "results/phase_3_9_metadata_prefiltering.json",
      source_key: "selection",
    },
    {
      title: "9. Structured XBRL SQL routing",
      status_type: "frozen",
      outcome: "selected",
      summary: "Single-fact lookup questions are routed to a deterministic SQL path over data/xbrl.duckdb instead of dense retrieval.",
      detail: "Routing coverage 80.60% (1,130/1,402 xbrl_fact questions), exact-match rate 99.91%, and — critically — 0.00% trap-leak rate across 139 unanswerable-by-construction questions.",
      source_path: "results/phase_3_10_xbrl_sql_path.json",
      source_key: "routing_coverage / sql_exact_match_rate / trap_leak_rate",
    },
    {
      title: "10. Derived calculations",
      status_type: "frozen",
      outcome: "evaluated",
      summary: "Year-over-year differences and cross-company comparisons are computed deterministically from two XBRL lookups rather than generated.",
      detail: "Difference: 79.51% coverage, 100% exact match (194/194 attempted). Greater-than: 82.86% coverage, 100% exact match (87/87 attempted).",
      source_path: "results/phase_3_11_derived_calculations.json",
      source_key: "difference / greater_than",
    },
    {
      title: "11. Tree / section navigation",
      status_type: "roadmap",
      outcome: "evaluated",
      summary: "Filing and section resolution (e.g. “Item 1A of a specific 10-K”) was implemented and measured, but is not wired into the live router — classify_intent() has no navigation intent yet.",
      detail: "Filing resolution 99.90% (987/988), section-found rate 99.88%, scope-leak rate 0.00%. Frozen capability, not a live route.",
      source_path: "results/phase_3_12_tree_section_navigation.json",
      source_key: "filing_resolution_rate / section_found_rate / scope_leak_rate",
    },
    {
      title: "12. Phase 3 exit audit",
      status_type: "frozen",
      outcome: "selected",
      summary: "All nine Phase 3 exit criteria passed before the project moved to full-corpus production work.",
      detail: "19 frozen ablation-table rows. Regression at that checkpoint: 1,867 portable tests passed, 1,897 full-suite tests passed.",
      source_path: "project_plan/PHASE3_EXIT_AUDIT.md",
      source_key: "exit criteria summary",
    },
  ],

  guardrails: [
    {
      name: "Input guardrails",
      description: "Request-length cap, scope enforcement, advice detection, PII checks, and injection-pattern detection run before any retrieval happens.",
      testCount: 74,
      source_path: "project_plan/PHASE4_INPUT_GUARDRAILS.md",
    },
    {
      name: "Context guardrails",
      description: "Retrieved evidence is treated as untrusted data, wrapped in explicit BEGIN/END delimiters, and checked for provenance completeness — tested against adversarial, instruction-shaped retrieval.",
      testCount: 52,
      source_path: "project_plan/PHASE4_CONTEXT_GUARDRAILS.md",
    },
    {
      name: "Output guardrails",
      description: "Every citation is checked against the evidence actually supplied to the model, plus advice-keyword detection, before a dense-route answer is returned.",
      testCount: 40,
      source_path: "project_plan/PHASE4_OUTPUT_GUARDRAILS.md",
    },
  ],

  evaluation: [
    {
      label: "Portable test suite",
      value: "2,223",
      unit: "passed",
      context: "38 deselected (local-data/GPU/model-marked tests) — the public-clone-safe subset.",
      source_path: "results/phase_4_11_deployment_summary.json",
      source_key: "regression_gates.portable_after_this_task",
      status_type: "frozen",
    },
    {
      label: "Full non-generation-api suite",
      value: "2,260",
      unit: "passed",
      context: "1 deselected (the live-network generation_api test, opt-in only).",
      source_path: "results/phase_4_11_deployment_summary.json",
      source_key: "regression_gates.not_generation_api_full_suite_after_this_task",
      status_type: "frozen",
    },
    {
      label: "Protected TEST usage",
      value: "0/3",
      context: "Official TEST runs used, unchanged throughout Phases 3–4.",
      source_path: "results/phase_4_11_deployment_summary.json",
      source_key: "protected_test_usage",
      status_type: "frozen",
    },
    {
      label: "Router accuracy",
      value: "85.82%",
      unit: "(1,658 / 1,932)",
      context: "Macro-F1 0.8871 over the 6 supported intents.",
      source_path: "results/phase_3_8_rules_first_router.json",
      source_key: "accuracy",
      status_type: "frozen",
    },
    {
      label: "XBRL SQL trap-leak rate",
      value: "0.00%",
      unit: "(0 / 139)",
      context: "No unanswerable-by-construction question was ever falsely answered by the structured route.",
      source_path: "results/phase_3_10_xbrl_sql_path.json",
      source_key: "trap_leak_rate",
      status_type: "frozen",
    },
  ],

  timeline: [
    { title: "Phase 0 — Foundation", description: "Environment, configuration, storage, logging, and a serving-feasibility spike. Complete.", status: "complete" },
    { title: "Phase 1 — Make It Work End-to-End", description: "A minimal, real, working RAG loop over a development corpus: normalize, chunk, embed, index, retrieve, generate, cite. Complete.", status: "complete" },
    { title: "Phase 2 — Evaluation Harness", description: "A frozen dev/test split, tag registry, truth contract, and evaluation schema — the measurement infrastructure everything after this relies on. Complete.", status: "complete" },
    { title: "Phase 3 — Measured Ablations", description: "Twelve controlled experiments decided chunking, embedding model, sparse/hybrid/rerank, confidence grading, routing, pre-filtering, and structured paths. All nine exit criteria passed.", status: "complete" },
    { title: "Phase 4 — Make It Real", description: "Full-corpus artifacts (10.49M chunks/embeddings), guardrails, a FastAPI service, and deployment preparation. In progress — deployment is deferred pending a local production-readiness gate.", status: "in-progress" },
  ],

  roadmap: {
    completed: [
      "Data preparation and readiness (Phase 0)",
      "Baseline end-to-end RAG loop (Phase 1)",
      "Evaluation harness — frozen DEV/TEST split, tag registry, truth contract (Phase 2)",
      "Architecture optimization — 12 measured ablations, chunking/embedding/routing/CRAG decisions (Phase 3)",
      "Full-corpus normalization, chunking, embedding, and vector index (Tasks 4.1–4.4)",
      "XBRL serving representation (Task 4.5)",
      "Generation production interface (Task 4.6)",
      "Input, context, and output guardrails (Tasks 4.7–4.9)",
      "FastAPI service with /health, /status, /query (Task 4.10)",
      "Local CPU containerization, Docker validation, and Terraform/Fargate preparation (Task 4.11 prep)",
      "Local chat UI and project showcase (Tasks 4.12–4.12b)",
    ],
    inProgress: [
      "Wire the selected metadata pre-filter into the live dense route — unscoped exact search over 10,487,096 rows measured about 33 s per query (Task 4.A smoke), versus about 60-80 ms when scoped by company and year",
      "Local end-to-end production integration, regression/reliability/performance validation (Gates B–D)",
      "Final evaluation/readiness and release-candidate freeze (Gates E–F)",
    ],
    deferred: [
      "Real AWS ECS/Fargate deployment — deferred by explicit user decision until the readiness gate passes",
      "ECR image push and terraform apply",
      "Deployed health/status/restart/logging validation on real infrastructure",
    ],
  },

  // ------------------------------------------------------------------
  // Task 4.12a - Deep System Architecture (Level 2). Every step below is
  // status-tagged: "live" (green, actually reachable through the current
  // API), "frozen" (blue, a real built/selected artifact or decision that
  // is NOT yet wired into the live request path), "planned" (amber, does
  // not exist yet), or "not-routed" (muted/dashed, implemented and
  // evaluated but not reachable from the live router).
  //
  // Two real findings surfaced while verifying this against source code
  // (not assumed from the task prompt): (1) CRAG confidence-based refusal
  // (src/crag/confidence.py) is never imported outside src/eval/
  // phase3_crag.py and its own tests - it is NOT wired into
  // src/generation/minimal.py, so the live dense route never refuses on
  // low confidence. (2) the live dense retriever (since Task 4.A,
  // src/retrieval/production.py:ProductionDenseRetriever) is never given
  // cik/fiscal_year by the service layer, so Task 3.9's metadata
  // pre-filtering is also selected-but-not-live. (3)
  // src/api/service.py's own docstring confirms numeric_derived/
  // cross_entity intents (and therefore "derived calculation") are not
  // wired into the live structured route either. All three are marked
  // "not-routed" below, exactly like tree/section navigation.
  // ------------------------------------------------------------------
  deepArchitecture: {
    tabs: [
      {
        id: "query",
        label: "Online Query Path",
        flows: [
          {
            title: "Request lifecycle",
            note: "The complete path a real HTTP request takes through this service today.",
            steps: [
              { label: "Browser / Client", status: "live",
                detail: { purpose: "Originates a question.", input: "Natural-language text", output: "HTTP request to this server", implementation: "Any HTTP client, including this page's own query UI", status: "Live" } },
              { label: "FastAPI endpoints", sublabel: "POST /query · GET /health · GET /status", status: "live",
                detail: { purpose: "The service's only entry points.", implementation: "src/api/app.py:create_app()", evidence: "openapi.json exposes exactly these 3 paths (test_openapi_contract_has_expected_paths_and_no_internal_fields)", status: "Live" } },
              { label: "Request Validation", sublabel: "Pydantic schema", status: "live",
                detail: { purpose: "Rejects a malformed request before any business logic runs.", input: "{question: str} (required)", output: "422 on missing/wrong-typed field", implementation: "src/api/schemas.py:QueryRequest", status: "Live" } },
              { label: "Input Guardrails", sublabel: "7 checks, first violation wins", status: "live",
                tooltip: "type → empty → length (max 2,000 chars) → control chars → injection (20 keywords) → advice (18 keywords) → PII (SSN/card/email/phone) → out-of-scope",
                detail: { purpose: "Deterministic, non-LLM request-level safety gate.", implementation: "src/guards/input.py:check_input() - exact order: type → empty_input → input_too_long (2,000 char cap) → disallowed_control_character → prompt_injection_detected → advice_request_detected → pii_detected → out_of_scope", output: "HTTP 200 with status=\"rejected\" + a stable reason_code (never 4xx/5xx - a guard refusal is an expected outcome, not a transport error)", evidence: "74 dedicated tests (project_plan/PHASE4_INPUT_GUARDRAILS.md)", status: "Live" } },
              { label: "Intent / Route Decision", sublabel: "rules-first router, 6 intents", status: "live",
                detail: { purpose: "Deterministic keyword/regex/gazetteer classification - no LLM call.", implementation: "src/router/rules.py:classify_intent() → xbrl_fact | numeric_derived | cross_entity | unanswerable | out_of_scope | advice", evidence: "Accuracy 85.82% (1,658/1,932), macro-F1 0.8871 (results/phase_3_8_rules_first_router.json)", status: "Live" } },
              { branch: [
                { label: "Dense retrieval", sublabel: "over SEC filing text", status: "live",
                  detail: { purpose: "Fallback for every non-xbrl_fact intent.", implementation: "See “Retrieval & Data Plane” tab for the full internal pipeline.", status: "Live" } },
                { label: "Structured XBRL route", sublabel: "deterministic SQL", status: "live",
                  detail: { purpose: "Single-fact lookup for the xbrl_fact intent.", implementation: "See “Retrieval & Data Plane” tab for the full internal pipeline.", status: "Live" } },
                { label: "Tree / section navigation", sublabel: "implemented — not live-routed", status: "not-routed",
                  detail: { purpose: "Filing/section resolution (e.g. “Item 1A of a specific 10-K”).", implementation: "src/nav/section_navigation.py - classify_intent()'s 6-intent taxonomy has no navigation intent, so there is no live routing decision that reaches it.", evidence: "Filing resolution 99.90%, section-found 99.88%, scope-leak 0.00% (results/phase_3_12_tree_section_navigation.json)", status: "Implemented + evaluated, not live-routed" } },
              ] },
              { label: "Retrieval Security Guard", sublabel: "dense route only, post-cache", status: "live",
                detail: { purpose: "Blocks poisoned, suspicious, duplicate, or provenance-invalid retrieved text before context construction.", implementation: "src/security/retrieval_guard.py:RetrievalSecurityGuard runs after retriever.retrieve(), so exact-cache HITs and MISSes are both scanned. Only approved candidates enter generation.", evidence: "Synthetic fixture thresholds: high-confidence poison blocked 100%, malicious context acceptance 0%, missing provenance blocked 100%, clean quoted examples retained 100%. Safe counters are exposed through GET /status as retrieval_security.", status: "Live deterministic scanner; no LLM classifier or external moderation call" } },
              { label: "Context Guardrails + Generation", sublabel: "dense route only", status: "live",
                detail: { purpose: "Treats retrieved evidence as untrusted data, then generates.", implementation: "src/generation/minimal.py:MinimalGenerator.answer()", status: "Live (structured route skips this entirely - no generation call)" } },
              { label: "Output Guardrails + Citation Validation", status: "live",
                detail: { purpose: "Validates citations against supplied evidence before the answer leaves the service.", implementation: "src/guards/output.py:check_dense_output() / check_structured_numeric_output()", status: "Live" } },
              { label: "FastAPI Response", status: "live",
                detail: { purpose: "Uniform JSON envelope regardless of route.", output: "{status, answer, citations, route, reason_code, request_id}", implementation: "src/api/schemas.py:QueryResponse", status: "Live" } },
            ],
          },
        ],
      },

      {
        id: "retrieval",
        label: "Retrieval & Data Plane",
        flows: [
          {
            title: "Dense retrieval — internal pipeline (live path)",
            steps: [
              { label: "Query", status: "live" },
              { label: "Exact Retrieval Cache", sublabel: "exact-query LRU + TTL, in-process", status: "live",
                detail: { purpose: "Skips repeated dense query embedding + LanceDB search only when the canonical query, k, filters, retriever config, model identity, and index artifact identity match exactly.", implementation: "src/retrieval/cache.py:CachedRetriever wraps the live BaselineRetriever during src/api/dependencies.py startup when RETRIEVAL_CACHE_ENABLED=true.", evidence: "Statistics are exposed through GET /status as retrieval_cache; cached values are retrieval evidence only, never generated answers.", status: "Live - per Python process, not semantic, not shared across workers" } },
              { branch: [
                { label: "HIT", sublabel: "Cached Candidate Evidence", status: "live",
                  detail: { purpose: "Return a defensive copy of previously retrieved evidence.", implementation: "Cache key is a SHA-256 digest; raw query text is not exposed in status/logging.", status: "Live" } },
                { label: "MISS", sublabel: "Embed + exact search + store", status: "live",
                  detail: { purpose: "Run the existing dense retriever unchanged, then store successful retrieval evidence.", implementation: "Exceptions/model failures/LanceDB failures are not cached.", status: "Live" } },
              ] },
              { label: "Query Embedding", sublabel: "Qwen/Qwen3-Embedding-0.6B on MISS", status: "live",
                tooltip: "Revision 97b0c614be... · 1024 dimensions • cosine similarity over normalized vectors",
                detail: { purpose: "Turns the question into a query vector when no exact cache entry exists.", implementation: "src/embeddings/model_registry.py:encode_queries(QWEN3_EMBEDDING, ...) with the frozen Qwen3 query instruction; identity cross-checked against the production index at startup", status: "Live - the Phase 3-selected model; startup fails closed if it does not match the index" } },
              { label: "LanceDB Vector Search", sublabel: "exact cosine, unfiltered on MISS", status: "live",
                detail: { purpose: "Top-k nearest neighbors by cosine distance when no exact cache entry exists.", implementation: "src/retrieval/production.py:ProductionDenseRetriever.retrieve() - exact search over the 10,487,096-row index; accepts cik/fiscal_year pre-filters but the live router does not pass them yet", status: "Live (unscoped searches are slow - see roadmap)" } },
              { label: "Candidate Evidence", status: "live" },
              { label: "Cache Store", sublabel: "successful dense retrieval only", status: "live",
                detail: { purpose: "Stores ordered retrieval evidence with scores/provenance for future exact cache hits.", implementation: "src/retrieval/cache.py:ExactRetrievalCache stores defensive copies and applies TTL/LRU eviction.", status: "Live" } },
              { label: "Retrieval Security Guard", sublabel: "runs after cache HIT or MISS", status: "live",
                detail: { purpose: "Prevents cache hits from bypassing query-time poison/provenance checks.", implementation: "src/security/retrieval_guard.py validates source/provenance, collapses exact duplicate text, scans dense text for deterministic prompt-injection signals, and returns approved/suspicious/blocked candidate sets.", evidence: "Cache stores raw retrieval results only; guard decisions are not cached forever. GET /status exposes aggregate retrieval_security counters only.", status: "Live - dense text only" } },
              { label: "Context Guardrails", sublabel: "untrusted evidence boundary", status: "live" },
              { label: "Prompt Assembly + Prompt-Prefix Cache", sublabel: "opt-in, off by default", status: "live",
                detail: { purpose: "Lays out guard-approved evidence before the question so providers can reuse the shared prompt prefix; adds provider cache breakpoints only where the model is known to need them.", implementation: "src/generation/minimal.py:build_user_prompt() + src/generation/prompt_cache.py (strategy: explicit_breakpoints for anthropic/*, automatic for OpenAI/DeepSeek/Gemini 2.5+, local_prefix for Ollama, none otherwise). Enabled with PROMPT_CACHE_ENABLED=true.", evidence: "Measured locally on Ollama gpt-oss:20b: same-evidence/new-question prompt processing 3.7 s -> 0.22 s (results/phase_4_14a_prompt_cache_benchmark.json). OpenRouter savings not measured. Aggregate counters exposed through GET /status as prompt_cache.", status: "Live when enabled; this is prompt-prefix caching, not response caching - no answer is ever cached" } },
              { label: "Generation", sublabel: "config-driven provider", status: "live" },
              { label: "Citation Validation", status: "live" },
              { label: "Response", status: "live" },
            ],
          },
          {
            title: "Frozen capabilities NOT currently wired into this live retriever",
            note: "Selected by Phase 3, built and measured - just not applied by the current thin API layer (Task 4.10's own documented scope decision).",
            steps: [
              { branch: [
                { label: "Metadata pre-filtering", sublabel: "Task 3.9 — selected", status: "not-routed",
                  detail: { purpose: "Scalar (CIK, fiscal_year) pre-filter before exact search.", implementation: "src/retrieval/filtered.py:build_predicate is reused by ProductionDenseRetriever, which accepts cik/fiscal_year - but the live service does not pass filters yet.", evidence: "Credible improvement, no regression (results/phase_3_9_metadata_prefiltering.json)", status: "Selected by Phase 3, not applied live" } },
                { label: "CRAG confidence gating", sublabel: "Task 3.7 — threshold 0.5531", status: "not-routed",
                  detail: { purpose: "Refuse to answer when top-1 retrieval confidence is below a calibrated threshold.", implementation: "src/crag/confidence.py:should_refuse() - never imported outside src/eval/phase3_crag.py and its own tests; not called from src/generation/minimal.py.", evidence: "True-refusal 83.19%, false-refusal 6.74% (results/phase_3_7_crag_confidence_grading.json)", status: "Frozen threshold selected, not applied live" } },
              ] },
            ],
          },
          {
            title: "Live vs. frozen vs. planned — the dense index specifically",
            steps: [
              { branch: [
                { label: "LIVE", sublabel: "Qwen3-Embedding-0.6B production index", status: "live",
                  tooltip: "10,487,096 rows · 1024-dim · 256-token window, stride 256, 0 overlap · cosine, normalized embeddings",
                  detail: { purpose: "What /query actually searches today (Task 4.A, Gate A).", implementation: "src/retrieval/production.py:ProductionDenseRetriever over artifacts/indexes_full; row count and model reported by /status", evidence: "results/phase_4a_production_dense_smoke.json", status: "Live, fetched live from /status" } },
                { label: "HISTORICAL / DEV", sublabel: "BAAI/bge-small-en-v1.5 dev index", status: "frozen",
                  tooltip: "162,357 rows · 384-dim · 512-token window, stride 512, 0 overlap (the original Task 1.3 pre-ablation baseline)",
                  detail: { purpose: "The Phase 1 development index, kept for reproducibility and tests.", implementation: "src/api/dependencies.py:DEV_CHUNK_CONFIG_HASH - reachable only with DENSE_RETRIEVER_MODE=dev", evidence: "results/phase_1_3_chunking_summary.json", status: "Explicit opt-in only; production mode never falls back to it" } },
                { label: "REMAINING GAP", sublabel: "pre-filter not routed live", status: "planned",
                  detail: { purpose: "Pass company/year filters from the router into the production retriever so queries avoid the unscoped exact scan (about 33 s measured).", implementation: "ProductionDenseRetriever already accepts cik/fiscal_year; the service layer does not pass them yet", status: "Not started" } },
              ] },
            ],
          },
          {
            title: "Structured XBRL route — internal pipeline (live path)",
            note: "Fundamentally different from dense RAG: deterministic SQL, no generation call.",
            steps: [
              { label: "Query", status: "live" },
              { label: "Structured Intent Detection", sublabel: "xbrl_fact intent only", status: "live" },
              { label: "Company / CIK Resolution", sublabel: "gazetteer over data/xbrl.duckdb", status: "live",
                detail: { implementation: "src/api/dependencies.py:build_production_gazetteer() - real SEC company/CIK data from the submissions table", status: "Live" } },
              { label: "Fiscal Year Resolution", sublabel: "2016–2020 supported window", status: "live" },
              { label: "Metric / XBRL Tag Resolution", sublabel: "15-tag frozen registry", status: "live",
                detail: { implementation: "configs/eval_tags.yaml via src/eval/tag_registry.py", status: "Live" } },
              { label: "DuckDB SQL Query", sublabel: "data/xbrl.duckdb", status: "live",
                tooltip: "~90.7M facts · 218,166 submissions · 10,757 CIKs · 291,429 distinct raw tags (15 evaluable)",
                detail: { implementation: "src/sql/xbrl_lookup.py:XbrlFactIndex", evidence: "DATA_READINESS_REPORT.md", status: "Live" } },
              { label: "Canonical Fact Selection", status: "live" },
              { label: "Optional Derived Calculation", sublabel: "year-over-year / cross-company", status: "not-routed",
                detail: { purpose: "Compute a difference or comparison from two XBRL lookups.", implementation: "src/sql/derived.py exists and is evaluated, but src/api/service.py's own docstring confirms numeric_derived/cross_entity intents are deliberately not wired into the live route.", evidence: "Difference 79.51% coverage / 100% exact match; greater-than 82.86% coverage / 100% exact match (results/phase_3_11_derived_calculations.json)", status: "Evaluated, not applied live" } },
              { label: "Structured Provenance", sublabel: "check_structured_numeric_output()", status: "live",
                detail: { purpose: "Validate deterministic XBRL fact provenance without forcing structured facts through the dense-text poison scanner.", implementation: "src.guards.output.check_structured_numeric_output reuses the structured context/provenance contract; the route has no generation call and no retrieved text prompt.", status: "Live; XBRL semantics unchanged" } },
              { label: "Deterministic Response", sublabel: "no generation call", status: "live",
                detail: { evidence: "Trap-leak rate 0.00% across 139 unanswerable-by-construction questions (results/phase_3_10_xbrl_sql_path.json)", status: "Live" } },
            ],
          },
        ],
      },

      {
        id: "offline",
        label: "Offline Build Pipeline",
        flows: [
          {
            title: "Production artifact build",
            steps: [
              { branch: [
                { label: "EDGAR-CORPUS", sublabel: "91,086 filings", status: "frozen" },
                { label: "SEC XBRL", sublabel: "data/xbrl.duckdb", status: "frozen" },
                { label: "Primary filings", sublabel: "990 filings, Docling-parsed", status: "frozen" },
              ] },
              { label: "Normalization", sublabel: "90,239 normalized · 847 valid-empty", status: "frozen",
                detail: { implementation: "results/phase_4_1_full_corpus_normalization.json", status: "Frozen (Task 4.1)" } },
              { label: "Chunking", sublabel: "256 tokens · 0 overlap · stride 256", status: "frozen",
                tooltip: "10,487,096 chunks across 54 Parquet shards — selected because it beat every other candidate on the frozen priority metric order after 3 practical-tie rounds",
                detail: { implementation: "results/phase_4_2_full_corpus_chunking.json", evidence: "See “Architecture Decisions” below for why this config won", status: "Frozen (Task 4.2)" } },
              { label: "Embedding", sublabel: "Qwen3-Embedding-0.6B, 1024-d", status: "frozen",
                tooltip: "10,487,096 vectors · 54 embedding shards · revision 97b0c614...",
                detail: { implementation: "results/phase_4_4_full_corpus_vector_index_summary.json (task_4_3_manifest_sha256)", status: "Frozen (Task 4.3)" } },
              { label: "Vector Index Build", sublabel: "10,487,096 rows, LanceDB exact", status: "frozen",
                detail: { status: "Frozen (Task 4.4)" } },
              { label: "Retrieval Security Audit Hook", sublabel: "synthetic dry-run smoke", status: "live",
                detail: { purpose: "Offline safety regression check for RAG poisoning fixtures and query-time scanner overhead.", implementation: "scripts/smoke_retrieval_security.py writes results/phase_4_14_retrieval_security_smoke.json from synthetic fixtures only.", evidence: "No full-corpus scan, no rebuild, no generation provider, no protected TEST access.", status: "Live developer smoke; production artifacts remain frozen" } },
              { label: "Production Artifacts", sublabel: "click for exact hashes/manifests", status: "frozen",
                detail: { purpose: "Reproducibility / artifact identity.", implementation: "phase_4_1_config_hash=754d9c898772c332...; chunk_config_hash=ba99e2f7861c48bc...; task_4_3_manifest_sha256=a4d1421bb287ea6a...; index_identity_hash=158e6b0605ad483e... (full values in results/phase_4_4_full_corpus_vector_index_summary.json)", status: "Frozen" } },
            ],
          },
          {
            title: "Architecture decisions — how choices were made",
            note: "Measured, not guessed. See the “Experiments” section above for full metrics.",
            multi: [
              { label: "Chunking", steps: [
                { label: "Candidate chunk strategies", status: "frozen" },
                { label: "DEV Evaluation", status: "frozen" },
                { label: "Retrieval Metrics", status: "frozen" },
                { label: "Winner Selection", status: "frozen" },
                { label: "Frozen: 256 tokens, 0 overlap", status: "frozen" },
              ] },
              { label: "Embedding model", steps: [
                { label: "Candidate embedding models", status: "frozen" },
                { label: "Controlled Benchmark", status: "frozen" },
                { label: "Retrieval Evaluation", status: "frozen" },
                { label: "Winner Selection", status: "frozen" },
                { label: "Qwen3-Embedding-0.6B", status: "frozen" },
              ] },
              { label: "Hybrid retrieval (negative result)", steps: [
                { label: "Dense + Sparse/BM25", status: "frozen" },
                { label: "RRF Experiment", status: "frozen" },
                { label: "Practical tie, no real gain", status: "not-routed" },
                { label: "Dense-only retained", status: "live" },
              ] },
              { label: "Reranking (negative result)", steps: [
                { label: "Dense candidates", status: "frozen" },
                { label: "Cross-encoder rerank experiment", status: "frozen" },
                { label: "Large negative result", status: "not-routed" },
                { label: "No reranker retained", status: "live" },
              ] },
            ],
          },
        ],
      },

      {
        id: "evaluation",
        label: "Evaluation & Release",
        flows: [
          {
            title: "Evaluation / release control plane",
            steps: [
              { label: "Frozen DEV Evaluation Set", status: "frozen" },
              { label: "Ablation / Experiment", status: "frozen" },
              { label: "Metrics", status: "frozen" },
              { label: "Regression Tests", sublabel: "2,278 passed, 1 deselected", status: "live",
                detail: { implementation: "python -m pytest -m \"not generation_api\"", status: "Current, re-run every task" } },
              { label: "Decision Record", sublabel: "results/phase_3_*.json", status: "frozen" },
              { label: "Frozen Configuration", status: "frozen" },
              { label: "Production Artifact Build", status: "frozen" },
              { label: "Local Production Readiness Gates", sublabel: "Gates A–F", status: "planned",
                detail: { implementation: "project_plan/PROJECT_EXECUTION.md, Task 4.11", status: "Gate A (full-corpus dense integration) not started" } },
              { label: "AWS Deployment", sublabel: "deferred", status: "planned" },
            ],
          },
        ],
      },

      {
        id: "runtime",
        label: "Runtime / Serving",
        flows: [
          {
            title: "Local runtime today",
            steps: [
              { label: "Browser", status: "live" },
              { label: "FastAPI Application", status: "live" },
              { branch: [
                { label: "Dense index", sublabel: "10,487,096 rows (production, Qwen3)", status: "live" },
                { label: "Retrieval Cache", sublabel: "LIVE · exact-query LRU + TTL · in-process", status: "live",
                  detail: { purpose: "Avoid duplicate dense embedding/search work for repeated exact retrieval requests.", implementation: "Configured by RETRIEVAL_CACHE_ENABLED/MAX_ENTRIES/TTL_SECONDS/SCHEMA_VERSION. Each Python process has its own memory cache.", status: "Live serving optimization; does not change retrieval ranking or integrate the Qwen production index" } },
                { label: "Retrieval Security", sublabel: "deterministic scanner + counters", status: "live",
                  detail: { purpose: "Filters dense retrieval evidence after cache lookup and before prompt construction.", implementation: "src/security/* plus MinimalGenerator integration; /status exposes safe aggregate telemetry as retrieval_security.", status: "Live; no raw queries or SEC text in telemetry" } },
                { label: "XBRL DuckDB", sublabel: "data/xbrl.duckdb", status: "live" },
                { label: "Embedding model", sublabel: "Qwen/Qwen3-Embedding-0.6B", status: "live" },
                { label: "Generation provider", sublabel: "config-driven", status: "live",
                  tooltip: "Currently configured: openrouter / openai/gpt-oss-20b (fetched live from /status)" },
              ] },
            ],
          },
          {
            title: "Planned AWS deployment (deferred)",
            note: "AWS deployment is currently DEFERRED until local production-readiness gates pass. No AWS resources are running.",
            steps: [
              { label: "ECR", sublabel: "image repository", status: "planned" },
              { label: "ECS Fargate", sublabel: "continuously warm, CPU-only", status: "planned" },
              { label: "EFS / artifact storage", sublabel: "candidate, not yet decided", status: "planned",
                detail: { purpose: "Deliver the dense index / xbrl.duckdb to the container.", implementation: "project_plan/PHASE4_DEPLOYMENT.md - a real bind-mount finding during Task 4.11 local validation favors EFS over a literal host path mount, but this was never decided or provisioned.", status: "Open decision" } },
              { label: "CloudWatch", sublabel: "logs", status: "planned" },
              { label: "Terraform", sublabel: "skeleton validated, never applied", status: "planned",
                detail: { implementation: "infra/terraform/ - terraform validate passes; terraform apply has never been run", status: "Prepared, not provisioned" } },
            ],
          },
        ],
      },
    ],
  },
};
