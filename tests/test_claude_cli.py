import asyncio
import stat

import pytest

from src.ai import claude_cli
from src.ai.client import create_ai_client
from src.models import AIConfig


def _fake_cli(tmp_path, body):
    script = tmp_path / "claude"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def _client():
    return create_ai_client(AIConfig(provider="claude_cli", model="haiku", api_key_env=""))


def test_returns_stdout_and_passes_prompt_on_stdin(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_cli, "CLAUDE_BIN", _fake_cli(tmp_path, 'printf "got:%s" "$(cat)"\n'))
    assert asyncio.run(_client().complete("sys", "hello")) == "got:hello"


def test_nonzero_exit_raises_with_stderr(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_cli, "CLAUDE_BIN", _fake_cli(tmp_path, "echo boom >&2; exit 3\n"))
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(_client().complete("sys", "hello"))
