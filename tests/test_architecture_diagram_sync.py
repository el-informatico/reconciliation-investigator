"""The README's architecture diagram and the canonical submission artifact
(docs/architecture-diagram-2026-09-06.md) carry the SAME mermaid block —
byte-identical — so the public README diagram and the hackathon submission
artifact cannot drift apart."""

import re
from pathlib import Path

README = Path("README.md").read_text(encoding="utf-8")
DIAGRAM_DOC = Path("docs/architecture-diagram-2026-09-06.md").read_text(
    encoding="utf-8"
)


def _mermaid_block(text: str, source: str) -> str:
    match = re.search(r"```mermaid\n(.*?)```", text, re.DOTALL)
    assert match, f"no ```mermaid fenced block found in {source}"
    return match.group(1)


def test_readme_and_diagram_doc_blocks_are_identical() -> None:
    readme_block = _mermaid_block(README, "README.md")
    doc_block = _mermaid_block(DIAGRAM_DOC, "docs/architecture-diagram-2026-09-06.md")
    assert readme_block == doc_block
