# deploy/ — AWS Bedrock AgentCore (PLACEHOLDER)

**Status: deliberately not implemented in this pass.** This directory is
a documented placeholder so the repo layout matches the build contract
from day one; nothing here deploys anything. The deferral is recorded in
this repo's `agent-memory/decisions.md` (bootstrap entry, 2026-09-04).

## What exists now

This README only. No deployment automation, no AgentCore runtime wiring,
no CI/CD.

## What a real implementation must decide (do NOT treat as done)

- The agent entrypoint module the runtime invokes, and its packaging.
- The AgentCore integration package and its CURRENT version — live-verify
  from PyPI/GitHub at the time of implementation; never carry a number
  from this file (there is none, on purpose).
- AWS credentials and region setup — human-provided and human-run; an
  Ares session never invents or stores cloud credentials. Note the
  standing model-credential policy (2026-09-04, `agents/model.py`): the
  Z.AI credential is reserved exclusively for Claude Code — never for
  this application — and the application itself uses GROQ_API_KEY only.
  That policy governs model access and is unaffected by infrastructure
  credentials, which remain a human decision.
- Whether EVAL_MODE applies in deployed environments at all (deployed
  runs presumably want real systems — that is the contract owners'
  call, Tier C).

Changes under `deploy/` follow the normal OCM gate; anything touching
`apply_correction`, `correction_executor`, or `human_gate` is Tier C
regardless (see the task contract's rule table).
