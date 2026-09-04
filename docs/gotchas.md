# Python-strands profile — documented gotchas

Authored 2026-09-04 with the profile itself (decisions D-2026-09-04-02,
aresV2) — unlike the two Java-era profiles this one was not extracted
from a completed reference project; its specification basis is the
fully-specified build contract of the profile's first stamp
(`reconciliation-investigator`). Everything below was live-verified
against primary sources on 2026-09-04 (PyPI JSON API, strandsagents.com
docs, docs.astral.sh). These are **known issues to handle proactively,
not historical trivia**.

## 0. No Docker / no Postgres / no compose — INTENTIONAL, not an oversight

This profile deliberately has no container stack. Data comes from a
mocked seed JSON file (`data/seed_transactions.json`) and the external
systems are mocked when `EVAL_MODE=1` is set — that environment
variable is exported by `scripts/verify.sh` step 6, and its semantics
are defined by the project's build contract (`docs/build-contract.md`),
not by this profile. Consequences to hold on to:

- verify.sh has NO compose-up/health-gate/teardown steps and must never
  grow them to "fix" a failure — a failing run means code or env is
  wrong, not that infrastructure is missing.
- Do not add Dockerfiles, compose files, or a Postgres dependency to a
  project built from this profile without an explicit contract change
  (Tier C).

## 1. uv: virtual project shape — never `uv init` here

- The shipped `pyproject.toml` has `[project]` and deliberately NO
  `[build-system]`: this is a uv "virtual" project — dependencies only,
  no package build, the repo runs from its root. Since uv 0.12, `uv
  init` defaults to a build system + `src/<name>/` layout; running it
  in this repo would corrupt the shape. Edit `pyproject.toml` by hand.
- `uv.lock` IS committed (generated at bootstrap by `uv lock`; uv
  documents the lockfile as meant for version control). verify.sh runs
  `uv sync --locked` / `uv run --locked`, which REFUSE if the lockfile
  is stale — regenerating it is always a deliberate, committed act.
- `.python-version` pins `3.13`. uv auto-downloads that interpreter if
  it is absent — do not "helpfully" switch to the system Python (which
  may be older than requires-python).
- pytest lives in the `dev` dependency-group (uv installs the dev group
  by default on `uv sync`).

## 2. Segregation of duties is structural, not stylistic

`scripts/guard-segregation-of-duties.sh` (shipped via templates/common)
fails the build when any `.py` line both constructs a Strands `Agent(`
and contains `apply_correction`. It runs in verify.sh step 2 and as the
git pre-commit hook (`scripts/hooks/pre-commit`, wired via `git config
core.hooksPath scripts/hooks`). Honest limits, stated in the guard's own
header: physical-line scope only (multi-line constructions and
indirection evade it), `--no-verify` bypasses the commit gate — it is a
tripwire, not containment. The deliberate-change path is covered by the
OCM rule table: changes touching `apply_correction`,
`correction_executor`, or `human_gate` are Tier C in projects built
from this profile (the project's task contract carries the row).

## 3. Strands API shapes this repo relies on (dated 2026-09-04)

Live-verified against https://strandsagents.com/docs/ user-guide
quickstart pages, for strands-agents 1.54.0:

- `from strands import Agent, tool` — Agent constructor and `@tool`
  decorator live at the top level of the `strands` package
  (`pip install strands-agents`).
- `Agent(tools=[...])` — the tools list is a constructor argument.
- First-party bundled tools are a SEPARATE distribution
  (`strands-agents-tools`, `from strands_tools import ...`) — not a
  dependency of this profile unless the project contract adds it.
- The evals framework (`strands-agents-evals`) imports as
  `strands_evals`; its documented entry point is the
  `Experiment`/`run_evaluations` API and the `strands-evals` CLI. The
  project's `evals/run_evals.py` (a build-contract artifact) decides the
  actual invocation — verify.sh runs that file, nothing else.
- The SDK's GitHub repository is now `strands-agents/harness-sdk`; the
  older `strands-agents/sdk` path is dead (verified 404 "Not Found"
  2026-09-04). Cite the new path in any research.

## 4. Stack versions — RE-VERIFY LIVE, never copy

Profile snapshot measured 2026-09-04 by the aresV2 controlling session
(direct fetches, cross-checked by a delegated research pass):

| Component | Snapshot | Source |
|---|---|---|
| Python | 3.13 (line: 3.13.15) | endoflife.date/api/python.json + python.org |
| strands-agents | 1.54.0 (2026-08-27) | pypi.org/pypi/strands-agents/json |
| strands-agents-evals | 1.2.0 (2026-08-21; requires strands-agents>=1.42.0) | pypi.org/pypi/strands-agents-evals/json |
| pytest | 9.1.1 | pypi.org/pypi/pytest/json |
| uv (tooling) | 0.12.9 (floor >=0.12 for the current behavior generation) | pypi.org/pypi/uv/json |

These are **dated snapshots, not template values** — a bootstrap must
look each one up live at bootstrap time and record source+date in the
project's `agent-memory/bootstrap-report.md`. requires_python for both
strands packages is >=3.10, but 3.10 EOLs 2026-10-31 — do not pin it
for new projects; 3.13 is the newest bugfix-status line. Ignore
prereleases unless deliberately chosen.
