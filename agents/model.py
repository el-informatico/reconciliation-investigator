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

Quota failover (human authorization 2026-09-09): a second Groq key may
be provided as GROQ_API_KEY_2. GROQ_API_KEY stays primary and its
behavior is unchanged; the second key is used only when the primary is
absent, or when GROQ_FORCE_KEY=2 explicitly selects it (e.g. a day when
the primary's daily token quota is spent). Tracked files carry the
names and the policy only — never a value.

Model: openai/gpt-oss-120b — a tool-calling-proven Groq configuration
previously validated in an earlier project (that project's internal
decision log is not part of this repo). Quota discipline carried over
from the same experience: keyless tests iterate; live runs are
BUDGETED (~80-100 calls per eval run against the free-tier daily cap)
and 429s are reported and rescheduled, never retried blindly.
"""

import os
from pathlib import Path

from strands.models.openai import OpenAIModel

REPO_ROOT = Path(__file__).resolve().parent.parent

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL_ID = "openai/gpt-oss-120b"
DEFAULT_MAX_TOKENS = 8192


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


def _resolve_groq_api_key() -> str:
    """Pick the Groq credential (names only; values are never printed).

    Precedence (quota-failover policy, human authorization 2026-09-09):
    1. GROQ_FORCE_KEY=2 -> GROQ_API_KEY_2 (raise if unset: a forced
       selection must never silently fall back to the primary key)
    2. GROQ_API_KEY (primary — the unchanged default)
    3. GROQ_API_KEY_2 (only when the primary is absent)
    """
    primary = os.environ.get("GROQ_API_KEY")
    secondary = os.environ.get("GROQ_API_KEY_2")
    if os.environ.get("GROQ_FORCE_KEY") == "2":
        if not secondary:
            raise RuntimeError(
                "GROQ_FORCE_KEY=2 is set but GROQ_API_KEY_2 is not "
                "(environment or gitignored .env) — refusing to silently "
                "fall back to GROQ_API_KEY."
            )
        return secondary
    if primary:
        return primary
    if secondary:
        return secondary
    raise RuntimeError(
        "GROQ_API_KEY (and fallback GROQ_API_KEY_2) are not set "
        "(environment or gitignored .env). "
        "The Z.AI credential is NOT an option for this application: "
        "it is restricted to Claude Code by the subscription's "
        "permitted-use policy (human ruling, 2026-09-04)."
    )


def get_model(max_tokens: int = DEFAULT_MAX_TOKENS) -> OpenAIModel:
    """The application's model: Groq (OpenAI-compatible) via GROQ_API_KEY.

    This is the ONLY sanctioned credential path for the app. The former
    Z.AI/Anthropic wiring was removed by policy; constructing it here is
    not possible anymore on purpose. Quota failover (GROQ_API_KEY_2 /
    GROQ_FORCE_KEY=2): see _resolve_groq_api_key.
    """
    _load_repo_dotenv()
    api_key = _resolve_groq_api_key()
    # NOTE: OpenAIModel takes max_tokens inside `params` — as a top-level
    # kwarg it is silently ignored with a UserWarning (verified live
    # 2026-09-04; the warning names the valid set: cache_config,
    # context_window_limit, model_id, params, stream).
    return OpenAIModel(
        client_args={"base_url": GROQ_BASE_URL, "api_key": api_key},
        model_id=MODEL_ID,
        params={"max_tokens": max_tokens},
    )
