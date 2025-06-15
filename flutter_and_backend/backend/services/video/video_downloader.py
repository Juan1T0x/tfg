"""
services/video/downloader.py
==============================
Descarga un vídeo de YouTube (u otras plataformas soportadas por yt-dlp)
en la carpeta  backend/videos  conservando el título del vídeo.
"""

from __future__ import annotations

import re, unicodedata, os
from pathlib import Path

from yt_dlp import YoutubeDL

# --- rutas / ficheros -------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parents[2]          # …/backend
VIDEOS_DIR = BASE_DIR / "videos"
VIDEOS_DIR.mkdir(exist_ok=True)

COOKIES_TXT = Path(__file__).parent / "cookies.txt"

# --- helpers ----------------------------------------------------------
_slug_re = re.compile(r"[^-\w]+")


def _slugify(value: str) -> str:
    """
    Convierte el título del vídeo a un nombre de archivo seguro.
    """
    value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    value = str(_slug_re.sub("-", value).strip("-").lower())
    return value[:120] or "video"


def download_video(url: str) -> Path:
    """
    Descarga el vídeo *url* en ``VIDEOS_DIR``.
    Devuelve la **ruta absoluta** del archivo mp4 resultante.
    Lanza excepción si falla algo.
    """
    # 1) primero obtenemos sólo la metadata para conocer el título
    meta_opts = {"skip_download": True, "quiet": True}
    if COOKIES_TXT.exists():
        meta_opts["cookiefile"] = str(COOKIES_TXT)

    with YoutubeDL(meta_opts) as tmp_ydl:
        info = tmp_ydl.extract_info(url, download=False)
        title = info.get("title") or "video"

    filename = _slugify(title) + ".%(ext)s"
    outtmpl  = str(VIDEOS_DIR / filename)

    # 2) opciones definitivas de descarga
    ydl_opts = {
        "outtmpl":      outtmpl,
        "merge_output_format": "mp4",
        "format":       "bestvideo+bestaudio/best",
        "noplaylist":   True,
        "cookiefile":   str(COOKIES_TXT) if COOKIES_TXT.exists() else None,
        "quiet":        True,
    }

    with YoutubeDL({k: v for k, v in ydl_opts.items() if v is not None}) as ydl:
        ydl.download([url])

    # yt-dlp rellena %(ext)s → normalmente “.mp4”
    final_file = next(VIDEOS_DIR.glob(_slugify(title) + ".*"))
    return final_file.resolve()
