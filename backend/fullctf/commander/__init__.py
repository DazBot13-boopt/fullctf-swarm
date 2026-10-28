"""Commander FullCTF Swarm (noyau code à règles explicites)."""

from .allocation import (
    SwarmMode,
    initial_agent_count,
    initial_mode,
    next_mode,
)
from .classifier import infer_category
from .commander import Commander, MissionPlan
from .stagnation import StagnationDetector

__all__ = [
    "Commander",
    "MissionPlan",
    "StagnationDetector",
    "SwarmMode",
    "infer_category",
    "initial_agent_count",
    "initial_mode",
    "next_mode",
]
