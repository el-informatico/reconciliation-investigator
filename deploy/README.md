# deploy/ — AWS Bedrock AgentCore deployment PLAN

**Status: PLANNED — nothing in this directory deploys anything.** Upgraded
from a bare placeholder to this concrete plan on 2026-09-09; the deferral
itself dates to the 2026-09-04 bootstrap (agent-memory/decisions.md,
local-only since the 2026-09-07 history excision). Implementation is a
separate human-gated task that executes against this plan. Every code
anchor below was verified against the tree on 2026-09-09; anything marked
OPEN is a decision this plan names but does not make.

## 0. Standing constraints (inherited, non-negotiable)

- **Segregation of duties is load-bearing:** `apply_correction` executes
  only inside `orchestrator/correction_executor.py`, behind
  `orchestrator/human_gate.py` — never registered on any LLM agent. No
  deployment shape may change that, and any change touching
  `apply_correction`, `correction_executor`, or `human_gate` — including
  the gate-integration decision in §1.1 — is Tier C (Architect + human).
- **The root manifest stays build-system-free** (virtual uv project —
  see the pyproject.toml header): deployment packaging lives under
  `deploy/` and must never retrofit `[build-system]` or a src/ layout
  into the root.
- **No credentials in the repository.** Cloud and model credentials are
  human-provisioned and human-run. The standing model-credential policy
  (2026-09-04, recorded in `agents/model.py`) is unaffected by
  infrastructure credentials: the application itself uses `GROQ_API_KEY`
  only.
- **`scripts/verify.sh` remains the authoritative end-to-end evidence**;
  CI (`.github/workflows/ci.yml`) covers only the offline suite — live
  steps stay out of CI.

## 1. Entrypoint (what a deployed runtime invokes)

- The deployable unit is the investigation spine plus the deterministic
  gate/executor path, already composed by ONE function:
  `orchestrator.graph.run_case_with_gate(instruction, *, case_id,
  decide, ...)` (`orchestrator/graph.py:313`) — "the single entry point
  the approval UI composes with". The AgentCore handler is a thin adapter
  over it, never a second orchestration path.
- New module (unbuilt): `deploy/agentcore/handler.py`, exposing an async
  streaming entry function per the AgentCore Runtime handler contract
  (JSON request in, async iteration of JSON events out). The exact SDK
  import/decorator names and package version are LIVE-VERIFIED from
  PyPI/GitHub at implementation time — never carried from this file (the
  placeholder's rule stands: there is deliberately no version here).
- Handler responsibilities, in order:
  1. parse `customer_id`/`case_id` and the instruction from the request
     (case ids are canonicalized inside `run_case_with_gate`);
  2. build the `decide` callback (§1.1);
  3. call `run_case_with_gate` and stream the verdict + gate/executor
     outcome as events.
- **§1.1 The `decide` callback (gate integration) — OPEN, Tier C.** In
  the dev surfaces the callback is a human at `approval/cli.py` or
  `approval/web.py`. Candidate deployed mechanisms: (a) AgentCore's
  human-in-the-loop pattern (pause the runtime, resume on decision), or
  (b) an approval surface operating against the same runtime stores,
  reached out-of-band. This plan does NOT choose. Hard requirements
  either way: no deployed `decide` ever auto-approves, and the token and
  executor semantics of `human_gate.py` / `correction_executor.py` are
  reused verbatim, never reimplemented.

## 2. Packaging

- `deploy/agentcore/pyproject.toml` (new, unbuilt) — its own manifest,
  so the root stays virtual. Runtime Python 3.13 (matches
  `.python-version` and `requires-python`).
- Application dependencies: `strands-agents` and `openai` (Groq
  OpenAI-compatible endpoint, `agents/model.py`), pinned at
  implementation time to the then-current verified set and locked;
  plus the AgentCore runtime SDK (§1 version rule). Judges are
  evaluation-only and are NOT deployed.
- `data/seed_transactions.json` ships only in EVAL_MODE deployments (§4).

## 3. Credentials (human-provisioned, human-run)

- `GROQ_API_KEY` — required by every variant (all three agents run on
  Groq in every configuration). Injected as an AgentCore
  secret/environment variable, least-privilege; never in code, never in
  this repository.
- `CORRECTION_TOKEN_SECRET` — required ONLY when the gate runs outside
  EVAL_MODE (`orchestrator/human_gate.py` falls back to the committed
  dev key in EVAL_MODE). A separate secret, provisioned if and only if
  §1.1 lands a production gate path.
- AWS credentials/region: the deploying human's IAM identity; deployment
  commands are human-run — an agent session never invents or stores
  cloud credentials.

## 4. EVAL_MODE decision

The contract owners' call (Tier C) — this plan frames the decision
rather than making it:

- **D1 (hackathon demo): `EVAL_MODE=1`.** Real-system access is not
  implemented (`tools/seed_data.py` refuses every other mode), so
  EVAL_MODE=1 — frozen seed data, public dev signing key — is the only
  runnable variant today. Acceptable ONLY as a demo of the topology, and
  the endpoint must label it as such.
- **D2 (production): not deployable yet.** Requires (a) real-system
  adapters behind the four read tools and the write target (unbuilt
  contract work), (b) `CORRECTION_TOKEN_SECRET` provisioning, (c) the
  §1.1 gate-integration ruling, (d) durable stores (§5). All four are
  prerequisites, not options.

## 5. State and stores (ephemerality warning)

All case state is local JSONL under `runtime/` — drafts, tickets,
overrides, `audit_log.jsonl`, `consumed_tokens.jsonl` (see the README
repo-structure map). A serverless runtime's local disk is ephemeral:
single-use token consumption and the audit trail would NOT survive
instance recycling. D1 accepts this (demo lifetime = one warm session).
D2 requires moving the stores to durable storage — which touches
executor/gate persistence assumptions and is therefore Tier C alongside
§1.1.

## 6. What this plan deliberately does not decide (OPEN list)

1. §1.1 gate-integration mechanism (Tier C).
2. Durable-store backing for D2 (Tier C, §5).
3. AgentCore SDK version and handler symbol names (implementation-time
   verification, §1).
4. Region, account, and network topology (the deploying human's, §3).
