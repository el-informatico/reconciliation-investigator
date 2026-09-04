"""Credential-policy tests for agents/model.py: the app uses GROQ_API_KEY
(env or gitignored .env), never the Claude Code / Z.AI credential; the
Anthropic path is gone structurally."""

import pytest

import agents.model as model_module
from agents.model import get_model


def test_get_model_raises_clear_policy_error_without_groq_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
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
    assert model_module.GROQ_BASE_URL == "https://api.groq.com/openai/v1"
