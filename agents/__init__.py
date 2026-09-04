"""Reconciliation Investigator agents (docs/build-contract.md §2).

Each module carries its system prompt VERBATIM from the contract
(byte-compared in tests/test_agents.py) plus a build factory with the
exact tool registration set §2.1-2.3 prescribes. No agent anywhere in
this repo is ever constructed with the correction write tool — see the
segregation-of-duties invariant (build-contract §4).
"""
