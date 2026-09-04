"""Nomination-order tests against the REAL Strands Graph engine with
fake executors (no model calls, no env vars) — the test class that would
have caught audit finding 1 (2026-09-04): a vacuously-True mirror edge
co-nominated the reporter with the first classifier batch, so the
reporter ran concurrently, never saw a verdict, invented its own
"classifier verdict", and §1's cap force-route was dead code."""

import json

from strands.agent.agent_result import AgentResult
from strands.agent.base import AgentBase
from strands.telemetry.metrics import EventLoopMetrics

from orchestrator.graph import (
    CLASSIFIER_NODE,
    DETECTOR_NODE,
    REPORTER_NODE,
    build_reconciliation_graph,
    verdict_from_result,
)


def _agent_result(text: str) -> AgentResult:
    """A minimal real AgentResult (the engine isinstance-checks node
    results when propagating inputs; anything else crashes
    get_agent_results)."""
    return AgentResult(
        stop_reason="end_turn",
        message={"role": "assistant", "content": [{"text": text}]},
        metrics=EventLoopMetrics(),
        state=None,
    )

CONFIDENT = json.dumps({
    "root_cause": "REVERSAL_NOT_PROPAGATED",
    "confidence": 0.92,
    "reasoning": "reversal in legacy only",
    "requires_correction": True,
})
LOW = json.dumps({
    "confidence": 0.4,
    "reasoning": "insufficient evidence",
    "investigation_hint": "widen the date range",
})


class FakeAgent(AgentBase):
    """AgentBase-shaped stub: records the input text it was invoked with
    and yields a canned result through the engine's streaming path."""

    def __init__(self, name: str, respond):
        self.name = name
        self.respond = respond
        self.inputs: list[str] = []

    async def stream_async(self, task, invocation_state=None, **kwargs):
        self.inputs.append(task if isinstance(task, str) else str(task))
        yield {"result": _agent_result(self.respond(self))}

    def __call__(self, task, **kwargs):
        return self.respond(self)


def _fake_builder(detector_text="EVIDENCE: reversal L-TXN-90002 in legacy only", classifier_outputs=None):
    """classifier_outputs: list of verdict JSON strings, consumed per call
    (last one repeats). Returns (node_builder, agents-by-name)."""
    classifier_outputs = classifier_outputs or [CONFIDENT]
    agents = {}

    def respond_classifier(agent):
        call = len(agent.inputs)
        return classifier_outputs[min(call - 1, len(classifier_outputs) - 1)]

    agents[DETECTOR_NODE] = FakeAgent(DETECTOR_NODE, lambda a: detector_text)
    agents[CLASSIFIER_NODE] = FakeAgent(CLASSIFIER_NODE, respond_classifier)
    agents[REPORTER_NODE] = FakeAgent(
        REPORTER_NODE, lambda a: "CASE FILE: root cause documented, correction drafted"
    )

    def node_builder(node_id):
        return agents[node_id]

    return node_builder, agents


def _run(builder):
    graph = build_reconciliation_graph(node_builder=builder)
    return graph("Investigate the flagged discrepancy for customer_id=C-1001")


def test_confident_case_reporter_runs_once_last_with_verdict_and_evidence() -> None:
    builder, agents = _fake_builder()
    result = _run(builder)
    order = [getattr(n, "node_id", str(n)) for n in result.execution_order]
    assert order.count(REPORTER_NODE) == 1, f"reporter ran {order.count(REPORTER_NODE)}x: {order}"
    assert order.index(CLASSIFIER_NODE) < order.index(REPORTER_NODE)
    reporter_input = agents[REPORTER_NODE].inputs[0]
    assert CONFIDENT in reporter_input, "reporter input missing the classifier verdict"
    assert "EVIDENCE" in reporter_input, "reporter input missing the detector evidence bundle"
    assert verdict_from_result(result)["root_cause"] == "REVERSAL_NOT_PROPAGATED"


def test_low_confidence_cycles_three_rounds_then_reporter_runs_once() -> None:
    builder, agents = _fake_builder(classifier_outputs=[LOW])
    result = _run(builder)
    order = [getattr(n, "node_id", str(n)) for n in result.execution_order]
    assert order.count(DETECTOR_NODE) == 3, f"detector rounds: {order.count(DETECTOR_NODE)} ({order})"
    assert order.count(CLASSIFIER_NODE) == 3
    assert order.count(REPORTER_NODE) == 1, f"reporter ran {order.count(REPORTER_NODE)}x: {order}"
    assert order.index(REPORTER_NODE) > order.index(CLASSIFIER_NODE)
    verdict = verdict_from_result(result)
    assert verdict["root_cause"] == "UNKNOWN"  # §1 cap force-route, now alive
    assert verdict.get("capped") is True


def test_reinvocation_hint_reaches_the_detector() -> None:
    builder, agents = _fake_builder(classifier_outputs=[LOW])
    _run(builder)
    # Second+ detector invocations must carry the classifier's hint (the
    # propagated input contains the low-confidence JSON with the hint).
    later_inputs = agents[DETECTOR_NODE].inputs[1:]
    assert later_inputs, "detector never re-invoked"
    assert all("investigation_hint" in text for text in later_inputs)


def test_reporter_never_sees_only_evidence_without_verdict() -> None:
    # Regression for the exact finding-1 mechanism: if the mirror edge is
    # vacuously True pre-classifier, the reporter input has evidence but
    # NO verdict JSON. Assert the invariant directly.
    builder, agents = _fake_builder()
    _run(builder)
    for text in agents[REPORTER_NODE].inputs:
        assert "root_cause" in text, "reporter invoked without a classifier verdict in its input"
