"""Suivi d'effort — adapté de ctf-agent cost_tracker (MIT) à notre modèle CLI.

ctf-agent calcule un coût USD précis via genai-prices + les tokens exacts du SDK
(RunUsage). Nous pilotons des CLI « boîte noire » : pas de genai-prices, pas de
pydantic_ai, et pas de compteur de tokens fiable. On suit donc l'EFFORT — durée et
nombre de tentatives par agent, + tokens SI le CLI les affiche (ex. codex « tokens
used N ») — ce qui est un proxy de coût suffisant pour mesurer et comparer les agents.

Crédit : concept repris de verialabs/ctf-agent (MIT), réécrit pour notre archi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Les CLI affichent parfois leur consommation ; on la récupère quand c'est le cas.
_TOKENS_RE = re.compile(r"tokens?\s*used[^\d]*([\d,]+)", re.I)


@dataclass
class AgentEffort:
    attempts: int = 0
    seconds: float = 0.0
    tokens: int = 0  # 0 = inconnu (le CLI ne l'a pas affiché)
    flags: int = 0   # nombre de flags trouvés par cet agent


@dataclass
class CostTracker:
    """Effort par agent (durée, tentatives, tokens si dispo, flags)."""

    by_agent: dict[str, AgentEffort] = field(default_factory=dict)

    def record(self, agent: str, seconds: float, output: str = "", *, found_flag: bool = False) -> None:
        e = self.by_agent.setdefault(agent, AgentEffort())
        e.attempts += 1
        e.seconds += seconds
        if found_flag:
            e.flags += 1
        m = _TOKENS_RE.search(output or "")
        if m:
            e.tokens += int(m.group(1).replace(",", ""))

    @property
    def total_seconds(self) -> float:
        return sum(e.seconds for e in self.by_agent.values())

    @property
    def total_attempts(self) -> int:
        return sum(e.attempts for e in self.by_agent.values())

    def format_summary(self) -> str:
        if not self.by_agent:
            return "  (aucun effort enregistré)"
        lines = []
        for a, e in sorted(self.by_agent.items()):
            tok = f", ~{e.tokens} tok" if e.tokens else ""
            lines.append(
                f"  {a:7} : {e.attempts} tentative(s), {e.seconds:.0f}s{tok}, {e.flags} flag(s)"
            )
        lines.append(f"  TOTAL   : {self.total_attempts} tentative(s), {self.total_seconds:.0f}s")
        return "\n".join(lines)
