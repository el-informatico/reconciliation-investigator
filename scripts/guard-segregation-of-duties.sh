#!/usr/bin/env bash
# Ares V2 guard — segregation of duties between INVESTIGATION and
# CORRECTION. Added 2026-09-04 (decisions D-2026-09-04-03) alongside the
# python-strands profile; ships to every repo via templates/common/ and
# is a harmless no-op wherever no .py files exist.
#
# INVARIANT ENFORCED: the string "apply_correction" must never appear on
# a Python source line that also constructs a Strands Agent. A violating
# line matches BOTH of:
#   - 'Agent' followed by optional whitespace then '(' — case-sensitive,
#     deliberately NO left word boundary, so "Agent(", "Agent (",
#     "strands.Agent(", "MyAgent(", "SubAgent(" all count: any
#     Agent-suffixed constructor is the same construction shape;
#   - the substring "apply_correction" anywhere on that physical line —
#     bare name, attribute access, inside a tools list, and also inside
#     a comment or string literal that quotes the shape (deliberate
#     over-blocking: exception handling is where approvals get
#     rewritten — same class as guard-dangerous-commands.sh, D-19).
#
# Violation => exit 1 (this is what fails the python-strands verify.sh
# step and the scripts/hooks/pre-commit commit gate). Bad invocation
# (target not a directory) => exit 2. Clean tree => exit 0, silent.
# Invoked as: guard-segregation-of-duties.sh [target-dir]  (default:
# this script's repo root).
#
# HONEST BOUNDARY (same honesty standard as guard-dangerous-commands.sh):
# this is a grep-shaped tripwire against the accident class, NOT
# containment.
#   - PHYSICAL-LINE scope only. A multi-line construction whose
#     apply_correction sits on a different line than the "Agent(" —
#       agent = Agent(
#           tools=[apply_correction],
#       )
#     — is NOT caught. Neither is indirection: a tools list built into
#     a variable elsewhere, aliasing (ac = apply_correction), getattr,
#     exec, or string-assembled names all evade it.
#   - It sees only *.py files under the scanned tree (skips .git/,
#     .venv/, node_modules/); generated code and other file types are
#     invisible to it. Symlinked .py files ARE followed; unreadable
#     directories are skipped with a find warning while the guard still
#     exits 0.
#   - Over-blocking, concretely: any ONE line pairing the words trips
#     it even outside construction syntax — e.g. a status log line
#     like  log.info(f"Agent (investigation) done; apply_correction
#     deferred"). Deliberate (D-19 class): reword the message, do not
#     add an exception path. A path containing the literal ':<digits>:'
#     before the word could alias the anchor — accepted next to the
#     alternative of flagging every apply_correction-named file.
#   - The pre-commit wiring is bypassable (--no-verify), and anyone who
#     can edit scripts/ can drop the verify step — but scripts/** is
#     outside every project seat's ownership and changes there are Tier
#     C territory.
# The COMPLEMENTARY structural check is procedural: in projects built
# from the python-strands profile, changes touching apply_correction,
# correction_executor, or human_gate are Tier C by rule table (the
# project's task contract carries the row) — this guard trips the
# careless, the rule table gates the deliberate.
#
# Auditing: every FAIL appends "UTC BLOCK(segregation: N)" to this
# repo's agent-memory/guard-audit.log (best-effort; an append failure
# never changes the decision). Passes are silent — verify.sh prints its
# own step line.

set -u
TARGET="${1:-$(cd "$(dirname "$0")/.." && pwd -P)}"
if [ ! -d "$TARGET" ]; then
  echo "guard-segregation: target '$TARGET' is not a directory" >&2
  exit 2
fi

# grep -anE finds Agent-construction lines (-a: files grep would class
# as binary, e.g. NUL-containing UTF-16 artifacts, are still scanned);
# the ':<digits>:' anchor keeps the second stage on the line CONTENT —
# a file merely NAMED apply_correction.py must not trip on its own
# path prefix. /dev/null forces file:line: prefixes even when a single
# file matches; xargs -r copes with zero .py files; -type l follows
# symlinked .py files (security review 2026-09-04, findings 2/3/5).
VIOL="$(find "$TARGET" \( -type f -o -type l \) -name '*.py' \
  -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/node_modules/*' \
  -print0 \
  | xargs -0 -r grep -anE 'Agent[[:space:]]*\(' -- /dev/null \
  | grep -E ':[0-9]+:.*apply_correction' || true)"

if [ -n "$VIOL" ]; then
  HITS="$(printf '%s\n' "$VIOL" | wc -l)"
  echo "BLOCKED (segregation-of-duties guard): $HITS line(s) construct a Strands Agent and reference apply_correction on the same physical line:" >&2
  printf '%s\n' "$VIOL" >&2
  echo "Investigation and correction must stay separate: apply_correction belongs to the correction-executor path (with its human gate), never to an Agent(...) tools list. Restructure the code, or route the change through the Tier C gate." >&2
  ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
  AUDIT="$ROOT/agent-memory/guard-audit.log"
  mkdir -p "$(dirname "$AUDIT")" 2>/dev/null || true
  printf '%s BLOCK(segregation: %s)\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$HITS" \
    >> "$AUDIT" 2>/dev/null || true
  exit 1
fi
exit 0
