"""Five-case Gemini-judge validation — ONE complete benchmark execution
with the controlled provider split (2026-09-04 task contract):

    Agents:   Groq / openai/gpt-oss-120b      — UNCHANGED (agents/model.py)
    Judges:   Google / gemini-3.1-flash-lite  — native Strands GeminiModel
              via google-genai 2.22.0 ephemeral overlay, shared per case,
              module-global 4.3 s pacer (≤14 RPM) across ALL five cases
    SafeActionCompliance: deterministic — unchanged, no model

This driver is a THIN LOOP: it reuses, unchanged, the validated one-case
machinery — evals.token_canary.run_one_case (per-case recorder, artifacts,
OTel cross-check) and evals.gemini_judge_canary's credential gate, native
GeminiModel factory, judge swap, and pacer. Loop-safety properties relied
on (verified 2026-09-04 against installed source):

- the judge swap REPLACES evaluator.model each case (never nests wrappers),
  and evaluators read self.model at evaluate() time;
- install_agent_model_patches re-wraps the REAL agents.model.get_model
  (idempotent; the graph is rebuilt per case inside run_evals.run_case);
- one module-global pacer timeline spans all five cases (the ≤14 RPM bound
  holds across case boundaries — no burst at case starts);
- evals.run_evals is imported once (module cache); the judge swap runs on
  EVERY case so cases 2-5 stay on Gemini;
- each case gets its own out_dir (its own JSONL, summaries, cross-check);
  a case failure is recorded and the loop CONTINUES — no case is ever
  re-run (task contract §2/§23).

Everything else — prompts, rubrics, cases, tools, schemas, topology,
trajectory construction, scoring, retry semantics, evaluator context — is
byte-identical to the default benchmark. Results are NOT numerically
interchangeable with historical all-Groq runs (the judge model changed).

2026-09-05 (observation-only addition): per-case + run-root retry-evidence
capture for the now-ACTIVE GroqParsingFailedRetryStrategy — a snapshot-diff
of the module-global classification registry (agents.retry) plus the retry
canary's ledger-derived accounting. No evaluated path (prompts, tools,
evaluators, scoring, routing, cases, pacer, retry semantics) is touched,
and the registry is never reset during a run.
"""

import argparse
import json
import sys
import traceback
from functools import partial
from pathlib import Path
from typing import Any

from agents.retry import get_retry_evidence
from evals.gemini_judge_canary import (
    GEMINI_MODEL_ID,
    GEMINI_PROVIDER,
    MIN_INTERVAL_S,
    resolve_gemini_api_key,
    swap_judge_models_gemini,
)
from evals.groq_parsing_retry_canary import (
    RETRY_STRATEGY_NAME,
    derive_ledger_summary,
    read_ledger_rows,
)
from evals.token_canary import PROVIDER as AGENT_PROVIDER, MODEL_ID as AGENT_MODEL_ID
from evals.token_canary import run_one_case

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = (
    REPO_ROOT / "agent-memory" / "evidence" / "gemini-judge-5-case-2026-09-04"
)
EXPECTED_CASE_COUNT = 5  # the benchmark's configured size; anything else is a misconfiguration


def list_case_names() -> list[str]:
    """The configured benchmark cases, in configured order, evaluated once."""
    from evals.cases import test_cases

    return [case.name for case in test_cases]


def _case_dir(out_dir: Path, index: int, name: str) -> Path:
    """Per-case evidence subdirectory (distinct by construction: index + name)."""
    return out_dir / f"case-{index:02d}-{name}"


def build_case_retry_evidence(
    case: str,
    index: int,
    classification_count_before: int,
    case_dir: Path,
) -> dict[str, Any]:
    """Per-case retry evidence for the ACTIVE GroqParsingFailedRetryStrategy
    (observation-only): snapshot-diff of the module-global classification
    registry (agents.retry) merged with the retry canary's ledger-derived
    accounting from this case's token-usage.jsonl. Nothing is mutated and
    no evaluated path is touched."""
    evidence = get_retry_evidence()
    events = list(evidence.get("events", []))
    count_after = int(evidence.get("classification_count", len(events)))
    before = min(classification_count_before, len(events))
    return {
        "case": case,
        "case_index": index,
        "retry_strategy": RETRY_STRATEGY_NAME,
        "cumulative_classification_count_before": classification_count_before,
        "cumulative_classification_count_after": count_after,
        "delta_classifications": count_after - classification_count_before,
        "delta_events": events[before:],
        "ledger_derived": derive_ledger_summary(read_ledger_rows(Path(case_dir))),
        "note": (
            "module-global cumulative registry, never reset during the run; "
            "per-case attribution via snapshot-diff; classification_count "
            "counts classifications, not retries performed"
        ),
    }


def _write_case_retry_evidence(
    case: str,
    index: int,
    classification_count_before: int,
    case_dir: Path,
) -> dict[str, Any] | None:
    """Best-effort per-case retry-evidence write — MUST NEVER raise (a
    capture failure is printed; a rerun is never the remedy)."""
    try:
        payload = build_case_retry_evidence(
            case, index, classification_count_before, case_dir
        )
        case_dir = Path(case_dir)
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "retry-evidence.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        return payload
    except Exception as exc:  # observation must never alter the run
        print(
            f"[gemini-5case] RETRY-EVIDENCE CAPTURE FAILURE (best-effort, "
            f"NOT rerun): {type(exc).__name__}: {exc}",
            flush=True,
        )
        return None


def _write_run_retry_evidence(
    out_dir: Path,
    per_case: list[dict[str, Any] | None],
) -> None:
    """Best-effort run-root retry-evidence summary — MUST NEVER raise."""
    try:
        payload = {
            "retry_strategy": RETRY_STRATEGY_NAME,
            "cumulative": get_retry_evidence(),
            "per_case": [
                {
                    "case": p["case"],
                    "case_index": p["case_index"],
                    "delta_classifications": p["delta_classifications"],
                    "delta_events": p["delta_events"],
                    "ledger_derived": p["ledger_derived"],
                }
                for p in per_case
                if p is not None
            ],
            "note": (
                "observation-only capture (2026-09-05); the registry is "
                "module-global and cumulative across all five cases (one "
                "process); per-case rows are snapshot-diffs of it"
            ),
        }
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "retry-evidence-run.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
    except Exception as exc:  # observation must never alter the run
        print(
            f"[gemini-5case] RUN RETRY-EVIDENCE WRITE FAILURE (best-effort, "
            f"NOT rerun): {type(exc).__name__}: {exc}",
            flush=True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ONE five-case Gemini-judge / Groq-agent validation run"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="evidence root (per-case subdirs are created below it)",
    )
    args = parser.parse_args(argv)

    # --- credential gate (identical policy to the one-case canary) --------
    api_key = resolve_gemini_api_key()
    if not api_key:
        print(
            "[gemini-5case] BLOCKED: GEMINI_API_KEY is not available through the "
            "application's authorized configuration (environment or repo-root .env "
            "via the app's own loader). Per the task contract this experiment "
            "STOPS here: no sibling-project credential is read or copied.",
            flush=True,
        )
        return 3

    # --- case-set gate: exactly the configured five, before any import
    #     preflight or request (fail fast on a misconfigured benchmark) ----
    cases = list_case_names()
    if len(cases) != EXPECTED_CASE_COUNT:
        print(
            f"[gemini-5case] BLOCKED: expected exactly {EXPECTED_CASE_COUNT} "
            f"configured cases, found {len(cases)}: {cases} — refusing to run a "
            "non-standard case set.",
            flush=True,
        )
        return 2

    # --- native-path preflight (google-genai via the ephemeral overlay) ---
    try:
        import strands.models.gemini  # noqa: F401 — availability pre-flight
    except ModuleNotFoundError:
        print(
            "[gemini-5case] BLOCKED: google-genai is not installed in this "
            "environment. Run via the probes' ephemeral overlay (zero repo "
            "changes), e.g.:\n"
            "  uv run --frozen --with google-genai==2.22.0 \\\n"
            "      python -m evals.gemini_judge_5case",
            flush=True,
        )
        return 4

    # The VALIDATED one-case judge swap, bound once — called by run_one_case
    # per case so every case's four judges sit on one shared native Gemini
    # model writing to that case's recorder. The pacer inside the wrapper is
    # module-global, so pacing spans all five cases continuously.
    judge_swap = partial(swap_judge_models_gemini, api_key=api_key)

    print(
        f"[gemini-5case] judges -> {GEMINI_PROVIDER}/{GEMINI_MODEL_ID} (native); "
        f"agents unchanged on {AGENT_PROVIDER}/{AGENT_MODEL_ID}; "
        f"pacer {MIN_INTERVAL_S}s shared across all {EXPECTED_CASE_COUNT} cases",
        flush=True,
    )
    print(f"[gemini-5case] cases: {cases}", flush=True)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    retry_evidence_per_case: list[dict[str, Any] | None] = []
    overall_rc = 0

    for index, name in enumerate(cases, start=1):
        prefix = f"[gemini-5case {index}/{len(cases)}]"
        case_dir = _case_dir(args.out_dir, index, name)
        # snapshot BEFORE the case: the registry is module-global and
        # cumulative across all five cases, so per-case attribution is a
        # snapshot-diff (the registry is never reset during a run)
        registry_count_before = int(
            get_retry_evidence().get("classification_count", 0)
        )
        try:
            rc = run_one_case(
                name,
                case_dir,
                judge_swap=judge_swap,
                log_prefix=prefix,
            )
        except Exception as exc:  # record and CONTINUE — a driver-level
            # failure in one case never aborts or re-runs the others
            print(f"{prefix} DRIVER-LEVEL FAILURE: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
            rc = 1
        retry_evidence_per_case.append(
            _write_case_retry_evidence(name, index, registry_count_before, case_dir)
        )
        results.append(
            {"index": index, "case": name, "exit_code": rc, "dir": str(case_dir)}
        )
        print(f"{prefix} finished rc={rc}", flush=True)
        if rc != 0:
            overall_rc = 1

    all_zero = all(r["exit_code"] == 0 for r in results)
    _write_run_retry_evidence(args.out_dir, retry_evidence_per_case)
    (args.out_dir / "index.json").write_text(
        json.dumps(
            {
                "run": "gemini-judge-5-case-2026-09-04",
                "executions": 1,
                "judge_provider": GEMINI_PROVIDER,
                "judge_model": GEMINI_MODEL_ID,
                "agent_provider": AGENT_PROVIDER,
                "agent_model": AGENT_MODEL_ID,
                "pacer_min_interval_s": MIN_INTERVAL_S,
                "retry_strategy": RETRY_STRATEGY_NAME,
                "retry_evidence": "retry-evidence-run.json",
                "case_count": len(cases),
                "cases": results,
                "all_exit_zero": all_zero,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"[gemini-5case] all {len(results)} cases attempted once; "
        f"all_exit_zero={all_zero}; index at {args.out_dir / 'index.json'}",
        flush=True,
    )
    return overall_rc


if __name__ == "__main__":
    sys.exit(main())
