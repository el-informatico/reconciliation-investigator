"""Loopback single-case approval screen — `python -m approval.web` (§2.4).

The §2.4 minimum viable interface as web pages, stdlib
http.server only (no framework, no JavaScript — plain forms): the Case
card and the Proposed-correction card are rendered from the LIVE
runtime store; APPROVE/REJECT construct a GateDecision and hand it to
the deterministic spine (run_human_gate, then — on APPROVE —
graph.apply_gate_approval); a replay button re-presents the consumed
capability to the executor to show it refused. The page holds NO
authority of its own — it is a view plus a button wired to the gate.
A second, strictly read-only page (/summary) shows all five seeded
cases' state at a glance: one row per case, sourced from the live
runtime store and the seed systems only — never from the eval case
definitions (ground-truth discipline, docs/EVALUATION.md §6) — with no
decision forms, because acting on a case stays on its own single-case
screen (docs/build-contract.md §2.4).

Demo boundary (stated, not silent): loopback only — 127.0.0.1 (the
committed default) or ::1; this build refuses any other --bind. Both
accepted literals are loopback-scope; ::1 exists because this repo's
WSL2 mirrored dev host drops IPv4-loopback TCP while ::1 stays healthy
(measured 2026-09-06, docs/approval-web-loopback-fix-and-validation-2026-09-06.md).
Approver authentication (§2.4 AMENDED 2026-09-10, human-approved Tier C
change): every request must present the per-session APPROVER ACCESS
TOKEN — HTTP Basic, where the username becomes the audited approver
identity and the password is the session token, compared constant-time.
That token is a different thing from the gate's approval capability
token and confers nothing by itself: APPROVE still constructs a
GateDecision and asks the deterministic gate. Every POST must also
carry the per-session CSRF nonce embedded in the served forms.
main() generates both per session and never serves without them;
build_server callers may pass auth_token/csrf_token=None explicitly
for the embedded/test posture. Session state (token / executed /
replay / action log / CSRF nonce) is in-memory and dies with the
process.
"""

from __future__ import annotations

import argparse
import base64
import html
import hmac
import json
import os
import secrets
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
  a { color: #245f9e; }
  table.summary { border-collapse: collapse; width: 100%; margin: 0.5rem 0; }
  table.summary th, table.summary td { border: 1px solid #cdd5df; padding: 0.3rem 0.55rem; text-align: left; font-size: 0.95em; }
  table.summary th { background: #e8ecf1; }
  ul { margin: 0.25rem 0; padding-left: 1.25rem; }
  .val-old { color: #9c2b2b; font-weight: 600; }
  .val-new { color: #1c6b3f; font-weight: 700; }
  .diff-arrow { color: #5b6774; padding: 0 0.3rem; }
  .val-delta { font-weight: 700; background: #e8ecf1; border-radius: 4px; padding: 0.05rem 0.4rem; }
  pre { background: #e8ecf1; border-radius: 6px; padding: 0.6rem 0.75rem; white-space: pre-wrap; overflow-x: auto; font-size: 0.88em; margin: 0.4rem 0 0; }
  details summary { cursor: pointer; color: #245f9e; }
  footer { color: #5b6774; font-size: 0.85rem; margin-top: 2rem; border-top: 1px solid #cdd5df; padding-top: 0.75rem; }
</style>
</head>
<body>
<h1>Reconciliation Investigator — human approval</h1>
<p class="muted">single-case approval screen (docs/build-contract.md §2.4 minimum viable interface)</p>
__BODY__
<footer>Security model: this page holds no authority. APPROVE constructs a GateDecision; the deterministic Python gate issues the scoped, expiring, single-use capability; the executor validates before any mutation. Loopback demo only; approver authentication: per-session access token (HTTP Basic) plus CSRF nonces on every decision form (docs/build-contract.md §2.4, amended 2026-09-10).</footer>
</body>
</html>
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _value(value: object) -> str:
    """Escaped display rendering of a stored value; None is explicit."""
    return _esc("n/a" if value is None else value)


def _is_number(value: object) -> bool:
    """Numeric-value test for the diff rendering. bool is excluded on
    purpose: it is a subclass of int in Python but never a correction
    value here, and rendering True as 1.00 would be noise, not a diff."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _value_diff(current: object, proposed: object) -> str:
    """The decision object as the hero of the screen: current -> proposed
    as a styled diff pair, with the computed delta emphasized when both
    sides are numeric (`350.50 -> 305.50 (-45.00)`); enum-style values
    (`ACTIVE -> SUSPENDED`) get the same visual treatment minus the
    delta. Numeric display is fixed to two decimals — these fields are
    money (balance) by contract; the delta always carries its sign."""
    if _is_number(current) and _is_number(proposed):
        old_txt, new_txt = f"{current:.2f}", f"{proposed:.2f}"
        delta = proposed - current
        return (
            f'<span class="val-old">{_esc(old_txt)}</span>'
            '<span class="diff-arrow">&rarr;</span>'
            f'<span class="val-new">{_esc(new_txt)}</span>'
            f' <span class="val-delta">({delta:+.2f})</span>'
        )
    return (
        f'<span class="val-old">{_value(current)}</span>'
        '<span class="diff-arrow">&rarr;</span>'
        f'<span class="val-new">{_value(proposed)}</span>'
    )


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
            f"<dt>ticket</dt><dd><code>{_esc(ticket.get('ticket_id', ''))}</code></dd>"
        )
        # The verbatim agent output stays one click away, honestly labeled,
        # collapsed by default so the raw markdown prose wall never
        # dominates the screen. Presentation-only: nothing is summarized
        # or reworded — the raw text is served escaped, byte for byte.
        rows.append(
            "<dt>case file</dt><dd>"
            "<details><summary>Raw agent ticket (verbatim)</summary>"
            f"<pre>{_esc(str(ticket.get('summary', '') or ''))}</pre>"
            "</details></dd>"
        )
        rows.append(
            f"<dt>root cause</dt><dd><strong>{_value(ticket.get('root_cause', ''))}</strong>"
            f" (confidence {_value(ticket.get('confidence', ''))})</dd>"
        )
        rows.append(f"<dt>evidence refs</dt><dd><code>{_esc(refs)}</code></dd>")
    return f'<section class="card"><h2>Case</h2><dl>{"".join(rows)}</dl></section>'


def _latest_draft(case_id: str) -> dict | None:
    """The case's most recent draft in ANY status. The store's
    pending-draft readers deliberately hide decided drafts; the executed /
    receipt state needs them, so a decided case stops rendering exactly
    like a never-investigated one."""
    path = seed_data.runtime_path("drafts.jsonl")
    if not path.exists():
        return None
    latest: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # a torn tail line is never a reason to crash the screen
        if record.get("customer_id") == case_id:
            latest = record
    return latest


def _decided_audit(draft: dict) -> dict | None:
    """The audit entry the executor recorded for a decided draft —
    approver and timestamp live there (the draft row itself carries only
    audit_entry_id / approved_at)."""
    audit_id = str(draft.get("audit_entry_id", "") or "")
    if not audit_id:
        return None
    path = seed_data.runtime_path("audit_log.jsonl")
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("audit_entry_id") == audit_id:
            return record
    return None


def _decided_card(draft: dict) -> str:
    """The post-decision state, distinct from never-ran: an execution
    receipt when the store says applied/consumed (status, the executed
    value change, single-use capability consumed, approver + timestamp,
    audit entry); rejected / correction_failed get the same card with
    their own status shown. The 'run the investigator' hint is reserved
    for a case with no draft at all — it was wrong for these states."""
    status = str(draft.get("status", ""))
    audit = _decided_audit(draft) if status in ("applied", "correction_failed") else None
    status_html = (
        f'<span class="ok">{_esc(status)}</span>'
        if status == "applied"
        else f'<span class="bad">{_esc(status)}</span>'
    )
    rows = f"<dt>status</dt><dd>{status_html}</dd>"
    rows += (
        "<dt>value change</dt><dd>"
        f"{_value_diff(draft.get('current_value'), draft.get('proposed_value'))}</dd>"
    )
    if status == "applied":
        rows += (
            "<dt>capability</dt><dd>single-use approval capability — "
            "consumed at execute (the executor refuses any replay)</dd>"
        )
    if draft.get("failure_reason"):
        rows += (
            f'<dt>failure reason</dt><dd class="bad">{_esc(draft["failure_reason"])}</dd>'
        )
    if audit is not None:
        rows += (
            f"<dt>approver</dt><dd>{_esc(audit.get('approver', '') or 'n/a')}</dd>"
            f"<dt>executed at</dt><dd>{_esc(audit.get('at', '') or 'n/a')}</dd>"
        )
    elif draft.get("approved_at"):
        rows += f"<dt>approved at</dt><dd>{_esc(draft['approved_at'])}</dd>"
    rows += (
        "<dt>audit entry</dt><dd><code>"
        f"{_esc(str(draft.get('audit_entry_id', '') or 'n/a'))}</code></dd>"
        f"<dt>draft id</dt><dd><code>{_esc(draft.get('draft_id', ''))}</code></dd>"
    )
    return (
        '<section class="card"><h2>Execution receipt</h2>'
        f"<dl>{rows}</dl>"
        '<p class="muted">read live from the runtime store — this state survives '
        "server restarts; nothing further is pending on this case</p></section>"
    )


def _correction_card(case_id: str, draft: dict | None) -> str:
    if draft is not None:
        rows = (
            f"<dt>field</dt><dd><code>{_esc(draft.get('field', ''))}</code></dd>"
            "<dt>value change</dt><dd>"
            f"{_value_diff(draft.get('current_value'), draft.get('proposed_value'))}</dd>"
            f"<dt>justification</dt><dd>{_value(draft.get('justification', ''))}</dd>"
            f"<dt>draft id</dt><dd><code>{_esc(draft.get('draft_id', ''))}</code>"
            f" — status {_esc(draft.get('status', ''))}</dd>"
        )
        return f'<section class="card"><h2>Proposed correction</h2><dl>{rows}</dl></section>'
    decided = _latest_draft(case_id)
    if decided is not None:
        return _decided_card(decided)
    return (
        '<section class="card"><h2>No pending correction draft</h2>'
        "<p>No pending correction draft. Run the investigation first: "
        f"<code>python -m approval.cli --customer {_esc(case_id)}</code></p></section>"
    )


def _csrf_field(state: dict) -> str:
    """The hidden nonce input for a decision form. Empty when the server
    was built without CSRF protection (auth_token/csrf_token=None — the
    explicit embedded/test posture), so every POST form carries the
    nonce exactly when the server will demand one."""
    token = state.get("csrf")
    if not token:
        return ""
    return f'<input type="hidden" name="csrf" value="{_esc(token)}">'


def _decision_card(draft: dict | None, state: dict) -> str:
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
        f'<form method="post" action="/approve">{_csrf_field(state)}'
        f'<button type="submit"{disabled}>APPROVE</button></form>'
        f'<form method="post" action="/reject">'
        f'<input type="text" name="reason" placeholder="rejection reason (audited)"{disabled}> '
        f'{_csrf_field(state)}<button type="submit"{disabled}>REJECT</button></form>'
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
        f"{_csrf_field(state)}"
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


def summarize_cases() -> list[dict]:
    """One row per seeded case (sorted), for the read-only /summary page.
    Sourced from the frozen seed + the runtime stores ONLY (latest
    ticket, pending draft, applied overrides) — never from the eval case
    definitions or seed annotations, so no ground-truth label can reach
    the page (leak discipline, docs/EVALUATION.md §6). The modern side is
    read through effective_modern_record() so an APPLIED correction
    override flips drift to False — the same read-your-writes overlay the
    read tools use, never a parallel truth."""
    seed = seed_data.load_seed()
    rows: list[dict] = []
    for case_id in sorted(seed["modern_system"]):
        legacy = seed["legacy_system"].get(case_id, {})
        modern = seed_data.effective_modern_record(case_id)
        ticket = latest_ticket(case_id)
        draft = latest_pending_draft(case_id)
        rows.append({
            "case_id": case_id,
            "drift": (
                legacy.get("BALANCE") != modern.get("balance")
                or legacy.get("STATUS") != modern.get("status")
            ),
            "legacy_balance": legacy.get("BALANCE"),
            "modern_balance": modern.get("balance"),
            "status_legacy": legacy.get("STATUS"),
            "status_modern": modern.get("status"),
            "ticket": (
                {
                    "ticket_id": ticket.get("ticket_id", ""),
                    "root_cause": ticket.get("root_cause", ""),
                    "confidence": ticket.get("confidence"),
                    "status": ticket.get("status", ""),
                }
                if ticket
                else None
            ),
            "pending_draft": (
                {
                    "draft_id": draft.get("draft_id", ""),
                    "field": draft.get("field", ""),
                    "current_value": draft.get("current_value"),
                    "proposed_value": draft.get("proposed_value"),
                }
                if draft
                else None
            ),
        })
    return rows


def _summary_section(rows: list[dict], active_case_id: str) -> str:
    """The /summary card: a read-only table, one row per seeded case —
    every dynamic value html.escape()d like every other card. NO forms:
    decisions happen only on a case's own single-case screen."""
    cells: list[str] = []
    for row in rows:
        ticket = row["ticket"]
        draft = row["pending_draft"]
        mark = " <strong>(this screen)</strong>" if row["case_id"] == active_case_id else ""
        root_cause = (
            f"{_esc(ticket['root_cause'])} (confidence {_value(ticket['confidence'])})"
            if ticket
            else '<span class="muted">no ticket yet</span>'
        )
        ticket_status = _esc(ticket["status"]) if ticket else "—"
        pending = (
            f"{_esc(draft['field'])}: {_value(draft['current_value'])}"
            f" -&gt; {_value(draft['proposed_value'])}"
            if draft
            else '<span class="muted">none</span>'
        )
        drift_cell = (
            '<td class="bad">drift</td>' if row["drift"] else '<td class="ok">aligned</td>'
        )
        cells.append(
            f"<tr><td><code>{_esc(row['case_id'])}</code>{mark}</td>{drift_cell}"
            f"<td>{root_cause}</td><td>{ticket_status}</td><td>{pending}</td></tr>"
        )
    return (
        '<section class="card"><h2>All five seed cases — read-only overview</h2>'
        '<table class="summary">'
        "<thead><tr><th>case</th><th>systems</th>"
        "<th>latest root cause</th><th>ticket status</th>"
        "<th>pending correction</th></tr></thead>"
        f"<tbody>{''.join(cells)}</tbody></table>"
        '<p class="muted">read live from the runtime store on every render; acting on a '
        "case happens on its own single-case screen (multi-case queue management "
        "remains out of scope, docs/build-contract.md §2.4)</p>"
        '<p><a href="/">back to this screen&rsquo;s case</a></p>'
        "</section>"
    )


def render_summary(active_case_id: str) -> str:
    """The /summary page: one read-only card over summarize_cases()."""
    return PAGE_SHELL.replace("__BODY__", _summary_section(summarize_cases(), active_case_id))


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
        '<p><a href="/summary">all five seed cases — read-only overview</a></p>'
        + (_error_card(error) if error else "")
        + _case_card(case_id, ticket)
        + _correction_card(case_id, draft)
        + _decision_card(draft, state)
        + _execution_card(state)
        + _replay_card(state)
        + _log_card(state)
    )
    return PAGE_SHELL.replace("__BODY__", body)


def _make_handler(
    case_id: str,
    approver: str,
    state: dict,
    lock: threading.Lock,
    auth_token: str | None = None,
    csrf_token: str | None = None,
) -> type:
    """Build the request-handler class with the session captured in a
    closure (one handler instance per connection; the shared state is
    serialized by `lock` because ThreadingHTTPServer serves each request
    on its own thread). auth_token/csrf_token: None disables that gate —
    the explicit embedded/test posture; main() always passes real
    per-session tokens (fail-closed), never None."""

    class ApprovalHandler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")  # the page is live state
            self.end_headers()
            self.wfile.write(body)

        def _credentials(self) -> tuple[str, str] | None:
            """Parse the Basic header into (username, password); None when
            absent or malformed. Never raises — an auth failure is a 401,
            not a 500."""
            header = self.headers.get("Authorization") or ""
            if not header.startswith("Basic "):
                return None
            try:
                decoded = base64.b64decode(
                    header[len("Basic "):].strip(), validate=True
                ).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                return None
            user, _, password = decoded.partition(":")
            return (user, password) if user else None

        def _authorized(self) -> bool:
            """The access gate, ahead of every request (GET and POST alike)
            and of any gate/executor code: without a valid token nothing
            renders and nothing runs. The username must be non-empty (it
            becomes the audited approver identity) and the password must
            equal the session's approver access token, compared
            constant-time."""
            if auth_token is None:
                return True  # the explicit embedded/test posture
            credentials = self._credentials()
            if credentials is None:
                return False
            user, password = credentials
            return bool(user.strip()) and hmac.compare_digest(
                password.encode("utf-8"), auth_token.encode("utf-8")
            )

        def _approver_identity(self) -> str:
            """Who the audit rows attribute: the authenticated username
            when auth is on (guaranteed non-empty past _authorized); the
            builder's `approver` argument otherwise."""
            if auth_token is not None:
                credentials = self._credentials()
                if credentials is not None and credentials[0].strip():
                    return credentials[0].strip()
            return approver

        def _send_unauthorized(self) -> None:
            body = b"approver authentication required\n"
            self.send_response(401)
            self.send_header(
                "WWW-Authenticate", 'Basic realm="approval", charset="UTF-8"'
            )
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
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
                if not self._authorized():
                    self._send_unauthorized()
                    return
                with lock:
                    path = urllib.parse.urlsplit(self.path).path
                    if path == "/summary":
                        # Read-only overview of all five seeded cases; the
                        # same session, lock, and (once auth lands) the
                        # same access gate as the decision page.
                        self._send(
                            200, render_summary(case_id).encode("utf-8"),
                            "text/html; charset=utf-8",
                        )
                        return
                    if path != "/":
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
                if not self._authorized():
                    self._send_unauthorized()
                    return
                form = self._form()  # parsed once; the CSRF check and the
                # reject handler consume the same body — a second read
                # would see an empty stream.
                with lock:
                    path = urllib.parse.urlsplit(self.path).path
                    if path not in ("/approve", "/reject", "/replay"):
                        self._send(404, b"not found\n", "text/plain; charset=utf-8")
                        return
                    if csrf_token is not None and not hmac.compare_digest(
                        form.get("csrf", "").encode("utf-8"),
                        csrf_token.encode("utf-8"),
                    ):
                        # Stale form (server restarted, nonce rotated) or a
                        # forged cross-origin POST: refused before any
                        # handler runs, so the store is untouched.
                        self._send(
                            400,
                            PAGE_SHELL.replace(
                                "__BODY__",
                                _error_card(
                                    "form nonce missing or wrong (stale form or "
                                    "forged request): nothing was changed"
                                ),
                            ).encode("utf-8"),
                            "text/html; charset=utf-8",
                        )
                        return
                    if path == "/approve":
                        self._do_approve()
                    elif path == "/reject":
                        self._do_reject(form)
                    else:
                        self._do_replay()
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

            approver = self._approver_identity()  # authenticated username when auth is on
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
            approver = self._approver_identity()  # authenticated username when auth is on
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
            approver = self._approver_identity()  # authenticated username when auth is on
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
    bind: str,
    port: int,
    case_id: str,
    approver: str,
    state: dict,
    auth_token: str | None = None,
    csrf_token: str | None = None,
) -> ThreadingHTTPServer:
    """The single construction path for the screen's server — main() and
    the HTTP-layer tests share it, so no second wiring can arise. The
    caller still owns serve_forever()/server_close(). auth_token and/or
    csrf_token None disables that gate (the explicit embedded/test
    posture); main() always passes real per-session tokens. A csrf_token
    is stashed into state["csrf"] so the served forms embed the same
    nonce the POST path will demand."""
    if csrf_token is not None:
        state["csrf"] = csrf_token
    cls = _ThreadingHTTPServerV6 if ":" in bind else ThreadingHTTPServer
    return cls(
        (bind, port),
        _make_handler(
            case_id, approver, state, threading.Lock(),
            auth_token=auth_token, csrf_token=csrf_token,
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m approval.web",
        description=(
            "Loopback single-case approval screen (docs/build-contract.md §2.4 minimum "
            "viable interface, auth amended 2026-09-10: every request must present the "
            "per-session approver access token)."
        ),
    )
    parser.add_argument(
        "--customer",
        required=True,
        help="canonical case/customer id (e.g. C-1001; validated against the seed)",
    )
    parser.add_argument("--port", type=int, default=8765, help="port to listen on (default: 8765)")
    parser.add_argument(
        "--auth-token",
        default=None,
        help=(
            "approver access token (the Basic-auth password; the username you type "
            "becomes the audited approver identity). Default: a random token "
            "generated for this session and printed once at startup — the screen "
            "never serves without one"
        ),
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
            "boundary (docs/build-contract.md §2.4)",
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
    # Fail-closed (§2.4 amendment, 2026-09-10): the screen never serves
    # without a per-session approver access token and CSRF nonce. An
    # operator-chosen --auth-token is not echoed back; a generated one is
    # printed exactly once, to the terminal that launched the server (the
    # operator is the trust anchor of this demo).
    approver_access_token = args.auth_token or secrets.token_urlsafe(16)
    server = build_server(
        args.bind, args.port, case_id, args.approver, state,
        auth_token=approver_access_token, csrf_token=secrets.token_urlsafe(16),
    )
    shown_host = f"[{args.bind}]" if ":" in args.bind else args.bind
    print(
        f"approval screen for case {case_id}: http://{shown_host}:{args.port}/ (Ctrl+C to stop)",
        flush=True,
    )
    if args.auth_token is None:
        print(
            "approver access token for this session (username = your name at the "
            f"browser prompt): {approver_access_token}",
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
