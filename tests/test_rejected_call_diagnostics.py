"""2026-09-06 rejected-call diagnostics regression tests: every rejected
draft_correction/create_case_ticket call (a) still raises the exact
pre-diagnostics error — observability only, zero accept/reject change —
and (b) appends exactly one record to runtime/rejected_calls.jsonl
carrying the timestamp, component, tool, the arguments AS RECEIVED
(clipped/masked), and the validator's own reason; valid calls write
nothing. The store is inert by construction and by test: the gate, the
executor, and the capability-token logic never read it (open-spy +
canary + source tripwire below), and a log-write failure never changes
a rejection outcome."""

import builtins
import datetime as dt
import io
import json
from pathlib import Path

import pytest

import tools.case_management as case_management
import tools.seed_data as seed_data
from orchestrator.correction_executor import execute_correction
from orchestrator.human_gate import (
    GateAction,
    GateDecision,
    latest_pending_draft,
    run_human_gate,
    validate_approval_token,
)
from tools.case_management import (
    _redact_call_args,
    create_case_ticket,
    draft_correction,
)

LOG_NAME = "rejected_calls.jsonl"

# Live modern-system balances the coherence checks quote (frozen seed).
_LIVE_BALANCE = {"C-1001": 1250.00, "C-1002": 1160.00}


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_MODE", "1")
    monkeypatch.setattr(seed_data, "RUNTIME_DIR", tmp_path)
    return tmp_path


def _entries() -> list[dict]:
    path = seed_data.RUNTIME_DIR / LOG_NAME
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _records(name: str) -> list[dict]:
    path = seed_data.RUNTIME_DIR / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _assert_entry_shape(entry: dict, tool: str) -> None:
    assert entry["tool"] == tool
    assert entry["component"] == "reporter"  # sole holder of these tools
    stamp = dt.datetime.fromisoformat(entry["timestamp"])
    assert stamp.utcoffset() == dt.timedelta(0)  # UTC ISO-8601, parseable


# --- draft_correction: still rejected identically, logged exactly once ---


# (args, match) pairs use the SAME match patterns as the 2026-09-05
# hygiene tests — the diagnostics pass must not have moved a message.
_DRAFT_REJECTIONS = [
    (("C-9999", "balance", 1.0, 2.0, "x"), "customer"),
    (("C-1001", "legacy_deposit_amount", 350.50, 305.50, "x"), "unknown field"),
    (("C-1001", "balance", "Modern balance is $250 lower", "1500.00", "x"), "current_value"),
    (("C-1001", "balance", 1250.00, True, "x"), "value"),
    (("C-1004", "status", "ACTIVE", "FROZEN", "x"), "status"),
    (("C-1001", "balance", 999.00, 1500.00, "x"), "current"),
    (("C-1001", "balance", 1250.00, 1250.00, "x"), "no-op|no op|same"),
]


@pytest.mark.parametrize("args,match", _DRAFT_REJECTIONS)
def test_rejected_draft_correction_still_rejects_and_logs_once(args, match) -> None:
    with pytest.raises(ValueError, match=match):
        draft_correction(*args)
    entries = _entries()
    assert len(entries) == 1  # exactly one record per rejected call
    _assert_entry_shape(entries[0], "draft_correction")
    assert entries[0]["args"] == {
        "customer_id": args[0],
        "field": args[1],
        "current_value": args[2],
        "proposed_value": args[3],
        "justification": args[4],
    }
    assert match.split("|")[0] in entries[0]["reason"]
    assert _records("drafts.jsonl") == []  # still rejected BEFORE any append


# --- create_case_ticket: still rejected identically, logged exactly once ---


_TICKET_REJECTIONS = [
    (("C-1001-001", "s", "SYNC_LAG", 0.9, [], None), "case_id|canonical"),
    (("C-9999", "s", "SYNC_LAG", 0.9, [], None), "customer|case_id"),
    (("C-1001", "s", "SYNC_LAG", 0.9, [], "None"), "draft"),
    (("C-1001", "s", "SYNC_LAG", 0.9, [], "DRF-doesnotexist"), "draft"),
]


@pytest.mark.parametrize("args,match", _TICKET_REJECTIONS)
def test_rejected_create_case_ticket_still_rejects_and_logs_once(args, match) -> None:
    with pytest.raises(ValueError, match=match):
        create_case_ticket(*args)
    entries = _entries()
    assert len(entries) == 1
    _assert_entry_shape(entries[0], "create_case_ticket")
    assert entries[0]["args"] == {
        "case_id": args[0],
        "summary": args[1],
        "root_cause": args[2],
        "confidence": args[3],
        "evidence_refs": list(args[4]),
        "correction_draft_id": args[5],
    }
    assert match.split("|")[0] in entries[0]["reason"]
    assert _records("tickets.jsonl") == []


def test_rejected_cross_case_draft_link_logs_the_received_link() -> None:
    foreign = draft_correction("C-1002", "balance", _LIVE_BALANCE["C-1002"], 1410.00, "other case")
    with pytest.raises(ValueError, match="case|draft"):
        create_case_ticket("C-1001", "s", "SYNC_LAG", 0.9, [], foreign["draft_id"])
    entries = _entries()
    assert len(entries) == 1  # the accepted C-1002 draft logged nothing
    _assert_entry_shape(entries[0], "create_case_ticket")
    assert entries[0]["args"]["correction_draft_id"] == foreign["draft_id"]
    assert len(_records("drafts.jsonl")) == 1  # the legit draft survived


def test_valid_calls_write_no_rejected_entries() -> None:
    draft = draft_correction("C-1001", "balance", _LIVE_BALANCE["C-1001"], 1500.00, "reversal evidence")
    create_case_ticket("C-1001", "s", "REVERSAL_NOT_PROPAGATED", 0.92, ["L-TXN-90002"], draft["draft_id"])
    create_case_ticket("C-1001", "s", "SYNC_LAG", 0.9, [], None)
    assert not (seed_data.RUNTIME_DIR / LOG_NAME).exists()  # zero entries, no file


def test_out_of_mode_call_is_rejected_and_logged(monkeypatch) -> None:
    # require_eval_mode's RuntimeError is a rejected call too — and the
    # entry is the only place the received shape survives it.
    monkeypatch.delenv("EVAL_MODE", raising=False)
    with pytest.raises(RuntimeError, match="EVAL_MODE"):
        draft_correction("C-1001", "balance", _LIVE_BALANCE["C-1001"], 1500.00, "x")
    entries = _entries()
    assert len(entries) == 1 and "EVAL_MODE" in entries[0]["reason"]


# --- clipping / masking: no unbounded or secret-looking content ---


def test_overlong_free_text_is_clipped_in_args_and_reason() -> None:
    prose = "x" * 5000
    with pytest.raises(ValueError, match="current_value"):
        draft_correction("C-1001", "balance", prose, "1500.00", "y" * 5000)
    entry = _entries()[0]
    clipped_value = entry["args"]["current_value"]
    assert clipped_value == "x" * 500 + "<truncated, 5000 chars total>"
    clipped_justification = entry["args"]["justification"]
    assert clipped_justification == "y" * 500 + "<truncated, 5000 chars total>"
    # The reason embeds the offending value -> it is clipped too.
    assert len(entry["reason"]) < 600
    assert entry["reason"].startswith("current_value for balance")


def test_redact_call_args_masks_secret_keys_and_caps_lists() -> None:
    redacted = _redact_call_args({
        "api_key": "sk-never-logged",
        "nested": {"auth_token": "abc", "ok": "fine"},
        "evidence_refs": [f"ref-{i}" for i in range(30)],
        "odd": {"weird": {1, 2}},
    })
    assert redacted["api_key"] == "<REDACTED:api_key>"
    assert redacted["nested"]["auth_token"] == "<REDACTED:auth_token>"
    assert redacted["nested"]["ok"] == "fine"
    refs = redacted["evidence_refs"]
    assert len(refs) == 21 and refs[-1] == "<30 items total>" and refs[0] == "ref-0"
    assert isinstance(redacted["odd"]["weird"], str)  # repr'd: JSON-safe always
    json.dumps(redacted)  # serializability is the redactor's contract


def test_post_validation_null_crash_is_logged_too() -> None:
    # The 2026-09-04 Groq null-lottery class: a model-emitted null that
    # slips the annotation crashes list(evidence_refs) AFTER validation —
    # previously a call that died with no trace of its shape.
    with pytest.raises(TypeError, match="not iterable"):
        create_case_ticket("C-1001", "s", "SYNC_LAG", 0.9, None, None)
    entries = _entries()
    assert len(entries) == 1
    _assert_entry_shape(entries[0], "create_case_ticket")
    assert entries[0]["args"]["evidence_refs"] is None
    assert "not iterable" in entries[0]["reason"]
    assert _records("tickets.jsonl") == []


def test_unserializable_argument_crash_is_logged() -> None:
    # justification carries no validation, so a non-JSON value reaches the
    # store append and dies there — still logged, still no draft written.
    with pytest.raises(TypeError, match="not JSON serializable"):
        draft_correction("C-1001", "balance", _LIVE_BALANCE["C-1001"], 1500.00, {"weird": {1, 2}})
    entries = _entries()
    assert len(entries) == 1 and entries[0]["tool"] == "draft_correction"
    assert "not JSON serializable" in entries[0]["reason"]
    assert _records("drafts.jsonl") == []


def test_log_write_failure_never_changes_the_rejection(monkeypatch, capsys) -> None:
    def broken_append(name, record):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(case_management, "_append_jsonl", broken_append)
    with pytest.raises(ValueError, match="no-op"):  # the ORIGINAL rejection
        draft_correction("C-1001", "balance", _LIVE_BALANCE["C-1001"], _LIVE_BALANCE["C-1001"], "x")
    assert "rejected-calls" in capsys.readouterr().err
    assert not (seed_data.RUNTIME_DIR / LOG_NAME).exists()


# --- the log is inert to the gate, the executor, and the token logic ---


def test_gate_and_executor_never_read_or_write_the_rejected_calls_log(monkeypatch) -> None:
    log_path = seed_data.RUNTIME_DIR / LOG_NAME
    # A canary entry a buggy future reader could confuse for a draft.
    log_path.write_text(json.dumps({
        "timestamp": "2026-09-06T00:00:00+00:00",
        "component": "reporter",
        "tool": "draft_correction",
        "args": {"customer_id": "C-1001", "field": "balance", "current_value": 1250.00,
                 "proposed_value": 999999.00, "justification": "canary — never a draft"},
        "reason": "canary entry written by the test",
    }) + "\n", encoding="utf-8")
    before = log_path.read_bytes()

    draft = draft_correction("C-1001", "balance", _LIVE_BALANCE["C-1001"], 1500.00, "reversal evidence")
    ticket = create_case_ticket("C-1001", "summary", "REVERSAL_NOT_PROPAGATED", 0.92,
                                ["L-TXN-90002"], draft["draft_id"])

    # Spy on EVERY file open (builtins.open and io.open) across the full
    # gate + executor + token flow: issue, validate, consume, audit.
    opened: list[tuple[str, str]] = []
    real_open = builtins.open

    def recording_open(file, mode="r", *args, **kwargs):
        try:
            opened.append((str(file), mode))
        except Exception:
            pass
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", recording_open)
    monkeypatch.setattr(io, "open", recording_open)

    pending = latest_pending_draft("C-1001")
    outcome = run_human_gate("case file", pending, GateDecision(GateAction.APPROVE))
    assert outcome["action"] is GateAction.APPROVE
    result = execute_correction(
        outcome["approval_token"], case_id="C-1001", field="balance", new_value=1500.00,
        ticket_id=ticket["ticket_id"], approver="human-test", draft_id=draft["draft_id"],
    )
    ok, reason = validate_approval_token(
        outcome["approval_token"], case_id="C-1001", field="balance", new_value=1500.00
    )
    assert not ok and "consumed" in reason  # single-use still enforced under the spy

    violations = [entry for entry in opened if entry[0].endswith(LOG_NAME)]
    assert violations == []  # never opened for reading — or anything else
    assert log_path.read_bytes() == before  # untouched, byte for byte
    assert result["status"] == "applied"
    assert result["after"] == 1500.00  # the REAL correction, not the canary's


def test_no_gate_executor_or_approval_source_references_the_log() -> None:
    # Mechanical tripwire complementing the spy: if any gate, executor,
    # or approval-surface module ever grows a reference to the store,
    # this fails before such code can become a read path.
    repo = Path(__file__).resolve().parent.parent
    scanned = sorted(repo.glob("orchestrator/*.py")) + sorted(repo.glob("approval/*.py"))
    assert scanned, "expected orchestrator/ and approval/ modules to exist"
    for module in scanned:
        assert "rejected_calls" not in module.read_text(encoding="utf-8"), module
