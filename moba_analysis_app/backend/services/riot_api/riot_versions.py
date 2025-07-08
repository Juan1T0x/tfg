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

# ─────────────────────────── Paths / constants ────────────────────────────
_URL   = "https://ddragon.leagueoflegends.com/api/versions.json"
_DB    = Path(__file__).resolve().parents[2] / "assets" / "db" / "moba_analysis.sqlite"
_TABLE = "versions"

# ───────────────────────────── DB helpers ─────────────────────────────────
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
    Insert **all** versions keeping both columns unique & in-sync.
    Return the net amount of *new* rows.
    """
    with sqlite3.connect(_DB) as conn:
        _create_table(conn)

        rows = [(idx, v) for idx, v in enumerate(versions)]
        sql  = (
            f"INSERT INTO {_TABLE}(version_id, version) VALUES (?, ?) "
            f"ON CONFLICT(version)    DO UPDATE SET version_id = excluded.version_id "
            f"ON CONFLICT(version_id) DO UPDATE SET version    = excluded.version"
        )

        before = conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]
        conn.executemany(sql, rows)
        after  = conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]

    return after - before

# ───────────────────────────── Public API ────────────────────────────────
def fetch_versions() -> List[str]:
    """
    Pull the *raw* JSON list from the Riot CDN (newest → oldest).  Network
    errors propagate as :class:`requests.HTTPError`.
    """
    r = requests.get(_URL, timeout=15)
    r.raise_for_status()
    return r.json()

def get_versions() -> List[str]:
    """
    Return the full patch list after refreshing the local cache.
    """
    inserted = _upsert(fetch_versions())
    if inserted:
        print(f"✔ Versions inserted/updated: {inserted}")

    with sqlite3.connect(_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT version FROM {_TABLE} ORDER BY version_id"
        ).fetchall()

    return [r["version"] for r in rows]

def get_latest_version() -> str:
    """
    Convenience helper ⇒ value where ``version_id = 0`` (always the newest).
    """
    _upsert(fetch_versions())  # keep cache fresh
    with sqlite3.connect(_DB) as conn:
        row = conn.execute(
            f"SELECT version FROM {_TABLE} WHERE version_id = 0"
        ).fetchone()

    if row is None:
        raise RuntimeError("Table 'versions' is empty or corrupt.")

    return row["version"]

def save_versions(versions: List[str]) -> int:
    """
    Upsert an *already-downloaded* list of patch strings into the DB.

    Parameters
    ----------
    versions : list[str]
        The exact array returned by Riot’s versions.json (newest → oldest).

    Returns
    -------
    int
        Net number of **new** rows inserted (same semantics as `_upsert`).
    """
    return _upsert(versions)

# ───────────────────────────── CLI / debug ───────────────────────────────
if __name__ == "__main__":
    print(f"🌟 Latest Riot patch: {get_latest_version()}")