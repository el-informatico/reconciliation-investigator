# Provider feasibility report — the two Groq environments ([SIBLING-A] & [SIBLING-B])

**Date:** 2026-09-04 · **Status:** investigation complete; classifications in §15
**Scope:** controlled feasibility test ONLY. The 5-case evaluation was NOT run; the
application provider was NOT switched; prompts/judges/reasoning/max-token settings
were NOT changed; neither sibling was modified; no accounts, keys, billing, or
fallbacks were created. 9 tiny live requests consumed (5 + 4), all evidence
sanitized. Claude Code's own GLM-5.3 configuration untouched.

Headline (details and evidence below): **both Groq keys authenticate and infer
`openai/gpt-oss-120b` perfectly, with tool calling and replay verified — but they
are two keys into the SAME organization, i.e. ONE shared quota pool, and that
pool is the Free Plan: 30 RPM / 8K TPM / 1K RPD / 200K TPD. The full evaluation
(450–650K tokens) is 2.25–3.25× over the documented daily token cap → NO-GO for
$0. On Developer/PAYG the same endpoint serves the run in minutes for ≈
$0.10–0.17, but enabling PAYG is a human billing action that was not (and may
not be) performed here.**

---

## 1. Executive summary

| Environment | Auth | GPT-OSS 120B | Inference | Tool/replay | RPM | TPM | RPD | TPD | Billing | Full-run |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| [SIBLING-A] key | 200 | present | 200 OK | ✓ verified | 30 (docs) | 8,000 (header-measured) | 1,000 (header-measured) | 200,000 (docs) | Free plan (evidence §9) | **NO-GO at $0** / CONDITIONAL GO on PAYG |
| [SIBLING-B] key | 200 | present | 200 OK | ✓ verified | 30 (docs) | 8,000 (header-measured) | 1,000 (header-measured) — **SHARED pool with the other key (§7.3)** | 200,000 (docs) | Free plan (evidence §9) | **NO-GO at $0** / CONDITIONAL GO on PAYG |

The decisive facts, each independently evidenced:

1. Both keys work end-to-end (models.list 200; tiny completion 200 with usage;
   tool call exact; tool-result replay exact — §7).
2. **They are one environment, not two**: the org-level request counter moved
   across keys exactly as a shared pool predicts (remaining-requests 993 = A's 3
   + B's 3 + 1; §7.3), and Groq documents that "rate limits apply at the
   organization level", keys carry no independent quota. There is no second
   quota to exploit — and the rules (correctly) forbid trying.
3. A **label correction with provenance**: `x-ratelimit-limit-requests: 1000`
   is the **RPD** (daily) bucket, not RPM. Groq's docs say the `*-requests`
   headers "always refer to Requests Per Day"; the gateway proved it twice via
   the +86.4 s reset ladder (86,400 s ÷ 1000); today's probes reproduced the
   same ladder. The "1,000 requests/min" phrasing that appeared in earlier
   local notes (groq-preflight §5) was the gateway's own corrected-away
   misread (their D012 amendment, 2026-08-22) — this report retires it here too.
4. Free-tier daily capacity (TPD 200K, documented per-model) vs our workload
   (450–650K): **2.25–3.25× over** → the full 5-case run cannot complete for $0
   on either key (§10).
5. PAYG cost of the full run at current official prices ($0.15/M in, $0.60/M
   out): **≈ $0.10–0.14 typical, ≤ $0.17 worst-case** (§11) — but enabling it
   requires adding a payment method (human action, not performed).

## 2. Scope and security constraints

As instructed, and as enforced structurally by the probe suite
(`probes/README.md` isolation contract): credentials loaded only by NAME from
explicit `.env` paths into the probe process; no credential value, prefix,
suffix, length, hash, or other derived representation appears in any artifact
(this report, evidence files, commit, or terminal output); request headers are
never recorded (only response headers, which never carry the key); no `.env`
contents displayed; neither sibling modified (verified read-only access;
gateway `.env` mtime unchanged at 2026-08-22); no keys/accounts/billing
created; Claude Code's GLM-5.3 configuration untouched. An adversarial
post-investigation scan (§14) re-verified all of this against BOTH sibling
`.env` files and this repo's own `.env`.

## 3. Repository architecture findings relevant to provider integration

(Re-verified; unchanged since the 2026-09-04 Cerebras/Gemini report.)

- The app's single wiring point is `agents/model.py`:
  `OpenAIModel(client_args={"base_url": "https://api.groq.com/openai/v1",
  "api_key": GROQ_API_KEY}, model_id="openai/gpt-oss-120b",
  params={"max_tokens": 8192})` — the exact configuration these probes
  exercised (same endpoint, same model, same client SDK underneath strands).
- Consumers: 3 graph agents (`agents/detector_investigator.py:45`,
  `agents/classifier.py:39`, `agents/reporter.py:36`) and the judge model
  (`evals/run_evals.py:75`, `get_model(max_tokens=8192)`); driver
  `evals/run_sequential.py` strictly sequential; no app-level pacer (SDK
  retries only: strands 6×4–240 s + openai 2× nested).
- The repo's own `.env` holds exactly one variable name, `GROQ_API_KEY`
  (transferred file-to-file per the 2026-09-04 preflight; same-org behavior
  with both sibling keys is consistent in the shared counter, though key-value
  equality was never tested — and never will be).
- Strands-level Groq tool/replay was already validated TODAY on the repo's own
  key (`agent-memory/evidence/groq-replay-probe-2026-09-04.txt`: turn-1 tool
  call 474 in/71 out, turn-2 replay 1,160 in/144 out, 3.1 s total; strands
  strips `reasoningContent` on replay with a warning — the trap the gateway's
  Java driver handles manually in `TooledChatModel.replaySafe`).

**Strands compatibility verdict:** the existing Groq integration uses the
validated transport as-is. Zero changes to agent architecture, tool
definitions, prompts, judge criteria, reasoning settings, token limits, or
methodology are needed for Groq to serve the evaluation — the only blocker is
quota, not compatibility. (No provider switch was implemented in this task.)

## 4. Official Groq documentation evidence (fetched 2026-09-04)

| Question | Finding | Source |
| --- | --- | --- |
| Free Plan limits, `openai/gpt-oss-120b` | **RPM 30 · RPD 1K · TPM 8K · TPD 200K** (per-model; TPM is combined input+output; cached tokens excluded) | console.groq.com/docs/rate-limits (Free Plan tab; table read from the page's embedded `freeRows` payload) |
| Developer/PAYG limits, same model | **RPM 1K · RPD 500K · TPM 250K · TPD none listed** (daily caps raised, not lifted); paid-only `flex` service tier at 10× limits, same price | same page (Developer Plan tab, `devRows`); /docs/flex-processing |
| Pricing | **Input $0.15/M · cached input $0.075/M · output $0.60/M**; batch −50% (doesn't stack with caching) | console.groq.com/docs/model/openai/gpt-oss-120b (per-model docs page is the authoritative pricing source; /docs/pricing 404s) |
| Rate-limit headers | Six `x-ratelimit-*` headers on EVERY response (incl. success); `retry-after` (seconds) only on 429; **`*-requests` headers always = RPD, `*-tokens` always = TPM; no header exposes RPM or TPD** | /docs/rate-limits header table |
| Error semantics | Generic `{"error": {message, type}}`; 429 documented generically; **HTTP 402 does not exist in Groq's taxonomy** (spend-limit block = 400 `blocked_api_access`; suspension for failed payment has no documented code) | /docs/errors, /docs/spend-limits, /docs/billing-faqs |
| Billing | PAYG = provide a payment method, effective immediately; **no top-ups — in-arrears with $1/$10/$100/$500/$1000 invoice thresholds; "only bill once usage ≥ $0.50"** | /docs/billing-faqs |
| Quota attribution | **Organization level, never per key**; project sub-limits only restrict further (org ceiling always governs) | /docs/rate-limits, /docs/projects, /docs/model-permissions |
| Usage/quota API | **None documented** — exact org limits and usage are console-only (account-settings limits page; Dashboard → Usage) | /docs/api-reference, /docs/rate-limits |

Provenance labels: all rows DOCUMENTED (official pages, fetched live today).
Project-specific *effective* limits came from response headers (§8), which the
docs themselves define as RPD/TPM surfaces — a rare case where the provider
DOES expose the effective per-org limits programmatically, per response.

## 5. [SIBLING-A] Groq environment findings

- Credential: `GROQ_API_KEY` present in `../[SIBLING-A]/.env` (name
  confirmed; never displayed). The project's app uses it via raw fetch
  (`convex/proveedores.ts`: Groq primary, `openai/gpt-oss-120b`,
  `reasoning_effort: low`, `response_format: json_object`, 12 s timeout —
  context only; not touched).
- **Phase 1 (models.list):** HTTP 200 (899 ms); catalog 14 models;
  `openai/gpt-oss-120b` **present**.
- **Phase 2 (tiny completion):** HTTP 200 (549 ms); content exactly `OK`;
  usage 76 prompt + 54 completion (of which **44 reasoning tokens**) = 130
  total; `x-ratelimit-limit-requests: 1000`, `x-ratelimit-limit-tokens: 8000`,
  remaining 999 / 7471, resets `1m26.4s` / `3.967s`.
- **Phase 3 (tool + replay):** tool round HTTP 200 (557 ms), exactly one
  `get_balance` call with exact args `{"account_id":"ACC-1"}`; replay round
  HTTP 200 (437 ms) with the correct final answer. Header capture ran on every
  call (models.list itself returned no `x-ratelimit-*` headers — recorded as
  empty; every chat completion did).
- Rate-limit evidence: limits identical on every response (1000 requests-bucket
  = RPD per docs; 8000 tokens-bucket = TPM). Remaining-requests ladder:
  999 → 998 → 997 for this key's three chat calls (window refills at
  ≈ 86.4 s/request — the RPD signature).

## 6. [SIBLING-B] Groq environment findings

- Credential: `GROQ_API_KEY` present in `../[SIBLING-B]/.env` (name
  confirmed; never displayed; file untouched, mtime 2026-08-22). The gateway is
  a Java 21 / Spring Boot app (Spring AI 2.0.1 OpenAI starter →
  `https://api.groq.com/openai/v1`, model `openai/gpt-oss-120b`, max-tokens
  4096, no streaming; replay-safe stripping in `TooledChatModel.java:64-88`).
- **Phase 1:** HTTP 200 (1,033 ms); catalog 14; `openai/gpt-oss-120b` present.
- **Phase 2:** HTTP 200 (444 ms); content `OK`; usage 76 + 47 (37 reasoning) =
  123 total; limits 1000 / 8000; **remaining-requests 996 at its FIRST chat
  call** — the seed of the shared-org finding.
- **Phase 3:** tool call exact (200, 524 ms); replay correct (200, 488 ms).
  Response body carries `"service_tier": "on_demand"` (observed metadata;
  `flex` is the paid-only elevated tier, so `on_demand` is not by itself a
  billing indicator — Free plan responses show it too).
- Historical corroboration in the gateway's own evidence (read-only):
  - 2026-08-22 header captures under their key: limits 1000/8000 (twice), and
    the three-request ladder 999→998→997 with resets 1m26.4s→2m52.8s→4m19.2s
    from which their D012 amendment derived "limit-requests 1000 = RPD".
  - Real-run anchor: held-out eval 85 requests = 47,350 prompt + 8,408
    completion tokens in ~10.6 min (≈ 5.3K tok/min average), **no 429**; a
    same-day 180-request iteration ≈ 119.5K tokens, also no 429. **No Groq 429
    has ever been captured on this organization.**

## 7. Sanitized live-test evidence

### 7.1 Commands (from repo root)

```bash
uv run --locked python probes/probe_groq.py --env-file ~/projects/[SIBLING-A]/.env --env-tag [SIBLING-A]
uv run --locked python probes/probe_groq.py --env-file ~/projects/[SIBLING-B]/.env   --env-tag gateway
uv run --locked python -   # one-call org disambiguation (script inline, tee'd to groq-org-disambiguation-2026-09-04.txt)
```

### 7.2 Key outputs (sanitized; full records in evidence files)

```text
env=[SIBLING-A]: P1 200 (899ms) catalog=14 model present | P2 200 "OK" 130 tok (44 reasoning)
    headers: limit-requests 1000 / limit-tokens 8000; remaining 999/998/997; resets 1m26.4s→4m19.2s
    P3a 200 tool_call get_balance{"account_id":"ACC-1"} | P3b 200 correct final answer
env=gateway:   P1 200 (1033ms) catalog=14 model present | P2 200 "OK" 123 tok (37 reasoning)
    headers: limits identical; remaining 996/995/994 at first use; resets 5m45.6s→8m38.4s
    P3a/P3b identical success; response body service_tier "on_demand"
disambiguation: [SIBLING-A] follow-up call → remaining-requests 993
```

### 7.3 The shared-organization proof (no key values involved)

Prediction table (request counter is org-level per docs):

| Hypothesis | Expected remaining at A's follow-up call |
| --- | --- |
| Shared org (A's 3 + B's 3 + this 1 = 7 used of 1000) | **993** |
| Independent orgs (A's 3 + 1 = 4 used) | 996 |

Measured: **993** — shared organization confirmed. Corroborated by docs ("rate
limits apply at the organization level, not individual users"; no per-key
quota exists) and by the identical limit values. Consequence: the two
"environments" are two keys into one quota pool; switching keys changes
nothing about capacity (and splitting load across them to evade limits is both
impossible and forbidden).

## 8. Rate-limit evidence and provenance

| Limit | Value | Provenance for THESE keys |
| --- | --- | --- |
| RPM | 30 | DOCUMENTED (Free Plan table). Not header-exposed (no RPM header exists). Not re-measured — inducing 429s is out of scope. |
| TPM | 8,000 combined in+out | **ACCOUNT-SPECIFIC CONFIRMED via live response headers** (`x-ratelimit-limit-tokens`, present on every 200) — same value on both keys. |
| RPD | 1,000 | **ACCOUNT-SPECIFIC CONFIRMED via live response headers** (`x-ratelimit-limit-requests` = RPD per docs; the +86.4 s refill ladder reproduced today, matching the gateway's 2026-08-22 proof). |
| TPD | 200,000 | DOCUMENTED (Free Plan table). **No header exposes TPD; today's usage never approached it** — the 2026-08-22 gateway runs (~55.8K and ~119.5K tokens) stayed under it without a 429, so the cap is docs-sourced, not header- or 429-verified. |
| Plan (Free vs PAYG) | Free | Header limits equal the documented Free table exactly (PAYG would show 1K RPM/250K TPM headers instead); no PAYG/billing indicators in either repo; gateway decision D011 "no budget for a paid tier". |
| Console-only | exact org limits page, usage analytics, spend limits, invoices | No usage/quota API exists (docs). |

No 429 and no 402 occurred (nor were any induced). Groq has no HTTP 402 in its
documented taxonomy; if inference had been blocked we would have expected
400 `blocked_api_access` (spend limit) or 401/403 — none seen.

## 9. Free vs PAYG distinction

Both keys: **Free Plan** — with high confidence, on three independent signals:
(1) live headers show the Free table's 1000-RPD / 8K-TPM buckets (a Developer
org would surface 500K/250K in the same headers); (2) neither sibling repo
records any payment method, credit, or PAYG enablement (the gateway's D011
explicitly records "no budget for a paid tier"); (3) `"service_tier":
"on_demand"` is returned identically on Free (it is not a tier indicator;
only `flex` marks the paid elevated service). Residual uncertainty: only Groq's
console (browser) can show the account's plan page directly — classification
here is from non-secret provider evidence only, as required.

## 10. Workload calculations (workload: 105 / 125–150 / 195 requests; 450K / 500K / 650K tokens)

### Free Plan (both keys, one shared pool: 30 RPM · 8K TPM · 1K RPD · 200K TPD)

| Dimension | Requirement | Capacity | Verdict |
| --- | --- | --- | --- |
| Requests/day | 105–195 | 1,000 | ✓ 10.5–19.5% |
| Tokens/day | 450–650K (worst 800K) | **200K** | ✗ **2.25–3.25× over (4× worst)** — dispositive |
| Tokens/min | bursts to 10–15K per large evidence-bundle/judge call | 8K combined | ✗ single large calls exceed a full minute's bucket; sustained max ≈ 8K/min ⇒ ≥57 min (450K) to ≥81 min (650K) even at perfect saturation |
| Requests/min | sequential 20–60/min natural | 30 | ✗ binds during judge bursts (unpaced) |
| Wall-clock (if TPD allowed) | — | TPM-bound ≥57–81 min + throttle churn; strands' nested retries (6×4–240 s × openai 2×) stretch 429 storms badly | fragile |
| Retry impact | — | A 429'd request still consumes the attempt; blind retries waste the tiny daily pool | stop-on-429 discipline required |

**Free-tier conclusion:** the full 5-case run cannot complete in one day
(TPD 200K). Splitting: one case ≈ 90–125K tokens = 45–62% of TPD; at most one
case/day is safe, two is already at/over the cap → a 3–4+ day split run,
each day fighting 8K TPM on 5–15K-token calls — the exact L007-style fragility
the gateway engineered around (12 s pacing, 3-attempt backoff). Not a full-run
vehicle; **a ONE-CASE canary fits comfortably** (see §15).

### Developer/PAYG (1K RPM · 250K TPM · 500K RPD · no TPD)

Requests 105–195 = 0.02–0.04% of RPD; peak minutes ~15K tokens ≈ 6% of TPM;
sequential unpaced wall-clock ≈ **2–10 min** (measured 0.44–1.03 s/call
latencies; no pacer needed); retries immaterial. The only gate is enabling
PAYG — a human billing action (add a payment method), explicitly out of scope
for this task.

## 11. Cost calculations (PAYG; current official prices $0.15/M input · $0.60/M output)

Input/output split assumption: 85%/15% — anchored on the gateway's measured
85-request tool-loop eval (47,350 in / 8,408 out = 84.9/15.1) and consistent
with the repo's own workload estimate (graph ≈ 46K in / 5K out; judges ≈ 44K
in / 12K out per case). Reasoning tokens are completion (output-priced).
No caching discount assumed (judge prompts share rubric prefixes → cached
input at $0.075/M is upside, not banked). Retry overhead excluded (PAYG makes
retries rare).

| Scenario | Tokens (in/out) | Cost |
| --- | --- | --- |
| Minimum (450K) | 383K / 68K | **$0.098** |
| Typical (535K) | 455K / 80K | **$0.116** |
| Conservative max (650K) | 553K / 98K | **$0.142** |
| Worst-case cycling (800K) | 680K / 120K | **$0.174** |

Note: Groq bills in arrears and "only bills once usage has reached at least
$0.50" — a single full run at these prices may not even cross the first
invoice threshold by itself. No purchase was made; enabling PAYG is the
human's decision.

## 12. Strands / tool / replay compatibility

- Raw transport (openai SDK over the app's exact endpoint/model, the client
  strands uses): **both keys pass tool-call and tool-result replay with exact
  arguments and correct finals** (§5, §6, §7.2).
- Strands-level (the real event loop, streaming defaults, message-history
  replay, `reasoningContent` stripping): **validated TODAY** on the repo's own
  key (`groq-replay-probe-2026-09-04.txt`; 2 turns, 474/71 + 1,160/144 usage).
  The keys are org-identical, and auth/quota — not transport — is the only
  key-dependent variable, so this validation carries to both sibling keys.
- gpt-oss catalog capabilities under this org's key: `context_window 131072`,
  `max_completion_tokens 65536`, features `tools, json_mode,
  structured_outputs, reasoning` (gateway's 2026-08-22 capture + today's
  catalog).
- **Nothing about agent architecture, tools, prompts, judges, reasoning
  settings, or max-token configuration needs to change for Groq.** The
  application is ALREADY wired to Groq (agents/model.py); using either sibling
  key would at most be a `.env` value provisioning choice for the human — not
  performed here.

## 13. Comparison against Gemini 3.1 Flash-Lite

(Prior investigation: `docs/provider-feasibility-cerebras-gemini.md`; Gemini
native Strands tool/replay VALIDATED; limits 15 RPM / 250K TPM / 500 RPD are
dashboard-observed, not API-verifiable; possible unpublished TPD.)

| Criterion | Groq (either key — one org) | Gemini 3.1 Flash-Lite ([SIBLING-F]) |
| --- | --- | --- |
| Free vs paid | Free plan now; PAYG ≈ $0.10–0.17/run | Free tier, $0 |
| Confirmed quota | **Stronger**: limits live in every response header (RPD/TPM account-confirmed) + documented TPD/RPM | Weaker: dashboard-observed only; TPD unknown |
| Effective throughput | Free: 8K TPM / 30 RPM (binding) · PAYG: 250K TPM / 1K RPM | 250K TPM / 15 RPM (TPM never binds; RPM needs a ≤14 RPM pacer) |
| Requests/day capacity (free) | 1,000 (plenty) | 500 (21–39% used by a run) |
| Tokens/day capacity (free) | **200K — insufficient (2.25–3.25×)** | No documented TPD; run fits unless an unpublished cap exists |
| Tool/replay validation | ✓ raw (both keys) + ✓ strands (today) — same code path as the app | ✓ raw + ✓ strands native (today) — via NEW GeminiModel path |
| Quality / suitability | **Same model the app already uses** (gpt-oss-120b); like-for-like agents AND judges; nothing re-validated needed | Lite-class; probe-level correctness only; **judge quality unverified — a validity disclosure** |
| Methodological impact | **Zero** (already the configured provider) | Provider swap + pacer + tokenizer/reasoning-profile disclosure (Category A + B changes) |
| Implementation changes | None (key already wired; PAYG = billing toggle by human) | google-genai pin + model.py swap + credential wiring + pacer (plan in prior report §8) |
| Reliability risk | Free: TPD certainty kills full run; PAYG: minimal | Quota knowledge dashboard-grade; unknown TPD; lite-judge noise |
| Expected full-run cost | $0 (impossible) → **$0.10–0.17** on PAYG | **$0** |

## 14. Risks, unknowns, and security verification

- **Same-org conclusion** rests on counter arithmetic (993 exactly as
  predicted) + documented org-level quota semantics; it is not a key-value
  comparison (forbidden). Confidence high; a console view could make it
  definitive (browser-only, not attempted).
- **TPD 200K is docs-sourced**, never header-observed (no TPD header exists).
  The gateway's ~119.5K-token day ran clean under it; today's 9 requests are
  noise. If the real TPD were somehow higher, free-tier feasibility would
  improve — but the documented value is the planning basis.
- Remaining-day headroom on the shared pool is only partially observable
  (remaining-requests at probe time: ~993/1000 of the RPD bucket; token bucket
  refills in seconds) — TPD usage is console-only.
- Groq catalog drift is real (13 ids on 2026-08-22 → 14 today); `openai/
  gpt-oss-120b` present throughout, and its limits row is stable across both
  dates.
- Security verification: adversarial scan (delegated, fresh-eyes) re-ran
  key-shape regexes, exact-value equality against BOTH sibling `.env`s and
  this repo's `.env` (values loaded in-process, never printed), response-headers-only
  capture audit, tool-isolation audit (only synthetic read-only `get_balance`),
  and additive-only git-state check. Verdict: **CLEAN** — no secrets, no
  key-shaped strings, no derived representations of any secret (the
  `system_fingerprint` fields in captured response bodies are provider
  model-build identifiers, not key-derived), request headers structurally
  absent from all evidence, additive-only git state.

## 15. Final recommendation and classifications

Per the decision rule:

- **[SIBLING-A] Groq environment: CONDITIONAL GO** — inference,
  model, tool calling, and replay all verified; but it is Free plan in a
  shared org whose TPD (200K, documented) cannot carry the full run; full-run
  capacity exists only after a human billing action (PAYG), which was not and
  may not be performed here. As a **free-tier canary vehicle: GO** (one case
  ≈ 45–62% of TPD, 2–4% of RPD).
- **[SIBLING-B] Groq environment: CONDITIONAL GO** — identical results
  and identical limits; **not an independent quota** (same organization,
  §7.3). No advantage over the other key; using both to widen quota is
  impossible and prohibited.

Answers to the seven questions:

1. **Does [SIBLING-A]'s key work for inference?** Yes — 200 on
   models/completion/tool/replay under `openai/gpt-oss-120b` (headers, usage,
   latency captured).
2. **Does [SIBLING-B]'s key work for inference?** Yes — identically,
   verified live today.
3. **Which has the better effective quota?** Neither — same organization, one
   shared pool (proof §7.3; docs: org-level limits). Identical 1000-RPD /
   8K-TPM buckets on every response.
4. **Can either complete the full evaluation for $0?** No. Free tier daily
   tokens 200K (documented) vs 450–650K required — 2.25–3.25× over; splitting
   across ≥3–4 days remains TPM-fragile and is not a full-run path.
5. **Exact PAYG cost/quota situation?** $0.098 / $0.116 / $0.142
   (min/typ/max), $0.174 worst-case (§11); Developer limits 1K RPM / 250K TPM /
   500K RPD / no TPD; in-arrears billing with a $0.50 minimum invoice;
   enabling = human adds a payment method (not done).
6. **Best Groq option vs Gemini 3.1 Flash-Lite?** For a **$0 full run**:
   Gemini is the only viable candidate (Groq free cannot; Gemini fits with a
   pacer but carries the lite-judge disclosure). For **full-run quality and
   zero methodological change**: Groq PAYG at ≈ $0.12 — same model, same
   wiring, strongest judge, quota certainty from headers. The two occupy
   different corners: Gemini = $0 + methodology change; Groq PAYG = cents +
   zero change.
7. **First controlled canary?** **Groq free tier on the existing wiring, one
   case** (e.g., case C-1001): ≈ 21–39 requests (2–4% RPD), ≈ 90–125K tokens
   (45–62% TPD), zero code changes, zero new credentials, the exact
   production path, real-run anchor exists (gateway: 85 requests/55.8K tokens
   in ~10.6 min, no 429). Run it on a fresh day (RPD bucket refills
   continuously; TPD resets daily), with stop-on-429 reporting. The canary's
   results then inform the full-run provider decision (Gemini free vs Groq
   PAYG) with evidence instead of estimates.

STOPPED here, as instructed: no evaluation run, no provider switch, no
methodology change, no sibling modifications, no fallback, nothing purchased.

---

### Evidence index (all sanitized)

| File | Content |
| --- | --- |
| `agent-memory/evidence/groq-probe-[SIBLING-A]-2026-09-04.{json,txt}` | Phase 1–3 records + headers (env A) |
| `agent-memory/evidence/groq-probe-gateway-2026-09-04.{json,txt}` | Phase 1–3 records + headers (env B) |
| `agent-memory/evidence/groq-org-disambiguation-2026-09-04.txt` | the 993 shared-org measurement |
| `agent-memory/evidence/groq-replay-probe-2026-09-04.txt` | (prior today) strands-level Groq tool/replay validation |
| Gateway read-only citations | `[SIBLING-B-INTERNAL]/groq-generation-headers.txt`, `[SIBLING-B-INTERNAL].txt` (RPD ladder proof, D012 amendment), `[SIBLING-B-INTERNAL]heldout-eval/[SIBLING-B-INTERNAL]heldout-eval-live-run5.txt` (85-req real-run usage) |
| Official docs | console.groq.com/docs: rate-limits (Free/Developer tabs), model/openai/gpt-oss-120b (pricing), errors, billing-faqs, spend-limits, projects, model-permissions, flex-processing, batch |
