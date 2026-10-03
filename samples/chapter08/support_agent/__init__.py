# samples/chapter08/support_agent/__init__.py
"""AgentCore Runtimeデプロイ用カスタマーサポートエージェント"""

from . import agent as agent
from .agent import root_agent

__all__ = ["agent", "root_agent"]
