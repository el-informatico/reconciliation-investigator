#!/usr/bin/env bash
# Ares V2 guard — SECONDARY, best-effort NOTICE. This is NOT enforcement.
#
# Empirical correction (2026-09-01, decisions.md D-07): a SessionStart hook
# cannot block a Claude Code session. Exit 1 and exit 2 both leave the
# session fully usable; interactively the trip message appears as a notice
# while the session continues, and in -p mode it does not appear at all.
# Real enforcement is the pre-launch wrapper scripts/ares-launch.sh, which
# refuses to start claude when CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS is
# present anywhere it can see. This hook stays registered as a redundant,
# audited notice for sessions started through some other path.
#
# Every invocation appends PASS/TRIP + UTC timestamp to
# agent-memory/guard-audit.log (directory auto-created; an append failure
# never changes this script's decision). The variable's value is never
# echoed or logged.
AUDIT_LOG="${CLAUDE_PROJECT_DIR:-.}/agent-memory/guard-audit.log"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$(dirname "$AUDIT_LOG")" 2>/dev/null || true
if [ -n "$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" ]; then
  echo "GUARD NOTICE (does NOT block — enforcement lives in scripts/ares-launch.sh):" \
       "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS is set (value withheld)." \
       "Agent Teams is forbidden in Ares V2. Stop this session and relaunch via ./scripts/ares-launch.sh." >&2
  printf '%s TRIP\n' "$STAMP" >> "$AUDIT_LOG" 2>/dev/null || true
  exit 2
fi
printf '%s PASS\n' "$STAMP" >> "$AUDIT_LOG" 2>/dev/null || true
exit 0
