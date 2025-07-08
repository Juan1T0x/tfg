#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services.riot_api.riot_versions
===============================

Persists every patch released by Riot (Data-Dragon) inside the
**versions** table (`assets/db/moba_analysis.sqlite`).  Riot returns the
version list ordered from **newest → oldest**; we preserve that order
assigning *version_id = 0* to the latest patch:

    ┌───────────┬─────────┐
    │ version_id│ version │
    ├───────────┼─────────┤
    │     0     │ 14.12.1 │  ← most recent
    │     1     │ 14.11.1 │
    │     2     │ 14.10.1 │
    │    …      │   …     │
    └───────────┴─────────┘

Public helpers
--------------
* :func:`get_versions` – full list (newest first).
* :func:`get_latest_version` – single call, always `version_id = 0`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

import requests

# --------------------------------------------------------------------------- #
# Constants / paths                                                           #
# --------------------------------------------------------------------------- #
_URL   = "https://ddragon.leagueoflegends.com/api/versions.json"
_DB    = Path(__file__).resolve().parents[2] / "assets" / "db" / "moba_analysis.sqlite"
_TABLE = "versions"

# --------------------------------------------------------------------------- #
# Fetch & store                                                               #
# --------------------------------------------------------------------------- #
def _fetch_versions() -> List[str]:
    """Return Riot’s patch list (already sorted newest → oldest)."""
    return requests.get(_URL, timeout=15).json()

def _create_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            version_id INTEGER PRIMARY KEY,
            version    TEXT UNIQUE
        )
        """
    )

def _upsert(versions: List[str]) -> int:
    """
    Insert *all* versions keeping bidirectional uniqueness guarantees:
    * **version_id** ↔ **version** are always in sync.
    Returns the net number of *new* rows inserted.
    """
    with sqlite3.connect(_DB) as conn:
        _create_table(conn)

        pairs   = [(idx, v) for idx, v in enumerate(versions)]
        sql = (
            f"INSERT INTO {_TABLE}(version_id, version) VALUES (?, ?) "
            f"ON CONFLICT(version)    DO UPDATE SET version_id = excluded.version_id "
            f"ON CONFLICT(version_id) DO UPDATE SET version    = excluded.version"
        )

        before = conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]
        conn.executemany(sql, pairs)
        after  = conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]

    return after - before

# --------------------------------------------------------------------------- #
# Public helpers                                                              #
# --------------------------------------------------------------------------- #
def get_versions() -> List[str]:
    """
    Return the full patch list (newest first) after refreshing the DB if
    necessary.
    """
    changes = _upsert(_fetch_versions())
    if changes:
        print(f"✔ Versiones nuevas/actualizadas: {changes}")
    with sqlite3.connect(_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT version FROM {_TABLE} ORDER BY version_id").fetchall()
    return [r["version"] for r in rows]

def get_latest_version() -> str:
    """
    Convenience shortcut → always the row where ``version_id = 0``.
    """
    _upsert(_fetch_versions())        # keep table fresh
    with sqlite3.connect(_DB) as conn:
        row = conn.execute(f"SELECT version FROM {_TABLE} WHERE version_id = 0").fetchone()
    if row is None:
        raise RuntimeError("Tabla 'versions' vacía o corrupta.")
    return row["version"]

# --------------------------------------------------------------------------- #
# CLI / debug                                                                 #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    print(f"🌟 Última versión Riot: {get_latest_version()}")
