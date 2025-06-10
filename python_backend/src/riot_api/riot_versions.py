import requests
import pandas as pd
import sqlite3
from pathlib import Path

URL          = "https://ddragon.leagueoflegends.com/api/versions.json"
DB_OUT       = Path(__file__).resolve().parents[1] / "database" / "moba_analysis.sqlite"
TABLE        = "versions"

def fetch_versions() -> pd.DataFrame:
    r = requests.get(URL, timeout=15)
    r.raise_for_status()
    versions = r.json()

    df = pd.DataFrame(versions, columns=["version"])
    df["version_id"] = df.index + 1  # ID incremental
    return df[["version_id", "version"]]

def save_versions(df: pd.DataFrame) -> None:
    with sqlite3.connect(DB_OUT) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                version_id INTEGER PRIMARY KEY,
                version TEXT UNIQUE
            )
        """)

        existing = pd.read_sql(f"SELECT version FROM {TABLE}", conn)
        new_versions = df[~df["version"].isin(existing["version"])]

        if not new_versions.empty:
            new_versions.to_sql(TABLE, conn, if_exists="append", index=False)
            print(f"✔ Añadidas {len(new_versions)} nuevas versiones.")
        else:
            print("✔ No hay nuevas versiones para añadir.")

def get_latest_version() -> str:
    df = fetch_versions()
    save_versions(df)
    
    with sqlite3.connect(DB_OUT) as conn:
        result = conn.execute(f"""
            SELECT version FROM {TABLE}
            ORDER BY version_id ASC LIMIT 1
        """).fetchone()
    
    if result:
        return result[0]
    raise RuntimeError("No se encontró ninguna versión en la base de datos.")

def main() -> None:
    latest = get_latest_version()
    print(f"🌟 Última versión: {latest}")

if __name__ == "__main__":
    main()