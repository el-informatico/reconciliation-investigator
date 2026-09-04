# reconciliation-investigator

- Start every session via `./scripts/ares-launch.sh` (args pass through),
  never `claude` directly — the wrapper is the Agent Teams enforcement
  point; the SessionStart hook is only a notice. The wrapper also
  enforces the concurrency governor at launch (below).
- Destructive or system-wide commands (docker prune family, powercfg/
  bcdedit/reg/wsl shutdown, recursive rm outside the repo, any sudo) are
  STRUCTURALLY BLOCKED by `scripts/guard-dangerous-commands.sh` (PreToolUse
  hook, exit 2 — genuinely prevents the call). This is a standing
  architectural property of Ares V2, not a convention: if a task seems to
  need such a command, hand it to the human to run directly — do not work
  around the guard.
- `contracts/openapi/*.yaml` are the source of truth (none exist in this
  stack — docs/build-contract.md is the product source of truth; treat it
  with contract discipline); contract changes are Tier C (Architect +
  human).
- Defining property — segregation of duties: the investigation agent
  analyzes disputed transactions and PROPOSES corrections but never
  executes them; `apply_correction` executes only on the separate
  `correction_executor` path, and only behind the `human_gate` approval
  step. It must never appear in any Strands `Agent(...)` tools list.
- That property is mechanically tripwired: `scripts/guard-segregation-of-duties.sh`
  (verify.sh step 2 + the git pre-commit hook, wired via
  `git config core.hooksPath scripts/hooks`) fails the build on an
  `Agent(` + `apply_correction` same-line violation; deliberate changes
  touching `apply_correction`, `correction_executor`, or `human_gate`
  are Tier C.
- `scripts/verify.sh` is the only authoritative end-to-end evidence.
- Concurrency governor: max 2 (`agent-memory/
  task-board.json`, inherited from aresV2 Phase 0) — ENFORCED at launch:
  `ares-launch.sh` refuses to start a session when live sessions for this
  repo already meet the value (counted statelessly from the process
  table; fail-open while the board carries no usable value, as at
  bootstrap before inheritance). The cap counts SESSIONS, not in-flight
  API calls — the board's original basis budgeted calls; the value is
  applied as a session cap because that is what a launcher can observe.

## Language Policy

All output from Claude Code in this repository must be in English:
source files, comments, commit messages, agent-memory reports and
decisions, AND conversational replies to the user in chat/terminal —
regardless of what language a prompt, a file, or the user's own message
is written in. This applies for the entire session, not just to the
task that first states it. If a user writes to you in Spanish, respond
in English and continue normally — do not treat it as a language-switch
instruction unless the user explicitly asks to change this policy.
