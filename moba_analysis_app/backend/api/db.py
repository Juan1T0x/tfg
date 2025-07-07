from fastapi import APIRouter, HTTPException
import asyncio
from services.db_utils import export_full_db, export_table

router = APIRouter(prefix="/api/database", tags=["database"])

VALID_TABLES = {"versions", "champions", "leaguepedia_games"}

@router.get("")
async def get_full_database():
    """Todas las tablas a JSON."""
    return await asyncio.to_thread(export_full_db)

@router.get("/{table_name}")
async def get_single_table(table_name: str):
    if table_name not in VALID_TABLES:
        raise HTTPException(status_code=404, detail="Tabla no encontrada")
    rows = await asyncio.to_thread(export_table, table_name)
    return {table_name: rows}
