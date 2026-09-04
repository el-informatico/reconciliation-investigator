"""Groq two-key live probe (2026-09-04). See probes/README.md.

Re-validates each sibling project's Groq environment INDEPENDENTLY
(treat the two GROQ_API_KEY values as unrelated organizations until
response metadata says otherwise — key values are never compared):

  --env-file ~/projects/[SIBLING-A]/.env  --env-tag [SIBLING-A]
  --env-file ~/projects/[SIBLING-B]/.env     --env-tag gateway

Phases and per-environment call budget (<=4 requests total):
  1. models.list                      (auth + openai/gpt-oss-120b presence; sanitized boolean)
  2. tiny completion                  (inference permission, usage, latency)
  3. tool-call round + tool replay    (2 requests; the mechanism the eval needs)
No retries of our own (SDK max_retries=0 so terminal statuses are seen exactly
once). STOPS at the first terminal failure (401/402/403/429 — for 429 we capture
the sanitized rate-limit metadata and stop, per instructions).

Rate-limit evidence: every response's `x-ratelimit-*` / `retry-after` headers
are captured verbatim (numeric metadata, non-secret) — on success AND on error.
Request headers are never recorded (they carry the credential).

Transport = the `openai` SDK over https://api.groq.com/openai/v1 — the same
client path the application's strands OpenAIModel uses. gpt-oss replay nuance:
the assistant message is replayed with content + tool_calls only (no reasoning
field), mirroring how strands strips `reasoningContent` on replay (see
agent-memory/evidence/groq-replay-probe-2026-09-04.txt for the strands-level
validation of exactly this on 2026-09-04).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import openai

from probe_common import DEFAULT_ENV_FILE, Evidence, load_credentials, make_redactor

MODEL = "openai/gpt-oss-120b"
BASE_URL = "https://api.groq.com/openai/v1"

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


def _ratelimit_headers(headers) -> dict:
    keep = ("x-ratelimit-", "retry-after")
    return {k: v for k, v in dict(headers).items() if k.lower().startswith(keep)}


def _call(ev: Evidence, label: str, fn) -> tuple[dict, object | None]:
    start = time.perf_counter()
    record: dict = {"label": label, "status": None, "ratelimit_headers": {},
                    "body": None, "elapsed_ms": None, "error": None}
    parsed = None
    try:
        raw = fn()
        record["status"] = raw.status_code
        record["ratelimit_headers"] = _ratelimit_headers(raw.headers)
        parsed = raw.parse()
        record["body"] = parsed.model_dump_json(indent=2) if hasattr(parsed, "model_dump_json") else str(parsed)
    except openai.APIStatusError as exc:
        record["status"] = exc.status_code
        record["ratelimit_headers"] = _ratelimit_headers(exc.response.headers)
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
    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE),
                    help="sibling .env to read GROQ_API_KEY from (by name only)")
    ap.add_argument("--env-tag", required=True,
                    choices=["[SIBLING-A]", "gateway"],
                    help="label for evidence files and summaries")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument(
        "--evidence-stem",
        default=None,
        help="default: agent-memory/evidence/groq-probe-<env-tag>-2026-09-04",
    )
    args = ap.parse_args()
    stem = args.evidence_stem or str(
        Path("~/projects/reconciliation-investigator/agent-memory/evidence")
        / f"groq-probe-{args.env_tag}-2026-09-04"
    )

    creds = load_credentials(Path(args.env_file), ["GROQ_API_KEY"])
    redact = make_redactor(creds)
    client = openai.OpenAI(base_url=args.base_url, api_key=creds["GROQ_API_KEY"], max_retries=0)
    raw_client = client.with_raw_response
    ev = Evidence(Path(stem), redact)
    summary = [f"GROQ PROBE env={args.env_tag} env_file={args.env_file} model={args.model} (openai-sdk transport)"]

    # -- Phase 1: auth + model availability (sanitized boolean only) --
    rec, models = _call(ev, "models_list", lambda: raw_client.models.list())
    ids = [m.id for m in models.data] if models is not None else []
    present = args.model in ids
    summary.append(
        f"[P1] models.list -> HTTP {rec['status']} ({rec['elapsed_ms']} ms); "
        f"catalog_size={len(ids)}; {args.model!r} present: {present}"
    )
    summary.append(f"[P1] rate-limit headers on models.list: {json.dumps(rec['ratelimit_headers'], sort_keys=True)}")
    if rec["status"] in TERMINAL or rec["status"] is None:
        summary.append(f"[P1] TERMINAL ({rec['status']} {rec.get('error', '')}) — stopping this environment.")
        ev.dump(summary)
        return
    if not present:
        summary.append(f"[P1] {args.model!r} NOT in catalog — stopping this environment (no inference probe).")
        ev.dump(summary)
        return

    # -- Phase 2: minimal inference --
    body2 = {
        "model": args.model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 512,
        "stream": False,
    }
    rec2, comp2 = _call(ev, "completion_tiny", lambda: raw_client.chat.completions.create(**body2))
    if comp2 is not None:
        usage2 = comp2.usage.model_dump() if comp2.usage else {}
        summary.append(f"[P2] completion -> HTTP {rec2['status']} ({rec2['elapsed_ms']} ms); finish={comp2.choices[0].finish_reason}")
        summary.append(f"[P2] content={json.dumps(comp2.choices[0].message.content)!s:.80}")
        summary.append(f"[P2] usage={json.dumps(usage2, sort_keys=True)}")
    else:
        summary.append(f"[P2] completion -> HTTP {rec2['status']} ({rec2['elapsed_ms']} ms); error={rec2.get('error')}")
        summary.append(f"[P2] body={str(rec2.get('body'))!s:.400}")
    summary.append(f"[P2] rate-limit headers: {json.dumps(rec2['ratelimit_headers'], sort_keys=True)}")
    if rec2["status"] == 429:
        summary.append("[P2] 429 — capturing sanitized rate-limit metadata and STOPPING this environment (per instructions).")
        ev.dump(summary)
        return
    if rec2["status"] in TERMINAL or rec2["status"] is None:
        summary.append(f"[P2] TERMINAL ({rec2['status']}) — stopping before tool rounds.")
        ev.dump(summary)
        return

    # -- Phase 3: tool call + replay (2 requests) --
    msgs3 = [
        {"role": "system", "content": "You are a compatibility probe. Use tools when asked."},
        {"role": "user", "content": "What is the settled balance of account ACC-1? Use the get_balance tool."},
    ]
    body3 = {
        "model": args.model, "messages": msgs3, "tools": [TOOL_DEF],
        "tool_choice": "auto", "max_tokens": 1024, "stream": False,
    }
    rec3, comp3 = _call(ev, "tool_call_round", lambda: raw_client.chat.completions.create(**body3))
    tool_calls = []
    if comp3 is not None:
        msg3 = comp3.choices[0].message
        tool_calls = list(msg3.tool_calls or [])
        usage3 = comp3.usage.model_dump() if comp3.usage else {}
        summary.append(f"[P3a] tool round -> HTTP {rec3['status']} ({rec3['elapsed_ms']} ms); tool_calls={len(tool_calls)}")
        for tc in tool_calls:
            summary.append(f"[P3a]   call {tc.id} {tc.function.name} args={tc.function.arguments}")
        summary.append(f"[P3a] usage={json.dumps(usage3, sort_keys=True)}")
        summary.append(f"[P3a] rate-limit headers: {json.dumps(rec3['ratelimit_headers'], sort_keys=True)}")
    else:
        summary.append(f"[P3a] tool round -> HTTP {rec3['status']} ({rec3['elapsed_ms']} ms); error={rec3.get('error')}")
        summary.append(f"[P3a] body={str(rec3.get('body'))!s:.400}")
        summary.append(f"[P3a] rate-limit headers: {json.dumps(rec3['ratelimit_headers'], sort_keys=True)}")
    if rec3["status"] in TERMINAL or not tool_calls:
        summary.append("[P3a] no tool call returned (or terminal status) — skipping replay.")
        ev.dump(summary)
        return

    msg3 = comp3.choices[0].message
    assistant_msg = {
        "role": "assistant",
        "content": msg3.content,
        "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in tool_calls
        ],
        # NOTE: no `reasoning` field replayed — mirrors strands' replay stripping
        # ("reasoningContent is not supported in multi-turn conversations").
    }
    tool_msg = {"role": "tool", "tool_call_id": tool_calls[0].id, "content": TOOL_RESULT_JSON}
    body4 = {
        "model": args.model, "messages": msgs3 + [assistant_msg, tool_msg],
        "tools": [TOOL_DEF], "tool_choice": "auto", "max_tokens": 1024, "stream": False,
    }
    rec4, comp4 = _call(ev, "tool_result_replay", lambda: raw_client.chat.completions.create(**body4))
    if comp4 is not None:
        usage4 = comp4.usage.model_dump() if comp4.usage else {}
        summary.append(f"[P3b] replay -> HTTP {rec4['status']} ({rec4['elapsed_ms']} ms)")
        summary.append(f"[P3b] content={json.dumps(comp4.choices[0].message.content)!s:.200}")
        summary.append(f"[P3b] usage={json.dumps(usage4, sort_keys=True)}")
        summary.append(f"[P3b] rate-limit headers: {json.dumps(rec4['ratelimit_headers'], sort_keys=True)}")
    else:
        summary.append(f"[P3b] replay -> HTTP {rec4['status']} ({rec4['elapsed_ms']} ms); error={rec4.get('error')}")
        summary.append(f"[P3b] body={str(rec4.get('body'))!s:.400}")
        summary.append(f"[P3b] rate-limit headers: {json.dumps(rec4['ratelimit_headers'], sort_keys=True)}")

    ev.dump(summary)


if __name__ == "__main__":
    main()
