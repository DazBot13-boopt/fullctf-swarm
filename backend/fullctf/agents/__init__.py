"""Adaptateurs d'agents FullCTF Swarm."""

from .base import AgentAdapter, AgentAvailability, MissionResult
from .mock import MockAgentAdapter
from .providers import make_claude_adapter, make_codex_adapter, make_cursor_adapter
from .registry import AgentRegistry
from .subprocess_adapter import SubprocessAgentAdapter

__all__ = [
    "AgentAdapter",
    "AgentAvailability",
    "AgentRegistry",
    "MissionResult",
    "MockAgentAdapter",
    "SubprocessAgentAdapter",
    "make_claude_adapter",
    "make_codex_adapter",
    "make_cursor_adapter",
]
