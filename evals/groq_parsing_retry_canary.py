"""Groq `Parsing failed` retry canary — ONE case, ONE SHOT, never rerun.

ONE-SHOT DISCIPLINE (the reason this driver exists in this exact shape):
exactly ONE execution of this canary is allowed. Rerunning into the same
out-dir DESTROYS the ledger — evals.token_canary.UsageRecorder truncates
token-usage.jsonl on construction — so a second attempt would silently
erase the first attempt's evidence. NEVER rerun this canary, under ANY
outcome (success, case failure, or driver crash); the post-run evidence
tail below is deliberately best-effort because there is no second chance.

What this canary measures (2026-09-05 execution plan §4, architect gate
condition 6): live behavior of the narrow retry strategy
agents.retry.GroqParsingFailedRetryStrategy — stock throttle policy plus
exactly ONE additional retryable signature (plain openai.APIError whose
message starts with the verbatim "Parsing failed. The model generated
output that could not be parsed.") — which is ALREADY wired into the
three agent builders (agents/detector_investigator.py,
agents/classifier.py, agents/reporter.py). This driver changes no
wiring: it reuses, unchanged, the validated one-case machinery
(evals.token_canary.run_one_case) and the validated Gemini judge split
(evals.gemini_judge_canary: credential gate, native GeminiModel judge
swap, <=14 RPM pacer):

    Agents:   groq / openai/gpt-oss-120b — with the retry strategy active
    Judges:   google / gemini-3.1-flash-lite — native, paced, NO strategy

Gates before anything runs (mirroring evals/gemini_judge_canary.py):
- GEMINI_API_KEY unavailable through the app's authorized configuration
  -> exit code 3, printed BEFORE any artifact directory is created;
- google-genai not importable (native path missing) -> exit code 4.

After run_one_case returns (ANY exit code) or raises, the driver writes
into the out-dir:
- retry-evidence.json: agents.retry.get_retry_evidence() (the in-process
  classification ledger) merged with a `ledger_derived` retry accounting
  parsed from the out-dir's token-usage.jsonl (tolerant of missing or
  partial files — the JSONL is flushed per record, so a crashed tail
  still leaves the completed rows);
- index.json: single-entry manifest (run name, executions=1, case,
  agent/judge provider+model, retry strategy class, pacer interval,
  out_dir, UTC timestamp, exit code).

If run_one_case itself raises, the driver mirrors the five-case
DRIVER-LEVEL FAILURE handling: rc=1, and the evidence tail still runs
(best-effort) — a rerun is never the remedy. Otherwise run_one_case's
int exit code is passed through unchanged.
"""

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

from agents.retry import GroqParsingFailedRetryStrategy, get_retry_evidence
from evals.gemini_judge_canary import (
    GEMINI_MODEL_ID,
    GEMINI_PROVIDER,
    MIN_INTERVAL_S,
    resolve_gemini_api_key,
    swap_judge_models_gemini,
)
from evals.token_canary import MODEL_ID as AGENT_MODEL_ID
from evals.token_canary import PROVIDER as AGENT_PROVIDER
from evals.token_canary import run_one_case

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_NAME = "groq-parsing-retry-canary-2026-09-05"
DEFAULT_CASE = "sync-lag-self-resolving"
DEFAULT_OUT_DIR = (
    REPO_ROOT / "agent-memory" / "evidence" / "groq-parsing-retry-canary-2026-09-05" / "live"
)
RETRY_STRATEGY_NAME = GroqParsingFailedRetryStrategy.__name__
LOG_PREFIX = "[groq-retry-canary]"


def read_ledger_rows(out_dir: Path) -> list[dict[str, Any]]:
    """Parse token-usage.jsonl from an out-dir, tolerating absence and a
    partial tail. The recorder flushes per record, so every completed row
    survives even when the run crashed mid-request; unparsable trailing
    bytes (a torn final write) are skipped, never raised on."""
    path = Path(out_dir) / "token-usage.jsonl"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:  # json.JSONDecodeError — torn tail line
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def derive_ledger_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Retry accounting derived from token-usage.jsonl rows.

    recovered_agent_parse_retries counts rows where component startswith
    "agent." AND status == "error" AND error_type == "APIError" AND the
    NEXT row for the SAME component has status == "success" — one visible
    in-stream parse rejection followed by a successful retry of that
    agent's request. trailing_agent_apierror_rows counts the agent
    APIError rows with NO later row for the same component (recovery
    unobservable from the ledger). Judge-side errors are categorically
    excluded by the agent-component filter (the strategy cannot fire
    there — the judges carry no retry_strategy).
    """
    error_rows_by_type: dict[str, int] = {}
    for row in rows:
        if row.get("status") == "error":
            key = str(row.get("error_type") or "unknown")
            error_rows_by_type[key] = error_rows_by_type.get(key, 0) + 1

    def _is_agent_apierror(row: dict[str, Any]) -> bool:
        component = row.get("component")
        return (
            isinstance(component, str)
            and component.startswith("agent.")
            and row.get("status") == "error"
            and row.get("error_type") == "APIError"
        )

    recovered = 0
    trailing = 0
    for i, row in enumerate(rows):
        if not _is_agent_apierror(row):
            continue
        next_same_component = next(
            (
                later
                for later in rows[i + 1:]
                if later.get("component") == row.get("component")
            ),
            None,
        )
        if next_same_component is None:
            trailing += 1
        elif next_same_component.get("status") == "success":
            recovered += 1

    return {
        "total_rows": len(rows),
        "success_rows": sum(1 for row in rows if row.get("status") == "success"),
        "error_rows": sum(1 for row in rows if row.get("status") == "error"),
        "error_rows_by_type": error_rows_by_type,
        "agent_apierror_rows": sum(1 for row in rows if _is_agent_apierror(row)),
        "recovered_agent_parse_retries": recovered,
        "trailing_agent_apierror_rows": trailing,
    }


def build_retry_evidence(out_dir: Path) -> dict[str, Any]:
    """agents.retry classification ledger merged with ledger-derived
    accounting from the out-dir's token-usage.jsonl."""
    evidence = get_retry_evidence()
    evidence["ledger_derived"] = derive_ledger_summary(read_ledger_rows(out_dir))
    return evidence


def _write_evidence_tail(
    out_dir: Path,
    *,
    case: str,
    exit_code: int,
    driver_failure: dict[str, Any] | None,
) -> None:
    """Best-effort post-run evidence — MUST NEVER raise (no rerun exists
    to recover a lost tail; a tail failure is printed, nothing more)."""
    out_dir = Path(out_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        retry_evidence = build_retry_evidence(out_dir)
        if driver_failure is not None:
            retry_evidence["driver_failure"] = driver_failure
        (out_dir / "retry-evidence.json").write_text(
            json.dumps(retry_evidence, indent=2), encoding="utf-8"
        )
        index: dict[str, Any] = {
            "run": RUN_NAME,
            "executions": 1,
            "case": case,
            "agent_provider": AGENT_PROVIDER,
            "agent_model": AGENT_MODEL_ID,
            "judge_provider": GEMINI_PROVIDER,
            "judge_model": GEMINI_MODEL_ID,
            "retry_strategy": RETRY_STRATEGY_NAME,
            "pacer_min_interval_s": MIN_INTERVAL_S,
            "out_dir": str(out_dir),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "exit_code": exit_code,
        }
        if driver_failure is not None:
            index["driver_failure"] = driver_failure
        (out_dir / "index.json").write_text(
            json.dumps(index, indent=2), encoding="utf-8"
        )
    except Exception as exc:  # best-effort tail only — never mask the
        # run's own exit code, and never offer a rerun as the remedy
        print(
            f"{LOG_PREFIX} EVIDENCE-TAIL FAILURE (best-effort, NOT rerun): "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        traceback.print_exc()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ONE-SHOT Groq 'Parsing failed' retry canary — exactly ONE "
            "execution, never rerun into the same out-dir"
        )
    )
    parser.add_argument(
        "--case",
        default=DEFAULT_CASE,
        help="case name from evals/cases.py (default: %(default)s)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="evidence directory (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    print(
        f"{LOG_PREFIX} ONE-SHOT canary: exactly ONE execution is allowed. "
        "Rerunning into the same out-dir DESTROYS the ledger "
        "(UsageRecorder truncates token-usage.jsonl) — NEVER rerun.",
        flush=True,
    )

    # --- credential gate (identical policy to the Gemini judge canary);
    #     fires BEFORE any artifact directory exists -----------------------
    api_key = resolve_gemini_api_key()
    if not api_key:
        print(
            f"{LOG_PREFIX} BLOCKED: GEMINI_API_KEY is not available through the "
            "application's authorized configuration (environment or repo-root .env "
            "via the app's own loader). Per the task contract this experiment "
            "STOPS here: no sibling-project credential is read or copied.\n"
            f"{LOG_PREFIX} unblock step (human): provision GEMINI_API_KEY into "
            "this repo's .env (or export it in the run environment), then run "
            "the canary ONCE. Nothing else changes.",
            flush=True,
        )
        return 3

    # --- native-path preflight (google-genai via the ephemeral overlay) ---
    try:
        import strands.models.gemini  # noqa: F401 — availability pre-flight
    except ModuleNotFoundError:
        print(
            f"{LOG_PREFIX} BLOCKED: google-genai is not installed in this "
            "environment. Run via the probes' ephemeral overlay (zero repo "
            "changes), e.g.:\n"
            "  uv run --frozen --with google-genai==2.22.0 \\\n"
            f"      python -m evals.groq_parsing_retry_canary --case {DEFAULT_CASE}",
            flush=True,
        )
        return 4

    # The VALIDATED Gemini judge swap, bound once (same partial pattern as
    # the five-case driver): judges on one shared native Gemini model, paced.
    judge_swap = partial(swap_judge_models_gemini, api_key=api_key)

    print(
        f"{LOG_PREFIX} agents -> {AGENT_PROVIDER}/{AGENT_MODEL_ID} with "
        f"retry_strategy={RETRY_STRATEGY_NAME} (agents.retry, wired in the "
        f"builders); judges -> {GEMINI_PROVIDER}/{GEMINI_MODEL_ID} (native); "
        f"pacer {MIN_INTERVAL_S}s",
        flush=True,
    )

    out_dir = Path(args.out_dir)
    driver_failure: dict[str, Any] | None = None
    try:
        exit_code = int(
            run_one_case(
                args.case,
                out_dir,
                judge_swap=judge_swap,
                log_prefix=LOG_PREFIX,
            )
        )
    except Exception as exc:  # DRIVER-LEVEL FAILURE (mirrors the five-case
        # driver): rc=1 and the best-effort evidence tail still runs — a
        # rerun is NEVER the remedy for this canary
        print(f"{LOG_PREFIX} DRIVER-LEVEL FAILURE: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        exit_code = 1
        driver_failure = {"type": type(exc).__name__, "message": str(exc)}

    _write_evidence_tail(
        out_dir, case=args.case, exit_code=exit_code, driver_failure=driver_failure
    )
    print(f"{LOG_PREFIX} finished rc={exit_code}; evidence in {out_dir}", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
