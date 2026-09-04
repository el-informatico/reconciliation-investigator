"""Transaction search and event-log read tools (detector_investigator only)."""

from strands import tool

from tools.seed_data import load_seed, require_eval_mode

_SYSTEMS = ("legacy", "modern")


def _system_or_raise(system: str) -> str:
    if system not in _SYSTEMS:
        raise ValueError(f"system must be one of {list(_SYSTEMS)}, got {system!r}")
    return system


@tool
def search_transactions(customer_id: str, system: str, date_from: str, date_to: str) -> list[dict]:
    """Search a customer's transactions on one system within a date window.

    Args:
        customer_id: customer identifier, e.g. C-1001
        system: "legacy" or "modern"
        date_from: inclusive window start, ISO 8601 (e.g. 2026-08-01T00:00:00Z)
        date_to: inclusive window end, ISO 8601
    """
    require_eval_mode()
    _system_or_raise(system)
    per_customer = load_seed()["transactions"].get(customer_id)
    if per_customer is None:
        raise ValueError(f"unknown customer_id {customer_id!r}")
    rows = per_customer.get(system, [])
    return [
        dict(row)
        for row in rows
        if str(date_from) <= row["timestamp"] <= str(date_to)
    ]


@tool
def get_event_log(entity_id: str, system: str) -> list[dict]:
    """Read the event log for one entity (usually a customer) on one system.

    Args:
        entity_id: entity identifier, typically the customer_id (e.g. C-1001)
        system: "legacy" or "modern"
    """
    require_eval_mode()
    _system_or_raise(system)
    per_entity = load_seed()["event_log"].get(entity_id)
    if per_entity is None:
        raise ValueError(f"unknown entity_id {entity_id!r}")
    return [dict(row) for row in per_entity.get(system, [])]
