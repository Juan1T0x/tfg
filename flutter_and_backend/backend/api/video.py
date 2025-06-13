import asyncio, hashlib, os, subprocess
from fastapi import APIRouter
from pydantic import HttpUrl, BaseModel
from yt_dlp import YoutubeDL
from core.worker import queue, ensure_worker_started   # ver más abajo

router = APIRouter(prefix="/api", tags=["video"])

class VideoSignal(BaseModel):
    url:  HttpUrl
    time: float

@router.post("/processvideosignal")
async def process_signal(sig: VideoSignal):
    await ensure_worker_started()          # garantía de que el worker existe
    url, time = str(sig.url), sig.time
    key  = f"{url}|{time:.3f}"
    name = hashlib.md5(key.encode()).hexdigest() + ".jpg"
    await queue.put({'url': url, 'time': time})
    return {"status": "queued", "frameName": name}
