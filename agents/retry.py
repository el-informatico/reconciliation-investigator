"""Narrow retry strategy for the Groq in-stream "Parsing failed" error.

Audited failure (docs/case-4-parsing-failure-audit-2026-09-04.md;
docs/gemini-groq-5-case-final-validation-2026-09-05.md §7): Groq's server
occasionally fails to parse one nondeterministic gpt-oss-120b emission and
terminates the HTTP-200 SSE stream with an error event whose message reads
"Parsing failed. The model generated output that could not be parsed.
Please adjust your prompt. See 'failed_generation' for more details." The
openai SDK raises that as a PLAIN ``openai.APIError`` (no ``status_code``
— constructed at ``openai/_streaming.py:206`` with the provider message
verbatim); strands classifies it as neither throttling nor context overflow
(``strands/models/_openai_errors.py``) and the stock ``ModelRetryStrategy``
retries only ``ModelThrottledException`` (``strands/event_loop/_retry.py``),
so the error was terminal and killed two benchmark cases (2026-09-04 case-4
and 2026-09-05 case-3, both at the detector node).

This module adds exactly ONE retryable signature to the stock policy via
the SDK's documented extension point ("Subclass and override
``is_retryable``", strands/event_loop/_retry.py:31-32). Everything else is
inherited unchanged: bounds stay max_attempts=6 total attempts,
initial_delay=4 s, max_delay=240 s, exponential, no jitter — identical to
the Agent stock default — and ``ModelThrottledException`` keeps its exact
stock behavior (the 2026-09-04 throttle recovered after ~4.008 s under
these same defaults).

Deliberately NOT retryable (verified by tests/test_groq_parsing_retry_offline.py):
every ``APIStatusError`` (auth 401 / permission 403 / rate-limit 429 /
4xx / 5xx — they carry ``status_code``), connection/timeout errors,
context-window overflow, ``MaxTokensReachedException``, the pre-fix Groq
in-stream "Tool call validation failed" tool-argument rejection, any
``openai.APIError`` whose message does not start with the verbatim prefix
below, and every non-openai exception (hence no Gemini error can match,
even with identical text).

A fresh instance must be constructed per Agent (the strategy keeps
per-invocation attempt state and graph nodes may run concurrently).
"""

import logging
import threading
from datetime import UTC, datetime
from typing import Any

import openai
from strands import ModelRetryStrategy

logger = logging.getLogger(__name__)

# Verbatim start of the audited provider message (both observed occurrences
# were byte-identical). Matching is deliberately prefix-exact, not substring:
# if Groq ever drifts the wording, matching degrades fail-safe (the error
# becomes terminal again, as before this change) — never to over-retrying.
GROQ_PARSING_FAILED_PREFIX = (
    "Parsing failed. The model generated output that could not be parsed."
)

_EVIDENCE_NOTE = "metadata-only ledger; provider error text carries no secrets"

_lock = threading.Lock()
_retry_classifications: list[dict[str, Any]] = []


def is_groq_parsing_failed_error(exception: BaseException) -> bool:
    """True only for the audited Groq in-stream parse rejection.

    Requires ALL of: ``openai.APIError``; NOT an ``APIStatusError``
    (in-stream errors carry no ``status_code``; 4xx/5xx/auth/quota errors
    do); message starts with the verbatim provider prefix.
    """
    return (
        isinstance(exception, openai.APIError)
        and not isinstance(exception, openai.APIStatusError)
        and str(exception).startswith(GROQ_PARSING_FAILED_PREFIX)
    )


def _record_classification(exception: openai.APIError) -> None:
    entry = {
        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "exception_type": type(exception).__name__,
        "message_head": str(exception)[:200],
        "classified_retryable": True,
    }
    with _lock:
        _retry_classifications.append(entry)
    logger.warning(
        "Groq in-stream 'Parsing failed' signature classified retryable "
        "(retry follows the stock bounded backoff): %s",
        entry["message_head"],
    )


def reset_retry_evidence() -> None:
    """Clear the classification ledger (test isolation)."""
    with _lock:
        _retry_classifications.clear()


def get_retry_evidence() -> dict[str, Any]:
    """Snapshot of narrow-match classifications for canary evidence."""
    with _lock:
        events = [dict(e) for e in _retry_classifications]
    return {
        "strategy_class": GroqParsingFailedRetryStrategy.__name__,
        "signature_prefix": GROQ_PARSING_FAILED_PREFIX,
        "classification_count": len(events),
        "events": events,
        "note": _EVIDENCE_NOTE,
    }


class GroqParsingFailedRetryStrategy(ModelRetryStrategy):
    """Stock throttle retry policy plus the single audited Groq signature.

    Construct with NO arguments in production: the inherited defaults then
    match the Agent stock strategy exactly (max_attempts=6 total attempts
    = 1 + 5 retries; initial_delay=4 s doubling to the 240 s cap; no
    jitter). Tests may shrink the delays via the inherited keyword-only
    constructor.
    """

    def is_retryable(self, exception: Exception) -> bool:
        if is_groq_parsing_failed_error(exception):
            _record_classification(exception)
            return True
        return super().is_retryable(exception)
