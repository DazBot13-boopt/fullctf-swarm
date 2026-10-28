"""Classification d'un challenge (noyau code du Commander, règles explicites)."""

from __future__ import annotations

from ..models.challenge import Category, Challenge

# Mots-clés par catégorie pour affiner quand la catégorie est inconnue.
_CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.WEB: ("http", "cookie", "xss", "sql", "flask", "php", "url", "jwt"),
    Category.PWN: ("overflow", "rop", "shellcode", "libc", "heap", "stack", "exploit"),
    Category.REVERSE: ("binary", "disassemble", "decompile", "ghidra", "obfuscat"),
    Category.CRYPTO: ("rsa", "aes", "cipher", "encrypt", "hash", "xor", "key"),
    Category.FORENSIC: ("pcap", "memory", "dump", "volatility", "carve", "steg"),
}

# Indices par extension de fichier.
_EXT_HINTS: dict[str, Category] = {
    ".pcap": Category.FORENSIC,
    ".pcapng": Category.FORENSIC,
    ".raw": Category.FORENSIC,
    ".mem": Category.FORENSIC,
}


def infer_category(challenge: Challenge) -> Category:
    """Déduit la catégorie si elle est inconnue, sinon garde celle fournie."""
    if challenge.category != Category.UNKNOWN:
        return challenge.category

    # Indice par extension de pièce jointe.
    for attachment in challenge.attachments:
        for ext, cat in _EXT_HINTS.items():
            if attachment.lower().endswith(ext):
                return cat

    # Indice par mots-clés dans le titre + description.
    text = f"{challenge.title} {challenge.description}".lower()
    best: Category = Category.UNKNOWN
    best_score = 0
    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best = category
    return best if best_score > 0 else Category.MISC
