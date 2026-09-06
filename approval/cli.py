"""Terminal human-approval flow — `python -m approval.cli` (§2.4 surface).

The §2.4 minimum viable interface, terminal edition: run ONE case's
investigation to completion via orchestrator.graph.run_case_with_gate,
put the reporter's case file and the pending correction draft in front
of the human, and turn their choice into a GateDecision for the
deterministic spine (human_gate issues the scoped, single-use,
expiring capability; the executor validates before any mutation — §2.5).
This module renders state and collects a decision; it holds NO security
logic of its own and never touches the write path directly.

Modes:
- interactive (default): the decide() prompt implemented below.
- --non-interactive: a scripted decision for validation runs — the
  startup banner says so; honest output only.
- --demo (after a terminal APPROVE that applied): mechanically
  demonstrates the capability boundary — replaying the consumed token
  through the executor must fail, and validate_approval_token must
  reject every out-of-scope presentation (wrong case / wrong field /
  wrong value / expired / malformed). Every line printed is the
  spine's own answer; a broken invariant prints as UNEXPECTED, it is
  never hidden or asserted away.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import tools.seed_data as seed_data
from orchestrator.correction_executor import execute_correction
from orchestrator.graph import run_case_with_gate
from orchestrator.human_gate import (
    GateAction,
    GateDecision,
    issue_approval_token,
    latest_ticket,
    ticket_for_draft,
    validate_approval_token,
)
from tools.case_management import get_draft, get_ticket
from tools.seed_data import canonical_case_id

SEPARATOR = "=" * 72

# --decision spellings -> GateAction ("more-info" is the CLI spelling
# of the §2.4 REQUEST_MORE_INFO outcome).
SCRIPTED_ACTIONS: dict[str, GateAction] = {
    "approve": GateAction.APPROVE,
    "reject": GateAction.REJECT,
    "more-info": GateAction.REQUEST_MORE_INFO,
}


def _action_label(action: object) -> str:
    """Compact label for a GateAction (str-enum: use its value) or
    whatever the spine returned."""
    return str(getattr(action, "value", action))


def _render_value(value: object) -> str:
    """One-line rendering of a correction value; json keeps numbers
    honest, strings render bare, None is explicitly 'n/a'."""
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    return json.dumps(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m approval.cli",
        description=(
            "Terminal human-approval surface for one reconciliation case "
            "(docs/build-contract.md §2.4). The deterministic gate stays "
            "authoritative; this tool renders state and collects a GateDecision."
        ),
    )
    parser.add_argument(
        "--customer",
        required=True,
        help="canonical case/customer id (e.g. C-1001; validated against the seed)",
    )
    parser.add_argument(
        "--instruction",
        default=None,
        help="investigation instruction (default: the standard customer pointer)",
    )
    parser.add_argument(
        "--approver",
        default="human",
        help="approver name recorded in the audit trail (default: human)",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=None,
        help="redirect the runtime store to this directory (dedicated demo/validation store)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="scripted decision for validation runs (NOT a human decision; banner printed)",
    )
    parser.add_argument(
        "--decision",
        choices=tuple(SCRIPTED_ACTIONS),
        default=None,
        help="scripted decision for --non-interactive (default: approve)",
    )
    parser.add_argument("--note", default="", help="note carried by a scripted more-info decision")
    parser.add_argument("--reason", default="", help="reason carried by a scripted reject decision")
    parser.add_argument(
        "--demo",
        action="store_true",
        help=(
            "after a terminal APPROVE that applied: replay the consumed token and "
            "run the negative matrix against the spine (capability-boundary demo)"
        ),
    )
    return parser


def build_interactive_decider(case_id: str, approver: str):
    """§2.4 pause-point, terminal edition: render the reporter's case
    file and the pending draft, read ONE human decision. Returns the
    decide(case_file_text, draft) callable run_case_with_gate expects."""

    def decide(case_file_text: str, draft: dict | None) -> GateDecision:
        print(SEPARATOR)
        print("HUMAN GATE — case file and proposed correction")
        print(SEPARATOR)
        print(case_file_text or "(the reporter produced no case file text)")
        print("-" * 72)
        if draft is None:
            print("(no correction draft — approving does nothing)")
        else:
            ticket = ticket_for_draft(case_id, str(draft.get("draft_id", ""))) or latest_ticket(case_id)
            print("proposed correction:")
            print(f"  case/customer:  {draft.get('customer_id', case_id)}")
            print(f"  field:          {draft.get('field', 'n/a')}")
            print(
                f"  value change:   {_render_value(draft.get('current_value'))}"
                f" -> {_render_value(draft.get('proposed_value'))}"
            )
            print(f"  justification:  {draft.get('justification', '')}")
            print(f"  draft id:       {draft.get('draft_id', 'n/a')}")
            print(f"  ticket id:      {ticket.get('ticket_id') if ticket else '(none on file)'}")
            print(f"  status:         {draft.get('status', 'n/a')}")
        print("-" * 72)
        while True:
            choice = input("[A]pprove / [R]eject / [M]ore info / [Q]uit: ").strip().lower()
            if choice in ("a", "approve"):
                return GateDecision(GateAction.APPROVE, approver=approver)
            if choice in ("r", "reject"):
                reason = input("reason (default 'rejected by human'): ").strip() or "rejected by human"
                return GateDecision(GateAction.REJECT, approver=approver, reason=reason)
            if choice in ("m", "more info", "more-info"):
                while True:
                    note = input("note to the investigator (required): ").strip()
                    if note:
                        return GateDecision(GateAction.REQUEST_MORE_INFO, approver=approver, note=note)
                    print("note cannot be empty — say what additional evidence you need")
            if choice in ("q", "quit"):
                # Deliberate: q exits the whole flow cleanly (nothing has
                # been approved; no draft was touched by this prompt).
                raise SystemExit(0)
            print("invalid choice — enter a, r, m, or q")

    return decide


def build_scripted_decider(action_name: str, approver: str, reason: str, note: str):
    """--non-interactive: the same GateDecision every round, printed as
    what it is — a scripted, non-human decision for validation runs."""
    action = SCRIPTED_ACTIONS[action_name]
    reason = reason or "rejected by scripted validation run"
    note = note or "scripted validation run: additional evidence requested"
    print("*" * 72)
    print("SCRIPTED DECISION — NON-INTERACTIVE MODE")
    print(f"decision={action_name}  approver={approver}")
    print(
        "This is NOT a human decision: --non-interactive supplies a scripted "
        "decision for validation runs (docs/build-contract.md §2.4 surface)."
    )
    print("*" * 72)

    def decide(case_file_text: str, draft: dict | None) -> GateDecision:
        # Visibility for validation runs: show exactly what the gate is
        # being asked to decide on (the interactive human sees this too).
        print(SEPARATOR)
        print("GATE INPUT (scripted run — the case file and draft as presented)")
        print(SEPARATOR)
        print(case_file_text or "(the reporter produced no case file text)")
        if draft is None:
            print("(no pending correction draft reached the gate)")
        else:
            print(f"(pending draft: {json.dumps(draft, default=str)})")
        if action is GateAction.REJECT:
            return GateDecision(GateAction.REJECT, approver=approver, reason=reason)
        if action is GateAction.REQUEST_MORE_INFO:
            return GateDecision(GateAction.REQUEST_MORE_INFO, approver=approver, note=note)
        return GateDecision(GateAction.APPROVE, approver=approver)

    return decide


def print_result_block(final: dict, case_id: str) -> None:
    """Structured summary of the completed flow — every field printed is
    read back from the spine's returned state / the runtime store, never
    restated from expectations."""
    verdict = final.get("verdict") or {}
    outcome = final.get("outcome") or {}
    gate = outcome.get("gate") if isinstance(outcome.get("gate"), dict) else outcome
    correction = outcome.get("correction")
    print()
    print(SEPARATOR)
    print("RESULT")
    print(SEPARATOR)
    print(f"case:        {case_id}")
    print(
        f"verdict:     root_cause={verdict.get('root_cause', 'n/a')} "
        f"confidence={verdict.get('confidence', 'n/a')}"
    )
    print(f"gate action: {_action_label(gate.get('action'))}")
    if outcome.get("max_rounds_exhausted"):
        print("gate rounds: exhausted (repeated more-info without closure)")
    if correction is None:
        line = f"correction:  none executed (gate action={_action_label(gate.get('action'))}"
        if isinstance(gate.get("tickets_closed"), int):
            line += f"; {gate['tickets_closed']} ticket(s) closed as rejected"
        print(line + ")")
    else:
        print(
            f"correction:  status={correction.get('status')} "
            f"before={_render_value(correction.get('before'))} "
            f"after={_render_value(correction.get('after'))} "
            f"no_op={correction.get('no_op')}"
        )
        if correction.get("audit_entry_id"):
            print(f"audit entry: {correction['audit_entry_id']}")
        if correction.get("error"):
            print(f"error:       {correction['error']}")
    ticket_id = (correction or {}).get("ticket_id") or (latest_ticket(case_id) or {}).get("ticket_id")
    if ticket_id:
        ticket = get_ticket(str(ticket_id))
        if ticket:
            print(f"ticket:      {ticket_id} status={ticket.get('status')}")
    print(SEPARATOR)


def _wrong_demo_value(draft: dict, new_value: object) -> object:
    """The 'wrong value' for the negative matrix: original+1 per the demo
    spec when the current value is numeric; status corrections get the
    other canonical status. Any value distinct from the approved one
    demonstrates value scoping — the small search guarantees distinct."""
    current = draft.get("current_value")
    if isinstance(current, (int, float)) and not isinstance(current, bool):
        for candidate in (current + 1, current - 1, current + 2):
            if json.dumps(candidate) != json.dumps(new_value):
                return candidate
    for candidate in ("ACTIVE", "SUSPENDED", "CLOSED"):
        if json.dumps(candidate) != json.dumps(new_value):
            return candidate
    return f"{new_value} (altered)"


def _demo_negative_matrix(case_id: str, field: str, new_value: object, draft: dict) -> None:
    """Present the capability OUT of scope and print the spine's own
    validate_approval_token answer, one compact line per case
    (consume=False: the matrix burns nothing and stores nothing)."""
    others = [name for name in sorted(seed_data.load_seed()["modern_system"]) if name != case_id]
    wrong_field = "status" if str(field).strip().lower() != "status" else "balance"
    wrong_value = _wrong_demo_value(draft, new_value)

    def check(name: str, token: str) -> None:
        ok, reason = validate_approval_token(
            token, case_id=case_id, field=field, new_value=new_value, consume=False
        )
        prefix = reason.split(",")[0]
        verdict = "REJECTED" if not ok else "ACCEPTED (UNEXPECTED — scope binding failed)"
        print(f"[demo] {name}: {verdict} ({prefix})")

    if others:
        check("different-case", issue_approval_token(others[0], field, new_value))
    else:
        print("[demo] different-case: SKIPPED (no other seed customer to scope against)")
    check("wrong-field", issue_approval_token(case_id, wrong_field, new_value))
    check("wrong-value", issue_approval_token(case_id, field, wrong_value))
    check("expired", issue_approval_token(case_id, field, new_value, ttl_seconds=-1))
    check("malformed", "not-a-token")


def run_capability_demo(final: dict, case_id: str, approver: str) -> None:
    """--demo: mechanically demonstrate the boundary of the issued
    capability. Requires a terminal APPROVE that applied; prints the
    spine's answers verbatim and flags anything unexpected as such."""
    outcome = final.get("outcome") or {}
    correction = outcome.get("correction") or {}
    gate = outcome.get("gate") or {}
    draft = gate.get("draft") or {}
    token = gate.get("approval_token") or ""
    print()
    print("[demo] capability-boundary demonstration (every answer below is the spine's own):")
    if correction.get("status") != "applied" or not token or not draft:
        # Honest skip: --demo is only meaningful after approve-that-applied.
        print(
            "[demo] skipped: needs a terminal APPROVE that applied a correction; this run "
            f"ended with gate action={_action_label((outcome.get('gate') or outcome).get('action'))} "
            f"correction status={correction.get('status') or 'none'}"
        )
        return

    field = str(draft.get("field", ""))
    new_value = draft.get("proposed_value")
    ticket_id = str(correction.get("ticket_id", "") or (latest_ticket(case_id) or {}).get("ticket_id", ""))
    # (a) REPLAY: same token, same arguments — single-use means refusal.
    replay = execute_correction(
        token,
        case_id=case_id,
        field=field,
        new_value=new_value,
        ticket_id=ticket_id,
        approver=approver,
        draft_id=str(draft.get("draft_id", "")),
    )
    replay_error = str(replay.get("error", ""))
    refused = replay.get("status") == "failed" and "consumed" in replay_error
    print(f"[demo] replay (same token, same arguments): status={replay.get('status')}")
    print(f"[demo] replay exact error: {replay_error}")
    print(f"[demo] replay correctly refused (single-use): {'yes' if refused else 'NO — UNEXPECTED'}")

    # (b) negative matrix: out-of-scope presentations must all be rejected.
    _demo_negative_matrix(case_id, field, new_value, draft)

    # Post-replay integrity: the failed replay must have changed neither
    # the resolved ticket nor the applied draft (read back from the store).
    ticket = get_ticket(ticket_id) if ticket_id else None
    draft_after = get_draft(str(draft.get("draft_id", "")))
    intact = (ticket or {}).get("status") == "resolved" and (draft_after or {}).get("status") == "applied"
    print(
        f"[demo] post-replay integrity: ticket {ticket_id or 'n/a'} "
        f"status={(ticket or {}).get('status', 'n/a')}, draft {draft.get('draft_id')} "
        f"status={(draft_after or {}).get('status', 'n/a')} — "
        f"applied state intact: {'yes' if intact else 'NO — UNEXPECTED'}"
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # EVAL_MODE=1 unless the caller deliberately set the environment:
    # the whole spine (seed reads, dev token key) is EVAL_MODE-only.
    os.environ.setdefault("EVAL_MODE", "1")
    try:
        case_id = canonical_case_id(args.customer)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.runtime_dir is not None:
        # Dedicated demo/validation store: the spine resolves every
        # runtime file through seed_data.runtime_path, which reads this
        # module attribute at call time.
        seed_data.RUNTIME_DIR = args.runtime_dir
    if not args.non_interactive and (args.decision or args.note or args.reason):
        print(
            "note: --decision/--note/--reason apply only to --non-interactive; "
            "ignoring them (interactive mode)."
        )

    instruction = args.instruction or f"Investigate the flagged discrepancy for customer_id={case_id}."
    if args.non_interactive:
        decide = build_scripted_decider(args.decision or "approve", args.approver, args.reason, args.note)
    else:
        decide = build_interactive_decider(case_id, args.approver)

    try:
        final = run_case_with_gate(instruction, case_id=case_id, decide=decide)
    except ValueError as exc:
        # Honest surface-level handling of a foreseeable spine refusal
        # (e.g. APPROVE with no pending draft because the reporter never
        # drafted one): report it, exit 1 — never a bare traceback.
        print(f"error: the gate refused the flow: {exc}", file=sys.stderr)
        return 1
    print_result_block(final, case_id)
    if args.demo:
        run_capability_demo(final, case_id, args.approver)
    return 0


if __name__ == "__main__":
    # Completed flow exits 0; an unknown customer exits 2 (printed error).
    # Unexpected exceptions propagate uncaught on purpose — the
    # interpreter prints the traceback and exits non-zero, which is the
    # only other non-zero path for this surface.
    sys.exit(main())
