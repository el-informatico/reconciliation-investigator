# Devpost submission draft — project description

**Status: DRAFT text for the submission form. Nothing here has been submitted;
no demo video exists.** Built for paste-in use field by field. Keep the pitch
text free of unlabeled numbers: every measured figure lives in
[`docs/EVALUATION.md`](EVALUATION.md), which is linked rather than restated.

---

## Tagline / one-liner

> An autonomous reconciliation investigator that can dig through the money —
> and structurally cannot touch it. Corrections require a human-approved,
> cryptographically signed, case-scoped, expiring, single-use capability
> token.

## Description (main text)

Every night, two systems that are supposed to agree — a legacy ledger and a
modern one — drift apart. Reconstructing what happened to a customer's balance
is slow, evidence-heavy detective work: export data, compare records, dig
through transaction history, find the root cause, document it, and only then
— if a correction is warranted — get a human to approve it.

**Reconciliation Investigator** does the investigation autonomously and
produces a complete, evidence-backed case file. What makes it different is not
the investigation quality (though it is measured and published honestly — see
[`docs/EVALUATION.md`](EVALUATION.md)) — it is the **safety architecture**:

**The agent can investigate the money. It cannot touch the money.**

This is an access-control system, not a prompt-level policy. The tool that
writes to the financial system (`apply_correction`) is never registered on any
LLM agent — it is a plain Python function whose only caller is a deterministic
executor that runs after a human has explicitly approved a specific correction.
No agent in this system can apply a correction even if it "decided" to; the
write path does not exist for it. That invariant is enforced three
independent ways: tool registration sets asserted by tests, a mechanical
grep tripwire wired into both the build and the pre-commit hook, and an
eval-time safe-action compliance check that fails any trajectory that so
much as touches the write tool.

Approval itself is capability-based: a human decision mints an
HMAC-SHA256-signed token scoped to one case, one field, one new value, with a
10-minute expiry and single-use (replay-rejected) semantics, and the executor
validates the token before applying anything. Every decision — approve,
reject, request-more-info — lands in an append-only audit trail, and the
executor records before/after values when a correction is applied.

## How we built it

- **Agents:** three reasoning agents on a cyclic Strands Agents SDK Graph —
  a detector/investigator (four read-only query tools), a root-cause
  classifier (no tools — pure reasoning over the evidence bundle, with a
  3-round investigation cap), and a reporter (drafts corrections and case
  tickets only). Models: Groq `openai/gpt-oss-120b`.
- **Evaluation:** the four LLM-judged eval dimensions run on native Strands
  `GeminiModel` (`gemini-3.1-flash-lite`), deliberately split from the agent
  provider; a fifth evaluator (safe-action compliance) is deterministic.
- **Resilience:** a narrow, bounded retry for exactly one provider failure
  signature (Groq's in-stream "Parsing failed" rejection), leaving stock
  throttle-retry behavior untouched.
- **Data:** five seeded discrepancy scenarios (reversal not propagated,
  duplicate transaction, sync lag, manual override, data-entry error) served
  through an `EVAL_MODE` seed layer with a read-your-writes overlay — the
  frozen seed is hash-asserted immutable.

## Challenges we ran into

The honest list:

1. **Provider instability** — Groq intermittently rejects an in-stream model
   output with a parse error. We answered it with a deliberately narrow retry
   (one exact failure signature, bounded attempts) and validated it live.
2. **Free-tier quotas** — we measured, not guessed: a full run needs more
   tokens than the free tier allows, which drove the Groq-agents +
   Gemini-judges split.
3. **The hardest one: we found a ground-truth leak in our own eval harness.**
   The seed scenario — the answer key — was reaching the agents' prompts
   verbatim. Every accuracy number we had previously recorded was an
   upper bound, not a measurement. We removed the leak (three separate
   channels), added regression tests, threw out every contaminated figure,
   and re-measured from zero. The clean baseline and the full story are in
   [`docs/EVALUATION.md`](EVALUATION.md).

## Accomplishments we're proud of

- A safety invariant that holds by construction — enforced in tool
  registration, mechanically tripwired in the build, and independently
  checked at eval time — not promised in a system prompt.
- Finding and fixing our own evaluation leak before anyone else could, and
  publishing the contaminated-figure list rather than quietly moving on.
- An evaluation doc that labels every claim (MEASURED / CALCULATED /
  OBSERVED / DOCUMENTED / PROJECTED / UNKNOWN) and names its own open
  limitations: a known tool-parameter fabrication pattern and a
  single-run (not-yet-a-rate) accuracy baseline.

## What we learned

That "the agent is not allowed to" is a prompt statement, but "the agent
cannot" is an architecture. Getting the second costs more design discipline
but survives adversarial agents, prompt injection, and your own future
mistakes. Also: the most valuable eval harness feature is the willingness to
invalidate your own headline numbers.

## What's next (explicitly unfinished — also listed in docs/EVALUATION.md)

- The polished end-to-end human-approval demo surface (the gate, tokens, and
  executor are implemented and tested at the code level; the UI is not built).
- The standalone architecture-diagram artifact required by the hackathon
  rules.
- The demo video (not recorded — shot-list draft below).
- Repeated clean runs to turn single data points into rates; remediation of
  the tool-parameter fabrication pattern.

## Built with

Python 3.13 · Strands Agents SDK · Strands evals · Groq (`openai/gpt-oss-120b`)
· Google Gemini (`gemini-3.1-flash-lite`, judging) · uv

---

## Demo video shot list (DRAFT PROSE — no video has been recorded)

Nothing below has been filmed; this is a plan for a future recording session.
Every shot shows something that actually exists in the repository today.

1. **Cold open — the problem.** Terminal + editor on
   `data/seed_transactions.json`: two mock systems, five seeded discrepancies.
   Narration: the nightly drift problem, and the one rule that matters — the
   investigator never writes.
2. **The architecture.** Walk the README flowchart into the code: cyclic
   Strands Graph, detector → classifier (3-round cap) → reporter; Groq agents
   on `openai/gpt-oss-120b`; Gemini judges kept on a separate provider.
3. **The invariant, proven three ways on screen.** (a) The detector's tool
   list — four read-only tools; classifier `tools=None`; reporter draft +
   ticket. (b) `apply_correction` as a plain function with a single caller
   (the executor). (c) Plant a violating line in a scratch file and let
   `scripts/guard-segregation-of-duties.sh` fail the build live; show the same
   guard wired into the pre-commit hook.
4. **The human gate.** Screen: `orchestrator/human_gate.py` — token payload
   (case, field, new value, expiry, jti), HMAC-SHA256 signing,
   constant-time verification. Then run the offline gate/executor tests to
   show expiry and replay rejection failing closed on screen.
5. **A live investigation.** Run the 5-case benchmark command in a terminal
   (real Groq + Gemini calls); open a produced case file — evidence,
   root cause, drafted correction awaiting approval.
6. **Honest results.** Screen: `docs/EVALUATION.md`. Narration: the clean
   baseline is a single observed data point, not a rate; the eval-leak
   discovery story; the named open limitation (fabricated tool parameters).
7. **Close — what's unfinished.** The remaining-work list on screen: approval
   UI, diagram artifact, this video. End on the thesis line: "The agent can
   investigate the money. It cannot touch the money."
