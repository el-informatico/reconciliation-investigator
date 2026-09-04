# Research prompt — compliant model access for our application's eval harness

Copy everything below the line into Claude Sonnet (with web search
enabled). It contains everything needed: what we're building, the tech
stack, exactly how the non-compliant usage works today, and the
specific questions to answer with sources.

---

I need you to research (with web search) and recommend a compliant,
cheap way to run LLM calls for our application's automated evaluation
harness. Please verify current facts against live web sources (2026)
and cite each one — do not rely on memory.

## Context — what we are developing and testing

We are building "Reconciliation Investigator" for the Agents for Humans
hackathon (Professional Agents track, submission deadline Sep 14, 2026):
a multi-agent financial-reconciliation system where an investigation
agent gathers evidence from two mocked systems, a classifier assigns a
root cause, and a reporter drafts corrections — with a hard
segregation-of-duties invariant (the write tool is never given to any
LLM agent; corrections require a signed, human-issued approval token).

Tech stack:
- Python 3.13 on WSL2 (Ubuntu 24.04), package management via uv
  (pinned, locked).
- **Strands Agents SDK** (`strands-agents==1.54.0` from PyPI, by AWS)
  — three agents wired in a cyclic **Strands Graph** (detector →
  classifier → detector loop with a 3-round cap → reporter).
- **strands-agents-evals==1.2.0** — evaluation harness: 5 synthetic
  test cases × 5 evaluators (Trajectory/Output/Tool-selection/
  Tool-parameter judges are LLM-judged; a deterministic
  SafeActionCompliance evaluator checks that no unauthorized write
  action was ever attempted).
- Each full 5-case eval run makes roughly **80–100 LLM calls**
  (each graph case ≈ 10–15 agent turns with growing evidence-bundle
  context, plus ~20 judge calls). Until the hackathon deadline we
  would run it a few times per day (~10 days left), plus a live demo.

## The problem — how the LLM is accessed today (non-compliant)

Our development environment is **Claude Code** (the CLI coding agent),
legitimately configured with a **Z.AI Annual Pro Legacy subscription**:
- `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic` (Z.AI's
  Anthropic-protocol gateway)
- `ANTHROPIC_API_KEY` = the Z.AI subscription key
- Claude Code itself therefore runs on **GLM-5.3** — this usage is
  fine and must stay.

The violation: our application's eval harness ALSO points at that same
key/endpoint. In code, `agents/model.py` does:

```python
from strands.models.anthropic import AnthropicModel
AnthropicModel(
    client_args={"base_url": os.environ["ANTHROPIC_BASE_URL"],
                 "api_key": os.environ["ANTHROPIC_API_KEY"]},
    model_id="glm-5.3",
    max_tokens=8192,
)
```

i.e. the Strands SDK → `anthropic` Python SDK → Z.AI's
Anthropic-compatible endpoint with the subscription key. Z.AI's policy
for this plan allows the key for Claude Code (agentic coding tools),
**not** for arbitrary application API calls — so this must stop (we
already stopped it; ~300–400 calls were consumed before we caught it).

## What I need you to find out (verify with sources, 2026-current)

1. **Z.AI policy facts**: What exactly does Z.AI's current
   subscription-plan policy (especially "Annual Pro Legacy" /
   GLM Coding Plan tiers) permit for API-key usage — Claude Code and
   similar coding agents only, or also general API/app usage? Cite the
   policy pages. Is there a way to LEGITIMATELY run app-level calls on
   any Z.AI plan (separate API platform key, pay-as-you-go API tier,
   etc.)? What would it cost at our volume (~100 calls/run, ~2–3 runs
   per day for 10 days, plus one demo; inputs up to ~10–20k tokens,
   outputs up to ~8k)?
2. **Best alternatives for the app/eval workload** usable from the
   Strands SDK. The SDK ships model providers including: Anthropic
   (anthropic SDK), OpenAI, **LiteLLM** (any OpenAI/Anthropic-compatible
   provider), Ollama (local), Bedrock, and more. Compare realistic
   options for a hackathon-scale budget, e.g.: Z.AI API platform (if
   allowed), OpenRouter (GLM or comparable open models), other
   GLM-4.x/GLM-5 hosts, DeepSeek/Qwen-class cheap API models via an
   OpenAI-compatible endpoint (LiteLLM path), and local Ollama (we
   have a laptop with ~8GB RAM free — is any local model good enough
   for (a) the tool-calling agents and (b) the LLM judges?). Judge
   quality matters: judges score root-cause correctness and tool-choice
   justification.
3. **Model-fit note**: our agent prompts were written against GLM-5.3
   behavior. Which alternatives preserve quality for multi-turn
   tool-calling + strict-JSON classifier outputs? Any known
   tool-calling quirks with LiteLLM-routed models on Strands?
4. **Clean credential separation** on WSL2 so this can never happen
   again by accident: recommended pattern so Claude Code keeps the Z.AI
   key while the app reads a DIFFERENT env var/key (e.g. per-process
   env, direnv, a `.env` the app loads that never contains the Z.AI
   key, wrapper that strips ANTHROPIC_* for app processes). Concrete
   setup steps.
5. **Deliverable**: a comparison table (provider/plan, compliance,
   setup path from Strands, cost estimate for ~3k–5k calls total, judge
   quality risk) and ONE concrete recommendation with exact setup
   steps for our stack.

Constraints: no Anthropic API (we have no Anthropic account); secrets
only in env vars, never committed; Claude Code itself stays on the
existing Z.AI key; we need a working eval run again before Sep 14.
