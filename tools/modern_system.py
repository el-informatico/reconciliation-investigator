"""Modern-system access.

read_modern_system is an ordinary Strands tool (read-only, camelCase
schema, overlays applied corrections — read-your-writes).

apply_correction is a PLAIN FUNCTION and must stay one: it is never
decorated with @tool, never wrapped as a Strands tool, and never
appears in any Agent tools list (docs/build-contract.md §3/§4 — the
segregation-of-duties invariant). Its only legitimate caller is
orchestrator/correction_executor.py, which validates a signed
approval token before invoking it. In EVAL_MODE=1 it writes to the
runtime override store only; data/seed_transactions.json is provably
immutable under a correction (tests/test_gate_executor.py asserts the
sha256 before/after).
"""

import datetime as dt
import uuid

from strands import tool

from tools.seed_data import (
    effective_modern_record,
    normalize_field,
    require_eval_mode,
    write_override,
)


@tool
def read_modern_system(customer_id: str) -> dict:
    """Read one customer's record from the modern system.

    Returns the modern record (customerId, balance, status, lastUpdated),
    reflecting any corrections applied via the approval path.

    Args:
        customer_id: customer identifier, e.g. C-1001
    """
    require_eval_mode()
    return effective_modern_record(customer_id)


def apply_correction(customer_id: str, field: str, new_value, approval_token: str) -> dict:
    """Apply an approved correction to the modern system (PLAIN FUNCTION).

    Writes the corrected value to the runtime override store (EVAL_MODE=1)
    and returns {"status": "applied"|"failed", "audit_entry_id": str}.
    Token validation, single-use enforcement, and the full audit entry
    (who/when/what/before/after) belong to the caller — the correction
    executor; this function asserts only that a token was presented.
    """
    require_eval_mode()
    if not approval_token:
        return {"status": "failed", "audit_entry_id": None, "error": "missing approval token"}
    audit_entry_id = f"AUD-{uuid.uuid4().hex[:12]}"
    try:
        applied_at = dt.datetime.now(dt.timezone.utc).isoformat()
        write_override(customer_id, field, new_value, applied_at)
    except Exception as exc:  # surfaced by the executor, never retried here
        return {"status": "failed", "audit_entry_id": audit_entry_id, "error": str(exc)}
    return {"status": "applied", "audit_entry_id": audit_entry_id}
