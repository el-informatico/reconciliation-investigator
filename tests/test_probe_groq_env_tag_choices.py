"""2026-09-07 regression tests for the probes/probe_groq.py --env-tag
rename (plan §4.5, decision D-1 Option B): the choices set must be
EXACTLY {key-a, key-b}, and the two retired sibling-derived evidence
labels must no longer appear anywhere on the probe's CLI surface.

This file never spells the retired labels: the sensitive-content
pre-commit guard (scripts/guard-sensitive-content.sh) blocks any staged
line that carries a configured token. The no-residual check instead
loads the token list at RUNTIME from .git/sensitive-tokens — the same
list, with the same blank-line semantics, that the guard itself
consumes — and asserts that no configured token appears in the probe's
--help output.

Offline by construction — the code-order guarantee in probe_groq.py:
  - main() builds its parser and calls parse_args() at line 108.
    --help exits 0 inside argparse; an out-of-choices --env-tag value
    exits 2 inside argparse. Both happen before any other statement of
    main() can run.
  - The next statement that can end the process is
    load_credentials(...) at line 114, which raises
    SystemExit("env file not found: <path>") for a missing env file
    (probes/probe_common.py:38, message echoed to stderr, exit status
    1) — BEFORE the OpenAI client is constructed (probe_groq.py:116)
    and before the first network request, models.list
    (probe_groq.py:122).
  - Importing the module (including `import openai`, line 37) performs
    no network I/O.
Every invocation in this module therefore terminates at line 108 or at
probe_common.py:38 and cannot reach line 122. The subprocess timeout in
run_probe() is a backstop against a future code-order regression, not
an expectation. The rename itself is line-count-neutral (each edited
hunk swaps two lines for two lines), so the line references above stay
valid after it lands.

Token-list semantics mirror scripts/guard-sensitive-content.sh: read
.git/sensitive-tokens (the guard resolves it via the git dir — the same
path in a normal clone; its honest-boundary note records that no linked
worktrees exist), CR-stripped, blank lines ignored; an absent or empty
list disables the check, matching the guard's documented fail-open
bootstrap posture. Assertion messages carry line NUMBERS only, never
token values (guard precedent: file names and counts only).

This module is written to live at tests/test_probe_groq_env_tag_choices.py
and resolves the repository root relative to its own location.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PROBE = REPO / "probes" / "probe_groq.py"
TOKENS = REPO / ".git" / "sensitive-tokens"

NEW_TAGS = ("key-a", "key-b")
UNKNOWN_TAG = "not-a-real-tag"
NOT_IN_CHOICES = "key-c"


def run_probe(*args):
    """Run the probe script with list args (no shell). Offline by
    construction — see the module docstring's code-order guarantee.
    The timeout is a backstop only; it is not expected to fire."""
    return subprocess.run(
        [sys.executable, str(PROBE), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )


def load_tokens():
    """Read .git/sensitive-tokens with the guard's parsing semantics.

    Returns the token list, or None when the check is disabled (list
    absent, empty, or unreadable at test time) so callers can skip —
    the guard's own fail-open bootstrap posture. The guard's
    fail-CLOSED stance for an unreadable list is a commit-time concern
    and is not re-litigated here.
    """
    try:
        raw = TOKENS.read_text(encoding="utf-8")
    except OSError:
        return None
    tokens = [line.replace("\r", "") for line in raw.splitlines()]
    tokens = [t for t in tokens if t.strip()]
    return tokens or None


# --- --help: the new tags ARE the CLI surface ------------------------------


def test_help_succeeds_and_lists_both_new_tags():
    result = run_probe("--help")
    assert result.returncode == 0, result.stderr
    for tag in NEW_TAGS:
        assert tag in result.stdout, f"--help output does not mention {tag!r}"


def test_help_output_carries_no_configured_sensitive_tokens():
    """No line of .git/sensitive-tokens may appear in --help output.
    This is what catches a half-done rename — a retired label still
    sitting in the argparse choices (rendered into the usage line) —
    without this file ever spelling it."""
    tokens = load_tokens()
    if tokens is None:
        pytest.skip(
            "sensitive-tokens list absent/empty; check disabled "
            "(guard bootstrap precedent)"
        )
    result = run_probe("--help")
    assert result.returncode == 0, result.stderr
    for index, token in enumerate(tokens, start=1):
        # Deliberately no token value in the message (guard precedent:
        # counts only). The 1-based list-line index identifies the
        # offending entry for offline diagnosis.
        assert token not in result.stdout, (
            f".git/sensitive-tokens line {index} appears in the probe "
            f"--help output"
        )


# --- out-of-choices tags: argparse ends the process before anything else ---


def test_unknown_env_tag_rejected_by_argparse(tmp_path):
    """rc 2 is argparse's exit code for an invalid choice: the process
    ends inside parse_args (probe_groq.py:108). --env-file is supplied
    (a nonexistent path is fine — it is never read) so the invalid tag
    is the ONLY rejection cause."""
    result = run_probe(
        "--env-file", str(tmp_path / "irrelevant.env"),
        "--env-tag", UNKNOWN_TAG,
    )
    assert result.returncode == 2, result.stderr
    assert "invalid choice" in result.stderr


def test_key_c_rejected_choices_are_exactly_the_new_pair(tmp_path):
    """key-a and key-b are accepted (see below) and key-c is not, so
    the choices set is exactly {key-a, key-b}: no third label, and no
    retired label hiding as an extra accepted choice."""
    result = run_probe(
        "--env-file", str(tmp_path / "irrelevant.env"),
        "--env-tag", NOT_IN_CHOICES,
    )
    assert result.returncode == 2, result.stderr
    assert "invalid choice" in result.stderr


# --- valid tags: parser accepts them; execution stops at the loader --------


@pytest.mark.parametrize("tag", NEW_TAGS)
def test_valid_tag_accepted_past_argparse_to_credential_loader(tmp_path, tag):
    """A nonexistent --env-file makes load_credentials raise
    SystemExit("env file not found: <path>") (probe_common.py:38,
    called from probe_groq.py:114); CPython prints the message to
    stderr and exits with status 1. Reaching that message PROVES the
    parser accepted the tag (parse_args at line 108 passed) and
    execution proceeded to the credential loader. The SystemExit
    precedes client construction (line 116) and the first network
    request (line 122), so the run is offline by construction."""
    missing_env = tmp_path / "does-not-exist.env"
    result = run_probe("--env-file", str(missing_env), "--env-tag", tag)
    assert result.returncode == 1, (
        f"expected exit status 1 from SystemExit on the missing env "
        f"file, got rc={result.returncode}"
    )
    assert f"env file not found: {missing_env}" in result.stderr, result.stderr
