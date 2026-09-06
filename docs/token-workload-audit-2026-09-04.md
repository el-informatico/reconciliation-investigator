# Token-workload audit — agents vs judges (READ-ONLY, 2026-09-04)

**Question:** of the ~450K–650K tokens estimated for the full 5-case evaluation,
how much is consumed by the SYSTEM'S AGENTS (detector / classifier / loop /
reporter) versus the HARNESS'S LLM JUDGES (Trajectory / Output / ToolSelection /
ToolParameter; SafeAction is deterministic)?

**Method:** static analysis + inspection of existing artifacts only. Zero new
LLM calls, zero file modifications, zero commits. Evidence labels used:
MEASURED (in existing logs/artifacts/source constants), CALCULATED (derived
mathematically from measured data), ESTIMATED (assumption-dependent),
UNKNOWN (no evidence). Token figures are ESTIMATED conversions of MEASURED
character volumes at ~4 chars/token (sensitivity 3.5–5 ⇒ ≈ ±15–20%); no
per-call token usage was ever recorded by the eval runs (see §6).

---

## 1. Executive summary

- **The judges are the majority of the workload: ≈ 60–70% of tokens (central
  ~68%); the agents ≈ 30–40% (central ~32%).** Central estimate for a full
  5-case run: **agents ≈ 98–147K tokens, judges ≈ 215–350K tokens, grand total
  ≈ 315–500K (central ~375K)**.
- **A single evaluator dominates everything: `TrajectoryEvaluator` alone is
  ~35–50% of the ENTIRE workload** (central ~43%) — it embeds the full
  `str(Session)` repr (~100–137K chars per case, MEASURED from the preserved
  run-2 trajectories) **uncapped** into one judge prompt per case
  (strands-agents-evals 1.2.0; the package's 600K-char cap is on a code path
  this evaluator does not use).
- **Requests: MEASURED 136 in run 2** (49 agent inference calls + 87 judge
  calls) — inside the historical 105–195 envelope ("105 min / 125–150 typical /
  195 max"), which also anticipates judge extra rounds (forced structured
  output +1 per call; invalid-schema retries uncapped) and detector cycling.
- **The historical 450K–650K estimate is PARTIALLY VERIFIED** — plausible as a
  conservative envelope, likely high at the top: evidence-based central is
  ~375K; 650K requires cycling + retry amplification + verbose judges.
- **Split feasibility changes materially:** agents-only ≈ 98–147K tokens FITS
  the Groq free tier (TPD 200K) — so `Groq agents + Gemini judges` completes
  the run at $0, which all-Groq cannot (1.6–2.5× over TPD). An all-Gemini run
  also fits at these measured sizes; the split's specific value is keeping the
  already-validated gpt-oss agents untouched.
- Premise corrections found during the audit: run A (sequential) was
  **85.07% (57/67 rows), not "all 1.0"** — 2 of 5 cases aborted at the
  reporter with `MaxTokensReachedException` (the since-fixed max_tokens
  placement bug); and run 2 (the only run with stored trajectories) ran an
  **older graph topology** (4 agent invocations/case incl. a superseded
  provisional ticket) — agent-side numbers below are adjusted for the current
  3-invocation topology and labeled accordingly.

## 2. Workload breakdown — agents vs judges

| Segment | Requests | Input tokens | Output tokens | Total tokens | % of workload |
| --- | ---: | ---: | ---: | ---: | ---: |
| Agents (graph) | 42–49 (MEASURED 49 in run-2 topology) | 85–121K | 13–26K (incl. gpt-oss reasoning) | **98–147K** | **30–40%** (central ~32%) |
| Judges (4 LLM evaluators) | 87–100 (MEASURED 87 + 2 crashed rows in run 2) | 196–307K | 16–47K | **215–350K** | **60–70%** (central ~68%) |
| SafeActionCompliance | 0 (deterministic) | 0 | 0 | 0 | 0% |
| **Total** | **~136–150** | **~280–430K** | **~30–70K** | **~315–500K (central ~375K)** | 100% |

## 3. Agent breakdown

Request-count model (CALCULATED from the graph source + MEASURED run-2 spans):
each `Agent` invocation = 1 initial model call + 1 per tool-call round;
classifier has no tools (exactly 1 call); the eval driver runs
`detector ×R → classifier ×R → reporter ×1` with R = 1–3 (MEASURED in run 2:
R = 1 for all 5 cases — classifier confidence 0.90/0.90/0.95/0.93/0.72, all ≥
the 0.7 threshold, so the detector loop never actually re-fired in preserved
evidence).

| Component | Requests (5-case run) | Input tokens | Output tokens | Total | % of workload |
| --- | ---: | ---: | ---: | ---: | ---: |
| Detector (incl. its tool rounds) | ~15–20 (MEASURED run-2 inference spans: 49 total across all agents) | 40–60K | 4–8K | 45–70K | ~12–18% |
| Classifier | 5 (1/case, MEASURED) | 8–14K (1,350-char prompt + evidence bundle) | 2–4K | 10–18K | ~3–5% |
| Detector loop (rounds 2–3) | 0 in all preserved runs (MEASURED R=1; capacity 2×(detector+classifier)) | 0 observed; capacity ~+30–60K if cycling fires | — | 0 observed | 0% observed |
| Reporter | ~15–20 (1–2 invocations + draft/ticket tool rounds; run 2 had a dual-ticket path, current graph 1 pass) | 35–55K (histories grow to ~27K chars by late turns — MEASURED 26,799-char request) | 6–12K (case file ~5–6K chars + draft ~1K + ticket args ~2–2.6K chars, MEASURED) | 40–65K | ~11–17% |
| **Total agents** | **42–49** | **85–121K** | **13–26K** | **98–147K** | **30–40%** |

How the detector loop is reconstructed when logs don't isolate it: run-2
`invoke_agent` spans give per-invocation identity (MEASURED: 4 invocations/
case under the OLD topology = detector, classifier, correction path, final
ticket; the CURRENT graph is 3 = detector, classifier, reporter), and
`edge_classifier_to_detector` cycling is bounded by `MAX_INVESTIGATION_ROUNDS
= 3` (orchestrator/graph.py:59) — in all preserved runs the loop never
re-fired (confidence ≥ 0.72 ≥ 0.7), so "Detector loop" contributes 0 in
evidence and only capacity in planning.

## 4. Judge breakdown

Invocation semantics (verified against installed strands-agents-evals 1.2.0
source): Trajectory/Output run once per case; ToolSelection and
ToolParameter run **once per tool execution each** (MEASURED run 2: T = 42
tool executions → 35 (+1 crashed) ToolSelection rows and 42 ToolParameter
rows); every judge is a full Strands Agent whose structured output is forced
via a tool call (+1 model call minimum; invalid schema args retry uncapped);
the trajectory judge additionally calls scorer tools (+1 or more cycles).

| Evaluator | Requests | Input tokens | Output tokens | Total tokens | % of workload |
| --- | ---: | ---: | ---: | ---: | ---: |
| Trajectory | 5 (1/case) | **119–229K** (str(Session) 100–137K chars/case MEASURED + ~4.9K-char fixed template) | ~1–3K | **120–232K** | **~35–50% (central ~43%)** |
| Output | 5 | ~14K (5.6K-char fixed template + case input + actual output ~5.9K chars) | ~0.6K | ~15K | ~4% |
| Tool Selection | T = 42 (MEASURED) | ~29–34K (~2.1K-char fixed + ALL prior tool I/O, quadratic in T) | ~6.5K (MEASURED 25.8K chars of reasons) | ~36–40K | ~10% |
| Tool Parameter | T = 42 | ~29–34K (same input shape) | ~7.6K (MEASURED 30.4K chars) | ~37–42K | ~10% |
| SafeActionCompliance | 0 (deterministic — run_evals.py:130-189, zero model) | 0 | 0 | 0 | 0% |
| **Total judges** | **87–100** | **196–307K** | **16–47K** | **215–350K** | **60–70%** |

**TrajectoryEvaluator really does send the full trajectory / full tool I/O** —
`<Trajectory> = str(Session)` (the entire pydantic session repr: every
inference span's full message history, every agent's system prompt, tool
args, complete tool results), and it is NOT capped for this evaluator. At
MEASURED run-2 sizes that is ~100–137K chars (~25–34K tokens) **per case**,
which is why this one evaluator ≈ 43% of the whole run.

## 5. Token accounting

| Quantity | Agents | Judges | Total | Agents % | Judges % |
| --- | ---: | ---: | ---: | ---: | ---: |
| Input tokens | 85–121K | 196–307K | 280–430K | ~30% | ~70% |
| Output tokens (visible text) | ~8.5K | ~16K | ~25K | — | — |
| Output tokens (gpt-oss incl. reasoning, ×1.5–3 on text) | 13–26K | 24–47K | 37–73K | — | — |
| **Total tokens** | **98–147K** | **215–350K** | **315–500K (central ~375K)** | **30–40%** | **60–70%** |

Where the ranges come from: (a) MEASURED character volumes (run-2 spans:
451,260 chars of agent request messages over 49 requests + 33.5K chars of
system prompts; trajectory JSON 617,827 chars; tool-judge fixed templates
~2.1K chars × 84 calls + cumulative prior-tool I/O ~68K chars; judge reasons
62,637 chars); (b) the chars→token ratio 3.5–5 (ESTIMATED); (c) topology
adjustment for the current 3-invocation graph (−15–30% on agent inputs,
CALCULATED); (d) gpt-oss reasoning share of completion tokens 37–44 of 45–54
on MEASURED probe calls → ×1.5–3 output multiplier (ESTIMATED for real-task
mix); (e) judge extra rounds (forced structured output +1/call, scorer
cycles, uncapped schema retries) bounded as +0–15% (CALCULATED).

**Historical 450K–650K (STEP 9 verdict): option B — reconstructible, and the
reconstruction says: plausible conservative envelope, upper end high.**
Central evidence-based total ≈ 375K tokens; 450K is reached at the pessimistic
edge (5.0 chars/token impossible-low is not needed — rather: cycling firing +
judge verbosity + retry amplification); 650K additionally requires the
195-request worst case. Keep 450–650K as a planning envelope; use ~375K
(±20%) as the evidence-based central. Requests: MEASURED 136 (run 2) —
squarely consistent with 105–195.

## 6. Evidence quality

| Number | Label | Source |
| --- | --- | --- |
| 49 agent inference requests; 42 tool executions; per-request message volumes (581…26,799 chars; 451,260 total); 4 invocations/case; classifier confidences; per-case wall clock | **MEASURED** | `reconciliation_investigator_report.json` run-2 trajectories (spans with `messages`, `tool_call`, `tool_result`, `start/end_time`) |
| 87 judge calls (35+42+5+5); judge output chars 62,637 | **MEASURED** (calls) / **MEASURED** (chars) | same report `detailed_results` + run-A summary (`per_evaluator` 26/26/5/5/5 over 3+2 cases) |
| Trajectory-judge payload = uncapped `str(Session)`; per-tool judges embed all prior tool I/O; forced +1 structured-output round; uncapped schema retries; scorer-tool cycles; SafeAction deterministic | **MEASURED** (source code constants; labels CALCULATED where counting rules derived) | installed strands-agents-evals 1.2.0 (evaluator + prompt-template + trace-extractor sources) |
| Agent/judge TOKEN counts | **ESTIMATED** (measured chars × 3.5–5 chars/token) | this audit — **no per-call token usage exists in ANY artifact** (keyword sweep: zero usage/token/metrics fields; the SDK exposes usage — proven by `groq-replay-probe` TURN1/TURN2 dicts — but the eval runner never captured it) |
| gpt-oss reasoning share 37–44 / 45–54 completion | **MEASURED** (tiny probes only) → output multiplier ×1.5–3 on real tasks is **ESTIMATED** | `groq-probe-*.json` `reasoning_tokens` |
| Current-topology agent share (3 vs 4 invocations) | **CALCULATED** | graph.py topology vs run-2 spans |
| Detector-loop contribution | **MEASURED 0** (R=1 in all preserved runs); capacity ~+30–60K tokens **ESTIMATED** | run-2 confidences vs threshold 0.7 |
| Per-case per-component split (exact detector-vs-reporter token boundary) | **UNKNOWN** (spans are per-inference, not per-agent-role labeled; attribution done by message-shape heuristics) | — |
| `runtime/consumed_tokens.jsonl` | NOT LLM data — human-gate consumed approval-jti store (2× 32-hex ids) | read: 66 bytes |

## 7. Split simulation (no model executed)

| Scenario | Groq tokens | Gemini tokens | Groq free tier (30 RPM / 8K TPM / 1K RPD / 200K TPD) | Gemini free tier (dashboard: 15 RPM / 250K TPM / 500 RPD) | Verdict |
| --- | ---: | ---: | --- | --- | --- |
| **All Groq** | 315–500K (central 375K) | — | TPD exceeded **1.6–2.5×**; even agents+judges requests OK (136 ≤ 1K RPD) but 8K TPM also throttles the ~27K-char reporter turns | — | **NO-GO at $0** (matches D-2026-09-04-13); PAYG cost at measured sizes ≈ **$0.06–0.13 (central ~$0.08)** at $0.15/$0.60 per M |
| **Groq agents + Gemini judges** | **98–147K** (49–74% of TPD; RPM/TPM fine with ~8–12 s spacing on big reporter turns) | **215–350K** (92–105 requests = 18–21% of RPD; biggest single call = trajectory judge ~25–34K tokens = 10–14% of TPM; ~7 min floor at 15 RPM) | fits, one full run/day + headroom | fits on RPM/TPM/RPD; **residual: unknown TPD** (if an unpublished TPD near the low end exists, 215–350K could brush it) | **$0 completion path** |
| (reference) All Gemini | — | 315–500K | — | fits similarly; changes BOTH agent and judge models | $0, single provider, larger agent-side methodology change |

## 8. Recommendation

**GO WITH VALIDATION** for the split strategy (`gpt-oss-120b/Groq → agents`,
`gemini-3.1-flash-lite → judges`), with three explicit conditions:

1. **Methodology disclosure (must):** judges run on a different, weaker model
   than the agents — the measurement instrument changes (lite-judge noise),
   token-denominated numbers shift by tokenizer, and the run is
   mixed-provider by design (distinct from the rejected *mid-run fallback*:
   here the assignment is fixed and declared up front). Every result row must
   carry this label.
2. **One instrumented canary case before any full run:** persist the
   per-request usage the SDK already exposes (proven by
   `groq-replay-probe` TURN1/TURN2 usage dicts) for agents and judges —
   ~21–27 requests, ~30–45K tokens, fits both free tiers — replacing this
   audit's ±20% ESTIMATED split with exact MEASURED per-component tokens.
3. **Quota pre-checks on the day:** Groq RPD/TPD pool freshness (headers
   expose it live) and the Gemini dashboard (RPM/TPM/RPD + whether any TPD
   row exists — the one number no API can give).

Honest counterpoint from the same evidence: at MEASURED sizes the whole run
on Groq PAYG costs ≈ **$0.08** with zero code and zero methodology change —
if strict-$0 is not a hard constraint, that remains the lowest-complexity
path; the split's value is specifically the $0 constraint plus keeping the
validated gpt-oss agents in place.

## 9. Files inspected (evidence base)

**Repo code (read):** `evals/run_sequential.py`, `evals/run_evals.py`,
`orchestrator/graph.py`, `agents/{detector_investigator,classifier,reporter}.py`,
`agents/model.py`, `tools/{legacy_system,modern_system,transactions}.py`,
`evals/cases.py` (via measurement script), `probes/README.md`.
**Installed SDK (read, via subagent):** `strands_evals/evaluators/*` (4 LLM
evaluators), `prompt_templates/*` (fixed template sizes),
`extractors/trace_extractor.py`, `mappers/strands_in_memory_session_mapper.py`,
`tools/evaluation_tools.py`, `structured_output_tool.py`, `experiment.py`,
`strands/event_loop/*` (retry + forced-round mechanics).
**Artifacts (read):** `reconciliation_investigator_report.json` (4.2 MB run-2
trajectories — the primary measured source), `reconciliation_investigator_evaluation.json`,
`agent-memory/evidence/evals-sequential-results-2026-09-04.json` (run A),
`evals-sequential-2026-09-04.txt`, `evals-sequential-final-2026-09-04.txt`,
`evals-run3{c,d,e}*.txt`, `evals-run4-official.txt`,
`verify-full-2026-09-04-run2.txt`, `groq-replay-probe-2026-09-04.txt`,
`groq-probe-{[SIBLING-A],gateway}-2026-09-04.{json,txt}`,
`runtime/{consumed_tokens,drafts,tickets}.jsonl` (inventory + sizes;
consumed_tokens read: gate store, not LLM).
**Measurement scripts (created OUTSIDE the repo in /tmp, nothing in the repo
modified):** prompt/tool-spec/case/tool-output char measurements; installed
type introspection. No `.env` was opened; no LLM call was made; nothing was
committed.

**Missing datum and the minimal measurement to get it (not executed):** exact
per-component token counts. Minimal sufficient measurement: run ONE case
with a usage-capturing callback (or read `result.usage` per agent call and
per judge Agent) and persist a per-request usage JSONL — ~21–27 requests,
~30–45K tokens, within both free tiers' daily budgets. That single
instrumented case converts every ESTIMATED row above into MEASURED.
