"""Tests du Local Solver (Sprint 2)."""

import os
import stat

import pytest

from fullctf.challenges import LocalSolver, detect_type, sha256_of


@pytest.fixture
def solver(tmp_path):
    return LocalSolver(data_root=tmp_path / "data")


def _write(path, data: bytes):
    path.write_bytes(data)
    return path


def test_detect_type_elf(tmp_path):
    f = _write(tmp_path / "bin", b"\x7fELF\x02\x01\x01\x00rest")
    assert detect_type(f) == "elf"


def test_detect_type_zip(tmp_path):
    f = _write(tmp_path / "a.zip", b"PK\x03\x04moredata")
    assert detect_type(f) == "zip"


def test_detect_type_python(tmp_path):
    f = _write(tmp_path / "solve.py", b"print('hi')\n")
    assert detect_type(f) == "python"


def test_detect_type_unknown(tmp_path):
    f = _write(tmp_path / "weird.bin", b"\x00\x01\x02\x03random")
    assert detect_type(f) == "unknown"


def test_import_preserves_original_and_is_readonly(solver, tmp_path):
    src = _write(tmp_path / "chall.py", b"flag_logic()\n")
    art = solver.import_file("chal-1", src)

    assert art.original_path.exists()
    assert art.detected_type == "python"
    assert art.checksum == sha256_of(src)
    assert art.size_bytes == src.stat().st_size

    # L'original importé est en lecture seule (pas de bit d'écriture).
    mode = art.original_path.stat().st_mode
    assert not (mode & stat.S_IWUSR)


def test_import_missing_file_raises(solver):
    with pytest.raises(FileNotFoundError):
        solver.import_file("chal-x", "/does/not/exist.bin")


def test_workspace_is_a_writable_copy(solver, tmp_path):
    src = _write(tmp_path / "data.txt", b"hello challenge")
    solver.import_file("chal-2", src)

    ws = solver.create_workspace("chal-2", "mission-1")
    copy = ws / "data.txt"
    assert copy.exists()
    assert copy.read_bytes() == b"hello challenge"

    # La copie de travail est modifiable.
    assert os.access(copy, os.W_OK)
    copy.write_bytes(b"modified by agent")
    assert copy.read_bytes() == b"modified by agent"


def test_workspaces_are_isolated(solver, tmp_path):
    src = _write(tmp_path / "shared.txt", b"base")
    solver.import_file("chal-3", src)

    ws1 = solver.create_workspace("chal-3", "m1")
    ws2 = solver.create_workspace("chal-3", "m2")
    assert ws1 != ws2

    (ws1 / "shared.txt").write_bytes(b"changed in m1")
    # m2 n'est pas affecté par les modifications de m1.
    assert (ws2 / "shared.txt").read_bytes() == b"base"
