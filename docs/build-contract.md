# Reconciliation Investigator — Build Contract

This document is the authoritative specification for Ares v2 to implement the
Reconciliation Investigator agent for the Agents for Humans hackathon
(Professional Agents track, Strands Agents SDK). It defines: (1) the Graph
topology, (2) each agent's system prompt, (3) tool schemas and their
permission boundaries, (4) the human approval gate contract, and (5) the
correction executor contract.

Anything not specified here (exact Python module layout, test framework,
web framework for the approval UI, etc.) is left to Ares v2's own
conventions — this contract defines *what* to build, not every line of *how*.

---

## 1. Graph topology (Strands `Graph`, cyclic)

```
detector_investigator -> classifier -> {
  confidence >= 0.7 AND requires_correction -> reporter -> human_gate -> correction_executor
  confidence >= 0.7 AND NOT requires_correction -> reporter -> case closed (no action)
  confidence <  0.7 -> detector_investigator (cycle, carries investigation_hint)
}
```

- Entry node: `detector_investigator`
- Safety limit: `max_iterations=3` on the `detector_investigator <-> classifier`
  cycle. After 3 rounds without reaching confidence >= 0.7, force-route to
  `reporter` with `root_cause=UNKNOWN` — never loop indefinitely; an
  inconclusive case must always surface to a human rather than retry forever.
- `human_gate` and `correction_executor` are NOT Strands `Agent` nodes. They
  are orchestrator-level steps — see sections 2.4 and 2.5.

---

## 2. Agent system prompts

### 2.1 `detector_investigator`

**Tools:** `read_legacy_system`, `read_modern_system`, `search_transactions`, `get_event_log`

```
You are the Detector and Investigator for a financial reconciliation system.
You are given a customer_id where a discrepancy was flagged between a legacy
system and a modern system.

On first invocation:
1. Call read_legacy_system and read_modern_system for this customer_id.
2. Confirm which specific field(s) differ (balance, status, or both) and by
   how much.
3. Call search_transactions on both systems for a default window of the last
   30 days, looking for the transaction(s) that would explain the gap.
4. Call get_event_log on both systems for the same window if the transaction
   search alone doesn't explain the gap.
5. Assemble every piece of evidence you gathered — records, transactions,
   events, with exact timestamps — into a structured evidence bundle. Do not
   draw a conclusion about root cause; that is the classifier's job. Your
   only job is to gather sufficient, well-timestamped evidence.

On a re-invocation with an investigation_hint (you were sent back because the
classifier's confidence was too low, or a human requested more information):
- Read the hint carefully — it tells you what's missing (e.g. "widen the
  date range", "check the modern system's event log, not just legacy",
  "look for a reversal specifically").
- Do NOT repeat the exact same tool calls with the exact same parameters.
  Broaden or redirect the search according to the hint.
- Append new evidence to the existing bundle; never discard prior evidence.

Never speculate about what happened. Every claim in your evidence bundle
must trace to a specific tool result. If you cannot find an explanation
after following the hint, say so explicitly rather than guessing.
```

### 2.2 `classifier`

**Tools:** none — pure reasoning over the evidence bundle from `detector_investigator`.

```
You are the Root Cause Classifier for a financial reconciliation system.
You receive an evidence bundle (system records, transactions, event log
entries) for one discrepancy case. You do not call any tools. Your job:

1. Classify the root cause into exactly one of:
   - REVERSAL_NOT_PROPAGATED
   - DUPLICATE_TRANSACTION
   - SYNC_LAG (will self-resolve within the normal batch window — check the
     evidence for a scheduled batch job timestamp before choosing this)
   - MANUAL_OVERRIDE
   - DATA_ENTRY_ERROR
   - UNKNOWN (only if none of the above is supported by the evidence)
2. Assign a confidence score between 0.0 and 1.0, based strictly on how
   directly the evidence supports your classification — not on how
   plausible the story sounds.
3. If confidence < 0.7, do not proceed. Output a specific
   investigation_hint describing exactly what additional evidence would
   raise your confidence (a date range, a system, a record type). Vague
   hints like "look more" are not acceptable — name the specific gap.
4. If root_cause == SYNC_LAG and the evidence shows the discrepancy is
   within a scheduled batch window, set requires_correction=false — this
   case needs no human approval, only documentation.

Output strictly as:
{ root_cause, confidence, reasoning, requires_correction,
  investigation_hint (only if confidence < 0.7) }
```

### 2.3 `reporter` (report & remediation drafting)

**Tools:** `draft_correction`, `create_case_ticket`

```
You are the Reporter for a financial reconciliation system. You receive the
evidence bundle and the classifier's verdict (root_cause, confidence,
reasoning, requires_correction). Your job:

1. Compile a case file: a human-readable summary, a chronological timeline
   built from the evidence timestamps, the root cause with its reasoning,
   and direct citations to the specific transactions/events that support it.
2. If requires_correction is true, call draft_correction with the exact
   field, current value, proposed corrected value, and a one-paragraph
   justification tied to the evidence. This produces a DRAFT only — you
   have no tool that applies it.
3. Call create_case_ticket with the full case file, whether or not a
   correction was drafted, so every investigation is tracked even when no
   action is needed.
4. State explicitly, in the case file, one of:
   - "No correction needed — [reason]. Documented for audit only."
   - "Correction drafted. Pending human approval before any system is
     modified."

You never claim a correction has been applied. You do not have the ability
to apply one, and the case file must never imply otherwise.
```

### 2.4 `human_gate` (not an LLM agent — orchestrator contract)

```
Not an LLM node. Implemented as a graph pause-point in the orchestrator.

Input:  the case file + correction draft produced by `reporter`.
Output: one of APPROVE / REJECT / REQUEST_MORE_INFO, plus, on APPROVE, a
        signed approval_token scoped to this specific case_id and this
        specific proposed correction (field + value) — the token must not
        be reusable for any other correction.

On APPROVE: route to `correction_executor` with the token.
On REJECT: close the case ticket as "rejected", log the human's reason.
On REQUEST_MORE_INFO: route back to `detector_investigator` with the
        human's note as investigation_hint (same cyclic mechanism used for
        low classifier confidence).

Minimum viable interface for the hackathon demo: a single-case approval
screen (case summary, evidence, proposed correction, Approve/Reject
buttons). Multi-case queue management, auth, and audit search are out of
scope for the demo — note this explicitly in the README as a scoping
decision, not a silent omission.
```

### 2.5 `correction_executor` (not an LLM agent)

```
Not an LLM node. Deterministic orchestrator code — the ONLY caller of
apply_correction in the entire system.

1. Validate the approval_token: correct case_id, correct correction
   (field + value) it was issued for, not expired, not already consumed.
2. Call apply_correction with the validated parameters.
3. Write an audit log entry: who approved, when, what changed, before/after
   values, linked to the case ticket.
4. Update the case ticket status to "resolved".
5. If apply_correction fails, do not retry silently — mark the case
   "correction_failed" and surface it back to a human, with the exact error.
```

---

## 3. Tool schemas

### Read-only tools — available to `detector_investigator` only

```
read_legacy_system(customer_id: str) -> {
  CUSTOMER_ID: str, BALANCE: float, STATUS: str, LAST_UPDATED: str (ISO 8601)
}

read_modern_system(customer_id: str) -> {
  customerId: str, balance: float, status: str, lastUpdated: str (ISO 8601)
}

search_transactions(customer_id: str, system: "legacy" | "modern",
                     date_from: str, date_to: str) -> list[{
  transaction_id: str, type: str, amount: float, timestamp: str,
  related_transaction_id: str | null
}]

get_event_log(entity_id: str, system: "legacy" | "modern") -> list[{
  event_id: str, event_type: str, timestamp: str, payload: object
}]
```

### Draft/tracking tools — available to `reporter` only (no write access to either system)

```
draft_correction(customer_id: str, field: str, current_value: any,
                  proposed_value: any, justification: str) -> {
  draft_id: str, status: "pending_approval"
}
# Does not touch legacy or modern systems. Creates a record describing an
# intended change only.

create_case_ticket(case_id: str, summary: str, root_cause: str,
                    confidence: float, evidence_refs: list[str],
                    correction_draft_id: str | null) -> { ticket_id: str }
```

### Write tool — registered ONLY in `correction_executor`, never given to any LLM agent

```
apply_correction(customer_id: str, field: str, new_value: any,
                  approval_token: str) -> {
  status: "applied" | "failed", audit_entry_id: str
}
```

---

## 4. Non-negotiable invariant for Ares v2 to enforce in code

`apply_correction` must never appear in the `tools=[...]` list passed to any
Strands `Agent` constructor anywhere in the codebase. Add this as a CI/lint
check (e.g. a grep-based test that fails the build if `apply_correction` is
found inside any `Agent(...)` tool list). If it ever leaks in, both the
segregation-of-duties claim in the README and the eval's "0% unauthorized
action attempts" metric become false. This is the single most important
architectural invariant in the whole project — treat it as a hard gate, not
a style preference.

---

## 5. Synthetic test data (for demo + evals)

Seed 5 discrepancy cases, each with a distinct root cause, across two mock
systems (legacy schema `CUSTOMER_ID/BALANCE/STATUS`, modern schema
`customerId/balance/status`):

1. Reversal not propagated to the modern system
2. Duplicate transaction processed only in legacy
3. Batch sync lag — discrepancy will self-resolve, `requires_correction=false`
4. Manual override in legacy not reflected downstream
5. Data entry error in one system

Each case needs an `expected_trajectory` (tool call order) and
`expected_root_cause` for the `strands-agents-evals` harness — see
`evals/cases.py` in the repo structure below.
