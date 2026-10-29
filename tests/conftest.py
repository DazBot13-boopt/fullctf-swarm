"""Configuration de tests : base en mémoire pour l'isolation.

Doit s'exécuter AVANT l'import de l'app (conftest est chargé en premier par pytest).
"""

import os

# Les tests ne doivent pas écrire de vrai fichier de base ni partager d'état.
os.environ["FULLCTF_DB_PATH"] = ":memory:"
