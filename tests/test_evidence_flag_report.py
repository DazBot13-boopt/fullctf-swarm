"""Tests Evidence Store + Flag Verifier + Reports (Sprint 6)."""

import pytest

from fullctf.evidence import EvidenceStore
from fullctf.models.challenge import Category, Challenge, Difficulty
from fullctf.models.evidence import Evidence, VerificationStatus
from fullctf.models.flag import FlagCandidate, FlagStatus
from fullctf.reports import build_markdown_report
from fullctf.verifier import FlagVerifier


# --- Evidence Store ---

def _evidence(cid="c1", mid="m1", obs="observed X"):
    return Evidence(challenge_id=cid, mission_id=mid, source="codex/ghidra", observation=obs)


def test_evidence_add_and_query():
    store = EvidenceStore()
    e = store.add(_evidence())
    assert store.get(e.id).observation == "observed X"
    assert store.for_challenge("c1") == [e]
    assert store.for_mission("m1") == [e]


def test_evidence_verification_filter():
    store = EvidenceStore()
    e1 = store.add(_evidence(obs="a"))
    store.add(_evidence(obs="b"))
    store.mark(e1.id, VerificationStatus.VERIFIED)
    verified = store.verified("c1")
    assert len(verified) == 1
    assert verified[0].observation == "a"


# --- Flag Verifier ---

def _flag(value="FLAG{test_123}"):
    return FlagCandidate(challenge_id="c1", value=value, source_mission="m1")


def test_flag_format_valid():
    v = FlagVerifier()
    f = v.check_format(_flag("FLAG{good_one}"))
    assert f.validation_status == FlagStatus.FORMAT_VALID


def test_flag_bad_format_rejected():
    v = FlagVerifier()
    f = v.check_format(_flag("not a flag at all"))
    assert f.validation_status == FlagStatus.REJECTED


def test_flag_full_happy_path():
    v = FlagVerifier()
    f = v.check_format(_flag("CTF{repro_me}"))
    f = v.reproduce(f, reproducer=lambda: True, reference="solve.py")
    assert f.validation_status == FlagStatus.REPRODUCED
    assert f.reproduction_reference == "solve.py"
    f = v.accept(f, platform_feedback="correct")
    assert f.validation_status == FlagStatus.ACCEPTED


def test_flag_reproduction_failure_rejects():
    v = FlagVerifier()
    f = v.check_format(_flag("CTF{fake}"))
    f = v.reproduce(f, reproducer=lambda: False, reference="x")
    assert f.validation_status == FlagStatus.REJECTED


def test_flag_cannot_skip_to_accept():
    v = FlagVerifier()
    f = _flag("FLAG{x}")  # encore candidate
    with pytest.raises(ValueError):
        v.accept(f)


# --- Reports ---

def test_report_contains_key_sections():
    challenge = Challenge(title="Baby RSA", category=Category.CRYPTO, difficulty=Difficulty.EASY)
    store = EvidenceStore()
    e = store.add(Evidence(
        challenge_id=challenge.id, mission_id="m1",
        source="claude/sage", observation="n se factorise",
        checksum="abc123",
    ))
    flag = FlagCandidate(
        challenge_id=challenge.id, value="FLAG{rsa_broken}",
        source_mission="m1", validation_status=FlagStatus.REPRODUCED,
        reproduction_reference="solve.sage",
    )
    md = build_markdown_report(
        challenge, [e], flag,
        strategies=["factorisation de n"], agents=["claude"], tools=["sagemath"],
        uncertainties="aucune",
    )
    assert "# Rapport — Baby RSA" in md
    assert "FLAG{rsa_broken}" in md
    assert "reproduced" in md
    assert "sagemath" in md
    assert "abc123" in md


def test_report_without_flag():
    challenge = Challenge(title="Mystery")
    md = build_markdown_report(challenge, [], None)
    assert "Aucun flag candidat" in md
