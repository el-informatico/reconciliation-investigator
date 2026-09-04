"""Reconciliation Investigator tools (docs/build-contract.md §3).

Read tools live in legacy_system / modern_system / transactions; draft
and tracking tools in case_management. The write tool apply_correction
is a PLAIN FUNCTION in modern_system.py — never a Strands tool, called
only by orchestrator/correction_executor.py (build-contract §4).
"""
