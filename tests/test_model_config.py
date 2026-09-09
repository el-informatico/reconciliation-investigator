"""Credential-policy tests for agents/model.py: the app uses GROQ_API_KEY
(env or gitignored .env), never the Claude Code / Z.AI credential; the
Anthropic path is gone structurally. Quota failover (2026-09-09):
GROQ_API_KEY_2 serves only as absence-fallback or GROQ_FORCE_KEY=2
override — the primary key's behavior is unchanged."""

import pytest

import agents.model as model_module
from agents.model import get_model


def test_get_model_raises_clear_policy_error_without_groq_key(tmp_path, monkeypatch):
    # delenv BOTH key names: earlier tests in the suite import
    # evals.run_evals, which builds judge models at import time and
    # thereby loads the real repo .env into os.environ for the whole
    # pytest process — monkeypatch must scrub it back out here.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
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
    built = get_model()
    assert type(built).__name__ == "OpenAIModel"
    assert built.config.get("model_id") == model_module.MODEL_ID == "openai/gpt-oss-120b"
    # max_tokens must ride inside params (top-level kwarg is ignored with
    # a UserWarning — verified live 2026-09-04).
    assert built.config.get("params") == {"max_tokens": model_module.DEFAULT_MAX_TOKENS}
    assert model_module.GROQ_BASE_URL == "https://api.groq.com/openai/v1"


def test_resolver_primary_wins_when_both_keys_present(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "primary-dummy")
    monkeypatch.setenv("GROQ_API_KEY_2", "secondary-dummy")
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    assert model_module._resolve_groq_api_key() == "primary-dummy"


def test_resolver_secondary_used_when_primary_absent(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY_2", "secondary-dummy")
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    assert model_module._resolve_groq_api_key() == "secondary-dummy"


def test_resolver_force_key_2_selects_secondary(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "primary-dummy")
    monkeypatch.setenv("GROQ_API_KEY_2", "secondary-dummy")
    monkeypatch.setenv("GROQ_FORCE_KEY", "2")
    assert model_module._resolve_groq_api_key() == "secondary-dummy"


def test_resolver_force_key_2_without_secondary_raises(monkeypatch):
    # A forced selection must fail loudly, never silently burn the
    # (possibly quota-exhausted) primary key instead.
    monkeypatch.setenv("GROQ_API_KEY", "primary-dummy")
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.setenv("GROQ_FORCE_KEY", "2")
    with pytest.raises(RuntimeError, match="GROQ_API_KEY_2"):
        model_module._resolve_groq_api_key()


def test_get_model_builds_with_secondary_when_primary_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(model_module, "REPO_ROOT", tmp_path)  # no .env
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY_2", "dummy-key-no-network-call")
    monkeypatch.delenv("GROQ_FORCE_KEY", raising=False)
    built = get_model()
    assert type(built).__name__ == "OpenAIModel"
    assert built.config.get("model_id") == model_module.MODEL_ID
