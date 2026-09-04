"""Single-credential model wiring: GLM-5.3 via the existing Z.AI
Anthropic-compatible endpoint (ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY
from the environment). Live smoke-verified 2026-09-04 through strands'
AnthropicModel — see agent-memory/evidence/model-wiring-smoke-2026-09-04.txt.
No second credential or second model exists anywhere in this repo.
"""

import os

from strands.models.anthropic import AnthropicModel

# Bare model id: the glm-5.3[1m] alias is a client-side-only convention
# and is rejected by the raw API.
MODEL_ID = "glm-5.3"
DEFAULT_MAX_TOKENS = 4096


def get_model(max_tokens: int = DEFAULT_MAX_TOKENS) -> AnthropicModel:
    missing = [
        name
        for name in ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            f"missing required environment variables: {missing} "
            "(single GLM-5.3 credential via the existing Z.AI setup)"
        )
    return AnthropicModel(
        client_args={
            "base_url": os.environ["ANTHROPIC_BASE_URL"],
            "api_key": os.environ["ANTHROPIC_API_KEY"],
        },
        model_id=MODEL_ID,
        max_tokens=max_tokens,
    )
