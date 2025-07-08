#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services.riot_api.riot_champions_info
-------------------------------------

Keeps table **champions** inside *assets/db/moba_analysis.sqlite*
fully-synced with the latest Data-Dragon metadata.

Main entry-point
~~~~~~~~~~~~~~~~
>>> from services.riot_api.riot_champions_info import update_champions_db
>>> update_champions_db("14.6.1")      # returns number of rows touched
402

Public helpers
~~~~~~~~~~~~~~
* :func:`get_champion_names`
* :func:`get_champion_names_and_classes`
* :func:`get_champions`
* :func:`roles_of_champion`
* :func:`champions_with_roles`
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, List, Tuple

import numpy as np
import pandas as pd
import requests

from .riot_versions import get_latest_version

# --------------------------------------------------------------------------- #
# Database path / constants                                                   #
# --------------------------------------------------------------------------- #
_DB: Path   = Path(__file__).resolve().parents[2] / "assets" / "db" / "moba_analysis.sqlite"
_TABLE: str = "champions"

# --------------------------------------------------------------------------- #
# Data-Dragon fetch / pre-processing                                          #
# --------------------------------------------------------------------------- #
def _fetch_dataframe(version: str) -> pd.DataFrame:
    """
    Download champion JSON for *version* and return a tidy :class:`pandas.DataFrame`.
    """
    url  = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    data = requests.get(url, timeout=15).json()["data"]

    rows: list[dict[str, Any]] = []
    for champ in data.values():
        rows.append(
            {
                "champion_id"  : int(champ["key"]),
                "champion_name": champ["name"],
                "roles"        : ", ".join(champ["tags"]),
                **champ["stats"],
            }
        )
    return pd.DataFrame(rows).sort_values("champion_name")

# --------------------------------------------------------------------------- #
# Table creation / UPSERT                                                     #
# --------------------------------------------------------------------------- #
def _create_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            champion_id            INTEGER PRIMARY KEY,
            champion_name          TEXT,
            roles                  TEXT,
            hp                     REAL,
            hpperlevel             REAL,
            mp                     REAL,
            mpperlevel             REAL,
            movespeed              REAL,
            armor                  REAL,
            armorperlevel          REAL,
            spellblock             REAL,
            spellblockperlevel     REAL,
            attackrange            REAL,
            hpregen                REAL,
            hpregenperlevel        REAL,
            mpregen                REAL,
            mpregenperlevel        REAL,
            crit                   REAL,
            critperlevel           REAL,
            attackdamage           REAL,
            attackdamageperlevel   REAL,
            attackspeedperlevel    REAL,
            attackspeed            REAL
        )
        """
    )

def _py(v: Any) -> Any:
    """Convert Numpy scalars to plain Python for SQLite."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v

def _upsert(df: pd.DataFrame) -> int:
    with sqlite3.connect(_DB) as conn:
        _create_table(conn)

        cols         = df.columns.tolist()
        placeholders = ", ".join("?" * len(cols))
        updates      = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "champion_id")

        sql = (
            f"INSERT INTO {_TABLE} ({', '.join(cols)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(champion_id) DO UPDATE SET {updates}"
        )

        before = conn.total_changes
        rows   = [tuple(_py(v) for v in r) for r in df.itertuples(index=False, name=None)]
        conn.executemany(sql, rows)
        conn.commit()

        return conn.total_changes - before

# --------------------------------------------------------------------------- #
# Public sync helper                                                          #
# --------------------------------------------------------------------------- #
def update_champions_db(version: str | None = None) -> int:
    """
    Ensure table **champions** is up-to-date.

    Parameters
    ----------
    version :
        Data-Dragon version.  When *None*, latest live version is resolved.

    Returns
    -------
    int
        Number of rows inserted or updated.
    """
    if version is None:
        version = get_latest_version()
    df = _fetch_dataframe(version)
    changed = _upsert(df)

    msg = "Tabla champions ya al día." if changed == 0 else f"Champions insertados/actualizados: {changed}"
    print(f"✔ {msg}")
    return changed

# --------------------------------------------------------------------------- #
# Read helpers                                                                #
# --------------------------------------------------------------------------- #
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def get_champion_names(version: str | None = None) -> List[str]:
    update_champions_db(version)
    with _conn() as c:
        rows = c.execute(f"SELECT champion_name FROM {_TABLE} ORDER BY champion_name").fetchall()
    return [r["champion_name"] for r in rows]

def get_champion_names_and_classes(version: str | None = None) -> List[Tuple[str, str]]:
    update_champions_db(version)
    with _conn() as c:
        rows = c.execute(f"SELECT champion_name, roles FROM {_TABLE} ORDER BY champion_name").fetchall()
    return [(r["champion_name"], r["roles"]) for r in rows]

def get_champions(version: str | None = None) -> List[dict]:
    update_champions_db(version)
    with _conn() as c:
        rows = c.execute(f"SELECT * FROM {_TABLE}").fetchall()
    return [dict(r) for r in rows]

def roles_of_champion(name: str, version: str | None = None) -> str | None:
    update_champions_db(version)
    with _conn() as c:
        row = c.execute(
            f"SELECT roles FROM {_TABLE} WHERE lower(champion_name)=lower(?) LIMIT 1",
            (name,),
        ).fetchone()
    return None if row is None else row["roles"]

# --------------------------------------------------------------------------- #
# Role-lookup helper                                                          #
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKD", s)).lower()

def champions_with_roles(roles_query: str, version: str | None = None) -> List[str]:
    """
    Exact‐match search on the *roles* column.

    Examples
    --------
    >>> champions_with_roles("Fighter")
    >>> champions_with_roles("Marksman, Mage")
    """
    rq = _norm(roles_query)
    update_champions_db(version)

    with _conn() as c:
        rows = c.execute(f"SELECT champion_name, roles FROM {_TABLE}").fetchall()

    return [r["champion_name"] for r in rows if _norm(r["roles"]) == rq]

# --------------------------------------------------------------------------- #
# CLI / debug                                                                 #
# --------------------------------------------------------------------------- #
def main() -> None:
    version = get_latest_version()
    print(f"🌍 Versión Riot más reciente: {version}")
    changed = update_champions_db(version)
    print(f"✔ Champions insertados/actualizados: {changed}")

if __name__ == "__main__":
    main()
