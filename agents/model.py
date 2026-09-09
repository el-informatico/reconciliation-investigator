"""Application model wiring: Groq via the OpenAI-compatible endpoint.

POLICY (human ruling 2026-09-04): the Z.AI subscription key behind
ANTHROPIC_BASE_URL / ANTHROPIC_API_KEY is for Claude Code ONLY — this
application must never read or use it. The Anthropic provider path was
therefore REMOVED (the `anthropic` dependency is gone from pyproject
and the lock); if you came looking for it, that is why.

Credential: GROQ_API_KEY — Groq API keys are intended for application
API calls. Loaded from the environment, or from a gitignored `.env` at
the repo root (environment wins; the file is never committed and its
value is never printed anywhere, including logs).

Quota failover (human authorization 2026-09-09, extended same day): up
to two additional Groq keys may be provided as GROQ_API_KEY_2 and
GROQ_API_KEY_3. Resolution order is GROQ_API_KEY -> GROQ_API_KEY_2 ->
GROQ_API_KEY_3 (absent names drop out of the chain); on a 429 throttle
from the current key the model rotates to the next key in the chain and
retries, and only when every configured key throttles does the stock
agent-level throttle backoff take over. GROQ_FORCE_KEY=2|3 starts the
chain at that key and never falls back to an earlier one (forcing a
missing key raises). Tracked files carry the names and the policy only —
never a value.

Model: openai/gpt-oss-120b — a tool-calling-proven Groq configuration
previously validated in an earlier project (that project's internal
decision log is not part of this repo). Quota discipline carried over
from the same experience: keyless tests iterate; live runs are
BUDGETED (~80-100 calls per eval run against the free-tier daily cap)
and 429s are reported and rescheduled, never retried blindly.
"""

import os
from pathlib import Path
from typing import Any

from strands.models.openai import OpenAIModel
from strands.types.exceptions import ModelThrottledException

REPO_ROOT = Path(__file__).resolve().parent.parent

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL_ID = "openai/gpt-oss-120b"
DEFAULT_MAX_TOKENS = 8192

# Key number -> environment/.env variable name (names and policy only).
GROQ_KEY_ENV_NAMES = {
    1: "GROQ_API_KEY",
    2: "GROQ_API_KEY_2",
    3: "GROQ_API_KEY_3",
}


def _load_repo_dotenv() -> None:
    """Load REPO/.env into os.environ WITHOUT printing values. Existing
    environment variables always win. No dependency: a 15-line parser."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip("'\"")
        if name and name not in os.environ:
            os.environ[name] = value


def _resolve_groq_api_keys() -> list[str]:
    """Ordered chain of available Groq credentials (names only; values
    are never printed).

    Quota-failover policy (human authorization 2026-09-09, extended same
    day): the default order is GROQ_API_KEY -> GROQ_API_KEY_2 ->
    GROQ_API_KEY_3; absent names simply drop out of the chain, so the
    primary key's behavior is unchanged when it is alone.
    GROQ_FORCE_KEY=2|3 starts the chain at that key and continues
    forward only — forcing a missing key raises rather than silently
    falling back to an earlier one. Duplicate values collapse (rotating
    to the same quota pool is pointless).
    """
    force = os.environ.get("GROQ_FORCE_KEY")
    if force in ("2", "3"):
        start = int(force)
        forced = os.environ.get(GROQ_KEY_ENV_NAMES[start])
        if not forced:
            raise RuntimeError(
                f"GROQ_FORCE_KEY={force} is set but "
                f"{GROQ_KEY_ENV_NAMES[start]} is not (environment or "
                "gitignored .env) — refusing to silently fall back to "
                "an earlier key."
            )
        order = [start] + [n for n in (1, 2, 3) if n > start]
    else:
        order = [1, 2, 3]
    chain: list[str] = []
    for n in order:
        value = os.environ.get(GROQ_KEY_ENV_NAMES[n])
        if value and value not in chain:
            chain.append(value)
    if not chain:
        raise RuntimeError(
            "GROQ_API_KEY (and fallbacks GROQ_API_KEY_2 / GROQ_API_KEY_3) "
            "are not set (environment or gitignored .env). "
            "The Z.AI credential is NOT an option for this application: "
            "it is restricted to Claude Code by the subscription's "
            "permitted-use policy (human ruling, 2026-09-04)."
        )
    return chain


class KeyRotatingModel:
    """Pass-through delegating wrapper over one OpenAIModel per Groq
    key, in chain order (same delegation pattern as the observation
    wrapper in evals/token_canary.py).

    On a 429 throttle (ModelThrottledException) from the current key,
    advance to the next key and retry the same stream there — forward
    only; the wrapper stays on the new key for subsequent requests. When
    the LAST configured key also throttles, re-raise: the agent-level
    stock throttle backoff (agents/retry.py keeps its exact behavior)
    takes over, exactly as it would have without this wrapper. Any
    non-throttle error propagates untouched.
    """

    def __init__(self, models: list[Any]) -> None:
        self._models = list(models)
        self._index = 0
        self.rotations = 0  # observability: count, never which key

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes Python did not find on the wrapper;
        # exposes the active inner model's read-only facts (e.g. model_id).
        return getattr(self._models[self._index], name)

    def update_config(self, *args: Any, **kwargs: Any) -> Any:
        return self._models[self._index].update_config(*args, **kwargs)

    def get_config(self) -> Any:
        return self._models[self._index].get_config()

    async def structured_output(self, *args: Any, **kwargs: Any) -> Any:
        async for chunk in self._models[self._index].structured_output(*args, **kwargs):
            yield chunk

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        while True:
            index = self._index
            try:
                async for chunk in self._models[index].stream(*args, **kwargs):
                    yield chunk
                return
            except ModelThrottledException:
                if index + 1 >= len(self._models):
                    raise  # every configured key throttled
                self._index = index + 1
                self.rotations += 1


def get_model(max_tokens: int = DEFAULT_MAX_TOKENS) -> OpenAIModel | KeyRotatingModel:
    """The application's model: Groq (OpenAI-compatible) via GROQ_API_KEY.

    This is the ONLY sanctioned credential path for the app. The former
    Z.AI/Anthropic wiring was removed by policy; constructing it here is
    not possible anymore on purpose. Quota failover (429 rotation across
    GROQ_API_KEY -> GROQ_API_KEY_2 -> GROQ_API_KEY_3, GROQ_FORCE_KEY=2|3):
    see _resolve_groq_api_keys and KeyRotatingModel. A single configured
    key returns the bare OpenAIModel — zero behavior change for the
    default and offline/CI configuration.
    """
    _load_repo_dotenv()
    api_keys = _resolve_groq_api_keys()
    # NOTE: OpenAIModel takes max_tokens inside `params` — as a top-level
    # kwarg it is silently ignored with a UserWarning (verified live
    # 2026-09-04; the warning names the valid set: cache_config,
    # context_window_limit, model_id, params, stream).
    models = [
        OpenAIModel(
            client_args={"base_url": GROQ_BASE_URL, "api_key": api_key},
            model_id=MODEL_ID,
            params={"max_tokens": max_tokens},
        )
        for api_key in api_keys
    ]
    return models[0] if len(models) == 1 else KeyRotatingModel(models)
