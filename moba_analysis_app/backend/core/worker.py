# core/worker.py
"""
Background worker que extrae **un fotograma** usando el servicio
`services.video.frame_extractor`.

Un `asyncio.Queue` global recibe dicts `{"url": str, "time": float}`.
`ensure_worker_started()` garantiza que el _loop_ se inicie solo una vez.
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any, TypedDict

from services.video.frame_extractor import async_extract_frame  # ← NUEVO

# ─────────────────────────── Paths ───────────────────────────
BASE_DIR   = Path(__file__).resolve().parents[1]      # …/backend
FRAMES_DIR = BASE_DIR / "frames"
FRAMES_DIR.mkdir(exist_ok=True)

# ─────────────────────────── Types ───────────────────────────
class Job(TypedDict):
    url: str
    time: float        # seconds

# ───────────────────────── Globals ───────────────────────────
queue: "asyncio.Queue[Job]" = asyncio.Queue()
_worker_task: asyncio.Task[Any] | None = None

# ───────────────────────── Worker loop ───────────────────────
async def _worker_loop() -> None:
    """Consume jobs forever, guardando un .jpg por cada job."""
    while True:
        job = await queue.get()
        url, t = job["url"], job["time"]

        frame_name = hashlib.md5(f"{url}|{t:.3f}".encode()).hexdigest() + ".jpg"
        print(f"▶ Processing {url} @ {t:.2f}s → {frame_name}")

        try:
            # toda la lógica pesada vive ahora en el servicio
            await async_extract_frame(url, t)
            print(f"✅ Saved frame: {frame_name}")

        except Exception as exc:
            print(f"❌ Worker error: {exc}")

        finally:
            queue.task_done()

# ───────────────── public helper ─────────────────────────────
async def ensure_worker_started() -> None:
    """Lanza el worker si aún no está corriendo (idempotente)."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())
