import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "assets" / "db" / "moba_analysis.sqlite"

print (f"Using database at {DB_PATH}")

def export_full_db() -> dict:
    """Devuelve todas las tablas (excepto sqlite internas)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [r["name"] for r in cur.fetchall()]

        dump: dict[str, list[dict]] = {}
        for t in tables:
            cur.execute(f"SELECT * FROM {t}")
            dump[t] = [dict(r) for r in cur.fetchall()]
    return dump

def export_table(table: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table}")
        return [dict(r) for r in cur.fetchall()]
