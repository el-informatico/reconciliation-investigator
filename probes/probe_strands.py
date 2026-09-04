"""Strands-abstraction compatibility probes (2026-09-04). See probes/README.md.

Runs the application's EXACT model-construction idiom (agents/model.py:71-75,
`OpenAIModel(client_args={base_url, api_key}, model_id=..., params=...)`)
against the candidate providers, with one synthetic read-only tool, through a
real Strands Agent loop: user -> model tool call -> tool execution ->
message replay -> final answer. That replay is the exact transport surface
the Groq replay probe validated (agent-memory/evidence/groq-replay-probe)
and the #1 correctness risk for any provider swap.

No app modules are imported; no benchmark code; no write tools; no retries
of our own (SDK defaults stay ON deliberately — they are part of the real
transport path being probed).

Providers:
  cerebras      OpenAIModel -> https://api.cerebras.ai/v1          (gpt-oss-120b)
  gemini-compat OpenAIModel -> .../v1beta/openai/  (Gemini OpenAI-compat layer)
  gemini-native GeminiModel (strands.models.gemini; needs google-genai:
                             run via `uv run --with google-genai ...`)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from probe_common import DEFAULT_ENV_FILE, load_credentials, make_redactor

QUESTION = "What is the settled balance of account ACC-1? Use the get_balance tool, then answer in one short sentence."
SYSTEM_PROMPT = (
    "You are a compatibility probe agent. When asked for a balance, call "
    "get_balance, then answer in one short sentence."
)


def _print_usage(agent, name: str) -> None:
    try:
        metrics = getattr(agent, "metrics", None)
        usage = getattr(metrics, "accumulated_usage", None)
        if usage is None:
            print(f"[{name}] usage: not exposed on agent.metrics")
            return
        if isinstance(usage, dict):
            picked = {k: usage.get(k) for k in ("inputTokens", "outputTokens", "totalTokens")}
        else:
            picked = {k: getattr(usage, k, None) for k in ("inputTokens", "outputTokens", "totalTokens")}
        print(f"[{name}] usage: {json.dumps(picked, sort_keys=True, default=str)}")
    except Exception as exc:  # noqa: BLE001 — usage reporting is best-effort
        print(f"[{name}] usage: not available ({type(exc).__name__}: {exc})")


def _run_agent(name: str, model, redact) -> bool:
    from strands import Agent, tool

    @tool
    def get_balance(account_id: str) -> str:
        """Return the settled balance of a ledger account."""
        return json.dumps({"account_id": account_id, "balance": 1000.25, "currency": "USD"})

    agent = Agent(
        model=model,
        tools=[get_balance],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )
    start = time.perf_counter()
    result = agent(QUESTION)
    elapsed = round((time.perf_counter() - start) * 1000, 1)
    text = redact(str(result).strip())
    ok = "1000.25" in text
    print(f"[{name}] wall_ms={elapsed} tool_answered={'YES' if ok else 'NO'}")
    print(f"[{name}] final: {text[:300]}")
    _print_usage(agent, name)
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=["cerebras", "gemini-compat", "gemini-native"])
    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    args = ap.parse_args()

    if args.provider == "cerebras":
        creds = load_credentials(Path(args.env_file), ["CEREBRAS_API_KEY"])
        redact = make_redactor(creds)
        from strands.models.openai import OpenAIModel

        model = OpenAIModel(
            client_args={"base_url": "https://api.cerebras.ai/v1", "api_key": creds["CEREBRAS_API_KEY"]},
            model_id="gpt-oss-120b",
            params={"max_tokens": 1024},  # app idiom: params dict (max_completion_tokens alias accepted per docs)
        )
        ok = _run_agent("cerebras", model, redact)
    elif args.provider == "gemini-compat":
        creds = load_credentials(Path(args.env_file), ["GEMINI_API_KEY"])
        redact = make_redactor(creds)
        from strands.models.openai import OpenAIModel

        model = OpenAIModel(
            client_args={
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "api_key": creds["GEMINI_API_KEY"],
            },
            model_id="gemini-3.1-flash-lite",
            params={"max_tokens": 1024},
        )
        ok = _run_agent("gemini-compat", model, redact)
    else:  # gemini-native
        try:
            from strands.models.gemini import GeminiModel
        except ImportError as exc:
            print(f"[gemini-native] SKIP — strands.models.gemini unavailable: {exc}")
            print("                run via: uv run --with google-genai python probes/probe_strands.py --provider gemini-native")
            return
        creds = load_credentials(Path(args.env_file), ["GEMINI_API_KEY"])
        redact = make_redactor(creds)
        model = GeminiModel(
            client_args={"api_key": creds["GEMINI_API_KEY"]},
            model_id="gemini-3.1-flash-lite",
            params={"max_output_tokens": 1024},
        )
        ok = _run_agent("gemini-native", model, redact)

    print(f"RESULT[{args.provider}]: {'OK' if ok else 'INCOMPLETE'}")


if __name__ == "__main__":
    main()
