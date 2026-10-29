"""Tests du connecteur CTFd + Local Executor (Sprint 10)."""

import pytest

from fullctf.ctfd import (
    CTFdClient,
    ExecutorKind,
    ExecutorNode,
    ExecutorPool,
    HttpResponse,
    NoExecutorAvailable,
)
from fullctf.models.policies import ExecutionMode


class FakeHttp:
    """Client HTTP factice, programmable, pour tester sans réseau."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def get(self, url, headers):
        self.calls.append(("GET", url))
        return self.responses.get(("GET", url), HttpResponse(status_code=404, json_body={}))

    def post(self, url, headers, json):
        self.calls.append(("POST", url))
        return self.responses.get(("POST", url), HttpResponse(status_code=404, json_body={}))


# --- CTFd client ---

def test_list_challenges():
    base = "https://ctf.example"
    http = FakeHttp({
        ("GET", f"{base}/api/v1/challenges"): HttpResponse(
            status_code=200,
            json_body={"data": [
                {"id": 1, "name": "Baby RSA", "category": "crypto", "value": 100},
                {"id": 2, "name": "Stack", "category": "pwn", "value": 300,
                 "solved_by_me": True},
            ]},
        )
    })
    client = CTFdClient(base, token="secret", http=http)
    chals = client.list_challenges()
    assert len(chals) == 2
    assert chals[0].name == "Baby RSA"
    assert chals[1].solved is True


def test_submit_correct_flag():
    base = "https://ctf.example"
    http = FakeHttp({
        ("POST", f"{base}/api/v1/challenges/attempt"): HttpResponse(
            status_code=200, json_body={"data": {"status": "correct", "message": "GG"}},
        )
    })
    client = CTFdClient(base, token="secret", http=http)
    res = client.submit_flag(1, "FLAG{x}")
    assert res.accepted is True


def test_submit_incorrect_flag():
    base = "https://ctf.example"
    http = FakeHttp({
        ("POST", f"{base}/api/v1/challenges/attempt"): HttpResponse(
            status_code=200, json_body={"data": {"status": "incorrect"}},
        )
    })
    client = CTFdClient(base, token="secret", http=http)
    assert client.submit_flag(1, "nope").accepted is False


def test_token_not_in_repr():
    client = CTFdClient("https://x", token="super-secret-token", http=FakeHttp({}))
    # Le token ne doit pas fuiter dans la représentation de l'objet.
    assert "super-secret-token" not in repr(client)


# --- Executor pool ---

def test_executor_prefers_local_for_local_only():
    pool = ExecutorPool()
    pool.register(ExecutorNode(id="srv", kind=ExecutorKind.SERVER, capabilities=["docker"]))
    pool.register(ExecutorNode(id="pc", kind=ExecutorKind.LOCAL_PC, capabilities=["docker"]))
    chosen = pool.select(ExecutionMode.LOCAL_ONLY)
    assert chosen.kind == ExecutorKind.LOCAL_PC


def test_executor_prefers_server_for_connected():
    pool = ExecutorPool()
    pool.register(ExecutorNode(id="srv", kind=ExecutorKind.SERVER))
    pool.register(ExecutorNode(id="pc", kind=ExecutorKind.LOCAL_PC))
    chosen = pool.select(ExecutionMode.CONNECTED)
    assert chosen.kind == ExecutorKind.SERVER


def test_executor_falls_back_when_preferred_absent():
    pool = ExecutorPool()
    pool.register(ExecutorNode(id="srv", kind=ExecutorKind.SERVER))
    # Pas de local dispo -> repli sur serveur même en local_only.
    chosen = pool.select(ExecutionMode.LOCAL_ONLY)
    assert chosen.kind == ExecutorKind.SERVER


def test_executor_requires_capabilities():
    pool = ExecutorPool()
    pool.register(ExecutorNode(id="srv", kind=ExecutorKind.SERVER, capabilities=["docker"]))
    with pytest.raises(NoExecutorAvailable):
        pool.select(ExecutionMode.CONNECTED, required_capabilities=["gpu"])


def test_executor_ignores_offline():
    pool = ExecutorPool()
    pool.register(ExecutorNode(id="pc", kind=ExecutorKind.LOCAL_PC, online=False))
    with pytest.raises(NoExecutorAvailable):
        pool.select(ExecutionMode.LOCAL_ONLY)
