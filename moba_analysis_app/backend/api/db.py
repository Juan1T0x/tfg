#!/usr/bin/env python3
# api/database.py
# ---------------------------------------------------------------------------–
# Lightweight read-only API for the project SQLite database.
#
# End-points
# ----------
# • **GET /api/database**               → dump every non-internal table
# • **GET /api/database/{table_name}**  → dump a single *whitelisted* table
#
# The router is intentionally narrow: write operations are *not* exposed.
# ---------------------------------------------------------------------------–

from __future__ import annotations

import asyncio
from typing import Dict, List, Literal

from fastapi import APIRouter, HTTPException, Path

from services.db_utils import export_full_db, export_table

router = APIRouter(prefix="/api/database", tags=["database"])

#: Tables clients are allowed to request individually
VALID_TABLES: set[str] = {
    "versions",
    "champions",
    "leaguepedia_games",
}

# ---------------------------------------------------------------------------–
# Routes
# ---------------------------------------------------------------------------–
@router.get(
    "",
    summary="Dump the entire database",
    response_description="Dictionary where every key is a table name and the "
    "value is the list of rows (dicts).",
)
async def dump_full_database() -> Dict[str, List[Dict]]:
    """
    Return **all** user-facing tables in a single JSON payload.

    Internally runs :func:`services.db_utils.export_full_db`
    inside a thread-pool to avoid blocking the event-loop.
    """
    return await asyncio.to_thread(export_full_db)


@router.get(
    "/{table_name}",
    summary="Dump one table",
    response_description="Table content keyed by its name.",
)
async def dump_single_table(
    table_name: Literal["versions", "champions", "leaguepedia_games"] = Path(
        ..., description="Allowed values: versions / champions / leaguepedia_games"
    )
) -> Dict[str, List[Dict]]:
    """
    Return the full content of **one** table.

    The route is protected by a static whitelist – any attempt to access an
    unknown or internal table results in *404 Not Found*.
    """
    if table_name not in VALID_TABLES:
        raise HTTPException(status_code=404, detail="Table not found or not allowed.")

    rows = await asyncio.to_thread(export_table, table_name)
    return {table_name: rows}
