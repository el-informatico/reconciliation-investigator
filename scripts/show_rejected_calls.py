"""Demo-debugging viewer for runtime/rejected_calls.jsonl — every
rejected draft_correction/create_case_ticket call recorded by
tools/case_management.py (2026-09-06 diagnostics pass).

Read-only and pure standard library (the probes/ convention for small
Python diagnostics — scripts/ itself is otherwise the shell-only
enforcement surface): this script never writes, never imports
application code, and is not wired into any guard/verify/hook path.
The log it displays is observability only — no gate, executor, or
capability-token logic ever reads it (pinned by
tests/test_rejected_call_diagnostics.py).

Usage:
  uv run --locked python scripts/show_rejected_calls.py              # last 20
  uv run --locked python scripts/show_rejected_calls.py --all
  uv run --locked python scripts/show_rejected_calls.py --limit 5
  uv run --locked python scripts/show_rejected_calls.py --tool draft_correction
  uv run --locked python scripts/show_rejected_calls.py --json       # re-serialized
  uv run --locked python scripts/show_rejected_calls.py --runtime-dir /tmp/alt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME_DIR = REPO_ROOT / "runtime"
LOG_NAME = "rejected_calls.jsonl"


def _load(path: Path) -> list[dict]:
    entries = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            print(f"WARN: skipping unparseable line {lineno} of {path}", file=sys.stderr)
    return entries


def _show(entry: dict) -> None:
    print(f"{entry.get('timestamp', '?')}  {entry.get('component', '?')}  {entry.get('tool', '?')}")
    print(f"  reason: {entry.get('reason', '?')}")
    print(f"  args:   {json.dumps(entry.get('args', {}), ensure_ascii=False)}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show rejected draft_correction/create_case_ticket calls "
        "(read-only viewer; the log is written by tools/case_management.py)."
    )
    parser.add_argument(
        "--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR,
        help="runtime store directory (default: <repo>/runtime)",
    )
    parser.add_argument(
        "--limit", type=int, default=20, metavar="N",
        help="show the last N entries (default: 20)",
    )
    parser.add_argument("--all", action="store_true", help="show every entry")
    parser.add_argument(
        "--tool", choices=["draft_correction", "create_case_ticket"],
        help="only entries for this tool",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print re-serialized JSON objects instead of the summary",
    )
    args = parser.parse_args(argv)

    path = args.runtime_dir / LOG_NAME
    if not path.exists():
        print(f"no rejected calls logged ({path} does not exist)")
        return 0
    entries = _load(path)
    if args.tool:
        entries = [entry for entry in entries if entry.get("tool") == args.tool]
    if not entries:
        print(f"no rejected calls logged in {path}")
        return 0

    shown = entries if args.all or not (0 < args.limit < len(entries)) else entries[-args.limit:]
    header = f"{len(entries)} rejected call(s) in {path}"
    if len(shown) < len(entries):
        header += f" — showing the last {len(shown)}"
    print(header)
    print()
    if args.json:
        for entry in shown:
            print(json.dumps(entry, ensure_ascii=False))
    else:
        for entry in shown:
            _show(entry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
