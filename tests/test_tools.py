"""Unit tests for tools/ against the frozen seed data (AC2).

Runtime isolation: tools.seed_data.RUNTIME_DIR is monkeypatched to a
tmp dir so tests never touch the real runtime/ store.
"""

import hashlib
import json
import types
from pathlib import Path

import pytest

import tools.seed_data as seed_data
from tools.case_management import create_case_ticket, draft_correction
from tools.legacy_system import read_legacy_system
from tools.modern_system import apply_correction, read_modern_system
from tools.transactions import get_event_log, search_transactions

SEED = seed_data.SEED_PATH


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_MODE", "1")
    monkeypatch.setattr(seed_data, "RUNTIME_DIR", tmp_path)
    return tmp_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_eval_mode_guard_blocks_real_system_mode(monkeypatch) -> None:
    monkeypatch.delenv("EVAL_MODE", raising=False)
    with pytest.raises(RuntimeError, match="EVAL_MODE"):
        read_legacy_system("C-1001")


def test_legacy_schema_is_upper_snake() -> None:
    record = read_legacy_system("C-1001")
    assert record == {
        "CUSTOMER_ID": "C-1001",
        "BALANCE": 1500.00,
        "STATUS": "ACTIVE",
        "LAST_UPDATED": "2026-08-25T22:10:00Z",
    }


def test_modern_schema_is_camel_case() -> None:
    record = read_modern_system("C-1001")
    assert record == {
        "customerId": "C-1001",
        "balance": 1250.00,
        "status": "ACTIVE",
        "lastUpdated": "2026-08-20T09:00:00Z",
    }


def test_unknown_customer_raises_on_both_systems() -> None:
    with pytest.raises(ValueError, match="unknown customer_id"):
        read_legacy_system("C-9999")
    with pytest.raises(ValueError, match="unknown customer_id"):
        read_modern_system("C-9999")


def test_search_filters_by_system_and_inclusive_window() -> None:
    # C-1001 legacy: one CHARGE (Aug 18) + one REVERSAL (Aug 25).
    rows = search_transactions("C-1001", "legacy", "2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
    assert [r["transaction_id"] for r in rows] == ["L-TXN-90002"]
    assert rows[0]["type"] == "REVERSAL"
    assert rows[0]["related_transaction_id"] == "L-TXN-90001"
    # Inclusive bounds: exact-timestamp window matches that row only.
    rows = search_transactions("C-1001", "legacy", "2026-08-18T14:32:00Z", "2026-08-18T14:32:00Z")
    assert [r["transaction_id"] for r in rows] == ["L-TXN-90001"]
    # Modern side of the same case never got the reversal.
    rows = search_transactions("C-1001", "modern", "2026-08-01T00:00:00Z", "2026-08-31T00:00:00Z")
    assert [r["transaction_id"] for r in rows] == ["M-TXN-90001"]


def test_search_duplicate_case_returns_both_modern_deposits() -> None:
    rows = search_transactions("C-1002", "modern", "2026-08-01T00:00:00Z", "2026-08-31T00:00:00Z")
    assert [r["transaction_id"] for r in rows] == ["M-TXN-90101", "M-TXN-90102"]
    assert all(r["type"] == "DEPOSIT" and r["amount"] == 180.00 for r in rows)


def test_search_rejects_unknown_system() -> None:
    with pytest.raises(ValueError, match="system"):
        search_transactions("C-1001", "warehouse", "2026-08-01T00:00:00Z", "2026-08-31T00:00:00Z")


def test_event_log_per_system_and_sync_lag_evidence() -> None:
    legacy = get_event_log("C-1003", "legacy")
    modern = get_event_log("C-1003", "modern")
    assert [e["event_type"] for e in legacy] == ["BATCH_EXPORT_QUEUED"]
    assert legacy[0]["payload"]["batch_window"] == "01:00-02:00Z"
    assert [e["event_type"] for e in modern] == ["BATCH_SYNC_SCHEDULED"]
    assert modern[0]["payload"]["scheduled_for"] == "2026-08-29T01:30:00Z"


def test_event_log_unknown_entity_raises() -> None:
    with pytest.raises(ValueError, match="unknown entity_id"):
        get_event_log("C-9999", "legacy")


def test_draft_and_ticket_write_only_to_runtime_store() -> None:
    draft = draft_correction("C-1001", "balance", 1500.00, 1250.00, "reversal not propagated")
    assert draft["status"] == "pending_approval"
    assert draft["draft_id"].startswith("DRF-")
    ticket = create_case_ticket(
        "C-1001", "summary", "REVERSAL_NOT_PROPAGATED", 0.9,
        ["L-TXN-90002"], draft["draft_id"],
    )
    assert ticket["ticket_id"].startswith("TCK-")
    drafts = (seed_data.RUNTIME_DIR / "drafts.jsonl").read_text().splitlines()
    tickets = (seed_data.RUNTIME_DIR / "tickets.jsonl").read_text().splitlines()
    assert json.loads(drafts[0])["draft_id"] == draft["draft_id"]
    assert json.loads(tickets[0])["ticket_id"] == ticket["ticket_id"]
    assert json.loads(tickets[0])["status"] == "open"
    # Structural no-write: no overrides/system state was created.
    assert not (seed_data.RUNTIME_DIR / "overrides.json").exists()


def test_apply_correction_is_a_plain_function_never_a_strands_tool() -> None:
    # AC2/§4: if this ever becomes a DecoratedFunctionTool, the guard's
    # grep could pass while the tool is nonetheless registrable — fail here.
    assert type(apply_correction) is types.FunctionType
    import strands.tools.decorator as decorator
    assert not isinstance(apply_correction, decorator.DecoratedFunctionTool)


def test_apply_correction_requires_a_token() -> None:
    result = apply_correction("C-1001", "balance", 1250.00, "")
    assert result["status"] == "failed"
    assert "approval token" in result["error"]


def test_apply_correction_rejects_unknown_field() -> None:
    result = apply_correction("C-1001", "nickname", "x", "tok")
    assert result["status"] == "failed"
    assert "unknown field" in result["error"]


def test_apply_correction_overlays_are_read_your_writes_and_seed_is_immutable() -> None:
    before_sha = _sha256(SEED)
    result = apply_correction("C-1001", "balance", 1250.00, "signed-token-for-test")
    assert result["status"] == "applied"
    assert result["audit_entry_id"].startswith("AUD-")
    # Read-your-writes: the modern record reflects the correction and its
    # application time; the legacy record is untouched.
    record = read_modern_system("C-1001")
    assert record["balance"] == 1250.00
    assert record["lastUpdated"] >= "2026-09-04"
    legacy = read_legacy_system("C-1001")
    assert legacy["BALANCE"] == 1500.00
    # AC2: the frozen seed file is byte-identical across a correction.
    assert _sha256(SEED) == before_sha
