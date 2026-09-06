"""2026-09-05 gate/executor linkage + replay regression tests:
ticket_for_draft exact draft<->ticket linkage; run_human_gate refusing
(invalid-draft approvals: audited gate_approval_refused, draft
rejected, NO token issued — never a crash); executor replay after
success failing on the consumed single-use token without clobbering
terminal ticket/draft state; wrong-case and empty-token executions
failing and auditing; status-correction end-to-end;
graph.apply_gate_approval resolving the draft-LINKED ticket (not the
latest); run_case_with_gate canonicalizing case_id BEFORE any graph
invocation."""

import hashlib
import json

import pytest

import tools.seed_data as seed_data
from orchestrator.correction_executor import execute_correction
from orchestrator.graph import apply_gate_approval, run_case_with_gate
from orchestrator.human_gate import (
    GateAction,
    GateDecision,
    issue_approval_token,
    latest_pending_draft,
    latest_ticket,
    run_human_gate,
    ticket_for_draft,
)
from tools.case_management import create_case_ticket, draft_correction, get_draft, get_ticket
from tools.modern_system import read_modern_system

SEED = seed_data.SEED_PATH


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_MODE", "1")
    monkeypatch.setattr(seed_data, "RUNTIME_DIR", tmp_path)
    return tmp_path


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audit_entries() -> list[dict]:
    path = seed_data.RUNTIME_DIR / "audit_log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_raw_draft(record: dict) -> None:
    """Append a record to drafts.jsonl DIRECTLY, bypassing draft_correction
    (simulates a legacy/foreign pending draft reaching the gate)."""
    path = seed_data.RUNTIME_DIR / "drafts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _draft_and_ticket(case_id="C-1001", current=1250.00, proposed=1500.00, field="balance"):
    draft = draft_correction(case_id, field, current, proposed, "reversal evidence")
    ticket = create_case_ticket(
        case_id, "summary", "REVERSAL_NOT_PROPAGATED", 0.92, ["L-TXN-90002"], draft["draft_id"]
    )
    return draft, ticket


def _approve(case_id, draft_record):
    return run_human_gate(
        "case file", draft_record, GateDecision(GateAction.APPROVE), case_id=case_id
    )


# --- ticket_for_draft: the deterministic draft<->ticket association ---


def test_ticket_for_draft_exact_link_wins_over_later_unlinked_ticket() -> None:
    draft, linked = _draft_and_ticket()
    # A LATER unlinked ticket for the same case is what latest_ticket
    # would return — the exact draft link must still win.
    unlinked = create_case_ticket("C-1001", "later round", "REVERSAL_NOT_PROPAGATED", 0.9, [], None)
    found = ticket_for_draft("C-1001", draft["draft_id"])
    assert found is not None
    assert found["ticket_id"] == linked["ticket_id"]
    assert found["ticket_id"] != unlinked["ticket_id"]


def test_ticket_for_draft_unknown_draft_id_falls_back_to_latest_case_ticket() -> None:
    draft, ticket = _draft_and_ticket()
    # DOCUMENTED fallback semantics (coordinator ruling over the drafted
    # strict variant): an id that links nothing resolves to the case's
    # LATEST ticket — legacy unlinked tickets (correction_draft_id=null,
    # observed in the live store) must still resolve; only a case with
    # no ticket at all yields None.
    assert ticket_for_draft("C-1001", "DRF-doesnotexist")["ticket_id"] == ticket["ticket_id"]
    assert ticket_for_draft("C-1002", "DRF-doesnotexist") is None


def test_latest_pending_draft_and_latest_ticket_still_resolve_for_canonical_ids() -> None:
    draft, ticket = _draft_and_ticket()
    assert latest_pending_draft("C-1001")["draft_id"] == draft["draft_id"]
    assert latest_ticket("C-1001")["ticket_id"] == ticket["ticket_id"]


# --- gate: invalid-draft approval is refused, never crashes ---


def test_gate_approve_of_invalid_draft_is_refused_not_crashed() -> None:
    # A legacy/foreign pending draft reaching the gate must NOT raise
    # (the latent uncaught ValueError in token issuance) and must NEVER
    # issue a token: the refusal is audited and the draft terminally
    # rejected.
    _append_raw_draft({
        "draft_id": "DRF-legacy000001",
        "customer_id": "C-1005",
        "field": "legacy_deposit_amount",
        "current_value": "50.00",
        "proposed_value": "95.0",
        "justification": "historical artifact",
        "status": "pending_approval",
        "created_at": "2026-09-04T12:00:00+00:00",
    })
    draft = latest_pending_draft("C-1005")
    outcome = run_human_gate(
        "case file", draft, GateDecision(GateAction.APPROVE), case_id="C-1005"
    )
    assert outcome["action"] is GateAction.REJECT
    # Contract sanctions "draft failed validation" or the deterministic
    # "unknown field" reason; the serialized-outcome scan accepts either
    # phrasing under either outcome key.
    blob = json.dumps(outcome, default=str)
    assert "draft failed validation" in blob or "unknown field" in blob
    assert "approval_token" not in outcome  # no token was issued
    refused = [a for a in _audit_entries() if a["type"] == "gate_approval_refused"]
    assert any(a.get("case_id") == "C-1005" for a in refused)
    assert get_draft("DRF-legacy000001")["status"] == "rejected"
    consumed = seed_data.RUNTIME_DIR / "consumed_tokens.jsonl"
    assert not consumed.exists() or consumed.read_text().strip() == ""


# --- executor: replay, terminal-state awareness, scope ---


def test_executor_replay_after_success_fails_without_clobbering_terminal_state() -> None:
    draft, ticket = _draft_and_ticket()
    record = get_draft(draft["draft_id"])
    draft_record = latest_pending_draft("C-1001")
    gate = _approve("C-1001", draft_record)
    before_sha = _sha256(SEED)
    first = execute_correction(
        gate["approval_token"],
        case_id="C-1001", field=record["field"], new_value=record["proposed_value"],
        ticket_id=ticket["ticket_id"], approver="human", draft_id=draft["draft_id"],
    )
    assert first["status"] == "applied"
    assert first["before"] == 1250.0
    assert first["after"] == 1500.0
    assert first["no_op"] is False
    replay = execute_correction(
        gate["approval_token"],
        case_id="C-1001", field=record["field"], new_value=record["proposed_value"],
        ticket_id=ticket["ticket_id"], approver="human", draft_id=draft["draft_id"],
    )
    assert replay["status"] == "failed"
    assert "consumed" in replay["error"]  # single-use token dies at validation
    failures = [a for a in _audit_entries() if a["type"] == "correction_failed"]
    assert any("consumed" in str(a.get("error", "")) for a in failures)  # replay still audited
    # Terminal-state awareness: the resolved/applied records survive.
    assert get_ticket(ticket["ticket_id"])["status"] == "resolved"
    assert get_draft(draft["draft_id"])["status"] == "applied"
    assert _sha256(SEED) == before_sha  # seed immutable under correction + replay


def test_failed_execute_after_reject_never_flips_rejected_ticket() -> None:
    # Also pins the empty-token contract: execute_correction("", ...) ->
    # failed "malformed" (token validation failed), audited.
    draft, ticket = _draft_and_ticket()
    outcome = run_human_gate(
        "case file", None, GateDecision(GateAction.REJECT, reason="wrong account"), case_id="C-1001"
    )
    assert outcome["action"] is GateAction.REJECT
    assert get_ticket(ticket["ticket_id"])["status"] == "rejected"
    result = execute_correction(
        "",
        case_id="C-1001", field="balance", new_value=1500.00,
        ticket_id=ticket["ticket_id"], approver="human", draft_id=draft["draft_id"],
    )
    assert result["status"] == "failed"
    assert "malformed" in result["error"]
    assert any(a["type"] == "correction_failed" for a in _audit_entries())  # still audited
    # Terminal-state awareness: a rejected ticket is never flipped to
    # correction_failed by a later failed execution.
    assert get_ticket(ticket["ticket_id"])["status"] == "rejected"


def test_executor_wrong_case_token_fails_and_leaves_target_untouched() -> None:
    token = issue_approval_token("C-1001", "balance", 1500.00)
    result = execute_correction(
        token, case_id="C-1002", field="balance", new_value=1500.00,
        ticket_id="", approver="human",
    )
    assert result["status"] == "failed"
    assert "case" in result["error"]
    assert read_modern_system("C-1002")["balance"] == 1160.00  # seed truth, unchanged


def test_status_correction_end_to_end_applies_and_overlays() -> None:
    before_sha = _sha256(SEED)
    draft = draft_correction(
        "C-1004", "status", "ACTIVE", "SUSPENDED", "manual override evidence"
    )
    ticket = create_case_ticket(
        "C-1004", "status-only discrepancy", "MANUAL_STATUS_OVERRIDE", 0.95,
        ["EVT-L-40041"], draft["draft_id"],
    )
    gate = _approve("C-1004", latest_pending_draft("C-1004"))
    result = execute_correction(
        gate["approval_token"],
        case_id="C-1004", field="status", new_value="SUSPENDED",
        ticket_id=ticket["ticket_id"], approver="human", draft_id=draft["draft_id"],
    )
    assert result["status"] == "applied"
    assert read_modern_system("C-1004")["status"] == "SUSPENDED"  # read-your-writes overlay
    assert _sha256(SEED) == before_sha


# --- graph composition: apply_gate_approval ---


def test_apply_gate_approval_resolves_the_linked_ticket_not_the_latest() -> None:
    older_open = create_case_ticket(
        "C-1001", "earlier round, no draft", "SYNC_LAG", 0.8, [], None
    )
    draft, linked = _draft_and_ticket()
    later_open = create_case_ticket(
        "C-1001", "later round, no draft", "SYNC_LAG", 0.8, [], None
    )
    # later_open makes the case's LATEST ticket unlinked — a latest-ticket
    # resolution would close the wrong record, so this order discriminates.
    draft_record = latest_pending_draft("C-1001")
    gate = _approve("C-1001", draft_record)
    result = apply_gate_approval("C-1001", gate, draft_record)
    assert result["status"] == "applied"
    assert get_ticket(linked["ticket_id"])["status"] == "resolved"
    assert get_ticket(older_open["ticket_id"])["status"] == "open"
    assert get_ticket(later_open["ticket_id"])["status"] == "open"


# --- run_case_with_gate: early case-id canonicalization ---


def test_run_case_with_gate_rejects_noncanonical_case_id_before_any_graph_run() -> None:
    calls = []

    def factory(trace_attributes=None):
        calls.append("built")

        class FakeGraph:
            def __call__(self, instruction: str):
                calls.append("ran")
                raise AssertionError("graph must never run for a non-canonical case_id")

        return FakeGraph()

    # Contract match "customer" or "case_id" (alternation accepts either).
    with pytest.raises(ValueError, match="customer|case_id"):
        run_case_with_gate(
            "Investigate C-1001",
            case_id="C-1001-001",
            decide=lambda case_file, draft_record: GateDecision(GateAction.REJECT),
            build_graph=factory,
        )
    assert calls == []  # canonicalization happens BEFORE any graph build/run
