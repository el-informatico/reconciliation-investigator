# Dissent-review §5 — verbatim reproduction and per-item verification
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

Date: 2026-09-05 · Mode: READ-ONLY follow-up (this file is the only artifact
created; no other file edited, created, or deleted; nothing staged,
committed, or pushed; no tests, benchmarks, canaries, or live LLM/API calls;
the separately-approved §6 notice amendment was NOT applied) · Subject:
full verbatim content of §5 of
`docs/case4-annotation-dissent-review-2026-09-05.md` (the "new findings"
section, headed "Additional findings this review surfaced (beyond the
dissent's items)"), and an evidence-traced verification of each item —
centered on the run4-attribution erratum shared by report A
(`docs/case4-outcome-and-toolparam-fabrication-audit-2026-09-05.md`) and
report B (`docs/case4-and-toolparam-fabrication-reverification-2026-09-05.md`).

**Method.** The main session re-verified every load-bearing premise directly
(reads/greps/stats of the attempt logs, `impl-diff-2026-09-04.txt`,
`runtime/tickets.jsonl`, `runtime/drafts.jsonl`, and the three reports
themselves, with line numbers). Three delegated read-only lanes ran in
parallel: (L1) repo-wide run-ordinal numbering inventory; (L2) per-run
ground-truth extraction from the evidence directories; (L3) correction-status
and materiality-surface sweep (notices, README/pitch/submission surfaces,
memory, git log). Where this report says MEASURED, the fact was re-verified
against raw artifacts in THIS task (main session or lane); DOCUMENTED means
quoted from an existing report with no independent source on disk;
CALCULATED means derived here from MEASURED premises. Full classification
table in §7.

**Line-number convention.** Report A's current numbering includes the 18-line
SUPERSEDED notice (lines 1–18; original content starts at line 19) — all `A:NNN`
citations below are current, matching the dissent review's convention. `B:NNN`
citations are to unmodified report B. Dissent-review citations use `DR:NNN`.

---

## 0. Executive summary

1. §5 contains THREE items, not one — §5a (a genuine A-vs-B factual
   disagreement on run-1 case-4 verdict preservation), §5b (the
   run3c/3d/3e adjudication, which ENDS with the run4-attribution erratum
   shared by both reports), and §5c (the blind second ruling on the STOP
   override). The prior relay to the human compressed §5a and §5c along with
   the run4 item. MEASURED (direct read of DR:471–556).
2. "run4" is NOT any of the three runs named in the task context (pre-retry
   5-case, retry-active 5-case, clean 5-case). It is the fourth numbered
   GLM-era Experiment-driver attempt of 2026-09-04
   (`agent-memory/evidence/evals-run4-official.txt`), hung at
   `await queue.join()` and SIGINT-killed at 16:52:54Z. MEASURED.
3. The erratum: both A (A:93, and affirmatively A:111–114) and B (B:85)
   attribute the 17:21:17Z case-4 pass (`TCK-4e744f8f7592`,
   `tickets.jsonl:31`) to run4-official's window. That execution provably
   died at 16:52:54Z — 2m19s before the first ticket (16:55:13Z) of the
   c1→c4 progression that produced the pass, and its death was already
   recorded in `impl-diff-2026-09-04.txt` (line 724) by 17:12:19Z, nine
   minutes before the pass. The pass belongs to a subsequent, unlogged
   execution. Premises MEASURED in this task; conclusion CALCULATED
   (the dissent review had tagged the same conclusion INFERRED).
4. Materiality, plainly: NO citable headline figure is affected — the pass
   itself is DIRECT in the ticket store, its existence and count are
   attribution-independent, no accuracy/token/retry/security figure anywhere
   depends on run4, the README carries no figures at all, and nothing is
   published. The damage is confined to the run-history narrative inside A
   and B — including a row-4-vs-row-5 self-contradiction inside B, the
   designated authoritative report. MEASURED (L3 surface sweep + L1 figure
   provenance).
5. Correction status: the erratum is corrected ONLY in the dissent review
   itself (DR:56–59, DR:520–530, DR:646). A and B both carry it live and
   unflagged as they stand; A's SUPERSEDED notice routes readers to B, which
   repeats the identical mis-attribution with no notice mechanism of its own.
   NOT moot for readers who arrive via the supersession chain. MEASURED.
6. Per-item recommendation (§6 below): fold the run4 erratum into the planned
   closure/index task (strongest of the three); fold §5a as one index line;
   record §5b's B:84 inference-as-fact caveat in the index; take no
   correction action for §5c beyond citing the dissent review.

---

## 1. §5 reproduced in full, verbatim

Source: `docs/case4-annotation-dissent-review-2026-09-05.md`, lines 471–556
(read directly in this task). Source hard line-wraps are preserved exactly,
including hyphen- and filename-splits at line ends.

```text
## 5. Additional findings this review surfaced (beyond the dissent's items)

### 5a. A genuine, previously-unfound A-vs-B factual disagreement: run-1
case-4 verdict preservation. MEASURED.

A:91 (§1b row 1): "**classifier verdict NOT preserved — UNKNOWN**". B:82
(§1b row 2): "not preserved in eval rows; ticket `TCK-eeac66ba7362`
`manual_override` (attribution by timing — INFERRED) … 0.95 (ticket)". The
artifact: `runtime/tickets.jsonl:7` = `TCK-eeac66ba7362`, C-1004,
`manual_override`, 0.95, created 2026-09-04T14:13:30Z — inside run 1's
window, via the same ticket-store channel A itself accepts for the 17:21 pass
and the clean run's confidence. **B matches the artifact; A's "NOT preserved"
is wrong unless the ticket's window attribution fails** — the ticket's
existence, content (`manual_override` @ 0.95), and 14:13:30Z timestamp are
MEASURED; its assignment to run 1 rests on timing (INFERRED, as B itself
tags it); and A is self-inconsistent here either way (A:392 claims to have
extracted "all 8 C-1004 tickets", which includes this one). Materiality:
negligible — no
determination changes (neither report counts run 1 among the prior passes;
the single-UNKNOWN claim is unaffected, since run 1's "UNKNOWN" was
absence-of-record, not an UNKNOWN emission). But it is a fact both reports
state, stated differently — the first true counterexample found to an
unqualified "agrees on every core fact" at row granularity.

### 5b. run3c/3d/3e adjudication: B's row is inference-as-fact, over-broad;
and BOTH reports share a run4-attribution erratum. MEASURED (logs/stores) /
INFERRED (window attributions).

- The four attempt logs contain only teardown tracebacks — zero per-case
  output (A's "no per-case output preserved" verified): `evals-run3c-
  foreground.txt` EXIT=124 (mtime 15:35:50Z), `evals-run3d.txt` EXIT=130
  (15:57:47Z), `evals-run3e-official.txt` EXIT=130 (16:21:39Z),
  `evals-run4-official.txt` EXIT=130 (16:52:54Z). NOTE:
  `docs/case-4-parsing-failure-audit-2026-09-04.md` contains zero mentions of
  run3c/3d/3e (grep-verified); that doc records the separate ~21:09 stop,
  which A:105–106 correctly cites it for — not these attempts.
- The ticket store shows no C-1004 ticket or draft between 15:35Z and
  17:21:07Z. With mtime-pinned attempt windows and the observed fresh
  c1-restart cadence (~9–10 min/case), the implied states at kill are:
  run3c died during case-2; run3d was killed 12 s after case-3's ticket;
  run3e died during case-3. On that basis "case-4 never reached" is a
  reasonable INFERENCE for run3c/3d/3e — but it rests on mtimes-as-death-
  times and window attribution, no artifact states it, and B presents it as
  fact with no citation.
- B's row 4 also sweeps "run4 attempts" into "never reached": for the logged
  run4-official (dead 16:52:54Z), case-4's detector may have started in the
  5.5 minutes before its SIGINT (certain is only that it never completed —
  no C-1004 ticket/draft); and if the 17:21 pass counts as "run4" per B's own
  row 5, then "run4 never reached case-4" is false by B's own table.
- New erratum shared by BOTH reports (INFERRED from MEASURED facts): the
  17:21 pass's "run4-official window" attribution (A:93, B:85, both
  "attribution by timing — INFERRED") is contradicted by evidence — the
  logged run4-official died at 16:52:54Z (its EXIT line was already captured
  verbatim in `impl-diff-2026-09-04.txt` at 17:12:19Z, lines 310/448/586/724),
  2.3 minutes BEFORE the 16:55:13→17:21:17 ticket progression began. A
  process that exited at 16:52:54 cannot have written those tickets: the pass
  belongs to a subsequent, unlogged execution. The pass itself remains
  DIRECT in the ticket store (`tickets.jsonl:31`, `TCK-4e744f8f7592`); only
  its run identity is mis-attributed — and it is mis-attributed identically
  in A and B.

### 5c. The blind second ruling on the STOP decision (DOCUMENTED — relayed
from D6, which was not shown the deciding agent's rationale; its verified
facts were spot-checked against disk by D6 itself and match §§1–4).

Ruling category: "(c) PROCEEDED DEFENSIBLY BUT WRONGLY ORDERED." Its stated
strongest reason, verbatim: "the STOP clause's example-trigger ('report #1
contains a finding NOT addressed or contradicted by report #2') fired on the
agent's own verified findings — several times over, including two genuine
conflicts — which made stopping non-discretionary under the task's own
terms; the agent substituted its own materiality judgment for the human's
reserved decision, against its own adjudicator's STOP ruling, and the notice
it inserted then exhibited exactly the defect the clause anticipated (the
'agrees on every core fact' sentence drops B's 're-derived here' qualifier
and is contradicted by the two divergences). The outcome is acceptable — the
notice is mostly accurate, scoped, non-destructive, disclosed, and reversible
— so removal is not warranted; the fault is the ordering, and it stands." It
judged the notice "not false, but materially misleading in two places"
(the unqualified agreement sentence; "grounds them against the raw evidence"
as applied to the quoted-not-derived rate table), held that disclosure and
reversibility "convert a wrongful ordering … into a one-command-reversible
state change" without curing the fault, and stated it would have stopped
first and returned with a proposed amended notice restoring B's hedge. Its
closing "what I would have done" passage ends, verbatim: "Approval would
likely have taken the human seconds — which is precisely why proceeding
without it bought nothing and cost the process."
```

End of verbatim reproduction (DR:471–556; §6 begins at DR:560 after a `---`
separator at DR:558).

---

## 2. The run4-attribution erratum (§5b, final bullet)

### 2a. Exact erratum text in report A and report B (all quotes read directly
from the current files in this task; MEASURED)

**A:93** (§1b timeline row 3 — the mis-attribution itself):

> | 3 | 09-04 17:21 | Experiment run4-official window (attribution by timing — INFERRED; the pass itself is DIRECT, ticket-store) | GLM / GLM | present | **PASS — `MANUAL_OVERRIDE` @ 0.95** (`TCK-4e744f8f7592`, draft `DRF-beac5cd8cb28` 17:21:08Z) — found by adversarial re-review; not part of any archived run tree | `runtime/tickets.jsonl:31`; `runtime/drafts.jsonl:20` |

**A:111–114** (the affirmative claim, at the end of A's "Not case-4
executions" note — this is the strongest form of the error, stated as fact):

> run4-official, by contrast, DID reach case-4 — timeline row 3's 17:21:17Z
> pass falls inside its window (c1@16:55 → c2@17:04 → c3@17:13 → c4@17:21
> ticket progression; run attribution INFERRED from timing, pass existence
> DIRECT in the ticket store).

Note also **A:103**, which lists only "run3c/3d/3e" among the
hung/timed-out attempts and deliberately omits run4 — A excludes run4 from
the "not case-4 executions" list precisely because it believes run4 reached
case-4. And **A:393** (§5 provenance table), which shows A knew the
attribution was an inference:

> | Additional case-4 PASS at 09-04 17:21:17Z, MANUAL_OVERRIDE @ 0.95 | MEASURED (existence) / INFERRED (run4 attribution, by ticket timing) | `runtime/tickets.jsonl:31` + `runtime/drafts.jsonl:20` — found by adversarial re-review |

**B:85** (§1b timeline row 5 — the identical mis-attribution):

> | 5 | 09-04 17:21 "run4-official window" | `MANUAL_OVERRIDE` (ticket store only, no archived tree — attribution INFERRED) | 0.95 | pass (ticket `TCK-4e744f8f7592`) |

**B:84** (§1b timeline row 4 — the row that self-conflicts with row 5):

> | 4 | 09-04 15:35–17:55 run3c/3d/3e/run4 attempts | case-4 never reached (killed) | — | — |

**B:118–122** (§1c — the pass count that consumes the 17:21 pass; the count
is unaffected by the erratum, but the phrase repeats the timing inference):

> Three archived, eval-row-backed prior passes exist (run 2 @ 0.93;
> sequential @ 0.92, 19/19; retry-active @ 0.95, 19/19), plus one
> ticket-store-only pass (17:21Z, attribution inferred by timing). The clean
> run is therefore the 4th archived pass (5th if the ticket-store-only pass
> is counted).

### 2b. What "run4" is, and what the misattribution concretely is

**"run4" denotes the fourth numbered eval-harness execution of 2026-09-04**
— the last of the manual `Experiment.run_evaluations` attempts, whose only
surviving log is `agent-memory/evidence/evals-run4-official.txt`
(132 content lines + final marker): hung at `await queue.join()`
(`strands_evals/experiment.py`), killed by SIGINT, ending
`EVALS_RUN4_EXIT=130`. The day's numbering is 1-indexed and
global-chronological (run 1 = the 14:04Z/16% verify.sh step-6 run; run 2 =
the 14:18Z/68% run; run 3 = the aborted 15:24/15:25 verify.sh attempts with
letter suffixes 3b/3c/3d/3e for the hung evals attempts; run 4 = the
16:2x–16:52:54Z attempt). Four independent anchors fix this: the evidence
filenames themselves, the `evals/run_sequential.py:6–13` docstring
("…tracebacks in … evals-run3d.txt, evals-run3e-official.txt, and
evals-run4-official.txt (each exit 130 after SIGINT…)"; "the harness last
finished (run 2)"), the commit messages `2ef1a51` ("all 20 judge rows failed
in run 1") and `6b8e29f` ("exactly what the ToolParameter judge flagged in
run 2"), and the `tickets.jsonl` timestamps bracketing each window (L1).
MEASURED.

**It is not any run discussed in the task context.** The pre-retry
(`gemini-groq-5-case-final-validation`), retry-active
(`groq-retry-active-5case-validation`), and clean (`clean-5case-validation`)
5-case runs are all Groq/Gemini-era executions of 2026-09-05, and no document
ever assigns them ordinals — later runs are named, never numbered (L1).
run4 is a GLM-era 2026-09-04 afternoon attempt that produced no eval rows,
no token record, and no per-case output at all.

**The misattribution concretely:** a *run-identity* error about a real pass —
not a fabricated event, not a mislabeled case, not a wrong metric. The
17:21:17.514059Z case-4 ticket `TCK-4e744f8f7592`
(`MANUAL_OVERRIDE` @ 0.95, draft `DRF-beac5cd8cb28`) genuinely exists in the
shared runtime store; both reports correctly recover it and correctly count
it. What is wrong is *which execution wrote it*: A (row 3 + the A:111–114
affirmation) and B (row 5) assign it to run4-official's window, when the
logged run4-official had been dead for 2m19s before the first artifact of
the c1→c4 progression that produced it. Two knock-on defects follow: A's
"run4-official … DID reach case-4" (A:111) is false, and B's rows 4 and 5
are mutually inconsistent under B's own attribution (if row 5 is right, row
4's "run4 … never reached" is wrong; the dissent review makes this point at
DR:515–519).

### 2c. Evidence trace — re-verified against raw artifacts in THIS task

| # | Premise | Value re-verified | Source |
|---|---|---|---|
| 1 | run4-official's log ends with its death marker | `EVALS_RUN4_EXIT=130` at line 132; lines 1–131 are httpx teardown tracebacks + `KeyboardInterrupt` at `experiment.run_evaluations` — zero per-case output | `agent-memory/evidence/evals-run4-official.txt` (read in full, 133 lines) |
| 2 | Time of death (last write to its log) | mtime `2026-09-04 11:52:54.600854588 -0500` = **16:52:54.600854Z** | `stat` |
| 3 | The death was already on record BEFORE the pass | `+EVALS_RUN4_EXIT=130` at `impl-diff-2026-09-04.txt:724`; that file's mtime is `2026-09-04 12:12:19 -0500` = **17:12:19Z**, i.e. 9m00s before the pass. (Sibling markers re-verified at :310 `RUN3C_EXIT=124`, :448 `RUN3D_EXIT=130`, :586 `RUN3E_EXIT=130` — the dissent review's "lines 310/448/586/724" citation is exact) | grep + `stat` |
| 4 | The ticket progression both reports rely on | `tickets.jsonl:28` `C-1001-20260826-001` @ **16:55:13.883672Z**; `:29` `C-1002-2026-08-27` @ 17:04:18.040441Z; `:30` `C-1003-sync_lag` @ 17:13:49.779931Z; `:31` `CASE-C-1004-MANUAL_OVERRIDE` `TCK-4e744f8f7592` @ **17:21:17.514059Z** — exactly A:112's "c1@16:55 → c2@17:04 → c3@17:13 → c4@17:21" | full timeline extraction of `runtime/tickets.jsonl` (59 tickets, id + created_at) |
| 5 | The paired draft | `drafts.jsonl:20` `DRF-beac5cd8cb28` @ **17:21:08.243202Z**, 9.27 s before the ticket, which references this draft id | `runtime/drafts.jsonl` |
| 6 | No case-4 work in any attempt window | No C-1004 ticket exists between 14:56:44Z (`TCK-0ca8551fc455`, line 15) and 17:21:17Z; exactly **8** C-1004 tickets exist overall (lines 7, 14, 15, 31, 34, 47, 53, 58) — which also independently confirms A:392's "all 8 C-1004 tickets" | C-1004 grep over `tickets.jsonl` |
| 7 | run4's own window contains no case-4 artifact | Tickets inside the window are lines 25–27 (16:28:07 / 16:36:57 / 16:47:25, the last a `C-1003` case); none is C-1004; the 16:47:25 c3 ticket sits 5m29s before the SIGINT — the dissent's "case-4's detector may have started in the 5.5 minutes before its SIGINT" reconciles exactly | timeline extraction |
| 8 | Independent triangulation | The sequential-driver commit `af90ddc` lands 43 s after run4's death (16:53:37Z) — the session had moved on to building `run_sequential.py` before the successor execution's first ticket (16:55:13Z) | L1, via `git log` |

**Correct attribution (CALCULATED from premises 1–8, all MEASURED above):**
the execution that wrote tickets 28–31 began producing store artifacts at
16:55:13Z, 2m19.3s after run4-official's last write; a process that exited
at 16:52:54 cannot have written them (the JSONL stores are written
synchronously at ticket/draft creation by a live app). The 17:21:17Z case-4
pass therefore belongs to a **subsequent, unlogged execution** whose only
surviving record is the shared ticket/draft store — consistent with both
reports' own caveat that the pass is "not part of any archived run tree"
(A:93) / "ticket store only, no archived tree" (B:85). The pass itself
(DIRECT, `tickets.jsonl:31`) and every figure built on its *existence* are
unaffected; only the run label is wrong — in both reports, identically. This
re-derivation matches the dissent review's §5b ruling (DR:520–530), which
tagged the same conclusion INFERRED; this task adds first-hand re-measurement
of every premise (the dissent review's lanes had measured them in its own
session).

### 2d. Materiality — plain statement

**No headline figure that has been or reasonably could be cited is affected.**
Specifically (L3 surface sweep + L1 figure-provenance):

- `README.md` contains **no figures at all** ("no numbers are claimed here
  until they're measured"; `evals/results.md` does not exist). Its security
  claims are architecture claims, not run-derived.
- No `docs/index*`, pitch, submission, portfolio, or results-summary doc
  exists (corroborated by `docs/state-and-gap-analysis-2026-09-05.md:7–9`).
- The figures that do circulate — 4/5 root-cause, 82.7%/85.9%, 313,842
  tokens, 9 fabricated-param rows, 18/19, single-UNKNOWN, 5/5 rc=0, 362,858
  tokens, 93.0%, 2/2/2/0 retries — all belong to the clean, final-validation,
  or retry-active runs; **no document attributes any metric to run4** (it has
  no metrics: no eval rows, no tokens, no outcomes). L1 §d checked each
  figure's provenance explicitly.
- The pass-count statements that consume the 17:21 pass ("3 archived + 1
  ticket-store-only"; "4th archived / 5th overall") are count statements
  about the pass's *existence*, which is DIRECT — they survive the
  re-attribution unchanged.
- Nothing is on the public remote: `main` = `origin/main` = `ac1ba3a`, and
  all three case-4 reports are untracked; no commit on any ref references
  them.

**But it is not zero-stakes.** It is a live, unflagged factual error about
run history inside BOTH reports — including B, the designated authoritative
record — plus an internal self-contradiction between B's rows 4 and 5, plus
A's flatly false affirmative sentence (A:111). Anyone reconstructing the
2026-09-04 execution sequence from A or B (exactly what a closure/index task
does) inherits the wrong attribution. Classified: low materiality for
citable figures; genuine, bounded materiality for the run-history record.

### 2e. Correction status as the files stand

- **Report A:** carries the erratum live (A:93, A:111–114, A:393 — confirmed
  by grep this task: those are A's only run4 mentions). A's SUPERSEDED
  notice (A:1–15, read in full this task) mentions only the FIFTH-vs-4th
  pass-count contradiction; it does not mention run4 and does not point to
  the dissent review.
- **Report B:** carries the erratum live (B:85; plus the row-4/row-5 tension
  at B:84 and the "attribution inferred by timing" repetition at B:118–122).
  B has no notice or erratum mechanism of any kind (L3 grep: zero hits for
  notice/SUPERSEDED/erratum/amendment).
- **The dissent review** states the correct attribution in three places
  (DR:56–59 §0 item 6; DR:520–530 §5b; DR:646 §7 row). It is the ONLY place
  in the repository, the memory directory, or git history that does: L3
  swept `agent-memory/decisions.md`, `task-board.json`, `guard-audit.log`,
  the auto-memory dir, and `git log --all` (full-message grep) — zero
  corrective records.
- **Therefore:** for a future reader who goes through the dissent review
  first, A and B's shared error is moot. For a reader who arrives the way
  the supersession chain directs them (A's notice → B), it is NOT moot: they
  land on B:85, read the wrong attribution, and nothing they were pointed at
  flags it. The erratum remains live and uncorrected in both A and B as they
  currently stand. MEASURED.

---

## 3. §5b, remaining components — the run3c/3d/3e adjudication (bullets 1–3)

**What it says** (quoted in §1 above, DR:499–519): B's timeline row 4
("case-4 never reached (killed)", B:84) presents as uncited fact what is
actually an inference from mtime-pinned windows and ticket cadence; it is
over-broad in sweeping "run4 attempts" into "never reached"; and A's
contrasting "reach UNKNOWN — no per-case output preserved" (A:103) is
verified true of the logs but over-cautious about the ticket ledger.

**Re-verified in this task (MEASURED):** all four attempt logs carry only
their EXIT markers plus teardown tracebacks — run4's was read in full
(§2c premise 1); run3c/3d/3e EXIT lines and mtimes re-verified
(`EVALS_RUN3C_EXIT=124` @15:35:50Z, `EVALS_RUN3D_EXIT=130` @15:57:47Z,
`EVALS_RUN3E_EXIT=130` @16:21:39Z); no C-1004 ticket exists in the
15:35–17:21:07 window (§2c premise 6); run3d's death (15:57:47) sits 12 s
after the 15:57:35 ticket (`tickets.jsonl:21`), exactly as DR:511 states.

**Not re-verified / inherently inferential:** the per-attempt "died during
case-N" positions (DR:509–511) are window attributions from cadence, not
artifact-recorded facts — raw evidence alone leaves them UNKNOWN. L1's
independent window reconstruction agrees on the anchors but arranges
interior tickets slightly differently across attempts; this divergence is
between two inferences, does not touch any MEASURED anchor, and nothing in
A, B, or the erratum depends on it. DR:504–506's claim that
`docs/case-4-parsing-failure-audit-2026-09-04.md` never mentions
run3c/3d/3e is DOCUMENTED (quoted; not re-checked here; not load-bearing —
it concerns which doc records the separate ~21:09 stop).

**Ground truth:** "never completed case-4" is certain for all four attempts
(no C-1004 ticket/draft; MEASURED). "Never reached (started) case-4" is
probable but unproven for run3c/3d/3e and for run4 (whose c3 ticket at
16:47:25 leaves a 5m29s window before its SIGINT); B states it as fact
without citation; A's "UNKNOWN" is the defensible epistemic form; the
dissent review's middle position (inference reasonable, presentation
over-broad; and B's row 4 self-conflicts with row 5 via the run4 erratum)
is confirmed by this task's re-measurements.

**Materiality:** low. Both reports already exclude these attempts from the
case-4 outcome record; no count, rate, or verdict depends on reach-vs-not.
The defect is presentational (inference-as-fact) plus the row-4/row-5
inconsistency noted in §2b.

**Correction status:** stated only in the dissent review (§3e DR:378–393,
§5b); B:84 stands unqualified. Same reachability caveat as §2e — not on the
A→B supersession path.

---

## 4. §5a — run-1 case-4 verdict preservation (A-vs-B factual disagreement)

**The two reports, verbatim (read this task):**

A:91 (§1b row 1):

> | 1 | 09-04 14:04 | verify.sh step-6 Exp run 1 (16%) | GLM / judges unwired | present | Ran (trajectory existed); all judged rows 0.00 on judge wiring; **classifier verdict NOT preserved** — UNKNOWN | `verify-full-2026-09-04.txt:502`; wiring fixed after, in `cf58ddf` |

B:82 (§1b row 2 — same 14:04Z run; B's table has one extra leading row, a
~13:18 bootstrap, so B's row numbers run one ahead of A's from here):

> | 2 | 09-04 14:04 verify run 1 (16.00%) | not preserved in eval rows; ticket `TCK-eeac66ba7362` `manual_override` (attribution by timing — INFERRED) | 0.95 (ticket) | 4/5 rows FAIL |

**Concrete description:** A asserts the run-1 classifier verdict was not
preserved (and labels the slot UNKNOWN); B asserts it survives in the shared
ticket store. This is a both-reports-state-it factual divergence at
timeline-row granularity — the dissent review's counterexample to the
notice's unqualified "agrees with it on every core fact" (A:6–8).

**Evidence trace (re-verified this task, MEASURED):** `tickets.jsonl:7` =
`TCK-eeac66ba7362`, `C-1004-STATUS-MISMATCH-20260829`,
`root_cause: "manual_override"`, `confidence: 0.95`, `created_at
2026-09-04T14:13:30.562198+00:00` — inside run 1's 14:04→14:18 window (run 2
starts 14:18 per both tables; its first ticket lands 14:20:14 at line 8).
Exactly 8 C-1004 tickets exist (§2c premise 6), matching A:392's claim to
have extracted "all 8" — so A had this ticket in hand and still wrote "NOT
preserved", the self-inconsistency DR:486–487 flags.

**Ground truth:** B matches the artifact; A's "NOT preserved" is wrong
unless the ticket's window attribution fails — and that attribution is
timing-based (INFERRED), as B itself tags. CALCULATED (from the MEASURED
ticket facts), agreeing with DR §5a.

**Materiality:** negligible, plainly. Neither report counts run 1 among the
prior passes (A §1c counts rows 2/3/4/7; B §1c counts run 2, sequential,
retry-active + the ticket-store-only pass); the single-UNKNOWN-on-record
claim is unaffected (run 1's slot was absence-of-record, not an UNKNOWN
emission); no rate, count, or citable figure changes. DR:487–493 states the
same and this task's re-measurements confirm it.

**Correction status:** in effect already corrected for chain-following
readers — A's notice directs authority to B, and B carries the
artifact-matching account. A:91 stands uncorrected in the superseded file,
flagged only by the notice's general authority sentence (which does not name
this divergence; the notice names only the FIFTH-vs-4th item). The dissent
review records the adjudication (DR:473–493, DR:643).

---

## 5. §5c — the blind second ruling on the STOP decision

**What it is:** DOCUMENTED content, relayed verbatim in §1 above (DR:532–556)
from the dissent review's D6 lane (deliberately not shown the deciding
agent's override rationale). It is a process finding about the prior
annotation task — category "(c) PROCEEDED DEFENSIBLY BUT WRONGLY ORDERED" —
not a claim about repository contents being wrong.

**Re-verified in this task:** the ruling's load-bearing factual premise —
that the notice's agreement sentence overstates B's own scoped claim — is
MEASURED here by direct comparison: A:6–8 says B "agrees with it on every
core fact and grounds them against the raw evidence", while B's Appendix A
opens "**agrees** with that file on every core fact **re-derived here**"
(B:395–396, read this task). The qualifier drop is real. The ruling text
itself has no on-disk source beyond the dissent review (the session record
is not a file): DOCUMENTED, quoted only.

**Materiality:** process-level, not figure-level. Its actionable descendant
is the dissent review §6's recommended one-sentence notice amendment —
already approved by the human as a separate action and deliberately out of
scope here (not applied in this task). Nothing in A or B requires correction
because of §5c itself.

**Correction status:** nothing to correct; it is already recorded (dissent
review §5c/§6; the pending amendment is also noted in the auto-memory file
`clean-5case-run-and-case4-record.md` as "PENDING HUMAN DECISION", per L3).

---

## 6. Recommendation — fold into the planned closure/index task, or leave as
historical record? (per item)

1. **run4-attribution erratum (§5b final bullet) — FOLD IN; highest priority
   of the three.** It is the only §5 finding that is a shared factual error
   in both reports, it sits unflagged in B — the designated authoritative
   report — with a row-4/row-5 self-contradiction, and the supersession
   chain (A's notice → B) delivers readers directly to the error with no
   pointer to the correction. The closure/index task should carry one line
   fixing the canonical attribution (e.g.: "the 2026-09-04 17:21:17Z case-4
   pass, `TCK-4e744f8f7592`, belongs to a subsequent unlogged execution —
   not run4-official, which died 16:52:54Z; see dissent review §5b and
   `docs/case4-dissent-section5-verbatim-and-verification-2026-09-05.md` §2").
   A one-line erratum footnote in B itself would also cure it but is an edit
   to the authoritative report and should get its own explicit human
   approval — not bundled with the already-approved §6 notice amendment.
2. **§5a run-1 verdict preservation — fold in as one index line; no report
   edits.** B already carries the artifact-matching account and holds
   authority; the index line (A:91 wrong / B:82 matches `tickets.jsonl:7`)
   costs nothing and closes the record. Below the run4 item in priority.
3. **§5b bullets 1–3 (run3c/3d/3e adjudication) — record as an index caveat
   on B:84; otherwise leave as historical record.** No figure depends on it;
   the index should note that B:84's "never reached" is an inference stated
   as fact (A's "UNKNOWN" is the defensible form) so the closure task does
   not canonize B's phrasing uncritically.
4. **§5c blind ruling — no correction action.** Cite the dissent review in
   the closure task as the standing record of the override adjudication;
   the §6 notice amendment is its actionable descendant and is already
   separately approved. Per this task's constraints, none of it is applied
   here.
5. **Adjacent finding worth one index line (new in this task, L2):** the
   evidence directories `clean-5case-validation-2026-09-05`,
   `gemini-groq-5-case-final-validation-2026-09-05`, and
   `groq-retry-active-5case-validation-2026-09-05` all carry the SAME
   driver-fixed internal run id `"gemini-judge-5-case-2026-09-04"` in their
   `index.json:2` — three distinct physical executions share one internal
   label. A closure/index task consolidating "which report is authoritative
   for which figure" should disambiguate physical runs by directory/date,
   not by that internal id.

---

## 7. Claim classification and provenance

| Claim (section) | Class | Re-verified in this task vs quoted |
|---|---|---|
| §5 reproduction above is verbatim, DR:471–556 (§1) | MEASURED | Transcribed from a direct read of the dissent review in this task |
| §5 has three items; prior relay compressed 5a/5c too (§0.1) | OBSERVED | Comparison of the relay description in the task context against DR:471–556 |
| A:93, A:100–114, A:393; B:82, B:84, B:85, B:118–122 quoted exactly (§2a, §4) | MEASURED | Read directly from A and B on disk, current line numbers |
| run4 = 4th numbered 09-04 Experiment attempt; 1-indexed day-local scheme; later runs never numbered (§2b) | MEASURED | Filenames, `run_sequential.py:6–13`, commits `2ef1a51`/`6b8e29f`, ticket windows (L1 + main session) |
| run4-official died 16:52:54Z, traceback-only log, EXIT=130 (§2c 1–2) | MEASURED | Full read of `evals-run4-official.txt` + `stat` (main session) |
| impl-diff:724 `+EVALS_RUN4_EXIT=130`; siblings at 310/448/586; file mtime 17:12:19Z (§2c 3) | MEASURED | grep + `stat` (main session) |
| Ticket progression 28–31 (16:55:13/17:04:18/17:13:49/17:21:17.514059); draft `DRF-beac5cd8cb28` @17:21:08.243202 (§2c 4–5) | MEASURED | Full timeline extraction of `tickets.jsonl` (59 rows) + `drafts.jsonl` grep (main session) |
| No C-1004 ticket 14:56:44→17:21:17; exactly 8 C-1004 tickets; run4 window tickets 25–27 incl. C-1003 @16:47:25 (§2c 6–7) | MEASURED | C-1004 grep + timeline extraction (main session) |
| Sequential commit `af90ddc` at 16:53:37Z, 43 s after run4 death (§2c 8) | MEASURED | `git log` (L1, in-task lane) |
| The 17:21 pass belongs to a subsequent unlogged execution (§2c conclusion) | CALCULATED | Derived here from MEASURED premises 1–8; matches DR §5b (which tagged it INFERRED) |
| First progression ticket postdates run4 death by 2m19.3s; pass by 28m22.9s (§2) | CALCULATED | Arithmetic on MEASURED timestamps; matches DR's "2.3 minutes" |
| No headline figure depends on run4; README figureless; no index/pitch/submission docs; nothing public (§2d) | MEASURED | L3 surface sweep + L1 figure provenance (in-task lanes); README quote read at `README.md:99–103` |
| Erratum corrected only in dissent review (DR:56–59, 520–530, 646); A notice silent on it; B has no notice mechanism; absent from memory/git (§2e) | MEASURED | A:1–15 read in full; L3 exhaustive sweep of docs/, agent-memory/, memory dir, `git log --all` |
| Attempt logs traceback-only; run3c/d/e EXIT lines + mtimes; run3d died 12 s after 15:57:35 ticket (§3) | MEASURED | greps/stats + timeline (main session) |
| Per-attempt "died during case-N" positions (DR:509–511) | UNKNOWN | Window/cadence inferences, not artifact-recorded; L1's reconstruction diverges harmlessly on interior placement |
| parsing-failure-audit doc has zero run3c/3d/3e mentions (DR:504–506) | DOCUMENTED | Quoted from the dissent review; not re-checked (not load-bearing) |
| `tickets.jsonl:7` content and 14:13:30Z timestamp; inside run-1 window; 8-ticket count matches A:392 (§4) | MEASURED | Direct store read (main session) |
| B:82 matches artifact; A:91 wrong unless window attribution fails (§4) | CALCULATED | From the MEASURED ticket facts; agrees with DR §5a |
| §5a materiality negligible (§4) | MEASURED | Neither report's pass counts consume run 1 (A §1c / B §1c read this task) |
| A:6–8 notice sentence vs B:395–396 scoped claim; qualifier dropped (§5) | MEASURED | Both passages read directly this task |
| §5c ruling text and category (§5) | DOCUMENTED | Relayed from the dissent review's D6 lane; no on-disk source exists to re-verify against |
| Pending §6 notice amendment exists, human-approved, not applied (§5) | DOCUMENTED | Per task context; corroborated by memory file note found by L3 |
| Three evidence dirs share internal run id `gemini-judge-5-case-2026-09-04` (§6.5) | MEASURED | L2 read of the three `index.json:2` files |
| Whether the human folds items 1–5 into the closure/index task | UNKNOWN | Reserved to the human |

---

## 8. Zero-modification confirmation

- `git status --porcelain=v1` BEFORE this task: 45 lines — 5 modified tracked
  files (`evals/run_evals.py`, `tools/legacy_system.py`,
  `tools/modern_system.py`, `tools/seed_data.py`, `tools/transactions.py`;
  all pre-existing modifications, untouched here) and 40 untracked entries;
  HEAD `ac1ba3a394e7afc85980e49615a9a720aa8b5b4f`. AFTER (closing
  verification command): 46 lines — the identical 45 plus exactly one new
  untracked line —
  `?? docs/case4-dissent-section5-verbatim-and-verification-2026-09-05.md`
  (this file). No tracked file changed; `git diff --cached` empty; HEAD
  unchanged; nothing staged, committed, or pushed. MEASURED.
- Report A, report B, the dissent review, the notice, and all
  application/eval code untouched; the §6 notice amendment was NOT applied.
- No tests, benchmarks, canaries, or live LLM/API calls were executed. All
  shell usage was read-only (grep / stat / find / git log / git status) plus
  one `nl`-based read-only timeline extraction over `runtime/tickets.jsonl`.
- No secrets encountered or reproduced: files read were ticket/draft/log text
  and reports; the two key-shaped filenames in the evidence tree were never
  opened (L2/L3 independently confirm no secret material in anything read).

END OF REPORT
