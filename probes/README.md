# probes/ — provider feasibility probes (2026-09-04)

Isolated live probes used ONLY for the Cerebras GPT-OSS-120B / Gemini 3.1
Flash-Lite provider-feasibility investigation
(`docs/provider-feasibility-cerebras-gemini.md`). They are deliberately
SEPARATE from the application and the benchmark:

- No imports from `agents/`, `orchestrator/`, `tools/`, `evals/`, `tests/`.
- No changes to the app's Groq wiring, the eval harness, or any case data.
- No write/correction tools are ever declared or sent to a model — the only
  tool any probe defines is a synthetic read-only `get_balance`.
- Credentials: `probe_common.load_credentials()` loads ONLY the explicitly
  requested variable NAMES (`CEREBRAS_API_KEY` / `GEMINI_API_KEY`) from an
  explicit `.env` file (default: the `../[SIBLING-A]` sibling).
  Values are passed in-process to the HTTP client / SDK client and are
  never printed, logged, or written. Every line that leaves a probe
  (stdout, evidence files) passes through a redactor that masks the loaded
  secret values plus any key-shaped token (`AIza…`, `csk-…`, `gsk_…`,
  `sk-…`, `Bearer …`).
- Request headers are never recorded; only RESPONSE headers are captured
  (that is where rate-limit information lives).
- Budget discipline: each probe makes a handful of tiny sequential calls,
  no loops, no concurrency, no retries, and STOPS at the first terminal
  failure (401/402/403/429) rather than burning quota.

Governance: `probes/` is controlling-session territory (like `scripts/`),
created for this investigation per the repo's probe precedent — probe
scripts stay out of `scripts/` (Tier C guard surface) and out of the
backend seat's `agents|orchestrator|tools|tests` tree.

## Files

| File | Purpose |
| --- | --- |
| `probe_common.py` | env loader (names only), redactor, HTTP capture, evidence writer |
| `probe_cerebras.py` | raw REST probe: auth/models, tiny completion, tool call + replay |
| `probe_gemini.py` | raw REST probe: model list, tiny completion, function call + replay, structured output |
| `probe_groq.py` | two-key Groq probe (openai-sdk transport): models list, tiny completion, tool round + replay, full `x-ratelimit-*` capture — one `--env-file`/`--env-tag` per sibling project |
| `probe_strands.py` | the app's exact Strands `OpenAIModel`/`GeminiModel` idiom against each provider, with a synthetic tool loop |

## Usage (from the repo root)

```bash
uv run --locked python probes/probe_cerebras.py
uv run --locked python probes/probe_gemini.py
uv run --locked python probes/probe_groq.py --env-file ~/projects/[SIBLING-A]/.env --env-tag [SIBLING-A]
uv run --locked python probes/probe_groq.py --env-file ~/projects/[SIBLING-B]/.env      --env-tag gateway
uv run --locked python probes/probe_strands.py --provider cerebras
uv run --locked python probes/probe_strands.py --provider gemini-compat
uv run --frozen --with google-genai python probes/probe_strands.py --provider gemini-native
```

Evidence lands in `agent-memory/evidence/` (`.json` machine records,
`.txt` human summaries) — all sanitized.
