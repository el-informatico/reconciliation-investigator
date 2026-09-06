"""Offline hermetic tests for the token-canary instrumentation.

No model, no network, no evals.run_evals import (that module constructs a
real provider model at import time). UsageRecordingModel is driven by a
fake inner model whose stream() yields canned chunks shaped like the real
SDK's stream events — a final metadata chunk carrying the Usage dict,
exactly as strands' OpenAIModel.format_chunk produces it.
"""

import asyncio
import hashlib
import json

import evals.token_canary as tc


class FakeInnerModel:
    """Minimal strands-Model-shaped fake (offline)."""

    model_id = "openai/fake-model"

    def __init__(self, chunks=None, error=None):
        self.chunks = chunks or []
        self.error = error
        self.update_calls = []

    def get_config(self):
        return {"model_id": self.model_id}

    def update_config(self, **kwargs):
        self.update_calls.append(kwargs)

    async def structured_output(self, *args, **kwargs):
        yield {"structured": True}

    async def stream(self, *args, **kwargs):
        for chunk in self.chunks:
            yield chunk
        if self.error is not None:
            raise self.error


def _collect(async_gen):
    async def run():
        return [c async for c in async_gen]

    return asyncio.run(run())


def _make(tmp_path, chunks=None, error=None):
    recorder = tc.UsageRecorder(tmp_path / "usage.jsonl")
    inner = FakeInnerModel(chunks=chunks, error=error)
    wrapper = tc.UsageRecordingModel(
        inner, component="agent.detector", component_type="agent", recorder=recorder
    )
    return recorder, inner, wrapper


def test_records_usage_and_passes_chunks_through(tmp_path):
    chunks = [
        {"textDelta": {"text": "hel"}},
        {"textDelta": {"text": "lo"}},
        {"metadata": {"usage": {
            "inputTokens": 474, "outputTokens": 71, "totalTokens": 545,
        }, "metrics": {"latencyMs": 0}}},
    ]
    recorder, _, wrapper = _make(tmp_path, chunks=chunks)
    out = _collect(wrapper.stream([], None, "system prompt text"))
    assert out == chunks, "wrapper must yield the inner chunks unchanged, in order"
    assert len(recorder.records) == 1
    rec = recorder.records[0]
    assert rec["component"] == "agent.detector"
    assert rec["component_type"] == "agent"
    assert rec["input_tokens"] == 474
    assert rec["output_tokens"] == 71
    assert rec["total_tokens"] == 545
    assert rec["had_usage"] is True
    assert rec["request_number"] == 1
    assert rec["status"] == "success"
    assert rec["error_type"] is None
    assert rec["case_id"] is None  # set_case not called


def test_records_without_usage_when_inner_raises(tmp_path):
    recorder, _, wrapper = _make(
        tmp_path,
        chunks=[{"textDelta": {"text": "partial"}}],
        error=RuntimeError("429 too many requests"),
    )
    try:
        _collect(wrapper.stream([], None, None))
    except RuntimeError:
        pass
    else:
        raise AssertionError("inner exception must propagate unchanged")
    assert len(recorder.records) == 1
    rec = recorder.records[0]
    assert rec["had_usage"] is False
    assert rec["status"] == "error"
    assert rec["error_type"] == "RuntimeError"
    assert rec["input_tokens"] is None
    assert rec["output_tokens"] is None
    assert rec["total_tokens"] is None


def test_jsonl_schema_is_metadata_only(tmp_path):
    chunks = [{"metadata": {"usage": {
        "inputTokens": 10, "outputTokens": 5, "totalTokens": 15,
        "cacheReadInputTokens": 2,
    }, "metrics": {}}}]
    recorder, _, wrapper = _make(tmp_path, chunks=chunks)
    _collect(wrapper.stream([], None, "prompt text must not be recorded"))
    raw = (tmp_path / "usage.jsonl").read_text(encoding="utf-8").strip()
    rec = json.loads(raw)
    assert tuple(sorted(rec)) == tuple(sorted(tc.RECORD_FIELDS))
    assert "prompt text must not be recorded" not in raw
    assert rec["cache_read_tokens"] == 2
    assert rec["system_prompt_sha256"] == hashlib.sha256(
        b"prompt text must not be recorded"
    ).hexdigest()[:16]
    assert rec["system_prompt_len"] == len("prompt text must not be recorded")


def test_signal_extraction_from_positional_args(tmp_path):
    chunks = [{"metadata": {"usage": {
        "inputTokens": 1, "outputTokens": 1, "totalTokens": 2,
    }, "metrics": {}}}]

    class SentinelAgent:
        pass

    sentinel = SentinelAgent()
    recorder, _, wrapper = _make(tmp_path, chunks=chunks)
    _collect(wrapper.stream(
        [],
        [{"name": "read_legacy_system"}, {"name": "search_transactions"}],
        "SYSTEM PROMPT",
        tool_choice=None,
        invocation_state={"agent": sentinel},
    ))
    rec = recorder.records[0]
    assert rec["tool_spec_names"] == ["read_legacy_system", "search_transactions"]
    assert rec["agent_class"] == "SentinelAgent"


def test_delegation_of_config_and_attributes(tmp_path):
    recorder, inner, wrapper = _make(tmp_path)
    assert wrapper.get_config() == {"model_id": "openai/fake-model"}
    assert wrapper.model_id == "openai/fake-model"  # via __getattr__
    wrapper.update_config(max_tokens=99)
    assert inner.update_calls == [{"max_tokens": 99}]
    assert _collect(wrapper.structured_output([])) == [{"structured": True}]


def test_status_incomplete_on_early_break(tmp_path):
    chunks = [
        {"textDelta": {"text": "first"}},
        {"metadata": {"usage": {
            "inputTokens": 5, "outputTokens": 2, "totalTokens": 7,
        }, "metrics": {}}},
    ]
    recorder, _, wrapper = _make(tmp_path, chunks=chunks)

    async def take_one_then_close():
        gen = wrapper.stream([], None, None)
        chunk = await gen.__anext__()
        await gen.aclose()
        return chunk

    first = asyncio.run(take_one_then_close())
    assert first == {"textDelta": {"text": "first"}}
    rec = recorder.records[0]
    assert rec["status"] == "incomplete"
    assert rec["error_type"] is None
    assert rec["had_usage"] is False


def test_model_and_provider_override(tmp_path):
    chunks = [{"metadata": {"usage": {
        "inputTokens": 1, "outputTokens": 1, "totalTokens": 2,
    }, "metrics": {}}}]
    recorder = tc.UsageRecorder(tmp_path / "usage.jsonl")
    wrapper = tc.UsageRecordingModel(
        FakeInnerModel(chunks=chunks),
        component="judge.trajectory",
        component_type="judge",
        recorder=recorder,
        model_id="gemini-3.1-flash-lite",
        provider="google",
    )
    _collect(wrapper.stream([], None, None))
    rec = recorder.records[0]
    assert rec["model"] == "gemini-3.1-flash-lite"
    assert rec["provider"] == "google"
    assert rec["component"] == "judge.trajectory"
    assert rec["component_type"] == "judge"


def test_summary_groups_and_detector_loop_rule(tmp_path):
    recorder = tc.UsageRecorder(tmp_path / "usage.jsonl")
    recorder.set_case("unit")
    plan = [
        ("agent.detector", 100, 20, 120, 1),
        ("agent.detector", 50, 10, 60, 2),
        ("agent.classifier", 200, 30, 230, 3),
        ("agent.detector", 70, 15, 85, 4),  # after classifier -> detector loop
        ("agent.reporter", 300, 60, 360, 5),
        ("judge.trajectory", 900, 40, 940, 6),
        ("judge.output", 150, 10, 160, 7),
        ("judge.tool_selection", 80, 20, 100, 8),
        ("judge.tool_parameter", 90, 25, 115, 9),
    ]
    for comp, i_, o_, t_, seq in plan:
        recorder.record(
            component=comp,
            component_type="agent" if comp.startswith("agent.") else "judge",
            model="openai/gpt-oss-120b",
            provider="groq",
            input_tokens=i_, output_tokens=o_, total_tokens=t_,
            request_number=seq, status="success", had_usage=True,
        )
    s = tc.summarize(recorder.records)
    comp = s["components"]
    assert comp["agent.detector"]["requests"] == 2
    assert comp["agent.detector"]["total"] == 180
    assert comp["agent.detector-loop"]["requests"] == 1
    assert comp["agent.detector-loop"]["total"] == 85
    agents_total = sum(comp[c]["total"] for c in comp if c.startswith("agent."))
    judges_total = sum(comp[c]["total"] for c in comp if c.startswith("judge."))
    assert s["groups"]["agents"]["total"] == agents_total
    assert s["groups"]["judges"]["total"] == judges_total
    assert s["groups"]["judges"]["share_pct"] == round(100 * judges_total / (agents_total + judges_total), 2)
    assert s["input_plus_output_equals_total"] is True
    assert s["requests"]["total"] == 9
