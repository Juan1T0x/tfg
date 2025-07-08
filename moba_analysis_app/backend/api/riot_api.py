#!/usr/bin/env python3
# api/riot.py
# -----------------------------------------------------------------------------
# Public REST interface to Riot Games’ Data Dragon (versions, champions, art).
#
# The router is intentionally thin: every expensive or blocking task is
# executed in a background thread via ``asyncio.to_thread``.  All network
# errors coming from Riot’s CDN are converted to **502 Bad Gateway** so
# clients can easily distinguish between *our* failures and upstream issues.
# -----------------------------------------------------------------------------
from __future__ import annotations

import asyncio
from typing import List

import requests
from fastapi import APIRouter, HTTPException, status

# ───────────────────────── Local services ──────────────────────────
from services.riot_api.riot_versions import (
    fetch_versions,
    get_latest_version,
    get_versions,
    save_versions,
)
from services.riot_api.riot_champions_images import (
    champion_images_urls,
    download_all_images,
    list_icons_urls,
    list_loading_urls,
    list_splash_urls,
)
from services.riot_api.riot_champions_info import (
    champions_with_roles,
    get_champion_names,
    get_champion_names_and_classes,
    get_champions,
    roles_of_champion,
    update_champions_db,
)

router = APIRouter(prefix="/api/riot", tags=["riot"])

# =============================================================================
# Helper utilities
# =============================================================================
def _http_error(exc: requests.HTTPError) -> HTTPException:
    """
    Convert a ``requests.HTTPError`` (usually raised while accessing the Riot
    CDN) into *502 Bad Gateway*.  The original response text is preserved in
    ``detail`` for debugging.
    """
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Riot CDN error: {exc}",
    )

# =============================================================================
# Version endpoints
# =============================================================================
@router.get(
    "/versions",
    summary="List every Data Dragon patch (most-recent first)",
)
async def versions() -> dict:
    """
    Return **all** available patch identifiers in the exact order provided by
    Riot (index 0 → most recent).  Makes sure the local cache is up-to-date.
    """
    try:
        ver = await asyncio.to_thread(get_versions)
    except requests.HTTPError as exc:     # pragma: no cover
        raise _http_error(exc) from exc

    return {"versions": ver, "status": "ok"}


@router.post(
    "/versions/update",
    summary="Refresh the *versions* table only",
)
async def update_versions():
    """
    Pull the latest ``versions.json`` from the CDN and upsert the *versions*
    table.  The endpoint is idempotent.
    """
    try:
        vers = await asyncio.to_thread(fetch_versions)
        added = await asyncio.to_thread(save_versions, vers)
    except requests.HTTPError as exc:     # pragma: no cover
        raise _http_error(exc) from exc

    return {
        "latest_version": vers[0],
        "versions_added": added,
        "status": "ok",
    }

# =============================================================================
# Champion metadata
# =============================================================================
@router.get(
    "/champions",
    summary="Full champions table with stats",
)
async def champions():
    """
    Return one big list of dictionaries – each dictionary is a full DB row
    (stats + roles).  The local DB is refreshed if needed.
    """
    try:
        ver = await asyncio.to_thread(get_latest_version)
        data = await asyncio.to_thread(get_champions, ver)
    except requests.HTTPError as exc:
        raise _http_error(exc) from exc

    return {"version_used": ver, "champions": data}


@router.get(
    "/champions/names",
    summary="Alphabetical list of champion names",
)
async def champion_names():
    try:
        ver = await asyncio.to_thread(get_latest_version)
        names = await asyncio.to_thread(get_champion_names, ver)
    except requests.HTTPError as exc:
        raise _http_error(exc) from exc

    return {"version_used": ver, "champion_names": names}


@router.get(
    "/champions/names_and_classes",
    summary="Name + raw *roles* column for every champion",
)
async def champion_names_and_classes():
    try:
        ver = await asyncio.to_thread(get_latest_version)
        data = await asyncio.to_thread(get_champion_names_and_classes, ver)
    except requests.HTTPError as exc:
        raise _http_error(exc) from exc

    return {"version_used": ver, "champions": data}


@router.get(
    "/champions/{champion_name}/roles",
    summary="Retrieve the *roles* string of one champion",
)
async def champion_roles(champion_name: str):
    try:
        ver = await asyncio.to_thread(get_latest_version)
        roles = await asyncio.to_thread(roles_of_champion, champion_name, ver)
    except requests.HTTPError as exc:
        raise _http_error(exc) from exc

    if roles is None:
        raise HTTPException(404, f"Champion '{champion_name}' not found")

    return {
        "version_used": ver,
        "champion": champion_name,
        "roles": roles,
        "status": "ok",
    }


@router.get(
    "/champions/by_roles",
    summary="Champions whose *roles* column matches exactly",
)
async def champions_by_roles(roles: str):
    """
    ``roles`` **must** follow Riot’s exact syntax, e.g. ``Fighter`` or
    ``Marksman, Mage``.
    """
    try:
        ver = await asyncio.to_thread(get_latest_version)
        champs = await asyncio.to_thread(champions_with_roles, roles, ver)
    except requests.HTTPError as exc:
        raise _http_error(exc) from exc

    return {
        "version_used": ver,
        "roles_query": roles,
        "champions": champs,
        "status": "ok",
    }


@router.post(
    "/champions/update",
    summary="Refresh only the champions table (stats, roles)",
)
async def update_champions_info():
    try:
        ver = await asyncio.to_thread(get_latest_version)
        rows = await asyncio.to_thread(update_champions_db, ver)
    except requests.HTTPError as exc:
        raise _http_error(exc) from exc

    return {"version_used": ver, "champions_rows": rows, "status": "ok"}

# =============================================================================
# Images
# =============================================================================
@router.get("/images/icons", summary="All icon URLs")
async def images_icons():
    return {"icons": list_icons_urls(), "status": "ok"}


@router.get("/images/splash_arts", summary="All splash-art URLs")
async def images_splash():
    return {"splash_arts": list_splash_urls(), "status": "ok"}


@router.get("/images/loading_screens", summary="All loading-screen URLs")
async def images_loading():
    return {"loading_screens": list_loading_urls(), "status": "ok"}


@router.get("/images/{champion_key}", summary="3-pack images of one champion")
async def images_by_champion(champion_key: str):
    """
    ``champion_key`` is the *internal* Riot key used in filenames  
    (e.g. **Aatrox**, **DrMundo**, **KhaZix**).
    """
    try:
        data = champion_images_urls(champion_key)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {**data, "status": "ok"}


@router.post(
    "/images/update",
    summary="Download / refresh champion art only",
)
async def update_champions_images():
    try:
        ver = await asyncio.to_thread(get_latest_version)
        downloaded = await asyncio.to_thread(download_all_images, ver)
    except requests.HTTPError as exc:
        raise _http_error(exc) from exc

    return {
        "version_used": ver,
        "images_downloaded": downloaded,
        "status": "ok",
    }

# =============================================================================
# Composite endpoint – keep everything in sync
# =============================================================================
@router.post(
    "/database/update",
    summary="One-stop shop: versions + images + champions info",
)
async def update_database():
    """
    Convenience endpoint for maintaining the **entire** local Riot cache in one
    call – useful for scheduled jobs.
    """
    try:
        # 1) refresh versions
        vers = await asyncio.to_thread(fetch_versions)
        vers_added = await asyncio.to_thread(save_versions, vers)
        latest = vers[0]

        # 2) (re)download art
        imgs_downloaded = await asyncio.to_thread(download_all_images, latest)

        # 3) refresh champion stats
        champ_rows = await asyncio.to_thread(update_champions_db, latest)

    except requests.HTTPError as exc:      # pragma: no cover
        raise _http_error(exc) from exc
    except Exception as exc:              # pragma: no cover
        raise HTTPException(500, detail=str(exc)) from exc

    return {
        "latest_version": latest,
        "versions_added": vers_added,
        "images_downloaded": imgs_downloaded,
        "champions_rows": champ_rows,
        "status": "ok",
    }
