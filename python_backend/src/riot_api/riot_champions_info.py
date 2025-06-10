#!/usr/bin/env python3
# riot_champions_info.py  – Excel + SQLite (sin conflicto de nombres)

import requests
import pandas as pd
import sqlite3
from pathlib import Path

from riot_versions import get_latest_version  # importa la versión actualizada

DB_OUT    = Path(__file__).resolve().parents[1] / "database" / "moba_analysis.sqlite"
EXCEL_OUT = Path("champions_info.xlsx")
TABLE     = "champions"

def fetch_dataframe(version: str) -> pd.DataFrame:
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    champs = r.json()["data"]

    rows = []
    for c in champs.values():
        rows.append({
            "champion_id"  : int(c["key"]),
            "champion_name": c["name"],
            "roles"        : ", ".join(c["tags"]),
            **c["stats"],
        })

    df = pd.DataFrame(rows).sort_values("champion_name")
    return df

def save_excel(df: pd.DataFrame) -> None:
    df.to_excel(EXCEL_OUT, index=False)
    print(f"✔ Excel guardado en {EXCEL_OUT.resolve()}")

def save_sqlite(df: pd.DataFrame) -> None:
    with sqlite3.connect(DB_OUT) as conn:
        df.to_sql(
            TABLE,
            conn,
            if_exists="replace",
            index=False,
            dtype={
                "champion_id":  "INTEGER PRIMARY KEY",
                "champion_name":"TEXT",
                "roles":        "TEXT",
            },
        )
    print(f"✔ Base de datos SQLite guardada en {DB_OUT.resolve()}")

def main() -> None:
    version = get_latest_version()
    print(f"🌍 Usando versión de Riot: {version}")

    df = fetch_dataframe(version)
    save_excel(df)
    save_sqlite(df)

if __name__ == "__main__":
    main()
