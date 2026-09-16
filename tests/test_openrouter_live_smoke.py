"""generation_api-marked: a real OpenRouter chat-completion call.

Tightened 2026-09-16 (Task 4.7 incident - see
project_plan/PHASE4_INPUT_GUARDRAILS.md's "Unintended live API calls"
section): merely having OPENROUTER_API_KEY/GENERATION_MODEL configured in
`.env` is no longer sufficient to run this test for real. `python-dotenv`
populates `os.environ` from `.env` as a side effect of importing
`src.config` anywhere in a test run (even indirectly, via an unrelated
test module) - so a developer's routine `.env` for local generation work
was silently enough to trigger a real, live, credentialed network call
every time the full (non-`--portable`) suite ran, with no explicit intent
expressed at that moment. This is now gated behind a SEPARATE, explicit
opt-in environment variable that a `.env` file would never set on its own
(`.env` is for durable local configuration, not "run live tests now").

Requires ALL THREE of: `RUN_LIVE_GENERATION_API_TEST=1` (explicit,
same-invocation intent - never sourced from a committed file),
`OPENROUTER_API_KEY`, and `GENERATION_MODEL`. Skips cleanly (never fails)
if any is absent - never invents a model choice, never runs merely
because credentials happen to exist. Fails (not skips) if the opt-in
flag and both credentials are present but the call itself is broken.
Never downloads anything. Never prints/logs the API key. Not part of the
routine portable/full test expectations - always a real network call,
and now always a deliberate one.

To run for real:

    RUN_LIVE_GENERATION_API_TEST=1 pytest -m generation_api
"""

import os

import pytest

from src.generation.openrouter import OpenRouterProvider, API_KEY_ENV_VAR
from src.generation.provider import GenerationRequest

LIVE_OPT_IN_ENV_VAR = "RUN_LIVE_GENERATION_API_TEST"


@pytest.mark.generation_api
def test_real_openrouter_call_succeeds():
    opted_in = os.environ.get(LIVE_OPT_IN_ENV_VAR, "").strip() == "1"
    api_key = os.environ.get(API_KEY_ENV_VAR, "").strip()
    model = os.environ.get("GENERATION_MODEL", "").strip()

    if not opted_in:
        pytest.skip(
            f"{LIVE_OPT_IN_ENV_VAR}=1 not set - this test makes a real, "
            f"credentialed OpenRouter call and requires explicit same-invocation "
            f"opt-in, never just a configured API key (see this file's docstring)"
        )
    if not api_key:
        pytest.skip(f"{API_KEY_ENV_VAR} not set in environment")
    if not model:
        pytest.skip("GENERATION_MODEL not set in environment")

    provider = OpenRouterProvider(model=model)
    response = provider.generate(GenerationRequest(
        system_prompt="Answer in exactly one short sentence.",
        user_prompt="What is 2 + 2?",
        temperature=0.0,
    ))

    assert response.text
    assert response.requested_model == model
    assert response.latency_ms > 0
