"""Mission Control : pont temps réel entre un run et le superviseur humain.

Le run (work-stealing) **publie** son état en continu et **lit** les ordres ;
un CLI superviseur lit l'état (« où en est Codex ? ») et écrit des ordres
(pause / reprise / stop / forcer le débat) = le relais d'ordres de la spec.

Échange par fichiers JSON (atomiques) pour fonctionner même quand le run tourne
dans un autre process (tmux). Le run reste maître : il LIT les ordres et décide
quand les appliquer (entre deux étapes), jamais une action sensible en plein vol.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path


class MissionControl:
    """État publié + ordres lus, partagés via deux fichiers JSON."""

    def __init__(self, data_root: str | Path) -> None:
        self.dir = Path(data_root)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.status_path = self.dir / "mission_status.json"
        self.control_path = self.dir / "mission_control.json"
        self._lock = threading.Lock()

    # --- côté RUN : publier l'état, lire les ordres ---
    def publish(self, status: dict) -> None:
        with self._lock:
            tmp = self.status_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.status_path)  # écriture atomique

    def _control(self) -> dict:
        try:
            return json.loads(self.control_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def paused(self) -> bool:
        return bool(self._control().get("paused"))

    def stopped(self) -> bool:
        return bool(self._control().get("stopped"))

    def force_debate_ids(self) -> set[int]:
        return {int(i) for i in self._control().get("force_debate", [])}

    def clear_force_debate(self, challenge_id: int) -> None:
        with self._lock:
            c = self._control()
            ids = [int(i) for i in c.get("force_debate", []) if int(i) != challenge_id]
            c["force_debate"] = ids
            self.control_path.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")

    # --- côté SUPERVISEUR : lire l'état, envoyer des ordres ---
    def read_status(self) -> dict:
        try:
            return json.loads(self.status_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def set_order(self, **kwargs) -> dict:
        """Écrit/merge un ordre (paused, stopped, force_debate=[...])."""
        with self._lock:
            c = self._control()
            c.update(kwargs)
            self.control_path.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
            return c

    def add_force_debate(self, challenge_id: int) -> None:
        with self._lock:
            c = self._control()
            ids = {int(i) for i in c.get("force_debate", [])}
            ids.add(int(challenge_id))
            c["force_debate"] = sorted(ids)
            self.control_path.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
