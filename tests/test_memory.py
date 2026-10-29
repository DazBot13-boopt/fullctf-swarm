"""Tests de la mémoire d'expérience (Sprint 8)."""

from fullctf.memory import MemoryEntry, MemoryStore
from fullctf.models.challenge import Category


def _seed(store: MemoryStore):
    store.add(MemoryEntry(
        challenge_title="Baby RSA", category=Category.CRYPTO,
        techniques=["factorisation", "fermat"], tools_used=["sagemath", "rsactftool"],
        summary="n était un produit de deux premiers proches",
        report_reference="reports/baby-rsa.md",
    ))
    store.add(MemoryEntry(
        challenge_title="Stack smash", category=Category.PWN,
        techniques=["buffer overflow", "ret2libc"], tools_used=["pwntools", "gdb"],
        summary="dépassement de tampon classique avec ret2libc",
        report_reference="reports/stack.md",
    ))
    store.add(MemoryEntry(
        challenge_title="Hidden pixels", category=Category.FORENSIC,
        techniques=["lsb stego"], tools_used=["zsteg"],
        summary="flag caché en LSB dans un PNG",
    ))


def test_add_and_get():
    store = MemoryStore()
    e = store.add(MemoryEntry(challenge_title="x", category=Category.WEB))
    assert store.get(e.id).challenge_title == "x"


def test_search_finds_relevant_entry():
    store = MemoryStore()
    _seed(store)
    results = store.search("rsa factorisation")
    assert results
    assert results[0].entry.challenge_title == "Baby RSA"
    # La source est citée.
    assert results[0].entry.report_reference == "reports/baby-rsa.md"


def test_search_empty_query():
    store = MemoryStore()
    _seed(store)
    assert store.search("") == []


def test_search_no_match():
    store = MemoryStore()
    _seed(store)
    assert store.search("quantum blockchain nonsense") == []


def test_search_category_filter_and_bonus():
    store = MemoryStore()
    _seed(store)
    results = store.search("overflow", category=Category.PWN)
    assert all(r.entry.category == Category.PWN for r in results)
    assert results[0].entry.challenge_title == "Stack smash"


def test_search_respects_limit():
    store = MemoryStore()
    for i in range(10):
        store.add(MemoryEntry(
            challenge_title=f"web {i}", category=Category.WEB,
            summary="sql injection login bypass",
        ))
    results = store.search("sql injection", limit=3)
    assert len(results) == 3
