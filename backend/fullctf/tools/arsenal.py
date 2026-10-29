"""Catalogue par défaut de l'arsenal CTF (manifestes).

Ces manifestes décrivent les outils de l'image fat. L'installation réelle se fait
dans le Dockerfile (infrastructure/Dockerfile.arsenal). Ici, on déclare seulement.
"""

from __future__ import annotations

from .manifest import ToolCategory, ToolManifest

DEFAULT_ARSENAL: list[ToolManifest] = [
    # --- Web ---
    ToolManifest(
        id="ffuf", category=ToolCategory.WEB, command="ffuf",
        description="Fuzzing rapide d'endpoints/paramètres web.",
        parameters=["-u", "-w", "-mc"], needs_network=True,
    ),
    ToolManifest(
        id="sqlmap", category=ToolCategory.WEB, command="sqlmap",
        description="Détection/exploitation d'injections SQL.",
        parameters=["-u", "--batch"], needs_network=True,
    ),
    # --- Pwn ---
    ToolManifest(
        id="pwntools", category=ToolCategory.PWN, command="python3",
        description="Framework d'exploitation (import pwn).",
        required_binaries=["python3"],
    ),
    ToolManifest(
        id="ROPgadget", category=ToolCategory.PWN, command="ROPgadget",
        description="Recherche de gadgets ROP.", parameters=["--binary"],
        produces_artifacts=True,
    ),
    # --- Reverse ---
    ToolManifest(
        id="ghidra", category=ToolCategory.REVERSE, command="ghidra",
        description="Décompilation (mode headless scriptable).",
        produces_artifacts=True, timeout_seconds=1800,
    ),
    ToolManifest(
        id="angr", category=ToolCategory.REVERSE, command="python3",
        description="Exécution symbolique (import angr).",
    ),
    # --- Crypto ---
    ToolManifest(
        id="sagemath", category=ToolCategory.CRYPTO, command="sage",
        description="Calcul mathématique pour la crypto.", timeout_seconds=900,
    ),
    ToolManifest(
        id="rsactftool", category=ToolCategory.CRYPTO, command="RsaCtfTool",
        description="Attaques RSA automatiques.", parameters=["--publickey", "--private"],
    ),
    # --- Forensic ---
    ToolManifest(
        id="volatility3", category=ToolCategory.FORENSIC, command="vol",
        description="Analyse de dumps mémoire.", produces_artifacts=True,
        timeout_seconds=1200,
    ),
    ToolManifest(
        id="binwalk", category=ToolCategory.FORENSIC, command="binwalk",
        description="Analyse/extraction de firmware et fichiers.",
        parameters=["-e"], produces_artifacts=True,
    ),
    ToolManifest(
        id="exiftool", category=ToolCategory.FORENSIC, command="exiftool",
        description="Métadonnées de fichiers/images.",
    ),
    # --- Network ---
    ToolManifest(
        id="tshark", category=ToolCategory.NETWORK, command="tshark",
        description="Analyse de captures réseau (PCAP).", parameters=["-r"],
    ),
    # --- Misc ---
    ToolManifest(
        id="zsteg", category=ToolCategory.MISC, command="zsteg",
        description="Stéganographie LSB sur PNG/BMP.",
    ),
]


def build_default_registry():
    """Construit un ToolRegistry pré-rempli avec l'arsenal par défaut."""
    from .registry import ToolRegistry

    reg = ToolRegistry()
    reg.register_many(DEFAULT_ARSENAL)
    return reg
