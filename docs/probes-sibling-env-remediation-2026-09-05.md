# probes/ sibling-.env default remediation — 2026-09-05
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

> REDACTED 2026-09-07 (privacy pass): sibling-project names and
> out-of-repo local paths in this report were replaced with neutral tokens
> ([SIBLING-A]…[SIBLING-J], ~) before publication; originals preserved in
> the author's private pre-rewrite bundle.

Status: COMPLETE (reviewer ACCEPT, round 2 — §9). Human-ruled
remediation; architect-gated Tier A PROCEED; all verification offline.

Task: remove the hardcoded sibling-project credential default
`DEFAULT_ENV_FILE = Path("~/projects/[SIBLING-A]/.env")`
from `probes/probe_common.py:35` (silent `--env-file` default in all four
probes), per the human ruling that closed the escalation left open by
`docs/final-doc-config-cleanup-2026-09-05.md` Item 4 (STOP branch).

Constraint compliance (all MEASURED/OBSERVED in this session):
- No sibling-project access of any kind. The old default path was NEVER
  executed — running any pre-fix probe without `--env-file` would have
  dereferenced the sibling `.env`, so pre-fix behavior was established
  statically from source, not by running it.
- No live LLM/API calls, no benchmarks, no canaries (verify.sh not run
  end-to-end: step 6 is the live 5-case Groq run; probes are also never
  exercised by verify.sh).
- No commits, staging, or pushes: `git diff --cached` empty throughout,
  HEAD unchanged at ac1ba3a (§7).
- Secrets: none read, none printed, none written. The reviewer verified
  `.env`-membership claims by name-presence greps only (values never read).

## 1. Remediation option chosen: (a) — no default, `--env-file` required

`--env-file` is now `required=True` with no default in all four probes;
omitting it exits rc=2 at argparse before any file read or client
construction (MEASURED, §5).

Justification, tied to the probes' coded purpose (all OBSERVED in source):
1. `probe_groq.py` exists to compare TWO external credential files
   (`--env-tag [SIBLING-A]|[SIBLING-B]`; pre-fix docstring named both sibling
   paths). `--env-file` selects which environment is under test — no
   single default can be semantically correct.
2. `probe_cerebras.py` / `probe_strands.py --provider cerebras` read
   `CEREBRAS_API_KEY`, which is not in this repo's `.env`
   (`.env.example:49-52`; reviewer name-presence-verified). Option (b)
   would install a default that cannot work for two of four probes.
3. `.env.example:49-52` (live doc) already mandates the explicit-only
   posture: probes "take credentials from an explicit --env-file
   argument and never read this repo's .env". Option (a) makes code
   match policy; option (b) would contradict it (also flagged by the
   architect: (b) would have forced an out-of-scope `.env.example` edit).
4. `load_credentials(env_file, names)` always took `env_file` as a
   required parameter — the design was explicit; only the argparse
   default leaked the sibling path. Option (a) is the minimal
   restoration of design intent.
5. Probes are deliberately isolated from app modules (`probe_common.py`
   docstring: "Pure standard library. No app/benchmark imports");
   adopting `agents/model.py`'s repo-`.env` convention would blur that
   isolation. `agents/model.py` was not touched.

## 2. Exact diffs

Change surface: 6 files, all under `probes/` (plus the ledger entry in
§6 and this document). `git diff -- probes/` in full (197 lines):

```diff
diff --git a/probes/README.md b/probes/README.md
index f0df1d7..a22e9af 100644
--- a/probes/README.md
+++ b/probes/README.md
@@ -9,9 +9,12 @@ SEPARATE from the application and the benchmark:
 - No changes to the app's Groq wiring, the eval harness, or any case data.
 - No write/correction tools are ever declared or sent to a model — the only
   tool any probe defines is a synthetic read-only `get_balance`.
-- Credentials: `probe_common.load_credentials()` loads ONLY the explicitly
-  requested variable NAMES (`CEREBRAS_API_KEY` / `GEMINI_API_KEY`) from an
-  explicit `.env` file (default: the `../[SIBLING-A]` sibling).
+- Credentials: `--env-file` is REQUIRED with NO default (since 2026-09-05;
+  it previously defaulted to a sibling project's `.env` — see
+  `docs/probes-sibling-env-remediation-2026-09-05.md`).
+  `probe_common.load_credentials()` loads ONLY the explicitly requested
+  variable NAMES (`CEREBRAS_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY`)
+  from the file you pass.
   Values are passed in-process to the HTTP client / SDK client and are
   never printed, logged, or written. Every line that leaves a probe
   (stdout, evidence files) passes through a redactor that masks the loaded
@@ -35,19 +38,27 @@ backend seat's `agents|orchestrator|tools|tests` tree.
 | `probe_common.py` | env loader (names only), redactor, HTTP capture, evidence writer |
 | `probe_cerebras.py` | raw REST probe: auth/models, tiny completion, tool call + replay |
 | `probe_gemini.py` | raw REST probe: model list, tiny completion, function call + replay, structured output |
-| `probe_groq.py` | two-key Groq probe (openai-sdk transport): models list, tiny completion, tool round + replay, full `x-ratelimit-*` capture — one `--env-file`/`--env-tag` per sibling project |
+| `probe_groq.py` | two-key Groq probe (openai-sdk transport): models list, tiny completion, tool round + replay, full `x-ratelimit-*` capture — one `--env-file`/`--env-tag` per credential source |
 | `probe_strands.py` | the app's exact Strands `OpenAIModel`/`GeminiModel` idiom against each provider, with a synthetic tool loop |
 
 ## Usage (from the repo root)
 
+`--env-file` is required everywhere — there is no default. (The 2026-09-04
+feasibility runs pointed it at sibling-project `.env` files under a
+since-superseded authorization, D-2026-09-04-12/-13; see
+`docs/probes-sibling-env-remediation-2026-09-05.md`.) This repo's own
+`.env` is a valid explicit choice for the `GROQ_API_KEY`/`GEMINI_API_KEY`
+probes; `CEREBRAS_API_KEY` is not in this repo's `.env`, so the Cerebras
+probes exit with `credential(s) not present in env file` if pointed there.
+
 ```bash
-uv run --locked python probes/probe_cerebras.py
-uv run --locked python probes/probe_gemini.py
-uv run --locked python probes/probe_groq.py --env-file ~/projects/[SIBLING-A]/.env --env-tag [SIBLING-A]
-uv run --locked python probes/probe_groq.py --env-file ~/projects/[SIBLING-B]/.env      --env-tag [SIBLING-B]
-uv run --locked python probes/probe_strands.py --provider cerebras
-uv run --locked python probes/probe_strands.py --provider gemini-compat
-uv run --frozen --with google-genai python probes/probe_strands.py --provider gemini-native
+uv run --locked python probes/probe_cerebras.py --env-file /path/to/cerebras.env
+uv run --locked python probes/probe_gemini.py  --env-file /path/to/gemini.env
+uv run --locked python probes/probe_groq.py    --env-file /path/to/first.env  --env-tag [SIBLING-A]
+uv run --locked python probes/probe_groq.py    --env-file /path/to/second.env --env-tag [SIBLING-B]
+uv run --locked python probes/probe_strands.py --provider cerebras      --env-file /path/to/cerebras.env
+uv run --locked python probes/probe_strands.py --provider gemini-compat --env-file /path/to/gemini.env
+uv run --frozen --with google-genai python probes/probe_strands.py --provider gemini-native --env-file /path/to/gemini.env
 ```
 
 Evidence lands in `agent-memory/evidence/` (`.json` machine records,
diff --git a/probes/probe_cerebras.py b/probes/probe_cerebras.py
index 06bd4f4..250cef7 100644
--- a/probes/probe_cerebras.py
+++ b/probes/probe_cerebras.py
@@ -35,7 +35,7 @@ from pathlib import Path
 
 import openai
 
-from probe_common import DEFAULT_ENV_FILE, Evidence, load_credentials, make_redactor
+from probe_common import Evidence, load_credentials, make_redactor
 
 TOOL_DEF = {
     "type": "function",
@@ -90,7 +90,8 @@ def _call(ev: dict, label: str, fn) -> tuple[dict, object | None]:
 
 def main() -> None:
     ap = argparse.ArgumentParser()
-    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
+    ap.add_argument("--env-file", required=True,
+                    help=".env file to read CEREBRAS_API_KEY from (by name only; required — no default)")
     ap.add_argument("--base-url", default="https://api.cerebras.ai/v1")
     ap.add_argument("--model", default="gpt-oss-120b")
     ap.add_argument(
diff --git a/probes/probe_common.py b/probes/probe_common.py
index 17fbf5e..49e5dac 100644
--- a/probes/probe_common.py
+++ b/probes/probe_common.py
@@ -30,10 +30,6 @@ _KEY_PATTERNS = [
     re.compile(r"Bearer\s+[0-9A-Za-z_\-.]+"),
 ]
 
-# Default credential source: the sibling project's .env (names verified
-# present there on 2026-09-04; values never read into any output).
-DEFAULT_ENV_FILE = Path("~/projects/[SIBLING-A]/.env")
-
 
 def load_credentials(env_file: Path, names: list[str]) -> dict[str, str]:
     """Load ONLY `names` from a .env-style file. Values are never printed."""
diff --git a/probes/probe_gemini.py b/probes/probe_gemini.py
index c7b32ca..dd81753 100644
--- a/probes/probe_gemini.py
+++ b/probes/probe_gemini.py
@@ -32,7 +32,6 @@ import json
 from pathlib import Path
 
 from probe_common import (
-    DEFAULT_ENV_FILE,
     Evidence,
     body_json,
     http_json,
@@ -94,7 +93,8 @@ def _function_call_part(data: dict) -> dict | None:
 
 def main() -> None:
     ap = argparse.ArgumentParser()
-    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
+    ap.add_argument("--env-file", required=True,
+                    help=".env file to read GEMINI_API_KEY from (by name only; required — no default)")
     ap.add_argument("--base-url", default="https://generativelanguage.googleapis.com")
     ap.add_argument("--model", default="gemini-3.1-flash-lite")
     ap.add_argument(
diff --git a/probes/probe_groq.py b/probes/probe_groq.py
index 683f03d..b04ccd7 100644
--- a/probes/probe_groq.py
+++ b/probes/probe_groq.py
@@ -1,11 +1,11 @@
 """Groq two-key live probe (2026-09-04). See probes/README.md.
 
-Re-validates each sibling project's Groq environment INDEPENDENTLY
+Re-validates each credential source's Groq environment INDEPENDENTLY
 (treat the two GROQ_API_KEY values as unrelated organizations until
 response metadata says otherwise — key values are never compared):
 
-  --env-file ~/projects/[SIBLING-A]/.env  --env-tag [SIBLING-A]
-  --env-file ~/projects/[SIBLING-B]/.env     --env-tag [SIBLING-B]
+  --env-file /path/to/first/.env   --env-tag [SIBLING-A]
+  --env-file /path/to/second/.env  --env-tag [SIBLING-B]
 
 Phases and per-environment call budget (<=4 requests total):
   1. models.list                      (auth + openai/gpt-oss-120b presence; sanitized boolean)
@@ -36,7 +36,7 @@ from pathlib import Path
 
 import openai
 
-from probe_common import DEFAULT_ENV_FILE, Evidence, load_credentials, make_redactor
+from probe_common import Evidence, load_credentials, make_redactor
 
 MODEL = "openai/gpt-oss-120b"
 BASE_URL = "https://api.groq.com/openai/v1"
@@ -93,8 +93,8 @@ def _call(ev: Evidence, label: str, fn) -> tuple[dict, object | None]:
 
 def main() -> None:
     ap = argparse.ArgumentParser()
-    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE),
-                    help="sibling .env to read GROQ_API_KEY from (by name only)")
+    ap.add_argument("--env-file", required=True,
+                    help=".env file to read GROQ_API_KEY from (by name only; required — no default)")
     ap.add_argument("--env-tag", required=True,
                     choices=["[SIBLING-A]", "[SIBLING-B]"],
                     help="label for evidence files and summaries")
diff --git a/probes/probe_strands.py b/probes/probe_strands.py
index 8a27298..1895b0b 100644
--- a/probes/probe_strands.py
+++ b/probes/probe_strands.py
@@ -16,7 +16,8 @@ Providers:
   cerebras      OpenAIModel -> https://api.cerebras.ai/v1          (gpt-oss-120b)
   gemini-compat OpenAIModel -> .../v1beta/openai/  (Gemini OpenAI-compat layer)
   gemini-native GeminiModel (strands.models.gemini; needs google-genai:
-                             run via `uv run --with google-genai ...`)
+                             run via `uv run --with google-genai ...`;
+                             --env-file required as everywhere)
 """
 
 from __future__ import annotations
@@ -26,7 +27,7 @@ import json
 import time
 from pathlib import Path
 
-from probe_common import DEFAULT_ENV_FILE, load_credentials, make_redactor
+from probe_common import load_credentials, make_redactor
 
 QUESTION = "What is the settled balance of account ACC-1? Use the get_balance tool, then answer in one short sentence."
 SYSTEM_PROMPT = (
@@ -79,7 +80,8 @@ def _run_agent(name: str, model, redact) -> bool:
 def main() -> None:
     ap = argparse.ArgumentParser()
     ap.add_argument("--provider", required=True, choices=["cerebras", "gemini-compat", "gemini-native"])
-    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
+    ap.add_argument("--env-file", required=True,
+                    help=".env file to read the provider API key from (by name only; required — no default)")
     args = ap.parse_args()
 
     if args.provider == "cerebras":
@@ -112,7 +114,7 @@ def main() -> None:
             from strands.models.gemini import GeminiModel
         except ImportError as exc:
             print(f"[gemini-native] SKIP — strands.models.gemini unavailable: {exc}")
-            print("                run via: uv run --with google-genai python probes/probe_strands.py --provider gemini-native")
+            print("                run via: uv run --with google-genai python probes/probe_strands.py --provider gemini-native --env-file /path/to/gemini.env")
             return
         creds = load_credentials(Path(args.env_file), ["GEMINI_API_KEY"])
         redact = make_redactor(creds)
```

Notes on deliberate non-changes in the diff:
- `probe_groq.py --env-tag` choices `["[SIBLING-A]", "[SIBLING-B]"]` kept:
  evidence-file labels, not paths (disposition: keep).
- `probe_strands.py`'s two `--env-file`-omitting usage hints (docstring
  provider table, `run via:` print) were caught by the adversarial
  reviewer and fixed in this same change (the last two hunks above).
- `.env.example` untouched — its lines 49-52 state the explicit-only
  policy, which this change makes true.

## 3. probes/README.md before/after

Before (key passages, OBSERVED pre-edit):

> Credentials: `probe_common.load_credentials()` loads ONLY the explicitly
> requested variable NAMES (`CEREBRAS_API_KEY` / `GEMINI_API_KEY`) from an
> explicit `.env` file (default: the `../[SIBLING-A]` sibling).

> | `probe_groq.py` | … — one `--env-file`/`--env-tag` per sibling project |

> ```bash
> uv run --locked python probes/probe_cerebras.py
> uv run --locked python probes/probe_gemini.py
> uv run --locked python probes/probe_groq.py --env-file ~/projects/[SIBLING-A]/.env --env-tag [SIBLING-A]
> uv run --locked python probes/probe_groq.py --env-file ~/projects/[SIBLING-B]/.env      --env-tag [SIBLING-B]
> uv run --locked python probes/probe_strands.py --provider cerebras
> uv run --locked python probes/probe_strands.py --provider gemini-compat
> uv run --frozen --with google-genai python probes/probe_strands.py --provider gemini-native
> ```

After: see the README hunks in §2 — required-`--env-file` statement with
pointer to this doc and the superseded authorization (D-2026-09-04-12/-13),
`GROQ_API_KEY` added to the loaded-names list, "per credential source"
wording, all seven usage lines passing explicit placeholder `--env-file`
paths, plus the note that this repo's `.env` is a valid explicit choice for
GROQ/GEMINI probes and that Cerebras probes correctly fail
`credential(s) not present in env file` against it.

Documentation-code match: the adversarial reviewer verified all seven
usage commands against the actual argparse definitions (flags and
required-ness), and the Cerebras-vs-repo-`.env` claim against the actual
`.env` by name-presence (GROQ present, GEMINI present, CEREBRAS absent;
values never read; quoted failure text matches `probe_common.py` verbatim).

## 4. Repo-wide sibling-reference inventory and dispositions

Exhaustive sweep (Explore agent, both pre- and post-remediation states
captured). Pattern counts (matching lines, excluding .git/.venv/
__pycache__/uv.lock): `[SIBLING-A]` 26 → 22; `[SIBLING-B]`
24 → 22; sibling absolute paths 11 → 6; `DEFAULT_ENV_FILE` 10 → 2 (quotes inside
the historical cleanup doc and, post-append, the D-2026-09-05-01 ledger
entry itself; the sweep's pre-append count of 1 was corrected on reviewer
re-check). All remaining occurrences are outside
live code. Dispositions:

FIXED (live code / live doc, this change):
- `probes/probe_common.py:35` — the constant + its comment (deleted).
- `probes/probe_groq.py:7-8,39,96-97`, `probe_cerebras.py:38,93`,
  `probe_gemini.py:34-35,97`, `probe_strands.py:29,82` — imports and
  argparse defaults (now `required=True`).
- `probes/README.md:14,38,46-47` — default claim, "per sibling project"
  wording, sibling-path usage examples.
- `probes/probe_strands.py` docstring + `run via:` print (reviewer-caught,
  fixed same change).

REPORTED-ONLY — out of this task's safe scope:
- `agents/model.py:14-16` — name-only provenance mention of
  [SIBLING-B] (no path, no credential). File explicitly out of
  scope for this task (DO NOT list). Pre-publication cleanup candidate
  for the human.
- `probes/probe_groq.py:110`, `probes/probe_gemini.py:102`,
  `probes/probe_cerebras.py:99` — own-repo ABSOLUTE evidence-stem
  defaults (`~/projects/reconciliation-investigator/...`).
  Not sibling references; portability follow-up (derive from `__file__`).
  Behavior-affecting beyond the authorized security surface — not changed.
- `evals/gemini_judge_canary.py:31,182`, `groq_parsing_retry_canary.py:253`,
  `gemini_judge_5case.py:201` — "no sibling-project credential is read or
  copied" assertions; accurate (more so post-fix); untouched
  (eval code is out of scope).
- Dated historical docs quoting sibling paths/old default
  (`docs/final-doc-config-cleanup-2026-09-05.md`, 
  `docs/provider-feasibility-groq-two-keys-2026-09-04.md:165-166`,
  `docs/provider-feasibility-cerebras-gemini.md` incl. bare invocations
  at 510-515 that relied on the then-default,
  `docs/commit-history-audit-and-github-repo-plan-2026-09-05.md:206`,
  `docs/state-and-gap-analysis-2026-09-05.md:241`,
  `docs/git-identity-audit-stage1-2026-09-05.md`,
  `docs/git-stage3-pending-work-audit-2026-09-05.md`) — point-in-time
  records; annotate-don't-erase (architect must-not-miss #4).
- `agent-memory/decisions.md` D-2026-09-04-12/-13 text,
  `agent-memory/gemini-feasibility-*.md`, `gemini-quota-provenance-*.md`,
  `groq-preflight-*.md` — authorization provenance; append-only ledger and
  read-only notes; untouched (superseded instead via §6).
- `agent-memory/evidence/**` (frozen run records incl.
  `groq-probe-[SIBLING-A]-*.txt`, `groq-probe-[SIBLING-B]-*.txt`, 385
  `~/.local/...` traceback frames) — frozen evidence; untouched.

Zero hits for all patterns in: root `README.md`, `CLAUDE.md`,
`docs/EVALUATION.md`, `docs/DEVPOST-DRAFT.md`, `docs/build-contract.md`,
`tools/`, `orchestrator/`, `scripts/`, `tests/`, `deploy/`, `runtime/`,
`data/`. No secret VALUES found anywhere (placeholders only).

## 5. Test results

`probes/` has NO test coverage — stated explicitly, not assumed:
- Before: `.venv/bin/python -m pytest probes/ -q` → `no tests ran in
  0.01s`, exit code 5 (pytest "no tests collected").
- After: same command → `no tests ran in 0.00s`, exit code 5.
- Zero test files exist under `probes/` (MEASURED: directory listing).

Offline verification battery (all MEASURED post-change; nothing here
reads any credential file or makes any network call):

| Check | Command (essence) | Result |
|---|---|---|
| Syntax | `py_compile` × 5 probe files | rc=0 all (re-run after the strands fix) |
| Fail-fast | run each probe, `--env-file` omitted | rc=2, `error: the following arguments are required: --env-file` ×4 (argparse, before any file read/client construction) |
| Missing file | `--env-file ./no-such-file.env` (gemini, groq) | rc=1, `env file not found: no-such-file.env` (SystemExit in `load_credentials`) |
| Help text | `--help` on gemini, groq | `--env-file ENV_FILE` shown required with new help |
| Sibling-free | grep `[SIBLING-A]\|[SIBLING-B]` under `probes/` | 0 matches (re-confirmed after strands fix) |
| SoD guard | `scripts/guard-segregation-of-duties.sh` | exit 0 (unaffected surface) |
| Nothing staged | `git diff --cached --stat` | empty |

Full `scripts/verify.sh` NOT run: step 6 is the live 5-case Groq benchmark
(forbidden here), and probes are never exercised by verify.sh anyway
(OBSERVED: no verify.sh step touches probes/).

## 6. decisions.md entry

Added: `D-2026-09-05-01` (first entry of 2026-09-05; the ledger had none).
Convention reasoning (DOCUMENTED): no supersede convention previously
existed — no ledger entry had ever superseded another, and
`docs/final-doc-config-cleanup-2026-09-05.md:336-340` itself flags that
absence as a gap (the Z.AI→Groq switch was never logged). The ledger's own
rules are only "Append-only. Every entry dated." — so a plain dated entry
recording the human ruling uses the existing convention rather than
inventing one; it follows D-05's "two events, one entry" shape and D-12's
meta-note precedent. Full text appended to `agent-memory/decisions.md`
(see the file; summary): human ruling closing the Item-4 escalation;
REMOVAL of DEFAULT_ENV_FILE and required-`--env-file` in all four probes;
why option (b) was rejected; D-12/-13 FINDINGS stand (only the sibling-.env
arrangement is superseded); docs updated; evidence = this document
(Tier A gate, offline battery, no live calls, no sibling access); ledger
note that this is the log's first supersession entry.

## 7. Git status before/after

Before (session start snapshot, OBSERVED): 10 tracked files modified
(LICENSE, README.md, deploy/README.md, docs/credential-alternatives-prompt.md,
evals/run_evals.py, pyproject.toml, tools/*.py ×4) + ~50 untracked files
(docs/*-2026-*.md, agent-memory/*, evals/*, tests/*, .env.example) — all
pre-existing, untouched by this task. `probes/` files were CLEAN (tracked,
unmodified).

After: identical to before, plus exactly:
- Modified (tracked): `probes/README.md`, `probes/probe_cerebras.py`,
  `probes/probe_common.py`, `probes/probe_gemini.py`, `probes/probe_groq.py`,
  `probes/probe_strands.py`, `agent-memory/decisions.md`.
- New (untracked): `docs/probes-sibling-env-remediation-2026-09-05.md`
  (this file).
- Nothing staged (`git diff --cached` empty), nothing committed (HEAD
  unchanged at ac1ba3a), nothing pushed (no network git operations).

## 8. Claim classification

| Claim | Class |
|---|---|
| `--env-file` omitted → rc=2 argparse error in all 4 probes; nonexistent file → rc=1 | MEASURED |
| py_compile 5/5 rc=0; sibling grep under probes/ = 0; SoD guard exit 0; nothing staged | MEASURED |
| pytest probes/: 0 tests collected, rc=5, before and after | MEASURED |
| `probes/` contains no test files | MEASURED |
| Pre-fix code read the sibling `.env` when `--env-file` omitted (constant → argparse default → `load_credentials` `read_text`) | OBSERVED (static source trace; never executed — sibling access forbidden) |
| CEREBRAS_API_KEY absent / GROQ+GEMINI present in repo `.env` (names only) | MEASURED (reviewer name-presence grep; values never read) |
| README now matches code (flags, required-ness, failure text verbatim) | OBSERVED (reviewer cross-check) + MEASURED (usage/`--help` output) |
| Nothing outside `probes/` imports `probe_common` or invokes a probe | OBSERVED (repo-wide sweep; tests/ look-alikes verified unrelated) |
| Option (a) is correct per probes' coded purpose (5 points, §1) | OBSERVED (source) + DOCUMENTED (.env.example policy) |
| Prior authorization D-2026-09-04-12/-13 was investigation-scoped; findings stand | DOCUMENTED (ledger, quoted verbatim by delegated dig) |
| No supersede convention existed; gap already flagged | DOCUMENTED (final-doc-config-cleanup:336-340) |
| Sibling `.env` existence/contents on disk today | UNKNOWN (deliberately — no sibling access) |
| Whether the sibling `.env` still holds those credential names | UNKNOWN (deliberately) |
| Pattern counts (26→22 etc.) | CALCULATED (sweep greps, both states) |
| Removing the default reduces public-repo exposure | PROJECTED (the human's stated rationale) |

## 9. Process record

- Architect gate: Tier A, PROCEED (change surface = probes/ + docs + one
  ledger entry; no contract, no segregation-of-duties surface, no in-use
  credential path changed; human ruling in hand).
- Adversarial review (round 1): REJECT — sole blocking basis: this
  evidence document did not yet exist while `probes/README.md` and the
  ledger entry cited it (a sequencing artifact of deferring the report
  until the verdict; resolved by writing this document). One minor
  finding fixed in the same change: `probe_strands.py`'s two usage hints
  omitted the now-required `--env-file`. One nit recorded, untouched:
  `.env.example:50` "never read this repo's .env" is now strictly
  falsifiable via an explicit `--env-file .env` — protective intent
  (no implicit read) holds.
- Re-review verdict (round 2): ACCEPT — blocking defect resolved (this
  document exists; all four citations re-verified to resolve; §2's
  after-hunks independently matched against the working tree), the minor
  strands finding confirmed fixed (`probe_strands.py:19-20`, `:117`),
  sibling grep still 0 matches under `probes/`. One non-blocking
  correction applied at the reviewer's direction: §4's `DEFAULT_ENV_FILE`
  post-count corrected 1 → 2.
