"""Vérifie que le prompt hard-CTF impose méthode + profil profond + anti-triche."""

from fullctf.agents.container_adapter import ContainerAgentAdapter
from fullctf.models.mission import AgentProvider
from fullctf.models.challenge import Category
from fullctf.playbooks.render import category_profile, hardctf_method


def _prompt(objective):
    ad = ContainerAgentAdapter(
        AgentProvider.CLAUDE, challenge_files_dir="/tmp", target="t:1",
        description="énoncé", exec_run=lambda a, t: (0, "ok"),
    )
    return ad._full_prompt(objective)


def test_method_block_is_injected():
    p = _prompt("PROFIL : expert PWN")
    for must in ("MÉTHODE OBLIGATOIRE", "ANALYSE AVANT D'AGIR", "HYPOTHÈSES",
                 "TESTE MÉTHODIQUEMENT", "PERSISTE", "VÉRIFIE"):
        assert must in p


def test_method_forbids_unverified_or_placeholder_flag():
    p = _prompt("x")
    assert "non reproduit" in p and "exemple de format" in p


def test_deep_profiles_have_real_checklists():
    assert "CHECKLIST" in category_profile(Category.PWN)
    assert "one_gadget" in category_profile(Category.PWN)
    assert "Wiener" in category_profile(Category.CRYPTO)
    assert "SageMath" in category_profile(Category.CRYPTO)
    assert "IDOR" in category_profile(Category.WEB)
    assert "volatility3" in category_profile(Category.FORENSIC)


def test_method_is_nonempty():
    assert len(hardctf_method()) > 200
