"""Store de documents SQLite (stdlib, zéro dépendance lourde).

Stocke des documents JSON par collection. Sert de persistance par défaut.
L'interface DocStore permet de brancher PostgreSQL plus tard sans réécrire
les repositories.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Protocol


class DocStore(Protocol):
    """Interface de stockage de documents (implémentable en SQLite, Postgres...)."""

    def put(self, collection: str, doc_id: str, data: dict) -> None: ...
    def get(self, collection: str, doc_id: str) -> dict | None: ...
    def list(self, collection: str) -> list[dict]: ...
    def delete(self, collection: str, doc_id: str) -> None: ...


class SqliteDocStore:
    """Store de documents JSON basé sur sqlite3 (stdlib).

    path=":memory:" pour un store éphémère (tests), ou un chemin de fichier pour
    une persistance réelle.
    """

    def __init__(self, path: str = ":memory:") -> None:
        # check_same_thread=False + lock : sûr pour un usage API simple.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                collection TEXT NOT NULL,
                id         TEXT NOT NULL,
                data       TEXT NOT NULL,
                PRIMARY KEY (collection, id)
            )
            """
        )
        self._conn.commit()

    def put(self, collection: str, doc_id: str, data: dict) -> None:
        payload = json.dumps(data)
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents (collection, id, data) VALUES (?, ?, ?) "
                "ON CONFLICT(collection, id) DO UPDATE SET data = excluded.data",
                (collection, doc_id, payload),
            )
            self._conn.commit()

    def get(self, collection: str, doc_id: str) -> dict | None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT data FROM documents WHERE collection = ? AND id = ?",
                (collection, doc_id),
            )
            row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def list(self, collection: str) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT data FROM documents WHERE collection = ? ORDER BY rowid",
                (collection,),
            )
            rows = cur.fetchall()
        return [json.loads(r[0]) for r in rows]

    def delete(self, collection: str, doc_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM documents WHERE collection = ? AND id = ?",
                (collection, doc_id),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
