#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_utils.py
=============

Utility helpers to **read-only** export data from the project database
(`assets/db/moba_analysis.sqlite`).  
Two levels of granularity are offered:

* :pyfunc:`export_full_db` – dump the content of *every* user table into a
  dictionary of lists (``{table_name: [row, …]}``).

* :pyfunc:`export_table` – fetch all rows from a single table as a list of
  dictionaries.

Both helpers open a *separate* connection and close it immediately after the
query, making them safe for concurrent use inside an async web server.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List

# --------------------------------------------------------------------------- #
# Database location
# --------------------------------------------------------------------------- #
DB_PATH: Path = (
    Path(__file__).resolve()
    .parents[1] / "assets" / "db" / "moba_analysis.sqlite"
)
print(f"Using database at {DB_PATH}")   # visible feedback on startup


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #
def export_full_db() -> Dict[str, List[Dict]]:
    """
    Return the complete contents of the database except for SQLite’s internal
    tables (``sqlite_*``).

    The result is a mapping ``{table_name: [row_dict, …]}``, where each
    *row_dict* maps column names to Python values.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        )
        tables = [row["name"] for row in cur.fetchall()]

        dump: Dict[str, List[Dict]] = {}
        for table in tables:
            cur.execute(f"SELECT * FROM {table}")
            dump[table] = [dict(r) for r in cur.fetchall()]

    return dump


def export_table(table: str) -> List[Dict]:
    """
    Fetch **all** rows from *table* and return them as a list of dictionaries.

    Parameters
    ----------
    table :
        Name of the table to export.  No quoting or validation is performed, so
        only call this helper with trusted table names.

    Raises
    ------
    sqlite3.OperationalError
        If the table does not exist.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table}")
        return [dict(r) for r in cur.fetchall()]
