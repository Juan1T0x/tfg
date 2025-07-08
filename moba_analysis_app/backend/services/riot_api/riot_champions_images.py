#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services.riot_api.riot_champions_images
---------------------------------------

Handles local storage and HTTP exposure of Riot-provided artwork
(champion square icons, loading screens, and splash arts).

A *single* public helper – :meth:`download_all_images` – downloads and
updates the full library for a given Data-Dragon version:

>>> from services.riot_api.riot_champions_images import (
...     download_all_images, get_latest_version)
>>> download_all_images(get_latest_version())
✔ Descargadas 402 nuevas imágenes.

The rest of the helpers simply return absolute paths or fully-qualified
URLs to the stored assets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from .riot_versions import get_latest_version

# --------------------------------------------------------------------------- #
# Local paths                                                                 #
# --------------------------------------------------------------------------- #
_ASSETS_DIR: Path = Path(__file__).resolve().parents[2] / "assets" / "images"
ICON_DIR:     Path = _ASSETS_DIR / "icons"
SPLASH_DIR:   Path = _ASSETS_DIR / "splash_arts"
LOADING_DIR:  Path = _ASSETS_DIR / "loading_screens"

for _p in (ICON_DIR, SPLASH_DIR, LOADING_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Download helpers                                                            #
# --------------------------------------------------------------------------- #
def _download(url: str, dest: Path) -> bool:
    """
    Download *url* into *dest* only if the file does **not** already exist.

    Returns ``True`` when a fresh download occurred, ``False`` otherwise.
    """
    if dest.exists():
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    dest.write_bytes(response.content)
    return True


def download_all_images(version: str) -> int:
    """
    Synchronise champion images for a given Data-Dragon *version*.

    Parameters
    ----------
    version :
        Riot's Data-Dragon version string (``13.21.1`` …).

    Returns
    -------
    int
        Number of files newly downloaded.
    """
    meta_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    champs   = requests.get(meta_url, timeout=15).json()["data"]

    downloaded = 0
    for name, info in champs.items():
        cid = info["id"]
        assets = {
            ICON_DIR   / f"{name}_icon.png"   : f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{cid}.png",
            SPLASH_DIR / f"{name}_splash.jpg" : f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{cid}_0.jpg",
            LOADING_DIR/ f"{name}_loading.jpg": f"https://ddragon.leagueoflegends.com/cdn/img/champion/loading/{cid}_0.jpg",
        }
        for path, url in assets.items():
            try:
                if _download(url, path):
                    downloaded += 1
            except Exception as exc:
                print(f"⚠️  {name}: {exc}")

    msg = "Biblioteca de imágenes ya al día." if downloaded == 0 else f"Descargadas {downloaded} nuevas imágenes."
    print(f"✔ {msg}")
    return downloaded

# --------------------------------------------------------------------------- #
# Absolute-path helpers                                                       #
# --------------------------------------------------------------------------- #
def get_icons_path() -> str        : return str(ICON_DIR.resolve())
def get_splash_arts_path() -> str  : return str(SPLASH_DIR.resolve())
def get_loading_screens_path() -> str: return str(LOADING_DIR.resolve())

# --------------------------------------------------------------------------- #
# URL helpers (FastAPI serves /static/… mounts)                               #
# --------------------------------------------------------------------------- #
_BASE_URL     = "http://localhost:8888"
_ICON_MOUNT   = "/static/icons"
_SPLASH_MOUNT = "/static/splash_arts"
_LOAD_MOUNT   = "/static/loading_screens"

def _folder_to_urls(folder: Path, mount: str) -> list[str]:
    return [f"{_BASE_URL}{mount}/{fp.name}" for fp in folder.iterdir() if fp.is_file()]

def list_icons_urls()   -> list[str]: return _folder_to_urls(ICON_DIR,   _ICON_MOUNT)
def list_splash_urls()  -> list[str]: return _folder_to_urls(SPLASH_DIR, _SPLASH_MOUNT)
def list_loading_urls() -> list[str]: return _folder_to_urls(LOADING_DIR, _LOAD_MOUNT)

def champion_images_urls(champion_key: str) -> dict[str, str]:
    """
    Return icon, splash-art and loading-screen URLs for *champion_key*.

    Raises
    ------
    FileNotFoundError
        If any of the three expected images is missing locally.
    """
    icon   = ICON_DIR   / f"{champion_key}_icon.png"
    splash = SPLASH_DIR / f"{champion_key}_splash.jpg"
    load   = LOADING_DIR/ f"{champion_key}_loading.jpg"

    for fp in (icon, splash, load):
        if not fp.exists():
            raise FileNotFoundError(
                f"{fp.name} no encontrado — el campeón “{champion_key}” no está descargado."
            )

    return {
        "champion"      : champion_key,
        "icon"          : f"{_BASE_URL}{_ICON_MOUNT}/{icon.name}",
        "splash_art"    : f"{_BASE_URL}{_SPLASH_MOUNT}/{splash.name}",
        "loading_screen": f"{_BASE_URL}{_LOAD_MOUNT}/{load.name}",
    }
