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

Model: openai/gpt-oss-120b — the same validated, tool-calling-proven
Groq configuration as [SIBLING-B] (see that repo's application
yml and decisions D007/D010/D012). Quota discipline imported from its
lesson L007: keyless tests iterate; live runs are BUDGETED (~80-100
calls per eval run against the free-tier daily cap) and 429s are
reported and rescheduled, never retried blindly.
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


def get_model(max_tokens: int = DEFAULT_MAX_TOKENS) -> OpenAIModel:
    """The application's model: Groq (OpenAI-compatible) via GROQ_API_KEY.

    This is the ONLY sanctioned credential path for the app. The former
    Z.AI/Anthropic wiring was removed by policy; constructing it here is
    not possible anymore on purpose.
    """
    _load_repo_dotenv()
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set (environment or gitignored .env). "
            "The Z.AI credential is NOT an option for this application: "
            "it is restricted to Claude Code by the subscription's "
            "permitted-use policy (human ruling, 2026-09-04)."
        )
    return OpenAIModel(
        client_args={"base_url": GROQ_BASE_URL, "api_key": api_key},
        model_id=MODEL_ID,
        max_tokens=max_tokens,
    )
