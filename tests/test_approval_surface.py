"""Approval-surface tests: the approval/ package renders state honestly
and delegates every decision to the deterministic spine. The web
screen's HTTP layer IS exercised below — over IPv6 loopback [::1],
because this environment's shell cannot reach IPv4 loopback listeners
(a bare python -m http.server on 127.0.0.1 times out too; OBSERVED
2026-09-06) while ::1 is healthy on the same host
(docs/approval-web-loopback-fix-and-validation-2026-09-06.md).
"""

import json
import threading
import urllib.error
import urllib.request

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


# --- read-only multi-case summary (/summary) ---


def test_summary_lists_all_five_seed_cases_empty_store() -> None:
    rows = web.summarize_cases()
    assert [row["case_id"] for row in rows] == [
        "C-1001", "C-1002", "C-1003", "C-1004", "C-1005",
    ]
    # every seeded case starts drifted, with nothing investigated yet
    assert all(row["drift"] for row in rows)
    assert all(row["ticket"] is None and row["pending_draft"] is None for row in rows)
    page = web.render_summary("C-1001")
    assert "All five seed cases" in page
    assert "<form" not in page  # read-only: no decision forms, nothing to submit
    # ground-truth discipline: with an empty store, no eval-case label,
    # seed annotation, or expected-output marker may appear on the page
    for marker in ("REVERSAL_NOT_PROPAGATED", "DUPLICATE_TRANSACTION", "_comment", "expected_"):
        assert marker not in page


def test_summary_reflects_ticket_and_pending_draft_from_the_store() -> None:
    _draft_and_ticket()  # C-1001: draft balance 1250->1500 + ticket REVERSAL_NOT_PROPAGATED
    rows = {row["case_id"]: row for row in web.summarize_cases()}
    ticket = rows["C-1001"]["ticket"]
    assert ticket["root_cause"] == "REVERSAL_NOT_PROPAGATED"
    assert ticket["confidence"] == 0.92
    assert ticket["status"] == "open"
    draft = rows["C-1001"]["pending_draft"]
    assert draft["field"] == "balance"
    assert draft["current_value"] == 1250.0
    assert draft["proposed_value"] == 1500.0
    assert all(rows[c]["ticket"] is None for c in ("C-1002", "C-1003", "C-1004", "C-1005"))


def test_summary_drift_flips_false_only_after_an_applied_override() -> None:
    rows = {row["case_id"]: row for row in web.summarize_cases()}
    assert rows["C-1001"]["drift"] is True  # seed: legacy 1500.0 vs modern 1250.0
    assert rows["C-1001"]["modern_balance"] == 1250.0
    # the executor's own store write, layered exactly as the read tools do
    seed_data.write_override("C-1001", "balance", 1500.0, "2026-09-10T12:00:00Z")
    rows = {row["case_id"]: row for row in web.summarize_cases()}
    assert rows["C-1001"]["drift"] is False
    assert rows["C-1001"]["modern_balance"] == 1500.0
    assert rows["C-1002"]["drift"] is True  # other cases untouched


def test_summary_escapes_untrusted_ticket_text() -> None:
    draft = draft_correction("C-1003", "balance", 4050.00, 4200.00, "sync lag evidence")
    # root_cause is a free string through the store AND a field the
    # summary table renders — the honest attack surface for this test
    create_case_ticket(
        "C-1003", "case summary", "<script>alert('root')</script> & \"q\"", 0.9,
        [], draft["draft_id"],
    )
    page = web.render_summary("C-1003")
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


# --- web screen HTTP layer (real sockets over ::1; IPv4 loopback is
# --- unreachable from this environment's shell — see module docstring) ---


def _http_server(case_id: str = "C-1001", approver: str = "human"):
    state = {"token": None, "executed": None, "replay": None, "action_log": []}
    server = web.build_server("::1", 0, case_id, approver, state)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://[::1]:{server.server_address[1]}/"


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.read().decode()


def _post(url: str):
    request = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, response.read().decode()


def _stop(server) -> None:
    server.shutdown()
    server.server_close()


def _store_lines(name: str):
    return [
        json.loads(line)
        for line in (seed_data.RUNTIME_DIR / name).read_text().splitlines()
        if line.strip()
    ]


def test_http_layer_serves_cards_over_ipv6_loopback() -> None:
    draft, ticket = _draft_and_ticket()
    server, url = _http_server()
    try:
        status, page = _get(url)
        assert status == 200
        assert "C-1001" in page and ticket["ticket_id"] in page
        assert "Proposed correction" in page and draft["draft_id"] in page
        assert "1250.0" in page and "1500.0" in page
        assert 'action="/approve"' in page  # the decision forms are wired
    finally:
        _stop(server)


def test_http_layer_approve_runs_shared_gate_and_executor() -> None:
    _draft_and_ticket()
    server, url = _http_server(approver="http-test")
    try:
        status, page = _post(url + "approve")
        assert status == 200
        assert "Execution result" in page and "applied" in page
        # The STORE proves the shared deterministic spine ran (not a UI
        # reimplementation): audit chain, draft applied, ticket resolved,
        # override mutation — the same artifacts the CLI path produces.
        actions = [row.get("type") for row in _store_lines("audit_log.jsonl")]
        assert "gate_approval" in actions and "correction_applied" in actions
        assert _store_lines("drafts.jsonl")[-1]["status"] == "applied"
        assert _store_lines("tickets.jsonl")[-1]["status"] == "resolved"
        overrides = json.loads((seed_data.RUNTIME_DIR / "overrides.json").read_text())
        assert overrides["C-1001"]["balance"] == 1500.0
    finally:
        _stop(server)


def test_http_layer_approve_records_approver_in_both_audit_rows() -> None:
    _draft_and_ticket()
    approver = "http-approver-attribution"
    server, url = _http_server(approver=approver)
    try:
        status, _page = _post(url + "approve")
        assert status == 200
        # Regression (2026-09-06): _do_approve omitted the approver kwarg
        # on apply_gate_approval, so the executor's correction_applied row
        # fell back to the default "human" while gate_approval carried the
        # real --approver. Both rows must attribute the same approver.
        rows = _store_lines("audit_log.jsonl")
        gate = [r for r in rows if r.get("type") == "gate_approval"]
        applied = [r for r in rows if r.get("type") == "correction_applied"]
        assert len(gate) == 1 and len(applied) == 1
        assert gate[0]["approver"] == approver
        assert applied[0]["approver"] == approver
    finally:
        _stop(server)


def test_http_layer_replay_is_refused_single_use() -> None:
    _draft_and_ticket()
    server, url = _http_server()
    try:
        _post(url + "approve")
        status, page = _post(url + "replay")
        assert status == 200
        assert "the executor refused the replay, as it must" in page
        assert "already consumed" in page
        actions = [row.get("type") for row in _store_lines("audit_log.jsonl")]
        assert "correction_failed" in actions  # the refused replay is audited
        # consumed_tokens.jsonl holds bare jti strings (one per line): the
        # approve consumed its jti exactly once and the replay added none.
        consumed = [
            line
            for line in (seed_data.RUNTIME_DIR / "consumed_tokens.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert len(consumed) == 1
    finally:
        _stop(server)


def test_http_layer_second_approve_is_refused() -> None:
    _draft_and_ticket()
    server, url = _http_server()
    try:
        _post(url + "approve")
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _post(url + "approve")
        assert excinfo.value.code == 500
        error_page = excinfo.value.read().decode()
        assert "cannot approve" in error_page
        assert "no pending correction draft" in error_page
    finally:
        _stop(server)


def test_http_layer_summary_route_is_served_read_only_and_linked() -> None:
    _draft_and_ticket()
    server, url = _http_server()
    try:
        status, summary = _get(url + "summary")
        assert status == 200
        for case_id in ("C-1001", "C-1002", "C-1003", "C-1004", "C-1005"):
            assert case_id in summary
        # the filed ticket's STORE content shows; nothing else is fabricated
        assert "REVERSAL_NOT_PROPAGATED" in summary
        assert "<form" not in summary  # read-only pinned at the HTTP layer too
        status, page = _get(url)
        assert status == 200 and 'href="/summary"' in page
        with pytest.raises(urllib.error.HTTPError) as excinfo:  # unknown paths still 404
            _get(url + "nope")
        assert excinfo.value.code == 404
    finally:
        _stop(server)


def test_bind_accepts_only_loopback_literals() -> None:
    # committed default stays the IPv4 literal; the refusal (exit 2,
    # before any socket is created) holds for wildcards, names, and LAN
    # addresses alike — the demo boundary is loopback-scope only.
    assert web.build_parser().get_default("bind") == "127.0.0.1"
    for bad in ("0.0.0.0", "::", "localhost", "192.0.2.7"):
        assert web.main(["--customer", "C-1004", "--bind", bad]) == 2


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
