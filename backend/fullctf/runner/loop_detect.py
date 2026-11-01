"""Détection de boucle — adapté de ctf-agent (MIT) à notre modèle CLI.

ctf-agent intercepte CHAQUE appel d'outil (SDK + hooks). Nous pilotons des CLI
« boîte noire » (claude -p / codex exec) : on ne voit que la SORTIE FINALE. On
détecte donc les boucles **a posteriori** dans cette sortie — une même commande
répétée sans résultat — pour :
- signaler qu'un agent a bouclé (trace / rapport) ;
- injecter un avertissement au prochain agent (bump) : « ne refais pas ça ».

Crédit : concept repris de verialabs/ctf-agent (MIT), réécrit pour notre archi.
"""

from __future__ import annotations

from collections import Counter

LOOP_WARNING_MESSAGE = (
    "⚠️ TU ÉTAIS EN BOUCLE : tu as relancé la même commande plusieurs fois avec le "
    "même résultat. ARRÊTE de la répéter. Prends du recul et essaie une approche "
    "RADICALEMENT différente (autre outil, autre angle). Qu'est-ce que tu n'as pas "
    "encore exploré ?"
)


def detect_loop(output: str, *, min_repeat: int = 4) -> tuple[bool, str | None]:
    """Repère une commande identique répétée au moins `min_repeat` fois dans la sortie.

    Retourne (a_bouclé, commande_répétée). Heuristique volontairement prudente : on
    ne compte que des lignes « commande-like » (ni trop courtes ni trop longues),
    pour éviter le bruit des sorties verbeuses.
    """
    lines = [ln.strip() for ln in (output or "").splitlines() if ln.strip()]
    cmds = [ln for ln in lines if 5 <= len(ln) <= 300]
    if not cmds:
        return False, None
    top, n = Counter(cmds).most_common(1)[0]
    if n >= min_repeat:
        return True, top
    return False, None
