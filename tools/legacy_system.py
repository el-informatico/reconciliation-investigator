"""Legacy-system read tool (detector_investigator only; UPPER_SNAKE schema)."""

from strands import tool

from tools.seed_data import load_seed, require_eval_mode


@tool
def read_legacy_system(customer_id: str) -> dict:
    """Read one customer's record from the legacy system.

    Returns the legacy record (CUSTOMER_ID, BALANCE, STATUS, LAST_UPDATED).

    Args:
        customer_id: customer identifier, e.g. C-1001
    """
    require_eval_mode()
    record = load_seed()["legacy_system"].get(customer_id)
    if record is None:
        raise ValueError(f"unknown customer_id {customer_id!r} in legacy system")
    return dict(record)
