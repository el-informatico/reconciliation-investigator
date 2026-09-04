"""human_gate — orchestrator-level approval pause-point (§2.4).

NOT an LLM node. Programmatic interface: a GateDecision comes in (from
the approval UI in a later pass, or from tests/callers directly), the
gate audits every decision and, on APPROVE, issues a signed
approval_token scoped to one (case_id, field, new_value), single-use
and expiring.

Token scheme (recorded decision): HMAC-SHA256 over the canonical JSON
payload {case_id, field, new_value, exp, jti}. Key source: when
EVAL_MODE=1 the key is the committed, deliberately NON-SECRET dev
constant below (nothing in EVAL_MODE is a secret — the never-committed
clause applies to the production key, which MUST come from env
CORRECTION_TOKEN_SECRET and is never defaulted)."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import uuid
from dataclasses import dataclass
from enum import Enum

import tools.seed_data as seed_data

DEFAULT_TTL_SECONDS = 600

# Committed ON PURPOSE and not a secret: EVAL_MODE-only dev key.
EVAL_MODE_DEV_KEY = "eval-mode-dev-key-not-a-secret"


class GateAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_MORE_INFO = "request_more_info"


@dataclass
class GateDecision:
    action: GateAction
    approver: str = "human"
    reason: str = ""  # REJECT: the human's reason (audited)
    note: str = ""  # REQUEST_MORE_INFO: becomes the investigation_hint


def _token_key() -> bytes:
    if os.environ.get("EVAL_MODE") == "1":
        return EVAL_MODE_DEV_KEY.encode()
    key = os.environ.get("CORRECTION_TOKEN_SECRET")
    if not key:
        raise RuntimeError(
            "CORRECTION_TOKEN_SECRET is required outside EVAL_MODE (the "
            "production signing key is never defaulted and never committed)"
        )
    return key.encode()


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _now_epoch() -> float:
    return dt.datetime.now(dt.timezone.utc).timestamp()


def issue_approval_token(
    case_id: str,
    field: str,
    new_value,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    """Signed, single-use, expiring token bound to exactly this correction."""
    field = seed_data.normalize_field(field)
    payload = {
        "case_id": case_id,
        "field": field,
        "new_value": new_value,
        "exp": _now_epoch() + ttl_seconds,
        "jti": uuid.uuid4().hex,
    }
    body = base64.urlsafe_b64encode(_canonical(payload).encode()).decode()
    signature = hmac.new(_token_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def validate_approval_token(
    token: str,
    *,
    case_id: str,
    field: str,
    new_value,
    consume: bool = True,
) -> tuple[bool, str]:
    """Validate signature, expiry, scope, and single-use; on success mark
    the token's jti consumed. Returns (ok, reason)."""
    if not token or token.count(".") != 1:
        return False, "malformed token"
    body, signature = token.split(".")
    expected = hmac.new(_token_key(), body.encode(), hashlib.sha256).hexdigest()
    try:
        if not hmac.compare_digest(signature, expected):
            return False, "invalid signature (forged or altered token)"
    except TypeError:
        # Non-ASCII signature (audit finding 7): reject as malformed, never
        # crash the executor out of its own audit path.
        return False, "malformed token"
    try:
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
    except (ValueError, json.JSONDecodeError):
        return False, "malformed token payload"
    if float(payload.get("exp", 0)) < _now_epoch():
        return False, "token expired"
    if payload.get("case_id") != case_id:
        return False, f"token scoped to case {payload.get('case_id')!r}, executed against {case_id!r}"
    try:
        field = seed_data.normalize_field(field)
    except ValueError as exc:
        return False, str(exc)
    if payload.get("field") != field:
        return False, f"token scoped to field {payload.get('field')!r}, executed against {field!r}"
    if _canonical(payload.get("new_value")) != _canonical(new_value):
        return False, "token scoped to a different correction value"
    jti = str(payload.get("jti", ""))
    if not jti:
        return False, "token missing jti"
    consumed_path = seed_data.runtime_path("consumed_tokens.jsonl")
    if consumed_path.exists():
        consumed = {line.strip() for line in consumed_path.read_text(encoding="utf-8").splitlines()}
        if jti in consumed:
            return False, "token already consumed (single-use)"
    if consume:
        with open(consumed_path, "a", encoding="utf-8") as f:
            f.write(jti + "\n")
    return True, "valid"


def audit_gate_event(entry: dict) -> None:
    """Append one gate/audit event to the runtime audit log (public: the
    orchestrator composition uses it for round-exhaustion events)."""
    path = seed_data.runtime_path("audit_log.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


_audit = audit_gate_event


def _close_ticket(ticket_id: str, status: str, extra: dict | None = None) -> None:
    from tools.case_management import update_ticket

    update_ticket(ticket_id, status=status, **(extra or {}))


def latest_pending_draft(case_id: str) -> dict | None:
    path = seed_data.runtime_path("drafts.jsonl")
    if not path.exists():
        return None
    draft = None
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("customer_id") == case_id and record.get("status") == "pending_approval":
            draft = record
    return draft


def latest_ticket(case_id: str) -> dict | None:
    path = seed_data.runtime_path("tickets.jsonl")
    if not path.exists():
        return None
    ticket = None
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("case_id") == case_id:
            ticket = record
    return ticket


def run_human_gate(
    case_file: str,
    correction_draft: dict | None,
    decision: GateDecision,
    case_id: str = "",
) -> dict:
    """§2.4 pause-point. Every decision is audited (with the case_id).
    APPROVE issues the scoped token and marks the draft approved (it can
    never be re-approved by a later run — audit finding 5); REJECT closes
    the case's OPEN tickets as rejected with the human's reason (audit
    finding 4: rejection is case-linked even when no draft exists);
    REQUEST_MORE_INFO returns the note as investigation_hint for
    re-invoking detector_investigator."""
    at = dt.datetime.now(dt.timezone.utc).isoformat()
    if decision.action is GateAction.APPROVE:
        if not correction_draft:
            raise ValueError("cannot approve: no pending correction draft for this case")
        token = issue_approval_token(
            correction_draft["customer_id"],
            correction_draft["field"],
            correction_draft["proposed_value"],
        )
        _audit({
            "type": "gate_approval",
            "at": at,
            "approver": decision.approver,
            "case_id": case_id or correction_draft["customer_id"],
            "field": correction_draft["field"],
            "new_value": correction_draft["proposed_value"],
        })
        from tools.case_management import update_draft

        update_draft(correction_draft["draft_id"], status="approved", approved_at=at)
        return {"action": GateAction.APPROVE, "approval_token": token, "draft": correction_draft}

    if decision.action is GateAction.REJECT:
        _audit({
            "type": "gate_rejection",
            "at": at,
            "approver": decision.approver,
            "case_id": case_id,
            "reason": decision.reason,
        })
        closed = 0
        if case_id:
            from tools.case_management import update_tickets_for_case

            closed = update_tickets_for_case(
                case_id, "rejected", rejection_reason=decision.reason
            )
        return {
            "action": GateAction.REJECT,
            "reason": decision.reason,
            "tickets_closed": closed,
        }

    # REQUEST_MORE_INFO
    _audit({
        "type": "gate_more_info",
        "at": at,
        "approver": decision.approver,
        "case_id": case_id,
        "note": decision.note,
    })
    return {"action": GateAction.REQUEST_MORE_INFO, "investigation_hint": decision.note}
