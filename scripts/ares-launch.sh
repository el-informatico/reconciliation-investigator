#!/usr/bin/env bash
# ares-launch.sh — the only sanctioned way to start an Ares V2 Control Plane
# session. Enforcement of the Agent Teams ban lives HERE, before the claude
# process exists at all, because SessionStart hooks CANNOT block a session
# (empirically verified 2026-09-01 — exit 1 and exit 2 both leave the session
# fully usable; see agent-memory/decisions.md D-07).
#
# Refuses to launch (exit 1, naming the source, appending REFUSED to the
# guard audit log) when CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS is:
#   1. configured in the env block of any of: ~/.claude/settings.json,
#      <project>/.claude/settings.json, <project>/.claude/settings.local.json
#      — a value someone deliberately put in a settings file deserves a
#      visible refusal, not a silent override;
#   2. present in the environment at invocation.
# As a final invariant the variable is unset immediately before exec, so no
# code path that reaches `exec claude` can ever carry it.
#
# Note on the two checks: the environment check refuses (rather than quietly
# stripping) because the wrapper cannot distinguish deliberate inline
# setting from ambient contamination, and a visible refusal is the safe
# failure mode; the unset remains as the last-line invariant regardless.

set -u
VAR="CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
AUDIT_LOG="$ROOT/agent-memory/guard-audit.log"

audit() { # $1 = reason tag
  mkdir -p "$(dirname "$AUDIT_LOG")" 2>/dev/null || true
  printf '%s REFUSED(%s)\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" \
    >> "$AUDIT_LOG" 2>/dev/null || true
}

# Returns 0 (and prints a detail line) if the settings file carries the key
# in its env block; falls back to a substring scan if the file is unparseable
# JSON so a broken settings file cannot hide the key.
settings_has_key() { # $1 = file
  python3 - "$1" "$VAR" <<'PY' 2>/dev/null
import json, sys
path, var = sys.argv[1], sys.argv[2]
try:
    with open(path) as f:
        doc = json.load(f)
except FileNotFoundError:
    sys.exit(1)
except Exception:
    sys.exit(0 if var in open(path, errors="replace").read() else 1)
if isinstance(doc, dict) and var in (doc.get("env") or {}):
    print(f"the env block of {path}")
    sys.exit(0)
sys.exit(1)
PY
}

for f in "$HOME/.claude/settings.json" "$ROOT/.claude/settings.json" "$ROOT/.claude/settings.local.json"; do
  if [ -f "$f" ]; then
    if detail="$(settings_has_key "$f")"; then
      echo "REFUSED: $VAR is configured in $detail." >&2
      echo "Remove it from that file, then relaunch. Agent Teams is forbidden in Ares V2." >&2
      audit "settings:$f"
      exit 1
    fi
  fi
done

if [ -n "${!VAR:-}" ]; then
  echo "REFUSED: $VAR is set in the environment at invocation (value withheld)." >&2
  echo "Unset it and relaunch. Agent Teams is forbidden in Ares V2; sessions start via ./scripts/ares-launch.sh." >&2
  audit "env"
  exit 1
fi

# --- Concurrency governor (added 2026-09-03; decisions D-2026-09-03-22) --
# Refuses to launch when live claude sessions for THIS project already meet
# max_concurrent_zai_calls from agent-memory/task-board.json. Liveness is
# measured statelessly from /proc: a session counts iff basename(argv[0])
# is "claude" AND its cwd is $ROOT (physical — hence pwd -P above). No
# counter file exists to go stale: a session killed -9 stops counting the
# moment it dies (a zombie's /proc/PID/cwd is unreadable and its cmdline
# is empty — verified empirically 2026-09-03), so no crash can wedge this
# gate. Only the FIRST cmdline field is compared: substring matching
# anywhere in cmdline false-positives on Bash-tool subshells carrying
# .claude/shell-snapshots paths. A SCRIPT named claude (shebang shim)
# is never counted: exec of a script rewrites argv[0] to its
# interpreter, so only a binary named claude matches — like the real
# ELF. Fail-open on missing/null/unparseable
# board or value < 1 — the template skeleton is deliberately null at
# bootstrap, and refusing there would break every scaffold. (Deliberate
# asymmetry with the Agent Teams check, which fails closed: a hidden
# dangerous key is a hazard; no configured limit is a policy absence,
# not a hazard.) The gate caps SESSIONS; the board's Phase 0 basis
# budgeted concurrent API calls — the value is applied as a session cap
# because that is what a launcher can observe.
BOARD="$ROOT/agent-memory/task-board.json"
max="$(python3 - "$BOARD" <<'PY' 2>/dev/null
import json, sys
try:
    v = json.load(open(sys.argv[1])).get("max_concurrent_zai_calls")
except Exception:
    sys.exit(0)  # missing/unparseable board: no limit (fail-open)
if isinstance(v, bool) or not isinstance(v, int) or v < 1:
    sys.exit(0)  # null, absent, non-int, bool, or < 1: no limit (fail-open)
print(v)
PY
)"

if [ -z "$max" ]; then
  echo "governor: no usable max_concurrent_zai_calls in $BOARD — proceeding without a session cap." >&2
else
  live=0
  for pid in /proc/[0-9]*; do
    [ -r "$pid/cmdline" ] || continue
    IFS= read -r -d '' argv0 < "$pid/cmdline" 2>/dev/null || continue
    [ "${argv0##*/}" = "claude" ] || continue
    [ "$(readlink "$pid/cwd" 2>/dev/null)" = "$ROOT" ] || continue
    live=$((live + 1))
  done
  if [ "$live" -ge "$max" ]; then
    echo "REFUSED: concurrency governor — $live live claude session(s) for this project already meet the max of $max." >&2
    echo "Close a session, or adjust max_concurrent_zai_calls in $BOARD, then relaunch." >&2
    audit "governor: ${live}/${max} live, board $BOARD"
    exit 1
  fi
fi

# Final invariant: never reach exec with the variable present.
unset "$VAR" 2>/dev/null || true
cd "$ROOT"
exec claude "$@"
