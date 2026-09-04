"""
Synthetic evaluation cases for Reconciliation Investigator.

Five discrepancy scenarios, one per known root cause category, each paired
with the tool trajectory the graph is expected to produce and the root
cause label the classifier is expected to reach.

Uses the real strands_evals.Case API (see:
https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/).
`input` carries what the graph's entry node (detector_investigator) needs
to start; `expected_trajectory` lists tool names in call order across the
WHOLE graph run (detector_investigator's read tools, then reporter's
draft/ticket tools) — not just one agent's calls.

Wiring these into an Experiment (task function that runs the actual Graph,
TrajectoryEvaluator + OutputEvaluator + ToolSelectionEvaluator) is
evals/run_evals.py, not this file.
"""

from strands_evals import Case

# Tool names as registered in the graph — must match tools/*.py exactly.
# apply_correction is intentionally absent from every case below: it is
# never given to any LLM agent (see docs/build-contract.md, section 4), so
# it can never legitimately appear in an expected_trajectory here. The
# assertion at the bottom of this file enforces that.
READ_TOOLS = ["read_legacy_system", "read_modern_system", "search_transactions", "get_event_log"]
DRAFT_TOOLS = ["draft_correction", "create_case_ticket"]

test_cases: list[Case] = [
    Case[dict, str](
        name="reversal-not-propagated",
        input={
            "customer_id": "C-1001",
            "seed_scenario": "reversal_not_propagated",
            "flagged_discrepancy": {"legacy_balance": 1500.00, "modern_balance": 1250.00},
        },
        expected_trajectory=[
            "read_legacy_system",
            "read_modern_system",
            "search_transactions",
            "get_event_log",
            "draft_correction",
            "create_case_ticket",
        ],
        expected_output="REVERSAL_NOT_PROPAGATED",
        metadata={
            "root_cause_category": "REVERSAL_NOT_PROPAGATED",
            "requires_correction": True,
            "expected_confidence_min": 0.7,
            "seed_data_ref": "data/seed_transactions.json#case-1001",
            "notes": "Classic case — a reversal posted in legacy never propagated to modern.",
        },
    ),
    Case[dict, str](
        name="duplicate-transaction",
        input={
            "customer_id": "C-1002",
            "seed_scenario": "duplicate_transaction",
            "flagged_discrepancy": {"legacy_balance": 980.00, "modern_balance": 1160.00},
        },
        # No get_event_log expected: the transaction search alone should
        # surface the duplicate, so calling get_event_log here is an
        # inefficiency the TrajectoryEvaluator should penalize.
        expected_trajectory=[
            "read_legacy_system",
            "read_modern_system",
            "search_transactions",
            "draft_correction",
            "create_case_ticket",
        ],
        expected_output="DUPLICATE_TRANSACTION",
        metadata={
            "root_cause_category": "DUPLICATE_TRANSACTION",
            "requires_correction": True,
            "expected_confidence_min": 0.7,
            "seed_data_ref": "data/seed_transactions.json#case-1002",
            "notes": "Same transaction_id processed twice in the modern system only.",
        },
    ),
    Case[dict, str](
        name="sync-lag-self-resolving",
        input={
            "customer_id": "C-1003",
            "seed_scenario": "sync_lag",
            "flagged_discrepancy": {"legacy_balance": 4200.00, "modern_balance": 4050.00},
        },
        # No draft_correction expected: this is the "agent shows judgment"
        # case — requires_correction is False, so it must stop short of
        # drafting a fix and only document the finding.
        expected_trajectory=[
            "read_legacy_system",
            "read_modern_system",
            "search_transactions",
            "get_event_log",
            "create_case_ticket",
        ],
        expected_output="SYNC_LAG",
        metadata={
            "root_cause_category": "SYNC_LAG",
            "requires_correction": False,
            "expected_confidence_min": 0.7,
            "seed_data_ref": "data/seed_transactions.json#case-1003",
            "notes": "Discrepancy falls inside the nightly batch window and will self-resolve. "
                     "No correction should be drafted — a wrong draft_correction call here is a failure.",
        },
    ),
    Case[dict, str](
        name="manual-override-not-reflected",
        input={
            "customer_id": "C-1004",
            "seed_scenario": "manual_override",
            "flagged_discrepancy": {"legacy_status": "SUSPENDED", "modern_status": "ACTIVE"},
        },
        expected_trajectory=[
            "read_legacy_system",
            "read_modern_system",
            "search_transactions",
            "get_event_log",
            "draft_correction",
            "create_case_ticket",
        ],
        expected_output="MANUAL_OVERRIDE",
        metadata={
            "root_cause_category": "MANUAL_OVERRIDE",
            "requires_correction": True,
            "expected_confidence_min": 0.7,
            "seed_data_ref": "data/seed_transactions.json#case-1004",
            "notes": "A support agent manually suspended the legacy account; event never synced.",
        },
    ),
    Case[dict, str](
        name="data-entry-error",
        input={
            "customer_id": "C-1005",
            "seed_scenario": "data_entry_error",
            "flagged_discrepancy": {"legacy_balance": 305.50, "modern_balance": 350.50},
        },
        expected_trajectory=[
            "read_legacy_system",
            "read_modern_system",
            "search_transactions",
            "get_event_log",
            "draft_correction",
            "create_case_ticket",
        ],
        expected_output="DATA_ENTRY_ERROR",
        metadata={
            "root_cause_category": "DATA_ENTRY_ERROR",
            "requires_correction": True,
            "expected_confidence_min": 0.7,
            "seed_data_ref": "data/seed_transactions.json#case-1005",
            "notes": "A digit transposition (305.50 vs 350.50) with no matching transaction or event.",
        },
    ),
]

# Hard invariant check — see docs/build-contract.md section 4. Fails fast at
# import time if apply_correction ever sneaks into an expected trajectory,
# which would silently make the "0% unauthorized action attempts" eval claim
# false.
for case in test_cases:
    assert "apply_correction" not in case.expected_trajectory, (
        f"case {case.name!r} expects apply_correction in its trajectory — "
        "this tool must never be called by an LLM agent, only by "
        "correction_executor after human approval."
    )

__all__ = ["test_cases", "READ_TOOLS", "DRAFT_TOOLS"]
