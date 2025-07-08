#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services.video.frame_extractor
------------------------------

Extracts **one** frame from a YouTube video and stores it under
``backend/frames``.

The extractor tries the highest-resolution *video-only* DASH stream first.
If that request fails at the `ffmpeg` level (common 403 on some playlists)
it falls back to the best *progressive* stream (video + audio).

Usage
~~~~~
>>> from services.video.frame_extractor import async_extract_frame
>>> jpg_path = await async_extract_frame(
...     "https://www.youtube.com/watch?v=dQw4w9WgXcQ", 123.45
... )

Returned value is an absolute :class:`pathlib.Path`.
"""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
from pathlib import Path
from typing import Any, Tuple

from yt_dlp import YoutubeDL

# --------------------------------------------------------------------------- #
# Paths                                                                       #
# --------------------------------------------------------------------------- #
BACKEND_DIR: Path = Path(__file__).resolve().parents[2]
FRAMES_DIR:  Path = BACKEND_DIR / "frames"
COOKIES_TXT: Path = Path(__file__).parent / "cookies.txt"

FRAMES_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------------------- #
# Internal helpers                                                            #
# --------------------------------------------------------------------------- #
def _best_stream_urls(url: str) -> Tuple[str, str]:
    """
    Return ``(video_only_url, progressive_url)``.

    * ``video_only_url`` — highest video-only stream (no audio).  
    * ``progressive_url`` — highest progressive stream; always present.

    The second value is used as a fallback if downloading the first one
    results in an HTTP 403 or any other I/O error.
    """
    opts: dict[str, Any] = {"quiet": True, "skip_download": True}
    if COOKIES_TXT.exists():
        opts["cookiefile"] = str(COOKIES_TXT)

    with YoutubeDL(opts) as ydl:
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
        raise RuntimeError("No progressive streams available")

    v_url = (
        max(video_only, key=lambda f: f.get("height") or 0)["url"]
        if video_only
        else ""
    )
    p_url = max(progressive, key=lambda f: f.get("height") or 0)["url"]
    return v_url, p_url


def _ffmpeg_extract_frame(stream_url: str, time_s: float, dst: Path) -> None:
    """
    Run *ffmpeg* to grab a single frame at ``time_s`` seconds.
    """
    cmd = [
        "ffmpeg", "-loglevel", "error",
        "-i", stream_url,
        "-ss", str(time_s),
        "-frames:v", "1",
        "-q:v", "2",          # high quality JPEG
        "-y", str(dst),
    ]
    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def extract_frame(url: str, time_pos: float) -> Path:
    """
    Grab a frame from *url* at *time_pos* (seconds).

    The output file name is a deterministic MD5 of the pair ``(url, time)`` so
    repeated calls with identical arguments use the cached file.

    Returns
    -------
    pathlib.Path
        Absolute path to the saved ``.jpg``.
    """
    file_hash = hashlib.md5(f"{url}|{time_pos:.3f}".encode()).hexdigest()
    dest      = FRAMES_DIR / f"{file_hash}.jpg"

    video_only_url, progressive_url = _best_stream_urls(url)

    try:
        if video_only_url:
            _ffmpeg_extract_frame(video_only_url, time_pos, dest)
        else:
            raise RuntimeError
    except Exception:
        _ffmpeg_extract_frame(progressive_url, time_pos, dest)

    return dest.resolve()


async def async_extract_frame(url: str, time_pos: float) -> Path:
    """
    Async wrapper around :func:`extract_frame`.
    """
    return await asyncio.to_thread(extract_frame, url, time_pos)
