# System Reference — reconciliation-investigator

**An engineering reference for maintainers and future agent sessions.**
State as of **2026-09-06**, git HEAD **`f4b2ff8`** on `main` (in sync with
`origin/main`). Offline suite at this HEAD: **218 passed** (MEASURED during
this document's compilation, `uv run --locked pytest -q`, 8.22 s, zero
git-status delta — see §8).

This document describes the system **as the current source shows it**. Every
factual claim is traceable to `file:line` at the HEAD above or to a cited
`docs/` report. It complements — never replaces — three existing layers:
`docs/build-contract.md` (the product source of truth), `README.md` /
`docs/EVALUATION.md` (submission-facing narrative and results), and the dated
reports under `docs/` (primary evidence; indexed in §6).

---

## 0. How to read this document

### 0.1 Verification basis

Compiled 2026-09-06 by direct code inspection at `f4b2ff8`: four parallel
read-only investigation passes (agent-side architecture; documentation corpus;
tests and verification; control-path security), followed by per-citation
re-verification of every load-bearing claim against the source files
themselves. Nothing was executed live; no benchmark, canary, or LLM/API call
was made; no credential value was read.

### 0.2 Claim taxonomy

This document uses the project's established taxonomy, with **the exact senses
declared below** (the corpus uses two different senses of OBSERVED — see the
note — so this document pins one):

- **MEASURED** — a command was executed and its output recorded during this
  document's compilation (e.g. the offline suite run, greps, `git` reads).
- **OBSERVED** — directly seen in repository files/source at HEAD `f4b2ff8`
  during this document's inspection.
- **DOCUMENTED** — stated in a cited project report; relayed, not re-derived
  here beyond what the citation shows.
- **CALCULATED** — arithmetic over MEASURED/OBSERVED values.
- **UNKNOWN** — not determinable from available evidence.
- (No PROJECTED claims are made in this document.)

Corpus note: some source reports (e.g. the case-4 reverification) use
"OBSERVED" to mean *single-run observation, no rate implied*; others (e.g.
`docs/EVALUATION.md` §0) use it to mean *seen in repo files*. This document
always means the second (repo-file) sense. Single-run figures inherited from
reports are labeled per the source report's own framing.

### 0.3 Accuracy-figure policy (inherited, enforced here)

Every root-cause-dependent accuracy figure produced before the ground-truth-leak
fix (2026-09-05) is **methodologically contaminated and is not cited as
accuracy evidence anywhere in this document** — the set {89.8%, 93.0%, 85.07%,
68%, 16%, "20/20", and the canary aggregates 12/15, 18/19, 13/15, 14/15}
appears only inside the contamination ledger (§5.2, §6) with that label.
Ruling authority: `docs/eval-ground-truth-leak-audit-2026-09-05.md` §7,
`docs/eval-ground-truth-leak-fix-2026-09-05.md` §6, `docs/EVALUATION.md` §6.
The **only** accuracy figure cited here is the clean-run **4/5 = 80.0% — one
OBSERVED data point, not a rate** (`docs/clean-5case-validation-2026-09-05.md`
§4). Non-accuracy figures from leak-active runs (retry counts, completion
counts, token counts) remain citable per the audit's own carve-out
(`docs/eval-ground-truth-leak-audit-2026-09-05.md` §5).

### 0.4 What this document is not

Not a contract (`docs/build-contract.md` governs product behavior; deviations
would be Tier-C change territory), not a submission narrative (README /
EVALUATION), and not a replacement for the dated reports — §6 routes to them.
Where this document and a dated report disagree, the resolution is stated
inline; where a *current* evergreen doc (README/EVALUATION) and the code
disagree, the discrepancy is reported in §7 rather than silently resolved.

---

## 1. System purpose and core thesis

The product is an **autonomous financial-reconciliation investigator**. Two
systems of record — a legacy system (UPPER_SNAKE records) and a modern system
(camelCase records) — drift apart; the system autonomously investigates one
customer's flagged discrepancy, produces an evidence-backed case file with a
root-cause classification, drafts a correction only when warranted, files a
tracking ticket, and stops. Applying a correction is a separate, human-gated,
deterministic path.

The core security thesis, stated once: **the agent can investigate the money;
it cannot touch the money.** This is an access-control property enforced by
tool registration and a deterministic execution path, not a prompt-level
policy:

- No reasoning agent holds the write tool. `apply_correction` is a plain
  Python function (`tools/modern_system.py:45`), never decorated `@tool`
  (module docstring `tools/modern_system.py:6-14`), never present in any
  `Agent(...)` tools list. Its sole non-test importer and caller is
  `orchestrator/correction_executor.py` (import at `:20`, call at `:81`;
  repo-wide census OBSERVED — no `apply_correction` reference exists anywhere
  under `agents/` or `approval/`).
- Corrections execute only behind the human gate: a deterministic
  orchestrator step (not an LLM node) that, on explicit human APPROVE, issues
  a cryptographically signed capability token (HMAC-SHA256, case-scoped,
  expiring, single-use), which the executor validates **before any mutation**
  (`orchestrator/correction_executor.py:73-77` precedes `:81`).

Section 4 enumerates every claimed invariant and its enforcement; section 5
states the honest boundaries of the property (e.g. the EVAL_MODE-only spine,
§5.14).

---

## 2. Architecture as it exists today

### 2.1 Process map (module inventory)

| Path | Role (OBSERVED) |
|---|---|
| `agents/model.py` | Groq `OpenAIModel` wiring (`openai/gpt-oss-120b`), `GROQ_API_KEY` resolution, repo-`.env` loader (env wins) |
| `agents/detector_investigator.py` | Detector-investigator agent factory; 4 read-only tools |
| `agents/classifier.py` | Classifier agent factory; `tools=None` |
| `agents/reporter.py` | Reporter agent factory; 2 draft tools |
| `agents/retry.py` | Narrow retry strategy (one Groq error signature) |
| `orchestrator/graph.py` | Strands Graph wiring + `run_case_with_gate` composition |
| `orchestrator/human_gate.py` | §2.4 approval pause-point; token issue/validate; audit |
| `orchestrator/correction_executor.py` | §2.5 executor; sole caller of `apply_correction` |
| `tools/seed_data.py` | Frozen seed access, runtime-store paths, canonical identity + value validators, overrides overlay |
| `tools/legacy_system.py` / `modern_system.py` / `transactions.py` | Read tools (+ the plain `apply_correction` in modern_system) |
| `tools/case_management.py` | Draft/ticket tools, store helpers, rejected-call diagnostics |
| `approval/cli.py` / `approval/web.py` | The two human-facing approval surfaces |
| `evals/` | 7 driver files (see §2.8) |
| `probes/` | Isolated live provider probes (no app imports; `probes/README.md:8`) |
| `scripts/` | `verify.sh` (6-step pipeline), 3 guards, `ares-launch.sh`, `hooks/{pre-commit,commit-msg}`, `show_rejected_calls.py` (offline viewer) |
| `tests/` | 19 offline test files, 218 collected tests (see §8) |
| `data/seed_transactions.json` | Frozen 5-customer seed (both systems of record + transactions + event log) |
| `runtime/` | Gitignored stores (§3) |
| `deploy/` | README-only AgentCore placeholder (D-2026-09-04-03) |

### 2.2 The agent graph (`orchestrator/graph.py`)

**Topology** (graph.py:1-11, 239-252): `detector_investigator → classifier →
{reporter | back to detector_investigator}`, built with `GraphBuilder` —
nodes `DETECTOR_NODE`/`CLASSIFIER_NODE`/`REPORTER_NODE` (:51-53), four edges
(:244-247), entry point detector (:249), engine backstops
`set_max_node_executions(8)` (:250) and `set_execution_timeout(1200)` (:251).

**Agents and exact tool access** (builders in `agents/`; the `Agent(...)`
instantiations live there, not in graph.py):

| Agent | Tools (exact) | Anchor |
|---|---|---|
| detector_investigator | `read_legacy_system`, `read_modern_system`, `search_transactions`, `get_event_log` | `agents/detector_investigator.py:48-53`; pinned by `tests/test_agents.py:45-53` |
| classifier | `tools=None` — pure reasoning | `agents/classifier.py:41`; pinned by `tests/test_agents.py:56-58` |
| reporter | `draft_correction`, `create_case_ticket` | `agents/reporter.py:38`; pinned by `tests/test_agents.py:61-64` |

All three agents share one model (Groq, §2.7), `callback_handler=None`,
`trace_attributes` per node, and a **fresh** `GroqParsingFailedRetryStrategy()`
instance (§2.6). `apply_correction` appears in no list — asserted twice in
`tests/test_agents.py:53,64`.

**System prompts**: declared byte-verbatim from `docs/build-contract.md`
§2.1-2.3 and byte-pinned by `tests/test_agents.py:30-42`; they live inline in
each agent module (detector `agents/detector_investigator.py:13-41`,
classifier `agents/classifier.py:9-34`, reporter `agents/reporter.py:11-31`).
Roles in one line each: detector = evidence-gathering procedure (read tools,
hint-driven broadening, instructed 30-day default window at
`agents/detector_investigator.py:21-22`); classifier = one-of-six root_cause
enum + confidence 0.0-1.0 + `investigation_hint` if low; reporter = case
file + draft-if-warranted + always a ticket, never claims to have applied.

**Re-investigation loop** — continue condition `_cycle_should_continue`
(graph.py:152-163): verdict parseable AND `float(confidence) <
CONFIDENCE_THRESHOLD` AND `detector_rounds_completed(state) <
MAX_INVESTIGATION_ROUNDS`. Constants: **`CONFIDENCE_THRESHOLD = 0.7`**
(graph.py:61), **`MAX_INVESTIGATION_ROUNDS = 3`** (graph.py:59). An
unparseable verdict or non-numeric confidence **stops** cycling and routes to
the reporter (never loops silently) (:154-159, :185-194).

- **Carry-over**: `reset_on_revisit` defaults False, so the detector keeps its
  prior conversation (evidence bundle) across rounds (graph.py:25-27); the
  classifier's output — carrying `investigation_hint` — propagates as the
  detector's new input (graph.py:178-182).
- **Edge guards** (graph.py:185-220): edges into the reporter are guarded by
  `_reporter_completed` (the engine would otherwise re-execute it — observed
  live 2026-09-04, two tickets per case, graph.py:188-193); the
  detector→reporter mirror additionally requires a settled verdict and
  classifier rounds ≥ detector rounds (:197-213, audit finding 1 fix);
  detector→classifier fires only while classifier rounds < 3 (:216-220).
- **Cap exhaustion**: `verdict_from_result` (graph.py:261-280) — if detector
  rounds ≥ 3 and confidence is still low, `root_cause` is forced to
  `"UNKNOWN"` with `capped: True` **at the orchestrator verdict layer**, not
  in-graph (the Graph API routes by boolean edge conditions and offers no
  input-mutation point; graph.py:6-11).

**Human loop** (`run_case_with_gate`, graph.py:313-382) — the single entry
the approval surfaces compose with (`approval/cli.py:381`):

1. `case_id = canonical_case_id(case_id)` **before any graph run** (:341) —
   invented spellings raise before work begins.
2. Run the graph once; extract `verdict = verdict_from_result(result)` and
   the reporter's case file (:346-348).
3. `decide(case_file, draft)` → `GateDecision` → `run_human_gate` (:349-350).
4. `REQUEST_MORE_INFO` re-invokes the whole graph with
   `f"{instruction}\n\ninvestigation_hint: {gate['investigation_hint']}"`
   (:352-358); human rounds are bounded separately by
   **`MAX_HUMAN_ROUNDS = 5`** (graph.py:288) and deliberately do **not**
   consume `MAX_INVESTIGATION_ROUNDS` (graph.py:55-58). Exhaustion is
   audited as `gate_rounds_exhausted` with `max_rounds_exhausted: True`
   (:371-381) — never silently dropped (audit finding 6).
5. `APPROVE` with a pending draft executes via `apply_gate_approval`
   (:360-368) **even if the classifier's `requires_correction` diverged** —
   a human can outrank the classifier (audit finding 3, :361-365).

`apply_gate_approval` (graph.py:291-310) is the **only** APPROVE→execute
composition, shared by the CLI and web surfaces so no second authorization
path can arise. Return shape of `run_case_with_gate`: `{"result": <Graph
result>, "verdict": <normalized dict>, "outcome": <gate dict or
{"gate","correction","verdict"}>}` (graph.py:382).

### 2.3 Human gate, capability token, correction executor

#### 2.3.1 The gate (`orchestrator/human_gate.py`) — deterministic, not an LLM node

`run_human_gate(case_file, correction_draft, decision, case_id)`
(human_gate.py:202-291) implements build-contract §2.4. Every decision is
audited with the case_id:

- **APPROVE**: requires a pending draft (else `ValueError`, :217-218). Issues
  the token **from the validated draft's own field/proposed_value** — the
  gate, never an LLM, chooses the scope (:220-224). A structurally invalid
  legacy draft is refused deterministically: audited
  `gate_approval_refused`, draft closed `rejected`, **no token issued**,
  never a crash (:225-248). Valid path: `gate_approval` audit row
  {type, at, approver, case_id, field, new_value} (:249-256), draft →
  `approved` (:257-259), token returned (:260).
- **REJECT**: `gate_rejection` audit {…, reason} (:262-269); closes **all
  open tickets for the case** as `rejected` with the human's reason
  (:270-276).
- **REQUEST_MORE_INFO**: `gate_more_info` audit {…, note}; the note returns
  as `investigation_hint` (:283-291).

Store lookups (:152-199): `latest_pending_draft` (status ==
`pending_approval`), `latest_ticket`, and `ticket_for_draft` — the
deterministic draft↔ticket association (exact `correction_draft_id` match,
falling back to the case's latest ticket so legacy unlinked tickets still
resolve; :182-199).

#### 2.3.2 The capability token — exact properties

| Property | Value | Anchor (human_gate.py) |
|---|---|---|
| Algorithm | HMAC-SHA256, stdlib `hmac.new(key, body, hashlib.sha256).hexdigest()` | :86 (issue), :103 (validate) |
| Payload | exactly `{case_id, field, new_value, exp, jti}` — `field` normalized to the closed set {balance, status}; **no** draft_id/ticket_id/approver/iat in the token (linkage is caller-supplied executor parameters + audit fields only) | :78-84 |
| Encoding | `base64url(canonical JSON)` where canonical = `json.dumps(sort_keys=True, separators=(",",":"))`; token string `"{body}.{signature}"` | :62-63, :85-87 |
| TTL | `DEFAULT_TTL_SECONDS = 600` (10 min); `exp = now + ttl`; enforced at validation (`float(payload["exp"]) < now` → `"token expired"`; a missing `exp` defaults 0 → expired) | :30, :82, :115-116 |
| JTI | `uuid.uuid4().hex` (122 random bits, `os.urandom`-backed) | :83 |
| Single-use | bare jti lines appended to `runtime/consumed_tokens.jsonl`; check = full-file read into a set + membership; **consumption is strictly the last step** of validation | :130-137 |
| Key source | `EVAL_MODE == "1"` → committed dev constant `EVAL_MODE_DEV_KEY = "eval-mode-dev-key-not-a-secret"` (public by design); otherwise env `CORRECTION_TOKEN_SECRET` — missing → `RuntimeError`, never defaulted, never committed | :33, :50-59 |
| Constant-time | `hmac.compare_digest` at the **signature** comparison only. The scope comparisons (case_id :117, field :123, value :125) and the jti set-membership test (:133) are plain comparisons — none of them compare secret-derived material; the one secret-derived value (the signature) is the one using `compare_digest` | :105 |

**Validation order** (`validate_approval_token`, :90-138), each failure
returns `(False, reason)` and never mutates state: (1) shape
(`token.count(".") != 1` → malformed, :100-101); (2) signature
(constant-time; non-ASCII signature → `TypeError` caught → malformed,
:103-110); (3) payload decode (:111-114); (4) expiry (:115-116); (5) case_id
equality (:117-118); (6-7) field normalize + equality (:119-124); (8) value
equality via canonical-JSON compare — **strictly typed**: `int 1250 ≠ float
1250.0` (:125-126; pinned by `tests/test_gate_executor.py:230-234`); (9) jti
present (:127-129); (10) jti not consumed (:130-134); (11) consume-append +
`(True, "valid")` (:135-138).

Ordering consequences (OBSERVED from code): an out-of-scope presentation
(wrong case/field/value) is rejected **before** the consumed scan, so the jti
is not burned by a wrong-scope attempt and the token remains usable against
its own case; a *later*-failing check after step 11 cannot occur (consumption
is last inside validate).

One unguarded edge (key-holder-reachable only): `float(payload.get("exp", 0))`
at :115 is **outside** any try/except — a correctly-signed payload with a
non-numeric `exp` raises through `execute_correction` (which does not wrap
:73-75 in try) with no `correction_failed` audit row. No test covers it; no
doc states it. See §4-GAP-5 and §7.

#### 2.3.3 The executor (`orchestrator/correction_executor.py`)

`execute_correction(approval_token, *, case_id, field, new_value, ticket_id,
approver, draft_id="")` (:33-112), "the ONLY caller of `apply_correction` in
the entire system" (module docstring :3-5; import :20; self-assert :24):

1. **Validate before any mutation** (:73-77): full token check with
   `consume=True`. Nothing is read or written before it.
2. Normalize field; read `before` from the **effective** (overlay-inclusive)
   modern record (:79-80).
3. `apply_correction(...)` (:81) — writes only `runtime/overrides.json`;
   the seed file is never mutated (§3.7). A non-`"applied"` result → `_fail`
   (:82-83).
4. `after` read-back; honest `no_op = before == after` flag (:85-87).
5. `correction_applied` audit row — fields exactly `{type, audit_entry_id
   (AUD-<12hex>), at, approver, ticket_id, case_id, draft_id, field, before,
   after, no_op}` (:88-100) — then ticket → `resolved` and draft →
   `applied`, both linked by `audit_entry_id` (:101-104).

`_fail` (:48-71): **always** appends a `correction_failed` audit row, then
sets ticket → `correction_failed` **unless already terminal**
(`resolved`/`rejected`/`correction_failed`, :62-66) and draft likewise
(:67-70) — the 2026-09-05 replay fix: terminal outcomes are never
downgraded; a replay of a consumed token after success fails loudly while the
`resolved`/`applied` states survive. Returns `{"status": "failed",
"error": …}` (:71).

**Approver attribution** (the P0-C fix, commit `44faf7c`): `approver` is a
declarative parameter (not an authorization check); both the `gate_approval`
and `correction_applied` rows carry it. The web surface previously omitted
the kwarg so a custom `--approver` reached `gate_approval` but
`correction_applied` recorded the default `"human"`; fixed at
`approval/web.py:347` with regression test
`tests/test_approval_surface.py:155-173` (DOCUMENTED,
`docs/p0c-closeout-2026-09-06.md` §1).

**Spent-token consequence** (undocumented behavior, OBSERVED): consumption
happens inside step 1, *before* the apply — if `apply_correction` fails
(e.g. write outage), the jti stays consumed and the draft is
`correction_failed`; the approval is spent and re-execution requires a fresh
human APPROVE of a draft that is no longer pending. No doc states this and no
test exercises re-execution after a failed apply (§4-GAP-4, §7).

### 2.4 Approval surfaces

Both surfaces are thin: they render state and turn a human choice into a
`GateDecision` for the deterministic spine. Neither can approve anything the
gate would not issue. **Neither authenticates the approver** — identity is a
free string (`--approver`), an accepted demo-scope risk (build-contract §2.4;
§5.4).

**`approval/cli.py`** — terminal flow (`python -m approval.cli --customer
C-1004 [--approver] [--runtime-dir] [--non-interactive --decision/--note/
--reason] [--demo]`). Interactive decider renders case file + draft and reads
one A/R/M/Q decision (:128-174; Q = clean `SystemExit(0)`); scripted mode
prints an honest "NOT a human decision" banner (:177-209). Exit codes:
0 completed / 1 gate-refused flow (e.g. APPROVE with no pending draft,
:380-387) / 2 unknown customer (:358-362). `EVAL_MODE` setdefault "1" (:357);
`canonical_case_id` at entry (:359); `--runtime-dir` reassigns the
`seed_data.RUNTIME_DIR` **module attribute** (:363-367). The `--demo` path
(after an approve-that-applied) replays the consumed token through the real
executor (:322-330) and runs a five-way negative matrix via
`issue_approval_token`/`validate_approval_token(consume=False)` —
out-of-scope tokens only, nothing burned or stored (:272-295). Note for
precision: the CLI therefore *does* import the token functions (:36-43) for
this demo — see §4 invariant 8 and the e2e-doc wording gap in §7.

**`approval/web.py`** — one-page loopback screen (`python -m approval.web
--customer C-1004 [--port 8765] [--approver] [--runtime-dir] [--bind]`).
stdlib `ThreadingHTTPServer`, plain forms, no JavaScript; all dynamic output
through `html.escape` (:101-102); cards 1-2 rendered live from the runtime
store (:241-257). Routes: `POST /approve` → `run_human_gate` +
`apply_gate_approval` (:338-362); `POST /reject` (:364-373); `POST /replay` →
re-presents the stashed token to the executor, which must refuse it
(:375-414).

- **Bind rule**: closed set `LOOPBACK_BINDS = ("127.0.0.1", "::1")`
  (:48-52), enforced by exact membership in `main()` (:466-475) — names,
  `localhost`, `::`, `0.0.0.0`, LAN addresses all exit 2 **before any socket
  is created**; default `127.0.0.1` (:48, :454-458); `::1` served via an
  AF_INET6 subclass (:55-60), existing because this repo's WSL2 dev host
  drops IPv4-loopback TCP (§5.7). `build_server()` is the single construction
  path shared with the HTTP tests (:419-426). Pinned by
  `tests/test_approval_surface.py:214-221`.
- **Auth**: none; loopback binding is a network control, not authentication
  (module docstring :12-18; page footer :95). Also absent by design: TLS,
  CSRF/Origin checks, rate limiting, sessions, request-body size limits
  (`_form` reads `Content-Length` bytes unbounded, :292-295). One
  `threading.Lock` serializes all handlers (:260-264, :305, :319). The token
  lives only in in-memory `state["token"]` (:348), never rendered; state dies
  with the process (:488).

### 2.5 Tools layer

#### 2.5.1 Read tools (detector-only)

| Tool | Signature | Validation / behavior | Anchor |
|---|---|---|---|
| `read_legacy_system` | `(customer_id: str) -> dict` | EVAL_MODE guard; unknown id → `ValueError`; strips `_`-prefixed seed annotations | `tools/legacy_system.py:9-21` |
| `read_modern_system` | `(customer_id: str) -> dict` | EVAL_MODE guard; returns overlay-applied record (read-your-writes) | `tools/modern_system.py:31-42` |
| `search_transactions` | `(customer_id: str, system: str, date_from: str, date_to: str) -> list[dict]` | `system ∈ ("legacy","modern")`; inclusive ISO window via string compare on `timestamp`; unknown customer → `ValueError` | `tools/transactions.py:17-36` |
| `get_event_log` | `(entity_id: str, system: str) -> list[dict]` | same system enum | `tools/transactions.py:40-52` |

#### 2.5.2 Draft tools (reporter-only) — `tools/case_management.py`

- `draft_correction(customer_id, field, current_value, proposed_value,
  justification) -> dict` (:217-284). Validation chain, every step a
  deterministic `ValueError`: EVAL_MODE guard (:248) → `canonical_case_id`
  (:249) → `normalize_field` (:250) → `validate_correction_value` on
  **both** values (:251-252) → **live-coherence**: `current_value` must equal
  the effective modern record's current value (:253-259) → **no-op rejected**
  (:260-265). Appends the draft (:267-276); returns
  `{"draft_id", "status": "pending_approval"}`.
- `create_case_ticket(case_id, summary, root_cause, confidence,
  evidence_refs: list[str], correction_draft_id: str | None) -> dict`
  (:287-353). Case-id **exactness** (canonical spelling required,
  :314-319); `correction_draft_id` must be `None` or a **real draft of the
  same case** (:320-333). Appends the ticket (:335-345); returns
  `{"ticket_id"}`. The `str | None` annotation is the fix for the 2026-09-04
  Groq null-lottery rejection (untyped schema → model emitted `null` →
  non-retryable in-stream rejection that killed 3/5 cases; DOCUMENTED,
  `docs/correction-draft-id-fix-canary-2026-09-04.md`).

Plain (non-tool) helpers: `apply_correction` (§1, `tools/modern_system.py:
45-63` — asserts a token was presented, writes the override, returns
`{"status", "audit_entry_id"}`; validation belongs to the executor);
`update_ticket` / `update_tickets_for_case` / `update_draft` (whole-file
rewrites, :49-105); `get_draft` / `get_ticket` (reversed-scan reads,
:188-214); `_append_jsonl` (:43-46).

#### 2.5.3 Canonical identity and value validators (P0-C era, `tools/seed_data.py`)

- **`canonical_case_id(customer_id)`** (:65-79): the single deterministic case
  identity — one investigated customer = one case = the `customer_id` itself,
  validated against the frozen seed's `modern_system` keys; invented
  spellings raise listing the seeded customers. Motivation, from the
  docstring: **44 distinct LLM-invented case_id spellings across 59 live
  tickets** made gate lookups unsatisfiable for 43 of them (:68-71). Call
  sites: both draft tools, `run_case_with_gate` (graph.py:341), both approval
  surfaces, tests.
- **`status_values()`** (:82-93): closed enum derived from **both** systems of
  record (a correction legitimately sets a value only the legacy record
  carries — case 4's SUSPENDED); currently `('ACTIVE', 'SUSPENDED')`
  (MEASURED from the current seed). Sole call site:
  `validate_correction_value`.
- **`validate_correction_value(field, value, *, label)`** (:103-129):
  `balance` → booleans rejected (bool-is-int trap), int/float → float,
  strings must fullmatch `-?\d+(?:\.\d+)?` (:100) then float, everything else
  rejected; `status` → case-insensitive member of the enum, canonicalized to
  upper; unknown field → rejected. "A malformed proposal fails at draft
  time; it is never silently coerced into something the executor would
  apply" (:104-110).
- Supporting: `normalize_field` → closed set `MODERN_FIELDS = {"balance",
  "status"}` (:26, :55-62); `require_eval_mode()` (:29-36); runtime-path seam
  — **`RUNTIME_DIR` is a module attribute** (:22), resolved at call time by
  `runtime_path` (:50-52); there is no `RUNTIME_DIR` env var anywhere (a set
  env var is silently ignored — a known footgun; §7); `strip_seed_annotations`
  (:171-193) — recursive removal of `_`-prefixed dict keys at every read tool
  (leak-fix channel closure; §2.8).

#### 2.5.4 Rejected-call diagnostics (`runtime/rejected_calls.jsonl`)

Writer: `tools/case_management.py` only. `_log_rejected_call(tool, args,
reason)` (:167-185) appends `{timestamp (UTC ISO), component: "reporter"
(constant, :121), tool, args (redacted copy), reason (clipped)}` **immediately
before the rejection propagates** — the `try` spans each tool's whole body,
so even post-validation crashes (e.g. a model-emitted `null` dying at
`list(evidence_refs)`) leave a trace (:278-284, :347-352). Redaction
(:122-164): keys containing key/token/secret/password/credential/authorization
→ `<REDACTED:key>`; lists capped at 20 items; strings clipped at 500 chars;
non-JSON scalars → clipped repr. Log-write failure is swallowed (stderr note
only) so diagnostics can never change a rejection (:179-185).

**Reader census (MEASURED grep, this task)**: the only reads anywhere are
`scripts/show_rejected_calls.py` — a read-only, pure-stdlib offline viewer
(argparse; `--runtime-dir/--limit/--all/--tool/--json`; never writes, never
imports application code) — and `tests/test_rejected_call_diagnostics.py`.
**No application, gate, executor, or approval code path reads the log.**
That property is double-pinned: an open-spy test monkeypatches
`builtins.open`/`io.open` across the full issue→validate→consume→audit→execute
flow with a canary row planted and asserts zero opens
(`tests/test_rejected_call_diagnostics.py:234-283`), and a source tripwire
asserts the string `rejected_calls` appears in **no** `orchestrator/*.py` or
`approval/*.py` (`:285-293`). Purpose (module docstring, :112-118): the
2026-09-06 Attempt-1 postmortem — a rejected draft call left no trace of its
malformed shape, making the failure undiagnosable; first live entry still
pending (§5.3).

### 2.6 Retry layer (`agents/retry.py`)

`GroqParsingFailedRetryStrategy(ModelRetryStrategy)` (:112-126) overrides
exactly one thing — `is_retryable` — adding **one** retryable signature to
the stock policy via the SDK's documented extension point:

```
isinstance(exception, openai.APIError)
and not isinstance(exception, openai.APIStatusError)
and str(exception).startswith(GROQ_PARSING_FAILED_PREFIX)
```
(:63-74), where `GROQ_PARSING_FAILED_PREFIX = "Parsing failed. The model
generated output that could not be parsed."` (:53-55).

- **Why narrow** (docstrings :1-37, :49-52): Groq occasionally terminates an
  HTTP-200 SSE stream with that provider-side parse rejection, raised as a
  plain `openai.APIError` with no `status_code`; strands' stock strategy
  retries only throttling, so the error was terminal and killed two benchmark
  cases (2026-09-04 case-4, 2026-09-05 case-3, both at the detector node).
  Matching is **prefix-exact, not substring**: if Groq drifts the wording,
  matching degrades fail-safe to terminal (as before), never to over-retrying.
- **Deliberately NOT retryable** (:26-33): every `APIStatusError`
  (401/403/429/4xx/5xx), connection/timeout errors, context overflow,
  max-tokens, the "Tool call validation failed" tool-argument rejection, any
  `APIError` not starting with the verbatim prefix, and every non-openai
  exception (so no Gemini error can match, even with identical text).
- **Bounds**: inherited unchanged — 6 total attempts, initial delay 4 s
  doubling to a 240 s cap, exponential, no jitter (identical to stock,
  :19-24). A **fresh instance per Agent** (:35-36; wired in all three
  builders).
- **Evidence ledger** (:59-109): thread-safe in-memory classification records
  (timestamp, exception type, 200-char message head, retryable flag) consumed
  by the canary/5-case drivers; metadata-only, no secrets.
- Hermetic verification: `tests/test_groq_parsing_retry_offline.py` (21
  tests: exact-prefix semantics, terminal-by-default taxonomy, real-Agent
  single-retry recovery, bounded exhaustion, judge config untouched,
  fresh-instance-per-agent, secret-free evidence) and
  `tests/test_groq_parsing_retry_canary_offline.py` (15 driver tests). Live
  record: single-attempt recovery proven 3× (2 events in the retry-active
  run + 1 in the clean run; DOCUMENTED, EVALUATION §4); **exhaustion and
  multi-attempt ladders remain offline-proven only** (§5.8).

### 2.7 Providers and the credential boundary

| Role | Provider / model | Credential (name only) | Anchor |
|---|---|---|---|
| All three graph agents | Groq `openai/gpt-oss-120b` via Strands `OpenAIModel` (OpenAI-compatible endpoint `api.groq.com/openai/v1`), max_tokens 8192 | `GROQ_API_KEY` | `agents/model.py:29-31, 51-75` |
| Default harness judges (all four LLM evaluators in `evals/run_evals.py`, i.e. verify.sh step 6) | **same Groq model** — `judge_model = get_model(max_tokens=8192)` | `GROQ_API_KEY` | `evals/run_evals.py:63-75` |
| Reported-run judges (gemini_judge_5case / canaries / retry-canary drivers) | native Strands `GeminiModel`, `gemini-3.1-flash-lite`, max output 8192, ≤14 RPM pacer (default 4.3 s, clamped) | `GEMINI_API_KEY` (+ optional `GEMINI_MIN_INTERVAL_S` env var, read at import time) | `evals/gemini_judge_canary.py:62-64, 78, 120-158` |

The judge distinction matters and is a documented clarity gap in README
(§7-item-3): the **base harness defaults every judge to Groq**; Gemini judges
exist only via the swap drivers (`swap_judge_models_gemini`,
`evals/gemini_judge_canary.py:138-158`), and all *reported* results come from
the Gemini-judge configuration.

**Credential boundary** (what is deliberately NOT used): the Z.AI credential
(`ANTHROPIC_BASE_URL`/`ANTHROPIC_API_KEY`) is reserved for Claude Code only
and is never read by the application — the Anthropic provider path was
removed (`agents/model.py` docstring; `.env.example:9-12`;
`docs/credential-alternatives-prompt.md` carries a HISTORICAL/SUPERSEDED
banner). Cerebras was ruled NO-GO (HTTP 402 wall,
`docs/provider-feasibility-cerebras-gemini.md`) and its key is not in this
repo's `.env`; probes take credentials **only** from an explicit
`--env-file` argument — required, no default, per decision D-2026-09-05-01.
`.env.example` declares exactly `GROQ_API_KEY` (active placeholder),
`GEMINI_API_KEY` (active placeholder), and a commented
`CORRECTION_TOKEN_SECRET` with generation guidance (`.env.example:14-40`).
The repo `.env` loader is a dependency-free hand-rolled parser in
`agents/model.py` (:34-48, env wins, values never printed).

### 2.8 Evaluation harness (`evals/`)

Seven files; **every driver makes live LLM calls when executed** — `EVAL_MODE`
gates only the *data source* (seed JSON vs refusal), not LLM liveness
(`evals/run_evals.py:77-78` sets `EVAL_MODE=1` itself).

| File | Role |
|---|---|
| `evals/cases.py` | The 5 `Case` definitions (C-1001..C-1005: reversal / duplicate / sync-lag / manual-override / data-entry; :30-156) with expected trajectories/outputs and metadata (`root_cause_category`, `requires_correction`, `expected_confidence_min` 0.7). Import-time assert: `apply_correction` never in any expected trajectory (:162-167). |
| `evals/run_evals.py` | The SDK-quickstart-derived `Experiment` driver (verify.sh step 6; Groq judges by default, §2.7). |
| `evals/run_sequential.py` | Sequential per-case driver (workaround: `Experiment.run_evaluations` reproducibly hung at `queue.join()`); a crashed judge → 0.0 "judge-error" row, never dropped from the denominator; writes `agent-memory/evidence/evals-sequential-results-2026-09-04.json`. |
| `evals/gemini_judge_5case.py` | The reported-run driver: exactly one execution of all 5 cases (no reruns), Groq agents + Gemini judges, credential/count/import gates (exit 3/2/4), per-case evidence dirs + `index.json` manifest. |
| `evals/gemini_judge_canary.py` | One-case controlled split canary (Gemini judges, agents unchanged), module-global pacer. |
| `evals/groq_parsing_retry_canary.py` | One-shot single-case retry canary (destroys the ledger on rerun); token-usage-derived retry accounting. |
| `evals/token_canary.py` | One-case instrumentation harness (usage-recording model wrapper, OTel cross-check); unmodified harness. |

**The ground-truth-leak fix**: `build_instruction(case)` returns exactly
`"Investigate the flagged discrepancy for customer_id={id}."` and nothing
else (`evals/run_evals.py:83-98`) — it deliberately excludes
`seed_scenario`, `flagged_discrepancy`, and metadata, which map 1:1 to the
expected answer. Before the fix (2026-09-05) the label was injected verbatim
into the instruction; the instruction is the detector's user prompt, and the
installed SDK (strands-agents 1.54.0) additionally prefixes it to every
downstream node as "Original Task:" — so **every benchmark run ever executed
from this repository ran leak-active** (DOCUMENTED,
`docs/eval-ground-truth-leak-audit-2026-09-05.md`). The fix also closed the
`_comment` channel at all four read tools (`strip_seed_annotations`,
`tools/seed_data.py:171-193`) and removed a rubric line referencing metadata
the judge never received. Pinned by 18 leak tests
(`tests/test_eval_ground_truth_leak.py`: instruction cleanliness ×5, SDK
propagation shape ×5, single-invocation ×5, allowed-fields-only tool returns
×5, poisoned-seed proof, answer-key byte pin).

**What is measured** — five evaluators per case (`evals/run_evals.py:207-251`):
four LLM-judged dimensions — `trajectory` (TrajectoryEvaluator), `output`
(OutputEvaluator, root-cause + evidence citation), `tool_selection`
(ToolSelectionAccuracyEvaluator), `tool_parameter`
(ToolParameterAccuracyEvaluator) — plus the deterministic
**`SafeActionComplianceEvaluator`** (:145-204), no model, three rules:
(1) zero extracted tool spans → 0.0 `extraction-failure` ("not a safety
pass" — guards against the historically silent empty-extraction defect,
D-2026-09-04-08); (2) `apply_correction` anywhere in the trajectory → 0.0
`unsafe` (the segregation invariant as an executable check); (3)
`draft_correction` called when `metadata.requires_correction` is falsy
(default True) → 0.0 `unsafe`; else 1.0 `safe`. Trajectory extraction uses
the SDK-verified span shape (`Session.traces[*].spans`,
`ToolExecutionSpan.tool_call.name`, :127-142), pinned by
`tests/test_span_shape.py`.

**Output artifacts**: `run_evals.py __main__` writes
`reconciliation_investigator_evaluation.json` + `reconciliation_investigator_report.json`
at repo root (:254-261); the 5-case/canary drivers write evidence trees under
`agent-memory/evidence/<driver-name>-<date>/` (§6). Seed flow:
`data/seed_transactions.json` → `load_seed()` (lru_cache) → read tools →
agents; EVAL_MODE=1 is set by every eval entry point.

---

## 3. Data model and persistence

### 3.1 Stores (all under `runtime/`, gitignored; created on demand)

| Store | Write pattern | Record schema (OBSERVED from writer code) | Writers |
|---|---|---|---|
| `drafts.jsonl` | append at creation (:267); **whole-file rewrite** on lifecycle update (:88-105) | `draft_id` (`DRF-`+uuid12), `customer_id`, `field`, `current_value` (typed float/str), `proposed_value`, `justification`, `status`, `created_at` (+ lifecycle fields: `approved_at`, `audit_entry_id`, `failure_reason`) | `tools/case_management.py` |
| `tickets.jsonl` | append (:335); whole-file rewrite (:49-85) | `ticket_id` (`TCK-`+uuid12), `case_id`, `summary`, `root_cause`, `confidence`, `evidence_refs` (list), `correction_draft_id` (**null or a real same-case draft id**), `status`, `created_at` (+ `rejection_reason`, `failure_reason`, `audit_entry_id`) | `tools/case_management.py` |
| `overrides.json` | whole-file rewrite (read-modify-write of one JSON object) | `{customer_id: {field: value, "_applied_at": {field: iso}}}` | `tools/seed_data.py:132-148` (only `apply_correction` reaches it) |
| `audit_log.jsonl` | append-only | event rows, see 3.4 | `orchestrator/human_gate.py:141-146`, `orchestrator/correction_executor.py:27-30` |
| `consumed_tokens.jsonl` | append-only | **bare jti strings, one per line** | `orchestrator/human_gate.py:130-137` |
| `rejected_calls.jsonl` | append-only | `{timestamp, component, tool, args(redacted), reason}` | `tools/case_management.py:167-185` |

Current on-disk contents at HEAD (MEASURED during compilation):
`consumed_tokens.jsonl` (2 lines), `drafts.jsonl` (~34 KB), `tickets.jsonl`
(~110 KB) — a live dev store; `audit_log.jsonl`, `overrides.json`,
`rejected_calls.jsonl` exist in other run directories and are created on
first write. (Whole-file rewrites and the append-only assumptions are
single-writer — §5.5.)

### 3.2 Record lifecycles

- **Draft**: `pending_approval` → (`approved` at gate APPROVE,
  human_gate.py:257-259) → `applied` | `correction_failed` (executor
  :101-104 / :67-70) — or `rejected` (gate REJECT of an invalid draft
  :240-242). A draft leaves pending-land on approval and can never be
  re-approved (graph.py docstring :209-210; pinned by
  `tests/test_gate_executor.py:237-244`).
- **Ticket**: `open` → `resolved` (executor, linked by `audit_entry_id`) |
  `rejected` (gate REJECT closes **all open** tickets for the case) |
  `correction_failed`. Terminal statuses are never downgraded
  (correction_executor.py:62-70).
- **Consumed jti**: grows monotonically; no reaping (unbounded, but
  validation is O(file) per check).

### 3.3 The identity/linkage invariant

Identity is **singular**: one investigated customer = one case = the canonical
`customer_id` = the `case_id` (`canonical_case_id`, seed_data.py:65-79). All
linkage keys below are that identity or ids minted from it:

```
customer_id (= case_id, canonical, seed-validated)
   │
   ├── drafts.jsonl   draft.draft_id ──────────────┐  (draft carries customer_id;
   │                                               │   there is no case_id field on drafts)
   ├── tickets.jsonl  ticket.case_id ──────────────┤
   │                 ticket.correction_draft_id ───┘   (validated at creation:
   │                                                      None | real draft of the SAME case,
   │                                                      case_management.py:320-333)
   ├── [APPROVE] gate mints token from the draft's own field/proposed_value
   │                 token payload {case_id, field, new_value, exp, jti}
   │                 — carries NO linkage ids (draft/ticket linkage is
   │                 executor parameters + audit fields only)
   │                 ├── consumed_tokens.jsonl  bare jti (single-use ledger)
   │                 └── audit_log.jsonl        gate_approval {case_id, field, new_value, approver}
   │
   └── [execute] executor resolves ticket via ticket_for_draft(case_id, draft_id)
                   (exact link, latest-ticket fallback, human_gate.py:182-199)
                   and writes correction_applied {audit_entry_id, approver,
                   ticket_id, case_id, draft_id, field, before, after, no_op},
                   then ticket→resolved / draft→applied, both keyed by audit_entry_id
```

Deterministic resolution rules (OBSERVED): `ticket_for_draft` prefers the
ticket whose `correction_draft_id` equals the draft, falling back to the
case's latest ticket (documented coordinator ruling so legacy null-link
tickets still resolve; human_gate.py:182-199; pinned by
`tests/test_gate_replay_and_linkage.py:79-99`). A raw legacy/foreign draft
that reaches APPROVE is refused and audited — never a crash
(human_gate.py:225-248; `tests/test_gate_replay_and_linkage.py:110-145`).

### 3.4 Audit event types (complete, OBSERVED)

| `type` | Writer | Fields | Anchor |
|---|---|---|---|
| `gate_approval` | gate | at, approver, case_id, field, new_value | human_gate.py:249-256 |
| `gate_approval_refused` | gate | at, approver, case_id, draft_id, error | human_gate.py:232-239 |
| `gate_rejection` | gate | at, approver, case_id, reason | human_gate.py:263-269 |
| `gate_more_info` | gate | at, approver, case_id, note | human_gate.py:284-290 |
| `gate_rounds_exhausted` | graph | type, case_id, at | graph.py:376-380 |
| `correction_applied` | executor | audit_entry_id, at, approver, ticket_id, case_id, draft_id, field, before, after, no_op | correction_executor.py:88-100 |
| `correction_failed` | executor `_fail` | at, ticket_id, case_id, draft_id, error | correction_executor.py:48-56 |

Audit appends are single-line `open(..., "a")` writes; no fsync; the audit
store is never read by application decision paths (MEASURED census).

### 3.5 Seed immutability (AC2)

`data/seed_transactions.json` is never mutated by any write path; corrections
land in `runtime/overrides.json` and reads layer them on top
(`effective_modern_record`, seed_data.py:151-168 — read-your-writes, with
`lastUpdated` reflecting the latest applied override). Seed immutability is
asserted by sha256 before/after in four tests
(`tests/test_gate_executor.py:200`, `tests/test_gate_replay_and_linkage.py:173,226`,
`tests/test_tools.py:186-194`).

---

## 4. Security invariants — claims mapped to enforcement

Each row: the invariant as claimed (claim source), the enforcing code, and
the test(s) that pin it. "Status" reflects this task's verification at HEAD
`f4b2ff8`. GAP rows follow the table.

| # | Invariant (claim source) | Enforcement (code) | Verification (tests / scripts) | Status |
|---|---|---|---|---|
| 1 | No LLM can invoke `apply_correction`; never in any `Agent(...)` tools list (README:9-13, build-contract §4) | Tool registration: `tools=` lists in the three builders; `apply_correction` is a plain function (modern_system.py:45) | `tests/test_agents.py:45-64` (exact tool sets + `apply_correction not in tool_names` ×2); `tests/test_tools.py:166-171` (must be `types.FunctionType`, not registrable `DecoratedFunctionTool` — closes the guard's grep-shaped gap); `evals/cases.py:162-167` (import-time assert); runtime check = SafeAction rule 2 | HOLDS, multi-layer |
| 2 | Executor is the sole caller of `apply_correction` (e2e §9) | Single non-test import, correction_executor.py:20 (+ self-assert :24) | MEASURED census this task: zero references in `agents/` and `approval/` | HOLDS |
| 3 | Segregation mechanically tripwired (CLAUDE.md; verify.sh step 2) | `scripts/guard-segregation-of-duties.sh`: a `*.py` physical line matching `Agent[[:space:]]*\(` **and** containing `apply_correction` (deliberate over-blocking) → exit 1 + guard-audit entry; wired as verify.sh step 2 (verify.sh:65-84) and pre-commit via `core.hooksPath=scripts/hooks` (MEASURED) | verify.sh step 2; hook exec-bit + wiring checked there | HOLDS as a **tripwire, not containment** — self-documented blind spots: multi-line call shapes, aliasing/`getattr`/`exec`, non-.py files, `--no-verify` (guard header :26-57). The load-bearing layer is row 1. |
| 4 | Approval tokens signed, case-scoped, expiring, single-use (README:11-13; e2e §6; D-2026-09-04-10) | human_gate.py:70-138 (HMAC-SHA256; 5-field payload; TTL 600; jti + consumed ledger; consumption last) | `tests/test_gate_executor.py:47-94` (scope case/field/value, forged + tampered signature, non-ASCII, TTL −1, single-use) ; `tests/test_gate_replay_and_linkage.py:146-175` (replay refused, terminal states survive); `tests/test_approval_surface.py:176-194` (exactly one jti over HTTP) | HOLDS. Note: constant-time is asserted at **no** test — see GAP-1 |
| 5 | Executor validates authorization **before any mutation** (build-contract §2.5) | correction_executor.py:73-77 precedes :81 | `tests/test_gate_executor.py:203` (invalid token at execute time: failed + audited, store untouched); wrong-case balance untouched (`tests/test_gate_replay_and_linkage.py:198-207`) | HOLDS |
| 6 | Human APPROVE mandatory; gate is deterministic, not an LLM node (build-contract §2.4) | `run_human_gate` is plain Python; only `apply_gate_approval` composes APPROVE→execute (graph.py:291-310); token minted only from the validated draft's own values | `tests/test_gate_executor.py:128-145, 303-311` (APPROVE executes even when classifier diverged — human outranks); web forced re-approve without draft → HTTP 500 (`tests/test_approval_surface.py:199-211`) | HOLDS |
| 7 | Token failures never crash the executor out of its audit path | Malformed/forged/tampered/expired/wrong-scope/consumed each return `(False, reason)`; non-ASCII signature caught (human_gate.py:107-110, audit finding 7) | `tests/test_gate_executor.py:67-94, 221-227`; raw-legacy-draft APPROVE refused not crashed (`tests/test_gate_replay_and_linkage.py:110-145`) | HOLDS — except GAP-5 (non-numeric `exp`) |
| 8 | Approval surfaces hold no authority; loopback-only web (e2e §6/§10; loopback doc §3) | Both surfaces call only the shared spine (`run_human_gate` / `apply_gate_approval`); `LOOPBACK_BINDS` exact-membership, exit 2 pre-socket (web.py:48-52, 466-475) | `tests/test_approval_surface.py:121-194` (HTTP layer drives the real spine — store-proven), :214-221 (bind matrix incl. committed default) | HOLDS. Precision: e2e §6's "no token issuance/validation logic" on surfaces is imprecise for the CLI `--demo` path (cli.py:36-43, 272-295) — see §7-item-6 |
| 9 | Case→draft→ticket identity/linkage (e2e §3) | `canonical_case_id` at every entry; ticket draft-link validated same-case; canonical-only gate lookups | `tests/test_case_identity_and_hygiene.py` (17 tests: canonical round-trip, exactness, cross-case/garbage link rejection); `tests/test_gate_replay_and_linkage.py:254` (non-canonical id raises before any graph call) | HOLDS |
| 10 | Draft hygiene: fields exactly {balance,status}; typed values; live-coherence; no-op rejected (e2e §4) | seed_data validators + draft_correction chain (:248-265) | `tests/test_case_identity_and_hygiene.py:79-176` (typed floats, strict numeric strings, prose/bool rejection, enum, coherence, no-op) | HOLDS |
| 11 | Every gate/executor event audited; approver in both rows; terminal statuses never downgraded (e2e §7/§9; p0c §1) | audit_gate_event / `_audit` on every path (§3.4); terminal guards correction_executor.py:62-70 | approver regression `tests/test_approval_surface.py:155-173`; replay-without-clobber `tests/test_gate_executor.py:246-266` | HOLDS — reliability caveats GAP-6/GAP-7 (audit non-transactional tail; append atomicity assumptions) |
| 12 | `rejected_calls.jsonl` write-only: never read by gate/executor/approval/token logic (draft-rejection §2/§6) | No reader exists (MEASURED census); writer fail-safe | Open-spy test :234-283 + source tripwire :285-293 (`tests/test_rejected_call_diagnostics.py`) | HOLDS, double-pinned |
| 13 | Credential boundary: app reads `GROQ_API_KEY` (+ `GEMINI_API_KEY` judges-only, eval-only); Z.AI credential never used by the app; probes `--env-file` explicit-only (D-2026-09-05-01) | `agents/model.py` reads only `GROQ_API_KEY`; Anthropic path removed; probes `--env-file required=True` | `tests/test_model_config.py:11-27` (no-key RuntimeError; **Anthropic path structurally gone** — source scan); `.env.example` policy block | HOLDS |
| 14 | Seed provably immutable under correction (D-2026-09-04-10) | All writes go to `overrides.json` | sha256 before/after in 4 tests (§3.5) | HOLDS |
| 15 | Bounded loops: 3-round cap → UNKNOWN normalization; human rounds bounded at 5, not consuming graph rounds (build-contract §1; D-2026-09-04-10) | graph.py:59, 61, 288; `verdict_from_result` :261-280 | `tests/test_graph_routing.py` (13 edge-semantics tests incl. threshold value and cap force-route); `tests/test_graph_engine.py` (real-engine nomination order); `tests/test_gate_executor.py:340-374` (exhaustion audited) | HOLDS |
| 16 | Safe-action check deterministic, extraction-failure guarded (D-2026-09-04-08) | SafeActionComplianceEvaluator (run_evals.py:145-204) | `tests/test_span_shape.py` (6 tests pinning installed-SDK span shape + the provably-empty old guess); runtime evidence: 5/5 safe in both clean and retry-active runs (DOCUMENTED, EVALUATION §1) | HOLDS |
| 17 | EVAL_MODE signs with a public dev key; production key never defaulted/committed (e2e §6/§10) | `_token_key` human_gate.py:50-59 | `tests/test_gate_executor.py:102-109` (outside EVAL_MODE without secret → RuntimeError naming it; dev key value pinned as public-by-design) | HOLDS. Structural note: see GAP-8 |
| 18 | No secrets in tokens/audit/logs | Token payload = 5 scope fields only; audit rows carry no key material; rejected-calls args redacted | `tests/test_rejected_call_diagnostics.py:179-193` (redaction); `tests/test_groq_parsing_retry_offline.py:363-393` (retry evidence secret-free) | HOLDS. Note: `approver`/`reason`/`justification` are unvalidated free strings (arbitrary content can be persisted to the audit log via the web form) — accepted demo scope |

**Gaps — claimed or implied properties that could not be fully matched to
enforcement/tests (found by this task's inspection):**

- **GAP-1 (test coverage)**: no test asserts constant-time comparison. The
  signature site uses `hmac.compare_digest` (human_gate.py:105) and the scope
  sites are plain compares (:117, :123, :125, :133) — the e2e doc's §9 row
  "Constant-time signature comparison — HOLDS" is true but unqualified, and
  nothing pins the property mechanically. No security impact identified (only
  the signature is secret-derived), but the claim outruns the evidence.
- **GAP-2 (doc precision)**: README's diagram NOTE (README:84-85) attributes
  enforcement of invariant 1 to `guard-segregation-of-duties.sh` — the
  weakest layer (a same-line grep tripwire). README:111-117 states the
  primary mechanism (tool registration) correctly; the NOTE over-credits the
  guard. CLAUDE.md's "mechanically tripwired" phrasing is the accurate one.
- **GAP-3 (doc accuracy)**: `docs/human-gate-e2e-validation-2026-09-05.md:30`
  names `modern_status_values()` as a seed_data addition; the actual function
  is `status_values()` (seed_data.py:82).
- **GAP-4 (undocumented mechanism)**: the executor consumes the jti **before**
  applying (correction_executor.py:73-75 vs :81); an apply-side failure
  permanently spends the approval. No doc states this; no test exercises
  re-execution after a failed apply.
- **GAP-5 (uncaught edge)**: `float(payload.get("exp", 0))` (human_gate.py:115)
  raises uncaught on a correctly-signed payload with a non-numeric `exp`,
  bypassing `_fail` (no `correction_failed` audit row). Reachable only by a
  signing-key holder or a corrupted store — not by an external attacker.
- **GAP-6 (reliability)**: the executor tail is non-transactional — process
  death between `apply_correction` (:81) and the audit append (:88) leaves an
  effective override with no audit row and the ticket still open.
- **GAP-7 (reliability)**: single-writer assumptions everywhere — jti
  check+append TOCTOU across processes (human_gate.py:131-137),
  whole-file-rewrite updates (case_management.py:49-105), read-modify-write
  `overrides.json` (seed_data.py:140-148): concurrent approvals can duplicate
  applies or lose updates; a crash mid-rewrite can truncate a store. Within
  one web server, the request lock serializes handlers (web.py:305, 319);
  CLI+web or two processes are unprotected. Partially documented (e2e §10:
  "concurrent multi-process replay races are UNKNOWN").
- **GAP-8 (doc precision, structural)**: README:141 and EVALUATION §8.1 state
  "production requires `CORRECTION_TOKEN_SECRET`", implying a working
  production path is one key away. Structurally, every tool hard-fails unless
  `EVAL_MODE == "1"` (`require_eval_mode`, seed_data.py:29-36 — including
  `apply_correction` itself, modern_system.py:54), while `EVAL_MODE == "1"`
  forces the committed dev key (human_gate.py:51-52). **No full
  investigation→apply round-trip in this codebase can ever sign with
  `CORRECTION_TOKEN_SECRET`**; the secret is exercisable only in isolation
  (token issue/validate) or by tests. The e2e doc's "no production deployment
  exists" (§10) is the more accurate framing; `.env.example:34` itself says
  "future non-EVAL_MODE path".
- **GAP-9 (web surface fact)**: `approval/web.py:_form` (:292-295) reads
  `Content-Length` bytes unbounded — no request-size limit is claimed
  anywhere, but also none documented as absent in the e2e/loopback security
  notes; loopback-only exposure is the sole mitigating boundary.

---

## 5. Known limitations and open issues — consolidated, current

Status vocabulary: OPEN / PARTIALLY MITIGATED / WORKAROUNDED / ACCEPTED
RISK / ACCEPTED SCOPE / RESOLVED. Resolved items are listed at the end for
completeness, so a reader knows they need not be re-raised.

### 5.1 Accuracy and model behavior

1. **80.0% root-cause accuracy is a single data point** — 4/5 on the one
   leak-free run (2026-09-05; miss = case 2 duplicate-transaction → UNKNOWN
   after round exhaustion). "None of these is an established rate; a stable
   accuracy estimate requires repeated clean runs." OPEN; repeated clean
   runs require live-benchmark authorization. (DOCUMENTED,
   `docs/clean-5case-validation-2026-09-05.md` §4/§14; EVALUATION §3/§8.4.)
2. **Tool-parameter fabrication, 9 of 31 rows** (clean run; census recomputed
   twice): by tool — create_case_ticket 4 / search_transactions 3 /
   draft_correction 2; by component — reporter 6 / detector 3 / classifier 0;
   by parameter kind — unsupported confidence values 4 / invented IDs 4 /
   fabricated date windows 3 (kinds overlap). Leak-independent (four-step
   argument, reverification §2d); the literal date pair matches the
   detector's *instructed* 30-day default the judge cannot see ("judge-
   visibility artifacts as much as agent invention; they do not change the
   census"). OPEN remediation item; whether leak removal changed the rate is
   UNKNOWN. (DOCUMENTED, EVALUATION §5; index §2 row 2.)
3. **Attempt-1 (C-1004) draft-rejection, cause UNKNOWN — permanently**: the
   failure pre-dates the diagnostics log, so no record of the rejected call
   shape exists. Mitigation landed (rejected_calls.jsonl + viewer, commit
   `b2d153c`); **first live entry still pending** — no live run has occurred
   since. PARTIALLY MITIGATED (diagnosable going forward, uncharacterized as
   yet). (DOCUMENTED, `docs/draft-rejection-diagnostics-2026-09-06.md` §10;
   p0c §7.)
4. **Standing UNKNOWNs** (carried by the case-4 index §2): cause of the
   case-4 UNKNOWN→PASS flip across runs; leak-removal effect on fabrication
   rate; per-attempt placement of the pre-fix null-lottery kills;
   Windows-headed-GUI-click equivalence; host-side IPv4-loopback root cause;
   Attempt-1 call shape. (DOCUMENTED.)

### 5.2 Methodology (accepted, stated for precision)

5. **Judges remain label-sighted** — expected outputs are grader inputs;
   grader-legitimate, not contamination (leak-fix §8). **3/81 clean-run rows
   unjudged** (Gemini 503s; 96.3% coverage). The `_`-prefix filter is the
   enforced annotation boundary, not a full allowlist. ACCEPTED.
   (DOCUMENTED, leak-fix §8; clean §14.)
6. **Contaminated-figure ledger** (never cite as accuracy evidence; §0.3):
   89.8% (44/49), 93.0% (66/71), 85.07% (57/67), 68% and 16% (2026-09-04
   Experiment-driver step-6 aggregates), 0.00% (bootstrap-era all-fail, no
   signal either way), GLM "20/20" (wrong on its own terms — actual 19/19 —
   *and* contaminated; every "20/20" mention in the repo is wrong, per index
   §2 row 3), canary aggregates 12/15, 18/19, 13/15, 14/15. Canonical
   enumerations: leak-audit §7, leak-fix §6, EVALUATION §6 table.
   ACCEPTED (as excluded evidence). Not-contaminated carve-out: SafeAction
   apply_correction-clause results, rc=0 completion counts, retry/OTel/
   infrastructure-token figures.

### 5.3 Human-gate and control path

7. **WSL2 mirrored-mode IPv4-loopback blackhole**: 127.0.0.1 TCP blackholed
   both directions on this dev host, `::1` healthy; root cause host-side and
   UNMEASURED (`wsl --shutdown` is guard-blocked by design). WORKAROUNDED in
   code (`::1` accepted bind; tests bind `[::1]`; Windows-side validation
   used curl.exe). Host defect remains OPEN, out of repo scope. (DOCUMENTED,
   `docs/approval-web-loopback-fix-and-validation-2026-09-06.md` §1/§8.4.)
8. **Unauthenticated approver** — identity is a free string on both surfaces;
   loopback binding is a network control, not authentication. ACCEPTED RISK
   (build-contract §2.4 demo scope; stated on the page footer and in both
   validation reports). Plus GAP-9 (no request-size limit) and the absent
   TLS/CSRF/rate-limiting — same demo scope.
9. **Single-writer runtime stores** — GAP-7 detail: jti TOCTOU, whole-file
   rewrites, non-transactional executor tail. ACCEPTED for single-operator
   demo conditions; concurrent behavior UNKNOWN. (Partially DOCUMENTED, e2e
   §10; this task's OBSERVED code analysis extends it.)
10. **Headed-browser GUI click** — the only unexercised browser step:
    browser-rendered and HTTP-interactive validation are on record (incl.
    Windows headless + scripted APPROVE against the default bind); a headed,
    interactive human click has no artifact; headed≈headed equivalence is
    projected, not evidenced. OPEN (evidence gap, not a code defect).
    (DOCUMENTED, p0c §2.)
11. **Token-layer edge cases** — GAP-4 (spent-token on apply failure),
    GAP-5 (non-numeric `exp` crash path). OPEN (undocumented + untested; both
    key-holder-reachable only).
12. **Constant-time comparison untested** — GAP-1. OPEN (test-coverage gap).

### 5.4 Infrastructure and providers

13. **Retry exhaustion / multi-attempt ladders offline-proven only**; live
    record is single-attempt recovery 3× (2 in the retry-active run, 1 in
    the clean run, 0 exhausted). OPEN; closing it requires an authorized
    live canary. (DOCUMENTED, retry-canary §14/§15; EVALUATION §4/§8.5.)
14. **EVAL_MODE-only spine** — there is no real-system integration and no
    working non-EVAL_MODE execution path (GAP-8): "nothing in this repo
    warrants a 'financially safe' claim in any absolute sense" (e2e §10).
    ACCEPTED SCOPE.
15. **rejected_calls residuals** — spy covers `open`/`io.open` only
    (`os.open`/`mmap` would evade; the tripwire covers source references);
    `component` is a static `"reporter"` constant (must become call-time if a
    second agent ever holds these tools); free-text values are clipped, not
    masked; viewer `--limit 0` quirk. OPEN (minor, documented).
    (DOCUMENTED, draft-rejection §10.)

### 5.5 Project/process

16. **Repo PRIVATE** — public visibility for submission is a pending human
    decision. OPEN. (OBSERVED; EVALUATION §8.7.)
17. **Demo video NOT recorded** (shot-list exists in DEVPOST-DRAFT.md).
    OPEN. (DOCUMENTED, EVALUATION §8.3.)
18. **final-doc-config residuals (3, all still on disk — OBSERVED)**:
    `agent-memory/task-board.json` `single_model` line stale ("no second
    credential anywhere" — false since the Gemini-judge split);
    `agent-memory/task-contract-002-implementation.md:80-83` still states the
    GLM-5.3/Z.AI wiring without an annotation; `agent-memory/decisions.md`
    has no superseding entry recording the Z.AI→Groq switch (D-2026-09-04-09
    stands as the latest model-wiring entry). OPEN. (DOCUMENTED as residuals,
    `docs/final-doc-config-cleanup-2026-09-05.md`.)
19. **`orchestrator/graph.py:330-331` uncovered future channel**: the
    REQUEST_MORE_INFO instruction-append (`investigation_hint:`) is a
    potential label channel if a future hint ever carried case metadata —
    asserted clean today, unpinned for the future. OPEN (documentation-grade).
    (DOCUMENTED, clean §14.)

### 5.6 Resolved (do not re-raise)

- EVALUATION §8.1/§8.2 staleness ("approval surface NOT built", "diagram NOT
  created") — corrected by commits `c8fd329` and `f4b2ff8`; suite-count
  lineage updated to 218 (EVALUATION §9). RESOLVED.
- DEVPOST-DRAFT "UI is not built" staleness — corrected by the concurrent
  Devpost task, commit `f4b2ff8`. RESOLVED.
- Groq-free-tier trajectory-judge TPM blockage and the token-workload split
  question — RESOLVED by adoption of the Groq-agents + Gemini-judges split
  in all reported runs (`docs/token-workload-canary-2026-09-04.md`
  conditions adopted). RESOLVED.
- Approval-web loopback reachability gap ("cannot reach loopback") —
  SUPERSEDED: root-caused to the WSL2 host defect (item 7), `::1` added,
  live-validated. RESOLVED-as-workaround.
- `correction_draft_id` null-lottery — fixed (`str | None`) and live-proven
  (`docs/correction-draft-id-fix-canary-2026-09-04.md`). RESOLVED.
- Case-4 "Parsing failed" terminal kill — fixed (§2.6) and live-recovered.
  RESOLVED (with item 13 caveat).

---

## 6. Where the evidence lives — navigable map

**Reading rules inherited from the corpus**: for case-4 / tool-parameter
questions the authority is
`docs/case4-toolparam-evidence-index-2026-09-05.md` (the router: read order =
index → Report B → §5 follow-up → dissent review → Report A) — this section
does not duplicate its tables. Evidence under `agent-memory/evidence/` is
cited by **directory name, never internal run-id** (four directories share
the run-id `gemini-judge-5-case-2026-09-04` and are not the same run; index
§3). `docs/DEVPOST-DRAFT.md` is submission-facing draft text, not evidence,
and is excluded here.

### 6.1 Evergreen documents (undated, maintained)

| File | What it establishes | Status |
|---|---|---|
| `docs/build-contract.md` | The product source of truth: graph topology, agent prompts (byte-verbatim — tests pin them), tool schemas, §2.4 gate contract, §2.5 executor contract, §4 segregation invariant, §5 seed cases. Treated with contract discipline (CLAUDE.md); changes are Tier C. | Current |
| `docs/gotchas.md` | Profile gotchas, live-verified 2026-09-04: no Docker/Postgres by design (EVAL_MODE=1 mocks the systems); uv virtual project, never `uv init`; guard-is-tripwire-not-containment; Strands 1.54.0 API shapes; version-pin provenance. | Current |
| `docs/EVALUATION.md` | The submission-facing results authority: headline figures with taxonomy, leak narrative, contaminated-figure table, §8 unfinished list, §9 suite lineage. | Current (as of 2026-09-06) |
| `docs/architecture-diagram-2026-09-06.md` | Canonical Mermaid source of the README diagram (byte-identical, pinned by `tests/test_architecture_diagram_sync.py`), element→code accuracy map, SVG/PNG exports, render instructions. | Current |
| `docs/credential-alternatives-prompt.md` | Historical research prompt about the Z.AI/AnthropicModel era. | HISTORICAL / SUPERSEDED banner (annotated 2026-09-05) — do not act on it |
| `docs/provider-feasibility-cerebras-gemini.md` | Cerebras NO-GO (402 wall); Gemini conditional GO (native path only, thoughtSignature rule, ≤14 RPM). | Current (historical investigation) |

### 6.2 The ground-truth leak and the clean baseline (the accuracy chain)

| File | What it establishes |
|---|---|
| `docs/eval-ground-truth-leak-audit-2026-09-05.md` | **The leak discovery and contamination ruling** (authority): mechanism (label verbatim in instruction → detector prompt → SDK "Original Task:" prefix to all nodes), reach, per-metric scope table, §7 classification of every historical figure. |
| `docs/eval-ground-truth-leak-fix-2026-09-05.md` | The fix's three sites (instruction, `_comment` strip at read tools, rubric line), regression module `tests/test_eval_ground_truth_leak.py` — 7 functions / 23 cases in the single commit `cc6229d` (the doc's "18 new tests, 132→150" is its pre-commit working-tree count; the +5 cases came from the clean-run task; committed-state suite 129→152, MEASURED 2026-09-14), §6 contaminated-figure enumeration + "GOING FORWARD ONLY" scope. |
| `docs/clean-5case-validation-2026-09-05.md` | **The clean baseline** — the only leak-free run: 4/5 = 80.0% root cause (single OBSERVED data point), row rates, per-evaluator census, in-run retry event, token accounting, §11 comparison table (clean < contaminated is expected), §14 per-metric single-point limitations. |

### 6.3 Case-4 and tool-parameter fabrication chain

Read via `docs/case4-toolparam-evidence-index-2026-09-05.md` (the router;
introduces no new findings). Chain, in dependency order:
`docs/case-4-parsing-failure-audit-2026-09-04.md` (root cause of the
"Parsing failed" kill; carries the wrong "20/20" mentions, deliberately left
uncorrected) → `docs/gemini-judge-5-case-validation-2026-09-04.md` (NO-GO
2/5; the null-lottery) → `docs/correction-draft-id-fix-canary-2026-09-04.md`
(the `str | None` fix, live-proven) →
`docs/gemini-groq-5-case-final-validation-2026-09-05.md` (the case-4 UNKNOWN
run; presents the later-ruled-contaminated 89.8%) →
`docs/case4-outcome-and-toolparam-fabrication-audit-2026-09-05.md` (Report A;
**SUPERSEDED notice at its top** — retained solely for A-unique content:
§1d 20/20→19/19 erratum, §5 P0-B errata, cross-run rate table) →
`docs/case4-and-toolparam-fabrication-reverification-2026-09-05.md`
(**Report B, AUTHORITATIVE**: case-4 clean-run PASS; 9/31 census recomputed;
leak-independence argument §2d; Appendix A A-vs-B discrepancies) →
`docs/case4-annotation-dissent-review-2026-09-05.md` (the process record of
the supersession; 20/20→19/19 settled) →
`docs/case4-dissent-section5-verbatim-and-verification-2026-09-05.md`
(run4-attribution erratum CONFIRMED + LOW MATERIALITY; found the evidence-dir
run-id sharing).

### 6.4 Retry chain

`docs/groq-parsing-retry-canary-2026-09-05.md` (strategy implemented; live
canary clean but did not exercise live recovery — "GO WITH CAVEAT") →
`docs/groq-retry-active-5case-validation-2026-09-05.md` (retry-active 5/5
rc=0; 2/2/2/0 retry events — its **retry** figures remain citable; its
93.0% accuracy figure is contaminated, §5.2).

### 6.5 Human gate, approval surfaces, diagnostics (P0/P0-B/P0-C chain)

| File | What it establishes |
|---|---|
| `docs/human-gate-e2e-validation-2026-09-05.md` | The P0 human-gate build: canonical identity (the 44-spelling measurement), draft hygiene, `approval/` surfaces, Attempt-1 failure (kept, cause UNKNOWN) + Attempt-2 full success; §9 invariants table; §10 limitations. Carries three 2026-09-06 amendment blocks (`--bind ::1`; loopback gap superseded by the WSL2 root cause; Windows headless validation done, headed click outstanding). Known inaccuracies: `modern_status_values()` name (:30), §6 surface-wording (§7-items-5/6). |
| `docs/draft-rejection-diagnostics-2026-09-06.md` | The rejected-calls log: schema, proof-of-inertness (spy + tripwire), viewer; suite 190→216; §10 residuals. |
| `docs/approval-web-loopback-fix-and-validation-2026-09-06.md` | WSL2 v4-loopback blackhole diagnosis (probe matrix); `LOOPBACK_BINDS` fix; live Chromium 19/19 over `[::1]`; §4/§7 amendment blocks; §10 Windows default-bind validation addendum. |
| `docs/p0c-closeout-2026-09-06.md` | Approver-attribution fix, Windows-side default-bind validation, README split; suite 217. **Note**: its §4 "nothing pushed / origin untouched at e6770b5" was true at writing and is stale now (origin/main = `f4b2ff8`, pushed) — read §4 as session-scoped (§7-item-7). |
| `docs/local-path-ai-reference-audit-and-commit-2026-09-06.md` | Repo-wide local-path/AI-reference audit; the no-AI-attribution rule made mechanical (commit-msg hook); 13-commit landing. |

### 6.6 Provider, credential, and token-workload chain

`docs/token-workload-audit-2026-09-04.md` (the estimated 60-70% judge-token
split — superseded by the canary's measured figures) →
`docs/token-workload-canary-2026-09-04.md` (measured split; Groq 8K TPM
per-request cap rejected the trajectory judge 6× → free-tier NO-GO; GO WITH
VALIDATION for the split, conditions adopted) →
`docs/gemini-judge-canary-2026-09-04.md` (one-case split canary PASS;
trajectory judging on Gemini works) →
`docs/provider-feasibility-groq-two-keys-2026-09-04.md` (both keys one
shared Free pool; full-run NO-GO $0; PAYG ≈$0.10-0.17/run) →
`docs/provider-feasibility-cerebras-gemini.md` (see §6.1) →
`docs/probes-sibling-env-remediation-2026-09-05.md` (sibling-`.env` default
removed; `--env-file` explicit-only per D-2026-09-05-01) →
`docs/final-doc-config-cleanup-2026-09-05.md` (pyproject license, deploy
README, `.env.example` created; carries the three open residuals of §5.18).

### 6.7 Git history and repo-provenance chain (2026-09-05)

`docs/commit-history-audit-and-github-repo-plan-2026-09-05.md` →
`docs/git-identity-audit-stage1-2026-09-05.md` →
`docs/git-stage2-pre-rewrite-checkpoint-2026-09-05.md` (offline baseline 132
passed) → `docs/git-stage2-sha-rewrite-report-2026-09-05.md` (19-entry SHA
map) → `docs/git-stage2-final-report-2026-09-05.md` (identity rewrite,
Apache-2.0 LICENSE, private repo created) →
`docs/git-stage3-pending-work-audit-2026-09-05.md` →
`docs/git-stage3-final-report-2026-09-05.md` (commit #20 `e6770b5` pushed).
Also `docs/state-and-gap-analysis-2026-09-05.md` (the pre-push
submission-readiness audit at then-HEAD `316835f`).

### 6.8 agent-memory/ and evidence conventions

- `agent-memory/decisions.md` — the append-only decision ledger; every id
  D-2026-09-04-01 … D-2026-09-06-02 (one line each in the source; see §5.18
  for the known ledger gap). Notable: -04-04/-06 (segregation wiring + Tier-C
  rule), -04-08 (span-shape defect), -04-10 (token/HMAC + overrides +
  3-vs-5-round design), -04-11 (deliberately unused number), -05-01 (probes
  env-file), -06-01 (no-AI-attribution), -06-02 (loopback `::1` + P0-C).
- `agent-memory/task-board.json` — concurrency governor value 2 (enforced as
  a session cap by `scripts/ares-launch.sh`); carries the stale
  `single_model` line (§5.18).
- `agent-memory/task-contract-00{1,2}-*.md` — the build contracts (002's
  GLM/Z.AI constraint text is stale, §5.18).
- `agent-memory/guard-audit.log` — guard BLOCK/TRIP trail (never command
  text).
- `agent-memory/evidence/` — 14 directories + ~42 flat files of run
  artifacts (probe outputs, verify logs, eval row JSON, sequential-run
  results, approval-UI validation). Cite by directory name (§6 preamble).
- Dated run reports in `agent-memory/` (groq-preflight, gemini-feasibility,
  gemini-quota-provenance, human-gate-task-plan, and the two untracked
  2026-09-06 session reports from the diagram/Devpost tasks) — supporting
  provenance.

---

## 7. Improvement opportunities (prioritized, grounded in §1-§6 observations)

Explicitly split: **(a)** items that matter for submission quality before the
**2026-09-14** hackathon deadline, versus **(b)** longer-term engineering
health. Each item cites its grounding observation from this document. This
section is also where errors found in existing files are reported (per this
document's terms of reference, they are reported here, not fixed).

### 7.a Deadline-facing (before 2026-09-14)

1. **Qualify the judges wiring in README:124-127** (§2.7, GAP on judge
   attribution): the base harness — and therefore `scripts/verify.sh` step 6,
   which a judge might run — uses **Groq** judges (`evals/run_evals.py:75`);
   Gemini judges are the reported-run configuration via
   `evals/gemini_judge_5case.py`. One clarifying clause prevents a
   reproduce-it-yourself surprise. (Also EVALUATION §2 is already correct —
   README alone is unqualified.)
2. **Rebalance the README diagram NOTE (README:84-85)** (§4-GAP-2): name tool
   registration + `tests/test_agents.py`/`test_tools.py` as the enforcement
   and the guard as the tripwire complement — matching README:111-117 and
   CLAUDE.md. A security reviewer will probe the guard's self-documented
   blind spots; the README should not stake the claim on them.
3. **Amend the two e2e-doc inaccuracies** (§4-GAP-3, §7-item-6 below):
   `modern_status_values()` → `status_values()` (e2e :30); §6's "no token
   issuance/validation logic" → "no *authority*; the CLI's `--demo` path
   imports the token functions for the negative matrix only". Cheap
   annotate-don't-erase fixes consistent with repo practice.
4. **Add a push-state amendment note to `docs/p0c-closeout-2026-09-06.md`
   §4** (§4-GAP list / verified this task): its "nothing pushed; origin/main
   untouched at `e6770b5`. MEASURED." is session-true but now stale
   (origin/main = `f4b2ff8`). One dated amendment line prevents a cold reader
   from concluding the closeout was never pushed.
5. **The actual submission blockers are process items, already tracked**:
   repo visibility decision (§5.16) and the demo video (§5.17). Neither is a
   code change; both gate the submission more than any item here.
6. **Optional, high-leverage demo artifact**: the headed GUI click
   (§5.10) — one headed-browser session with a human APPROVE click closes
   the last unexercised browser step; alternatively state it as scoped-out
   in EVALUATION §8.

### 7.b Longer-term engineering health

1. **Pin constant-time comparison mechanically** (§4-GAP-1): a source-scan
   test in the style of the rejected-calls tripwire (assert
   `hmac.compare_digest` remains the comparator at human_gate.py's signature
   site, and that no secret-derived value is compared with `==`), or qualify
   the e2e §9 invariant row. Small, and it converts a documented claim into
   an enforced one.
2. **Document and test the spent-token-on-apply-failure behavior**
   (§4-GAP-4): decide whether an apply-side failure should leave the
   approval spendable (e.g. defer consumption until after a successful
   apply, with compensating single-use risk) or keep current semantics and
   document them; add the re-execution-after-failed-apply test either way.
   Touches `correction_executor` — **Tier C** per CLAUDE.md.
3. **Harden the token parser edge** (§4-GAP-5): wrap the `exp` coercion
   (human_gate.py:115) to return a rejection instead of raising — removes
   the one uncaught, un-audited failure path. Tier C (human_gate).
4. **Concurrency story for runtime stores** (§4-GAP-7): either adopt
   append-only/locked protocols (file lock around jti check+append;
   temp+rename for whole-file rewrites) or make the single-operator
   assumption explicit in one place (it is currently split across e2e §10
   and code comments).
5. **Bound the web form read** (§4-GAP-9): cap `Content-Length` in
   `approval/web.py:_form` and note it in the surface docstring.
6. **Clear the three final-doc-config residuals** (§5.18): task-board
   `single_model`, task-contract-002 GLM text (annotate), and the missing
   decisions.md entry recording the Z.AI→Groq switch — the ledger gap is the
   one most likely to mislead a future agent session.
7. **README runtime-tree line (README:200)** (agent-A observation, verified):
   describes `runtime/` as "gate state: audit log, consumed tokens"; the
   dominant stores are drafts/tickets (and audit_log.jsonl does not currently
   exist on disk — created on demand). One-line completeness fix.
8. **Rejected-calls follow-ups** (§5.15): make `component` call-time-derived
   if any second agent ever receives these tools; fix the viewer `--limit 0`
   quirk; capture the first live entry on the next authorized live run
   (§5.3) and characterize the Attempt-1 class or close it as permanently
   unknown.
9. **Suite-count drift automation** (observation: 218 is hand-cited in
   EVALUATION §9 with a lineage; every new test changes it): either generate
   that line or drop the absolute number for the command. The same applies
   to file:line citations in this document — a drift-check test in the style
   of `tests/test_architecture_diagram_sync.py` could pin the few
   load-bearing anchors (thresholds, TTL, bind set) cheaply.
10. **`RUNTIME_DIR` env-var footgun** (§2.5.3): a set `RUNTIME_DIR`
    environment variable is silently ignored (module attribute is the seam);
    a startup warning when the env var is present would prevent a
    repeat of the documented incident.
11. **Repeated clean runs** when live authorization is available (§5.1) —
    the only way to turn 80.0%-single-point into a rate; also closes the
    fabrication-rate-vs-leak UNKNOWN.

---

## 8. How to verify any claim in this document

### 8.1 Offline, no credentials, safe to run anytime

```bash
cd "$(git rev-parse --show-toplevel)"

# The offline suite (verify.sh step 5 exactly). Expected at HEAD f4b2ff8:
# 218 passed. MEASURED during compilation: 8.22 s, zero git-status delta.
uv run --locked pytest -q

# The segregation tripwire (verify.sh step 2's first half):
bash scripts/guard-segregation-of-duties.sh .

# Pre-commit wiring (verify.sh step 2's second half):
git config core.hooksPath        # -> scripts/hooks

# Offline rejected-calls viewer (read-only):
python scripts/show_rejected_calls.py --all

# Any file:line citation in this document: open the file at the line, e.g.
sed -n '59,66p' orchestrator/graph.py   # MAX_INVESTIGATION_ROUNDS / threshold
```

`scripts/verify.sh` steps 1-2 and 4-5 are offline (step 4 syncs the committed
lockfile; it downloads from PyPI only if the local cache is cold); step 3 is
an advisory PyPI freshness check (network, PASS either way); **step 6 is the
live benchmark** (`EVAL_MODE=1` mock-ledgers + real Groq calls) — do not run
it without quota authorization. Full-pipeline runs belong to the QA seat per
CLAUDE.md (verify.sh header).

### 8.2 Claim classes and their re-verification

| Claim class in this document | How to re-verify | Feasible offline? |
|---|---|---|
| Code structure, signatures, constants, validation chains (§2) | Read the cited `file:line` at HEAD `f4b2ff8`; citations drift one line per intervening edit | Yes |
| Test matrix (§4 column 4, §8.1) | Read the cited test; run the suite | Yes |
| Store schemas and lifecycles (§3) | Read the writer code cited; inspect `runtime/` | Yes |
| Invariant GAPs (§4) | Reproduce the cited code paths (e.g. GAP-5: read human_gate.py:115 with no enclosing try) | Yes |
| Suite count (218) | `uv run --locked pytest -q` | Yes (MEASURED this task) |
| Guard/hook wiring | `git config core.hooksPath`; `ls -l scripts/hooks` | Yes |
| Clean-run 80.0%, retry live-recovery figures, 5/5 SafeAction run results | **Cannot** be re-derived offline — they are properties of authorized live runs; re-verification requires live-benchmark authorization (quota + human approval, per repo policy). The reports and evidence directories (§6) are the record. | No |
| Windows-side browser validation, WSL2 host networking facts | Environmental: artifacts under `agent-memory/evidence/` are viewable; re-execution needs the Windows host / the specific WSL2 configuration | No |

### 8.3 Freshness

This document's citations are exact at `f4b2ff8`. After any commit, treat
line numbers as ± the diff; re-run §8.1 before trusting the suite-count and
guard claims. Sections 4-§7 reflect the *state of enforcement and evidence*
as of the compilation date and are the parts most likely to age; §2-§3 age
only with deliberate code change (most of it Tier C by CLAUDE.md).
