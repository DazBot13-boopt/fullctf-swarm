"""Tests des playbooks (Sprint 7)."""

from fullctf.models.challenge import Category, Challenge
from fullctf.playbooks import (
    DEFAULT_PLAYBOOKS,
    Playbook,
    PlaybookRegistry,
    PlaybookStep,
    build_default_playbook_registry,
)


def test_default_playbooks_well_formed():
    assert len(DEFAULT_PLAYBOOKS) >= 5
    ids = [p.id for p in DEFAULT_PLAYBOOKS]
    assert len(ids) == len(set(ids))
    for p in DEFAULT_PLAYBOOKS:
        assert p.steps  # chaque playbook a des étapes


def test_playbook_matches_scoring():
    p = Playbook(
        id="x", category=Category.PWN, triggers=["overflow", "stack"],
        steps=[PlaybookStep(description="s")],
    )
    assert p.matches("there is a stack overflow here") == 2
    assert p.matches("nothing relevant") == 0


def test_registry_for_category():
    reg = build_default_playbook_registry()
    pwn = reg.for_category(Category.PWN)
    assert pwn
    assert all(p.category == Category.PWN for p in pwn)


def test_registry_select_best_by_triggers():
    reg = build_default_playbook_registry()
    c = Challenge(
        title="Baby RSA", category=Category.CRYPTO,
        description="given the public key with n = ... and e = ...",
    )
    selected = reg.select(c)
    assert selected is not None
    assert selected.id == "crypto/rsa"


def test_registry_select_none_for_unknown_category():
    reg = build_default_playbook_registry()
    c = Challenge(title="weird", category=Category.MISC)
    assert reg.select(c) is None


def test_registry_select_forensic_memory_vs_stego():
    reg = build_default_playbook_registry()
    c = Challenge(
        title="RAM capture", category=Category.FORENSIC,
        description="analyze this volatility memory dump", attachments=["capture.raw"],
    )
    selected = reg.select(c)
    assert selected is not None
    assert selected.id == "forensic/memory"
