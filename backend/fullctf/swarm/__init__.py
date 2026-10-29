"""Swarm FullCTF : collaboration et débat entre agents."""

from .collaboration import AgentTask, CollaborationEngine
from .debate import DebateEngine, DebateOutcome, ReviewVerdict

__all__ = [
    "AgentTask",
    "CollaborationEngine",
    "DebateEngine",
    "DebateOutcome",
    "ReviewVerdict",
]
