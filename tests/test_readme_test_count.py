"""The README's repo-structure block states how many offline test files
tests/ holds. That number drifted once (2026-09-09: README said 20, tests/
had 21), so it is now pinned the same way the architecture diagram is:
the count stays in the README (readers use it) and this test fails the
suite the moment the two disagree."""

import re
from pathlib import Path

README = Path("README.md").read_text(encoding="utf-8")

COUNT_PATTERN = re.compile(r"# (\d+) offline test files")


def test_readme_offline_test_file_count_matches_reality() -> None:
    test_files = sorted(p.name for p in Path("tests").glob("test_*.py"))
    match = COUNT_PATTERN.search(README)
    assert match, (
        "README.md no longer states '# <N> offline test files' in the "
        "repo-structure block — either restore the count (this test keeps "
        "it honest) or retire both the count and this test together, "
        "deliberately"
    )
    stated = int(match.group(1))
    assert stated == len(test_files), (
        f"README says {stated} offline test files but tests/ holds "
        f"{len(test_files)}: {test_files} — update README.md (and "
        "docs/EVALUATION.md §9's suite count) in the same change"
    )
