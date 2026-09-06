"""Offline hermetic tests for the Groq `Parsing failed` retry canary driver.

No model, no network, no google-genai required (the native-path preflight
is faked via sys.modules, or its ModuleNotFoundError is forced through a
monkeypatched builtins.__import__). The repo .env is never relied upon:
the dotenv loader inside evals.gemini_judge_canary is monkeypatched to a
no-op and GEMINI_API_KEY is controlled via the environment. run_one_case
is always a fake — the canary itself is ONE-SHOT and must never execute
from a test.
"""

import builtins
import importlib
import json
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

import agents.retry as agents_retry
import evals.gemini_judge_canary as gjc
import evals.groq_parsing_retry_canary as driver


def _row(component: str, status: str, error_type: str | None = None, seq: int = 1) -> dict:
    """A minimal token-usage.jsonl row (only the fields the ledger-derived
    parser reads carry meaning; the rest are shape-faithful filler)."""
    is_judge = component.startswith("judge.")
    return {
        "timestamp": "2026-09-05T00:00:00.000+00:00",
        "case_id": "sync-lag-self-resolving",
        "component": component,
        "component_type": "judge" if is_judge else "agent",
        "model": "gemini-3.1-flash-lite" if is_judge else "openai/gpt-oss-120b",
        "provider": "google" if is_judge else "groq",
        "input_tokens": 100 if status == "success" else None,
        "output_tokens": 20 if status == "success" else None,
        "total_tokens": 120 if status == "success" else None,
        "request_number": seq,
        "status": status,
        "error_type": error_type,
        "had_usage": status == "success",
    }


def _fake_gemini_module(monkeypatch):
    # The native-path pre-flight does `import strands.models.gemini`; inject
    # a stub so the happy path can be exercised without google-genai.
    stub = types.ModuleType("strands.models.gemini")
    monkeypatch.setitem(sys.modules, "strands.models.gemini", stub)


def _hermetic_credential(monkeypatch, key: str = "dummy-key") -> None:
    monkeypatch.setenv("GEMINI_API_KEY", key)
    monkeypatch.setattr(gjc, "_load_repo_dotenv", lambda: None)


# --- module surface / CLI defaults -----------------------------------------


def test_driver_constants():
    assert driver.RUN_NAME == "groq-parsing-retry-canary-2026-09-05"
    assert driver.DEFAULT_CASE == "sync-lag-self-resolving"
    assert driver.DEFAULT_OUT_DIR == (
        driver.REPO_ROOT
        / "agent-memory"
        / "evidence"
        / "groq-parsing-retry-canary-2026-09-05"
        / "live"
    )
    assert driver.RETRY_STRATEGY_NAME == "GroqParsingFailedRetryStrategy"


def test_cli_defaults_flow_through(tmp_path, monkeypatch):
    _fake_gemini_module(monkeypatch)
    _hermetic_credential(monkeypatch)
    default_out = tmp_path / "default-live"
    monkeypatch.setattr(driver, "DEFAULT_OUT_DIR", default_out)

    calls = []

    def fake_run_one_case(case_name, out_dir, judge_swap=None, log_prefix=""):
        calls.append((case_name, Path(out_dir)))
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        return 0

    monkeypatch.setattr(driver, "run_one_case", fake_run_one_case)
    rc = driver.main([])  # no arguments at all — pure CLI defaults
    assert rc == 0
    assert calls == [("sync-lag-self-resolving", default_out)]
    assert (default_out / "index.json").exists()


# --- gates (fire before any artifact exists) --------------------------------


def test_main_blocks_without_credential_before_any_artifact(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(gjc, "_load_repo_dotenv", lambda: None)
    out = tmp_path / "out"
    rc = driver.main(["--out-dir", str(out)])
    assert rc == 3
    assert not out.exists()  # gate fires BEFORE any artifact directory
    captured = capsys.readouterr().out
    assert "BLOCKED" in captured and "GEMINI_API_KEY" in captured


def test_main_blocks_without_native_path(tmp_path, monkeypatch, capsys):
    _hermetic_credential(monkeypatch)
    # Force the exact exception the preflight catches, deterministically,
    # whether or not google-genai happens to be installed.
    real_import = builtins.__import__

    def forcing_import(name, *args, **kwargs):
        if name == "strands.models.gemini":
            raise ModuleNotFoundError(f"No module named {name!r} (forced for test)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forcing_import)
    out = tmp_path / "out"
    rc = driver.main(["--out-dir", str(out)])
    assert rc == 4
    assert not out.exists()  # native-path gate also fires before artifacts
    captured = capsys.readouterr().out
    assert "BLOCKED" in captured and "google-genai" in captured


# --- ledger-derived retry accounting ----------------------------------------


def test_ledger_recovery_same_component():
    # (a) an agent APIError row whose next row for the SAME component is a
    # success — one visible parse-retry recovery (a different component in
    # between must not break the same-component lookup).
    rows = [
        _row("agent.detector", "error", "APIError", 1),
        _row("agent.classifier", "success", None, 2),
        _row("agent.detector", "success", None, 3),
    ]
    s = driver.derive_ledger_summary(rows)
    assert s["total_rows"] == 3
    assert s["success_rows"] == 2
    assert s["error_rows"] == 1
    assert s["error_rows_by_type"] == {"APIError": 1}
    assert s["agent_apierror_rows"] == 1
    assert s["recovered_agent_parse_retries"] == 1
    assert s["trailing_agent_apierror_rows"] == 0


def test_ledger_no_recovery_when_only_other_components_follow():
    # (b) an agent APIError row followed only by a DIFFERENT component —
    # not recovered; and with no later same-component row, its recovery is
    # unobservable from the ledger (trailing).
    rows = [
        _row("agent.detector", "error", "APIError", 1),
        _row("judge.trajectory", "success", None, 2),
    ]
    s = driver.derive_ledger_summary(rows)
    assert s["agent_apierror_rows"] == 1
    assert s["recovered_agent_parse_retries"] == 0
    assert s["trailing_agent_apierror_rows"] == 1


def test_ledger_trailing_apierror_not_recovered():
    # (c) a trailing agent APIError error row (last row of the ledger) —
    # not recovered, unobservable.
    rows = [
        _row("agent.detector", "success", None, 1),
        _row("agent.classifier", "error", "APIError", 2),
    ]
    s = driver.derive_ledger_summary(rows)
    assert s["recovered_agent_parse_retries"] == 0
    assert s["trailing_agent_apierror_rows"] == 1


def test_ledger_ignores_judge_side_status_errors():
    # (d) judge-side APIStatusError rows never reach the agent filter —
    # the retry strategy cannot fire on the judge path.
    rows = [
        _row("judge.trajectory", "error", "APIStatusError", 1),
        _row("judge.trajectory", "success", None, 2),
        _row("agent.reporter", "success", None, 3),
    ]
    s = driver.derive_ledger_summary(rows)
    assert s["agent_apierror_rows"] == 0
    assert s["recovered_agent_parse_retries"] == 0
    assert s["trailing_agent_apierror_rows"] == 0
    assert s["error_rows"] == 1
    assert s["error_rows_by_type"] == {"APIStatusError": 1}


def test_ledger_error_rows_by_type_and_throttle_exclusion():
    rows = [
        _row("agent.detector", "error", "ModelThrottledException", 1),
        _row("agent.detector", "success", None, 2),
        _row("agent.classifier", "error", "APIError", 3),
    ]
    s = driver.derive_ledger_summary(rows)
    assert s["error_rows_by_type"] == {"ModelThrottledException": 1, "APIError": 1}
    # the throttle row recovered, but it is NOT an APIError parse row
    assert s["agent_apierror_rows"] == 1
    assert s["recovered_agent_parse_retries"] == 0
    assert s["trailing_agent_apierror_rows"] == 1


def test_ledger_missing_file_yields_zeros_no_raise(tmp_path):
    # (e) no token-usage.jsonl at all — zeros, never an exception, and the
    # classification-ledger half of the evidence is still intact.
    agents_retry.reset_retry_evidence()
    assert driver.read_ledger_rows(tmp_path) == []
    zeros = {
        "total_rows": 0,
        "success_rows": 0,
        "error_rows": 0,
        "error_rows_by_type": {},
        "agent_apierror_rows": 0,
        "recovered_agent_parse_retries": 0,
        "trailing_agent_apierror_rows": 0,
    }
    assert driver.derive_ledger_summary([]) == zeros
    evidence = driver.build_retry_evidence(tmp_path)
    assert evidence["ledger_derived"] == zeros
    assert evidence["strategy_class"] == "GroqParsingFailedRetryStrategy"
    assert evidence["classification_count"] == 0
    assert evidence["events"] == []
    assert isinstance(evidence["note"], str)


def test_read_ledger_rows_tolerates_partial_tail(tmp_path):
    # The recorder flushes per record; a crashed artifact tail can leave a
    # torn final line — the reader keeps the complete rows, never raises.
    good1 = json.dumps(_row("agent.detector", "error", "APIError", 1))
    good2 = json.dumps(_row("agent.detector", "success", None, 2))
    (tmp_path / "token-usage.jsonl").write_text(
        good1 + "\n" + good2 + "\n" + '{"component": "agent.repo',
        encoding="utf-8",
    )
    rows = driver.read_ledger_rows(tmp_path)
    assert len(rows) == 2
    assert driver.derive_ledger_summary(rows)["recovered_agent_parse_retries"] == 1


# --- end-to-end driver path (run_one_case faked; canary never executes) -----


def test_main_writes_index_and_retry_evidence(tmp_path, monkeypatch):
    _fake_gemini_module(monkeypatch)
    _hermetic_credential(monkeypatch)
    agents_retry.reset_retry_evidence()

    swaps = []
    monkeypatch.setattr(
        driver,
        "swap_judge_models_gemini",
        lambda module, recorder, api_key=None: swaps.append((module, recorder, api_key)),
    )

    calls = []

    def fake_run_one_case(case_name, out_dir, judge_swap=None, log_prefix=""):
        calls.append((case_name, Path(out_dir), judge_swap, log_prefix))
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        rows = [
            _row("agent.detector", "error", "APIError", 1),
            _row("agent.detector", "success", None, 2),
            _row("judge.trajectory", "error", "APIStatusError", 3),
            _row("agent.reporter", "success", None, 4),
        ]
        with (out / "token-usage.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return 0

    monkeypatch.setattr(driver, "run_one_case", fake_run_one_case)

    out = tmp_path / "live"
    rc = driver.main(["--out-dir", str(out)])
    assert rc == 0

    # exactly one execution, with the validated judge swap bound through
    assert len(calls) == 1
    case_name, out_arg, swap, prefix = calls[0]
    assert case_name == "sync-lag-self-resolving"
    assert out_arg == out
    assert prefix == driver.LOG_PREFIX
    assert callable(swap)
    swap("fake_module", "fake_recorder")
    assert swaps == [("fake_module", "fake_recorder", "dummy-key")]

    index = json.loads((out / "index.json").read_text())
    assert index["run"] == "groq-parsing-retry-canary-2026-09-05"
    assert index["executions"] == 1
    assert index["case"] == "sync-lag-self-resolving"
    assert index["agent_provider"] == "groq"
    assert index["agent_model"] == "openai/gpt-oss-120b"
    assert index["judge_provider"] == "google"
    assert index["judge_model"] == "gemini-3.1-flash-lite"
    assert index["retry_strategy"] == "GroqParsingFailedRetryStrategy"
    assert index["pacer_min_interval_s"] == driver.MIN_INTERVAL_S
    assert index["out_dir"] == str(out)
    assert index["exit_code"] == 0
    timestamp = datetime.fromisoformat(index["timestamp_utc"])
    assert timestamp.utcoffset() == timedelta(0)
    assert "driver_failure" not in index

    evidence = json.loads((out / "retry-evidence.json").read_text())
    assert evidence["strategy_class"] == "GroqParsingFailedRetryStrategy"
    assert evidence["signature_prefix"] == agents_retry.GROQ_PARSING_FAILED_PREFIX
    assert evidence["classification_count"] == 0
    assert evidence["events"] == []
    assert isinstance(evidence["note"], str)
    ledger = evidence["ledger_derived"]
    assert ledger["total_rows"] == 4
    assert ledger["success_rows"] == 2
    assert ledger["error_rows"] == 2
    assert ledger["error_rows_by_type"] == {"APIError": 1, "APIStatusError": 1}
    assert ledger["agent_apierror_rows"] == 1
    assert ledger["recovered_agent_parse_retries"] == 1
    assert ledger["trailing_agent_apierror_rows"] == 0


def test_main_driver_level_failure_still_writes_evidence(tmp_path, monkeypatch, capsys):
    _fake_gemini_module(monkeypatch)
    _hermetic_credential(monkeypatch)
    agents_retry.reset_retry_evidence()

    def raising_run_one_case(case_name, out_dir, judge_swap=None, log_prefix=""):
        raise RuntimeError("simulated driver-level blowup")

    monkeypatch.setattr(driver, "run_one_case", raising_run_one_case)
    out = tmp_path / "live"
    rc = driver.main(["--out-dir", str(out)])
    assert rc == 1
    captured = capsys.readouterr().out
    assert "DRIVER-LEVEL FAILURE" in captured and "RuntimeError" in captured

    index = json.loads((out / "index.json").read_text())
    assert index["exit_code"] == 1
    assert index["executions"] == 1
    assert index["case"] == "sync-lag-self-resolving"
    assert index["driver_failure"] == {
        "type": "RuntimeError",
        "message": "simulated driver-level blowup",
    }

    evidence = json.loads((out / "retry-evidence.json").read_text())
    assert evidence["driver_failure"]["type"] == "RuntimeError"
    assert evidence["ledger_derived"] == {
        "total_rows": 0,
        "success_rows": 0,
        "error_rows": 0,
        "error_rows_by_type": {},
        "agent_apierror_rows": 0,
        "recovered_agent_parse_retries": 0,
        "trailing_agent_apierror_rows": 0,
    }


def test_evidence_tail_failure_never_raises(tmp_path, monkeypatch, capsys):
    # A best-effort tail failure (out-dir path occupied by a file) must be
    # reported, never raised — and must not mask the run's own exit code
    # (a rerun is not a remedy for this ONE-SHOT canary).
    _fake_gemini_module(monkeypatch)
    _hermetic_credential(monkeypatch)
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where the directory should go", encoding="utf-8")
    monkeypatch.setattr(
        driver,
        "run_one_case",
        lambda case_name, out_dir, judge_swap=None, log_prefix="": 0,
    )
    rc = driver.main(["--out-dir", str(blocker)])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "EVIDENCE-TAIL FAILURE" in captured


def test_driver_does_not_import_run_evals_at_import_time():
    # evals.run_evals constructs a real provider model at import time; the
    # driver must reach it only lazily (inside run_one_case, which is faked
    # in every test here). Re-executing the module body proves it freshly.
    # An ambient run_evals left by an unrelated earlier test is set aside so
    # this measures only what the driver's own import pulls in.
    saved = sys.modules.pop("evals.run_evals", None)
    try:
        importlib.reload(driver)
        assert "evals.run_evals" not in sys.modules
    finally:
        if saved is not None:
            sys.modules["evals.run_evals"] = saved
