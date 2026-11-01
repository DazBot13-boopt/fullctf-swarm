"""Rendu d'un playbook + profil d'expert par catégorie, pour injection au prompt.

Transforme l'intelligence « froide » (catalogue de playbooks) en guidage concret
pour le worker : au lieu de tâtonner, il reçoit le profil d'expert de la catégorie
et une démarche éprouvée. C'est le levier de fiabilité pour pwn/rev/crypto/forensic.
"""

from __future__ import annotations

from ..models.challenge import Category
from .playbook import Playbook

# Méthode OBLIGATOIRE injectée dans chaque prompt : force le raisonnement profond,
# le test systématique, la persistance et l'auto-vérification. C'est le levier n°1
# pour les challenges DURS (le goulot n'est pas l'outil, c'est la rigueur de l'agent).
HARD_CTF_METHOD = (
    "MÉTHODE OBLIGATOIRE (challenge DUR — prends ton temps, ne saute AUCUNE étape) :\n"
    "1) ANALYSE AVANT D'AGIR : énumère TOUT (recon, lecture intégrale de la source, "
    "protections, surface d'attaque). Écris 2–3 HYPOTHÈSES d'attaque explicites AVANT "
    "d'essayer quoi que ce soit.\n"
    "2) TESTE MÉTHODIQUEMENT : une hypothèse à la fois. Après CHAQUE échec, écris "
    "POURQUOI ça a échoué et ce que tu ÉCARTES. Ne répète JAMAIS la même tentative.\n"
    "3) PERSISTE : si bloqué, recule et change RADICALEMENT d'angle. Sers-toi de TOUT "
    "l'arsenal ; installe ce qui manque (pip/apt/gem). N'abandonne pas à la 1re idée.\n"
    "4) VÉRIFIE : dès que tu tiens un flag candidat, REJOUE ta méthode pour confirmer "
    "qu'il ressort bien de la cible. Ne reporte JAMAIS un flag non reproduit, ni un "
    "exemple de format. Si tu ne l'as pas : dis-le honnêtement + liste ce que tu as écarté."
)

# Profil d'expert PROFOND + arsenal + checklist réelle, par catégorie (hard-CTF).
_PROFILES: dict[Category, str] = {
    Category.WEB: (
        "PROFIL : expert WEB. Arsenal : curl, ffuf, feroxbuster, sqlmap, nuclei, dalfox, "
        "httpx, Playwright, python3.\n"
        "CHECKLIST : 1) cartographie (routes, méthodes, paramètres, cookies/JWT, en-têtes) ; "
        "2) LIS la source fournie ligne par ligne — repère la logique d'auth et les requêtes "
        "DB ; 3) teste systématiquement : IDOR / contrôle d'accès (change d'ID/owner), "
        "injections (SQLi, NoSQLi avec $ne/$gt/$or/$regex, SSTI, cmd), SSRF/LFI/XXE, "
        "désérialisation, race conditions, JWT (alg=none, clé faible), mass assignment ; "
        "4) si la source est donnée, trouve la faille DANS le code avant de fuzzer à l'aveugle."
    ),
    Category.PWN: (
        "PROFIL : expert PWN. Arsenal : pwntools, gdb+gef+pwndbg, ROPgadget, ropper, "
        "one_gadget, libc-database, pwninit, seccomp-tools, angr.\n"
        "CHECKLIST : 1) `checksec` (NX/PIE/canary/RELRO) + identifie l'architecture ; "
        "2) repère la PRIMITIVE (overflow stack/heap, format string, OOB, UAF/double-free) ; "
        "3) trouve l'offset (cyclic/pattern) ; 4) selon protections : ret2win → ret2libc "
        "(leak GOT→libc, one_gadget) → ROP → heap (tcache/fastbin/unlink) ; contourne "
        "PIE/ASLR via un leak ; 5) format string = lecture/écriture arbitraire (%p/%n) ; "
        "6) teste en LOCAL d'abord, puis `remote(host,port)`. Utilise pwninit + libc-database "
        "pour la bonne libc."
    ),
    Category.REVERSE: (
        "PROFIL : expert REVERSE. Arsenal : Ghidra (analyzeHeadless scriptable), radare2, "
        "angr, gdb+gef, python3.\n"
        "CHECKLIST : 1) `file`, `strings`, imports, protections, packing ; 2) décompile "
        "(Ghidra headless) et ISOLE la fonction de vérification/check ; 3) reconstitue la "
        "logique (transformations, comparaisons, clés) ; 4) si contraintes → angr/z3 pour "
        "résoudre l'entrée valide ; 5) anti-debug/packé → dump à l'exécution (gdb) ; "
        "6) le flag est souvent CALCULÉ, pas en clair — reconstruis l'algo inverse."
    ),
    Category.CRYPTO: (
        "PROFIL : expert CRYPTO. Arsenal : SageMath, RsaCtfTool, z3, pycryptodome, sympy, "
        "gmpy2, fpylll, flint.\n"
        "CHECKLIST : 1) identifie le schéma EXACT (RSA, AES+mode, ECC, DH, hash, LCG, XOR) ; "
        "2) RSA : n petit/partagé (gcd/factordb), e faible (racine e-ième), Wiener (d petit), "
        "Hastad/Franklin-Reiter, Coppersmith (sage), mauvais padding ; 3) AES : ECB (blocs "
        "identiques), CBC padding-oracle / bit-flip, CTR nonce réutilisé ; 4) ECC : courbe "
        "faible, Smart/MOV, nonce ECDSA réutilisé ; 5) autres : XOR (analyse fréquentielle), "
        "LCG (récupère l'état), aléa prévisible. Utilise SageMath pour les maths lourdes "
        "(lattices/LLL via fpylll)."
    ),
    Category.FORENSIC: (
        "PROFIL : expert FORENSIC. Arsenal : volatility3, binwalk, foremost, exiftool, "
        "steghide, zsteg, tshark, scapy, strings, xxd.\n"
        "CHECKLIST : 1) `file` + `strings` + `exiftool` + `binwalk` (fichiers embarqués) ; "
        "2) image → stégano (zsteg LSB, steghide, bits de poids faible, données après EOF) ; "
        "3) pcap → suis les flux TCP (tshark follow), extrais fichiers/credentials, exfil "
        "HTTP/DNS/ICMP ; 4) dump mémoire → volatility3 (pslist, cmdline, filescan, dumpfiles, "
        "hashdump, netscan) ; 5) le flag est souvent caché/encodé (base64, hex, zlib, rot)."
    ),
    Category.MISC: (
        "PROFIL : généraliste rigoureux. Identifie la nature exacte du défi (encodage, "
        "esolang, logique, QR/barcode, PPC/scripting réseau…) et attaque avec l'arsenal "
        "(strings, python3, binwalk, zsteg, CyberChef-like en python). Automatise si le "
        "défi demande de la vitesse (PPC)."
    ),
}


def category_profile(category: Category) -> str:
    """Profil d'expert + arsenal pour une catégorie (chaîne vide si inconnue)."""
    return _PROFILES.get(category, "")


def hardctf_method() -> str:
    """Bloc méthode obligatoire (raisonnement profond + persistance + vérification)."""
    return HARD_CTF_METHOD


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
