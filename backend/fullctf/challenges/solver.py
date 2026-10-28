"""Local Solver (Sprint 2) : import de challenges locaux.

Responsabilités :
- Importer un fichier de challenge (ZIP, ELF, Python, PCAP, image, dump, texte...).
- Conserver l'original IMMUABLE (lecture seule).
- Créer un workspace isolé où les agents pourront travailler sur une COPIE.
- Calculer l'empreinte (checksum) pour la traçabilité.

Aucune exécution du fichier importé : on ne fait que le ranger et le décrire.
"""

from __future__ import annotations

import hashlib
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImportedArtifact:
    """Un fichier de challenge importé et rangé."""

    original_path: Path  # Copie immuable de l'original
    checksum: str  # SHA-256
    size_bytes: int
    detected_type: str  # Type grossier détecté (voir detect_type)


def sha256_of(path: Path) -> str:
    """Calcule le SHA-256 d'un fichier."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_type(path: Path) -> str:
    """Détecte un type grossier à partir des octets de tête (magic bytes).

    Détection volontairement simple et sûre : on lit juste l'en-tête,
    on n'exécute jamais le fichier.
    """
    try:
        with path.open("rb") as f:
            head = f.read(16)
    except OSError:
        return "unknown"

    if head.startswith(b"\x7fELF"):
        return "elf"
    if head.startswith(b"PK\x03\x04"):
        return "zip"
    if head.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8")):
        return "image"
    if head.startswith((b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x0a\x0d\x0d\x0a")):
        return "pcap"
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".txt", ".md"}:
        return "text"
    return "unknown"


class LocalSolver:
    """Gère l'import des challenges et la création des workspaces.

    Arborescence :
      data_root/
        challenges/<challenge_id>/original/   <- originaux immuables
        challenges/<challenge_id>/workspaces/<mission_id>/  <- copies de travail
    """

    def __init__(self, data_root: str | Path):
        self.data_root = Path(data_root)
        self.challenges_dir = self.data_root / "challenges"
        self.challenges_dir.mkdir(parents=True, exist_ok=True)

    def _original_dir(self, challenge_id: str) -> Path:
        return self.challenges_dir / challenge_id / "original"

    def import_file(self, challenge_id: str, source_file: str | Path) -> ImportedArtifact:
        """Importe un fichier en conservant l'original immuable.

        Le fichier source n'est jamais modifié ni exécuté : il est copié,
        puis la copie est passée en lecture seule.
        """
        source = Path(source_file)
        if not source.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {source}")

        dest_dir = self._original_dir(challenge_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name

        shutil.copy2(source, dest)
        # Passage en lecture seule (immuable pour les agents).
        dest.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        return ImportedArtifact(
            original_path=dest,
            checksum=sha256_of(dest),
            size_bytes=dest.stat().st_size,
            detected_type=detect_type(dest),
        )

    def create_workspace(self, challenge_id: str, mission_id: str) -> Path:
        """Crée un workspace isolé pour une mission, avec une COPIE des originaux.

        Les agents travaillent ici, jamais sur les originaux.
        """
        workspace = self.challenges_dir / challenge_id / "workspaces" / mission_id
        workspace.mkdir(parents=True, exist_ok=True)

        original_dir = self._original_dir(challenge_id)
        if original_dir.is_dir():
            for item in original_dir.iterdir():
                if item.is_file():
                    copy = workspace / item.name
                    shutil.copy2(item, copy)
                    # La copie de travail est modifiable (pas l'original).
                    copy.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return workspace
