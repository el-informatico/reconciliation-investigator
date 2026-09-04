#!/usr/bin/env bash
# reconciliation-investigator — verify.sh (Ares V2 python-strands profile).
#
# Control-plane artifact stamped from the profile template (the
# verify.sh carve-out is recorded in aresV2 decisions D-2026-09-04-02):
# these steps are the profile's BASELINE acceptance criteria.
# Project-specific criteria are ADDED as new steps — never by deleting
# or weakening these. Executed by the QA seat; its output is the
# authoritative end-to-end evidence.
#
# Steps:
#   1 preflight      — uv, python3, git present (uv missing = FAIL with
#                      manual-install instructions; NEVER auto-installed)
#   2 segregation    — scripts/guard-segregation-of-duties.sh over the
#                      repo (apply_correction must never construct an
#                      Agent on one line) + pre-commit wiring check
#                      (core.hooksPath + exec bit: git silently ignores
#                      a non-executable hook)
#   3 pypi-freshness — ADVISORY: pinned (pyproject.toml) vs live latest
#                      (pypi.org/pypi/<pkg>/json); PASS either way,
#                      prints REFRESH-RECOMMENDED on drift, WARNs (never
#                      silently skips) if PyPI is unreachable
#   4 uv-sync        — uv sync --locked (uv.lock must exist and be
#                      current; regenerating it is a deliberate act)
#   5 pytest         — uv run --locked pytest -q
#   6 evals          — EVAL_MODE=1 uv run --locked python
#                      evals/run_evals.py (absent runner = FAIL:
#                      application spec files not yet placed)
#
# Conventions per the validated Ares verify.sh shape: set -u, NOT set -e
# — a failing check must count, not abort; full output teed to /tmp;
# ends with a VERDICT line and exit 0/1. There is NO Docker/Postgres/
# compose step in this profile BY DESIGN: EVAL_MODE=1 mocks both
# external systems from data/seed_transactions.json (docs/gotchas.md
# §0). Do not "fix" a failing run by adding a container stack.

set -u -o pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
LOG="/tmp/$(basename "$ROOT")-verify-$(date -u +%Y%m%dT%H%M%SZ).log"
PASS=0
FAIL=0

exec > >(tee -a "$LOG") 2>&1

echo "[verify] repo: $ROOT"
echo "[verify] log:  $LOG"

# --- step 1: preflight -----------------------------------------------------
echo
echo "[verify] === step 1: preflight ==="
missing=""
for tool in uv python3 git; do
  command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
done
if [ -n "$missing" ]; then
  FAIL=$((FAIL + 1))
  echo "[verify] FAIL  step 1 preflight — missing:$missing"
  echo "  uv install is a human-approved manual act (never run an installer from a verify script):"
  echo "    curl -LsSf https://astral.sh/uv/install.sh | sh   # user-local, ~/.local/bin"
else
  PASS=$((PASS + 1))
  echo "[verify] PASS  step 1 preflight — $(uv --version 2>/dev/null | head -1); $(python3 --version 2>&1); $(git --version 2>/dev/null)"
fi

# --- step 2: segregation of duties (+ pre-commit wiring) -------------------
echo
echo "[verify] === step 2: segregation-of-duties guard ==="
if [ ! -f "$ROOT/scripts/guard-segregation-of-duties.sh" ]; then
  FAIL=$((FAIL + 1))
  echo "[verify] FAIL  step 2 segregation guard — scripts/guard-segregation-of-duties.sh is MISSING (wiring defect; scripts/** is controlling-session territory)"
elif ! bash "$ROOT/scripts/guard-segregation-of-duties.sh" "$ROOT"; then
  FAIL=$((FAIL + 1))
  echo "[verify] FAIL  step 2 segregation guard — see the BLOCKED lines above (investigation and correction must stay separate)"
else
  PASS=$((PASS + 1))
  echo "[verify] PASS  step 2 segregation guard — no Agent(...)+apply_correction line"
  hookpath="$(git -C "$ROOT" config core.hooksPath 2>/dev/null || true)"
  if [ "$hookpath" = "scripts/hooks" ] && [ -x "$ROOT/scripts/hooks/pre-commit" ]; then
    echo "[verify]        pre-commit wiring OK (core.hooksPath=scripts/hooks, hook executable)"
  else
    FAIL=$((FAIL + 1))
    echo "[verify] FAIL  step 2 pre-commit wiring — core.hooksPath='$hookpath' (want scripts/hooks) or scripts/hooks/pre-commit lacks the exec bit; git SILENTLY IGNORES a non-executable hook"
  fi
fi

# --- step 3: PyPI freshness (advisory) --------------------------------------
echo
echo "[verify] === step 3: pypi freshness (advisory) ==="
if python3 - "$ROOT/pyproject.toml" <<'PY'
# Advisory freshness report: pinned vs live-latest per dependency.
# Exits 0 even on warn-able conditions (staleness is a recommendation,
# not a failure; a network outage must not fail verify — but must never
# be silent). A non-zero exit here means python3 itself failed.
import json
import sys
import urllib.request

try:
    import tomllib
    with open(sys.argv[1], "rb") as f:
        doc = tomllib.load(f)
    pins = {}
    for dep in doc.get("project", {}).get("dependencies", []):
        base = dep.split(";")[0].strip()          # drop env markers
        name, _, spec = base.partition("==")
        if spec:
            pins[name.strip().split("[")[0]] = spec.strip().split()[0]
except Exception as exc:  # unparsable pins: warn, do not fail
    print(f"  WARN: could not parse pyproject pins ({exc!r}) — freshness check skipped")
    sys.exit(0)

for name, pinned in sorted(pins.items()):
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=15) as r:
            latest = json.load(r)["info"]["version"]
        marker = "" if latest == pinned else "  REFRESH-RECOMMENDED"
        print(f"  {name}: pinned={pinned} latest={latest}{marker}")
    except Exception as exc:
        print(f"  WARN: pypi lookup failed for {name} ({exc!r})")
PY
then
  PASS=$((PASS + 1))
  echo "[verify] PASS  step 3 pypi freshness — advisory, see table above"
else
  rc=$?
  FAIL=$((FAIL + 1))
  echo "[verify] FAIL  step 3 pypi freshness — python3 failed (exit $rc); the advisory report could not run at all"
fi

# --- step 4: uv sync --------------------------------------------------------
echo
echo "[verify] === step 4: uv sync --locked ==="
if [ ! -f "$ROOT/uv.lock" ]; then
  FAIL=$((FAIL + 1))
  echo "[verify] FAIL  step 4 uv-sync — uv.lock absent; bootstrap must generate and commit it (run: uv lock), then re-run verify"
elif (cd "$ROOT" && uv sync --locked); then
  PASS=$((PASS + 1))
  echo "[verify] PASS  step 4 uv sync --locked"
else
  rc=$?
  FAIL=$((FAIL + 1))
  echo "[verify] FAIL  step 4 uv sync --locked (exit $rc) — lockfile stale or environment broken; regenerate deliberately (uv lock), re-commit, re-run"
fi

# --- step 5: pytest ---------------------------------------------------------
echo
echo "[verify] === step 5: pytest ==="
if (cd "$ROOT" && uv run --locked pytest -q); then
  PASS=$((PASS + 1))
  echo "[verify] PASS  step 5 pytest"
else
  rc=$?
  FAIL=$((FAIL + 1))
  echo "[verify] FAIL  step 5 pytest (exit $rc)"
fi

# --- step 6: evals ----------------------------------------------------------
echo
echo "[verify] === step 6: evals (EVAL_MODE=1) ==="
# PYTHONPATH=$ROOT: `python evals/run_evals.py` puts the SCRIPT's dir on
# sys.path, not the repo root — in this virtual project nothing else adds
# the root, so the runner's absolute imports (evals.cases, and later
# orchestrator.*, tools.*) need it explicitly. stdin feeds 'q':
# report.run_display() opens an INTERACTIVE rich prompt (expand cases /
# q to quit); under a non-tty it would EOFError and fail the step. The
# pass rate inside the report is the application's own score — this
# step proves the HARNESS runs; per-project criteria may assert on the
# rate when implementation lands.
if [ ! -f "$ROOT/evals/run_evals.py" ]; then
  FAIL=$((FAIL + 1))
  echo "[verify] FAIL  step 6 evals — evals/run_evals.py not present (application spec files not yet placed; expected at evals/cases.py, evals/run_evals.py, data/seed_transactions.json)"
elif (cd "$ROOT" && printf 'q\n' | EVAL_MODE=1 PYTHONPATH="$ROOT" uv run --locked python evals/run_evals.py); then
  PASS=$((PASS + 1))
  echo "[verify] PASS  step 6 evals (EVAL_MODE=1)"
else
  rc=$?
  FAIL=$((FAIL + 1))
  echo "[verify] FAIL  step 6 evals (exit $rc) — exact error above"
fi

# --- verdict ----------------------------------------------------------------
echo
if [ "$FAIL" -eq 0 ]; then
  echo "[verify] VERDICT: PASS ($PASS steps passed)"
  exit 0
fi
echo "[verify] VERDICT: FAIL (PASS=$PASS FAIL=$FAIL) — full log: $LOG"
exit 1
