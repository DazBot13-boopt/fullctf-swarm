"""Mission Runner (Sprint 12 — intégration).

C'est la colonne vertébrale : il déroule une mission de bout en bout en reliant
tous les modules, et il APPLIQUE réellement l'autonomy_policy.

Cycle :
  workspace (Solver)
    -> exécution de l'agent
    -> preuve (Evidence Store)
    -> extraction du flag candidat
    -> vérification du format
    -> reproduction (si un reproducteur est fourni)
    -> point de contrôle humain (si human_checkpoints)
    -> soumission (si auto_submit_flag ET flag reproduit)

Garde-fous conservés :
- Un flag non reproduit n'est jamais soumis automatiquement.
- Les transitions d'état passent par la table de transitions.
- Les dépendances externes (soumission, approbation, reproduction) sont injectées
  => entièrement testable avec des mocks, sans réseau ni vrais agents.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from ..agents.registry import AgentRegistry
from ..challenges.solver import LocalSolver
from ..evidence.store import EvidenceStore
from ..models.challenge import Challenge
from ..models.evidence import ConfidenceLevel, Evidence
from ..models.flag import FlagCandidate, FlagStatus
from ..models.mission import Mission, MissionStatus, can_transition
from ..verifier.flag_verifier import FlagVerifier, extract_flags


class FlagSubmitter(Protocol):
    """Soumet un flag à la plateforme. Retourne True si accepté."""

    def submit(self, challenge: Challenge, flag_value: str) -> bool: ...


class ApprovalGate(Protocol):
    """Demande une validation humaine. Retourne True si approuvé."""

    def request(self, context: str) -> bool: ...


# Reproducteur : rejoue la résolution pour confirmer le flag (pas un faux positif).
Reproducer = Callable[[FlagCandidate, str], bool]


@dataclass
class MissionOutcome:
    """Résultat complet d'une mission."""

    mission_id: str
    status: MissionStatus
    flag: FlagCandidate | None = None
    evidences: list[Evidence] = field(default_factory=list)
    submitted: bool = False
    accepted: bool = False
    needs_human_approval: bool = False
    notes: str = ""


class MissionRunner:
    """Exécute une mission complète en reliant tous les modules."""

    def __init__(
        self,
        solver: LocalSolver,
        registry: AgentRegistry,
        evidence_store: EvidenceStore,
        verifier: FlagVerifier | None = None,
        *,
        reproducer: Reproducer | None = None,
        submitter: FlagSubmitter | None = None,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        self.solver = solver
        self.registry = registry
        self.evidence_store = evidence_store
        self.verifier = verifier or FlagVerifier()
        self.reproducer = reproducer
        self.submitter = submitter
        self.approval_gate = approval_gate

    def _set(self, mission: Mission, target: MissionStatus) -> None:
        if not can_transition(mission.status, target):
            raise ValueError(
                f"Transition interdite : {mission.status.value} -> {target.value}"
            )
        mission.status = target

    def _build_prompt(self, mission: Mission) -> str:
        parts = [mission.objective or "Résoudre le challenge."]
        if mission.playbook_id:
            parts.append(f"Playbook suggéré : {mission.playbook_id}.")
        if mission.allowed_tools:
            parts.append(f"Outils disponibles : {', '.join(mission.allowed_tools)}.")
        parts.append("Si tu trouves le flag, affiche-le au format NOM{...}.")
        return " ".join(parts)

    def run(self, challenge: Challenge, mission: Mission) -> MissionOutcome:
        outcome = MissionOutcome(mission_id=mission.id, status=mission.status)

        # 1. Préparer : workspace + passage à RUNNING.
        workspace = self.solver.create_workspace(challenge.id, mission.id)
        mission.workspace = str(workspace)
        self._set(mission, MissionStatus.VALIDATED)
        self._set(mission, MissionStatus.QUEUED)
        self._set(mission, MissionStatus.RUNNING)

        # 2. Exécuter l'agent.
        adapter = self.registry.get(mission.agent_provider)
        result = adapter.run_mission(
            self._build_prompt(mission), mission.workspace, mission.time_budget_seconds
        )

        # 3. Enregistrer la preuve brute.
        evidence = Evidence(
            challenge_id=challenge.id,
            mission_id=mission.id,
            source=f"{mission.agent_provider.value}/{mission.specialist_profile}",
            observation=result.output if result.success else (result.error or "échec"),
            confidence=ConfidenceLevel.MEDIUM if result.success else ConfidenceLevel.LOW,
        )
        self.evidence_store.add(evidence)
        outcome.evidences.append(evidence)

        if not result.success:
            self._set(mission, MissionStatus.FAILED)
            outcome.status = mission.status
            outcome.notes = "exécution de l'agent échouée"
            return outcome

        # 4. Extraire un flag candidat.
        candidates = extract_flags(result.output)
        if not candidates:
            self._set(mission, MissionStatus.COMPLETED)
            outcome.status = mission.status
            outcome.notes = "aucun flag trouvé"
            return outcome

        flag = FlagCandidate(
            challenge_id=challenge.id, value=candidates[0], source_mission=mission.id
        )

        # 5. Vérifier le format.
        flag = self.verifier.check_format(flag)
        outcome.flag = flag
        if flag.validation_status == FlagStatus.REJECTED:
            self._set(mission, MissionStatus.COMPLETED)
            outcome.status = mission.status
            outcome.notes = "flag au mauvais format"
            return outcome

        # 6. Reproduire (si possible). Sans reproducteur, on reste prudent.
        if self.reproducer is not None:
            flag = self.verifier.reproduce(
                flag, lambda: self.reproducer(flag, mission.workspace),
                reference=f"workspace:{mission.workspace}",
            )
            outcome.flag = flag
            if flag.validation_status == FlagStatus.REJECTED:
                self._set(mission, MissionStatus.COMPLETED)
                outcome.status = mission.status
                outcome.notes = "reproduction échouée (faux positif probable)"
                return outcome

        # 7. Décider de la soumission selon l'autonomy_policy.
        self._maybe_submit(challenge, mission, flag, outcome)
        return outcome

    def _maybe_submit(
        self, challenge: Challenge, mission: Mission, flag: FlagCandidate,
        outcome: MissionOutcome,
    ) -> None:
        policy = mission.autonomy_policy

        # Un flag doit être reproduit avant toute soumission automatique.
        reproduced = flag.validation_status == FlagStatus.REPRODUCED

        if not (policy.auto_submit_flag and reproduced and self.submitter is not None):
            # Pas de soumission auto : on propose le flag à l'humain.
            self._set(mission, MissionStatus.COMPLETED)
            outcome.status = mission.status
            outcome.notes = "flag proposé (soumission manuelle)"
            return

        # Point de contrôle humain avant une action sensible (la soumission).
        if policy.human_checkpoints:
            approved = (
                self.approval_gate.request(f"Soumettre {flag.value} ?")
                if self.approval_gate is not None
                else False
            )
            if not approved:
                self._set(mission, MissionStatus.WAITING_APPROVAL)
                outcome.status = mission.status
                outcome.needs_human_approval = True
                outcome.notes = "en attente d'approbation humaine avant soumission"
                return

        # Soumission.
        accepted = self.submitter.submit(challenge, flag.value)
        outcome.submitted = True
        outcome.accepted = accepted
        if accepted:
            outcome.flag = self.verifier.accept(flag, "accepté par la plateforme")
        else:
            outcome.flag = self.verifier.reject(flag, "rejeté par la plateforme")
        self._set(mission, MissionStatus.COMPLETED)
        outcome.status = mission.status
        outcome.notes = "soumis automatiquement"
