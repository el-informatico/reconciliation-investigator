"""Token-usage canary: ONE evaluation case, instrumented, harness unmodified.

Purpose (2026-09-04 task contract): replace the ESTIMATED agent/judge token
split in docs/token-workload-audit-2026-09-04.md with MEASURED per-request
usage from the provider's own usage metadata, by running exactly ONE case
(`reversal-not-propagated`) through the existing sequential-eval path.

Why this file is safe (methodology unchanged):
- It MODIFIES NO EXISTING MODULE. No prompt, rubric, evaluator, case, tool,
  model id, provider, parameter, or scoring logic is touched.
- It wraps the model objects the harness itself constructs (the return
  value of agents.model.get_model()) in a pass-through delegating wrapper.
  The wrapper's stream() yields EXACTLY the inner chunks in the same order;
  it only additionally reads the usage dict the SDK attaches to the final
  metadata chunk (strands maps Groq prompt_tokens/completion_tokens/
  total_tokens to inputTokens/outputTokens/totalTokens — installed
  strands/models/openai.py, format_chunk "metadata" case). The same
  OpenAIModel config object is reused, so request bytes are identical.
- Wiring, done at driver runtime only:
  * the module-global `get_model` reference inside the three agents/*
    factory modules is re-bound to a tagged wrapper factory (the graph's
    default node_builder calls these factories with model=None);
  * the four LLM-judge singletons in evals.run_evals get `.model` swapped
    for tagged wrappers around the SAME shared judge_model instance
    (evaluators read self.model on every evaluate() call when building
    their internal scoring agents).
- Attribution is therefore exact by construction (agent.detector /
  agent.classifier / agent.reporter / judge.trajectory / judge.output /
  judge.tool_selection / judge.tool_parameter); SafeActionComplianceEvaluator
  is deterministic (a span walk, no model) and is reported with 0 tokens.

What is recorded — METADATA ONLY, per request:
  timestamp, case_id, component, component_type, model, provider,
  input_tokens, output_tokens, total_tokens, request_number,
  plus safe attribution cross-checks: had_usage, cache_read_tokens,
  system_prompt_sha256 (truncated digest — never the text),
  system_prompt_len, tool_spec_names (tool NAMES, not schemas),
  agent_class (class name of the calling agent object).

NEVER recorded: prompts, message contents, tool I/O, HTTP headers,
model config (it contains the API key), environment values, secrets.

Known measurement limit: the SDK drops the reasoning-token split and
Groq's timing fields before this interception point; completion tokens
(= output) still INCLUDE reasoning tokens. Totals are provider-reported,
never estimated from characters.

Cross-check: after the run, the already-running in-memory OTel exporter
is harvested for "chat" spans, keeping ONLY span name and gen_ai.*
attributes (span events carry prompt text and are never read).
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.model import GROQ_BASE_URL, MODEL_ID

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVIDER = "groq" if "api.groq.com" in GROQ_BASE_URL else GROQ_BASE_URL
DEFAULT_OUT_DIR = REPO_ROOT / "agent-memory" / "evidence" / "token-canary-2026-09-04"

RECORD_FIELDS = (
    "timestamp",
    "case_id",
    "component",
    "component_type",
    "model",
    "provider",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "request_number",
    "status",
    "error_type",
    "had_usage",
    "cache_read_tokens",
    "system_prompt_sha256",
    "system_prompt_len",
    "tool_spec_names",
    "agent_class",
)


class UsageRecorder:
    """Append-only JSONL sink for per-request usage metadata.

    Single-threaded by design (the sequential eval path is synchronous);
    each record is flushed on write so a crashed run still leaves the
    requests that completed.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []
        self._seq = 0
        self.case_id: str | None = None
        # Start from an empty file; refuse to mix with a previous run.
        self.path.write_text("", encoding="utf-8")

    def set_case(self, case_id: str) -> None:
        self.case_id = case_id

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def record(
        self,
        *,
        component: str,
        component_type: str,
        model: str,
        provider: str,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        request_number: int,
        status: str,
        had_usage: bool,
        error_type: str | None = None,
        cache_read_tokens: int | None = None,
        system_prompt_sha256: str | None = None,
        system_prompt_len: int | None = None,
        tool_spec_names: list[str] | None = None,
        agent_class: str | None = None,
    ) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "case_id": self.case_id,
            "component": component,
            "component_type": component_type,
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "request_number": request_number,
            "status": status,
            "error_type": error_type,
            "had_usage": had_usage,
            "cache_read_tokens": cache_read_tokens,
            "system_prompt_sha256": system_prompt_sha256,
            "system_prompt_len": system_prompt_len,
            "tool_spec_names": tool_spec_names,
            "agent_class": agent_class,
        }
        self.records.append(row)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


class UsageRecordingModel:
    """Pass-through delegating wrapper around a strands Model.

    Implements the Model interface (update_config / get_config /
    structured_output / stream) by pure delegation; any other attribute
    access (e.g. model_id) falls through to the inner object. stream()
    tees the final metadata chunk's usage dict into the recorder. The
    chunks yielded, their order, and every request byte are the inner
    model's own — nothing is added, removed, or altered.
    """

    def __init__(
        self,
        inner: Any,
        *,
        component: str,
        component_type: str,
        recorder: UsageRecorder,
        model_id: str = MODEL_ID,
        provider: str = PROVIDER,
    ) -> None:
        self._inner = inner
        self._component = component
        self._component_type = component_type
        self._recorder = recorder
        self._model_id = model_id
        self._provider = provider

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes Python did not find on the wrapper
        # (update_config/get_config/structured_output/stream/_inner etc.
        # are all found normally). Exposes inner read-only facts such as
        # model_id without copying config (config carries the API key).
        return getattr(self._inner, name)

    def update_config(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.update_config(*args, **kwargs)

    def get_config(self) -> Any:
        return self._inner.get_config()

    async def structured_output(self, *args: Any, **kwargs: Any) -> Any:
        # Unused on this eval path (judges force structured output through
        # stream()); delegated unchanged for interface completeness.
        async for chunk in self._inner.structured_output(*args, **kwargs):
            yield chunk

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        seq = self._recorder.next_seq()
        usage: dict[str, Any] | None = None

        # Attribution cross-check signals (metadata only). The harness
        # calls stream(messages, tool_specs, system_prompt, ...keyword
        # rest) — installed event_loop/streaming.py stream_messages.
        system_prompt = kwargs.get("system_prompt")
        if system_prompt is None and len(args) >= 3:
            system_prompt = args[2]
        sp_sha = None
        sp_len = None
        if isinstance(system_prompt, str):
            sp_sha = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:16]
            sp_len = len(system_prompt)
        tool_spec_names: list[str] = []
        tool_specs = kwargs.get("tool_specs")
        if tool_specs is None and len(args) >= 2:
            tool_specs = args[1]
        if isinstance(tool_specs, list):
            for spec in tool_specs:
                if isinstance(spec, dict):
                    name = spec.get("name") or spec.get("spec", {}).get("name")
                    tool_spec_names.append(str(name) if name else "?")
        invocation_state = kwargs.get("invocation_state")
        agent_obj = invocation_state.get("agent") if isinstance(invocation_state, dict) else None
        agent_class = type(agent_obj).__name__ if agent_obj is not None else None

        error_type: str | None = None
        try:
            async for chunk in self._inner.stream(*args, **kwargs):
                if isinstance(chunk, dict) and isinstance(chunk.get("metadata"), dict):
                    candidate = chunk["metadata"].get("usage")
                    if isinstance(candidate, dict):
                        usage = candidate  # last metadata chunk wins
                yield chunk
        except BaseException as exc:  # re-raised below; only the class name is recorded
            error_type = type(exc).__name__
            raise
        finally:
            # Runs on normal exhaustion, on consumer break (GeneratorExit),
            # and on inner exceptions — one record per stream() call. Status:
            # success = usage captured; error = exception propagated;
            # incomplete = no usage and no exception (stream not exhausted).
            self._recorder.record(
                component=self._component,
                component_type=self._component_type,
                model=self._model_id,
                provider=self._provider,
                input_tokens=usage.get("inputTokens") if usage else None,
                output_tokens=usage.get("outputTokens") if usage else None,
                total_tokens=usage.get("totalTokens") if usage else None,
                cache_read_tokens=usage.get("cacheReadInputTokens") if usage else None,
                request_number=seq,
                status=(
                    "success" if usage is not None
                    else ("error" if error_type and error_type != "GeneratorExit" else "incomplete")
                ),
                had_usage=usage is not None,
                error_type=error_type if error_type != "GeneratorExit" else None,
                system_prompt_sha256=sp_sha,
                system_prompt_len=sp_len,
                tool_spec_names=tool_spec_names or None,
                agent_class=agent_class,
            )


def install_agent_model_patches(recorder: UsageRecorder) -> None:
    """Re-bind the module-global get_model name inside the three agent
    factory modules so each factory's default model is a tagged wrapper
    around exactly what agents.model.get_model() would have returned.
    The real constructor is still called (same key loading, same config);
    nothing about the model changes except observation."""
    import agents.classifier
    import agents.detector_investigator
    import agents.reporter
    from agents import model as agents_model

    targets = [
        (agents.detector_investigator, "agent.detector"),
        (agents.classifier, "agent.classifier"),
        (agents.reporter, "agent.reporter"),
    ]
    for module, component in targets:
        def patched(max_tokens: int = agents_model.DEFAULT_MAX_TOKENS, *, _component=component):
            inner = agents_model.get_model(max_tokens)
            return UsageRecordingModel(
                inner, component=_component, component_type="agent", recorder=recorder
            )

        module.get_model = patched


def swap_judge_models(run_evals_module: Any, recorder: UsageRecorder) -> None:
    """Swap .model on the four LLM-judge singletons for tagged wrappers
    around the SAME shared judge_model instance they already hold."""
    targets = [
        ("trajectory_evaluator", "judge.trajectory"),
        ("output_evaluator", "judge.output"),
        ("tool_selection_evaluator", "judge.tool_selection"),
        ("tool_parameter_evaluator", "judge.tool_parameter"),
    ]
    for attr, component in targets:
        evaluator = getattr(run_evals_module, attr)
        evaluator.model = UsageRecordingModel(
            evaluator.model, component=component, component_type="judge", recorder=recorder
        )


def _otel_crosscheck(run_evals_module: Any) -> dict[str, Any]:
    """Independent totals from the in-memory OTel exporter: every finished
    'chat' span's gen_ai.* attributes (usage + request model). Span EVENTS
    (which carry prompt text) are never read or persisted."""
    spans = run_evals_module.telemetry.in_memory_exporter.get_finished_spans()
    rows = []
    for span in spans:
        attrs = {k: v for k, v in dict(span.attributes or {}).items() if k.startswith("gen_ai.")}
        rows.append({"span_name": str(span.name), "attributes": attrs})
    chat_rows = [r for r in rows if r["span_name"] == "chat"]

    def _sum(key_variants: tuple[str, ...]) -> int | None:
        # One alias per span: the exporter emits BOTH
        # gen_ai.usage.input_tokens and gen_ai.usage.prompt_tokens with
        # the same value — summing across variants double-counts (observed
        # live 2026-09-04: exactly 2x the wrapper's totals).
        values = []
        for r in chat_rows:
            for k in key_variants:
                v = r["attributes"].get(k)
                if isinstance(v, (int, float)):
                    values.append(v)
                    break
        return sum(values) if values else None

    return {
        "all_span_names": sorted({r["span_name"] for r in rows}),
        "span_count_total": len(rows),
        "chat_span_count": len(chat_rows),
        "chat_usage_sums": {
            "input_tokens": _sum(("gen_ai.usage.input_tokens", "gen_ai.usage.prompt_tokens")),
            "output_tokens": _sum(("gen_ai.usage.output_tokens", "gen_ai.usage.completion_tokens")),
            "total_tokens": _sum(("gen_ai.usage.total_tokens",)),
        },
        "chat_spans": chat_rows,
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate raw records into component/group tables. The raw JSONL is
    the source of truth; 'Detector loop' is derived here: detector requests
    whose sequence number falls after the first classifier request (the
    graph only re-nominates the detector after a low-confidence verdict)."""
    def bucket() -> dict[str, Any]:
        return {"requests": 0, "input": 0, "output": 0, "total": 0, "missing_usage": 0}

    first_classifier_seq = min(
        (r["request_number"] for r in records if r["component"] == "agent.classifier"),
        default=None,
    )

    components: dict[str, dict[str, Any]] = {}
    for r in records:
        comp = r["component"]
        if comp == "agent.detector" and first_classifier_seq is not None:
            if r["request_number"] > first_classifier_seq:
                comp = "agent.detector-loop"
        b = components.setdefault(comp, bucket())
        b["requests"] += 1
        b["input"] += r["input_tokens"] or 0
        b["output"] += r["output_tokens"] or 0
        b["total"] += r["total_tokens"] or 0
        if not r["had_usage"]:
            b["missing_usage"] += 1

    groups = {}
    for gname, gtype in (("agents", "agent"), ("judges", "judge")):
        g = bucket()
        for comp, b in components.items():
            if comp.startswith(gtype + "."):
                for k in g:
                    g[k] += b[k]
        groups[gname] = g

    grand = groups["agents"]["total"] + groups["judges"]["total"]
    groups["agents"]["share_pct"] = round(100 * groups["agents"]["total"] / grand, 2) if grand else None
    groups["judges"]["share_pct"] = round(100 * groups["judges"]["total"] / grand, 2) if grand else None

    sum_in = sum(r["input_tokens"] or 0 for r in records)
    sum_out = sum(r["output_tokens"] or 0 for r in records)
    sum_tot = sum(r["total_tokens"] or 0 for r in records)
    return {
        "requests": {
            "total": len(records),
            "with_usage": sum(1 for r in records if r["had_usage"]),
            "without_usage": sum(1 for r in records if not r["had_usage"]),
        },
        "totals": {"input": sum_in, "output": sum_out, "total_reported": sum_tot},
        "input_plus_output_equals_total": (sum_in + sum_out) == sum_tot,
        "components": components,
        "groups": groups,
        "deterministic_evaluator": {
            "SafeActionComplianceEvaluator": {
                "requests": 0,
                "llm_tokens": 0,
                "note": "deterministic span walk (evals/run_evals.py SafeActionComplianceEvaluator) — no model, 0 LLM tokens",
            }
        },
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print("\n[canary] === Token usage (provider-reported) ===", flush=True)
    header = f"{'component':28} {'reqs':>5} {'input':>9} {'output':>8} {'total':>9}"
    print(header, flush=True)
    for comp in sorted(summary["components"]):
        b = summary["components"][comp]
        note = f"  (missing usage: {b['missing_usage']})" if b["missing_usage"] else ""
        print(f"{comp:28} {b['requests']:>5} {b['input']:>9} {b['output']:>8} {b['total']:>9}{note}", flush=True)
    for g in ("agents", "judges"):
        b = summary["groups"][g]
        share = f"  share={b['share_pct']}%" if b["share_pct"] is not None else ""
        print(f"{g.upper():28} {b['requests']:>5} {b['input']:>9} {b['output']:>8} {b['total']:>9}{share}", flush=True)
    t = summary["totals"]
    print(
        f"\n[canary] totals: input={t['input']} output={t['output']} "
        f"total={t['total_reported']} requests={summary['requests']}",
        flush=True,
    )


def run_one_case(
    case_name: str,
    out_dir: Path,
    judge_swap=None,
    log_prefix: str = "[canary]",
) -> int:
    """Execute exactly ONE case through the unmodified sequential-eval path.

    judge_swap: optional fn(run_evals_module, recorder) that replaces the
    four LLM-judge singletons' .model — defaults to the Groq-wrapping
    swap_judge_models (the original token canary). The Gemini judge
    canary passes its own. Everything else (evaluators, order, rows,
    error handling) is identical either way.
    """
    out_dir = Path(out_dir)
    recorder = UsageRecorder(out_dir / "token-usage.jsonl")

    install_agent_model_patches(recorder)

    # Import AFTER patches: the judge model is constructed at import time
    # (unpatched — agents.model.get_model via its own reference); judge
    # attribution comes from the .model swap below, not the import.
    from evals import run_evals
    from evals.cases import test_cases
    from strands_evals.types.evaluation import EvaluationData

    if judge_swap is None:
        judge_swap = swap_judge_models
    judge_swap(run_evals, recorder)

    case = next((c for c in test_cases if c.name == case_name), None)
    if case is None:
        print(f"{log_prefix} unknown case: {case_name}", flush=True)
        return 2
    recorder.set_case(case.name)

    evaluators = [
        run_evals.trajectory_evaluator,
        run_evals.output_evaluator,
        run_evals.tool_selection_evaluator,
        run_evals.tool_parameter_evaluator,
        run_evals.safe_action_evaluator,
    ]

    started = time.monotonic()
    print(f"{log_prefix} case 1/1: {case.name}", flush=True)

    # --- identical to run_sequential.py's per-case body (single case) ---
    rows: list[dict] = []
    try:
        out = run_evals.run_case(case)
    except Exception as exc:
        import traceback

        print(f"{log_prefix}   TASK FAILED: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        for evaluator in evaluators:
            rows.append({
                "case": case.name,
                "evaluator": type(evaluator).__name__,
                "score": 0.0,
                "test_pass": False,
                "reason": f"task function failed: {type(exc).__name__}: {exc}",
                "label": "task-failure",
            })
    else:
        for evaluator in evaluators:
            data = EvaluationData[dict, str](
                input=case.input,
                name=case.name,
                expected_output=case.expected_output,
                expected_trajectory=case.expected_trajectory,
                metadata=case.metadata,
                actual_output=out.get("output"),
                actual_trajectory=out.get("trajectory"),
            )
            try:
                outputs = evaluator.evaluate(data)
            except Exception as exc:
                import traceback

                print(f"{log_prefix}   evaluator {type(evaluator).__name__} FAILED: {exc}", flush=True)
                traceback.print_exc()
                record = {
                    "score": 0.0,
                    "test_pass": False,
                    "reason": f"judge crashed: {type(exc).__name__}: {exc}",
                    "label": "judge-error",
                }
                record.update({"case": case.name, "evaluator": type(evaluator).__name__})
                rows.append(record)
                print(
                    f"{log_prefix}   {type(evaluator).__name__}: pass=False score=0.0 label=judge-error",
                    flush=True,
                )
                continue
            for row in outputs:
                record = row.model_dump()
                record.update({"case": case.name, "evaluator": type(evaluator).__name__})
                rows.append(record)
                print(
                    f"{log_prefix}   {type(evaluator).__name__}: pass={record.get('test_pass')} "
                    f"score={record.get('score')} label={record.get('label')}",
                    flush=True,
                )

    elapsed = time.monotonic() - started

    # --- artifacts ---------------------------------------------------------
    crosscheck = _otel_crosscheck(run_evals)
    (out_dir / "otel-crosscheck.json").write_text(json.dumps(crosscheck, indent=2), encoding="utf-8")

    passed = sum(1 for r in rows if r.get("test_pass"))
    summary_rows = {
        "case": case.name,
        "rows": len(rows),
        "passed": passed,
        "labels": sorted({str(r.get("label")) for r in rows}),  # labels may be None
        "per_evaluator": {},
        "wall_clock_seconds": round(elapsed, 1),
    }
    for row in rows:
        b = summary_rows["per_evaluator"].setdefault(row["evaluator"], {"rows": 0, "passed": 0})
        b["rows"] += 1
        b["passed"] += 1 if row.get("test_pass") else 0
    (out_dir / "eval-rows.json").write_text(
        json.dumps({"summary": summary_rows, "rows": rows}, indent=2), encoding="utf-8"
    )

    token_summary = summarize(recorder.records)
    token_summary["case_id"] = case.name
    token_summary["wall_clock_seconds"] = round(elapsed, 1)
    token_summary["otel_crosscheck_totals"] = crosscheck["chat_usage_sums"]
    token_summary["otel_chat_span_count"] = crosscheck["chat_span_count"]
    (out_dir / "token-summary.json").write_text(json.dumps(token_summary, indent=2), encoding="utf-8")

    _print_summary(token_summary)
    print(f"\n[canary] artifacts in: {out_dir}", flush=True)

    if not recorder.records:
        print(f"{log_prefix} MEASUREMENT FAILED: zero requests recorded", flush=True)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--case",
        default="reversal-not-propagated",
        help="case name from evals/cases.py (default: reversal-not-propagated)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="evidence directory (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    return run_one_case(args.case, args.out_dir)


if __name__ == "__main__":
    sys.exit(main())
