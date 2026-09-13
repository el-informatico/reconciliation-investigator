# approval/web.py loopback fix + live-browser validation (2026-09-06)
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

> REDACTED 2026-09-07 (privacy pass): sibling-project names and
> out-of-repo local paths in this report were replaced with neutral tokens
> ([SIBLING-A]…[SIBLING-J], ~) before publication; originals preserved in
> the author's private pre-rewrite bundle.

Task: research this machine's loopback-connectivity fix via sibling
projects (explicitly authorized, read-only, THIS TASK ONLY), apply a
minimal fix to `approval/web.py`, and validate the screen in a real
browser. Commissioned directly by the human owner; gated Tier C
(Architect PROCEED-WITH-CONDITIONS C1–C8, all discharged here).

Claim tags: MEASURED (instrumented this run) / CALCULATED (derived) /
OBSERVED (seen, not instrumented) / DOCUMENTED (cited from a prior
record) / PROJECTED (prediction) / UNKNOWN (open).

---

## 1. Root cause — MEASURED

The prior gap ("this dev environment cannot reach loopback listeners
from the shell", docs/human-gate-e2e-validation-2026-09-05.md §10) is
NOT the Claude-Code sandbox and NOT generic WSL2 breakage. On this
host (WSL2 Ubuntu 24.04, kernel 6.18.33.2-microsoft-standard-WSL2,
`networkingMode=mirrored`):

- `ip route get 127.0.0.1` → `via 169.254.73.152 dev loopback0 table 127`
  — mirrored-mode policy rules (`ip rule show`: priority-1 `ipproto
  tcp/udp lookup 127/128`) hijack IPv4 TCP/UDP lookups for 127.0.0.0/8
  into the loopback-mirroring machinery, which **blackholes** them
  here. MEASURED 2026-09-06, unsandboxed.
- A stdlib server bound 127.0.0.1 and connected to from the **same
  process** times out — MEASURED (rules above, so even in-process v4
  loopback dies).
- Same result with the Bash-tool sandbox disabled — the sandbox is
  exonerated. MEASURED.
- WSL→Windows IPv4 loopback (port 135 RPC) also times out. MEASURED.
- ICMP to 127.0.0.1 answers (rules only match tcp/udp). MEASURED.
- **IPv6 loopback `::1` TCP is fully healthy** (bind + connect + HTTP
  200 in-process and cross-process). MEASURED.
- Windows→WSL IPv4 loopback **works**: native `curl.exe` from Windows
  fetched a WSL-bound 127.0.0.1 listener (HTTP 200) and a dual-stack
  `::` listener via `localhost` (200); a `::1`-only listener is NOT
  reachable from Windows (timeout). MEASURED.
- `/etc/hosts` maps `localhost` → 127.0.0.1 only, so every WSL client
  that says `localhost` hits the blackhole. OBSERVED.
- Windows `chrome.exe` / `powershell.exe` spawned from this shell hang
  (>2 min on `--version` / first request); `curl.exe` and `cmd.exe`
  are fast. OBSERVED. (So driving a Windows-side browser from this
  shell is not viable; see §4's honesty boundary.)

Probe matrix (WSL-bound listener → client), MEASURED — full transcript
in `evidence/probes.txt` (re-measured 2026-09-06T06:53Z, reproducing
the ~01:30Z originals exactly; routing/rules/hosts dumps included):

| bind | WSL client | Windows client (`curl.exe`) |
|---|---|---|
| `127.0.0.1` | timeout (blackhole) | **200 OK** (also via `localhost`) |
| `::1` | **200 OK** | timeout |
| `::` dual-stack | 200 via `[::1]` | 200 via `localhost` — but all-interfaces exposure |

## 2. Phase 1 — sibling research (read-only, authorized for this task)

Inspected read-only: `~/projects/[SIBLING-G]`, `aresV2`,
`[SIBLING-B]`, `[SIBLING-A]`. **No sibling was
modified; nothing was executed inside any sibling; no `.env`,
credential, or secret file was opened** ([SIBLING-A]'s
`.env`/`.env.local` and [SIBLING-G]' `credential-precheck.sh` were
deliberately skipped). DOCUMENTED/OBSERVED via the delegated read-only
research agent (paths below are sibling-internal, cited for the human's
verification only):

- **[SIBLING-G]** had already diagnosed this exact host defect (2026-08-18,
  `agent-memory/evidence/phase7-part-c/c3-host-loopback-diagnosis.txt`):
  IPv4 127.0.0.1 inbound TCP dropped at filter level, `::1` healthy,
  sandbox exonerated — matching §1's independent re-measurement. Its
  distilled technique (lesson L012,
  `agent-memory/lessons.md`): *the loopback address must be a
  flag/env value with a committed loopback default — never a hardcoded
  single literal discovered broken later.* It also validated an
  all-IPv6 live chain and a bounded "probe ::1 then 127.0.0.1,
  first that answers wins" fallback.
- **[SIBLING-A]** proved the Windows-browser path under
  mirrored networking (Vite bound `::`, Windows Edge at
  `http://localhost:PORT`; README 147–152).
- **aresV2** corroborates the machine facts (same kernel, mirrored
  networking, tailscaled host-side;
  `wsl2-memory-analysis-2026-09-04.md` §1) but runs no web server.
- **[SIBLING-B]** sidesteps host loopback entirely (one-shot
  Docker verify containers, where v4 loopback is healthy) — a
  different technique, not applied here (heavier than an approval
  screen needs, and it would not serve a browser without published
  ports).

**Technique reused (general pattern, no sibling code/config copied):**
[SIBLING-G]' L012 loopback-literal-as-flag pattern, restricted to loopback
literals only — i.e. this repo's `--bind` keeps a committed
`127.0.0.1` default and additionally accepts the `::1` loopback
literal, with everything else still refused. [SIBLING-A]'s
all-interfaces `::` bind was deliberately NOT adopted: with tailscale0
and a LAN-facing eth2 live in WSL, `::`/`0.0.0.0` would NOT be
local-only exposure (CALCULATED; interfaces MEASURED via `ip addr`).

## 3. The fix (Phase 2a) — MEASURED + DOCUMENTED

`approval/web.py` only (diff: +58/−21 lines against 8552390; the
APPROVE/REJECT/REPLAY handlers, routes, token/session state, and
EVAL_MODE handling are byte-untouched — C1):

1. `LOOPBACK_BINDS = ("127.0.0.1", "::1")`; `--bind` default stays
   `LOOPBACK = "127.0.0.1"`. Acceptance is exact set membership — no
   name resolution, no wildcards: `localhost`, `::`, `0.0.0.0`, LAN
   addresses all still exit 2 with the loopback-only rationale.
   (Regression-tested: `test_bind_accepts_only_loopback_literals`.)
2. `_ThreadingHTTPServerV6` (AF_INET6 subclass) so the `::1` literal
   can bind; `build_server()` is the single construction path shared
   by `main()` and the tests (no second wiring can arise).
3. Startup URL prints bracketed (`http://[::1]:8765/`) for v6.
   Docstring/`--help` updated; module docstring of
   `tests/test_approval_surface.py` rewritten (it documented the old
   "HTTP layer NOT exercised" limitation).

Launch for validation was exactly:
```
uv run --locked python -m approval.web --customer C-1004 --bind ::1 \
  --port 8765 --approver browser-validation-2026-09-06 \
  --runtime-dir agent-memory/evidence/approval-web-loopback-2026-09-06/runtime
```

### Security-boundary assessment — EXPLICIT (task requirement)

- The security boundary is the deterministic spine behind the screen
  (canonical identity → gate → scoped, expiring, single-use token →
  executor that validates before mutating), NOT the network binding.
  The change touches zero spine code; APPROVE still routes
  `run_human_gate` → `apply_gate_approval` (the single shared
  composition; `approval/` still contains no `apply_correction`
  reference — segregation guard PASS, verify step 2). MEASURED.
- Loopback-only scope preserved: both accepted literals are loopback
  addresses (127.0.0.1 RFC 1122; ::1 RFC 4291 §2.5.3). Exposure
  NARROWS, not widens: on this machine a `::1` bind is unreachable
  from Windows (MEASURED), while the unchanged `127.0.0.1` default
  remains Windows-reachable via mirrored localhost (MEASURED 200 OK).
  No firewall/WSL step was needed precisely because no non-loopback
  address became bindable.
- `docs/build-contract.md` prescribes no bind address (§2.4 is about
  interface scope and token scoping) — no contract text changed.
  DOCUMENTED (Architect-verified).

## 4. Live validation (Phase 2b) — MEASURED

Setup: fresh synthetic C-1004 case (the same seed case the CLI
validation used), seeded deterministically via the real store tools
(`draft_correction` + `create_case_ticket`; draft
`DRF-62da3621be9a`, ticket `TCK-cea240c5ad42`, evidence ref
`EVT-L-40041` from the customer's actual seed event) into an isolated
`--runtime-dir`. **Zero LLM/API calls anywhere in this validation**
(no benchmark, no canary, no live graph run).

**What was verified by REAL BROWSER INTERACTION** (headless Chromium
engine via Playwright 1.x in a `/tmp` scratch venv — not the project
env; driving `http://[::1]:8765/` with real form submissions;
19/19 checks PASS, raw log + screenshots in the evidence dir):

- Cards render in the browser: Case card (C-1004, ticket id, root
  cause `LEGACY_MODERN_STATUS_DISAGREEMENT`), Proposed-correction card
  (field `status`, `ACTIVE → SUSPENDED`, justification, draft id),
  enabled APPROVE/REJECT buttons. Full-page screenshots captured at
  each stage (1280 px wide; height grows as cards accumulate).
- **Real click on APPROVE** (form POST `/approve`) → Execution result
  card: status `applied`, `before=ACTIVE after=SUSPENDED`,
  `no_op=False`, audit `AUD-2cac68807ede`, ticket `resolved`.
- **Real click on "Attempt replay of the consumed capability"** →
  Replay result card: `failed`, "the executor refused the replay, as
  it must", "token already consumed (single-use)".
- APPROVE is disabled after execution (no pending draft) — the UI
  cannot re-approve; a forced `POST /approve` bypassing the disabled
  button is refused server-side (HTTP 500, "cannot approve: no
  pending correction draft", server-console traceback recorded).

**The APPROVE click invoked the SAME deterministic gate, not a second
implementation** — evidenced three ways: (a) code: `web.py _do_approve`
calls the spine (`run_human_gate`, `apply_gate_approval`) and
`approval/` has no `apply_correction` reference; (b) the browser-driven
run produced the same artifact chain the CLI validation produced —
`gate_approval` → `correction_applied` → `correction_failed` audit
rows, draft `applied`, ticket `resolved`, exactly one consumed jti,
`overrides.json` mutation `C-1004.status = SUSPENDED` (full dump in
the evidence dir); (c) the new HTTP-layer tests assert that chain
against the store, over real sockets.

**Verified by server-side logs / store only (not browser):** the
request log (GET 200, POST /approve 200, POST /replay 200, forced
POST /approve 500), the store dump, and repo-integrity re-checks —
seed sha256 unchanged (`seed-sha256.txt`); repo `runtime/` FILENAME
SET identical before/after (listing diff at validation time;
`repo-runtime-before.txt`) with post-run content hashes captured in
`repo-runtime-sha256-after.txt`. Precisely: the before-capture was a
filename listing, not hashes, so content byte-identity across the run
is not separately proven (UNKNOWN in the strict sense; contamination
is implausible — all validation ran against the isolated
`--runtime-dir` and the suite uses tmp_path isolation). Working-tree
snapshot: `git-status-after.txt` — among tracked files this task
modified exactly `approval/web.py` and
`tests/test_approval_surface.py`; the other modified/untracked files
are the concurrent session's and the held README.md.

**Honesty boundary — what was NOT verified here:**
- A Windows-side GUI browser (Edge/Chrome) opening
  `http://localhost:8765` against the default `127.0.0.1` bind:
  reachability is curl-exe-MEASURED (200 OK), but no GUI browser was
  driven from Windows — `chrome.exe`/`powershell.exe` spawned from
  this shell hang (OBSERVED), so that remains the human's check.
  > AMENDED 2026-09-06 (P0-C closeout): an AUTOMATED Windows-side
  > validation of the default bind has since run — real Windows
  > Edge/Chrome **headless** engines rendered the screen (DOM dumps +
  > PNG screenshots) and a native Windows client scripted the APPROVE
  > through the real gate; see §10. The prior "hang" was a launched
  > persistent GUI session whose launcher never exits, not a deadlock.
  > A headed, interactive GUI click remains the only unexercised step.
- The screenshots are verified as structurally valid full-page PNGs
  (1280×1700/1821, `file` MEASURED); this agent could not visually
  inspect their pixels (no image rendering in this seat) — the render
  claims rest on the browser's own DOM/text assertions, which ARE
  render-level. OBSERVED/MEASURED as stated.
- The "forced re-approve" was a browser-context request (Playwright
  `ctx.request`), not a button click — the honest click-path
  equivalent is the disabled-button check preceding it.
- Headless-Chromium-in-WSL is a real Chromium engine but not a
  human's interactive browser session. PROJECTED: nothing observed
  suggests headed behavior differs (plain HTML forms, no JS).

## 5. Tests and verification — MEASURED

- `tests/test_approval_surface.py`: 8 existing tests untouched + 5 new
  real-socket HTTP-layer tests over `[::1]` (cards; approve → store
  chain; replay refused single-use; second approve → 500; bind refusal
  for `0.0.0.0`/`::`/`localhost`/LAN).
- Full suite: **214 passed** (`uv run --locked pytest -q`). The tree
  also carries a concurrent session's new tests (suite was 190 at the
  human-gate task); everything passes together.
- verify.sh steps 1–5 replicated individually, all PASS (preflight;
  segregation guard + hook wiring; uv sync --locked; pytest; PyPI
  freshness advisory, all pins current). **Step 6 (the live 5-case
  benchmark) EXCLUDED per task contract** — precedent: e2e report §8.
  Log: `agent-memory/evidence/approval-web-loopback-2026-09-06/verify-steps-1-5.txt`.
- No benchmark, canary, or other live LLM/API call was run. MEASURED
  (no such command executed this task).

Evidence dir: `agent-memory/evidence/approval-web-loopback-2026-09-06/`
— seed-output.json, server-console.txt (full request log + designed
refusal traceback), browser-run.txt + browser/browser-checks.json +
3 screenshots, runtime-store-after.txt, runtime/ (isolated store),
verify-steps-1-5.txt, seed-sha256.txt, repo-runtime-before.txt,
probes.txt (loopback diagnosis transcript, re-measured 2026-09-06T06:53Z),
repo-runtime-sha256-after.txt, git-status-after.txt. Reviewer verdict:
ACCEPT (two MINOR evidence-hardening findings, both discharged by the
three artifacts added above).

## 6. Sibling-project integrity — CONFIRMED

- No sibling directory was modified, written to, or executed in.
  (Read-only delegation; no sibling file content entered this repo
  except the general technique descriptions above.)
- No `.env`, credential, or secret file from any sibling — or from
  this repo — was opened, read, printed, or persisted. Skipped on
  sight: [SIBLING-A] `.env`/`.env.local`; [SIBLING-G]
  `scripts/lib/credential-precheck.sh` (credential-named).
- The authorization was task-scoped and does NOT extend to future
  tasks. DOCUMENTED (task text) + OBSERVED (this run).

## 7. Known defect noted (NOT fixed here — out of scope)

`web.py _do_approve` calls `apply_gate_approval(case_id, outcome,
draft)` without the `approver` kwarg, so a custom `--approver` reaches
the `gate_approval` audit row but the executor's `correction_applied`
row records the default `"human"` (visible in this run's audit dump:
approver `browser-validation-2026-09-06` vs `"human"`). Audit
attribution only; no authorization effect. Fix is one kwarg + one
test assertion — left for a deliberate Tier-C pass.

> AMENDED 2026-09-06 (P0-C closeout): FIXED — `_do_approve` now passes
> `approver=approver` to `apply_gate_approval`, matching the CLI-path
> forwarding in `orchestrator/graph.py` and `_do_replay`'s existing
> kwarg. Regression test
> `test_http_layer_approve_records_approver_in_both_audit_rows`
> (negative-control-verified: failed pre-fix on exactly the
> `correction_applied` approver). Live-confirmed by a Windows-originated
> approval — both audit rows carry the custom approver (§10 evidence).
> Commit hashes: docs/p0c-closeout-2026-09-06.md §4.

## 8. Follow-ups for the human

1. **Commit decision**: this change is uncommitted (working tree), per
   the task's no-commit instruction. Diff: `approval/web.py`,
   `tests/test_approval_surface.py`, this doc, the decisions entry,
   two annotation blocks in `docs/human-gate-e2e-validation-2026-09-05.md`,
   plus the evidence dir. Nothing staged; nothing pushed.
2. **Windows GUI check** (the one remaining browser step): with the
   default binding, run the screen and open `http://localhost:8765`
   in Edge/Chrome on Windows.
   > AMENDED 2026-09-06 (P0-C closeout): done by AUTOMATED tooling to
   > the browser-rendered + HTTP-interactive level (headless Edge/Chrome
   > DOM + screenshots, native-client scripted APPROVE through the real
   > gate) — see §10. Only the headed interactive click is left for a
   > human who wants it.
3. **README line** (held per D-2026-09-06-01): "the browser screen has
   no live-browser validation in the dev environment" is now stale.
4. Optional: the host-side IPv4-loopback blackhole itself (Windows
   Firewall / Hyper-V mirrored policy / Tailscale WFP — root-cause
   candidates per [SIBLING-G]' diagnosis) can only be chased from the Windows
   side with admin rights; `wsl --shutdown` class fixes are
   guard-blocked here by design. UNKNOWN which component drops it.

## 9. Classification summary

- Loopback diagnosis, probe matrix, browser checks, store artifacts,
  test/verify results, integrity hashes: MEASURED.
- "Narrows exposure", "`::` would expose LAN/tailscale": CALCULATED
  from MEASURED interfaces/rules.
- chrome.exe/powershell.exe hangs, concurrent-session tree changes:
  OBSERVED.
- Sibling techniques, prior e2e claims, contract scope: DOCUMENTED.
- Headless≈headed for this page: PROJECTED.
- Host-side root cause (which Windows component drops v4 loopback);
  Windows GUI-browser behavior: UNKNOWN (not testable from this seat).
- Windows-side default-bind validation (2026-09-06 closeout §10):
  browser render (DOM + screenshots) and scripted HTTP approve from
  native Windows clients: MEASURED; headed interactive GUI click:
  UNKNOWN (headless engines + native HTTP client only).

## 10. Addendum — Windows-side automated validation of the default
## binding (2026-09-06, P0-C closeout)

Human decision for the closeout task: do not wait for manual
Windows-browser confirmation; validate the unchanged default
(`127.0.0.1`) binding with automated tooling instead.

- **Method**: Windows curl.exe (native client) + real Windows browser
  engines headless — Edge 152.0.4191.62 `--headless=new --dump-dom`,
  Chrome 152.0.7977.76 `--headless=new --screenshot` — each spawned
  from this WSL shell with a throwaway `--user-data-dir`, completing in
  ~1 s. powershell.exe remains unusable from this shell (hangs in every
  variant, including via cmd.exe). MEASURED.
- **Setup**: fresh synthetic C-1001 case (balance 1250.00 → 1500.00,
  draft `DRF-359ed2fed288`, ticket `TCK-095f5266963b`), isolated
  `--runtime-dir`, server launched with NO `--bind` flag (committed
  default `127.0.0.1`), port 8791, `--approver
  windows-default-bind-2026-09-06`. Zero LLM/API calls.
- **Results**: 9/9 initial-render content greps in the Edge DOM dump
  (case card, ticket, root cause, correction card with values and draft
  id, approve form, security footer); Chrome PNGs 1280×900 before and
  after approval; scripted `POST /approve` from curl.exe → Execution
  result card (`applied`, `AUD-da0a75f69c2d`, ticket `resolved`);
  scripted `POST /replay` → refused "token already consumed
  (single-use)". Store: `gate_approval` AND `correction_applied` both
  carry `approver=windows-default-bind-2026-09-06` (live confirmation
  of the §7 fix), draft applied, ticket resolved,
  `overrides C-1001.balance=1500.0`, exactly one consumed jti.
  MEASURED; full log: evidence dir `windows-run.txt`.
- **Incident, disclosed**: the first seeding attempt set a `RUNTIME_DIR`
  env var, which `tools/seed_data.py` does not read (the store location
  is its `RUNTIME_DIR` module attribute) — two rows appended to the
  REPO's `runtime/` store. Detected immediately; both lines truncated;
  all three repo runtime files verified byte-identical (sha256) to this
  doc's `repo-runtime-sha256-after.txt` capture before and after the
  validation. Nothing executed against those rows; nothing consumed.
- **Honesty boundary**: verification level = BROWSER-RENDERED (real
  Windows Edge/Chrome engines, DOM + screenshots) + HTTP-INTERACTIVE
  (native-client scripted form POSTs through the deterministic gate).
  NOT done from Windows: a headed, interactive GUI click (headless
  dump/screenshot cannot click; click-level evidence remains the
  Playwright run over `::1`, WSL side).
- **Cleanup**: server stopped, port released, Windows temp dir deleted
  (verified absent), no scheduled tasks created, no persistent Windows
  state. Evidence:
  `agent-memory/evidence/approval-web-windows-default-bind-2026-09-06/`.
