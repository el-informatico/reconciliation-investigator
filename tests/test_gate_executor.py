"""AC4 (gate/executor half): §2.4 human_gate and §2.5 correction_executor
— token matrix (scope, single-use, expiry, FORGED signature), audit
entries with real before/after, ticket state transitions, seed
immutability, and the §2.4 decision routing through run_case_with_gate
with a stubbed graph (no model calls)."""

import hashlib
import json
from types import SimpleNamespace

import pytest

import tools.seed_data as seed_data
from orchestrator.correction_executor import execute_correction
from orchestrator.graph import run_case_with_gate
from orchestrator.human_gate import (
    EVAL_MODE_DEV_KEY,
    GateAction,
    GateDecision,
    issue_approval_token,
    run_human_gate,
    validate_approval_token,
)
from tools.case_management import create_case_ticket, draft_correction

SEED = seed_data.SEED_PATH


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_MODE", "1")
    monkeypatch.setattr(seed_data, "RUNTIME_DIR", tmp_path)
    return tmp_path


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _issue(case_id="C-1001", field="balance", value=1250.00):
    return issue_approval_token(case_id, field, value)


# --- token matrix (§2.4: case-scoped, correction-scoped, single-use) ---


def test_token_happy_path_validates() -> None:
    ok, reason = validate_approval_token(_issue(), case_id="C-1001", field="balance", new_value=1250.00)
    assert ok, reason


def test_token_wrong_case_id_rejected() -> None:
    ok, reason = validate_approval_token(_issue(), case_id="C-1002", field="balance", new_value=1250.00)
    assert not ok and "case" in reason


def test_token_wrong_field_rejected() -> None:
    ok, reason = validate_approval_token(_issue(), case_id="C-1001", field="status", new_value=1250.00)
    assert not ok and "field" in reason


def test_token_wrong_value_rejected() -> None:
    ok, reason = validate_approval_token(_issue(), case_id="C-1001", field="balance", new_value=999.00)
    assert not ok and "value" in reason


def test_token_forged_signature_rejected() -> None:
    token = _issue()
    body, _ = token.split(".")
    forged = f"{body}.{'0' * 64}"
    ok, reason = validate_approval_token(forged, case_id="C-1001", field="balance", new_value=1250.00)
    assert not ok and "signature" in reason


def test_token_tampered_payload_rejected() -> None:
    import base64

    body, signature = _issue().split(".")
    payload = json.loads(base64.urlsafe_b64decode(body.encode()))
    payload["new_value"] = 1_000_000.00  # escalate the amount
    tampered_body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    ok, reason = validate_approval_token(
        f"{tampered_body}.{signature}", case_id="C-1001", field="balance", new_value=1_000_000.00
    )
    assert not ok and "signature" in reason


def test_token_expired_rejected() -> None:
    token = issue_approval_token("C-1001", "balance", 1250.00, ttl_seconds=-1)
    ok, reason = validate_approval_token(token, case_id="C-1001", field="balance", new_value=1250.00)
    assert not ok and "expired" in reason


def test_token_single_use_second_consume_rejected() -> None:
    token = _issue()
    ok, _ = validate_approval_token(token, case_id="C-1001", field="balance", new_value=1250.00)
    assert ok
    ok, reason = validate_approval_token(token, case_id="C-1001", field="balance", new_value=1250.00)
    assert not ok and "consumed" in reason


def test_production_key_required_outside_eval_mode(monkeypatch) -> None:
    monkeypatch.delenv("EVAL_MODE", raising=False)
    monkeypatch.delenv("CORRECTION_TOKEN_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="CORRECTION_TOKEN_SECRET"):
        issue_approval_token("C-1001", "balance", 1.0)


def test_eval_mode_key_is_a_committed_non_secret_by_design() -> None:
    # The dev key is public by design; the production key never defaults.
    assert EVAL_MODE_DEV_KEY == "eval-mode-dev-key-not-a-secret"


# --- §2.4 decision routing ---


def _draft_and_ticket(case_id="C-1001"):
    # 2026-09-05 coherence rule: current_value must be the LIVE modern
    # value (C-1001 balance 1250.00 — the earlier 1500.00/1250.00 pair
    # was the legacy/modern swap the hygiene pass eliminates); the
    # reversal-not-propagated fix proposes 1500.00.
    draft = draft_correction(case_id, "balance", 1250.00, 1500.00, "reversal evidence")
    ticket = create_case_ticket(case_id, "summary", "REVERSAL_NOT_PROPAGATED", 0.92,
                                ["L-TXN-90002"], draft["draft_id"])
    return draft, ticket


def test_gate_approve_issues_scoped_token_and_audits() -> None:
    _draft_and_ticket()
    # Approve without a pending draft must be refused:
    with pytest.raises(ValueError, match="no pending correction draft"):
        run_human_gate("case file", None, GateDecision(GateAction.APPROVE))
    from orchestrator.human_gate import latest_pending_draft

    outcome = run_human_gate("case file", latest_pending_draft("C-1001"), GateDecision(GateAction.APPROVE))
    assert outcome["action"] is GateAction.APPROVE
    ok, reason = validate_approval_token(
        outcome["approval_token"], case_id="C-1001", field="balance", new_value=1500.00, consume=False
    )
    assert ok, reason
    audits = (seed_data.RUNTIME_DIR / "audit_log.jsonl").read_text().splitlines()
    assert any(json.loads(line)["type"] == "gate_approval" for line in audits)


def test_gate_reject_closes_ticket_with_reason_and_case_linkage() -> None:
    _draft_and_ticket()
    outcome = run_human_gate(
        "case file", None, GateDecision(GateAction.REJECT, reason="wrong account"), case_id="C-1001"
    )
    assert outcome["action"] is GateAction.REJECT
    assert outcome["tickets_closed"] >= 1
    tickets = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "tickets.jsonl").read_text().splitlines()]
    assert all(t["status"] == "rejected" for t in tickets if t["case_id"] == "C-1001")
    assert any(t.get("rejection_reason") == "wrong account" for t in tickets)
    audits = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "audit_log.jsonl").read_text().splitlines()]
    rejection = [a for a in audits if a["type"] == "gate_rejection"][0]
    assert rejection["case_id"] == "C-1001"


def latest_draft():
    from orchestrator.human_gate import latest_pending_draft

    return latest_pending_draft("C-1001")


def test_gate_request_more_info_returns_hint_and_audits() -> None:
    outcome = run_human_gate("case file", None, GateDecision(GateAction.REQUEST_MORE_INFO, note="check event log"))
    assert outcome["action"] is GateAction.REQUEST_MORE_INFO
    assert outcome["investigation_hint"] == "check event log"
    audits = (seed_data.RUNTIME_DIR / "audit_log.jsonl").read_text().splitlines()
    assert any(json.loads(line)["type"] == "gate_more_info" for line in audits)


# --- §2.5 executor ---


def test_executor_applies_with_real_before_after_and_resolves_ticket() -> None:
    draft, ticket = _draft_and_ticket()
    token = issue_approval_token("C-1001", "balance", 1250.00)
    before_sha = _sha256(SEED)
    result = execute_correction(
        token, case_id="C-1001", field="balance", new_value=1250.00,
        ticket_id=ticket["ticket_id"], approver="human-jrivera", draft_id=draft["draft_id"],
    )
    assert result["status"] == "applied"
    assert result["before"] == 1250.00  # modern seed value (overlay empty pre-correction)
    assert result["after"] == 1250.00  # corrected value now effective
    assert result["no_op"] is True  # honest flag: effective value did not change (seed oddity)
    audits = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "audit_log.jsonl").read_text().splitlines()]
    applied = [a for a in audits if a["type"] == "correction_applied"][0]
    assert applied["approver"] == "human-jrivera"
    assert applied["ticket_id"] == ticket["ticket_id"]
    assert applied["field"] == "balance"
    assert applied["no_op"] is True
    tickets = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "tickets.jsonl").read_text().splitlines()]
    assert tickets[-1]["status"] == "resolved"
    assert tickets[-1]["audit_entry_id"] == result["audit_entry_id"]
    drafts = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "drafts.jsonl").read_text().splitlines()]
    assert drafts[-1]["status"] == "applied"  # draft lifecycle: never re-approvable
    assert _sha256(SEED) == before_sha  # AC2: seed immutable under a correction


def test_executor_invalid_token_fails_and_marks_ticket() -> None:
    draft, ticket = _draft_and_ticket()
    token = issue_approval_token("C-1001", "balance", 1250.00)
    # Wrong value at execution time -> scope mismatch.
    result = execute_correction(
        token, case_id="C-1001", field="balance", new_value=999.00,
        ticket_id=ticket["ticket_id"], approver="human", draft_id=draft["draft_id"],
    )
    assert result["status"] == "failed"
    assert "token validation failed" in result["error"]
    tickets = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "tickets.jsonl").read_text().splitlines()]
    assert tickets[-1]["status"] == "correction_failed"
    drafts = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "drafts.jsonl").read_text().splitlines()]
    assert drafts[-1]["status"] == "correction_failed"
    audits = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "audit_log.jsonl").read_text().splitlines()]
    assert any(a["type"] == "correction_failed" for a in audits)


def test_token_non_ascii_signature_rejected_not_crashed() -> None:
    token = _issue()
    body, _ = token.split(".")
    ok, reason = validate_approval_token(
        body + ".ññ", case_id="C-1001", field="balance", new_value=1250.00
    )
    assert not ok and reason == "malformed token"


def test_token_typed_value_mismatch_rejected() -> None:
    ok, reason = validate_approval_token(
        _issue(value=1250.00), case_id="C-1001", field="balance", new_value=1250
    )
    assert not ok and "value" in reason  # int 1250 != float 1250.0: strictly typed


def test_approved_draft_cannot_be_reapproved() -> None:
    _draft_and_ticket()
    from orchestrator.human_gate import latest_pending_draft

    first = run_human_gate("case file", latest_pending_draft("C-1001"), GateDecision(GateAction.APPROVE))
    assert first["action"] is GateAction.APPROVE
    assert latest_pending_draft("C-1001") is None  # draft left pending-land: stale re-approval impossible


def test_executor_apply_failure_surfaces_exact_error(monkeypatch) -> None:
    draft, ticket = _draft_and_ticket()
    token = issue_approval_token("C-1001", "balance", 1250.00)

    import orchestrator.correction_executor as executor

    def broken_apply(*args, **kwargs):
        return {"status": "failed", "audit_entry_id": None, "error": "simulated write outage"}

    monkeypatch.setattr(executor, "apply_correction", broken_apply)
    result = execute_correction(
        token, case_id="C-1001", field="balance", new_value=1250.00,
        ticket_id=ticket["ticket_id"], approver="human",
    )
    assert result == {"status": "failed", "error": "simulated write outage"}
    tickets = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "tickets.jsonl").read_text().splitlines()]
    assert tickets[-1]["status"] == "correction_failed"


# --- §2.4 + §1 composition via a stubbed graph (no model calls) ---


def test_run_case_with_gate_approve_path_end_to_end_with_stub_graph() -> None:
    draft, ticket = _draft_and_ticket()

    def fake_graph_factory(trace_attributes=None):
        class FakeGraph:
            def __call__(self, instruction: str):
                return SimpleNamespace(
                    execution_order=[
                        SimpleNamespace(node_id="detector_investigator"),
                        SimpleNamespace(node_id="classifier"),
                        SimpleNamespace(node_id="reporter"),
                    ],
                    results={
                        "classifier": SimpleNamespace(
                            result='{"root_cause": "REVERSAL_NOT_PROPAGATED", "confidence": 0.92, "requires_correction": true}'
                        ),
                        "reporter": SimpleNamespace(result="case file text"),
                    },
                )

        return FakeGraph()

    def approve(case_file, draft_record):
        return GateDecision(GateAction.APPROVE)

    outcome = run_case_with_gate(
        "Investigate C-1001", case_id="C-1001", decide=approve, build_graph=fake_graph_factory
    )
    correction = outcome["outcome"]["correction"]
    assert correction["status"] == "applied"
    assert outcome["verdict"]["root_cause"] == "REVERSAL_NOT_PROPAGATED"
    tickets = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "tickets.jsonl").read_text().splitlines()]
    assert tickets[-1]["status"] == "resolved"


def test_approve_executes_even_when_classifier_says_no_correction() -> None:
    # Audit finding 3's scenario (reviewer-mandated test): the human
    # approved a drafted correction while the classifier's verdict said
    # requires_correction=false — human authority executes, never silent.
    draft, ticket = _draft_and_ticket()

    def fake_graph_factory(trace_attributes=None):
        class FakeGraph:
            def __call__(self, instruction: str):
                return SimpleNamespace(
                    execution_order=[
                        SimpleNamespace(node_id="detector_investigator"),
                        SimpleNamespace(node_id="classifier"),
                        SimpleNamespace(node_id="reporter"),
                    ],
                    results={
                        "classifier": SimpleNamespace(
                            result='{"root_cause": "SYNC_LAG", "confidence": 0.9, "requires_correction": false}'
                        ),
                        "reporter": SimpleNamespace(result="case file"),
                    },
                )

        return FakeGraph()

    outcome = run_case_with_gate(
        "Investigate C-1001",
        case_id="C-1001",
        decide=lambda case_file, draft_record: GateDecision(GateAction.APPROVE),
        build_graph=fake_graph_factory,
    )
    correction = outcome["outcome"]["correction"]
    assert correction["status"] == "applied"
    tickets = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "tickets.jsonl").read_text().splitlines()]
    assert tickets[-1]["status"] == "resolved"


def test_max_human_rounds_exhaustion_is_audited_and_surfaced() -> None:
    # Audit finding 6's scenario (reviewer-mandated test): a decide() that
    # always requests more info must end with an explicit, audited
    # exhaustion marker — never a silently dropped final review.
    def fake_graph_factory(trace_attributes=None):
        class FakeGraph:
            def __call__(self, instruction: str):
                return SimpleNamespace(
                    execution_order=[
                        SimpleNamespace(node_id="detector_investigator"),
                        SimpleNamespace(node_id="classifier"),
                        SimpleNamespace(node_id="reporter"),
                    ],
                    results={
                        "classifier": SimpleNamespace(
                            result='{"root_cause": "UNKNOWN", "confidence": 0.5, "requires_correction": false}'
                        ),
                        "reporter": SimpleNamespace(result="case file"),
                    },
                )

        return FakeGraph()

    outcome = run_case_with_gate(
        "Investigate C-1001",
        case_id="C-1001",
        decide=lambda case_file, draft_record: GateDecision(
            GateAction.REQUEST_MORE_INFO, note="keep digging"
        ),
        build_graph=fake_graph_factory,
    )
    assert outcome["outcome"].get("max_rounds_exhausted") is True
    audits = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "audit_log.jsonl").read_text().splitlines()]
    assert any(a["type"] == "gate_rounds_exhausted" for a in audits)


def test_run_case_with_gate_request_more_info_reinvokes_graph_with_hint() -> None:
    calls = []

    def fake_graph_factory(trace_attributes=None):
        class FakeGraph:
            def __call__(self, instruction: str):
                calls.append(instruction)
                return SimpleNamespace(
                    execution_order=[
                        SimpleNamespace(node_id="detector_investigator"),
                        SimpleNamespace(node_id="classifier"),
                        SimpleNamespace(node_id="reporter"),
                    ],
                    results={
                        "classifier": SimpleNamespace(
                            result='{"root_cause": "SYNC_LAG", "confidence": 0.9, "requires_correction": false}'
                        ),
                        "reporter": SimpleNamespace(result="case file"),
                    },
                )

        return FakeGraph()

    decisions = iter([
        GateDecision(GateAction.REQUEST_MORE_INFO, note="check legacy event log"),
        GateDecision(GateAction.REJECT, reason="enough"),
    ])

    outcome = run_case_with_gate(
        "Investigate C-1003",
        case_id="C-1003",
        decide=lambda case_file, draft: next(decisions),
        build_graph=fake_graph_factory,
    )
    assert len(calls) == 2
    assert "investigation_hint: check legacy event log" in calls[1]
    assert outcome["verdict"]["root_cause"] == "SYNC_LAG"
