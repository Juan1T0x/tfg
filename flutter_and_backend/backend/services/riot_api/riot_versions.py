# services/riot_api/riot_versions.py
"""
Tabla **versions** con el mismo índice que Riot:
    ┌───────────┬─────────┐
    │ version_id│ version │
    ├───────────┼─────────┤
    │     0     │ 14.12.1 │  ← más reciente
    │     1     │ 14.11.1 │
    │     2     │ 14.10.1 │
    │    ...    │  ...    │
    └───────────┴─────────┘
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

import requests

URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DB_OUT = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "db"
    / "moba_analysis.sqlite"
)
TABLE = "versions"


# ───────────────── helpers ──────────────────
def fetch_versions() -> List[str]:
    """Lista completa, ordenada de **más nueva a más antigua**."""
    return requests.get(URL, timeout=15).json()


def save_versions(versions: List[str]) -> int:
    """
    Inserta/actualiza todas las versiones con su índice original:
    id 0 = versión más reciente.
    Devuelve cuántas filas nuevas se añadieron o se actualizaron.
    """
    with sqlite3.connect(DB_OUT) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                version_id INTEGER PRIMARY KEY,
                version    TEXT UNIQUE
            )
            """
        )

        # Construimos tuples (id, version)
        tuples = [(idx, v) for idx, v in enumerate(versions)]

        sql = (
            f"INSERT INTO {TABLE}(version_id, version) "
            f"VALUES (?, ?) "
            f"ON CONFLICT(version)    DO UPDATE SET version_id = excluded.version_id "
            f"ON CONFLICT(version_id) DO UPDATE SET version    = excluded.version"
        )

        before = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
        conn.executemany(sql, tuples)
        after = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]

    changed = after - before
    print(
        "✔ Versiones añadidas/actualizadas" if changed else "✔ Tabla versions ya al día.",
        changed if changed else "",
    )
    return changed


def get_versions() -> List[str]:
    """
    Asegura que la tabla esté actualizada y devuelve **todas** las versiones
    en el mismo orden que el JSON de Riot (id 0 → más reciente).
    """
    versions = fetch_versions()          # puede lanzar HTTPError
    save_versions(versions)              # inserta/actualiza

    with sqlite3.connect(DB_OUT) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT version FROM {TABLE} ORDER BY version_id ASC"
        ).fetchall()

    return [r["version"] for r in rows]

def get_latest_version() -> str:
    """Actualiza la tabla y devuelve la versión con `version_id = 0`."""
    versions = fetch_versions()
    save_versions(versions)

    with sqlite3.connect(DB_OUT) as conn:
        row = conn.execute(
            f"SELECT version FROM {TABLE} WHERE version_id = 0 LIMIT 1"
        ).fetchone()

    if not row:
        raise RuntimeError("No se encontró ninguna versión en la base de datos.")
    return row[0]


# ─────────── CLI/debug ───────────
if __name__ == "__main__":
    print(f"🌟 Última versión Riot: {get_latest_version()}")
