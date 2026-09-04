"""AC4 (routing half): §1 topology semantics as pure-function tests over
fabricated graph states — no model calls. The conditions under test are
the exact functions wired into build_reconciliation_graph."""

from types import SimpleNamespace

from orchestrator.graph import (
    CONFIDENCE_THRESHOLD,
    MAX_INVESTIGATION_ROUNDS,
    detector_rounds_in_result,
    edge_classifier_to_detector,
    edge_classifier_to_reporter,
    edge_detector_to_classifier,
    edge_detector_to_reporter,
    extract_json_object,
    verdict_from_result,
    verdict_from_state,
)


def state(verdict_json: str | None, detector_rounds: int):
    execution_order = []
    for _ in range(detector_rounds):
        execution_order.append(SimpleNamespace(node_id="detector_investigator"))
        execution_order.append(SimpleNamespace(node_id="classifier"))
    results = {}
    if verdict_json is not None:
        results["classifier"] = SimpleNamespace(result=verdict_json)
    return SimpleNamespace(execution_order=execution_order, results=results)


CONFIDENT = '{"root_cause": "REVERSAL_NOT_PROPAGATED", "confidence": 0.92, "reasoning": "r", "requires_correction": true}'
LOW = '{"root_cause": null, "confidence": 0.5, "reasoning": "r", "requires_correction": null, "investigation_hint": "widen the date range"}'


def test_confident_verdict_routes_to_reporter_not_back() -> None:
    s = state(CONFIDENT, detector_rounds=1)
    assert edge_classifier_to_reporter(s) is True
    assert edge_classifier_to_detector(s) is False


def test_low_confidence_under_cap_cycles_back() -> None:
    s = state(LOW, detector_rounds=1)
    assert edge_classifier_to_detector(s) is True
    assert edge_classifier_to_reporter(s) is False


def test_low_confidence_at_cap_force_routes_to_reporter() -> None:
    s = state(LOW, detector_rounds=MAX_INVESTIGATION_ROUNDS)
    assert edge_classifier_to_detector(s) is False
    assert edge_classifier_to_reporter(s) is True


def test_unparseable_verdict_routes_to_reporter_never_loops() -> None:
    s = state("the classifier rambled without json", detector_rounds=1)
    assert edge_classifier_to_detector(s) is False
    assert edge_classifier_to_reporter(s) is True


def test_missing_classifier_result_routes_to_reporter() -> None:
    s = state(None, detector_rounds=1)
    assert edge_classifier_to_detector(s) is False
    assert edge_classifier_to_reporter(s) is True


def test_verdict_from_result_normalizes_capped_low_confidence_to_unknown() -> None:
    result = state(LOW, detector_rounds=MAX_INVESTIGATION_ROUNDS)
    verdict = verdict_from_result(result)
    assert verdict["root_cause"] == "UNKNOWN"
    assert verdict.get("capped") is True
    assert detector_rounds_in_result(result) == MAX_INVESTIGATION_ROUNDS


def test_verdict_from_result_keeps_a_confident_verdict_untouched() -> None:
    result = state(CONFIDENT, detector_rounds=MAX_INVESTIGATION_ROUNDS)
    verdict = verdict_from_result(result)
    assert verdict["root_cause"] == "REVERSAL_NOT_PROPAGATED"
    assert "capped" not in verdict


def test_extract_json_object_handles_prose_nesting_and_strings() -> None:
    assert extract_json_object('prose before {"a": 1} prose after') == {"a": 1}
    assert extract_json_object('{"outer": {"inner": 2}, "s": "brace } inside"}') == {
        "outer": {"inner": 2},
        "s": "brace } inside",
    }
    assert extract_json_object("no json here") is None
    assert extract_json_object('{"broken": ') is None


def test_extract_json_object_multiple_objects_and_failed_first_candidate() -> None:
    # Reviewer-mandated (audit finding 2): multiple objects — first valid
    # one wins; an unparseable first candidate is skipped, scanning
    # resumes at the next object rather than returning None.
    assert extract_json_object('first {"a": 1} then {"b": 2}') == {"a": 1}
    assert extract_json_object('oops {"a": unquoted junk} then {"b": 2}') == {"b": 2}
    assert extract_json_object('only {"a": unquoted junk} here') is None
    # A brace inside a quoted string is never treated as an object start.
    assert extract_json_object('illustration "{"field": "balance"}" — verdict: {"root_cause": "SYNC_LAG"}') == {
        "root_cause": "SYNC_LAG"
    }


def test_threshold_is_the_contracted_value() -> None:
    assert CONFIDENCE_THRESHOLD == 0.7
    assert MAX_INVESTIGATION_ROUNDS == 3


# --- re-execution guards (added after the first real eval run: the
# engine re-nominates on satisfied conditions, running the reporter
# twice per case — two tickets — until these guards landed) ---


def reporter_done_state():
    s = state(CONFIDENT, detector_rounds=1)
    s.completed_nodes = [
        SimpleNamespace(node_id="detector_investigator"),
        SimpleNamespace(node_id="classifier"),
        SimpleNamespace(node_id="reporter"),
    ]
    return s


def test_reporter_edges_never_fire_once_reporter_completed() -> None:
    s = reporter_done_state()
    assert edge_classifier_to_reporter(s) is False
    assert edge_detector_to_reporter(s) is False


def test_reporter_edges_fire_before_reporter_has_run() -> None:
    s = state(CONFIDENT, detector_rounds=1)
    s.completed_nodes = [
        SimpleNamespace(node_id="detector_investigator"),
        SimpleNamespace(node_id="classifier"),
    ]
    assert edge_classifier_to_reporter(s) is True
    assert edge_detector_to_reporter(s) is True


def test_detector_to_classifier_gated_by_cycle_budget() -> None:
    assert edge_detector_to_classifier(state(CONFIDENT, detector_rounds=1)) is True
    assert edge_detector_to_classifier(state(CONFIDENT, detector_rounds=MAX_INVESTIGATION_ROUNDS)) is False
