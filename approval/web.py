"""Loopback single-case approval screen — `python -m approval.web` (§2.4).

The §2.4 minimum viable interface as one web page, stdlib
http.server only (no framework, no JavaScript — plain forms): the Case
card and the Proposed-correction card are rendered from the LIVE
runtime store; APPROVE/REJECT construct a GateDecision and hand it to
the deterministic spine (run_human_gate, then — on APPROVE —
graph.apply_gate_approval); a replay button re-presents the consumed
capability to the executor to show it refused. The page holds NO
authority of its own — it is a view plus a button wired to the gate.

Demo boundary (stated, not silent): loopback only — 127.0.0.1 (the
committed default) or ::1; this build refuses any other --bind — and
no authentication, per §2.4's "auth ... out of scope for the demo"
scoping. Both accepted literals are loopback-scope, so the boundary
is unchanged; ::1 exists because this repo's WSL2 mirrored dev host
drops IPv4-loopback TCP while ::1 stays healthy (measured
2026-09-06, docs/approval-web-loopback-fix-and-validation-2026-09-06.md).
Session state (token / executed / replay / action log) is in-memory
and dies with the process.
"""

from __future__ import annotations

import argparse
import html
import os
import socket
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import tools.seed_data as seed_data
from orchestrator.correction_executor import execute_correction
from orchestrator.human_gate import (
    GateAction,
    GateDecision,
    latest_pending_draft,
    latest_ticket,
    run_human_gate,
    ticket_for_draft,
)
from tools.case_management import get_draft, get_ticket
from tools.seed_data import canonical_case_id

LOOPBACK = "127.0.0.1"
# The closed set of accepted --bind values: loopback literals only,
# compared by exact membership (no name resolution, no wildcards —
# "localhost", "::", and "0.0.0.0" are all refused).
LOOPBACK_BINDS = ("127.0.0.1", "::1")


class _ThreadingHTTPServerV6(ThreadingHTTPServer):
    """AF_INET6 flavor so the ::1 loopback literal can bind (hosts whose
    IPv4 loopback TCP is dropped — this repo's WSL2 mirrored dev host —
    still have a healthy ::1)."""

    address_family = socket.AF_INET6

# __BODY__ is replaced (not str.format — the CSS braces would all need
# doubling); everything dynamic goes through html.escape first.
PAGE_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Reconciliation Investigator — human approval</title>
<style>
  /* Explicit colors throughout: the page must render identically under
     OS dark mode (theme-independent demo build). */
  body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background: #eef1f5; color: #16202b; max-width: 48rem; margin: 2rem auto; padding: 0 1rem 3rem; }
  h1 { font-size: 1.3rem; margin-bottom: 0.25rem; }
  .card { background: #ffffff; border: 1px solid #cdd5df; border-radius: 8px; padding: 0.9rem 1.25rem; margin: 1rem 0; }
  h2 { font-size: 1rem; margin: 0 0 0.5rem; color: #24313f; border-bottom: 1px solid #d9dfe7; padding-bottom: 0.3rem; }
  code { background: #e8ecf1; border-radius: 4px; padding: 0.05rem 0.35rem; font-size: 0.9em; }
  dt { font-weight: 600; color: #37424e; margin-top: 0.4rem; }
  dd { margin: 0.1rem 0 0 1rem; }
  .muted { color: #5b6774; }
  .ok { color: #1c6b3f; }
  .bad { color: #9c2b2b; }
  .error-card { border-color: #b23b3b; background: #fdf2f2; }
  form { display: inline-block; margin: 0.4rem 1rem 0.4rem 0; }
  button { font: inherit; background: #245f9e; color: #ffffff; border: 1px solid #1c4a7c; border-radius: 6px; padding: 0.45rem 1.1rem; cursor: pointer; }
  button[disabled] { background: #aeb8c2; border-color: #98a3ae; cursor: not-allowed; }
  input[type="text"] { font: inherit; padding: 0.35rem 0.5rem; border: 1px solid #c3ccd6; border-radius: 6px; background: #ffffff; color: #16202b; width: 22rem; max-width: 100%; }
  ul { margin: 0.25rem 0; padding-left: 1.25rem; }
  footer { color: #5b6774; font-size: 0.85rem; margin-top: 2rem; border-top: 1px solid #cdd5df; padding-top: 0.75rem; }
</style>
</head>
<body>
<h1>Reconciliation Investigator — human approval</h1>
<p class="muted">single-case approval screen (docs/build-contract.md §2.4 minimum viable interface)</p>
__BODY__
<footer>Security model: this page holds no authority. APPROVE constructs a GateDecision; the deterministic Python gate issues the scoped, expiring, single-use capability; the executor validates before any mutation. Loopback demo only — no authentication (docs/build-contract.md §2.4 scoping).</footer>
</body>
</html>
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _value(value: object) -> str:
    """Escaped display rendering of a stored value; None is explicit."""
    return _esc("n/a" if value is None else value)


def _case_card(case_id: str, ticket: dict | None) -> str:
    rows = [f"<dt>case id</dt><dd><code>{_esc(case_id)}</code></dd>"]
    if ticket is None:
        rows.append(
            '<dd class="muted">no ticket on file for this case yet — the investigation '
            "has not produced a case file</dd>"
        )
    else:
        refs = ", ".join(str(ref) for ref in (ticket.get("evidence_refs") or [])) or "none cited"
        rows.append(
            f"<dt>ticket</dt><dd><code>{_esc(ticket.get('ticket_id', ''))}</code>"
            f" — {_value(ticket.get('summary', ''))}</dd>"
        )
        rows.append(
            f"<dt>root cause</dt><dd><strong>{_value(ticket.get('root_cause', ''))}</strong>"
            f" (confidence {_value(ticket.get('confidence', ''))})</dd>"
        )
        rows.append(f"<dt>evidence refs</dt><dd><code>{_esc(refs)}</code></dd>")
    return f'<section class="card"><h2>Case</h2><dl>{"".join(rows)}</dl></section>'


def _correction_card(case_id: str, draft: dict | None) -> str:
    if draft is None:
        return (
            '<section class="card"><h2>No pending correction draft</h2>'
            "<p>No pending correction draft. Run the investigation first: "
            f"<code>python -m approval.cli --customer {_esc(case_id)}</code></p></section>"
        )
    rows = (
        f"<dt>field</dt><dd><code>{_esc(draft.get('field', ''))}</code></dd>"
        f"<dt>value change</dt><dd>{_value(draft.get('current_value'))}"
        f" -> {_value(draft.get('proposed_value'))}</dd>"
        f"<dt>justification</dt><dd>{_value(draft.get('justification', ''))}</dd>"
        f"<dt>draft id</dt><dd><code>{_esc(draft.get('draft_id', ''))}</code>"
        f" — status {_esc(draft.get('status', ''))}</dd>"
    )
    return f'<section class="card"><h2>Proposed correction</h2><dl>{rows}</dl></section>'


def _decision_card(draft: dict | None) -> str:
    disabled = "" if draft else " disabled"
    muted = (
        ""
        if draft
        else '<p class="muted">buttons disabled: no pending correction draft to act on</p>'
    )
    return (
        '<section class="card"><h2>Decision</h2>'
        "<p>APPROVE asks the deterministic gate for the scoped, single-use, expiring "
        "capability and executes the drafted correction through the executor. REJECT "
        "closes the case ticket with your reason.</p>"
        f"{muted}"
        f'<form method="post" action="/approve"><button type="submit"{disabled}>APPROVE</button></form>'
        f'<form method="post" action="/reject">'
        f'<input type="text" name="reason" placeholder="rejection reason (audited)"{disabled}> '
        f'<button type="submit"{disabled}>REJECT</button></form>'
        "</section>"
    )


def _execution_card(state: dict) -> str:
    executed = state.get("executed")
    if not executed:
        return ""
    ticket_id = str(executed.get("ticket_id", "") or "")
    ticket = get_ticket(ticket_id) if ticket_id else None
    rows = f"<dt>status</dt><dd>{_esc(executed.get('status', ''))}</dd>"
    if executed.get("error"):
        rows += f'<dt>error</dt><dd class="bad">{_esc(executed["error"])}</dd>'
    rows += (
        f"<dt>before</dt><dd>{_value(executed.get('before'))}</dd>"
        f"<dt>after</dt><dd>{_value(executed.get('after'))}</dd>"
        f"<dt>no_op</dt><dd>{_esc(executed.get('no_op'))}</dd>"
        f"<dt>audit entry</dt><dd><code>{_esc(executed.get('audit_entry_id', ''))}</code></dd>"
        f"<dt>ticket</dt><dd><code>{_esc(ticket_id)}</code>"
        f" — status {_esc((ticket or {}).get('status', 'n/a'))}</dd>"
    )
    return (
        '<section class="card"><h2>Execution result</h2>'
        f"<dl>{rows}</dl>"
        '<form method="post" action="/replay">'
        "<button type=\"submit\">Attempt replay of the consumed capability</button></form>"
        "<p class=\"muted\">replay re-presents the SAME token and arguments to the "
        "executor; single-use means it must be refused</p>"
        "</section>"
    )


def _replay_card(state: dict) -> str:
    replay = state.get("replay")
    if not replay:
        return ""
    failed = replay.get("status") == "failed"
    detail = replay.get("error") or (
        f"before={replay.get('before')} after={replay.get('after')}"
    )
    verdict = (
        '<p class="bad">the executor refused the replay, as it must (single-use)</p>'
        if failed
        else '<p class="bad">UNEXPECTED: the replay was not refused</p>'
    )
    return (
        '<section class="card"><h2>Replay result</h2>'
        f"<p>status: {_esc(replay.get('status', ''))}</p>"
        f"{verdict}"
        f"<p>executor answer (verbatim): <code>{_esc(str(detail))}</code></p>"
        "</section>"
    )


def _log_card(state: dict) -> str:
    log = state.get("action_log") or []
    if not log:
        return ""
    items = "".join(f"<li>{_esc(entry)}</li>" for entry in log)
    return (
        '<section class="card"><h2>Session action log</h2>'
        f"<ul>{items}</ul>"
        '<p class="muted">in-memory, this server process only</p></section>'
    )


def _error_card(message: str) -> str:
    return (
        '<section class="card error-card"><h2>Action failed</h2>'
        f"<p>{_esc(message)}</p>"
        '<p class="muted">the deterministic spine raised this; nothing was fabricated '
        "— see the server console for the full traceback</p></section>"
    )


def render_page(case_id: str, state: dict, error: str | None = None) -> str:
    """One page: cards 1-2 are read LIVE from the runtime store on every
    render; cards 5-6 come from this process's session state."""
    draft = latest_pending_draft(case_id)
    # §2.4 case card: the ticket linked to the pending draft when one
    # exists, else the latest ticket for the case.
    ticket = ticket_for_draft(case_id, str(draft.get("draft_id", ""))) if draft else latest_ticket(case_id)
    body = (
        (_error_card(error) if error else "")
        + _case_card(case_id, ticket)
        + _correction_card(case_id, draft)
        + _decision_card(draft)
        + _execution_card(state)
        + _replay_card(state)
        + _log_card(state)
    )
    return PAGE_SHELL.replace("__BODY__", body)


def _make_handler(case_id: str, approver: str, state: dict, lock: threading.Lock) -> type:
    """Build the request-handler class with the session captured in a
    closure (one handler instance per connection; the shared state is
    serialized by `lock` because ThreadingHTTPServer serves each request
    on its own thread)."""

    class ApprovalHandler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")  # the page is live state
            self.end_headers()
            self.wfile.write(body)

        def _send_page(self, error: str | None = None) -> None:
            self._send(200, render_page(case_id, state, error=error).encode("utf-8"),
                       "text/html; charset=utf-8")

        def _send_error_page(self, exc: Exception) -> None:
            # The browser never gets a stack trace — the message only.
            # The re-raise below lands in socketserver's handle_error,
            # which prints the full traceback to THIS console.
            page = (
                '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
                "<title>approval screen — error</title></head><body>"
                "<h1>approval screen: action failed</h1>"
                f"<p>{html.escape(str(exc))}</p>"
                "<p>see the server console for details.</p></body></html>"
            ).encode("utf-8")
            self._send(500, page, "text/html; charset=utf-8")

        def _form(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            return {key: values[0] for key, values in urllib.parse.parse_qs(raw).items() if values}

        def _case_file_text(self) -> str:
            # The closest honest stand-in for the reporter's case file in
            # the store: the case ticket's summary (empty until the
            # investigation files one).
            return str((latest_ticket(case_id) or {}).get("summary", ""))

        def do_GET(self) -> None:
            try:
                with lock:
                    if urllib.parse.urlsplit(self.path).path != "/":
                        self._send(404, b"not found\n", "text/plain; charset=utf-8")
                        return
                    self._send_page()
            except Exception as exc:
                try:
                    self._send_error_page(exc)
                except Exception:
                    pass
                raise

        def do_POST(self) -> None:
            try:
                with lock:
                    path = urllib.parse.urlsplit(self.path).path
                    if path == "/approve":
                        self._do_approve()
                    elif path == "/reject":
                        self._do_reject(self._form())
                    elif path == "/replay":
                        self._do_replay()
                    else:
                        self._send(404, b"not found\n", "text/plain; charset=utf-8")
                        return
                    self._send_page()
            except Exception as exc:
                try:
                    self._send_error_page(exc)
                except Exception:
                    pass
                raise

        def _do_approve(self) -> None:
            # Lazy import on purpose: keeps the graph/agent wiring out of
            # this server's startup — only a real approval needs it.
            from orchestrator.graph import apply_gate_approval

            draft = latest_pending_draft(case_id)
            decision = GateDecision(GateAction.APPROVE, approver=approver)
            outcome = run_human_gate(self._case_file_text(), draft, decision, case_id=case_id)
            if outcome.get("action") is GateAction.APPROVE:
                executed = apply_gate_approval(case_id, outcome, draft, approver=approver)
                state["token"] = outcome.get("approval_token")
                state["executed"] = executed
                state["replay"] = None
                state["action_log"].append(
                    f"APPROVE by {approver}: executed status={executed.get('status')} "
                    f"audit_entry_id={executed.get('audit_entry_id', '')}"
                )
            else:
                # The gate refused (e.g. an invalid draft) and said so
                # itself — record its own outcome; invent nothing.
                state["action_log"].append(
                    f"APPROVE by {approver}: gate returned "
                    f"{getattr(outcome.get('action'), 'value', outcome.get('action'))} "
                    f"({outcome.get('reason', outcome.get('investigation_hint', ''))})"
                )

        def _do_reject(self, form: dict[str, str]) -> None:
            reason = (form.get("reason") or "").strip() or "rejected by human"
            decision = GateDecision(GateAction.REJECT, approver=approver, reason=reason)
            outcome = run_human_gate(
                self._case_file_text(), latest_pending_draft(case_id), decision, case_id=case_id
            )
            state["action_log"].append(
                f"REJECT by {approver}: reason={reason!r} "
                f"tickets_closed={outcome.get('tickets_closed')}"
            )

        def _do_replay(self) -> None:
            executed = state.get("executed") or {}
            token = state.get("token")
            if not token or not executed:
                state["replay"] = {
                    "status": "failed",
                    "error": "nothing to replay: no approved execution in this server process",
                }
                state["action_log"].append("replay: precheck refused — no consumed capability held")
                return
            # Same arguments as the approved execution: the token stashed
            # at approve time plus the correction reconstructed from the
            # store (ticket -> linked draft).
            ticket_id = str(executed.get("ticket_id", "") or "")
            ticket = get_ticket(ticket_id) if ticket_id else None
            draft_id = str((ticket or {}).get("correction_draft_id", "") or "")
            draft = get_draft(draft_id) if draft_id else None
            if draft is None:
                state["replay"] = {
                    "status": "failed",
                    "error": (
                        "cannot reconstruct the executed correction: ticket "
                        f"{ticket_id or '(none)'} links no draft in the store"
                    ),
                }
                state["action_log"].append("replay: precheck refused — executed draft not resolvable")
                return
            replay = execute_correction(
                token,
                case_id=case_id,
                field=draft.get("field"),
                new_value=draft.get("proposed_value"),
                ticket_id=ticket_id,
                approver=approver,
                draft_id=str(draft.get("draft_id", "") or ""),
            )
            state["replay"] = replay
            state["action_log"].append(
                f"replay attempted: status={replay.get('status')} error={replay.get('error', '')}"
            )

    return ApprovalHandler


def build_server(
    bind: str, port: int, case_id: str, approver: str, state: dict
) -> ThreadingHTTPServer:
    """The single construction path for the screen's server — main() and
    the HTTP-layer tests share it, so no second wiring can arise. The
    caller still owns serve_forever()/server_close()."""
    cls = _ThreadingHTTPServerV6 if ":" in bind else ThreadingHTTPServer
    return cls((bind, port), _make_handler(case_id, approver, state, threading.Lock()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m approval.web",
        description=(
            "Loopback single-case approval screen (docs/build-contract.md §2.4 minimum "
            "viable interface; no authentication by stated demo scope)."
        ),
    )
    parser.add_argument(
        "--customer",
        required=True,
        help="canonical case/customer id (e.g. C-1001; validated against the seed)",
    )
    parser.add_argument("--port", type=int, default=8765, help="port to listen on (default: 8765)")
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
        "--bind",
        default=LOOPBACK,
        help=(
            f"bind address — loopback literals only ({LOOPBACK} default; ::1 for"
            " hosts whose IPv4 loopback is unreachable); anything else is REFUSED"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.bind not in LOOPBACK_BINDS:
        print(
            f"error: --bind must be one of {' / '.join(LOOPBACK_BINDS)} in this "
            f"demo build (got {args.bind!r}): loopback-only is a stated demo "
            "boundary — the page carries no authentication "
            "(docs/build-contract.md §2.4 scoping)",
            file=sys.stderr,
        )
        return 2
    # EVAL_MODE=1 unless the caller deliberately set the environment:
    # the whole spine (seed reads, dev token key) is EVAL_MODE-only.
    os.environ.setdefault("EVAL_MODE", "1")
    try:
        case_id = canonical_case_id(args.customer)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.runtime_dir is not None:
        # Dedicated demo/validation store; every runtime read/write in
        # the spine resolves through seed_data.runtime_path -> RUNTIME_DIR.
        seed_data.RUNTIME_DIR = args.runtime_dir
    state: dict = {"token": None, "executed": None, "replay": None, "action_log": []}
    server = build_server(args.bind, args.port, case_id, args.approver, state)
    shown_host = f"[{args.bind}]" if ":" in args.bind else args.bind
    print(
        f"approval screen for case {case_id}: http://{shown_host}:{args.port}/ (Ctrl+C to stop)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ninterrupt received — shutting down (session state was in-memory only)")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
