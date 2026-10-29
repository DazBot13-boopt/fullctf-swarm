"""Supervisor Chat / Mission Control (Sprint 9).

Architecture hybride :
- Noyau CODE : fournit les FAITS bruts fiables (état des missions, preuves, blocages).
  Jamais faux, instantané, gratuit.
- Couche LLM (optionnelle) : traduit ces faits en langage naturel. Si indisponible,
  on renvoie quand même les faits bruts.

Lecture seule : le superviseur LIT l'état, il ne décide rien. Toute action passe
par le Commander (ailleurs) avec confirmation.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..agents.base import AgentAdapter
from ..evidence.store import EvidenceStore
from ..models.mission import Mission, MissionStatus

# Statuts considérés comme "actifs" (une mission en cours de travail).
_ACTIVE = {MissionStatus.RUNNING, MissionStatus.WAITING_APPROVAL}


class MissionSnapshot(BaseModel):
    """Faits bruts sur une mission (noyau code)."""

    mission_id: str
    challenge_id: str
    provider: str
    profile: str
    status: str
    evidence_count: int
    verified_evidence_count: int
    blocked: bool


class SupervisorSnapshot(BaseModel):
    """Vue d'ensemble fiable de l'état du système."""

    total_missions: int
    active_missions: int
    completed_missions: int
    failed_missions: int
    missions: list[MissionSnapshot]


class SupervisorService:
    """Lit l'état réel et répond aux questions du superviseur humain."""

    def __init__(self, evidence_store: EvidenceStore) -> None:
        self.evidence_store = evidence_store

    # --- Noyau code : les faits -----------------------------------------

    def _mission_snapshot(self, mission: Mission, blocked_ids: set[str]) -> MissionSnapshot:
        ev = self.evidence_store.for_mission(mission.id)
        verified = [e for e in ev if e.verification_status.value == "verified"]
        return MissionSnapshot(
            mission_id=mission.id,
            challenge_id=mission.challenge_id,
            provider=mission.agent_provider.value,
            profile=mission.specialist_profile,
            status=mission.status.value,
            evidence_count=len(ev),
            verified_evidence_count=len(verified),
            blocked=mission.id in blocked_ids,
        )

    def snapshot(
        self, missions: list[Mission], blocked_ids: set[str] | None = None
    ) -> SupervisorSnapshot:
        """Construit la vue d'ensemble à partir des missions et des preuves."""
        blocked_ids = blocked_ids or set()
        snaps = [self._mission_snapshot(m, blocked_ids) for m in missions]
        return SupervisorSnapshot(
            total_missions=len(missions),
            active_missions=sum(1 for m in missions if m.status in _ACTIVE),
            completed_missions=sum(1 for m in missions if m.status == MissionStatus.COMPLETED),
            failed_missions=sum(1 for m in missions if m.status == MissionStatus.FAILED),
            missions=snaps,
        )

    def blocked(self, snapshot: SupervisorSnapshot) -> list[MissionSnapshot]:
        """Missions actuellement bloquées (remontées du Stagnation Detector)."""
        return [m for m in snapshot.missions if m.blocked]

    # --- Couche LLM : le résumé (lecture seule) -------------------------

    def _facts_text(self, snapshot: SupervisorSnapshot) -> str:
        lines = [
            f"Missions: {snapshot.total_missions} "
            f"(actives {snapshot.active_missions}, "
            f"terminées {snapshot.completed_missions}, "
            f"échouées {snapshot.failed_missions})."
        ]
        for m in snapshot.missions:
            flag = " [BLOQUÉE]" if m.blocked else ""
            lines.append(
                f"- {m.provider}/{m.profile} : {m.status}, "
                f"{m.evidence_count} preuves ({m.verified_evidence_count} vérifiées){flag}"
            )
        return "\n".join(lines)

    def summarize(
        self,
        snapshot: SupervisorSnapshot,
        question: str,
        adapter: AgentAdapter | None,
        *,
        workspace: str = "",
        timeout: int = 30,
    ) -> str:
        """Répond en langage naturel. Sans LLM dispo, renvoie les faits bruts.

        Le LLM ne reçoit QUE des faits déjà établis par le code : il résume,
        il n'invente pas.
        """
        facts = self._facts_text(snapshot)
        if adapter is None:
            return facts

        prompt = (
            "Tu es un assistant de supervision en LECTURE SEULE. "
            "Résume l'état ci-dessous pour répondre à la question, sans rien inventer "
            "et sans proposer d'action.\n\n"
            f"État réel :\n{facts}\n\nQuestion : {question}"
        )
        result = adapter.run_mission(prompt, workspace, timeout)
        if not result.success:
            # Repli sur les faits bruts si le LLM échoue.
            return facts
        return result.output
