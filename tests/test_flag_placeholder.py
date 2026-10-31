"""Les placeholders de format ne doivent JAMAIS être pris pour un vrai flag."""
from fullctf.verifier.flag_verifier import extract_flags, is_placeholder_flag


def test_placeholders_rejected():
    assert is_placeholder_flag("NOM{...}")
    assert is_placeholder_flag("FLAG{...}")
    assert is_placeholder_flag("CTF{…}")
    assert is_placeholder_flag("flag{XXX}")
    assert not is_placeholder_flag("CTF{a1428a3ae5db7d74}")
    assert not is_placeholder_flag("bugpwn{real_flag_here}")


def test_extract_ignores_placeholders_keeps_real():
    text = ("affiche le flag au format NOM{...}. "
            "J'ai trouvé : CTF{a1428a3ae5db7d74d6c6d1eab1c6296f}")
    flags = extract_flags(text)
    assert "NOM{...}" not in flags
    assert flags == ["CTF{a1428a3ae5db7d74d6c6d1eab1c6296f}"]
