"""Draft/tracking tools (reporter only) — NO write access to either system.

draft_correction and create_case_ticket create records describing intent
and tracking only: they append to the gitignored runtime/ store and can
structurally never touch the legacy or modern system modules (they do
not import them and expose no write path at all).

2026-09-05 identity + hygiene pass: both tools now VALIDATE
deterministically at creation time (previously any string was stored —
the live store carries 44 invented case_id spellings, non-canonical
draft fields like legacy_deposit_amount, string-numeric and prose
values, and garbage draft links). Validation applies to NEW writes
only; existing runtime records are preserved evidence and are never
rewritten.

2026-09-06 diagnostics pass: every REJECTED (or otherwise failed) call
to either tool is also appended to runtime/rejected_calls.jsonl (see
REJECTED_CALLS_LOG below) BEFORE its exception propagates — such a
failure used to leave no trace of the call shape it rejected. That
store is write-only observability for humans: the gate, the executor,
and every approval/capability-token path never read it, and a log-write
failure is swallowed so diagnostics can never change a rejection
outcome.
"""

import datetime as dt
import json
import sys
import uuid

from strands import tool

from tools.seed_data import (
    canonical_case_id,
    effective_modern_record,
    normalize_field,
    require_eval_mode,
    runtime_path,
    validate_correction_value,
)


def _append_jsonl(name: str, record: dict) -> None:
    path = runtime_path(name)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def update_ticket(ticket_id: str, **fields) -> dict | None:
    """Update one ticket record in the runtime store (plain helper — not a
    Strands tool; used by the orchestrator's gate/executor path)."""
    path = runtime_path("tickets.jsonl")
    if not path.exists():
        return None
    updated = None
    out_lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("ticket_id") == ticket_id:
            record.update(fields)
            updated = record
        out_lines.append(json.dumps(record))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    return updated


def update_tickets_for_case(case_id: str, status: str, **fields) -> int:
    """Set the status of EVERY ticket for one case (reject/resolve close
    all open tickets — audit finding 5: re-invocation rounds accumulate
    tickets). Returns how many were updated."""
    path = runtime_path("tickets.jsonl")
    if not path.exists():
        return 0
    changed = 0
    out_lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("case_id") == case_id and record.get("status") == "open":
            record.update(fields, status=status)
            changed += 1
        out_lines.append(json.dumps(record))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    return changed


def update_draft(draft_id: str, **fields) -> dict | None:
    """Update one draft record (plain helper — draft lifecycle:
    pending_approval -> approved -> applied / correction_failed /
    rejected)."""
    path = runtime_path("drafts.jsonl")
    if not path.exists() or not draft_id:
        return None
    updated = None
    out_lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("draft_id") == draft_id:
            record.update(fields)
            updated = record
        out_lines.append(json.dumps(record))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    return updated


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


# --- rejected-call diagnostics (2026-09-06) --------------------------------
#
# The 2026-09-06 human-gate e2e Attempt-1 postmortem: a draft_correction
# call that never reached the gate left NO trace of the malformed shape
# it was rejected for, so the failure was undiagnosable in the moment.
# REJECTED_CALLS_LOG closes that gap for humans only — it is never an
# input to any decision (pinned by tests/test_rejected_call_diagnostics.py).

REJECTED_CALLS_LOG = "rejected_calls.jsonl"
_TOOL_COMPONENT = "reporter"  # sole holder of these tools (agents/reporter.py)
_MAX_LOGGED_CHARS = 500
_MAX_LOGGED_LIST_ITEMS = 20
# Parameter names that would never legitimately appear in these calls'
# arguments; a model-fabricated match is masked, never copied into the log.
_SECRET_KEY_MARKERS = ("key", "token", "secret", "password", "credential", "authorization")


def _clip(text: str) -> str:
    """Bound free text to _MAX_LOGGED_CHARS (validator messages embed the
    offending value, which a model can make arbitrarily long)."""
    text = str(text)
    if len(text) <= _MAX_LOGGED_CHARS:
        return text
    return text[:_MAX_LOGGED_CHARS] + f"<truncated, {len(text)} chars total>"


def _redact_call_args(args: dict) -> dict:
    """A copy of a rejected call's arguments that is safe for the
    diagnostic log and always JSON-serializable: secret-looking keys are
    masked, over-long strings clipped, over-long lists capped, and
    non-JSON scalars reduced to their repr (clipped)."""

    def redact(value):
        if isinstance(value, dict):
            out = {}
            for key, item in value.items():
                if any(marker in str(key).lower() for marker in _SECRET_KEY_MARKERS):
                    out[key] = f"<REDACTED:{key}>"
                else:
                    out[key] = redact(item)
            return out
        if isinstance(value, (list, tuple)):
            items = [redact(item) for item in value[:_MAX_LOGGED_LIST_ITEMS]]
            if len(value) > _MAX_LOGGED_LIST_ITEMS:
                items.append(f"<{len(value)} items total>")
            return items
        if isinstance(value, str):
            return _clip(value)
        if isinstance(value, (bool, int, float)) or value is None:
            return value
        return _clip(repr(value))

    return redact(args)


def _log_rejected_call(tool_name: str, args: dict, reason: str) -> None:
    """Record one rejected draft/ticket call, immediately BEFORE the
    rejection propagates (see the module note: observability only, never
    an input to the gate/executor/approval paths)."""
    try:
        _append_jsonl(REJECTED_CALLS_LOG, {
            "timestamp": _now(),
            "component": _TOOL_COMPONENT,
            "tool": tool_name,
            "args": _redact_call_args(args),
            "reason": _clip(reason),
        })
    except Exception as exc:
        # Diagnostics must never alter behavior: the call stays rejected
        # with its original error even when the diagnostic write fails.
        try:
            print(f"[rejected-calls] diagnostic log write failed: {exc!r}", file=sys.stderr)
        except Exception:
            pass


def get_draft(draft_id: str) -> dict | None:
    """Read one draft record (plain helper — used by the gate/executor
    path; returns the record or None for unknown/empty ids)."""
    if not draft_id:
        return None
    path = runtime_path("drafts.jsonl")
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        record = json.loads(line)
        if record.get("draft_id") == draft_id:
            return record
    return None


def get_ticket(ticket_id: str) -> dict | None:
    """Read one ticket record (plain helper — same contract as get_draft)."""
    if not ticket_id:
        return None
    path = runtime_path("tickets.jsonl")
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        record = json.loads(line)
        if record.get("ticket_id") == ticket_id:
            return record
    return None


@tool
def draft_correction(customer_id: str, field: str, current_value, proposed_value, justification: str) -> dict:
    """Create a DRAFT correction record (pending_approval). Applies nothing.

    Every argument is validated deterministically; malformed proposals
    are rejected with a ValueError naming the exact problem, so the
    human gate only ever sees canonical, coherent drafts.

    Args:
        customer_id: customer whose record the correction targets — the
          exact seeded id (e.g. C-1001); it IS the case identity, and
          invented spellings are rejected
        field: modern-system field to correct: exactly "balance" or
          "status" (corrections target the modern system's own fields;
          any other name is rejected)
        current_value: the live modern-system value observed during the
          investigation (a number for balance, e.g. 1250.00; "ACTIVE" or
          "SUSPENDED" for status). Must equal the current system value
        proposed_value: the corrected value the evidence supports (same
          type rules; plain numeric strings like "1500.00" are accepted
          and canonicalized to a number)
        justification: one paragraph tied to the evidence
    """
    received = {
        "customer_id": customer_id,
        "field": field,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "justification": justification,
    }
    try:
        require_eval_mode()
        customer_id = canonical_case_id(customer_id)
        field = normalize_field(field)
        current = validate_correction_value(field, current_value, label="current_value")
        proposed = validate_correction_value(field, proposed_value, label="proposed_value")
        live = effective_modern_record(customer_id).get(field)
        if current != live:
            raise ValueError(
                f"current_value {current!r} does not match the live modern-system "
                f"{field} {live!r} for {customer_id}: re-read the record and draft "
                f"the value you actually observed"
            )
        if proposed == current:
            raise ValueError(
                f"proposed_value equals current_value {current!r} — a no-op: a "
                f"correction draft must change the value; if no change is "
                f"needed, do not draft a correction"
            )
        draft_id = f"DRF-{uuid.uuid4().hex[:12]}"
        _append_jsonl("drafts.jsonl", {
            "draft_id": draft_id,
            "customer_id": customer_id,
            "field": field,
            "current_value": current,
            "proposed_value": proposed,
            "justification": justification,
            "status": "pending_approval",
            "created_at": _now(),
        })
        return {"draft_id": draft_id, "status": "pending_approval"}
    except Exception as exc:
        # Diagnostics only (REJECTED_CALLS_LOG above): record the call as
        # received, then propagate the original error, untouched. The try
        # spans the whole call, so even a post-validation crash (e.g. a
        # model-emitted null dying at the store append) leaves a trace.
        _log_rejected_call("draft_correction", received, str(exc))
        raise


@tool
def create_case_ticket(case_id: str, summary: str, root_cause: str, confidence: float, evidence_refs: list[str], correction_draft_id: str | None) -> dict:
    """Create a tracking ticket for an investigation (always called, correction or not).

    Args:
        case_id: MUST be exactly the customer_id under investigation
          (e.g. "C-1001") — one investigated customer is one case, and
          the case identity is never invented: any other spelling is
          rejected with the canonical value in the error
        summary: human-readable case summary from the case file
        root_cause: classifier root-cause label
        confidence: classifier confidence, 0.0-1.0
        evidence_refs: citations to specific transactions/events
        correction_draft_id: the draft_id returned by draft_correction
          for THIS case, or None — unknown ids, placeholder strings, and
          drafts belonging to a different case are rejected
    """
    received = {
        "case_id": case_id,
        "summary": summary,
        "root_cause": root_cause,
        "confidence": confidence,
        "evidence_refs": evidence_refs,
        "correction_draft_id": correction_draft_id,
    }
    try:
        require_eval_mode()
        canonical = canonical_case_id(case_id)
        if str(case_id) != canonical:
            raise ValueError(
                f"case_id must be exactly the customer_id under investigation "
                f"(canonical: {canonical!r}), got {case_id!r}"
            )
        if correction_draft_id is not None:
            draft = get_draft(correction_draft_id)
            if draft is None:
                raise ValueError(
                    f"correction_draft_id {correction_draft_id!r} matches no draft: "
                    f"pass the draft_id returned by draft_correction for this case, "
                    f"or None (never placeholder strings like 'None' or '')"
                )
            if draft.get("customer_id") != canonical:
                raise ValueError(
                    f"correction_draft_id {correction_draft_id!r} belongs to case "
                    f"{draft.get('customer_id')!r}, not {canonical!r}: a ticket "
                    f"links only its own case's drafts"
                )
        ticket_id = f"TCK-{uuid.uuid4().hex[:12]}"
        _append_jsonl("tickets.jsonl", {
            "ticket_id": ticket_id,
            "case_id": canonical,
            "summary": summary,
            "root_cause": root_cause,
            "confidence": confidence,
            "evidence_refs": list(evidence_refs),
            "correction_draft_id": correction_draft_id,
            "status": "open",
            "created_at": _now(),
        })
        return {"ticket_id": ticket_id}
    except Exception as exc:
        # Diagnostics only (REJECTED_CALLS_LOG above): record the call as
        # received, then propagate the original error, untouched. The try
        # spans the whole call, so even a post-validation crash (e.g. a
        # model-emitted null dying at list(evidence_refs)) leaves a trace.
        _log_rejected_call("create_case_ticket", received, str(exc))
        raise
