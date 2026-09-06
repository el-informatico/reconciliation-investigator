"""2026-09-05 identity + hygiene regression tests (draft-side contract):
seed_data.canonical_case_id as the single case identity; draft_correction
deterministic validation (canonical customer, canonical modern field,
typed/canonicalized values, coherence against the live modern record,
no-op refusal); create_case_ticket identity and draft-link validation
(None | real same-case DRF- id, stored verbatim); get_draft/get_ticket
readback. Raw legacy records in the store are preserved evidence:
validation guards NEW writes only and never rewrites history."""

import json

import pytest

import tools.seed_data as seed_data
from tools.case_management import (
    create_case_ticket,
    draft_correction,
    get_draft,
    get_ticket,
)

# Seed truth (data/seed_transactions.json, modern system).
_LIVE_BALANCE = {
    "C-1001": 1250.00,
    "C-1002": 1160.00,
    "C-1003": 4050.00,
    "C-1004": 2100.00,
    "C-1005": 350.50,
}


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_MODE", "1")
    monkeypatch.setattr(seed_data, "RUNTIME_DIR", tmp_path)
    return tmp_path


def _records(name: str) -> list[dict]:
    path = seed_data.RUNTIME_DIR / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_raw_draft(record: dict) -> None:
    """Append a record to drafts.jsonl DIRECTLY, bypassing draft_correction
    (simulates pre-validation / legacy rows in the live runtime store)."""
    path = seed_data.RUNTIME_DIR / "drafts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _draft_for(customer_id: str) -> dict:
    balance = _LIVE_BALANCE[customer_id]
    return draft_correction(customer_id, "balance", balance, balance + 250.00, "reversal evidence")


# --- canonical_case_id: the single deterministic case identity ---


def test_canonical_case_id_round_trips_every_seeded_customer() -> None:
    for customer_id in ("C-1001", "C-1002", "C-1003", "C-1004", "C-1005"):
        assert seed_data.canonical_case_id(customer_id) == customer_id


def test_canonical_case_id_rejects_unknown_invented_and_empty_ids() -> None:
    # Match "customer": canonical_case_id's own message names the
    # customer ("unknown customer_id ...").
    for bad in ("C-9999", "C-1001-001", ""):
        with pytest.raises(ValueError, match="customer"):
            seed_data.canonical_case_id(bad)


# --- draft_correction: deterministic draft-time validation ---


def test_draft_correction_stores_canonicalized_numeric_values() -> None:
    draft = draft_correction("C-1001", "balance", 1250.00, 1500.00, "reversal evidence")
    assert draft["draft_id"].startswith("DRF-")
    assert draft["status"] == "pending_approval"
    stored = get_draft(draft["draft_id"])
    assert stored["customer_id"] == "C-1001"
    assert stored["field"] == "balance"
    assert stored["current_value"] == 1250.0  # typed float, never a string
    assert stored["proposed_value"] == 1500.0
    assert stored["status"] == "pending_approval"
    on_disk = _records("drafts.jsonl")
    assert on_disk and on_disk[0]["draft_id"] == draft["draft_id"]
    assert on_disk[0]["current_value"] == 1250.0
    assert on_disk[0]["proposed_value"] == 1500.0


def test_draft_correction_canonicalizes_strict_numeric_strings() -> None:
    # The live reporter emits numeric STRINGS; exactly-plain decimals are
    # accepted and canonicalized to floats, everything else is rejected.
    draft = draft_correction("C-1001", "balance", "1250.00", "1500.0", "numeric strings")
    stored = get_draft(draft["draft_id"])
    assert stored["current_value"] == 1250.0
    assert stored["proposed_value"] == 1500.0
    assert isinstance(stored["current_value"], float)
    assert isinstance(stored["proposed_value"], float)


def test_draft_correction_rejects_unknown_and_invented_customer() -> None:
    # Match "customer" (contract's alternative; canonical_case_id names
    # the customer in the message).
    for bad in ("C-9999", "C-1001-001"):
        with pytest.raises(ValueError, match="customer"):
            draft_correction(bad, "balance", 1.0, 2.0, "x")
    assert _records("drafts.jsonl") == []  # rejected BEFORE any append


def test_draft_correction_rejects_the_three_live_noncanonical_fields() -> None:
    # The exact field spellings measured in the 2026-09-05 live-store
    # audit (all C-1005 drafts): legacy-side names and transaction-
    # annotated names are schema violations, not modern-field corrections.
    for bad_field in (
        "legacy_deposit_amount",
        "transaction_amount (L-TXN-90301)",
        "deposit_amount (transaction MTXN-20230901-002)",
    ):
        with pytest.raises(ValueError, match="unknown field"):
            draft_correction("C-1005", bad_field, 350.50, 305.50, "x")
    assert _records("drafts.jsonl") == []


def test_draft_correction_rejects_prose_and_boolean_values() -> None:
    # Stronger match "current_value" (contract also allows plain
    # "value"): the live prose artifact named the observed value.
    with pytest.raises(ValueError, match="current_value"):
        draft_correction("C-1001", "balance", "Modern balance is $250 lower", "1500.00", "x")
    # bool is an int subclass in Python — must be rejected as a value
    # type, never coerced to 1.0.
    with pytest.raises(ValueError, match="value"):
        draft_correction("C-1001", "balance", 1250.00, True, "x")
    assert _records("drafts.jsonl") == []


def test_draft_correction_rejects_status_values_outside_the_seed_enum() -> None:
    # Stronger match "status" (contract also allows "value"): the enum
    # is derived from the seed — only ACTIVE and SUSPENDED exist.
    with pytest.raises(ValueError, match="status"):
        draft_correction("C-1004", "status", "ACTIVE", "FROZEN", "x")
    assert _records("drafts.jsonl") == []


def test_draft_correction_rejects_current_value_incoherent_with_live_record() -> None:
    # Stronger match "current" (contract also allows "live"): the draft
    # must quote what the modern system actually holds (C-1001: 1250.00).
    with pytest.raises(ValueError, match="current"):
        draft_correction("C-1001", "balance", 999.00, 1500.00, "x")
    assert _records("drafts.jsonl") == []


def test_draft_correction_rejects_noop_proposal() -> None:
    # Contract sanctions any of the three phrasings; alternation accepts
    # all of them while the ValueError + no-append carry the weight.
    with pytest.raises(ValueError, match="no-op|no op|same"):
        draft_correction("C-1001", "balance", 1250.00, 1250.00, "x")
    assert _records("drafts.jsonl") == []


def test_draft_correction_accepts_status_correction_canonicalized() -> None:
    draft = draft_correction("C-1004", "status", "ACTIVE", "SUSPENDED", "manual override evidence")
    stored = get_draft(draft["draft_id"])
    assert stored["field"] == "status"
    assert stored["current_value"] == "ACTIVE"
    assert stored["proposed_value"] == "SUSPENDED"
    # Case-insensitive input canonicalizes to the enum's upper form.
    lower = draft_correction("C-1004", "status", "active", "suspended", "lowercase evidence")
    stored_lower = get_draft(lower["draft_id"])
    assert stored_lower["current_value"] == "ACTIVE"
    assert stored_lower["proposed_value"] == "SUSPENDED"


# --- create_case_ticket: identity + draft-link validation ---


def test_create_case_ticket_records_real_same_case_link_and_null_link_verbatim() -> None:
    draft = _draft_for("C-1001")
    linked = create_case_ticket(
        "C-1001", "summary", "REVERSAL_NOT_PROPAGATED", 0.92, ["L-TXN-90002"], draft["draft_id"]
    )
    unlinked = create_case_ticket(
        "C-1001", "summary", "REVERSAL_NOT_PROPAGATED", 0.92, ["L-TXN-90002"], None
    )
    assert linked["ticket_id"].startswith("TCK-")
    assert unlinked["ticket_id"].startswith("TCK-")
    tickets = _records("tickets.jsonl")
    # Real id stored verbatim; None stored as JSON null.
    assert [t["correction_draft_id"] for t in tickets] == [draft["draft_id"], None]
    assert all(t["case_id"] == "C-1001" and t["status"] == "open" for t in tickets)


def test_create_case_ticket_rejects_noncanonical_case_ids() -> None:
    # Invented spellings: contract match "case_id" or "canonical"
    # (alternation accepts either phrasing).
    for bad in ("C-1001-001", "CASE-C-1001", "C-1005-20230901"):
        with pytest.raises(ValueError, match="case_id|canonical"):
            create_case_ticket(bad, "s", "SYNC_LAG", 0.9, [], None)
    # Unknown customer: contract match "customer" or "case_id".
    with pytest.raises(ValueError, match="customer|case_id"):
        create_case_ticket("C-9999", "s", "SYNC_LAG", 0.9, [], None)
    assert _records("tickets.jsonl") == []  # rejected BEFORE any append


def test_create_case_ticket_rejects_garbage_and_unknown_draft_links() -> None:
    # The live store carried "None"/"null"/"" links on 11 tickets; the
    # wire contract is None | real same-case DRF- id, nothing else.
    for bad in ("", "None", "null", "DRF-doesnotexist"):
        with pytest.raises(ValueError, match="draft"):
            create_case_ticket("C-1001", "s", "SYNC_LAG", 0.9, [], bad)
    assert _records("tickets.jsonl") == []


def test_create_case_ticket_rejects_cross_case_draft_link() -> None:
    # Contract match "case" or "draft" (alternation accepts either).
    foreign = _draft_for("C-1002")
    with pytest.raises(ValueError, match="case|draft"):
        create_case_ticket("C-1001", "s", "SYNC_LAG", 0.9, [], foreign["draft_id"])
    assert _records("tickets.jsonl") == []


# --- get_draft / get_ticket readback ---


def test_get_draft_and_get_ticket_return_none_for_unknown_or_empty_ids() -> None:
    draft = _draft_for("C-1001")
    ticket = create_case_ticket("C-1001", "s", "SYNC_LAG", 0.9, [], draft["draft_id"])
    assert get_draft(draft["draft_id"])["draft_id"] == draft["draft_id"]
    assert get_ticket(ticket["ticket_id"])["ticket_id"] == ticket["ticket_id"]
    assert get_draft("DRF-doesnotexist") is None
    assert get_draft("") is None
    assert get_ticket("TCK-doesnotexist") is None
    assert get_ticket("") is None


def test_raw_legacy_draft_records_are_preserved_evidence() -> None:
    # Pre-validation rows in the live store are evidence: never
    # rewritten, never "repaired"; get_draft returns them verbatim.
    # Validation guards NEW writes only.
    raw = {
        "draft_id": "DRF-legacy000001",
        "customer_id": "C-1005",
        "field": "legacy_deposit_amount",
        "current_value": "50.00",
        "proposed_value": "95.0",
        "justification": "historical artifact",
        "status": "pending_approval",
        "created_at": "2026-09-04T12:00:00+00:00",
    }
    _append_raw_draft(raw)
    assert get_draft("DRF-legacy000001") == raw
