"""Gemini judge canary — ONE case, judges on Gemini 3.1 Flash-Lite (native).

EXPERIMENT DECLARATION — this is a CONTROLLED METHODOLOGICAL CHANGE to the
measurement instrument, declared up front (2026-09-04 task contract):

    Judge model/provider:  Groq openai/gpt-oss-120b  ->  gemini-3.1-flash-lite
                           (native Strands GeminiModel via google-genai)
    Agents:                UNCHANGED — GPT-OSS-120B / Groq (existing wiring)
    Everything else:       UNCHANGED — prompts, rubrics, cases, tools,
                           evaluator invocation counts, scoring thresholds.

Results from this configuration are NOT comparable 1:1 with all-Groq runs:
the judge model (and its tokenizer) changed. The split must be disclosed
in the benchmark methodology if adopted (restating the standing condition
from docs/token-workload-audit-2026-09-04.md §8 and the feasibility docs).

Design facts this builds on (verified against installed source + the
probe suite, 2026-09-04):
- Native path REQUIRED: the OpenAI-compatible Gemini endpoint drops
  Gemini 3.x function-call thoughtSignature -> hard 400 on replay
  (probes/probe_gemini.py; docs/provider-feasibility-cerebras-gemini.md
  §4.3-4.4). strands' GeminiModel preserves and replays signatures
  (strands/models/gemini.py capture/replay paths).
- google-genai is NOT a project dependency; the sanctioned zero-repo-change
  mechanism is the probes' ephemeral overlay (probes/README.md):
    uv run --frozen --with google-genai==2.22.0 \
        python -m evals.gemini_judge_canary --case reversal-not-propagated
  (2.22.0 = the version the probe suite validated against strands 1.54.0.)
- Credential: GEMINI_API_KEY from the environment or the repo-root .env
  via the app's own loader (agents.model._load_repo_dotenv — environment
  wins, value never printed). No sibling-project credential is read. If
  absent, this driver STOPS before any request (exit code 3).
- Usage capture: identical strands-normalized metadata chunk shape as the
  Groq path (gemini.py format_chunk "metadata": inputTokens = prompt +
  tool_use_prompt; outputTokens = candidates + thoughts; totalTokens).
- Pacing: Gemini free tier observed at ~15 RPM (dashboard) -> this driver
  paces judge requests at GEMINI_MIN_INTERVAL_S (default 4.3 s, <=14 RPM)
  per the feasibility mandate. Timing only; no semantic change. Agents
  stay unpaced on Groq (9 requests over minutes is far under limits).
- Known risks carried into the run, not worked around: 5xx ServerError is
  not mapped to a retryable exception by strands (gemini.py catches only
  ClientError); forced structured output retries exactly once before
  StructuredOutputException. Either failure would be recorded as evidence.
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

from agents.model import _load_repo_dotenv
from evals.token_canary import (
    UsageRecordingModel,
    UsageRecorder,
    run_one_case,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
GEMINI_MODEL_ID = "gemini-3.1-flash-lite"  # verbatim probe-validated id
GEMINI_PROVIDER = "google"
JUDGE_MAX_OUTPUT_TOKENS = 8192  # mirrors the Groq judge capacity decision
                                # (evals/run_evals.py judge max_tokens=8192)
DEFAULT_OUT_DIR = (
    REPO_ROOT / "agent-memory" / "evidence" / "gemini-judge-canary-2026-09-04"
)

# Feasibility-mandated pacer: >= 60/14 s between judge request starts.
# Interval from GEMINI_MIN_INTERVAL_S (env) with the 4.3 s default; clamped
# to [0, 3600] so a bad value (empty/negative/inf/nan) can neither disable
# pacing silently nor hang a judge forever. Read dynamically by _pace_wait
# so tests can shrink it via monkeypatching.
import math as _math

try:
    _raw_interval = float(os.environ.get("GEMINI_MIN_INTERVAL_S", "4.3"))
    if not _math.isfinite(_raw_interval):
        raise ValueError
    MIN_INTERVAL_S = min(max(_raw_interval, 0.0), 3600.0)
except ValueError:
    MIN_INTERVAL_S = 4.3

_last_request_start = 0.0


def _pace_wait() -> float:
    """Seconds to sleep before the next paced request (slot-reserving)."""
    global _last_request_start
    now = time.monotonic()
    wait = max(0.0, MIN_INTERVAL_S - (now - _last_request_start))
    _last_request_start = max(_last_request_start, now + wait)
    return wait


class PacedUsageRecordingModel(UsageRecordingModel):
    """UsageRecordingModel that sleeps the pacer interval before each
    request. Pass-through in every other respect — the delay is timing
    only and changes no request bytes, prompts, or semantics."""

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        wait = _pace_wait()
        if wait > 0:
            await asyncio.sleep(wait)
        async for chunk in super().stream(*args, **kwargs):
            yield chunk


def resolve_gemini_api_key(*, _loader=None) -> str | None:
    """GEMINI_API_KEY via the app's existing authorized mechanism only:
    the environment, or the repo-root .env loaded by the app's own loader
    (environment wins). The value is never printed or logged. Returns None
    when unavailable — callers must STOP, not search elsewhere."""
    loader = _loader if _loader is not None else _load_repo_dotenv
    try:
        loader()
    except Exception as exc:  # a broken .env must not crash the gate
        print(f"[gemini-canary] dotenv loader problem (ignored): {type(exc).__name__}", flush=True)
    return os.environ.get("GEMINI_API_KEY") or None


def make_gemini_judge_model(api_key: str):
    """The native Strands Gemini model, constructed exactly as the probe
    suite validated (probes/probe_strands.py): the API key MUST travel in
    client_args — a top-level kwarg would be silently ignored (config
    validation only warns). Lazy import so this module (and its tests)
    load without google-genai installed."""
    from strands.models.gemini import GeminiModel

    return GeminiModel(
        client_args={"api_key": api_key},
        model_id=GEMINI_MODEL_ID,
        params={"max_output_tokens": JUDGE_MAX_OUTPUT_TOKENS},
    )


def swap_judge_models_gemini(run_evals_module: Any, recorder: UsageRecorder, api_key: str) -> None:
    """Swap .model on the four LLM-judge singletons for paced, tagged
    wrappers around ONE shared native Gemini model — mirroring the shared
    judge_model pattern of the unmodified harness (evals/run_evals.py)."""
    shared = make_gemini_judge_model(api_key)
    targets = [
        ("trajectory_evaluator", "judge.trajectory"),
        ("output_evaluator", "judge.output"),
        ("tool_selection_evaluator", "judge.tool_selection"),
        ("tool_parameter_evaluator", "judge.tool_parameter"),
    ]
    for attr, component in targets:
        evaluator = getattr(run_evals_module, attr)
        evaluator.model = PacedUsageRecordingModel(
            shared,
            component=component,
            component_type="judge",
            recorder=recorder,
            model_id=GEMINI_MODEL_ID,
            provider=GEMINI_PROVIDER,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ONE-case Gemini-judge canary")
    parser.add_argument(
        "--case",
        default="reversal-not-propagated",
        help="case name from evals/cases.py (default: %(default)s)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="evidence directory (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    api_key = resolve_gemini_api_key()
    if not api_key:
        print(
            "[gemini-canary] BLOCKED: GEMINI_API_KEY is not available through the "
            "application's authorized configuration (environment or repo-root .env "
            "via the app's own loader). Per the task contract this experiment "
            "STOPS here: no sibling-project credential is read or copied.\n"
            "[gemini-canary] unblock step (human): provision GEMINI_API_KEY into "
            "this repo's .env (or export it in the run environment), then re-run "
            "the same single-case command. Nothing else changes.",
            flush=True,
        )
        return 3

    try:
        import strands.models.gemini  # noqa: F401 — availability pre-flight
    except ModuleNotFoundError:
        print(
            "[gemini-canary] BLOCKED: google-genai is not installed in this "
            "environment. Run via the probes' ephemeral overlay (zero repo "
            "changes), e.g.:\n"
            "  uv run --frozen --with google-genai==2.22.0 \\\n"
            "      python -m evals.gemini_judge_canary --case reversal-not-propagated",
            flush=True,
        )
        return 4

    def judge_swap(run_evals_module: Any, recorder: UsageRecorder) -> None:
        swap_judge_models_gemini(run_evals_module, recorder, api_key)

    print(
        f"[gemini-canary] judges -> {GEMINI_PROVIDER}/{GEMINI_MODEL_ID} (native); "
        f"agents unchanged on groq; pacer {MIN_INTERVAL_S}s",
        flush=True,
    )
    return run_one_case(
        args.case,
        args.out_dir,
        judge_swap=judge_swap,
        log_prefix="[gemini-canary]",
    )


if __name__ == "__main__":
    sys.exit(main())
