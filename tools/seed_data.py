"""Shared data access for tools/ (EVAL_MODE=1: seed JSON + runtime stores).

EVAL_MODE=1 is the only implemented mode in this pass: tools read
data/seed_transactions.json and write ONLY to the gitignored runtime/
directory (drafts, tickets, correction overrides, audit log). The seed
file itself is never mutated — a correction records an override that
read tools layer on top (read-your-writes), so the correction
executor's before/after audit values are real, observed values.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = REPO_ROOT / "data" / "seed_transactions.json"
# Tests monkeypatch this to a tmp dir; nothing else may hardcode it.
RUNTIME_DIR = REPO_ROOT / "runtime"

# Corrections target the modern system's own record fields (README: the
# write tool "writes to the modern system"); accepted case-insensitively.
MODERN_FIELDS = {"balance", "status"}


def require_eval_mode() -> None:
    """Real-system integrations are out of scope for this pass."""
    if os.environ.get("EVAL_MODE") != "1":
        raise RuntimeError(
            "EVAL_MODE is not 1: real-system access is not implemented in "
            "this pass (docs/build-contract.md §3 — set EVAL_MODE=1 to read "
            "from data/seed_transactions.json)"
        )


@lru_cache(maxsize=1)
def _load_seed() -> dict:
    with open(SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_seed() -> dict:
    """Seed data (cached; the file is frozen spec — never mutated)."""
    return _load_seed()


def runtime_path(name: str) -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / name


def normalize_field(field: str) -> str:
    normalized = str(field).strip().lower()
    if normalized not in MODERN_FIELDS:
        raise ValueError(
            f"unknown field {field!r}: corrections target the modern "
            f"system's own fields {sorted(MODERN_FIELDS)}"
        )
    return normalized


def canonical_case_id(customer_id: str) -> str:
    """The single deterministic case identity: one investigated customer
    = one case = the customer_id itself, validated against the seed.
    Never a model-chosen free string — the 2026-09-05 identity audit
    measured 44 distinct LLM-invented case_id spellings across 59 live
    tickets, which made the gate's draft/ticket lookups unsatisfiable
    for 43 of them."""
    canonical = str(customer_id).strip()
    modern = load_seed()["modern_system"]
    if canonical not in modern:
        raise ValueError(
            f"unknown case_id/customer_id {customer_id!r}: the case "
            f"identity is exactly one of the seeded customers {sorted(modern)}"
        )
    return canonical


def status_values() -> tuple[str, ...]:
    """The closed enum of status values a correction may set, derived
    from the frozen seed's systems of record — BOTH systems: a
    correction legitimately sets a value the modern system has not shown
    yet (case 4: modern says ACTIVE, the override truth is SUSPENDED,
    which only the legacy record carries), so deriving from modern alone
    would make the correct fix inexpressible. The whitelist follows the
    data, never a second list to keep in sync."""
    seed = load_seed()
    values = {str(record["status"]) for record in seed["modern_system"].values()}
    values |= {str(record["STATUS"]) for record in seed["legacy_system"].values()}
    return tuple(sorted(values))


# Exactly a plain decimal number ("1500.00", "-250", "350.50") — no
# thousands separators, currency symbols, units, or prose. The live
# reporter emits numeric strings, so these are ACCEPTED and canonicalized
# to float; everything else is a deterministic rejection.
_PLAIN_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def validate_correction_value(field: str, value, *, label: str):
    """Deterministic value contract for correction drafts (2026-09-05
    hygiene pass). balance: a JSON number, or a string that is exactly a
    plain decimal number -> canonicalized to float. status: one of the
    seed's enum values, case-insensitively -> canonicalized to upper.
    Booleans, prose, and partially-numeric strings are REJECTED — a
    malformed proposal fails here, at draft time; it is never silently
    coerced into something the executor would apply."""
    if field == "balance":
        if isinstance(value, bool):
            raise ValueError(f"{label} for balance must be a number, got boolean {value!r}")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and _PLAIN_NUMBER.fullmatch(value.strip()):
            return float(value.strip())
        raise ValueError(
            f"{label} for balance must be a plain number (e.g. 1500.00), got {value!r}"
        )
    if field == "status":
        allowed = status_values()
        if isinstance(value, str) and value.strip().upper() in allowed:
            return value.strip().upper()
        raise ValueError(f"{label} for status must be one of {list(allowed)}, got {value!r}")
    raise ValueError(
        f"unknown field {field!r}: corrections target the modern "
        f"system's own fields {sorted(MODERN_FIELDS)}"
    )


def _read_overrides() -> dict:
    path = runtime_path("overrides.json")
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_override(customer_id: str, field: str, new_value, applied_at_iso: str) -> None:
    """Record a correction override in the runtime store (seed untouched)."""
    field = normalize_field(field)
    overrides = _read_overrides()
    entry = overrides.setdefault(customer_id, {})
    entry[field] = new_value
    entry.setdefault("_applied_at", {})[field] = applied_at_iso
    with open(runtime_path("overrides.json"), "w", encoding="utf-8") as f:
        json.dump(overrides, f, indent=2)


def effective_modern_record(customer_id: str) -> dict:
    """Modern-system record with the overrides overlay applied (read-your-
    writes); lastUpdated reflects the latest applied override."""
    seed = load_seed()["modern_system"].get(customer_id)
    if seed is None:
        raise ValueError(f"unknown customer_id {customer_id!r} in modern system")
    record = dict(seed)
    overrides = _read_overrides().get(customer_id)
    if not overrides:
        return record
    last_updated = record.get("lastUpdated")
    for field, stamp in overrides.get("_applied_at", {}).items():
        if field in record:
            record[field] = overrides[field]
        if stamp and (last_updated is None or stamp > last_updated):
            last_updated = stamp
    record["lastUpdated"] = last_updated
    return record
