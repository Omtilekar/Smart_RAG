"""Task 4.14a - reproducible prompt-caching benchmark.

Runs the REAL generation path (MinimalGenerator -> retrieval-security guard
-> context guard -> prompt layout -> provider adapter) against synthetic,
deterministic SEC-style evidence, once with prompt caching disabled (legacy
layout) and once enabled (stable-prefix layout), and writes
results/phase_4_14a_prompt_cache_benchmark.json plus a markdown table.

Default provider is the free local Ollama server. OpenRouter is a paid API:
it is refused unless --allow-paid is passed explicitly. Metrics a provider
does not report are written as null / "unavailable" - never estimated.

    python scripts/benchmark_prompt_cache.py --provider ollama --model gpt-oss:20b

Measurement notes (also recorded in the JSON):
- Evidence is synthetic (no retrieval index / embedding model needed); chunk
  size mirrors the production 512-token window. Each run mixes a per-run salt
  into the evidence so leftover provider state from an earlier run can never
  produce a hit.
- --num-predict caps Ollama's output length (injected into the HTTP payload
  by this harness only, not by the product code) so generation time does not
  drown the prompt-processing signal. Cloud runs are not capped.
- Ollama reports no cached-token count; its `prompt_eval_ms` (prompt
  processing time) is the only observable signal of local KV-prefix reuse.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.generation.minimal import MinimalGenerator  # noqa: E402
from src.generation.prompt_cache import PromptCacheConfig, PromptCacheMetrics  # noqa: E402
from src.generation.provider import ProviderResponse  # noqa: E402
from src.retrieval.baseline import RetrievalResult  # noqa: E402

OUT_PATH = REPO / "results" / "phase_4_14a_prompt_cache_benchmark.json"

_TOPICS = ["net sales", "operating margin", "research and development expense", "liquidity and capital resources",
           "risk factors related to supply chain", "segment revenue", "long-term debt", "share repurchases"]
_Q = {
    "q1": "What were total net sales for the fiscal year?",
    "q2": "How did operating margin change versus the prior year?",
    "q3": "What does the filing say about liquidity and capital resources?",
    "q4": "What were the main risk factors described?",
}


def _chunk_text(company: str, fy: int, idx: int, salt: str, words: int = 380) -> str:
    rnd = random.Random(f"{company}|{fy}|{idx}|{salt}")
    out = []
    while len(out) < words:
        topic = rnd.choice(_TOPICS)
        out.append(
            f"For fiscal {fy}, {company} reported {topic} of ${rnd.randint(100, 9999)}.{rnd.randint(0, 9)} million, "
            f"a change of {rnd.randint(1, 40)}% compared with the prior period, driven by {rnd.choice(_TOPICS)} "
            f"and {rnd.choice(_TOPICS)} as discussed in Item {rnd.randint(1, 9)}A of the annual report."
        )
        out = " ".join(out).split()
    return " ".join(out[:words]) + "."


def _results(company: str, fy: int, salt: str, variant: int = 0) -> list[RetrievalResult]:
    return [
        RetrievalResult(
            rank=i + 1, score=0.9, distance=0.1, chunk_id=f"{company.lower()}_{fy}.htm::chunk{i + variant * 10}",
            document_id=f"{company.lower()}_{fy}.htm", text=_chunk_text(company, fy, i + variant * 10, salt),
            cik=1000, company=company, form_type="10-K", fiscal_year=fy, source="edgar_corpus",
            source_filename=f"{company.lower()}_{fy}.htm", source_split="bench", ordinal=i, token_count=512,
            chunk_config_hash="bench", normalizer_version="bench", normalization_build_sha256="0" * 64,
            development_manifest_sha256="0" * 64,
        )
        for i in range(5)
    ]


class _SyntheticRetriever:
    """Returns the evidence set queued for the next call."""

    def __init__(self):
        self.next: list[RetrievalResult] = []

    def retrieve(self, question, k=5):
        return self.next


# (scenario, company, fiscal_year, evidence_variant, question_key)
SCENARIOS = [
    ("1_repeated_query", "ACME", 2022, 0, "q1"),
    ("1_repeated_query", "ACME", 2022, 0, "q1"),
    ("1_repeated_query", "ACME", 2022, 0, "q1"),
    ("2_same_evidence_new_question", "ACME", 2022, 0, "q2"),
    ("2_same_evidence_new_question", "ACME", 2022, 0, "q3"),
    ("2_same_evidence_new_question", "ACME", 2022, 0, "q4"),
    ("3_different_company", "GLOBEX", 2022, 0, "q1"),
    ("3_different_company", "INITECH", 2022, 0, "q1"),
    ("4_different_fiscal_period", "ACME", 2021, 0, "q1"),
    ("4_different_fiscal_period", "ACME", 2023, 0, "q1"),
    ("5_new_retrieved_context", "ACME", 2022, 1, "q1"),
    ("5_new_retrieved_context", "ACME", 2022, 2, "q1"),
]


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, round(p / 100 * (len(s) - 1)))]


def _build_provider(args, enabled: bool):
    config = PromptCacheConfig(enabled=enabled)
    metrics = PromptCacheMetrics()
    if args.provider == "ollama":
        from src.generation.ollama_provider import OllamaProvider
        return OllamaProvider(args.model, config, metrics)
    from src.generation.openrouter import OpenRouterProvider
    return OpenRouterProvider(args.model, config, metrics)


def run_mode(args, enabled: bool) -> list[dict]:
    salt = f"{time.time_ns()}|{'on' if enabled else 'off'}"
    retriever = _SyntheticRetriever()
    provider = _build_provider(args, enabled)
    generator = MinimalGenerator(retriever, provider, cache_friendly_prompt=enabled)
    rows = []
    for scenario, company, fy, variant, qkey in SCENARIOS:
        retriever.next = _results(company, fy, salt, variant)
        t0 = time.perf_counter()
        _result, resp, _ = generator._answer_with_diagnostics(_Q[qkey])
        wall_ms = (time.perf_counter() - t0) * 1000
        assert isinstance(resp, ProviderResponse), "benchmark evidence must pass the guards"
        rows.append({
            "scenario": scenario, "company": company, "fiscal_year": fy, "evidence_variant": variant,
            "question": qkey, "cache_strategy": resp.cache_strategy,
            "input_tokens": resp.prompt_tokens, "output_tokens": resp.completion_tokens,
            "cached_input_tokens": resp.cached_prompt_tokens, "cache_write_tokens": resp.cache_write_tokens,
            "provider_latency_ms": round(resp.latency_ms, 1), "end_to_end_ms": round(wall_ms, 1),
            "prompt_eval_ms": None if resp.prompt_eval_ms is None else round(resp.prompt_eval_ms, 1),
            "cost_usd": resp.cost_usd,
        })
        print(f"  [{'on ' if enabled else 'off'}] {scenario:30s} {company:8s} {fy} {qkey} "
              f"in={resp.prompt_tokens} lat={resp.latency_ms:8.0f}ms prompt_eval={resp.prompt_eval_ms}", flush=True)
    return rows


def _summ(rows: list[dict], key: str) -> dict:
    vals = [r[key] for r in rows if isinstance(r[key], (int, float))]
    return {"n": len(vals), "mean": statistics.fmean(vals) if vals else None,
            "p50": _pct(vals, 50), "p95": _pct(vals, 95), "sum": sum(vals) if vals else None}


def summarize(rows: list[dict]) -> dict:
    by_scn: dict[str, list[dict]] = {}
    for r in rows:
        by_scn.setdefault(r["scenario"], []).append(r)
    return {
        "input_tokens": _summ(rows, "input_tokens"),
        "cached_input_tokens": _summ(rows, "cached_input_tokens"),
        "provider_latency_ms": _summ(rows, "provider_latency_ms"),
        "prompt_eval_ms": _summ(rows, "prompt_eval_ms"),
        "cost_usd": _summ(rows, "cost_usd"),
        "by_scenario": {s: {"provider_latency_ms": _summ(v, "provider_latency_ms"),
                            "prompt_eval_ms": _summ(v, "prompt_eval_ms")} for s, v in by_scn.items()},
    }


def _fmt(v, digits=0):
    return "unavailable" if v is None else f"{v:,.{digits}f}"


def _diff(a, b, digits=0, pct=True):
    if a is None or b is None:
        return "unavailable"
    d = b - a
    if pct and a:
        return f"{d:+,.{digits}f} ({d / a * 100:+.1f}%)"
    return f"{d:+,.{digits}f}"


def markdown(off: dict, on: dict) -> str:
    rows = [
        ("Input tokens / request (mean)", "input_tokens", "mean", 0),
        ("Cached input tokens (sum)", "cached_input_tokens", "sum", 0),
        ("P50 latency, ms", "provider_latency_ms", "p50", 0),
        ("P95 latency, ms", "provider_latency_ms", "p95", 0),
        ("P50 prompt-eval time, ms (Ollama)", "prompt_eval_ms", "p50", 0),
        ("P95 prompt-eval time, ms (Ollama)", "prompt_eval_ms", "p95", 0),
        ("Cost per query, USD", "cost_usd", "mean", 6),
    ]
    lines = ["| Metric | No caching | Caching enabled | Difference |", "|---|---|---|---|"]
    for label, key, stat, digits in rows:
        a, b = off[key][stat], on[key][stat]
        lines.append(f"| {label} | {_fmt(a, digits)} | {_fmt(b, digits)} | {_diff(a, b, digits)} |")
    lines.append("| First-token latency | unavailable (non-streaming) | unavailable (non-streaming) | unavailable |")
    lines += ["", "Per scenario (mean provider latency / mean prompt-eval ms):", "",
              "| Scenario | No caching | Caching enabled |", "|---|---|---|"]
    for s in off["by_scenario"]:
        def cell(summary):
            d = summary["by_scenario"][s]
            return f"{_fmt(d['provider_latency_ms']['mean'])} ms / {_fmt(d['prompt_eval_ms']['mean'])} ms"
        lines.append(f"| {s} | {cell(off)} | {cell(on)} |")
    lines.append("| 6_multi_turn_conversation | not applicable (no conversation state in /query) | not applicable |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=["ollama", "openrouter"], default="ollama")
    ap.add_argument("--model", default="gpt-oss:20b")
    ap.add_argument("--allow-paid", action="store_true", help="required for --provider openrouter (real, billed calls)")
    ap.add_argument("--num-predict", type=int, default=64, help="Ollama output cap applied by this harness only; 0 = uncapped")
    ap.add_argument("--repeats", type=int, default=3,
                    help="independent runs per mode (fresh salt each); percentiles pool all runs, so one outlier run is visible")
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args()

    if args.provider == "openrouter" and not args.allow_paid:
        print("Refusing: OpenRouter calls are billed. Re-run with --allow-paid to authorize.", file=sys.stderr)
        return 2

    if args.provider == "ollama" and args.num_predict:
        import src.generation.ollama_provider as op
        real_post = op.requests.post

        def capped_post(url, json=None, timeout=None):
            json = dict(json, options={**json["options"], "num_predict": args.num_predict})
            return real_post(url, json=json, timeout=timeout)

        op.requests.post = capped_post

    print(f"provider={args.provider} model={args.model} requests/mode/repeat={len(SCENARIOS)}")
    # Warm-up (model load + weights) so load time never lands on a measured request.
    warm = _build_provider(args, False)
    from src.generation.provider import GenerationRequest
    warm.generate(GenerationRequest(system_prompt="Reply OK.", user_prompt="warm-up " + str(time.time_ns())))

    off_rows, on_rows = [], []
    for rep in range(args.repeats):
        print(f"--- repeat {rep + 1}/{args.repeats}")
        off_rows += [dict(r, repeat=rep) for r in run_mode(args, enabled=False)]
        on_rows += [dict(r, repeat=rep) for r in run_mode(args, enabled=True)]
    off_s, on_s = summarize(off_rows), summarize(on_rows)
    table = markdown(off_s, on_s)
    print("\n" + table)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "provider": args.provider, "model": args.model, "num_predict_cap": args.num_predict or None, "repeats": args.repeats,
        "evidence": "synthetic, deterministic, 5 x ~512-token chunks per request, per-run salt",
        "no_caching": {"rows": off_rows, "summary": off_s}, "caching_enabled": {"rows": on_rows, "summary": on_s},
        "markdown": table,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
