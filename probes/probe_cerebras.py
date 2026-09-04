"""Cerebras GPT-OSS-120B live probe (2026-09-04). See probes/README.md.

Transport note: the first attempt used raw urllib and was blocked at the
Cloudflare edge (HTTP 403, `error code: 1010`, Server: cloudflare — a
browser-signature ban, NOT an API/auth response; no quota consumed).
Evidence: agent-memory/evidence/cerebras-probe-2026-09-04-urllib-blocked.json.
This version therefore uses the SAME transport as the application itself:
the `openai` SDK (httpx) that `strands.models.openai.OpenAIModel` uses —
which also makes this probe a faithful preview of the production path.

Call budget by design: <=4 sequential requests —
  1. models.list            (auth + catalog; metadata-only)
  2. tiny chat completion   (auth, usage reporting, headers, latency)
  3. tool-call round        (function calling)
  4. tool-result replay     (multi-turn semantics)
No retries of our own (SDK max_retries set to 0 so terminal statuses are
seen exactly once). STOPS at the first terminal failure (401/402/403/429).
The synthetic tool is read-only; nothing from the benchmark or app is used.

Docs-verified parameter notes (2026-09-04):
- `max_completion_tokens` is canonical; `max_tokens` is an alias and the
  two must never be sent together.
- gpt-oss-120b always reasons; reasoning tokens count toward completion
  tokens (usage.completion_tokens_details.reasoning_tokens).
- tools + response_format are mutually exclusive on this model — never
  combined here.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import openai

from probe_common import DEFAULT_ENV_FILE, Evidence, load_credentials, make_redactor

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "get_balance",
        "description": "Return the settled balance of a ledger account.",
        "parameters": {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
    },
}

TOOL_RESULT_JSON = json.dumps(
    {"account_id": "ACC-1", "balance": 1000.25, "currency": "USD"}
)

TERMINAL = {401, 402, 403, 429}


def _filtered_headers(headers) -> dict:
    keep = ("x-", "retry-after", "date", "content-type")
    return {k: v for k, v in dict(headers).items() if k.lower().startswith(keep)}


def _call(ev: dict, label: str, fn) -> tuple[dict, object | None]:
    """Run one SDK call with full capture (status/headers/body/latency)."""
    start = time.perf_counter()
    record: dict = {"label": label, "status": None, "headers": {}, "body": None,
                    "elapsed_ms": None, "error": None}
    parsed = None
    try:
        raw = fn()
        record["status"] = raw.status_code
        record["headers"] = _filtered_headers(raw.headers)
        parsed = raw.parse()
        record["body"] = parsed.model_dump_json(indent=2) if hasattr(parsed, "model_dump_json") else str(parsed)
    except openai.APIStatusError as exc:
        record["status"] = exc.status_code
        record["headers"] = _filtered_headers(exc.response.headers)
        record["body"] = exc.response.text[:4000]
        record["error"] = f"APIStatusError: {exc.message}"
    except openai.APIError as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 — capture everything, never retry
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 1)
    ev.add(label, record)
    return record, parsed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    ap.add_argument("--base-url", default="https://api.cerebras.ai/v1")
    ap.add_argument("--model", default="gpt-oss-120b")
    ap.add_argument(
        "--evidence-stem",
        default="~/projects/reconciliation-investigator/agent-memory/evidence/cerebras-probe-2026-09-04",
    )
    args = ap.parse_args()

    creds = load_credentials(Path(args.env_file), ["CEREBRAS_API_KEY"])
    redact = make_redactor(creds)
    client = openai.OpenAI(  # transport identical to the app's OpenAIModel path
        base_url=args.base_url, api_key=creds["CEREBRAS_API_KEY"], max_retries=0
    )
    ev = Evidence(Path(args.evidence_stem), redact)
    summary = [f"CEREBRAS PROBE (openai-sdk transport) model={args.model} base={args.base_url}"]

    raw_client = client.with_raw_response

    # -- Step 1: models.list (auth check; metadata-only, no inference quota) --
    rec, models = _call(ev, "models_list", lambda: raw_client.models.list())
    ids = sorted(m.id for m in models.data) if models is not None else []
    summary.append(
        f"[1] models.list -> HTTP {rec['status']} ({rec['elapsed_ms']} ms); "
        f"catalog={len(ids)} models; gpt-oss ids={[i for i in ids if 'gpt-oss' in i]}"
    )
    if rec["status"] in TERMINAL or rec["status"] is None:
        summary.append(f"[1] TERMINAL ({rec['status']} {rec.get('error', '')}) — stopping, no further calls.")
        ev.dump(summary)
        return

    # -- Step 2: tiny completion --
    body2 = {
        "model": args.model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_completion_tokens": 512,
        "stream": False,
    }
    rec2, comp2 = _call(ev, "completion_tiny", lambda: raw_client.chat.completions.create(**body2))
    if comp2 is not None:
        msg2 = comp2.choices[0].message
        usage2 = comp2.usage.model_dump() if comp2.usage else {}
        summary.append(f"[2] completion -> HTTP {rec2['status']} ({rec2['elapsed_ms']} ms); finish={comp2.choices[0].finish_reason}")
        summary.append(f"[2] content={json.dumps(msg2.content)!s:.120}")
        summary.append(f"[2] usage={json.dumps(usage2, sort_keys=True)}")
    else:
        summary.append(f"[2] completion -> HTTP {rec2['status']} ({rec2['elapsed_ms']} ms); error={rec2.get('error')}")
        summary.append(f"[2] body={str(rec2.get('body'))!s:.300}")
    if rec2["status"] in TERMINAL or rec2["status"] is None:
        summary.append(f"[2] TERMINAL ({rec2['status']}) — stopping before tool rounds.")
        ev.dump(summary)
        return

    # -- Step 3: function-calling round --
    msgs3 = [
        {"role": "system", "content": "You are a compatibility probe. Use tools when asked."},
        {"role": "user", "content": "What is the settled balance of account ACC-1? Use the get_balance tool."},
    ]
    body3 = {
        "model": args.model, "messages": msgs3, "tools": [TOOL_DEF],
        "tool_choice": "auto", "max_completion_tokens": 1024, "stream": False,
    }
    rec3, comp3 = _call(ev, "tool_call_round", lambda: raw_client.chat.completions.create(**body3))
    tool_calls = []
    if comp3 is not None:
        msg3 = comp3.choices[0].message
        tool_calls = list(msg3.tool_calls or [])
        usage3 = comp3.usage.model_dump() if comp3.usage else {}
        summary.append(f"[3] tool round -> HTTP {rec3['status']} ({rec3['elapsed_ms']} ms); tool_calls={len(tool_calls)}")
        for tc in tool_calls:
            summary.append(f"[3]   call {tc.id} {tc.function.name} args={tc.function.arguments}")
        summary.append(f"[3] usage={json.dumps(usage3, sort_keys=True)}")
    else:
        summary.append(f"[3] tool round -> HTTP {rec3['status']} ({rec3['elapsed_ms']} ms); error={rec3.get('error')}")
        summary.append(f"[3] body={str(rec3.get('body'))!s:.300}")
    if rec3["status"] in TERMINAL or not tool_calls:
        summary.append("[3] no tool call returned (or terminal status) — skipping replay.")
        ev.dump(summary)
        return

    # -- Step 4: tool-result replay (preserve tool_calls verbatim) --
    msg3 = comp3.choices[0].message
    assistant_msg = {
        "role": "assistant",
        "content": msg3.content,
        "tool_calls": [
            {
                "id": tc.id, "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in tool_calls
        ],
    }
    tool_msg = {"role": "tool", "tool_call_id": tool_calls[0].id, "content": TOOL_RESULT_JSON}
    body4 = {
        "model": args.model, "messages": msgs3 + [assistant_msg, tool_msg],
        "tools": [TOOL_DEF], "tool_choice": "auto",
        "max_completion_tokens": 1024, "stream": False,
    }
    rec4, comp4 = _call(ev, "tool_result_replay", lambda: raw_client.chat.completions.create(**body4))
    if comp4 is not None:
        usage4 = comp4.usage.model_dump() if comp4.usage else {}
        summary.append(f"[4] replay -> HTTP {rec4['status']} ({rec4['elapsed_ms']} ms)")
        summary.append(f"[4] content={json.dumps(comp4.choices[0].message.content)!s:.200}")
        summary.append(f"[4] usage={json.dumps(usage4, sort_keys=True)}")
    else:
        summary.append(f"[4] replay -> HTTP {rec4['status']} ({rec4['elapsed_ms']} ms); error={rec4.get('error')}")
        summary.append(f"[4] body={str(rec4.get('body'))!s:.300}")

    ev.dump(summary)


if __name__ == "__main__":
    main()
