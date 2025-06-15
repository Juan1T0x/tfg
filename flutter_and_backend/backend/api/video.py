# api/video.py
"""
Puntos de acceso REST para operaciones de vídeo:

• /api/video/processVideoSignal   →  encola la extracción de **un fotograma**
                                     (modelo clásico con worker asíncrono).

• /api/video/extractFrameNow      →  extrae el fotograma al instante
                                     (sin pasar por el worker).

• /api/video/downloadVideo        →  descarga el vídeo completo en backend/videos
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl

from core.worker import ensure_worker_started, queue
from services.video.frame_extractor import async_extract_frame          # ← NUEVO
from services.video.video_downloader import download_video

# ---------------------------------------------------------------------
router = APIRouter(prefix="/api/video", tags=["video"])
# ---------------------------------------------------------------------


# ───────────────────────── Models ─────────────────────────
class VideoSignal(BaseModel):
    url:  HttpUrl
    time: float            # seconds


class DownloadRequest(BaseModel):
    url: HttpUrl


# ────────────────── Encolar extracción (worker) ──────────────────
@router.post("/processVideoSignal", tags=["video"])
async def process_video_signal(sig: VideoSignal):
    """
    Encola la extracción de un fotograma.
    El worker guardará un .jpg en “backend/frames”.
    """
    await ensure_worker_started()

    key  = f"{sig.url}|{sig.time:.3f}"
    name = hashlib.md5(key.encode()).hexdigest() + ".jpg"

    await queue.put({"url": str(sig.url), "time": sig.time})
    return {"status": "queued", "file_name": name}


# ────────────────── Extracción inmediata ─────────────────────────
@router.post("/extractFrameNow", tags=["video"])
async def extract_frame_now(sig: VideoSignal):
    """
    Extrae el fotograma *en el momento* (sin pasar por la cola).
    Puede tardar varios segundos; se ejecuta en el thread-pool.
    """
    try:
        path: Path = await async_extract_frame(str(sig.url), sig.time)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Frame extraction error: {exc}",
        ) from exc

    return {"status": "ok", "file_name": path.name, "abs_path": str(path)}


# ────────────────── Descargar vídeo completo ─────────────────────
@router.post("/downloadVideo", status_code=202, tags=["video"])
async def download_video_endpoint(req: DownloadRequest):
    """
    Descarga **todo** el vídeo en “backend/videos”.
    La descarga se lanza en un hilo para no bloquear el event-loop.
    """
    try:
        file_path: Path = await asyncio.to_thread(download_video, str(req.url))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download error: {exc}",
        ) from exc

    return {
        "status": "ok",
        "file_name": file_path.name,
        "abs_path": str(file_path),
    }
