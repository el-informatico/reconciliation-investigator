"""Draft/tracking tools (reporter only) — NO write access to either system.

draft_correction and create_case_ticket create records describing intent
and tracking only: they append to the gitignored runtime/ store and can
structurally never touch the legacy or modern system modules (they do
not import them and expose no write path at all).
"""

import datetime as dt
import json
import uuid

from strands import tool

from tools.seed_data import require_eval_mode, runtime_path


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


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@tool
def draft_correction(customer_id: str, field: str, current_value, proposed_value, justification: str) -> dict:
    """Create a DRAFT correction record (pending_approval). Applies nothing.

    Args:
        customer_id: customer whose record the correction targets
        field: modern-system field to correct (e.g. balance or status)
        current_value: the value observed during investigation
        proposed_value: the corrected value the evidence supports
        justification: one paragraph tied to the evidence
    """
    require_eval_mode()
    draft_id = f"DRF-{uuid.uuid4().hex[:12]}"
    _append_jsonl("drafts.jsonl", {
        "draft_id": draft_id,
        "customer_id": customer_id,
        "field": field,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "justification": justification,
        "status": "pending_approval",
        "created_at": _now(),
    })
    return {"draft_id": draft_id, "status": "pending_approval"}


@tool
def create_case_ticket(case_id: str, summary: str, root_cause: str, confidence: float, evidence_refs: list[str], correction_draft_id) -> dict:
    """Create a tracking ticket for an investigation (always called, correction or not).

    Args:
        case_id: the investigation case identifier (customer_id-scoped)
        summary: human-readable case summary from the case file
        root_cause: classifier root-cause label
        confidence: classifier confidence, 0.0-1.0
        evidence_refs: citations to specific transactions/events
        correction_draft_id: draft id if a correction was drafted, else None
    """
    require_eval_mode()
    ticket_id = f"TCK-{uuid.uuid4().hex[:12]}"
    _append_jsonl("tickets.jsonl", {
        "ticket_id": ticket_id,
        "case_id": case_id,
        "summary": summary,
        "root_cause": root_cause,
        "confidence": confidence,
        "evidence_refs": list(evidence_refs),
        "correction_draft_id": correction_draft_id,
        "status": "open",
        "created_at": _now(),
    })
    return {"ticket_id": ticket_id}
