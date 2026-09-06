"""Offline hermetic tests for the five-case Gemini-judge driver.

No model, no network, no google-genai required (the native-path preflight
is faked via sys.modules where a full-loop exercise is needed). The repo
.env is never relied upon: the credential gate is monkeypatched.
"""

import json
import sys
import types
from pathlib import Path

import evals.gemini_judge_5case as driver

EXPECTED_FIVE = [
    "reversal-not-propagated",
    "duplicate-transaction",
    "sync-lag-self-resolving",
    "manual-override-not-reflected",
    "data-entry-error",
]


def test_exactly_five_cases_configured_in_order():
    names = driver.list_case_names()
    assert names == EXPECTED_FIVE
    assert len(names) == driver.EXPECTED_CASE_COUNT


def test_case_dirs_distinct_and_ordered(tmp_path):
    dirs = [driver._case_dir(tmp_path, i, n) for i, n in enumerate(EXPECTED_FIVE, 1)]
    assert len(set(dirs)) == 5
    assert dirs[0].name == "case-01-reversal-not-propagated"
    assert dirs[-1].name == "case-05-data-entry-error"


def test_main_blocks_without_credential(tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "resolve_gemini_api_key", lambda: None)
    out = tmp_path / "evidence"
    assert driver.main(["--out-dir", str(out)]) == 3
    assert not out.exists()  # gate fires BEFORE any artifact is created


def test_main_blocks_if_case_count_is_not_five(tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "resolve_gemini_api_key", lambda: "dummy-key")
    monkeypatch.setattr(driver, "list_case_names", lambda: EXPECTED_FIVE[:4])
    out = tmp_path / "evidence"
    assert driver.main(["--out-dir", str(out)]) == 2
    assert not out.exists()  # case-set gate fires before the import preflight


def _fake_gemini_module(monkeypatch):
    # The native-path pre-flight does `import strands.models.gemini`; inject
    # a stub so the loop can be exercised without google-genai installed.
    stub = types.ModuleType("strands.models.gemini")
    monkeypatch.setitem(sys.modules, "strands.models.gemini", stub)


def test_main_runs_each_case_once_no_reruns(tmp_path, monkeypatch):
    _fake_gemini_module(monkeypatch)
    monkeypatch.setattr(driver, "resolve_gemini_api_key", lambda: "dummy-key")

    calls = []

    def fake_run_one_case(name, case_dir, judge_swap=None, log_prefix=""):
        calls.append((name, Path(case_dir), judge_swap))
        Path(case_dir).mkdir(parents=True, exist_ok=True)
        return 0

    swaps = []
    monkeypatch.setattr(
        driver,
        "swap_judge_models_gemini",
        lambda module, recorder, api_key=None: swaps.append((module, recorder, api_key)),
    )
    monkeypatch.setattr(driver, "run_one_case", fake_run_one_case)

    out = tmp_path / "evidence"
    rc = driver.main(["--out-dir", str(out)])

    assert rc == 0
    assert [c[0] for c in calls] == EXPECTED_FIVE  # each case exactly once, in order
    assert len({str(c[1]) for c in calls}) == 5  # distinct per-case evidence dirs
    for _name, _dir, swap in calls:
        assert callable(swap)  # the Gemini judge swap is wired into every case
        swap("fake_module", "fake_recorder")  # partial binds the api_key through
    assert swaps and all(s[2] == "dummy-key" for s in swaps)

    index = json.loads((out / "index.json").read_text())
    assert index["case_count"] == 5
    assert index["all_exit_zero"] is True
    assert index["judge_model"] == "gemini-3.1-flash-lite"
    assert index["agent_model"] == "openai/gpt-oss-120b"
    assert [r["case"] for r in index["cases"]] == EXPECTED_FIVE


def test_main_continues_after_case_failure(tmp_path, monkeypatch):
    _fake_gemini_module(monkeypatch)
    monkeypatch.setattr(driver, "resolve_gemini_api_key", lambda: "dummy-key")

    calls = []

    def fake_run_one_case(name, case_dir, judge_swap=None, log_prefix=""):
        calls.append(name)
        Path(case_dir).mkdir(parents=True, exist_ok=True)
        return 1 if name == "sync-lag-self-resolving" else 0  # case 3 "fails"

    monkeypatch.setattr(driver, "run_one_case", fake_run_one_case)
    out = tmp_path / "evidence"
    rc = driver.main(["--out-dir", str(out)])

    assert rc == 1  # failure propagates to the exit status ...
    assert calls == EXPECTED_FIVE  # ... but every case still ran exactly once
    index = json.loads((out / "index.json").read_text())
    assert index["all_exit_zero"] is False
    assert [r["exit_code"] for r in index["cases"]] == [0, 0, 1, 0, 0]


def test_driver_inherits_canary_configuration():
    # Single source of truth: the five-case run must reuse the exact
    # one-case-validated model id / provider, not restate them.
    import evals.gemini_judge_canary as gjc

    assert driver.GEMINI_MODEL_ID is gjc.GEMINI_MODEL_ID
    assert driver.GEMINI_PROVIDER is gjc.GEMINI_PROVIDER
    # the pacer continuity requirement: the swap used per case is literally
    # the validated canary swap (bound with partial in main)
    assert driver.swap_judge_models_gemini is gjc.swap_judge_models_gemini


def test_main_writes_retry_evidence_per_case_and_run_root(tmp_path, monkeypatch):
    """Observation-only capture: one classification mid-run (case 2) must be
    attributed to case 2 ONLY via snapshot-diff, land in that case's
    retry-evidence.json, and aggregate into the run-root file + index."""
    _fake_gemini_module(monkeypatch)
    monkeypatch.setattr(driver, "resolve_gemini_api_key", lambda: "dummy-key")

    registry = {"classification_count": 0, "events": []}

    def fake_get_retry_evidence():
        return {
            "strategy_class": "GroqParsingFailedRetryStrategy",
            "signature_prefix": "Parsing failed. The model generated output that could not be parsed.",
            "classification_count": registry["classification_count"],
            "events": list(registry["events"]),
            "note": "test double",
        }

    def fake_run_one_case(name, case_dir, judge_swap=None, log_prefix=""):
        Path(case_dir).mkdir(parents=True, exist_ok=True)
        if name == "duplicate-transaction":  # case 2: one classification mid-case
            registry["classification_count"] += 1
            registry["events"].append(
                {
                    "timestamp": "2026-09-05T00:00:00.000+00:00",
                    "exception_type": "APIError",
                    "message_head": "Parsing failed. The model generated ...",
                    "classified_retryable": True,
                }
            )
        return 0

    monkeypatch.setattr(driver, "get_retry_evidence", fake_get_retry_evidence)
    monkeypatch.setattr(driver, "run_one_case", fake_run_one_case)

    out = tmp_path / "evidence"
    rc = driver.main(["--out-dir", str(out)])

    assert rc == 0
    deltas, afters = [], []
    for i, name in enumerate(EXPECTED_FIVE, 1):
        payload = json.loads(
            (out / f"case-{i:02d}-{name}" / "retry-evidence.json").read_text()
        )
        assert payload["case"] == name
        assert payload["case_index"] == i
        assert payload["retry_strategy"] == "GroqParsingFailedRetryStrategy"
        deltas.append(payload["delta_classifications"])
        afters.append(payload["cumulative_classification_count_after"])
        assert len(payload["delta_events"]) == payload["delta_classifications"]
        assert (  # internal consistency: after == before + delta
            payload["cumulative_classification_count_after"]
            == payload["cumulative_classification_count_before"]
            + payload["delta_classifications"]
        )
        assert payload["ledger_derived"]["total_rows"] == 0  # no JSONL in fake dirs
    assert deltas == [0, 1, 0, 0, 0]  # attributed to case 2 alone
    assert afters == [0, 1, 1, 1, 1]  # cumulative registry as of each capture
    assert afters[-1] == registry["classification_count"]  # ends at the final count

    run_root = json.loads((out / "retry-evidence-run.json").read_text())
    assert run_root["retry_strategy"] == "GroqParsingFailedRetryStrategy"
    assert [p["delta_classifications"] for p in run_root["per_case"]] == [0, 1, 0, 0, 0]
    assert run_root["cumulative"]["classification_count"] == 1

    index = json.loads((out / "index.json").read_text())
    assert index["retry_strategy"] == "GroqParsingFailedRetryStrategy"
    assert index["retry_evidence"] == "retry-evidence-run.json"


def test_retry_evidence_capture_failure_never_raises(tmp_path, capsys, monkeypatch):
    """The capture is observation-only: even total failure is swallowed and
    printed — it can never alter the run's own exit path."""
    def _boom(*_args, **_kwargs):
        raise RuntimeError("capture exploded")

    monkeypatch.setattr(driver, "build_case_retry_evidence", _boom)
    result = driver._write_case_retry_evidence("case-x", 1, 0, tmp_path)
    assert result is None
    assert "RETRY-EVIDENCE CAPTURE FAILURE" in capsys.readouterr().out
