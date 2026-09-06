"""Minimal human approval surface for the correction gate: a terminal
flow (`python -m approval.cli`) and a loopback single-case screen
(`python -m approval.web`). The deterministic Python gate in
orchestrator/human_gate.py stays authoritative — these entry points
hold no security logic of their own; they render state and construct
GateDecision objects for the existing spine, per docs/build-contract.md
§2.4's minimum viable interface (auth and multi-case queue management
are out of scope for the demo)."""
