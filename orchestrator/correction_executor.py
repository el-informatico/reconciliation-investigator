"""correction_executor — deterministic orchestrator code (§2.5).

NOT an LLM node. The ONLY caller of apply_correction in the entire
system (this module holds the single non-test import of it; the
segregation guard and tests/test_gate_executor.py keep that true).

Steps per §2.5: validate the approval_token (correct case, correct
correction, not expired, not consumed) -> apply -> audit-log who/when/
what/before/after linked to the ticket -> ticket "resolved". On any
failure: mark the case "correction_failed", surface the exact error,
never retry silently."""

from __future__ import annotations

import datetime as dt
import json

from orchestrator.human_gate import validate_approval_token
from tools.case_management import update_draft, update_ticket
from tools.modern_system import apply_correction
from tools.seed_data import effective_modern_record, normalize_field, runtime_path

# The one and only import of the write tool in non-test source.
assert apply_correction is not None  # imported explicitly, never as a tool


def _audit(entry: dict) -> None:
    path = runtime_path("audit_log.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def execute_correction(
    approval_token: str,
    *,
    case_id: str,
    field: str,
    new_value,
    ticket_id: str,
    approver: str,
    draft_id: str = "",
) -> dict:
    """Apply one human-approved correction, or surface failure. Draft
    lifecycle rides along (audit finding 5): applied / correction_failed
    transitions keep a draft from ever being re-approved later."""
    at = dt.datetime.now(dt.timezone.utc).isoformat()

    def _fail(error: str) -> dict:
        _audit({
            "type": "correction_failed",
            "at": at,
            "ticket_id": ticket_id,
            "case_id": case_id,
            "draft_id": draft_id or None,
            "error": error,
        })
        if ticket_id:
            update_ticket(ticket_id, status="correction_failed", failure_reason=error)
        if draft_id:
            update_draft(draft_id, status="correction_failed", failure_reason=error)
        return {"status": "failed", "error": error}

    ok, reason = validate_approval_token(
        approval_token, case_id=case_id, field=field, new_value=new_value
    )
    if not ok:
        return _fail(f"token validation failed: {reason}")

    field = normalize_field(field)
    before = effective_modern_record(case_id).get(field)
    result = apply_correction(case_id, field, new_value, approval_token)
    if result.get("status") != "applied":
        return _fail(result.get("error", "unknown apply failure"))

    after = effective_modern_record(case_id).get(field)
    no_op = before == after  # honest flag (audit finding 8): approved and
    # in effect, but the effective value did not change
    _audit({
        "type": "correction_applied",
        "audit_entry_id": result["audit_entry_id"],
        "at": at,
        "approver": approver,
        "ticket_id": ticket_id,
        "case_id": case_id,
        "draft_id": draft_id or None,
        "field": field,
        "before": before,
        "after": after,
        "no_op": no_op,
    })
    if ticket_id:
        update_ticket(ticket_id, status="resolved", audit_entry_id=result["audit_entry_id"])
    if draft_id:
        update_draft(draft_id, status="applied", audit_entry_id=result["audit_entry_id"])
    return {
        "status": "applied",
        "audit_entry_id": result["audit_entry_id"],
        "ticket_id": ticket_id,
        "before": before,
        "after": after,
        "no_op": no_op,
    }
