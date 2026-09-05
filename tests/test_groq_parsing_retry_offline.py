"""Hermetic offline tests for agents.retry — the narrow Groq "Parsing failed"
retry strategy (2026-09-05 remediation experiment).

No network, no live provider, no evals.run_evals import. Real openai
exception objects are constructed against httpx2 (the HTTP library openai
3.8.0 actually imports) request/response objects — httpx2, NOT httpx.

Mandated coverage (task 2026-09-05, Phase 4):
1. exact-signature APIError classified retryable
2. matching error then success -> recovery after exactly one retry
   (through a REAL strands Agent — the hook must engage end-to-end)
3. unrelated APIError NOT retryable
4. context-window overflow NOT retryable
5. tool/schema validation errors NOT retryable (incl. the pre-fix Groq
   "Tool call validation failed" in-stream rejection as the control)
6. auth/authz-style API errors NOT retryable
7. always-raising matching error stops at the bounded retry limit and
   surfaces the raw failure
8. existing ModelThrottledException retry behavior intact
9. Gemini-class errors cannot be retried (type gate: non-openai exceptions
   never match, even with identical text)

Session-2 additions (2026-09-05 verification pass): 10. evidence reset
clears a POPULATED ledger; 11. the evidence mechanism is metadata-only
(request headers/body are never serialized; the message head is bounded
at 200 chars) — plus loop-level terminal control through the subclass and
mid-stream (partial output, then raise) recovery fidelity.
"""

import json
import logging

import httpx2
import openai
import pytest
from strands import Agent, ModelRetryStrategy
from strands.types.exceptions import (
    ContextWindowOverflowException,
    MaxTokensReachedException,
    ModelThrottledException,
)

from agents.retry import (
    GROQ_PARSING_FAILED_PREFIX,
    GroqParsingFailedRetryStrategy,
    get_retry_evidence,
    is_groq_parsing_failed_error,
    reset_retry_evidence,
)

# The audited provider message, verbatim (both observed occurrences were
# byte-identical; docs/case-4-parsing-failure-audit-2026-09-04.md).
AUDITED_MESSAGE = (
    "Parsing failed. The model generated output that could not be parsed. "
    "Please adjust your prompt. See 'failed_generation' for more details."
)


def groq_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def api_error(message: str) -> openai.APIError:
    """A PLAIN in-stream APIError — exactly what openai/_streaming.py:206
    raises for an SSE error event inside HTTP-200 (no status_code)."""
    return openai.APIError(message, groq_request(), body={"message": message})


def status_error(cls, status_code: int, message: str):
    """An APIStatusError subclass carrying a real status_code."""
    request = groq_request()
    response = httpx2.Response(status_code, request=request, headers={"x-request-id": "offline-test"})
    return cls(message, response=response, body={"message": message})


@pytest.fixture(autouse=True)
def _clean_evidence():
    reset_retry_evidence()
    yield
    reset_retry_evidence()


# --------------------------------------------------------------------------
# Unit: classification (mandated cases 1, 3, 4, 5, 6, 8-predicate, 9)
# --------------------------------------------------------------------------

def test_exact_audited_signature_is_retryable():
    strategy = GroqParsingFailedRetryStrategy()
    assert strategy.is_retryable(api_error(AUDITED_MESSAGE)) is True
    assert is_groq_parsing_failed_error(api_error(AUDITED_MESSAGE)) is True
    evidence = get_retry_evidence()
    assert evidence["classification_count"] == 1
    assert evidence["events"][0]["exception_type"] == "APIError"
    assert evidence["events"][0]["message_head"].startswith("Parsing failed.")
    assert evidence["signature_prefix"] == GROQ_PARSING_FAILED_PREFIX


def test_extended_provider_tail_still_matches_prefix_semantics():
    # The match is a verbatim PREFIX: Groq may extend the tail
    # ('failed_generation' details) without breaking the match.
    assert is_groq_parsing_failed_error(api_error(AUDITED_MESSAGE + " (ref xyz)")) is True


def test_unrelated_api_error_not_retryable():
    strategy = GroqParsingFailedRetryStrategy()
    assert strategy.is_retryable(api_error("Some unrelated provider failure")) is False
    assert get_retry_evidence()["classification_count"] == 0


def test_connection_error_not_retryable():
    assert is_groq_parsing_failed_error(openai.APIConnectionError(request=groq_request())) is False


def test_context_window_overflow_not_retryable():
    strategy = GroqParsingFailedRetryStrategy()
    assert strategy.is_retryable(
        ContextWindowOverflowException("maximum context length is 131072 tokens")
    ) is False
    assert strategy.is_retryable(MaxTokensReachedException("max_tokens reached")) is False
    # Raw provider text that strands classifies as context overflow must stay
    # terminal even though it arrives as a plain APIError.
    assert is_groq_parsing_failed_error(
        api_error("This model's maximum context length is 131072 tokens, however you requested...")
    ) is False


def test_tool_validation_failures_not_retryable():
    strategy = GroqParsingFailedRetryStrategy()
    # The pre-fix correction_draft_id killer: ALSO an in-stream, no-status
    # Groq rejection — it MUST stay terminal (architect binding condition).
    tool_validation = api_error(
        "Tool call validation failed: json.loads failed: expected string, but got null"
    )
    assert strategy.is_retryable(tool_validation) is False
    assert is_groq_parsing_failed_error(tool_validation) is False
    # Application/tool programming errors likewise.
    assert strategy.is_retryable(TypeError("tool argument validation failed")) is False


def test_auth_and_status_errors_not_retryable():
    strategy = GroqParsingFailedRetryStrategy()
    cases = [
        status_error(openai.AuthenticationError, 401, "Incorrect API key provided"),
        status_error(openai.PermissionDeniedError, 403, "Forbidden"),
        status_error(openai.RateLimitError, 429, "Rate limit reached"),
        status_error(openai.BadRequestError, 400, "Invalid request"),
        status_error(openai.InternalServerError, 500, "Internal server error"),
    ]
    for exc in cases:
        assert strategy.is_retryable(exc) is False, type(exc).__name__
    # Adversarial: a status error CARRYING the audited text must stay terminal.
    assert strategy.is_retryable(status_error(openai.BadRequestError, 400, AUDITED_MESSAGE)) is False


def test_throttle_retryable_and_stock_equivalence():
    strategy = GroqParsingFailedRetryStrategy()
    stock = ModelRetryStrategy()
    throttle = ModelThrottledException("OpenAI threw rate limit error")
    assert strategy.is_retryable(throttle) is True
    assert stock.is_retryable(throttle) is True
    # The subclass equals stock on EVERYTHING except the one narrow signature.
    others = [
        api_error("unrelated"),
        openai.APIConnectionError(request=groq_request()),
        ContextWindowOverflowException("x"),
        MaxTokensReachedException("x"),
        status_error(openai.AuthenticationError, 401, "x"),
        status_error(openai.RateLimitError, 429, "x"),
        ValueError(AUDITED_MESSAGE),
        RuntimeError("RESOURCE_EXHAUSTED"),
        TypeError("tool argument validation failed"),
    ]
    for exc in others:
        expected = stock.is_retryable(exc)
        assert expected is False, type(exc).__name__
        assert strategy.is_retryable(exc) is expected, type(exc).__name__


def test_non_openai_exceptions_never_match_even_with_identical_text():
    # Gemini judge errors are google-genai classes — categorically not
    # openai.APIError. (google-genai is an ephemeral overlay, absent in the
    # offline env; ANY non-openai exception is the same proof of the type
    # gate — the message alone can never trigger a retry.)
    for exc in (ValueError(AUDITED_MESSAGE), Exception(AUDITED_MESSAGE)):
        assert is_groq_parsing_failed_error(exc) is False


def test_prefix_perturbations_not_retryable():
    lowered = api_error(AUDITED_MESSAGE.lower())
    prefixed = api_error("Error: " + AUDITED_MESSAGE)
    truncated = api_error("Parsing failed.")
    reworded = api_error("Parsing failed. The model generated output could not be parsed.")
    for exc in (lowered, prefixed, truncated, reworded):
        assert is_groq_parsing_failed_error(exc) is False


def test_stock_bounds_unchanged():
    # Production wiring constructs the strategy with NO arguments; the
    # effective bounds must equal the Agent stock default exactly.
    custom = GroqParsingFailedRetryStrategy()
    stock = ModelRetryStrategy()
    assert (custom._max_attempts, custom._initial_delay, custom._max_delay) == (6, 4, 240)
    assert (custom._max_attempts, custom._initial_delay, custom._max_delay) == (
        stock._max_attempts,
        stock._initial_delay,
        stock._max_delay,
    )


# --------------------------------------------------------------------------
# Integration: the hook engages through a REAL strands Agent (fake model)
# --------------------------------------------------------------------------

class FakeGroqModel:
    """Minimal strands-Model-shaped fake (offline): raises the queued
    exceptions on the first stream() calls, then streams one well-formed
    minimal chunk set (a metadata chunk alone completes a cycle with the
    default end_turn stop reason — strands/event_loop/streaming.py:438)."""

    model_id = "openai/fake-groq"
    stateful = False

    def __init__(self, errors):
        self._errors = list(errors)
        self.calls = 0

    def get_config(self):
        return {"model_id": self.model_id}

    def update_config(self, **kwargs):
        pass

    async def structured_output(self, *args, **kwargs):
        yield {}

    async def stream(self, *args, **kwargs):
        self.calls += 1
        if self._errors:
            raise self._errors.pop(0)
        yield {
            "metadata": {
                "usage": {"inputTokens": 3, "outputTokens": 4, "totalTokens": 7},
                "metrics": {"latencyMs": 1, "timeToFirstByteMs": 1},
            }
        }


def fast_strategy(max_attempts=3):
    # Same policy, shrunk delays (tests must not sleep the stock 4 s backoff).
    return GroqParsingFailedRetryStrategy(max_attempts=max_attempts, initial_delay=0, max_delay=0)


def test_recovery_after_one_retry_through_real_agent():
    model = FakeGroqModel([api_error(AUDITED_MESSAGE)])
    agent = Agent(
        model=model,
        system_prompt="offline test",
        callback_handler=None,
        retry_strategy=fast_strategy(),
    )
    result = agent("hello")
    assert model.calls == 2  # 1 failed attempt + 1 retry
    assert result.stop_reason == "end_turn"
    assert get_retry_evidence()["classification_count"] == 1


def test_bounded_exhaustion_surfaces_raw_error():
    model = FakeGroqModel([api_error(AUDITED_MESSAGE) for _ in range(5)])
    agent = Agent(
        model=model,
        system_prompt="offline test",
        callback_handler=None,
        retry_strategy=fast_strategy(max_attempts=3),
    )
    with pytest.raises(openai.APIError, match="Parsing failed"):
        agent("hello")
    assert model.calls == 3  # bounded: initial + 2 retries, then terminal
    assert get_retry_evidence()["classification_count"] == 3


def test_throttle_recovery_through_subclass():
    model = FakeGroqModel([ModelThrottledException("OpenAI threw rate limit error")])
    agent = Agent(
        model=model,
        system_prompt="offline test",
        callback_handler=None,
        retry_strategy=fast_strategy(),
    )
    result = agent("hello")
    assert model.calls == 2  # stock throttle path retried and recovered
    assert result.stop_reason == "end_turn"
    assert get_retry_evidence()["classification_count"] == 0  # no narrow classification


def test_default_strategy_unchanged_for_matching_error():
    # The judge-side configuration (Agent WITHOUT retry_strategy — exactly
    # how strands_evals constructs judge agents) must keep stock behavior:
    # the audited error stays terminal on the first attempt.
    model = FakeGroqModel([api_error(AUDITED_MESSAGE)])
    agent = Agent(model=model, system_prompt="offline test", callback_handler=None)
    with pytest.raises(openai.APIError, match="Parsing failed"):
        agent("hello")
    assert model.calls == 1


def test_detector_builder_wires_strategy_and_it_engages():
    # The production wiring: build_detector_investigator(model=...) must
    # attach the strategy and the hook must engage end-to-end. This ONE
    # test sleeps the stock initial_delay=4 s once (builder wiring uses
    # production bounds) — accepted deliberately to prove the real config.
    from agents.detector_investigator import build_detector_investigator

    model = FakeGroqModel([api_error(AUDITED_MESSAGE)])
    agent = build_detector_investigator(model=model)
    assert isinstance(agent._retry_strategy, GroqParsingFailedRetryStrategy)
    result = agent("hello")
    assert model.calls == 2
    assert result.stop_reason == "end_turn"
    assert get_retry_evidence()["classification_count"] == 1


def test_all_three_builders_attach_the_strategy():
    from agents.classifier import build_classifier
    from agents.detector_investigator import build_detector_investigator
    from agents.reporter import build_reporter

    for builder in (build_detector_investigator, build_classifier, build_reporter):
        agent = builder(model=FakeGroqModel([]))
        assert isinstance(agent._retry_strategy, GroqParsingFailedRetryStrategy), builder.__name__
        # Fresh mutable state per Agent (never a shared instance).
        other = builder(model=FakeGroqModel([]))
        assert other._retry_strategy is not agent._retry_strategy


# --------------------------------------------------------------------------
# Session-2 additions (2026-09-05 verification pass): close the two
# mandated-coverage gaps (evidence reset lifecycle; metadata-only evidence
# under adversarial inputs) and two adversarial-review fidelity gaps
# (loop-level terminal control through the subclass; mid-stream failure
# with partial output before the raise).
# --------------------------------------------------------------------------


def test_reset_clears_a_populated_ledger():
    # Mandated item 9, closed by the session-2 audit: reset was previously
    # exercised only against assumed-empty ledgers (the autouse fixture).
    # Populate first, then prove the documented clear semantics.
    strategy = GroqParsingFailedRetryStrategy()
    assert strategy.is_retryable(api_error(AUDITED_MESSAGE)) is True
    assert strategy.is_retryable(api_error(AUDITED_MESSAGE)) is True
    populated = get_retry_evidence()
    assert populated["classification_count"] == 2
    assert [e["classified_retryable"] for e in populated["events"]] == [True, True]
    reset_retry_evidence()
    cleared = get_retry_evidence()
    assert cleared["classification_count"] == 0
    assert cleared["events"] == []
    # A later NON-matching classification must not resurrect old entries.
    assert strategy.is_retryable(api_error("unrelated provider failure")) is False
    assert get_retry_evidence()["classification_count"] == 0


def test_evidence_emits_no_request_secrets_and_bounds_message_head(caplog):
    # Mandated item 10, closed by the session-2 audit: the evidence ledger
    # must be metadata-only. The realistic secret carriers on an
    # openai.APIError are .request (headers, including a bearer token if one
    # were ever attached) and .body; the ledger must serialize NEITHER —
    # only the exception type name and the 200-char-bounded message head.
    # Material past 200 chars of provider text must never reach the
    # evidence or the WARNING log line.
    secret = "gsk_OFFLINE_TEST_TOKEN_0123456789abcdef"
    request = httpx2.Request(
        "POST",
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "x-api-key": secret},
    )
    overlong = AUDITED_MESSAGE + " tail:" + "x" * 400
    error = openai.APIError(overlong, request, body={"message": "body " + secret})
    with caplog.at_level(logging.WARNING, logger="agents.retry"):
        assert GroqParsingFailedRetryStrategy().is_retryable(error) is True
    evidence = get_retry_evidence()
    assert evidence["classification_count"] == 1
    (event,) = evidence["events"]
    assert set(event) == {"timestamp", "exception_type", "message_head", "classified_retryable"}
    assert len(event["message_head"]) == 200  # hard truncation bound holds
    assert event["message_head"].startswith(GROQ_PARSING_FAILED_PREFIX)
    blob = json.dumps(evidence)
    assert secret not in blob
    assert "Authorization" not in blob and "Bearer" not in blob and "x-api-key" not in blob
    for record in caplog.records:
        assert secret not in record.getMessage()
        assert "Authorization" not in record.getMessage()


def test_unrelated_error_terminal_through_subclass_at_loop_level():
    # Session-2 adversarial-review finding: terminal-class control was
    # proven at predicate level and at loop level for the judge config (no
    # strategy) — never at loop level THROUGH the subclass. With the
    # strategy attached, an unrelated APIError must stay terminal on the
    # FIRST model call (no retry, no ledger entry).
    model = FakeGroqModel([api_error("Some unrelated provider failure")])
    agent = Agent(
        model=model,
        system_prompt="offline test",
        callback_handler=None,
        retry_strategy=fast_strategy(),
    )
    with pytest.raises(openai.APIError, match="unrelated provider failure"):
        agent("hello")
    assert model.calls == 1
    assert get_retry_evidence()["classification_count"] == 0


class MidstreamFailureModel(FakeGroqModel):
    """Fidelity to the audited sequence: Groq terminates a live HTTP-200
    SSE stream mid-flight — partial content is emitted BEFORE the error
    event. Attempt 1 streams one content chunk then raises the audited
    APIError; attempt 2 completes normally."""

    async def stream(self, *args, **kwargs):
        self.calls += 1
        if self._errors:
            yield {"contentBlockDelta": {"delta": {"text": f"partial-attempt-{self.calls}"}}}
            raise self._errors.pop(0)
        yield {"contentBlockDelta": {"delta": {"text": "final answer"}}}
        yield {"contentBlockStop": {}}  # text lands in message content only on stop
        yield {
            "metadata": {
                "usage": {"inputTokens": 3, "outputTokens": 4, "totalTokens": 7},
                "metrics": {"latencyMs": 1, "timeToFirstByteMs": 1},
            }
        }


def test_midstream_failure_after_partial_output_recovers_cleanly():
    # Session-2 adversarial-review finding: the audited failure is IN-STREAM
    # (partial emission, then the SSE error event). Recovery must discard
    # the attempt-1 partial output entirely — the final result carries only
    # attempt-2 content.
    model = MidstreamFailureModel([api_error(AUDITED_MESSAGE)])
    agent = Agent(
        model=model,
        system_prompt="offline test",
        callback_handler=None,
        retry_strategy=fast_strategy(),
    )
    result = agent("hello")
    assert model.calls == 2
    assert result.stop_reason == "end_turn"
    text_blob = str(result) + str(getattr(result, "message", ""))
    assert "partial-attempt-1" not in text_blob
    assert "final answer" in text_blob
    assert get_retry_evidence()["classification_count"] == 1
