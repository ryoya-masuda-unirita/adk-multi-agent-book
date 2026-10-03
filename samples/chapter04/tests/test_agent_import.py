"""memory_agent.agentのimport時副作用を検証する。"""
from __future__ import annotations

import importlib

import pytest


def test_agent_import_does_not_create_runner(monkeypatch):
    """ADK CLIがappを読み込むだけならサービス環境変数を要求しない。"""
    monkeypatch.setenv("AGENT_ENV", "prod")
    monkeypatch.delenv("RDS_ENDPOINT", raising=False)

    module = importlib.import_module("memory_agent.agent")
    module = importlib.reload(module)

    assert module.app.name == "customer_support"
    with pytest.raises(ValueError, match="RDS_ENDPOINT"):
        module.create_runner()
