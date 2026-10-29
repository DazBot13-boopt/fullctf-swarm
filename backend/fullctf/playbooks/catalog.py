"""Catalogue de playbooks par défaut (Sprint 7)."""

from __future__ import annotations

from ..models.challenge import Category
from .playbook import Playbook, PlaybookStep

DEFAULT_PLAYBOOKS: list[Playbook] = [
    Playbook(
        id="pwn/basic-bof",
        category=Category.PWN,
        triggers=["overflow", "buffer", "stack", "ret", "nc "],
        description="Résolution d'un dépassement de tampon classique.",
        steps=[
            PlaybookStep(description="Vérifier les protections du binaire", tool="pwntools",
                         args_hint=["checksec"]),
            PlaybookStep(description="Trouver l'offset de contrôle de RIP/EIP", tool="gdb"),
            PlaybookStep(description="Chercher des gadgets ROP si NX actif", tool="ROPgadget",
                         args_hint=["--binary"]),
            PlaybookStep(description="Écrire l'exploit et récupérer le shell", tool="pwntools"),
        ],
    ),
    Playbook(
        id="web/recon",
        category=Category.WEB,
        triggers=["http", "url", "login", "cookie", "api"],
        description="Reconnaissance et test d'une application web.",
        steps=[
            PlaybookStep(description="Fuzzer les endpoints et fichiers cachés", tool="ffuf",
                         args_hint=["-u", "-w"]),
            PlaybookStep(description="Tester les injections (SQL, etc.)", tool="sqlmap",
                         args_hint=["-u", "--batch"]),
            PlaybookStep(description="Inspecter cookies/JWT et logique d'auth"),
            PlaybookStep(description="Vérifier SSRF/LFI/IDOR selon la surface"),
        ],
    ),
    Playbook(
        id="crypto/rsa",
        category=Category.CRYPTO,
        triggers=["rsa", "modulus", "public key", "n =", "e ="],
        description="Attaques RSA courantes.",
        steps=[
            PlaybookStep(description="Tenter les attaques RSA automatiques", tool="rsactftool",
                         args_hint=["--publickey", "--private"]),
            PlaybookStep(description="Factoriser n si petit / spécial", tool="sagemath"),
            PlaybookStep(description="Vérifier e faible, n partagé, Wiener, etc.", tool="sagemath"),
        ],
    ),
    Playbook(
        id="forensic/memory",
        category=Category.FORENSIC,
        triggers=["memory", "dump", "ram", "volatility", ".raw", ".mem"],
        description="Analyse d'un dump mémoire.",
        steps=[
            PlaybookStep(description="Lister les processus et connexions", tool="volatility3",
                         args_hint=["-f", "windows.pslist"]),
            PlaybookStep(description="Extraire fichiers/artefacts suspects", tool="volatility3"),
            PlaybookStep(description="Chercher le flag dans la mémoire/les dumps"),
        ],
    ),
    Playbook(
        id="forensic/stego-image",
        category=Category.FORENSIC,
        triggers=["image", "png", "jpg", "steg", "hidden"],
        description="Recherche de données cachées dans une image.",
        steps=[
            PlaybookStep(description="Lire les métadonnées", tool="exiftool"),
            PlaybookStep(description="Chercher des fichiers embarqués", tool="binwalk",
                         args_hint=["-e"]),
            PlaybookStep(description="Tester la stégano LSB", tool="zsteg"),
        ],
    ),
]


def build_default_playbook_registry():
    """Construit un PlaybookRegistry pré-rempli."""
    from .registry import PlaybookRegistry

    reg = PlaybookRegistry()
    reg.register_many(DEFAULT_PLAYBOOKS)
    return reg
