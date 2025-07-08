#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services.video.downloader
-------------------------

Download a complete video ‒ YouTube or any other provider supported by
**yt-dlp** ‒ into ``backend/videos``.  

The retained file name is a safe, ASCII-only slug built from the original
video title.

Examples
~~~~~~~~
>>> from services.video.downloader import download_video
>>> path = download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
>>> print(path)
WindowsPath('…/backend/videos/rick-astley-never-gonna-give-you-up.mp4')
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from yt_dlp import YoutubeDL

# --------------------------------------------------------------------------- #
# Paths & constants                                                           #
# --------------------------------------------------------------------------- #
BACKEND_DIR: Path = Path(__file__).resolve().parents[2]
VIDEOS_DIR:  Path = BACKEND_DIR / "videos"
COOKIES_TXT: Path = Path(__file__).parent / "cookies.txt"

VIDEOS_DIR.mkdir(exist_ok=True)

_SLUG_RE = re.compile(r"[^-\w]+")

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _slugify(text: str, max_len: int = 120) -> str:
    """
    Convert *text* into a filesystem-safe, lowercase slug.

    Non-ASCII characters are stripped, anything that is not a dash or a
    word-character is replaced by a single dash, and the result is trimmed
    to *max_len* characters.
    """
    ascii_text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    cleaned = _SLUG_RE.sub("-", ascii_text).strip("-").lower()
    return cleaned[:max_len] or "video"

# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def download_video(url: str) -> Path:
    """
    Download *url* to :pydata:`backend/videos`.

    Returns
    -------
    pathlib.Path
        Absolute path to the resulting MP4 file.

    Raises
    ------
    Any exception propagated by **yt-dlp** if the download fails.
    """
    # ――― 1.  Quick metadata pass to obtain the title ――― #
    meta_opts: dict[str, object] = {
        "skip_download": True,
        "quiet": True,
    }
    if COOKIES_TXT.exists():
        meta_opts["cookiefile"] = str(COOKIES_TXT)

    with YoutubeDL(meta_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get("title") or "video"

    out_template = str(VIDEOS_DIR / (_slugify(title) + ".%(ext)s"))

    # ――― 2.  Full download with the best available quality ――― #
    ydl_opts: dict[str, object] = {
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "format": "bestvideo+bestaudio/best",
        "noplaylist": True,
        "quiet": True,
    }
    if COOKIES_TXT.exists():
        ydl_opts["cookiefile"] = str(COOKIES_TXT)

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # yt-dlp substitutes ``%(ext)s`` ‒ look for any extension just in case.
    final_file = next(VIDEOS_DIR.glob(_slugify(title) + ".*"))
    return final_file.resolve()
