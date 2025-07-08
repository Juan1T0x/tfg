#!/usr/bin/env python3
# api/video.py
# -----------------------------------------------------------------------------
# Video-related REST endpoints
#
# 1. **/api/video/processVideoSignal** ─ push one single frame extraction task
#    onto the shared async worker queue.
#
# 2. **/api/video/extractFrameNow** ─ run the very same extraction immediately
#    (synchronous from the caller’s perspective).
#
# 3. **/api/video/downloadVideo** ─ download the *full* YouTube video to
#    ``backend/videos`` using the smart wrapper built around *yt-dlp*.
#
# Every expensive operation is delegated either to:
#   • the background worker (queue)  ➜ doesn’t block the HTTP request
#   • ``asyncio.to_thread``          ➜ keeps the event-loop responsive
# -----------------------------------------------------------------------------
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl

from core.worker import ensure_worker_started, queue
from services.video.frame_extractor import async_extract_frame
from services.video.video_downloader import download_video

router = APIRouter(prefix="/api/video", tags=["video"])

# =============================================================================
# Pydantic payload models
# =============================================================================
class VideoSignal(BaseModel):
    """
    Generic *“extract one frame”* request body.
    """
    url:  HttpUrl  # fully-qualified video URL (YouTube or any yt-dlp backend)
    time: float    # seek position in **seconds** from the beginning


class DownloadRequest(BaseModel):
    """
    Request body for *download full video*.
    """
    url: HttpUrl


# =============================================================================
# Background-queue extraction
# =============================================================================
@router.post(
    "/processVideoSignal",
    summary="Enqueue one frame extraction (handled by worker)",
)
async def process_video_signal(sig: VideoSignal):
    """
    Put a **single** extraction job on the global queue.
    The worker stores the resulting *JPEG* under ``backend/frames`` and keeps
    the same hashing convention used here so clients can predict the filename.
    """
    await ensure_worker_started()

    # Deterministic output name: md5(<url>|<time.xxx>) + '.jpg'
    key = f"{sig.url}|{sig.time:.3f}"
    file_name = hashlib.md5(key.encode()).hexdigest() + ".jpg"

    await queue.put({"url": str(sig.url), "time": sig.time})
    return {"status": "queued", "file_name": file_name}


# =============================================================================
# Immediate extraction – no queue, blocking until ready
# =============================================================================
@router.post(
    "/extractFrameNow",
    summary="Extract frame synchronously (no queue)",
)
async def extract_frame_now(sig: VideoSignal):
    """
    Perform the extraction right away.  
    Internally we **off-load** the FFmpeg call to the thread-pool to keep the
    server reactive; nevertheless the HTTP client waits for completion.
    """
    try:
        path: Path = await async_extract_frame(str(sig.url), sig.time)
    except Exception as exc:                        # pragma: no cover
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Frame extraction error: {exc}",
        ) from exc

    return {
        "status": "ok",
        "file_name": path.name,
        "abs_path": str(path),
    }


# =============================================================================
# Download full video
# =============================================================================
@router.post(
    "/downloadVideo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Download the entire video to backend/videos",
)
async def download_video_endpoint(req: DownloadRequest):
    """
    Start a full-video download.  
    The heavy lifting runs in a background thread; once the file lands on
    disk the absolute path is returned so external services can pick it up.
    """
    try:
        file_path: Path = await asyncio.to_thread(download_video, str(req.url))
    except Exception as exc:                        # pragma: no cover
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Download error: {exc}",
        ) from exc

    return {
        "status": "ok",
        "file_name": file_path.name,
        "abs_path": str(file_path),
    }
