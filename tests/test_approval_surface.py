"""Approval-surface tests (socket-free): the approval/ package renders
state honestly and delegates every decision to the deterministic spine.
The web screen's HTTP layer is NOT exercised here — this environment's
shell cannot reach loopback listeners (a bare python -m http.server
times out too; OBSERVED 2026-09-06), so the screen is verified at the
render + delegation level and by code review; the CLI's flow is the
live-verified surface (docs/human-gate-e2e-validation-2026-09-05.md).
"""

import json

import pytest

import tools.seed_data as seed_data
from approval import cli, web
from tools.case_management import create_case_ticket, draft_correction


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_MODE", "1")
    monkeypatch.setattr(seed_data, "RUNTIME_DIR", tmp_path)
    return tmp_path


def _draft_and_ticket(case_id="C-1001"):
    draft = draft_correction(case_id, "balance", 1250.00, 1500.00, "reversal evidence")
    ticket = create_case_ticket(
        case_id, "summary of the case", "REVERSAL_NOT_PROPAGATED", 0.92,
        ["L-TXN-90002"], draft["draft_id"],
    )
    return draft, ticket


# --- web screen rendering (direct render_page calls; no sockets) ---


def test_web_page_with_pending_draft_shows_case_and_correction() -> None:
    draft, ticket = _draft_and_ticket()
    page = web.render_page("C-1001", {"token": None, "executed": None, "replay": None, "action_log": []})
    assert "No pending correction draft" not in page
    assert "C-1001" in page
    assert ticket["ticket_id"] in page
    assert "summary of the case" in page
    assert "REVERSAL_NOT_PROPAGATED" in page
    assert "balance" in page and "1500.0" in page and "1250.0" in page
    assert draft["draft_id"] in page
    assert "holds no authority" in page  # the security-model footer


def test_web_page_without_draft_disables_decisions_and_points_to_cli() -> None:
    page = web.render_page("C-1004", {"token": None, "executed": None, "replay": None, "action_log": []})
    assert "No pending correction draft" in page
    assert "approval.cli --customer C-1004" in page
    assert "disabled" in page  # APPROVE/REJECT are inert without a draft


def test_web_page_escapes_untrusted_draft_text() -> None:
    draft_correction(
        "C-1002", "balance", 1160.00, 980.00,
        "<script>alert('x')</script> & \"quotes\"",
    )
    page = web.render_page("C-1002", {"token": None, "executed": None, "replay": None, "action_log": []})
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_web_execution_and_replay_cards_render_from_session_state() -> None:
    state = {
        "token": "body.sig",
        "executed": {"status": "applied", "before": 1250.0, "after": 1500.0,
                     "no_op": False, "audit_entry_id": "AUD-x", "ticket_id": "TCK-x"},
        "replay": {"status": "failed", "error": "token validation failed: token already consumed (single-use)"},
        "action_log": ["APPROVE by human: executed status=applied"],
    }
    page = web.render_page("C-1001", state)
    assert "Execution result" in page and "AUD-x" in page
    assert "Replay result" in page
    assert "refused the replay, as it must" in page
    assert "already consumed" in page


# --- CLI: startup validation and scripted-decision plumbing ---


def test_cli_rejects_unknown_customer_with_exit_2(capsys) -> None:
    assert cli.main(["--customer", "C-9999"]) == 2
    assert "unknown case_id/customer_id" in capsys.readouterr().err


def test_cli_scripted_decider_is_labeled_non_human(capsys) -> None:
    decide = cli.build_scripted_decider("approve", "validation-run", "", "")
    banner = capsys.readouterr().out
    assert "NOT a human decision" in banner  # honest labeling, every run
    decision = decide("case file", None)
    assert decision.action.value == "approve"
    assert decision.approver == "validation-run"


def test_cli_interactive_decider_approve_and_quit(monkeypatch) -> None:
    decide = cli.build_interactive_decider("C-1001", "human")
    inputs = iter(["a"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    decision = decide("the case file text", None)
    assert decision.action.value == "approve"
    # q is a clean exit with nothing approved
    monkeypatch.setattr("builtins.input", lambda prompt="": "q")
    with pytest.raises(SystemExit) as exc:
        decide("case file", None)
    assert exc.value.code == 0


def test_cli_result_block_reads_back_real_state(capsys) -> None:
    _draft_and_ticket()
    from orchestrator.graph import apply_gate_approval
    from orchestrator.human_gate import (
        GateAction,
        GateDecision,
        latest_pending_draft,
        run_human_gate,
    )

    # The gate consumes the STORED draft record (the tool's return value
    # is just {draft_id, status}).
    draft = latest_pending_draft("C-1001")
    gate = run_human_gate("case file", draft, GateDecision(GateAction.APPROVE), case_id="C-1001")
    executed = apply_gate_approval("C-1001", gate, draft, approver="human")
    ticket_id = executed["ticket_id"]
    final = {"verdict": {"root_cause": "REVERSAL_NOT_PROPAGATED", "confidence": 0.92},
             "outcome": {"gate": gate, "correction": executed, "verdict": {}}}
    cli.print_result_block(final, "C-1001")
    out = capsys.readouterr().out
    assert "root_cause=REVERSAL_NOT_PROPAGATED" in out
    assert "status=applied" in out and "1250.0" in out and "1500.0" in out
    assert "AUD-" in out
    assert f"ticket:      {ticket_id} status=resolved" in out
    # the printed ticket status comes from the store read-back, not the echo
    stored = [json.loads(line) for line in (seed_data.RUNTIME_DIR / "tickets.jsonl").read_text().splitlines()]
    assert stored[-1]["status"] == "resolved"
