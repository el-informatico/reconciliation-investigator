"""Credential-policy tests for agents/model.py: the app uses GROQ_API_KEY
(env or gitignored .env), never the Claude Code / Z.AI credential; the
Anthropic path is gone structurally. Quota failover (2026-09-09, extended
same day): the key chain is GROQ_API_KEY -> GROQ_API_KEY_2 ->
GROQ_API_KEY_3 (absent names drop out; GROQ_FORCE_KEY=2|3 starts at that
key, forward only); a 429 throttle rotates to the next key via
KeyRotatingModel, and a single configured key means a bare OpenAIModel
with unchanged behavior."""

import pytest

import agents.model as model_module
from agents.model import get_model


def test_get_model_raises_clear_policy_error_without_groq_key(tmp_path, monkeypatch):
    # delenv ALL key names: earlier tests in the suite import
    # evals.run_evals, which builds judge models at import time and
    # thereby loads the real repo .env into os.environ for the whole
    # pytest process — monkeypatch must scrub it back out here.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_3", raising=False)
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    monkeypatch.setattr(model_module, "REPO_ROOT", tmp_path)  # no .env there
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        get_model()


def test_anthropic_path_is_structurally_gone():
    # The policy ruling made structural: the anthropic SDK is not a
    # dependency, and the model module must not reference the Claude Code
    # credential names in any usable code path.
    import subprocess
    import sys

    probe = subprocess.run(
        [sys.executable, "-c", "import anthropic"],
        capture_output=True,
        cwd=model_module.REPO_ROOT,
    )
    assert probe.returncode != 0, "the anthropic SDK must not be importable in the app venv"


def test_dotenv_loader_env_wins_and_file_fills_missing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment line\n"
        "GROQ_API_KEY=file-key-should-not-be-printed\n"
        "OTHER_VAR=from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(model_module, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OTHER_VAR", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "env-key-wins")
    model_module._load_repo_dotenv()
    import os

    assert os.environ["GROQ_API_KEY"] == "env-key-wins"
    assert os.environ["OTHER_VAR"] == "from-file"


def test_get_model_constructs_groq_provider_with_key(tmp_path, monkeypatch):
    monkeypatch.setattr(model_module, "REPO_ROOT", tmp_path)  # no .env
    monkeypatch.setenv("GROQ_API_KEY", "dummy-key-no-network-call")
    # Scrub the fallback names too (same import-time .env pollution as
    # the no-key test) — this test asserts the SINGLE-key shape.
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_3", raising=False)
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    built = get_model()
    assert type(built).__name__ == "OpenAIModel"
    assert built.config.get("model_id") == model_module.MODEL_ID == "openai/gpt-oss-120b"
    # max_tokens must ride inside params (top-level kwarg is ignored with
    # a UserWarning — verified live 2026-09-04).
    assert built.config.get("params") == {"max_tokens": model_module.DEFAULT_MAX_TOKENS}
    assert model_module.GROQ_BASE_URL == "https://api.groq.com/openai/v1"


def test_resolver_chain_default_order_with_absent_names_dropped(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.setenv("GROQ_API_KEY_3", "k3")
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    assert model_module._resolve_groq_api_keys() == ["k1", "k3"]


def test_resolver_chain_dedupes_identical_values(monkeypatch):
    # Rotating to the same quota pool is pointless — duplicates collapse.
    monkeypatch.setenv("GROQ_API_KEY", "same-key")
    monkeypatch.setenv("GROQ_API_KEY_2", "same-key")
    monkeypatch.delenv("GROQ_API_KEY_3", raising=False)
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    assert model_module._resolve_groq_api_keys() == ["same-key"]


def test_resolver_force_2_starts_chain_at_secondary_forward_only(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")
    monkeypatch.setenv("GROQ_API_KEY_3", "k3")
    monkeypatch.setenv("GROQ_FORCE_KEY", "2")
    assert model_module._resolve_groq_api_keys() == ["k2", "k3"]


def test_resolver_force_3_is_a_terminal_chain(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")
    monkeypatch.setenv("GROQ_API_KEY_3", "k3")
    monkeypatch.setenv("GROQ_FORCE_KEY", "3")
    assert model_module._resolve_groq_api_keys() == ["k3"]


def test_resolver_force_missing_key_raises(monkeypatch):
    # A forced selection must fail loudly, never silently fall back to
    # an earlier (possibly quota-exhausted) key.
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.setenv("GROQ_FORCE_KEY", "2")
    with pytest.raises(RuntimeError, match="GROQ_API_KEY_2"):
        model_module._resolve_groq_api_keys()


def test_resolver_fallback_chain_when_primary_absent(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")
    monkeypatch.setenv("GROQ_API_KEY_3", "k3")
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    assert model_module._resolve_groq_api_keys() == ["k2", "k3"]


class _FakeModel:
    """Offline stream stand-in: yields chunks, or raises the configured
    error/throttle before yielding anything (throttles arrive at request
    time, which is exactly what rotation assumes)."""

    def __init__(self, *, chunks=(), throttle=False, error=None):
        from strands.types.exceptions import ModelThrottledException

        self._chunks = list(chunks)
        self._throttle_exc = ModelThrottledException("throttled") if throttle else None
        self._error = error
        self.calls = 0

    async def stream(self, *args, **kwargs):
        self.calls += 1
        if self._throttle_exc is not None:
            raise self._throttle_exc
        if self._error is not None:
            raise self._error
        for chunk in self._chunks:
            yield chunk


def _collect(wrapper):
    import asyncio

    async def run():
        return [chunk async for chunk in wrapper.stream()]

    return asyncio.run(run())


def test_rotating_model_rotates_on_throttle_and_stays_on_new_key():
    throttled = _FakeModel(throttle=True)
    healthy = _FakeModel(chunks=[{"from": "healthy"}])
    wrapper = model_module.KeyRotatingModel([throttled, healthy])
    assert _collect(wrapper) == [{"from": "healthy"}]
    assert wrapper.rotations == 1
    # Subsequent requests stay on the new key; the throttled key is not
    # retried (it stays off until the process restarts).
    assert _collect(wrapper) == [{"from": "healthy"}]
    assert throttled.calls == 1
    assert healthy.calls == 2


def test_rotating_model_reraises_when_every_key_throttles():
    from strands.types.exceptions import ModelThrottledException

    wrapper = model_module.KeyRotatingModel(
        [_FakeModel(throttle=True), _FakeModel(throttle=True)]
    )
    with pytest.raises(ModelThrottledException):
        _collect(wrapper)
    assert wrapper.rotations == 1  # rotated once, then the last key re-raised


def test_rotating_model_propagates_non_throttle_errors_immediately():
    healthy = _FakeModel(chunks=[{"from": "healthy"}])
    wrapper = model_module.KeyRotatingModel(
        [_FakeModel(error=ValueError("not a throttle")), healthy]
    )
    with pytest.raises(ValueError, match="not a throttle"):
        _collect(wrapper)
    assert wrapper.rotations == 0
    assert healthy.calls == 0  # rotation never engages on non-throttle errors


def test_get_model_returns_bare_model_with_a_single_key(tmp_path, monkeypatch):
    # Single-key configuration (default, offline, CI): bare OpenAIModel,
    # no wrapper — zero behavior change.
    monkeypatch.setattr(model_module, "REPO_ROOT", tmp_path)  # no .env
    monkeypatch.setenv("GROQ_API_KEY", "dummy-key-no-network-call")
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_3", raising=False)
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    built = get_model()
    assert type(built).__name__ == "OpenAIModel"
    assert built.config.get("model_id") == model_module.MODEL_ID


def test_get_model_wraps_chain_with_rotation_for_multiple_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(model_module, "REPO_ROOT", tmp_path)  # no .env
    monkeypatch.setenv("GROQ_API_KEY", "dummy-key-1")
    monkeypatch.setenv("GROQ_API_KEY_2", "dummy-key-2")
    monkeypatch.setenv("GROQ_API_KEY_3", "dummy-key-3")
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    built = get_model()
    assert type(built).__name__ == "KeyRotatingModel"
    assert built.rotations == 0
    # Delegation proof via the supported accessor (this SDK's OpenAIModel
    # exposes model_id through config, not as a public attribute).
    assert built.get_config().get("model_id") == model_module.MODEL_ID
    assert len(built._models) == 3
