"""2026-09-06 sensitive-content guard regression tests: the three
weaknesses found by the cde3e6f push-verification pass must not return,
and the behaviors that were already correct must stay correct.

Every test runs against a THROWAWAY git repository under pytest's
tmp_path — the real repository is never modified (the only real-repo
operation is the read-only `git check-ignore` of the tracked
.gitignore), and only a SYNTHETIC token is ever staged, so no raw
sensitive string enters any file or object store.

Covered:
- guard scans added diff lines whose payload itself begins with '+'
  (content "++ <token>" reaches the diff as "+++ <token>", exactly
  file-header-shaped; the old awk skipped any '^+++ ' line and missed
  it) — the '++'-prefix blind spot, fixed by taking added lines from
  inside the hunks only (everything after the first @@);
- commit-msg AND the guard fail CLOSED (exit 2) when the token list
  exists but is not a readable regular file (chmod 000, a directory at
  the path, a dangling symlink) — the old commit-msg failed OPEN
  there, contradicting CONTRIBUTING.md's "present but unreadable =
  commit refused (fail closed)";
- both still fail OPEN when the list is absent or empty (bootstrap
  precedent per the ares-launch.sh governor), and commit-msg still
  blocks token-bearing and AI-attribution messages;
- the guard stays added-lines-only: REMOVING a token line never trips
  it (frozen-evidence viability, D-2026-09-05-01);
- the .gitignore class globs match the REAL relocated filename shapes
  — including the backup-chain class, whose real name carries NO
  leading prefix (the old '*-backup-chain-...' glob never matched it)
  — while legitimate repo files stay unignored.

Out of scope by design (documented accepted boundary, unchanged):
binary staged content is not scanned — git emits no content lines for
it (guard-sensitive-content.sh header, HONEST BOUNDARY).
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / "scripts" / "guard-sensitive-content.sh"
COMMIT_MSG = REPO / "scripts" / "hooks" / "commit-msg"
SYNTH_TOKEN = "ZZTOKEN-synthetic-regression-XYZ"

CLEAN_MSG = "Fix the thing\n\nPlain body, no attribution, no tokens.\n"
TOKEN_MSG = f"Mentions {SYNTH_TOKEN} in the body\n"
ATTRIBUTION_MSG = (
    "Subject\n\nCo-Authored-By: Claude <noreply@example.com>\n"
)


def _run(args, cwd, **kwargs):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, **kwargs)


def _git(repo, *args):
    return _run(["git", "-C", str(repo), *args], repo)


def make_repo(tmp_path, tokens=None, tokens_mode="file"):
    """A throwaway repo with an optional sensitive-tokens fixture.

    tokens_mode: "file" (regular readable file — the normal case),
    "dir" (a directory at the path — unreadable AS A LIST for any
    user, so the test never depends on not being root), "dangling"
    (a symlink pointing at a nonexistent target).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "agent-memory").mkdir()  # guard audit-log target (*.log-ignored)
    if tokens is not None:
        target = repo / ".git" / "sensitive-tokens"
        if tokens_mode == "file":
            target.write_text("".join(t + "\n" for t in tokens))
        elif tokens_mode == "dir":
            target.mkdir()
        elif tokens_mode == "dangling":
            target.symlink_to(str(tmp_path / "no-such-target"))
        else:  # pragma: no cover - programming error, not a case under test
            raise ValueError(tokens_mode)
    return repo


def make_unreadable_tokens(repo):
    target = repo / ".git" / "sensitive-tokens"
    target.write_text(SYNTH_TOKEN + "\n")
    target.chmod(0o000)


def stage(repo, name, text):
    (repo / name).write_text(text)
    assert _git(repo, "add", name).returncode == 0


def commit_all(repo, message):
    assert _git(
        repo,
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=test",
        "commit",
        "-q",
        "-m",
        message,
    ).returncode == 0


def run_guard(repo):
    return _run(["bash", str(GUARD)], repo)


def run_commit_msg(repo, message):
    msg = repo / "COMMIT_MSG_TEST"
    msg.write_text(message)
    return _run(["bash", str(COMMIT_MSG), str(msg)], repo)


# --- guard: the '++'-prefix blind spot (B3) -------------------------------


def test_guard_blocks_token_on_header_shaped_added_line(tmp_path):
    """Content '++ <token>' diffs as '+++ <token>' — old awk skipped it
    as a file header; the hunk-aware filter must scan it."""
    repo = make_repo(tmp_path, tokens=[SYNTH_TOKEN])
    stage(repo, "quoted-diff.md", f"intro\n++ {SYNTH_TOKEN}\noutro\n")
    result = run_guard(repo)
    assert result.returncode == 1, result.stderr


def test_guard_blocks_token_on_single_plus_prefixed_content(tmp_path):
    """Content '+ <token>' diffs as '++ <token>' — worked before the
    fix via the '^+' branch; must keep working after it."""
    repo = make_repo(tmp_path, tokens=[SYNTH_TOKEN])
    stage(repo, "quoted-diff.md", f"intro\n+ {SYNTH_TOKEN}\noutro\n")
    result = run_guard(repo)
    assert result.returncode == 1, result.stderr


def test_guard_passes_clean_staged_file(tmp_path):
    repo = make_repo(tmp_path, tokens=[SYNTH_TOKEN])
    stage(repo, "clean.md", "nothing sensitive here\n")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr


def test_guard_ignores_removed_token_lines(tmp_path):
    """Added-lines-only invariant: deleting a token-bearing line is a
    REDUCTION of sensitive content and must never block the commit
    (frozen-evidence viability, D-2026-09-05-01)."""
    repo = make_repo(tmp_path, tokens=[SYNTH_TOKEN])
    stage(repo, "history.md", f"old line\n{SYNTH_TOKEN}\n")
    commit_all(repo, "seed the token line")
    (repo / "history.md").write_text("old line\n")
    assert _git(repo, "add", "history.md").returncode == 0
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr


# --- guard: fail-closed ladder for the token list (B1 parity) --------------


def test_guard_fails_closed_when_tokens_path_is_a_directory(tmp_path):
    repo = make_repo(tmp_path, tokens=["unused"], tokens_mode="dir")
    stage(repo, "clean.md", "clean content\n")
    result = run_guard(repo)
    assert result.returncode == 2, result.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads through chmod 000")
def test_guard_fails_closed_when_tokens_file_unreadable(tmp_path):
    repo = make_repo(tmp_path, tokens=[SYNTH_TOKEN])
    make_unreadable_tokens(repo)
    stage(repo, "clean.md", "clean content\n")
    result = run_guard(repo)
    assert result.returncode == 2, result.stderr


def test_guard_disabled_when_tokens_absent(tmp_path):
    repo = make_repo(tmp_path, tokens=None)
    stage(repo, "clean.md", f"even {SYNTH_TOKEN} would pass: check disabled\n")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr


def test_guard_disabled_when_tokens_empty(tmp_path):
    repo = make_repo(tmp_path, tokens=[""])
    stage(repo, "clean.md", f"even {SYNTH_TOKEN} would pass: check disabled\n")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr


# --- commit-msg: fail-closed on unreadable list (B1) -----------------------


def test_commit_msg_fails_closed_when_tokens_path_is_a_directory(tmp_path):
    repo = make_repo(tmp_path, tokens=["unused"], tokens_mode="dir")
    result = run_commit_msg(repo, CLEAN_MSG)
    assert result.returncode == 2, result.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads through chmod 000")
def test_commit_msg_fails_closed_when_tokens_file_unreadable(tmp_path):
    repo = make_repo(tmp_path, tokens=[SYNTH_TOKEN])
    make_unreadable_tokens(repo)
    result = run_commit_msg(repo, CLEAN_MSG)
    assert result.returncode == 2, result.stderr


def test_commit_msg_fails_closed_when_tokens_is_dangling_symlink(tmp_path):
    repo = make_repo(tmp_path, tokens=["unused"], tokens_mode="dangling")
    result = run_commit_msg(repo, CLEAN_MSG)
    assert result.returncode == 2, result.stderr


# --- commit-msg: preserved fail-open bootstrap + blocking behavior ----------


def test_commit_msg_passes_clean_message(tmp_path):
    repo = make_repo(tmp_path, tokens=[SYNTH_TOKEN])
    result = run_commit_msg(repo, CLEAN_MSG)
    assert result.returncode == 0, result.stderr


def test_commit_msg_fail_open_when_tokens_absent(tmp_path):
    """Absent list = check disabled (bootstrap precedent, CONTRIBUTING.md):
    even a token-bearing message passes — freeze the documented intent."""
    repo = make_repo(tmp_path, tokens=None)
    result = run_commit_msg(repo, TOKEN_MSG)
    assert result.returncode == 0, result.stderr


def test_commit_msg_disabled_when_tokens_empty(tmp_path):
    repo = make_repo(tmp_path, tokens=[""])
    result = run_commit_msg(repo, TOKEN_MSG)
    assert result.returncode == 0, result.stderr


def test_commit_msg_blocks_token_in_message(tmp_path):
    repo = make_repo(tmp_path, tokens=[SYNTH_TOKEN])
    result = run_commit_msg(repo, TOKEN_MSG)
    assert result.returncode == 1, result.stderr


def test_commit_msg_blocks_ai_attribution(tmp_path):
    """Pre-existing gate (D-2026-09-06-01) must survive the token-check
    restructure untouched."""
    repo = make_repo(tmp_path, tokens=None)
    result = run_commit_msg(repo, ATTRIBUTION_MSG)
    assert result.returncode == 1, result.stderr


# --- .gitignore class globs vs the real relocated names (B2) ----------------


@pytest.mark.parametrize(
    "path",
    [
        # the three REAL relocated filename shapes (two carry a leading
        # project-area prefix; the backup-chain one carries NONE)
        "docs/agent-memory-privacy-audit-2026-09-06.md",
        "docs/agent-memory-rewrite-execution-plan-2026-09-06.md",
        "docs/backup-chain-investigation-2026-09-06.md",
        "agent-memory/agent-memory-privacy-audit-2026-09-06.md",
        "agent-memory/agent-memory-rewrite-execution-plan-2026-09-06.md",
        "agent-memory/backup-chain-investigation-2026-09-06.md",
        # future dated files of the same classes, prefixed and unprefixed
        "docs/privacy-audit-2099-01-01.md",
        "docs/rewrite-execution-plan-2099-01-01.md",
        "docs/backup-chain-investigation-2099-01-01.md",
        "agent-memory/backup-chain-investigation-2099-01-01.md",
        # the wholesale rule (2026-09-07 history-excision follow-up):
        # agent-memory/ is local-only — ordinary ledger/report files under
        # it are deliberately ignored too, superseding the old "class
        # patterns must not swallow them" expectation
        "agent-memory/decisions.md",
        "agent-memory/sensitive-docs-relocation-2026-09-06.md",
    ],
)
def test_gitignore_covers_relocated_name_classes(path):
    # excludesFile pinned so a machine-global ignore file cannot
    # satisfy (or break) the assertion — the REPO .gitignore is the
    # artifact under test.
    result = _run(
        ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "-q", "--", path],
        REPO,
    )
    assert result.returncode == 0, f"{path} is NOT ignored (rc={result.returncode})"


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "CONTRIBUTING.md",
        "docs/SENSITIVE-PLANNING-DOCS-RELOCATED.md",
        "docs/SYSTEM-REFERENCE.md",
        "docs/local-path-ai-reference-audit-and-commit-2026-09-06.md",
        # agent-memory/* entries were removed 2026-09-07: the wholesale
        # `agent-memory/` rule (history-excision follow-up) deliberately
        # ignores the entire directory — those paths now belong to the
        # IGNORED expectation in test_gitignore_covers_relocated_name_classes.
    ],
)
def test_gitignore_does_not_swallow_legitimate_files(path):
    result = _run(
        ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "-q", "--", path],
        REPO,
    )
    assert result.returncode == 1, f"{path} is wrongly ignored"
