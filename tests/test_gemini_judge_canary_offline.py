"""Offline hermetic tests for the Gemini judge canary driver.

No model, no network, no google-genai required (the driver imports it
lazily). The pacer is exercised with a shrunk interval via monkeypatch;
the credential gate is exercised with the environment controlled.
"""

import asyncio
import time

import evals.gemini_judge_canary as gjc
import evals.token_canary as tc


class FakeInnerModel:
    model_id = "gemini-fake"

    def get_config(self):
        return {"model_id": self.model_id}

    def update_config(self, **kwargs):
        pass

    async def structured_output(self, *args, **kwargs):
        yield {"structured": True}

    async def stream(self, *args, **kwargs):
        yield {"textDelta": {"text": "x"}}
        yield {"metadata": {"usage": {
            "inputTokens": 11, "outputTokens": 4, "totalTokens": 15,
        }, "metrics": {}}}


def _paced_wrapper(recorder, component="judge.trajectory"):
    return gjc.PacedUsageRecordingModel(
        FakeInnerModel(),
        component=component,
        component_type="judge",
        recorder=recorder,
        model_id=gjc.GEMINI_MODEL_ID,
        provider=gjc.GEMINI_PROVIDER,
    )


def _collect(async_gen):
    async def run():
        return [c async for c in async_gen]

    return asyncio.run(run())


def test_pacer_delays_sequential_requests(tmp_path, monkeypatch):
    monkeypatch.setattr(gjc, "MIN_INTERVAL_S", 0.12)
    monkeypatch.setattr(gjc, "_last_request_start", 0.0)
    recorder = tc.UsageRecorder(tmp_path / "usage.jsonl")
    w1 = _paced_wrapper(recorder, "judge.output")
    w2 = _paced_wrapper(recorder, "judge.trajectory")

    started = time.monotonic()
    out1 = _collect(w1.stream([], None, None))
    out2 = _collect(w2.stream([], None, None))
    elapsed = time.monotonic() - started

    assert out1[-1]["metadata"]["usage"]["totalTokens"] == 15
    assert out2[-1]["metadata"]["usage"]["totalTokens"] == 15
    # first request: slot was cold (>= 0 wait is fine); second must have
    # waited at least the interval minus scheduling slack
    assert elapsed >= 0.10, f"pacer did not delay the second request: {elapsed:.3f}s"
    recs = recorder.records
    assert [r["component"] for r in recs] == ["judge.output", "judge.trajectory"]
    assert all(r["status"] == "success" for r in recs)
    assert all(r["model"] == "gemini-3.1-flash-lite" and r["provider"] == "google" for r in recs)


def test_pace_wait_slot_reservation(monkeypatch):
    monkeypatch.setattr(gjc, "MIN_INTERVAL_S", 1.0)
    monkeypatch.setattr(gjc, "_last_request_start", 0.0)
    first = gjc._pace_wait()
    second = gjc._pace_wait()
    # cold start -> no wait; immediate second call -> nearly full interval
    assert first == 0.0
    assert 0.9 < second <= 1.0


def test_resolve_gemini_api_key_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert gjc.resolve_gemini_api_key(_loader=lambda: None) is None


def test_resolve_gemini_api_key_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-value-not-printed")
    key = gjc.resolve_gemini_api_key(_loader=lambda: None)
    assert key == "dummy-value-not-printed"  # value used, never printed by the driver


def test_main_blocks_without_credential(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # hermetic: do not touch the real repo .env loader in this test
    monkeypatch.setattr(gjc, "_load_repo_dotenv", lambda: None)
    rc = gjc.main(["--case", "reversal-not-propagated", "--out-dir", str(tmp_path / "out")])
    assert rc == 3
    out = capsys.readouterr().out
    assert "BLOCKED" in out and "GEMINI_API_KEY" in out
    # stopped BEFORE creating any evidence artifacts
    assert not (tmp_path / "out").exists()
    # and the block message must not echo any credential material
    assert "dummy" not in out


def test_driver_constants_match_probe_validated_configuration():
    assert gjc.GEMINI_MODEL_ID == "gemini-3.1-flash-lite"
    assert gjc.GEMINI_PROVIDER == "google"
    assert gjc.JUDGE_MAX_OUTPUT_TOKENS == 8192
