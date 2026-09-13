# Provider feasibility report — Cerebras GPT-OSS-120B & Gemini 3.1 Flash-Lite
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

> REDACTED 2026-09-07 (privacy pass): sibling-project names and
> out-of-repo local paths in this report were replaced with neutral tokens
> ([SIBLING-A]…[SIBLING-J], ~) before publication; originals preserved in
> the author's private pre-rewrite bundle.

**Date:** 2026-09-04 · **Status:** investigation complete; NO-GO / CONDITIONAL GO issued below
**Scope:** READ-ONLY investigation of the target repo + authorized live probes only. The
5-case evaluation was NOT run; the production model was NOT switched; the benchmark
methodology was NOT changed. No credential value was read into any output.

Investigation request: free-tier feasibility for the full 5-case evaluation
(~105–195 LLM requests, ~450–650K tokens, strictly sequential driver
`evals/run_sequential.py`) on (A) Cerebras `gpt-oss-120b` and (B) Google
`gemini-3.1-flash-lite`, using the credentials that exist in the sibling
`[SIBLING-A]` project's `.env` (names only ever handled: `CEREBRAS_API_KEY`,
`GEMINI_API_KEY`).

Prior in-repo context this report builds on (and supersedes where noted):
`agent-memory/groq-preflight-2026-09-04.md` (workload model; Groq free tier NO-GO),
`agent-memory/gemini-feasibility-2026-09-04.md` (pre-live Gemini analysis),
`agent-memory/gemini-quota-provenance-2026-09-04.md` (20-vs-500 RPD provenance).

---

## 1. Executive summary

| Provider | Model | Free API | Auth works | Tool calling | Effective RPM | Effective TPM | Effective RPD | Monthly limit | Full eval | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cerebras | `gpt-oss-120b` | Documented free tier exists, **but this account's inference is blocked (HTTP 402)** | Yes (key valid; `models.list` 200) | **NOT TESTABLE** (blocked; documented as supported) | DOCUMENTED 5 (account-effective: none — no inference) | DOCUMENTED 30K uncached / 90K total (account-effective: none) | Not published per day for free tier (TPD 1M documented; no RPD metric) | None documented | **NO** | **NO-GO** |
| Google | `gemini-3.1-flash-lite` | Yes (free tier; key works) | Yes | **Yes — verified incl. multi-turn replay via strands `GeminiModel`** | DASHBOARD-OBSERVED 15 (account-specific; not API-verifiable) | DASHBOARD-OBSERVED 250K | DASHBOARD-OBSERVED 500 (account-specific; not API-verifiable) | None documented | **Yes, with mandatory ≤14 RPM pacing** | **CONDITIONAL GO** |

Direct answers to the fourteen questions:

1. **Cerebras GPT-OSS-120B on our Strands tool-calling workload?** Cannot run at
   all: every inference call returns `402 payment_required` (`param: quota`) for this
   account. Verified live twice (below). NOT a code or transport problem.
2. **Gemini 3.1 Flash-Lite on our Strands tool-calling workload?** **Yes — through
   the native path only** (`strands.models.gemini.GeminiModel` + `google-genai`):
   full Agent loop (tool call → local execution → replay → final answer) verified
   live and correct. The OpenAI-compat endpoint path **fails** inside the Strands
   loop (replay drops Gemini's `thoughtSignature` → HTTP 400) — rejected.
3. **Current effective limits for the actual credentials?** Cerebras: account is
   inference-blocked, so no effective serving limits exist to matter; documented
   free-tier numbers in §3. Gemini: 15 RPM / 250K TPM / 500 RPD **as shown on the
   [SIBLING-F] AI Studio dashboard (user-supplied observation)** — there is NO
   API mechanism that exposes them (§4, Layer A/B findings).
4. **How determined?** See §2 provenance table.
5. **Published / API / headers / dashboard / experimental?** Cerebras: published
   docs (+ console dashboard, browser-only; NO quota API; headers not observed).
   Gemini: dashboard only (docs table removed 2026-era; NO quota API reachable
   with an API key; NO quota headers; one *empirical* cross-project 429 exists for
   a different model — §4.4).
6. **Cover ~105–195 requests / 450–650K tokens?** Cerebras: N/A (blocked).
   Gemini: **yes** — 21–39% of RPD; TPM never binds at paced rate; requests
   comfortably inside RPD. Residual unknown: an unpublished TPD (§5.3).
7. **Pacing required?** Gemini: **mandatory** ≤14 RPM pacer (~4.3 s floor between
   request starts), implemented as a model-adapter concern (§8), plus
   stop-on-repeat-429 discipline. Cerebras: N/A (and would need ~12 s at 5 RPM).
8. **Integration changes?** Gemini native: one dependency pin + `agents/model.py`
   provider swap + credential wiring + pacer; **zero eval-harness changes**
   (§8). OpenAI-compat variant: rejected. Cerebras: two-line swap would suffice
   *if* the account were unblocked (it cannot be, within task constraints).
9. **Tool calling behaves correctly with Strands?** Verified YES for Gemini native
   (correct tool, correct args, correct replay, correct final answer). NOT
   TESTABLE for Cerebras. **NO for Gemini via OpenAI-compat** (replay 400).
10. **Structured output usable?** Gemini: YES — verified schema-valid JSON via
    `responseMimeType`+`responseSchema` (our judges, however, use rubric prompts,
    not response schemas — this de-risks any future use). Cerebras: documented
    supported; unverified (blocked). Note: Cerebras documents that `tools` +
    `response_format` cannot be combined on `gpt-oss-120b` — irrelevant to our
    judge design but a constraint to remember.
11. **Model suitability for this benchmark?** `gpt-oss-120b` is the SAME weights as
    the current Groq config (`openai/gpt-oss-120b`) → like-for-like capability,
    though unverified on Cerebras serving. `gemini-3.1-flash-lite`: probe-level
    correctness verified; **full-case reasoning and judge quality remain
    UNVERIFIED** — "operationally viable but quality remains unverified" (§6).
12. **Strictly $0 choice:** **Gemini 3.1 Flash-Lite (native path)** — the only
    candidate that can actually serve requests for free with the existing
    credentials.
13. **If one is operationally unreliable:** Cerebras is *already* operationally
    unavailable ($0). Gemini native is the reliability pick of the two as well;
    its residual risks (dashboard-only quota knowledge, possible unpublished TPD,
    lite-judge noise) are disclosed in §4/§5/§6 with mitigations. (Outside the $0
    frame, paid Groq GPT-OSS-120B remains the zero-code-change option per the
    prior Gemini-feasibility report.)
14. **Final GO/NO-GO:** Cerebras **NO-GO**; Gemini **CONDITIONAL GO** (§9).

---

## 2. Evidence provenance

| Claim | Source class | Where |
| --- | --- | --- |
| Cerebras free-tier 5 RPM / 30K uncached TPM / 90K total TPM / 1M TPH / 1M TPD for `gpt-oss-120b` | **DOCUMENTED** (official rate-limits page, fetched 2026-09-04; changelog current through 2026-09-03) | inference-docs.cerebras.ai/support/rate-limits |
| Cerebras free-tier context 65K / max output 32K; reasoning always-on, counted | **DOCUMENTED** | inference-docs.cerebras.ai/models/openai-oss |
| Cerebras key valid, inference 402 | **OBSERVED** (live probe, this investigation, 2 requests) + prior OBSERVED 2026-08-28 (SDK + raw curl, both models) | evidence below; ~/scratch-tests/validation-report.md §2 |
| Cerebras no quota-query API; headers not documented | **DOCUMENTED (absence)** — no such endpoint on any official page; console dashboard browser-only | §3.5 |
| Cerebras rate-limit response headers | **NOT OBSERVED** on our 200/402 responses (only `x-should-retry: false` on the 402); a GitHub user report suggests `x-ratelimit-limit-*` — labeled secondary, not relied upon | evidence below |
| Gemini free-tier 15 RPM / 250K TPM / 500 RPD for `gemini-3.1-flash-lite` ([SIBLING-F]) | **ACCOUNT-SPECIFIC: dashboard-observed, user-supplied** — Google removed the per-model free-tier table from the docs (rate-limits page, updated 2026-09-02); no API exposes it; **not independently re-verified programmatically (no mechanism exists)** | §4.2/§4.3 |
| Gemini quotas are per project (not per key); RPD resets midnight PT | **DOCUMENTED** | ai.google.dev/gemini-api/docs/rate-limits |
| Gemini 3.x replay requires `thoughtSignature` | **OBSERVED** (live 400 without / 200 with, both captured) + Google doc page thought-signatures | §4.4; evidence files |
| Gemini success responses carry no quota headers | **OBSERVED** (5 distinct 200 responses captured; only `X-Gemini-Service-Tier` etc.) | evidence files |
| Gemini "20 RPD" | **OBSERVED (third project, different model, 2026-08-22)** — `gemini-3.6-flash`, `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quotaValue 20 | [SIBLING-B] evidence, §4.6 |
| Workload 105–195 requests / 450–650K tokens / sequential | **ACCOUNT-SPECIFIC CONFIRMED** (derived from installed evaluator source + prior preflight; not re-measured) | groq-preflight §2 |

Legend: DOCUMENTED = current official documentation (URL cited). OBSERVED = captured
live by this investigation. ACCOUNT-SPECIFIC CONFIRMED = verified for THIS
project/credential. ACCOUNT-SPECIFIC UNKNOWN = no mechanism exists to confirm.

---

## 3. Cerebras findings

### 3.1 Identity and endpoints

- Model ID: **`gpt-oss-120b`** — confirmed present in the live catalog
  (`GET /v1/models` → 200, 3 models, `gpt-oss-120b` among them).
- API: `https://api.cerebras.ai/v1` (OpenAI-compatible; `/chat/completions`,
  `/models`, …). Auth: `Authorization: Bearer <CEREBRAS_API_KEY>`.
- Transport note (worth recording): **raw `urllib` is blocked at the Cloudflare
  edge** — HTTP 403, body `error code: 1010`, `Server: cloudflare` (browser-signature
  ban; the request never reached the API; no quota consumed). The `openai` SDK
  (httpx) — the same transport the app's `OpenAIModel` uses — passes normally.
  Evidence: `agent-memory/evidence/cerebras-probe-2026-09-04-urllib-blocked.json`.
  Any future hand-rolled Cerebras client must not use bare urllib.

### 3.2 Authentication result

Key VALID at the API layer: `models.list` → **HTTP 200** (629.9 ms, catalog of 3).
This matches the 2026-08-28 bench (SDK `models.list` 200 then too).

### 3.3 Inference result — the decisive finding

`POST /v1/chat/completions` (tiny prompt) → **HTTP 402**, body (sanitized, verbatim):

```json
{"message": "Payment required to access this resource. Visit your billing tab.",
 "type": "payment_required_error", "param": "quota", "code": "payment_required"}
```

with response header `x-should-retry: false`. This is an **account-level wall**, not a
rate limit and not a code issue:

- Same error class observed 2026-08-28 (~/scratch-tests, SDK streaming +
  non-streaming + raw curl, both `gpt-oss-120b` and `gemma-4-31b`) — i.e. stable for
  a week, account-wide.
- Consistent with the documented 2026-07-16 free-tier rework: "New accounts now
  receive $5 in free credits **after adding a verified payment method**" — this
  account evidently has no usable free inference allocation.
- Remedies (billing setup / payment method / credits) are all **forbidden actions**
  under this task's constraints ("do not modify billing settings or enable paid
  usage"). This is a human decision, not an engineering one.

Consequences: **tool calling, multi-turn replay, and Strands compatibility are NOT
TESTABLE for Cerebras** — the first inference call never succeeds. The Strands probe
was therefore NOT run for Cerebras: it uses the identical openai-SDK transport and
base URL that just returned 402, so its outcome is fully determined (a skipped,
deducible call — per the "no unnecessary live API calls" rule).

### 3.4 Documented free-tier limits (would apply IF the account were unblocked)

| Metric (Free Trial, `gpt-oss-120b`) | Value | Note |
| --- | --- | --- |
| RPM | **5** | org-level, per-model |
| TPM (uncached) | **30K** | "primary" bucket |
| TPM (total) | **90K** | = 3× uncached |
| TPH / TPD | **1M / 1M** | |
| Context / max output | **65K / 32K** | free tier (paid: 131K / 40K) |
| Enforcement | token bucket, continuous replenishment | no fixed windows; pre-check estimates `input + max_completion_tokens` |
| Reasoning | always on (cannot disable); tokens counted; `reasoning_effort` low/med/high (default medium) | |
| Tools / structured output | supported; `parallel_tool_calls` default true; strict schemas; **`tools` + `response_format` mutually exclusive** | |
| Params | `max_completion_tokens` canonical (`max_tokens` alias; never both) | app currently sends `max_tokens` — harmless (alias) |

Hypothetical fit (moot while blocked): 5 RPM → 105 req ≥ 21 min, 195 req ≥ 39 min of
starts alone; the token-bucket pre-check would count each large evidence-bundle call
as ~15–25K (input + 8192 max_completion estimate) against the 30K uncached bucket →
effective ~1–2 large calls/min → a realistic 1.5–3 h run; TPD 1M covers 450–650K with
~35% retry headroom; 65K context covers our ~15K max.

### 3.5 Limit discoverability for the actual credential

- **Layer A (quota API):** none documented. The Metrics API
  (`cloud.cerebras.ai/api/v1/metrics/organizations/{id}`, Prometheus format, opt-in,
  6 RPM) has request/token counters but **no quota/remaining metrics**.
- **Layer B (headers):** nothing observed on our 200/402 responses (only
  `x-should-retry`). Not documented; one unconfirmed user report of
  `x-ratelimit-limit-{requests,tokens}-minute` exists — not relied upon.
- **Layer C (dashboard):** console → Analytics ("Show quotas" toggle) and a Limits
  page — **browser-only**; not inspected here (no console access from CLI).
- **Layer D (probe):** the 402 IS the probe result. We did not, and will not,
  attempt to enumerate limits by inducing 429s.

---

## 4. Gemini findings

### 4.1 Identity

- Model ID: **`gemini-3.1-flash-lite`** (GA since 2026-05-07). Live `models.list`
  also shows `gemini-3.1-flash-lite-preview` (deprecated), `gemini-3.5-flash-lite`,
  `gemini-flash-lite-latest`, `gemini-2.5-flash-lite`.
- Project: the Google AI Studio project behind the sibling's `GEMINI_API_KEY`,
  historically identified as **"[SIBLING-F]"** (identification only; no key
  material handled or compared).
- Context window **1,048,576 in / 65,536 out** (documented) — dwarfing our ~15K max.
- Function calling, structured outputs, system instructions: documented supported;
  **verified live** (below).

### 4.2 Live probe results (raw REST, `v1beta`, key via `x-goog-api-key` header only)

| Step | Result | Detail |
| --- | --- | --- |
| `GET /v1beta/models` | 200 (1342 ms) | 54 models; **no quota/rate fields in the Model resources** (only `inputTokenLimit`/`outputTokenLimit`) — Layer A negative confirmed live |
| Tiny completion ("Reply with exactly: OK") | **200**, text `OK` (1826 ms) | `usageMetadata`: 6 prompt / 1 candidate / 7 total; `serviceTier: standard` |
| Function-calling round | **200** (1559 ms) | exact `functionCall {name: get_balance, args: {account_id: ACC-1}, id}` + `thoughtSignature` (156 chars) on the part |
| Tool-result replay **without** signature | **400 INVALID_ARGUMENT** | verbatim: `"Function call is missing a thought_signature in functionCall parts…"` |
| Tool-result replay **with verbatim part** | **200** (2417 ms) | correct final: "The settled balance of account ACC-1 is 1000.25 USD." |
| Structured output (`responseSchema`) | **200** (3847 ms) | schema-valid JSON `{"verdict": "mismatch", "amount": 90.25}` |
| Response headers on all 200s | — | **no quota/remaining headers** (only `X-Gemini-Service-Tier`, `X-Content-Type-Options`, …) — Layer B negative |

Token reporting: full `usageMetadata` (prompt/candidates/total, thoughts counter
field exists) on every call. Latency profile: 0.8–3.8 s per tiny call.

### 4.3 Strands compatibility (the decisive test for the app's architecture)

| Path | Result |
| --- | --- |
| `OpenAIModel` → Gemini OpenAI-compat endpoint (`/v1beta/openai/`) | **BROKEN for the real agent loop.** Turn 1 succeeds (model emits `tool_calls`, strands executes the tool), but the strands replay drops Gemini's thought-signature → **HTTP 400, identical `"missing thought_signature"` error**, `EventLoopException`. Evidence: `agent-memory/evidence/strands-probe-gemini-compat-2026-09-04.txt`. **Rejected as an integration path** (fixing it means patching the strands OpenAI adapter — not a small change). |
| `GeminiModel` (strands native) + `google-genai` | **WORKS end-to-end.** Full Agent loop with the app's exact construction idiom: tool called with correct args, executed locally, replayed, final answer correct ("…1000.25 USD."), 5.49 s wall. Ran with ephemeral `uv run --frozen --with google-genai` — **`uv.lock` and `pyproject.toml` untouched** (verified by `git status`). Evidence: `agent-memory/evidence/strands-probe-gemini-native-2026-09-04.txt`. |

Dependency facts for the plan: resolved `google-genai==2.22.0`; strands 1.54.0
declares extra `gemini` = `google-genai>=1.67.0,<3.0.0` (2.22.0 in range).

### 4.4 The thought-signature replay rule (new, hard evidence)

Gemini 3.x models attach a `thoughtSignature` to function-call parts and **require
it to be replayed verbatim**; dropping it is a hard 400 (captured both via raw REST
and inside strands' OpenAI adapter). The native `google-genai` SDK carries the full
part structure, which is why `GeminiModel` works. This is the same *class* of trap
as the Groq `reasoning_content` replay issue from the [SIBLING-B]'s lessons — and it is
now **de-risked by evidence** for the native path.

### 4.5 Effective limits for [SIBLING-F]'s credential

- **RPM 15 / TPM 250K / RPD 500** — from the AI Studio dashboard (user-supplied
  observation, project [SIBLING-F]). Classification: **ACCOUNT-SPECIFIC:
  dashboard-observed; not API-verifiable.**
  - Layer A: `models.list` provably carries no quota fields (verified live).
    The Service Usage API `consumerQuotaMetrics.list` exists but requires **OAuth2**
    (`cloud-platform` scopes) + `serviceusage.quotas.get` — **cannot be called with
    an AI Studio API key**; using it would need an OAuth credential we do not have
    (and creating one is out of scope).
  - Layer B: no quota headers on success (verified live, 5 responses).
  - Layer C: AI Studio dashboard/rate-limit page — **browser-only** (login-walled;
    302 to accounts.google.com verified).
  - Layer D: deliberately NOT probed to exhaustion (no induced 429s).
- Attribution: **per project, not per key** (documented); keys inherit the
  project's tier; tiers sit at the billing-account level. RPD resets **midnight
  Pacific**. Documented caveat that even failed (400/500) requests count against
  quota → blind retries are quota-destructive.
- Possible **TPD**: docs say some models "might have" a token-per-day limit, none
  published for this model → **ACCOUNT-SPECIFIC UNKNOWN**; §5.3 mitigations.

### 4.6 Resolution of the "500 RPD vs 20 RPD" discrepancy

**Resolved — they were never the same quota.**

1. **Provenance of 20 RPD:** a verbatim Google 429 `QuotaFailure` captured live on
   **2026-08-22** in the *[SIBLING-B]* project's evidence
   (`agent-memory/evidence/[SIBLING-B-INTERNAL]-model-loop/[SIBLING-B-INTERNAL]-model-loop-live-smoke-run3.txt`
   lines 170/211, re-verified byte-exact during this investigation):
   `quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier`, **model
   `gemini-3.6-flash`**, `quotaValue 20`.
2. **Different model** (3.6-flash ≠ 3.1-flash-lite), **different project**
   ([SIBLING-B]'s then-key, not [SIBLING-F]'s), and the quotaId itself
   declares **per-project AND per-model** scoping — so the figure cannot transfer
   even if the projects coincided.
3. It was an **empirical server response**, not documentation; and current official
   documentation publishes **no** free-tier RPD rows at all (table removed), so no
   documented "20 RPD" exists to conflict with.
4. **Conclusion for our credential:** [SIBLING-F]'s `gemini-3.1-flash-lite` daily
   request quota is **500 per the dashboard (user-supplied)**. It is not
   independently confirmable programmatically — stated plainly: *account-specific
   RPD is confirmed only at dashboard confidence level.* Nothing was averaged or
   assumed away; the 20-RPD figure is fully attributed and excluded.

### 4.7 Limitations (Gemini)

- Quota knowledge is dashboard-grade, one observation, user-supplied; today's
  remaining headroom is visible only in that dashboard (we consumed **12 requests**
  during this investigation: 6 raw + 2 replay-fix + 2 compat + 2 native).
- Possible unpublished TPD (unknown; mitigations in §5.3).
- Judge/agent quality on a lite model — a validity question, not a quota one (§6).
- Strands `GeminiModel` verified for the tool loop + replay; judge-style (no-tool)
  calls de-risked by raw-probe steps 2/5 but not re-run through strands (the judge
  path is a strict subset of the verified surface: same model class, no tools).
- `google-genai` SDK auto-retries transient errors (documented: up to 4 attempts,
  ~1 s initial, 60 s max) and strands maps `RESOURCE_EXHAUSTED`/`UNAVAILABLE` →
  `ModelThrottledException` (`strands/models/gemini.py:683-686`) engaging strands'
  retry (6 attempts, 4→240 s). Worst-case amplification on a throttled logical
  call ≈ 6×(1+4) = **30 transport attempts** — another reason pacing (not
  retry-luck) must carry the run.

---

## 5. Full-run calculations

### 5.1 Assumptions (all explicit)

- Workload (from groq-preflight, architecture-derived): requests **105 min / 125–150
  typical / 195 max**; tokens **450K / 500K / 650K** (worst-case cycling ~800K);
  max single request ~15K tokens; **strictly sequential** driver; graph ≈7–11
  calls/case (to ~21 with cycling), judges ≈10–18 calls/case.
- Gemini limits: 15 RPM / 250K TPM / 500 RPD (dashboard-observed; §4.5).
- Pacing: ≤14 RPM ⇒ **4.29 s floor between request starts**; observed per-call
  latency 0.8–3.8 s tiny / assume 1.5–4 s realistic.
- Retries: SDK stacks left at defaults (as the app runs today); with pacing they
  should ~never engage; **no blind-retry policy** (failed requests still consume
  quota — documented).

### 5.2 Wall-clock and quota fit (Gemini 3.1 Flash-Lite, native, paced)

| Scenario | Requests | Tokens | Start-scheduler time (×4.29 s) | Realistic wall-clock (incl. latency) | RPD used (of 500) | TPM peak (of 250K) |
| --- | --- | --- | --- | --- | --- | --- |
| Minimum | 105 | 450K | 7.5 min | **~11–14 min** | 21% | typical minute ~45–70K (18–28%); absolute worst homogeneous minute (14×15K) 210K (84%) |
| Typical-low | 125 | 500K | 8.9 min | **~13–17 min** | 25% | as above |
| Typical-high | 150 | 550–600K | 10.7 min | **~16–20 min** | 30% | as above |
| Maximum | 195 | 650K | 14.0 min | **~21–26 min** | 39% | as above |

- **Fits in one day / one quota window:** yes — a single run uses 21–39% of RPD;
  even a same-day full rerun (2×195 = 390 < 500) remains inside RPD, though the
  prudent budget is ONE full run + ~100 requests of probe/headroom per day.
- **TPM risk:** negligible at paced rate (aggregate token flow ≈ 450K/20 min ≈
  23K/min ≈ 9% of TPM; 650K/26 min ≈ 25K/min ≈ 10%). The only theoretically tight
  window is a homogeneous minute of maximum-size calls (84% of TPM) — if paranoid,
  pace at 12 RPM (5.0 s): 105→8.8 min, 195→16.3 min scheduler time, worst minute
  → 180K (72%).
- **RPD risk:** low; retries-with-pacer ≈ none. **Unpaced** sequential judge bursts
  (20–60 RPM natural) WOULD storm 429s, consume quota on failures, and trigger the
  30-attempt retry stack — this is why the pacer is a **condition** of GO, not an
  optimization.
- **Retry amplification over quota:** bounded by pacing + a stop rule (§8: ≥3
  consecutive 429s → abort, report, reschedule — lesson L007 discipline).

### 5.3 Unknown-TPD contingency (honesty item)

If an unpublished TPD exists for this model below ~650K, the run could stall late.
Mitigations, in order: (1) check the dashboard for a TPD row before the run
(browser, human); (2) run one canary case (~90–125K tokens) and re-check the
dashboard usage; (3) if a TPD binds, split the run across days at the midnight-PT
reset (RPD allows ~½ run + reruns per day regardless). This residual cannot be
closed from the CLI — no API exposes it.

### 5.4 Cerebras (for completeness — moot while 402)

At documented 5 RPM: 105 req ≥ 21 min, 195 ≥ 39 min scheduler-time; token-bucket
pre-check (input + max_completion_tokens) makes effective pace ~1–2 large
calls/min → **1.5–3 h realistic**; TPD 1M covers 450–650K (≤65%, thin for
retries); context 65K OK. Conclusion unchanged: **NO-GO — the account cannot
infer at all.**

---

## 6. Model suitability (evidence-based only)

What the benchmark actually demands (from the repo's prompts/judges):
correct tool selection among 4 read tools; exact parameter extraction
(account IDs, filters); multi-step evidence assembly; conservative
classification with a confidence signal (drives the ≤3-round loop);
drafting structured corrections/tickets via tool args; judges scoring
trajectories/tool-choice/tool-params/output against rubrics; refusal to
act outside the gate.

| Capability | Cerebras gpt-oss-120b | Gemini 3.1 Flash-Lite |
| --- | --- | --- |
| Tool selection & args | Same weights as current Groq config ⇒ like-for-like expected — **unverified (account blocked)** | **Verified at probe level** (exact tool, exact `account_id` arg, correct parse of the tool result) |
| Multi-turn replay | Unverifiable | **Verified** (native path, signature-correct) |
| Instruction-following | Unverifiable | Verified (exact "OK"; schema-exact JSON) |
| Financial reasoning / report quality | Expected like-for-like; unverified on this serving | **UNVERIFIED** — lite-class; full cases never run |
| Judge consistency | Unverifiable | **UNVERIFIED** — weakest link (lite judge = measurement-instrument change; disclose) |

Honest verdicts: Cerebras — capability expected (identical weights to the current
model) but **nothing verifiable** on this account. Gemini — **"operationally
viable; quality remains unverified."** The quality question can only be closed by
running the actual benchmark, which this task forbids; the first real run must be
labeled as the model-swap run it is (§7).

---

## 7. Methodology assessment

**Category A — changes required merely to make the provider work (Gemini native):**

1. `pyproject.toml`: add `google-genai==2.22.0` (pin per repo discipline; strands
   `gemini` extra range satisfied).
2. `agents/model.py`: swap `OpenAIModel`→`GeminiModel`; `GEMINI_API_KEY` wiring
   (same gitignored-.env + environment-wins loader pattern); `MODEL_ID =
   "gemini-3.1-flash-lite"`; `params={"max_output_tokens": 8192}` (name differs
   from `max_tokens`).
3. A ≤14 RPM pacer — recommended as a thin model-adapter wrapper in
   `agents/model.py` so **the eval harness needs zero changes** (graph and judges
   both construct models through `get_model()`).
4. Optional: keep the Groq path in git history only (no runtime fallback —
   mid-run provider fallback is rejected as evidence-smearing; prior ruling).

**Category B — changes that materially alter the benchmark methodology (NOT made):**

- **Agent AND judge model swap** — the measurement instrument changes; scores are
  not comparable to the GLM-era 85.07% baseline or the Groq configuration; every
  result must carry the disclosure "agents + judges ran on gemini-3.1-flash-lite".
- **Tokenizer differences** — token-based quantities (max_tokens budgets, the
  ~450–650K workload estimate) shift by the model's tokenizer (±~30% class).
- **Reasoning profile** — gpt-oss always-reasons (medium) and spends completion
  tokens on reasoning; flash-lite is a minimal-thinking model with
  thought-signatures. Output-length distributions and failure modes differ.
- **Retry/backoff profile** — genai+strands stack (documented above) differs from
  the openai+strands stack; with pacing this is dormant.
- System-prompt handling: `GeminiModel` maps the system prompt to Gemini's system
  instruction (probe carried it correctly); temperature/sampling left at provider
  defaults in both configurations (unchanged policy).

None of Category B was implemented, and Category A was not applied to the app
either — only the isolated `probes/` suite exists. The GO conditions in §9 include
explicit human approval of both categories.

---

## 8. Recommended implementation plan (winning provider: Gemini 3.1 Flash-Lite, native path)

**Not implemented.** Exact plan, smallest-change-preserving-architecture:

1. **Dependencies** — `pyproject.toml`: `google-genai==2.22.0` (dated-snapshot pin,
   live-verified 2026-09-04); `uv lock`; commit pin + lock together (repo rule).
2. **`agents/model.py`** (the single wiring point):
   - `GeminiModel(client_args={"api_key": GEMINI_API_KEY}, model_id="gemini-3.1-flash-lite", params={"max_output_tokens": max_tokens})`;
   - keep the `.env` loader; read `GEMINI_API_KEY` the same way (user provisions
     the value into the repo `.env` — no cross-project copying);
   - wrap with a `PacedModel` (thin `Model` proxy, ~30 lines) enforcing
     `max(0, MIN_INTERVAL_S - since_last_call)` sleep before each request,
     `MIN_INTERVAL_S` from env `GEMINI_MIN_INTERVAL_S`, default **4.3** (≤14 RPM);
     logs a line on every 429 rather than silently retrying.
   - judge path (`get_model(max_tokens=8192)` in `evals/run_evals.py`) inherits
     pacing automatically — zero eval-harness edits.
3. **Tests** — update `tests/test_model_config.py`: keep the anthropic-import
   guard; add: returns `GeminiModel`, correct model id, correct params, pacer
   floor honored (fake clock), `GEMINI_API_KEY` absence raises the clear error.
   All keyless (DummyModel pattern stays).
4. **verify.sh** — no edits needed; step 6 exercises the new provider at next run.
5. **Run protocol (first execution)** — pre-flight: dashboard check (RPD/TPD
   visibility, human); start after a midnight-PT reset; canary = case 1 only;
   re-check dashboard; then the remaining 4 cases. Abort rule: ≥3 consecutive
   429s → stop, report, reschedule next day (never blind-retry; L007).
6. **Token accounting (optional, recommended)** — a small callback summing
   `usageMetadata` per run into the evidence file (the data is already on every
   response; ~20 lines) — turns the next preflight's ±50% estimate into a
   measurement.
7. **Rollback** — single `git revert` of the swap commit; `.env` key removal
   optional; Groq wiring recoverable from history (`76fd468` lineage).

**Cerebras contingent plan (only if the human unblocks billing — outside this
task's permissions):** `agents/model.py` two-value swap (`base_url=
https://api.cerebras.ai/v1`, model `gpt-oss-120b`) + `CEREBRAS_API_KEY` wiring +
`params={"max_completion_tokens": 8192}` + a ~12 s pacer (5 RPM) + re-probe tool
replay (unverifiable today). It stays NO-GO until the account is fixed by its
owner.

---

## 9. Final decision

### CEREBRAS — **NO-GO**

Account-level inference block (HTTP 402 `payment_required`, `param: quota`),
stable ≥1 week, re-verified live today on the exact app transport. No quota of
any kind is reachable; fixing it requires billing actions explicitly forbidden
here. Nothing about tool calling/Strands could be (or was) claimed.

### GEMINI — **CONDITIONAL GO**

Conditions (all required, all human-approved before the eval run):
1. Native path only (`GeminiModel` + `google-genai==2.22.0`); OpenAI-compat path
   is rejected on evidence (replay 400).
2. Provider swap in `agents/model.py` + credential wiring per §8 (Category A).
3. Mandatory ≤14 RPM pacing (model-adapter level) + L007 stop-on-429 discipline.
4. Pre-run dashboard check (quota headroom + TPD existence) and canary-first run
   protocol (§8.5).
5. Explicit methodology disclosure (Category B): agents AND judges on a lite
   model; results not comparable to prior baselines; tokenizer/reasoning profile
   changed.

### STRICT $0 RECOMMENDATION

**Gemini 3.1 Flash-Lite, native path** — the only candidate that can serve the
full workload for $0 with existing credentials: 21–39% of RPD, TPM ~10% at paced
rate, ~12–26 min wall-clock, one rerun's headroom same-day.

### RELIABILITY RECOMMENDATION

Also **Gemini native**, with eyes open: its residual risks (dashboard-only quota
knowledge; possible unpublished TPD; lite-judge noise) are known, bounded, and
mitigable (§5.3, §8.5) — whereas Cerebras is not merely unreliable but *unavailable*
at $0, and Groq free tier remains token-cap-impossible (prior NO-GO). If the $0
constraint is ever lifted, paid Groq GPT-OSS-120B remains the zero-code-change,
strongest-judge option (prior report's GO) — noted for context, not acted on.

---

## Evidence

### Live commands executed (all from repo root; sanitized outputs below)

```bash
uv run --locked python probes/probe_cerebras.py                       # urllib attempt → Cloudflare 1010 (preserved as *-urllib-blocked.*)
uv run --locked python probes/probe_cerebras.py                       # openai-sdk transport (rewrite)
uv run --locked python probes/probe_gemini.py                         # full 5-step probe
uv run --locked python probes/probe_gemini.py --only replay --evidence-stem agent-memory/evidence/gemini-probe-2026-09-04-replay-fixed
uv run --locked python probes/probe_strands.py --provider gemini-compat   | tee agent-memory/evidence/strands-probe-gemini-compat-2026-09-04.txt
uv run --frozen --with google-genai python probes/probe_strands.py --provider gemini-native | tee agent-memory/evidence/strands-probe-gemini-native-2026-09-04.txt
uv run --frozen --with google-genai python -c '…'                     # google-genai 2.22.0 + strands extras (offline metadata)
git status --porcelain uv.lock pyproject.toml                          # empty — lockfile untouched
```

### Sanitized key outputs

```text
CEREBRAS (openai-sdk transport):
[1] models.list -> HTTP 200 (629.9 ms); catalog=3 models; gpt-oss ids=['gpt-oss-120b']
[2] completion -> HTTP 402 (203.0 ms); body={"message":"Payment required to access
    this resource. Visit your billing tab.","type":"payment_required_error",
    "param":"quota","code":"payment_required"}; response header x-should-retry: false
(urllib attempt, preserved): HTTP 403 "error code: 1010", Server: cloudflare — edge block, no API contact

GEMINI raw REST:
[1] GET /v1beta/models -> HTTP 200 (1342.1 ms); listed=54; flash-lite ids=[… 'models/gemini-3.1-flash-lite' …]
[1] quota-ish fields present in Models.list resources: ['inputTokenLimit', 'outputTokenLimit']
[2] generateContent -> HTTP 200 (1825.5 ms); text='OK'; usage 6/1/7; headers: X-Gemini-Service-Tier only (no quota headers)
[3] function round -> HTTP 200 (1558.4 ms); functionCall={"name":"get_balance","args":{"account_id":"ACC-1"},"id":"call_…"}; thoughtSignature present (156 chars)
[4] replay WITHOUT signature -> HTTP 400 "Function call is missing a thought_signature …"
[4] replay WITH verbatim part  -> HTTP 200 (2416.5 ms); text='The settled balance of account ACC-1 is 1000.25 USD.'; usage 123/19/142
[5] structured output -> HTTP 200 (3846.7 ms); schema-valid JSON: True; body={"verdict":"mismatch","amount":90.25}

STRANDS gemini-compat (OpenAIModel → /v1beta/openai/): turn 1 OK (tool_use), replay -> 400
    "missing thought_signature" via EventLoopException  [REJECTED PATH]
STRANDS gemini-native (GeminiModel + google-genai 2.22.0): wall_ms=5489.5
    tool_answered=YES; final="The settled balance of account ACC-1 is 1000.25 USD."
    git status of uv.lock/pyproject.toml: clean
```

### Request/token/latency ledger (this investigation)

| Provider | Requests | Statuses | Latencies | Notes |
| --- | --- | --- | --- | --- |
| Cerebras | 2 API (+1 edge-blocked) | 200, 402 (+403 edge) | 629.9 ms, 203.0 ms | no inference tokens possible |
| Gemini | 12 | 11×200, 1×400 (the captured finding) | 789–3847 ms | probe tokens: ~7+89+142+77+89+142 usage-total per evidence files |

### Documentation references (fetched 2026-09-04)

- Cerebras: inference-docs.cerebras.ai — `/support/rate-limits`, `/models/openai-oss`,
  `/support/change-log`, `/support/error`, `/api-reference/authentication`,
  `/resources/openai`, `/capabilities/tool-use`, `/capabilities/structured-outputs`,
  `/capabilities/reasoning`, `/console/usage-monitoring`, `/api-reference/metrics/retrieve-metrics`.
- Gemini: ai.google.dev/gemini-api/docs — `/rate-limits` (updated 2026-09-02; per-model
  table REMOVED), `/billing` (2026-09-03), `/models/gemini-3.1-flash-lite` (2026-07-21),
  `/api-errors`, `/troubleshooting`, `/thinking`, `/api/models`, `/api/generate-content`,
  `/openai` (compat layer), `/thought-signatures`; docs.cloud.google.com/service-usage
  `consumerQuotaMetrics.list` (OAuth-only).
- Local prior evidence: `agent-memory/groq-preflight-2026-09-04.md`,
  `agent-memory/gemini-feasibility-2026-09-04.md`,
  `agent-memory/gemini-quota-provenance-2026-09-04.md`,
  [SIBLING-B] `[SIBLING-B-INTERNAL]-model-loop-live-smoke-run3.txt:170,211`,
  ~/scratch-tests `validation-report.md` §2 (2026-08-28, Spanish-language bench; only
  its English error strings quoted here).

### Files changed by this investigation (additive only)

```text
probes/README.md                                   (new — isolation contract + usage)
probes/probe_common.py                             (new — env loader, redactor, HTTP capture, evidence writer)
probes/probe_cerebras.py                           (new — openai-sdk transport probe)
probes/probe_gemini.py                             (new — REST probe incl. verbatim-part replay)
probes/probe_strands.py                            (new — Strands idiom probes, 3 providers)
docs/provider-feasibility-cerebras-gemini.md       (this report)
agent-memory/evidence/cerebras-probe-2026-09-04{.json,.txt}                     (+ -urllib-blocked variants)
agent-memory/evidence/gemini-probe-2026-09-04{.json,.txt}                       (+ -replay-fixed variants)
agent-memory/evidence/strands-probe-gemini-{compat,native}-2026-09-04.txt
```

`git diff` summary (at close-out): additions only — 5 probe files, 1 report,
10 evidence files, 1 decisions.md entry; **no changes** to `agents/`,
`orchestrator/`, `tools/`, `evals/`, `tests/`, `scripts/`, `pyproject.toml`,
`uv.lock`, or any case data. The full evaluation was not run; the production
model was not switched; the benchmark methodology was not modified.

**STOPPED here, as instructed.**
