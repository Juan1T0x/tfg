# services/video/frame_extractor.py
from __future__ import annotations

import asyncio, hashlib, subprocess, tempfile
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL


BASE_DIR   = Path(__file__).resolve().parents[2]
FRAMES_DIR = BASE_DIR / "frames"
COOKIES_TXT = Path(__file__).parent / "cookies.txt"
FRAMES_DIR.mkdir(exist_ok=True)


def _best_stream_urls(url: str) -> tuple[str, str]:
    """
    Devuelve (video_only_url, progressive_url).
    progressive_url se usa como *plan B* si el primero da error 403.
    """
    ydl_opts: dict[str, Any] = {"quiet": True, "skip_download": True}
    if COOKIES_TXT.exists():
        ydl_opts["cookiefile"] = str(COOKIES_TXT)

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    video_only = [
        f for f in info["formats"]
        if f.get("vcodec") != "none" and f.get("acodec") == "none"
    ]
    progressive = [
        f for f in info["formats"]
        if f.get("vcodec") != "none" and f.get("acodec") != "none"
    ]
    if not progressive:
        raise RuntimeError("no hay streams progresivos disponibles")

    v_only_url = max(video_only, key=lambda f: f.get("height") or 0)["url"] if video_only else ""
    prog_url   = max(progressive, key=lambda f: f.get("height") or 0)["url"]
    return v_only_url, prog_url


def _ffmpeg_frame(stream_url: str, t: float, dest: Path) -> None:
    cmd = [
        "ffmpeg", "-loglevel", "error",
        "-i", stream_url,
        "-ss", str(t),
        "-frames:v", "1",
        "-q:v", "2",
        "-y", str(dest),
    ]
    subprocess.run(cmd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def extract_frame(url: str, t: float) -> Path:
    name = hashlib.md5(f"{url}|{t:.3f}".encode()).hexdigest() + ".jpg"
    jpg  = FRAMES_DIR / name

    v_only, prog = _best_stream_urls(url)

    try:
        if v_only:
            _ffmpeg_frame(v_only, t, jpg)            # plan A
        else:
            raise RuntimeError                       # obliga a ir al plan B
    except Exception:
        _ffmpeg_frame(prog, t, jpg)                  # plan B (progresivo)

    return jpg.resolve()


async def async_extract_frame(url: str, t: float) -> Path:
    return await asyncio.to_thread(extract_frame, url, t)
