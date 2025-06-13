# api/riot.py
from fastapi import APIRouter, HTTPException, status
import asyncio, requests

from services.riot_api.riot_versions import (
    get_latest_version,
    fetch_versions,
    save_versions,
    get_versions
)
from services.riot_api.riot_champions_images import download_all_images
from services.riot_api.riot_champions_info import (
    update_champions_db,
    get_champion_names,
    get_champion_names_and_classes
)

router = APIRouter(prefix="/api/riot", tags=["riot"])


# ──────────────────────── helpers comunes ───────────────────────
def _http_error(e: requests.HTTPError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Riot CDN error: {e}",
    )

# ────────────────────────── ENDPOINTS ───────────────────────────

# ────────────────────────── VERSIONS ───────────────────────────
@router.get("/versions")
async def versions():
    """
    Devuelve la lista completa de versiones en orden Riot
    (posición 0 = más reciente).
    """
    try:
        versions = await asyncio.to_thread(get_versions)
    except requests.HTTPError as e:
        raise _http_error(e) from e
    return {"versions": versions, "status": "ok"}

@router.post("/versions/update")
async def update_versions():
    """Actualiza solo la tabla versions."""
    try:
        versions = await asyncio.to_thread(fetch_versions)
        added = await asyncio.to_thread(save_versions, versions)
    except requests.HTTPError as e:
        raise _http_error(e) from e
    latest = versions[0]
    return {
        "latest_version": latest,
        "versions_added": added,
        "status": "ok",
    }

# ────────────────────────── CHAMPIONS ───────────────────────────

@router.get("/champions/names")
async def champion_names():
    """
    Devuelve una lista alfabética con todos los nombres de campeones.
    La función actualiza antes la tabla champions si fuera necesario.
    """
    try:
        version = await asyncio.to_thread(get_latest_version)
        names = await asyncio.to_thread(get_champion_names, version)
    except requests.HTTPError as e:
        raise _http_error(e) from e
    return {"version_used": version, "champion_names": names}

@router.get("/champions/names_and_classes")
async def champion_names_and_classes():
    """
    Devuelve una lista [(name, roles), …] ordenada alfabéticamente.
    `roles` es el contenido literal de la columna `roles`
    (por ejemplo 'Mage, Assassin').
    """
    try:
        version = await asyncio.to_thread(get_latest_version)
        data = await asyncio.to_thread(get_champion_names_and_classes, version)
    except requests.HTTPError as e:
        raise _http_error(e) from e
    return {"version_used": version, "champions": data}

@router.post("/champions/update")
async def update_champions_info():
    """Actualiza solo la tabla champions (stats, roles…)."""
    try:
        version = await asyncio.to_thread(get_latest_version)
        rows = await asyncio.to_thread(update_champions_db, version)
    except requests.HTTPError as e:
        raise _http_error(e) from e
    return {
        "version_used": version,
        "champions_rows": rows,
        "status": "ok",
    }


# ────────────────────────── IMAGES ───────────────────────────

@router.post("/images/update")
async def update_champions_images():
    """Actualiza / descarga solo las imágenes de campeones."""
    try:
        version = await asyncio.to_thread(get_latest_version)
        downloaded = await asyncio.to_thread(download_all_images, version)
    except requests.HTTPError as e:
        raise _http_error(e) from e
    return {
        "version_used": version,
        "images_downloaded": downloaded,
        "status": "ok",
    }

# ────────────────────────── DATABASE ───────────────────────────

@router.post("/database/update")
async def update_database():
    """
    Endpoint compuesto: ejecuta los tres anteriores
    (versions + images + champions info).
    """
    try:
        # 1) versions
        versions = await asyncio.to_thread(fetch_versions)
        versions_added = await asyncio.to_thread(save_versions, versions)
        latest = versions[0]

        # 2) imágenes
        images_downloaded = await asyncio.to_thread(download_all_images, latest)

        # 3) champions info
        champions_rows = await asyncio.to_thread(update_champions_db, latest)

    except requests.HTTPError as e:
        raise _http_error(e) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {
        "latest_version": latest,
        "versions_added": versions_added,
        "images_downloaded": images_downloaded,
        "champions_rows": champions_rows,
        "status": "ok",
    }


