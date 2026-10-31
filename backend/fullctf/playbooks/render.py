"""Rendu d'un playbook + profil d'expert par catégorie, pour injection au prompt.

Transforme l'intelligence « froide » (catalogue de playbooks) en guidage concret
pour le worker : au lieu de tâtonner, il reçoit le profil d'expert de la catégorie
et une démarche éprouvée. C'est le levier de fiabilité pour pwn/rev/crypto/forensic.
"""

from __future__ import annotations

from ..models.challenge import Category
from .playbook import Playbook

# Profil d'expert + arsenal disponible, par catégorie.
_PROFILES: dict[Category, str] = {
    Category.WEB: (
        "PROFIL : expert WEB. Arsenal dans le conteneur : curl, ffuf, feroxbuster, "
        "sqlmap, nikto, whatweb, Playwright, python3. Démarche : cartographier les "
        "routes, lire le code source fourni, chercher IDOR / contrôle d'accès cassé / "
        "injections (SQL, NoSQL avec opérateurs $), SSRF/LFI/XXE, défauts JWT/session."
    ),
    Category.PWN: (
        "PROFIL : expert PWN. Arsenal : pwntools, gdb+pwndbg, ROPGadget, one_gadget, "
        "radare2, angr. Démarche : `checksec` le binaire, trouver l'offset de contrôle, "
        "selon les protections monter ret2win / ret2libc / ROP, écrire l'exploit "
        "pwntools. Service distant : `pwntools remote(host, port)`."
    ),
    Category.REVERSE: (
        "PROFIL : expert REVERSE. Arsenal : Ghidra headless (analyzeHeadless), radare2, "
        "angr, python3. Démarche : décompiler, isoler la fonction de vérification, "
        "reconstituer la logique, résoudre les contraintes (angr/z3) pour retrouver "
        "l'entrée valide / le flag."
    ),
    Category.CRYPTO: (
        "PROFIL : expert CRYPTO. Arsenal : RsaCtfTool, sage (si présent), z3, "
        "pycryptodome, sympy, gmpy2, fpylll. Démarche : identifier le schéma, pour RSA "
        "tester les attaques classiques (n petit/partagé, e faible, Wiener, Hastad), "
        "pour le reste repérer le défaut (nonce réutilisé, padding, XOR, LCG...)."
    ),
    Category.FORENSIC: (
        "PROFIL : expert FORENSIC. Arsenal : volatility3, binwalk, foremost, exiftool, "
        "steghide, zsteg, tshark, scapy, strings. Démarche : identifier le type de "
        "fichier, trier (métadonnées, fichiers embarqués, stégano LSB), pour un pcap "
        "suivre les flux, pour un dump mémoire lister processus/artefacts, puis chercher "
        "le flag."
    ),
    Category.MISC: (
        "PROFIL : généraliste. Analyse le challenge, identifie la nature du défi et "
        "utilise l'arsenal du conteneur (strings, python3, binwalk, zsteg, etc.)."
    ),
}


def category_profile(category: Category) -> str:
    """Profil d'expert + arsenal pour une catégorie (chaîne vide si inconnue)."""
    return _PROFILES.get(category, "")


def render_playbook(playbook: Playbook | None) -> str:
    """Rend un playbook en bloc de prompt (démarche ordonnée). Vide si None."""
    if playbook is None:
        return ""
    lines = [f"PLAYBOOK « {playbook.id} » — {playbook.description}",
             "Démarche recommandée (adapte si besoin) :"]
    for i, step in enumerate(playbook.steps, 1):
        tool = f" [outil: {step.tool}" + (f" {' '.join(step.args_hint)}" if step.args_hint else "") + "]" if step.tool else ""
        lines.append(f"  {i}. {step.description}{tool}")
    return "\n".join(lines)
