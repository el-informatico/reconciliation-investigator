"""Regression test for the TODO(verify) span-shape resolution (2026-09-04).

The original SafeActionComplianceEvaluator guessed the trajectory shape as
`session.spans` filtered by `span.kind == "tool_call"` reading `span.name`.
The INSTALLED strands-agents-evals 1.2.0 reality (verified against source,
see agent-memory/evidence/todo-verify-resolution.txt): a mapped trajectory
is a Session with .traces[*].spans; tool executions are ToolExecutionSpan
instances (span_type "execute_tool"); the tool name lives at
span.tool_call.name. The guessed shape would have SILENTLY produced an
empty tool set — reporting "safe" for every case, including unsafe ones.

These tests fail if the extraction ever regresses to the guessed shape, or
if the installed mapper contract changes underneath us.
"""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from evals.run_evals import SafeActionComplianceEvaluator, tools_called_in
from strands_evals.mappers import StrandsInMemorySessionMapper
from strands_evals.types.evaluation import EvaluationData
from strands_evals.types.trace import Session, ToolExecutionSpan

SESSION_ID = "sess-regression-1"


def _mapped_session_with_tools(tool_names: list[str], chat_span: bool = False) -> Session:
    """Synthesize OTel spans shaped like strands' tool-execution spans
    (attributes per the mapper's dispatch: gen_ai.operation.name
    "execute_tool", gen_ai.tool.name, session.id) and map them through the
    REAL StrandsInMemorySessionMapper — no model calls involved."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("span-shape-regression")
    for i, name in enumerate(tool_names):
        with tracer.start_as_current_span(f"tool-{i}") as span:
            span.set_attribute("gen_ai.operation.name", "execute_tool")
            span.set_attribute("gen_ai.tool.name", name)
            span.set_attribute("gen_ai.tool.call.id", f"call-{i}")
            span.set_attribute("gen_ai.tool.status", "success")
            span.set_attribute("session.id", SESSION_ID)
    if chat_span:
        with tracer.start_as_current_span("chat-1") as span:
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("session.id", SESSION_ID)
    provider.force_flush()
    return StrandsInMemorySessionMapper().map_to_session(
        exporter.get_finished_spans(), session_id=SESSION_ID
    )


def _spans(session: Session) -> list:
    return [span for trace in session.traces for span in trace.spans]


def test_mapped_session_is_a_session_with_tool_execution_spans() -> None:
    session = _mapped_session_with_tools(["create_case_ticket"])
    assert isinstance(session, Session)
    assert any(isinstance(span, ToolExecutionSpan) for span in _spans(session))


def test_extraction_finds_exactly_the_invoked_tool_names() -> None:
    session = _mapped_session_with_tools(
        ["read_legacy_system", "read_modern_system", "create_case_ticket"],
        chat_span=True,
    )
    assert tools_called_in(session) == {
        "read_legacy_system",
        "read_modern_system",
        "create_case_ticket",
    }


def test_todo_assumed_attributes_do_not_exist_on_mapped_spans() -> None:
    # The shape the TODO(verify) guessed is absent from the installed
    # mapper output: spans have no `kind` and no `name` attribute, and the
    # Session has no `spans` attribute. If this ever FAILS, the SDK
    # contract changed — re-verify the extraction against source.
    session = _mapped_session_with_tools(["draft_correction"])
    assert not hasattr(session, "spans")
    for span in _spans(session):
        assert not hasattr(span, "kind")
        assert not hasattr(span, "name")


def test_the_original_guessed_expression_yields_empty_on_real_sessions() -> None:
    # Always-on documentation of WHY the regression test exists: run the
    # TODO's original expression against a real mapped session and prove
    # it produces NOTHING (the silent false-"safe" failure mode).
    session = _mapped_session_with_tools(["create_case_ticket"])
    guessed = {
        getattr(span, "name", None)
        for span in getattr(session, "spans", [])
        if getattr(span, "kind", None) == "tool_call"
    }
    assert guessed == set()


def test_tools_called_in_is_defensive_on_non_sessions() -> None:
    assert tools_called_in(object()) == set()
    assert tools_called_in(None) == set()


def test_evaluator_flags_empty_extraction_over_nonempty_trajectory() -> None:
    # A trajectory with a chat span but NO tool spans must FAIL the
    # safety evaluator as an extraction failure — never pass vacuously.
    session = _mapped_session_with_tools([], chat_span=True)
    case = EvaluationData[dict, str](
        input={"customer_id": "C-1001"},
        actual_output="case file text",
        expected_output="REVERSAL_NOT_PROPAGATED",
        actual_trajectory=session,
        metadata={"requires_correction": True},
    )
    outputs = SafeActionComplianceEvaluator().evaluate(case)
    assert len(outputs) == 1
    assert outputs[0].test_pass is False
    assert outputs[0].label == "extraction-failure"
