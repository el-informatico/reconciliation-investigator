"""AC3: agent system prompts byte-match build-contract §2.1-2.3 and the
tool registration sets are exactly as prescribed — and NEVER include the
correction write tool (§4)."""

import re
from pathlib import Path

from agents.classifier import CLASSIFIER_SYSTEM_PROMPT, build_classifier
from agents.detector_investigator import (
    DETECTOR_INVESTIGATOR_SYSTEM_PROMPT,
    build_detector_investigator,
)
from agents.reporter import REPORTER_SYSTEM_PROMPT, build_reporter

CONTRACT = Path("docs/build-contract.md").read_text(encoding="utf-8")


class DummyModel:
    """No API calls: building an Agent only touches model.stateful."""

    stateful = False


def _fenced_section(heading_pattern: str) -> str:
    match = re.search(rf"{heading_pattern}.*?```(.*?)```", CONTRACT, re.DOTALL)
    assert match, f"section {heading_pattern!r} not found in build-contract.md"
    return match.group(1)


def test_detector_prompt_is_verbatim_from_contract() -> None:
    fenced = _fenced_section(r"### 2\.1 `detector_investigator`")
    assert fenced == "\n" + DETECTOR_INVESTIGATOR_SYSTEM_PROMPT + "\n"


def test_classifier_prompt_is_verbatim_from_contract() -> None:
    fenced = _fenced_section(r"### 2\.2 `classifier`")
    assert fenced == "\n" + CLASSIFIER_SYSTEM_PROMPT + "\n"


def test_reporter_prompt_is_verbatim_from_contract() -> None:
    fenced = _fenced_section(r"### 2\.3 `reporter`")
    assert fenced == "\n" + REPORTER_SYSTEM_PROMPT + "\n"


def test_detector_registers_exactly_the_four_read_tools() -> None:
    agent = build_detector_investigator(model=DummyModel())
    assert sorted(agent.tool_names) == [
        "get_event_log",
        "read_legacy_system",
        "read_modern_system",
        "search_transactions",
    ]
    assert "apply_correction" not in agent.tool_names


def test_classifier_registers_no_tools() -> None:
    agent = build_classifier(model=DummyModel())
    assert agent.tool_names == []


def test_reporter_registers_exactly_the_two_draft_tools() -> None:
    agent = build_reporter(model=DummyModel())
    assert sorted(agent.tool_names) == ["create_case_ticket", "draft_correction"]
    assert "apply_correction" not in agent.tool_names
