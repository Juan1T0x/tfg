# core/worker.py
"""
Asynchronous worker that extracts a single video frame with **yt-dlp + ffmpeg**.

A global `queue` receives jobs of the form `{"url": str, "time": float}`.
`ensure_worker_started()` makes sure the background task is running exactly once.
"""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
from pathlib import Path
from typing import Any, TypedDict

from yt_dlp import YoutubeDL

# ──────────────────────────── Paths ────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[1]           # …/backend
FRAMES_DIR = BASE_DIR / "frames"
COOKIES = BASE_DIR / "cookies.txt"
FRAMES_DIR.mkdir(exist_ok=True)

# ──────────────────────────── Types ────────────────────────────
class Job(TypedDict):
    url: str
    time: float  # seconds

# ──────────────────────────── Globals ──────────────────────────
queue: "asyncio.Queue[Job]" = asyncio.Queue()
_worker_task: asyncio.Task[Any] | None = None


# ───────────────────────── Worker loop ─────────────────────────
async def _worker_loop() -> None:
    """Consume jobs forever, saving one JPG frame per job."""
    ydl_opts: dict[str, Any] = {"format": "bestvideo[ext=mp4]+bestaudio/best"}
    if COOKIES.exists():
        ydl_opts["cookiefile"] = str(COOKIES)

    while True:
        job = await queue.get()
        url, time_pos = job["url"], job["time"]

        frame_name = (
            hashlib.md5(f"{url}|{time_pos:.3f}".encode()).hexdigest() + ".jpg"
        )
        frame_path = FRAMES_DIR / frame_name
        print(f"▶ Processing {url} @ {time_pos:.2f}s → {frame_name}")

        try:
            # 1) Resolve stream URL via yt-dlp
            info = await asyncio.to_thread(
                lambda: YoutubeDL(ydl_opts).extract_info(url, download=False)
            )
            stream_url: str | None = info.get("url")  # type: ignore[index]

            if not stream_url and "formats" in info:
                stream_url = max(
                    info["formats"], key=lambda f: f.get("height") or 0  # type: ignore[index]
                ).get("url")  # type: ignore[index]

            if not stream_url:
                raise RuntimeError("No direct stream URL found")

            # 2) Extract frame with ffmpeg
            cmd = [
                "ffmpeg",
                "-ss",
                str(time_pos),
                "-i",
                stream_url,
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                str(frame_path),
            ]
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"✅ Saved frame: {frame_name}")

        except Exception as exc:
            print(f"❌ Worker error: {exc}")

        finally:
            queue.task_done()


# ─────────────────── Public helper to start worker ─────────────
async def ensure_worker_started() -> None:
    """Idempotently starts the background worker."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())
