"""Gemini 3.1 Flash-Lite live probe (2026-09-04). See probes/README.md.

Call budget by design: <=5 sequential requests (--only all), or exactly 2
(--only replay) —
  1. GET /v1beta/models            (metadata-only; also verifies that the
                                     Models.list response carries NO quota
                                     fields, per docs)
  2. tiny generateContent          (auth, usageMetadata, headers, latency)
  3. functionCalling round         (function calling)
  4. functionResponse replay       (multi-turn semantics — the part is
                                     replayed VERBATIM incl. thoughtSignature)
  5. structured output             (responseSchema JSON)
No retries, no loops, no concurrency. STOPS at the first terminal
failure (401/403/429). The synthetic tool is read-only; nothing from
the benchmark or the app is used.

Live findings baked into this script (2026-09-04, first run):
- Gemini 3.x attaches a `thoughtSignature` to function-call parts and
  REQUIRES it to be replayed verbatim; dropping it yields HTTP 400
  INVALID_ARGUMENT "Function call is missing a thought_signature"
  (evidence: gemini-probe-2026-09-04.json, function_response_replay).
- Success responses carry NO quota/rate-limit headers (Layer-B answer).

Auth note: the API key travels ONLY in the `x-goog-api-key` request
header (never in the URL), so captured URLs stay secret-free.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from probe_common import (
    Evidence,
    body_json,
    http_json,
    load_credentials,
    make_redactor,
)

FUNC_DECL = {
    "name": "get_balance",
    "description": "Return the settled balance of a ledger account.",
    "parameters": {
        "type": "object",
        "properties": {"account_id": {"type": "string"}},
        "required": ["account_id"],
    },
}

TOOL_RESULT = {"account_id": "ACC-1", "balance": 1000.25, "currency": "USD"}

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string"},
        "amount": {"type": "number"},
    },
    "required": ["verdict", "amount"],
}

TERMINAL = {401, 403, 429}


def _texts(data: dict) -> str:
    parts = []
    for cand in data.get("candidates", []):
        for part in (cand.get("content", {}) or {}).get("parts", []):
            if "text" in part:
                parts.append(part["text"])
    return "".join(parts)


def _function_call(data: dict) -> dict | None:
    for cand in data.get("candidates", []):
        for part in (cand.get("content", {}) or {}).get("parts", []):
            if "functionCall" in part:
                return part["functionCall"]
    return None


def _function_call_part(data: dict) -> dict | None:
    """The FULL part containing the functionCall — including any
    `thoughtSignature` that Gemini 3.x thinking models attach and REQUIRE
    to be replayed verbatim."""
    for cand in data.get("candidates", []):
        for part in (cand.get("content", {}) or {}).get("parts", []):
            if "functionCall" in part:
                return part
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", required=True,
                    help=".env file to read GEMINI_API_KEY from (by name only; required — no default)")
    ap.add_argument("--base-url", default="https://generativelanguage.googleapis.com")
    ap.add_argument("--model", default="gemini-3.1-flash-lite")
    ap.add_argument(
        "--evidence-stem",
        default="~/projects/reconciliation-investigator/agent-memory/evidence/gemini-probe-2026-09-04",
    )
    ap.add_argument(
        "--only",
        choices=["all", "replay"],
        default="all",
        help="'replay' runs only the function round + verbatim-part replay (2 calls)",
    )
    args = ap.parse_args()

    creds = load_credentials(Path(args.env_file), ["GEMINI_API_KEY"])
    redact = make_redactor(creds)
    headers = {"x-goog-api-key": creds["GEMINI_API_KEY"], "Content-Type": "application/json"}
    gen_url = f"{args.base_url}/v1beta/models/{args.model}:generateContent"
    ev = Evidence(Path(args.evidence_stem), redact)
    summary = [f"GEMINI PROBE model={args.model} base={args.base_url} only={args.only}"]

    if args.only == "all":
        # -- Step 1: models list (metadata-only; verify no quota fields) --
        rec = http_json("GET", f"{args.base_url}/v1beta/models?pageSize=200", {"x-goog-api-key": creds["GEMINI_API_KEY"]})
        ev.add("models_list", rec)
        data = body_json(rec) or {}
        names = sorted(m.get("name", "?") for m in data.get("models", [])) if isinstance(data, dict) else []
        quota_fields = [
            k for m in (data.get("models", []) if isinstance(data, dict) else [])
            for k in m if any(t in k.lower() for t in ("quota", "rate", "remaining"))
        ]
        summary.append(
            f"[1] GET /v1beta/models -> HTTP {rec['status']} ({rec['elapsed_ms']} ms); "
            f"listed={len(names)}; flash-lite ids={[n for n in names if 'flash-lite' in n][:8]}"
        )
        summary.append(f"[1] quota-ish fields present in Models.list resources: {sorted(set(quota_fields)) or 'NONE'}")
        if rec["status"] in TERMINAL or rec["status"] is None:
            summary.append(f"[1] TERMINAL ({rec['status']}) — stopping.")
            ev.dump(summary)
            return

        # -- Step 2: tiny completion --
        body2 = {
            "contents": [{"role": "user", "parts": [{"text": "Reply with exactly: OK"}]}],
            "generationConfig": {"maxOutputTokens": 512},
        }
        rec2 = http_json("POST", gen_url, headers, body2)
        ev.add("completion_tiny", rec2)
        data2 = body_json(rec2) or {}
        hdr2 = {k: v for k, v in rec2["headers"].items() if k.lower().startswith(("x-", "retry-after", "date", "content-type"))}
        summary.append(f"[2] generateContent -> HTTP {rec2['status']} ({rec2['elapsed_ms']} ms); text={_texts(data2)!r:.80}")
        summary.append(f"[2] usageMetadata={json.dumps(data2.get('usageMetadata', {}), sort_keys=True)}")
        summary.append(f"[2] response-headers(filtered)={json.dumps(hdr2, sort_keys=True)}")
        if rec2["status"] in TERMINAL or rec2["status"] is None:
            summary.append(f"[2] TERMINAL ({rec2['status']}) — stopping before function rounds.")
            ev.dump(summary)
            return

    # -- Step 3: function-calling round --
    contents3 = [
        {"role": "user", "parts": [{"text": "What is the settled balance of account ACC-1? Use the get_balance tool."}]},
    ]
    body3 = {
        "contents": contents3,
        "tools": [{"functionDeclarations": [FUNC_DECL]}],
        "generationConfig": {"maxOutputTokens": 1024},
    }
    rec3 = http_json("POST", gen_url, headers, body3)
    ev.add("function_call_round", rec3)
    data3 = body_json(rec3) or {}
    fc = _function_call(data3)
    fc_part = _function_call_part(data3)
    summary.append(f"[3] function round -> HTTP {rec3['status']} ({rec3['elapsed_ms']} ms); functionCall={json.dumps(fc)}")
    summary.append(
        f"[3] part carries thoughtSignature: {'YES' if fc_part and 'thoughtSignature' in fc_part else 'NO'}"
    )
    summary.append(f"[3] usageMetadata={json.dumps(data3.get('usageMetadata', {}), sort_keys=True)}")
    if rec3["status"] in TERMINAL or not fc:
        summary.append("[3] no functionCall returned (or terminal status) — skipping replay.")
        ev.dump(summary)
        return

    # -- Step 4: functionResponse replay (part replayed VERBATIM — including
    # thoughtSignature and id; dropping thoughtSignature yields 400, verified) --
    contents4 = contents3 + [
        {"role": "model", "parts": [fc_part]},
        {"role": "user", "parts": [{"functionResponse": {"name": fc["name"], "response": TOOL_RESULT}}]},
    ]
    body4 = {
        "contents": contents4,
        "tools": [{"functionDeclarations": [FUNC_DECL]}],
        "generationConfig": {"maxOutputTokens": 1024},
    }
    rec4 = http_json("POST", gen_url, headers, body4)
    ev.add("function_response_replay", rec4)
    data4 = body_json(rec4) or {}
    summary.append(f"[4] replay -> HTTP {rec4['status']} ({rec4['elapsed_ms']} ms); text={_texts(data4)!r:.160}")
    summary.append(f"[4] usageMetadata={json.dumps(data4.get('usageMetadata', {}), sort_keys=True)}")

    if args.only == "replay":
        ev.dump(summary)
        return

    # -- Step 5: structured output --
    body5 = {
        "contents": [{
            "role": "user",
            "parts": [{
                "text": (
                    "Legacy ledger shows 100.25 USD for ACC-1; the modern system shows 90.25 USD. "
                    'Return JSON with keys "verdict" (string, exactly "mismatch") and "amount" (number, 90.25).'
                ),
            }],
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "maxOutputTokens": 512,
        },
    }
    rec5 = http_json("POST", gen_url, headers, body5)
    ev.add("structured_output", rec5)
    data5 = body_json(rec5) or {}
    text5 = _texts(data5)
    parsed = None
    try:
        parsed = json.loads(text5)
    except (TypeError, ValueError):
        pass
    ok5 = isinstance(parsed, dict) and "verdict" in parsed and "amount" in parsed
    summary.append(f"[5] structured output -> HTTP {rec5['status']} ({rec5['elapsed_ms']} ms); schema-valid JSON: {ok5}; body={text5!r:.120}")
    summary.append(f"[5] usageMetadata={json.dumps(data5.get('usageMetadata', {}), sort_keys=True)}")

    ev.dump(summary)


if __name__ == "__main__":
    main()
