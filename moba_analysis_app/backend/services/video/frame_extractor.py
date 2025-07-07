# services/video/frame_extractor.py
"""
Extrae **un solo fotograma** de un vídeo online con yt-dlp + ffmpeg.

`extract_frame(url, t)`  ➜  Path al JPG creado en backend/frames
"""
from __future__ import annotations

import asyncio, hashlib, subprocess
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

# ────────────────────── rutas ──────────────────────
BASE_DIR   = Path(__file__).resolve().parents[2]        # …/backend
FRAMES_DIR = BASE_DIR / "frames"
COOKIES_TXT = Path(__file__).parent / "cookies.txt"
FRAMES_DIR.mkdir(exist_ok=True)

# ────────────────────── helper ─────────────────────
def _stream_url(url: str) -> str:
    """Resuelve la URL de streaming más alta disponible."""
    ydl_opts: dict[str, Any] = {"format": "bestvideo[ext=mp4]+bestaudio/best"}
    if COOKIES_TXT.exists():
        ydl_opts["cookiefile"] = str(COOKIES_TXT)

    info = YoutubeDL(ydl_opts).extract_info(url, download=False)
    if info.get("url"):                          # type: ignore[arg-type]
        return info["url"]                       # type: ignore[index]

    fmt = max(info["formats"], key=lambda f: f.get("height") or 0)
    return fmt["url"]                            # type: ignore[index]


# ────────────────────── API pública ─────────────────────
def extract_frame(url: str, time_pos: float) -> Path:
    """
    Descarga un único frame y lo guarda en *backend/frames*.
    Devuelve la **ruta absoluta** del .jpg resultante.
    """
    frame_name = hashlib.md5(f"{url}|{time_pos:.3f}".encode()).hexdigest() + ".jpg"
    frame_path = FRAMES_DIR / frame_name

    stream_url = _stream_url(url)
    cmd = [
        "ffmpeg",
        "-ss", str(time_pos),
        "-i",  stream_url,
        "-frames:v", "1",
        "-q:v", "2",
        "-y", str(frame_path),
    ]
    subprocess.run(cmd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return frame_path.resolve()


async def async_extract_frame(url: str, time_pos: float) -> Path:
    """Versión *async friendly* que usa `asyncio.to_thread`."""
    return await asyncio.to_thread(extract_frame, url, time_pos)
