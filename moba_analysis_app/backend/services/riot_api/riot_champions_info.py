# services/riot_api/riot_champions_info.py
"""
Actualiza la tabla **champions** con la última información de Riot.
• Tabla: champions(champion_id PK, champion_name, roles, …stats)
• Ruta : backend/assets/db/moba_analysis.sqlite
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, List, Tuple

import numpy as np
import pandas as pd
import requests

from .riot_versions import get_latest_version

DB_OUT = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "db"
    / "moba_analysis.sqlite"
)
TABLE = "champions"


# ─────────────────── descarga y pre-procesado ──────────────────
def fetch_dataframe(version: str) -> pd.DataFrame:
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    champs = requests.get(url, timeout=15).json()["data"]

    rows: list[dict[str, Any]] = []
    for c in champs.values():
        rows.append(
            {
                "champion_id": int(c["key"]),
                "champion_name": c["name"],
                "roles": ", ".join(c["tags"]),
                **c["stats"],
            }
        )
    return pd.DataFrame(rows).sort_values("champion_name")


# ─────────────────────── tabla y UPSERT ────────────────────────
def _create_table_if_needed(conn: sqlite3.Connection) -> None:
    """Crea la tabla si no existe (solo se llama una vez)."""
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            champion_id   INTEGER PRIMARY KEY,
            champion_name TEXT,
            roles         TEXT,
            hp            REAL,
            hpperlevel    REAL,
            mp            REAL,
            mpperlevel    REAL,
            movespeed     REAL,
            armor         REAL,
            armorperlevel REAL,
            spellblock    REAL,
            spellblockperlevel REAL,
            attackrange   REAL,
            hpregen       REAL,
            hpregenperlevel REAL,
            mpregen       REAL,
            mpregenperlevel REAL,
            crit          REAL,
            critperlevel  REAL,
            attackdamage  REAL,
            attackdamageperlevel REAL,
            attackspeedperlevel REAL,
            attackspeed   REAL
        )
        """
    )


def _py_cast(x: Any) -> Any:
    """Convierte numpy types a nativos Python para SQLite."""
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    return x


def upsert_sqlite(df: pd.DataFrame) -> int:
    with sqlite3.connect(DB_OUT) as conn:
        _create_table_if_needed(conn)

        cols = df.columns.tolist()
        placeholders = ", ".join("?" * len(cols))
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "champion_id")

        sql = (
            f"INSERT INTO {TABLE} ({', '.join(cols)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(champion_id) DO UPDATE SET {updates}"
        )

        before = conn.total_changes
        tuples = [
            tuple(_py_cast(v) for v in row)
            for row in df.itertuples(index=False, name=None)
        ]
        conn.executemany(sql, tuples)
        conn.commit()
        changed = conn.total_changes - before          # filas realmente afectadas

    if changed:
        print(f"✔ Champions insertados/actualizados: {changed}")
    else:
        print("✔ Tabla champions ya al día.")
    return changed


# ──────────────────────── API helper ───────────────────────────
def update_champions_db(version: str) -> int:
    """Descarga la info y realiza upsert; devuelve nº de filas procesadas."""
    df = fetch_dataframe(version)
    return upsert_sqlite(df)

# ────────────────────────── CONSULTAS ──────────────────────────
def _open_conn() -> sqlite3.Connection:
    
    """Conexión helper en modo row dict + foreign keys."""
    conn = sqlite3.connect(DB_OUT)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_champion_names(version: str) -> List[str]:

    # Primero actualizamos la tabla con la última info.
    update_champions_db(version)

    """
    Devuelve TODOS los nombres (orden alfabético) existentes en la tabla.
    """
    with _open_conn() as conn:
        rows = conn.execute(
            f"SELECT champion_name FROM {TABLE} ORDER BY champion_name ASC"
        ).fetchall()
    return [r["champion_name"] for r in rows]


def get_champion_names_and_classes(version: str) -> List[Tuple[str, str]]:


    # Primero actualizamos la tabla con la última info.
    update_champions_db(version)

    """
    Devuelve [(name, roles), …] ordenados alfabéticamente.
    `roles` es el contenido literal de la columna `roles`
    (p.ej. 'Mage, Assassin').
    """
    with _open_conn() as conn:
        rows = conn.execute(
            f"SELECT champion_name, roles FROM {TABLE} ORDER BY champion_name ASC"
        ).fetchall()
    return [(r["champion_name"], r["roles"]) for r in rows]

def get_champions(version: str) -> List[dict]:
    """
    Devuelve TODA la tabla champions como lista de dicts
    (se asegura antes de que esté actualizada).
    """
    update_champions_db(version)                # refresca si es necesario
    with _open_conn() as conn:
        rows = conn.execute(f"SELECT * FROM {TABLE}").fetchall()
    return [dict(r) for r in rows]

def roles_of_champion(champion_name: str, version: str) -> str | None:
    """
    Devuelve la cadena `roles` del campeón indicado (p.ej. "Mage, Assassin").
    Si no existe, retorna **None**.
    """
    update_champions_db(version)
    with _open_conn() as conn:
        row = conn.execute(
            f"""
            SELECT roles
              FROM {TABLE}
             WHERE lower(champion_name)=lower(?)
             LIMIT 1
            """,
            (champion_name,),
        ).fetchone()
    return None if row is None else row["roles"]

def _normalize(s: str) -> str:
    """Lower-case y sin espacios para comparaciones robustas."""
    return s.replace(" ", "").lower()

def champions_with_roles(
    roles_query: str,
    version: str,
) -> List[str]:
    """
    Devuelve los nombres de campeones cuyo campo **roles**
    coincide *exactamente* con `roles_query` (misma secuencia).

    • `roles_query` debe ir con la misma notación que Riot:
         "Fighter"              → sólo los de 1 rol Fighter
         "Marksman, Mage"       → exactamente esos dos y en ese orden
    """
    roles_query_norm = _normalize(roles_query)
    update_champions_db(version)

    with _open_conn() as conn:
        rows = conn.execute(f"SELECT champion_name, roles FROM {TABLE}").fetchall()

    return [
        r["champion_name"]
        for r in rows
        if _normalize(r["roles"]) == roles_query_norm
    ]


# ───────────────────────── CLI/debug ───────────────────────────
def main() -> None:
    version = get_latest_version()
    print(f"🌍 Última versión Riot: {version}")

    rows = update_champions_db(version)
    print(f"✔ Champions actualizados/insertados: {rows}")


if __name__ == "__main__":
    main()
