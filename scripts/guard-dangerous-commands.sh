#!/usr/bin/env bash
# Ares V2 guard — PreToolUse BLOCKING guard for destructive / system-wide
# Bash commands. Unlike the SessionStart notice (which empirically cannot
# block — decisions.md D-07/D-08), PreToolUse exit 2 genuinely prevents the
# tool call and feeds this script's stderr to Claude as the denial reason.
#
# Origin: D-2026-09-03-18 — an approved-in-outcome but not-approved-as-
# described `docker volume prune -f` + `powercfg` ran on a 12-of-147 sample
# preview. This guard makes that class of command structurally un-runnable
# from any Ares session, regardless of preview steps or asserted semantics.
#
# Blocked categories (matched against the literal Bash command string):
#   1. Global container-engine cleanup: any docker/podman/nerdctl
#      `... prune`, any flags, including quote-split or .exe variants and
#      any command where 'prune' co-occurs with 'docker' indirection.
#      Project-scoped `docker compose ...` is deliberately NOT blocked —
#      verify.sh's `compose down -v` teardown is designed behavior.
#   2. System/OS configuration: powercfg, bcdedit, reg add/delete/import,
#      wsl --shutdown / --terminate / -t.
#   3. Recursive deletion outside the repo root: rm -r variants (absolute
#      or via cd, .., ~, symlinks, {} find-exec feeding, quoted payloads
#      to bash/sh -c, $-indirection fail-closed), find -delete/-exec rm
#      with outside operands, python -c shutil.rmtree. In-repo recursive
#      deletions remain allowed ($PWD is resolved; other variables fail
#      closed).
#   4. sudo anything — the allowlist is deliberately EMPTY. The corrective
#      pattern from the incident is to hand elevated commands to the human
#      to run directly (e.g. the wsl.conf rewrite), not to route them
#      through a session.
#
# Deliberate over-blocking: strings that merely CONTAIN a pattern (echoing
# or documenting "docker volume prune" in a Bash argument) are blocked too
# — the incident taught that clever exception handling is where approvals
# get rewritten. Workflow adaptation for this repo's own documentation
# work: write text via the Write tool and use `git commit -F <file>`, so
# the pattern never appears in the Bash command string.
#
# HONEST BOUNDARY (see decisions D-2026-09-03-19): this is a tripwire
# against the accident class that already happened, NOT containment.
# String matching cannot see runtime state (cd after the check, glob
# expansion, TOCTOU symlink swaps), other executors (base64|bash,
# printf|sh, ssh, perl, arbitrary python beyond the -c rmtree pattern,
# rsync --delete, docker run -v ...), commands run outside the Bash tool
# (Write + bash file.sh, MCP tools), or a human typing in a raw terminal.
#
# Auditing: every BLOCK appends "UTC BLOCK(<category>)" to
# agent-memory/guard-audit.log — the command text is never logged (it
# could contain secrets). Allows are silent. If this script cannot run
# (python3 missing), it fails CLOSED with exit 2.
#
# Hook registration (PreToolUse, matcher Bash) lives in .claude/settings.json:
#   bash "$CLAUDE_PROJECT_DIR/scripts/guard-dangerous-commands.sh"

AUDIT_LOG="${CLAUDE_PROJECT_DIR:-.}/agent-memory/guard-audit.log"

command -v python3 >/dev/null 2>&1 || {
  echo "BLOCKED (guard-error): guard-dangerous-commands.sh cannot run (python3 missing) — failing closed per design. Fix the guard before proceeding." >&2
  exit 2
}

INPUT="$(cat)"
VERDICT="$(python3 - "$INPUT" <<'PY'
import json, os, re, shlex, sys

try:
    doc = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)                       # not valid hook JSON: not ours to judge

if doc.get("tool_name") not in (None, "Bash"):
    sys.exit(0)

cmd = (doc.get("tool_input") or {}).get("command") or ""
if not cmd.strip():
    sys.exit(0)

repo = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR")
                        or doc.get("cwd") or os.getcwd())
low = cmd.lower()

# Normalized copy for category matching: quotes and backslashes between
# word characters vanish, so 'docker "volume" prune', 'docker vo\lume
# prune' and 'su""do' collapse to their plain forms.
norm = re.sub(r'["\'\\]', '', low)

def emit(cat, why):
    print("BLOCK\t%s\t%s" % (cat, why))
    sys.exit(0)

# --- Category 1: global container-engine prune (any form) -----------------
if (re.search(r'\b(docker|podman|nerdctl)(\.exe)?\s+((system|volume|builder|image|container|network)\s+)?prune\b', norm)
        or (re.search(r'(?<![\w-])prune\b', norm) and re.search(r'\b(docker|podman|nerdctl)\b', norm))):
    emit("docker-prune",
         "Global docker prune destroys volumes/cache/images across ALL "
         "projects on this machine, not just this repo. That is outside "
         "any Ares session's authority. If you (the human) want this "
         "cleanup, run it yourself in your own terminal.")

# --- Category 2: system/OS configuration ----------------------------------
if (re.search(r'\bpowercfg(\.exe)?\b', norm)
        or re.search(r'\bbcdedit(\.exe)?\b', norm)
        or re.search(r'\breg(\.exe)?\s+(add|delete|import)\b', norm)
        or re.search(r'\bwsl(\.exe)?\s+(--shutdown|--terminate|-t)\b', norm)):
    emit("system-config",
         "This command changes Windows/WSL system configuration, which "
         "affects the whole machine, not just this repo. That is outside "
         "any Ares session's authority. Run it yourself directly if you "
         "want it (e.g. via the ! prompt prefix).")

# --- Category 3: recursive deletion outside the repo root ------------------

def tokenize(text):
    """Quote-aware tokens incl. shell operators as their own tokens."""
    lex = shlex.shlex(text, posix=True, punctuation_chars='();&|<>')
    lex.whitespace_split = True
    return list(lex)

OPERATORS = {'&&', '||', ';', '|', '(', ')', '&', '<', '>', ';;'}

def outside(p, anchor):
    """True if resolved path p escapes the repo root."""
    expanded = os.path.expanduser(p)
    expanded = expanded.replace('$pwd', anchor).replace('${pwd}', anchor)
    if '$' in expanded or '`' in expanded:
        return None                    # unresolvable -> caller fails closed
    if not os.path.isabs(expanded):
        expanded = os.path.join(anchor, expanded)
    real = os.path.realpath(expanded)  # resolves symlink escapes
    return not (real == repo or real.startswith(repo + os.sep))

def check_rm_tokens(tokens, anchor, depth, allow_placeholder=False):
    """Walk one token list; block on recursive rm escaping the repo."""
    i = 0
    while i < len(tokens):
        t = tokens[i]
        bare = t.lstrip('`$([{')
        if bare == 'rm' or bare.endswith('/rm'):
            j = i + 1
            flags, paths = set(), []
            while j < len(tokens) and tokens[j] not in OPERATORS:
                x = tokens[j]
                if x.startswith('-') and x != '-':
                    flags.update(x[1:].lstrip('-'))
                    j += 1
                else:
                    paths.append(x)
                    j += 1
            if 'r' in flags or 'R' in flags:
                if not paths:
                    emit("rm-outside-repo",
                         "Recursive rm with no explicit path operand (e.g. "
                         "fed by xargs at runtime) cannot be confined to "
                         "the repo; the guard fails closed. Name the "
                         "paths explicitly under the repo root.")
                for p in paths:
                    if '{' in p or '}' in p:
                        if not allow_placeholder:
                            emit("rm-outside-repo",
                                 "rm -r with find-exec placeholders ({}) "
                                 "outside a find command cannot be "
                                 "confined; the guard fails closed. Delete "
                                 "with explicit paths under the repo root.")
                        continue
                    verdict = outside(p, anchor)
                    if verdict is None:
                        emit("rm-outside-repo",
                             "rm -r with a variable/unresolvable target "
                             "cannot be confined to the repo; the guard "
                             "fails closed. Use an explicit path under the "
                             "repo root ($PWD is resolved).")
                    if verdict:
                        emit("rm-outside-repo",
                             "Recursive rm on a path outside this repo can "
                             "destroy other projects' files — outside any "
                             "Ares session's authority. Keep deletions "
                             "inside the repo, or run it yourself directly "
                             "if you really want it.")
            i = j if j > i else i + 1
        else:
            # Quoted payloads (bash -c '...', su -c '...', eval '...') are
            # single tokens: rescan their contents, depth-limited.
            if depth > 0 and re.search(r'(^|\s)(/bin/)?rm\s+-[a-z]*r', t):
                try:
                    check_rm_tokens(tokenize(t), anchor, depth - 1)
                except ValueError:
                    emit("rm-outside-repo",
                         "An rm command inside a quoted payload could not "
                         "be parsed; the guard fails closed. Rewrite it "
                         "plainly.")
            i += 1

def check_find(tokens, anchor):
    if not tokens or tokens[0] not in ('find', '/usr/bin/find', '/bin/find'):
        return
    destructive = any(t in ('-delete', '-rm') for t in tokens) or (
        any(t in ('-exec', '-execdir') for t in tokens)
        and any(t.rstrip(';+\\') == 'rm' for t in tokens))
    if not destructive:
        return
    paths = []
    for t in tokens[1:]:
        if t.startswith('(') or t.startswith('-'):
            break
        paths.append(t)
    if not paths:
        paths = ['.']
    for p in paths:
        verdict = outside(p, anchor)
        if verdict is None or verdict:
            emit("rm-outside-repo",
                 "find with -delete/-exec rm over paths outside (or "
                 "unresolvable against) this repo cannot be confined; the "
                 "guard fails closed. Keep find deletions inside the repo.")
    # If rm rides an -exec, its explicit operands must also stay in-repo
    # ({} placeholders are fine — confined by find's validated roots).
    for k, t in enumerate(tokens):
        if t in ('-exec', '-execdir'):
            check_rm_tokens(tokens[k + 1:], anchor, 0, allow_placeholder=True)
            break

# python -c with rmtree: realistic agent-shaped deletion bypass
if re.search(r'\bpython3?\s+(-[a-z]\s+)*-c', norm) and re.search(
        r'shutil\.rmtree\s*\(|os\.system\s*\(\s*[\'"][^\'"]*rm\b', norm):
    emit("rm-outside-repo",
         "python -c with shutil.rmtree/os.system(rm...) cannot be "
         "confined to the repo by string inspection; the guard fails "
         "closed. Use explicit rm with paths under the repo root.")

try:
    tokens = tokenize(low)
except ValueError:
    if re.search(r'[\s(=`]rm[\s)`]|^rm[\s)`]', low):
        emit("rm-outside-repo",
             "An rm command in this line could not be parsed (unbalanced "
             "quoting); the guard fails closed for rm-shaped commands. "
             "Rewrite the command plainly.")
    sys.exit(0)

# Walk tokens as segments split by shell operators, tracking cd so
# relative deletions anchor to where the shell would actually run them.
anchor = os.path.realpath(doc.get("cwd") or repo)
seg = []
for t in tokens + [';']:
    if t in OPERATORS:
        if seg:
            first = seg[0].lstrip('$').lstrip('(')
            if first == 'cd' and len(seg) >= 2:
                target = seg[1].replace('$pwd', anchor).replace('${pwd}', anchor)
                if not target.startswith(('/', '$', '~')) and '$' not in target:
                    anchor = os.path.realpath(os.path.join(anchor, target))
                else:
                    try:
                        anchor = os.path.realpath(os.path.expanduser(target))
                    except Exception:
                        pass
            elif first in ('find', '/usr/bin/find', '/bin/find'):
                check_find(seg, anchor)
            else:
                check_rm_tokens(seg, anchor, 2)
        seg = []
    else:
        seg.append(t)

# --- Category 4: sudo (allowlist deliberately empty) -----------------------
if re.search(r'(^|[\s;|&](?!>))sudo(\.exe)?(\s|$)', norm) or re.search(
        r'[\s(;&]sudo[\s]', norm) or norm.startswith('sudo ') or norm.startswith('sudo\t'):
    emit("sudo",
         "Elevated (sudo) commands are outside any Ares session's "
         "authority — the allowlist is deliberately empty. If a command "
         "needs elevation, hand it to the human to run directly (the "
         "wsl.conf rewrite pattern from the incident report).")

# Anything else: allow (stay silent).
PY
)"
case $? in
  0) ;;
  *) echo "BLOCKED (guard-error): guard-dangerous-commands.sh internal failure — failing closed per design." >&2
     exit 2 ;;
esac

if [ -n "$VERDICT" ]; then
  CAT="$(printf '%s' "$VERDICT" | cut -f2)"
  WHY="$(printf '%s' "$VERDICT" | cut -f3-)"
  mkdir -p "$(dirname "$AUDIT_LOG")" 2>/dev/null || true
  printf '%s BLOCK(%s)\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$CAT" \
    >> "$AUDIT_LOG" 2>/dev/null || true
  echo "BLOCKED (dangerous-command guard, category: $CAT): $WHY" >&2
  exit 2
fi
exit 0
