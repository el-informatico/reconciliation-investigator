"""Strands Graph wiring per docs/build-contract.md §1 (cyclic topology).

Topology: detector_investigator -> classifier -> {reporter | back to
detector_investigator}. The classifier->reporter edge fires when the
verdict confidence >= 0.7 OR the autonomous investigation cycle has run
MAX_INVESTIGATION_ROUNDS rounds (then the orchestrator-level verdict is
normalized to root_cause UNKNOWN — the installed Graph API (verified
against source, strands-agents 1.54.0) routes by per-edge boolean
conditions and provides no input-mutation point, so the UNKNOWN
normalization is applied at the verdict layer this module exposes; the
in-graph reporter input carries the classifier's raw output).

Verified API facts this wiring relies on (2026-09-04, installed source):
- nodes are Agent instances; add_edge(from, to, condition) with
  conditions returning bool over GraphState;
- a node is ready when ANY incoming edge condition is satisfied, AND a
  satisfied condition re-nominates its target on later batch scans —
  stateless True conditions therefore re-execute nodes (observed live
  2026-09-04: the reporter ran twice per case until every edge into it
  gained an execution-state guard). The detector->reporter edge mirrors
  the classifier->reporter predicate (identical functions cannot
  diverge) to give the reporter BOTH the evidence bundle and the
  verdict in its propagated input (input propagation is
  direct-edges-only);
- reset_on_revisit defaults to False, so the detector keeps its prior
  conversation (evidence bundle) across cycle rounds — §2.1's "append to
  the existing bundle" depends on this;
- GraphBuilder.build() does not forward trace_attributes: they are set
  on each Agent node instead (tagging every node also keeps the eval
  mapper's session-id filtering consistent).

human_gate and correction_executor are NOT graph nodes: §1 makes them
orchestrator-level deterministic steps (human_gate.py,
correction_executor.py), composed after the graph run by
run_case_with_gate().
"""

from __future__ import annotations

import json
from typing import Any

from strands.multiagent import GraphBuilder
from strands.multiagent.graph import Graph

from agents.classifier import build_classifier
from agents.detector_investigator import build_detector_investigator
from agents.reporter import build_reporter

DETECTOR_NODE = "detector_investigator"
CLASSIFIER_NODE = "classifier"
REPORTER_NODE = "reporter"

# §1: safety limit on the detector<->classifier cycle. This bounds the
# AUTONOMOUS low-confidence loop only — human REQUEST_MORE_INFO
# re-entries do not consume rounds (recorded decision; every re-entry is
# audit-logged by human_gate).
MAX_INVESTIGATION_ROUNDS = 3

CONFIDENCE_THRESHOLD = 0.7

# Hard backstops: 3 rounds x (detector + classifier) + reporter = 7
# executions; 8 leaves headroom. Total wall-clock backstop per run.
MAX_NODE_EXECUTIONS = 8
EXECUTION_TIMEOUT_SECONDS = 1200


def extract_json_object(text: str) -> dict[str, Any] | None:
    """First balanced {...} object in text (quote-aware); None if absent."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def _node_ids(state: Any) -> list[str]:
    return [getattr(node, "node_id", str(node)) for node in getattr(state, "execution_order", [])]


def detector_rounds_completed(state: Any) -> int:
    return _node_ids(state).count(DETECTOR_NODE)


def verdict_from_state(state: Any) -> dict[str, Any] | None:
    """Parse the classifier verdict out of a GraphState (or a fabricated
    test state); None when the classifier has not run or its output is
    unparseable (treated as route-to-reporter: never proceed silently)."""
    results = getattr(state, "results", {})
    node_result = results.get(CLASSIFIER_NODE)
    if node_result is None:
        return None
    agent_result = getattr(node_result, "result", None)
    if agent_result is None:
        return None
    return extract_json_object(str(agent_result))


def _cycle_should_continue(state: Any) -> bool:
    verdict = verdict_from_state(state)
    if verdict is None:
        return False
    try:
        confidence = float(verdict.get("confidence", 0.0))
    except (TypeError, ValueError):
        return False
    return (
        confidence < CONFIDENCE_THRESHOLD
        and detector_rounds_completed(state) < MAX_INVESTIGATION_ROUNDS
    )


def _reporter_completed(state: Any) -> bool:
    completed = getattr(state, "completed_nodes", None)
    if completed is None:
        # Fabricated test states may carry only execution_order.
        return REPORTER_NODE in _node_ids(state)
    return any(getattr(node, "node_id", str(node)) == REPORTER_NODE for node in completed)


def _classifier_rounds(state: Any) -> int:
    return _node_ids(state).count(CLASSIFIER_NODE)


def edge_classifier_to_detector(state: Any) -> bool:
    """§1: confidence < 0.7 -> cycle back to detector_investigator
    (the classifier output — carrying investigation_hint — propagates as
    the detector's new input)."""
    return _cycle_should_continue(state)


def edge_classifier_to_reporter(state: Any) -> bool:
    """§1: confidence >= 0.7, OR the cycle cap was reached (force-route);
    an unparseable verdict also routes here rather than looping. Guarded
    against re-execution: the engine re-nominates a node whenever an
    incoming edge condition is satisfied on a later batch scan, so a
    stateless True here ran the reporter TWICE per case in the first
    real eval run (two tickets per case — caught by the SDK's tool
    judges 2026-09-04). Once the reporter has completed, no edge into it
    may fire again."""
    return not _cycle_should_continue(state) and not _reporter_completed(state)


def edge_detector_to_reporter(state: Any) -> bool:
    """Mirror of edge_classifier_to_reporter: exists only so the
    reporter's propagated input includes the evidence bundle (input
    propagation is direct-edges-only in the installed API). Same
    re-execution guard."""
    return edge_classifier_to_reporter(state)


def edge_detector_to_classifier(state: Any) -> bool:
    """Advance to the classifier only while cycle budget remains: the
    unconditional form re-nominated the classifier on later batch scans
    after the final verdict, wasting a model call past the cap."""
    return _classifier_rounds(state) < MAX_INVESTIGATION_ROUNDS


def build_reconciliation_graph(trace_attributes: dict | None = None) -> Graph:
    """Build the §1 graph. trace_attributes are applied to EVERY agent
    node (the builder cannot set them graph-wide; tagging all nodes keeps
    the eval session mapper's filtering consistent)."""
    builder = GraphBuilder()
    builder.add_node(
        build_detector_investigator(trace_attributes=trace_attributes),
        node_id=DETECTOR_NODE,
    )
    builder.add_node(build_classifier(trace_attributes=trace_attributes), node_id=CLASSIFIER_NODE)
    builder.add_node(build_reporter(trace_attributes=trace_attributes), node_id=REPORTER_NODE)

    builder.add_edge(DETECTOR_NODE, CLASSIFIER_NODE, condition=edge_detector_to_classifier)
    builder.add_edge(CLASSIFIER_NODE, DETECTOR_NODE, condition=edge_classifier_to_detector)
    builder.add_edge(CLASSIFIER_NODE, REPORTER_NODE, condition=edge_classifier_to_reporter)
    builder.add_edge(DETECTOR_NODE, REPORTER_NODE, condition=edge_detector_to_reporter)

    builder.set_entry_point(DETECTOR_NODE)
    builder.set_max_node_executions(MAX_NODE_EXECUTIONS)
    builder.set_execution_timeout(EXECUTION_TIMEOUT_SECONDS)
    return builder.build()


def detector_rounds_in_result(result: Any) -> int:
    return [getattr(node, "node_id", str(node)) for node in getattr(result, "execution_order", [])].count(
        DETECTOR_NODE
    )


def verdict_from_result(result: Any) -> dict[str, Any]:
    """Classifier verdict after a completed run, with §1's UNKNOWN
    normalization: when the cap was reached without confidence >= 0.7,
    root_cause is forced to UNKNOWN at this (orchestrator verdict)
    layer."""
    verdict = verdict_from_state(result) or {}
    confidence = verdict.get("confidence", 0.0)
    try:
        low = float(confidence) < CONFIDENCE_THRESHOLD
    except (TypeError, ValueError):
        low = True
    capped = detector_rounds_in_result(result) >= MAX_INVESTIGATION_ROUNDS
    if capped and low:
        verdict = dict(verdict)
        verdict["root_cause"] = "UNKNOWN"
        verdict["confidence"] = float(confidence) if isinstance(confidence, (int, float)) else 0.0
        verdict["capped"] = True
    return verdict


# Safety stop for HUMAN-driven re-invocation rounds only (§2.4
# REQUEST_MORE_INFO). Deliberately distinct from §1's autonomous-cycle
# cap: human rounds do not consume MAX_INVESTIGATION_ROUNDS (recorded
# decision, audited per round) — this bound just keeps a runaway
# decide() loop from spinning forever in the demo path.
MAX_HUMAN_ROUNDS = 5


def run_case_with_gate(
    instruction: str,
    *,
    case_id: str,
    decide,
    trace_attributes: dict | None = None,
    build_graph=None,
) -> dict:
    """Run the §1 graph, then the deterministic §2.4/§2.5 path.

    decide(case_file_text, correction_draft_or_None) -> GateDecision.
    APPROVE -> issue the scoped token and execute the correction via the
    executor (the system's only apply path). REJECT -> ticket closed as
    rejected. REQUEST_MORE_INFO -> re-invoke the graph with the human's
    note as investigation_hint (the same propagation the §1 cycle uses).
    Returns the final graph result, normalized verdict, and gate/executor
    outcome — the single entry point the approval UI composes with.
    """
    from orchestrator import correction_executor
    from orchestrator.human_gate import (
        GateAction,
        latest_pending_draft,
        latest_ticket,
        run_human_gate,
    )

    graph_factory = build_graph or build_reconciliation_graph
    result = graph_factory(trace_attributes=trace_attributes)(instruction)
    outcome: dict = {}
    for _ in range(MAX_HUMAN_ROUNDS):
        verdict = verdict_from_result(result)
        draft = latest_pending_draft(case_id)
        case_file = str(getattr(getattr(result, "results", {}).get(REPORTER_NODE), "result", ""))
        gate = run_human_gate(case_file, draft, decide(case_file, draft))
        outcome = gate
        if gate["action"] is GateAction.REQUEST_MORE_INFO:
            # §2.4: route back with the human's note as the hint. The
            # detector sees the hint through the same input-propagation
            # mechanism the low-confidence cycle uses (§2.1 re-invocation).
            result = graph_factory(trace_attributes=trace_attributes)(
                f"{instruction}\n\ninvestigation_hint: {gate['investigation_hint']}"
            )
            continue
        if gate["action"] is GateAction.APPROVE and verdict.get("requires_correction"):
            ticket = latest_ticket(case_id) or {}
            executed = correction_executor.execute_correction(
                gate["approval_token"],
                case_id=case_id,
                field=draft["field"],
                new_value=draft["proposed_value"],
                ticket_id=ticket.get("ticket_id", ""),
                approver="human",
            )
            outcome = {"gate": gate, "correction": executed}
        break
    return {"result": result, "verdict": verdict_from_result(result), "outcome": outcome}
