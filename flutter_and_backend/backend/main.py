"""
Arranca con:
    python main.py --reload
"""

import os
import argparse
import hashlib
import subprocess
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import uvicorn

from yt_dlp import YoutubeDL

# ──────────────────────────── Config ────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
FRAMES_DIR   = os.path.join(BASE_DIR, 'frames')
COOKIES_PATH = os.path.join(BASE_DIR, 'cookies.txt')

os.makedirs(FRAMES_DIR, exist_ok=True)

# Cola de trabajo
queue: asyncio.Queue[dict] = asyncio.Queue()

# ──────────────────────────── Modelos ────────────────────────────
class VideoSignal(BaseModel):
    url:  HttpUrl
    time: float  # segundos

# ──────────────────────────── FastAPI ────────────────────────────
app = FastAPI(title="Frame Extractor (async queue)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def start_worker():
    """Arranca el worker en background que consume la cola."""
    async def worker():
        # Opciones para yt-dlp
        ydl_opts = {'format': 'bestvideo[ext=mp4]+bestaudio/best'}
        if os.path.exists(COOKIES_PATH):
            ydl_opts['cookiefile'] = COOKIES_PATH

        while True:
            job = await queue.get()
            url  = job['url']
            time = job['time']

            # Genera un nombre único para el frame
            key        = f"{url}|{time:.3f}"
            frame_name = hashlib.md5(key.encode()).hexdigest() + ".jpg"
            frame_path = os.path.join(FRAMES_DIR, frame_name)

            print(f"▶︎ Procesando: {url} @ {time:.2f}s → {frame_name}")

            try:
                # 1) Extraer metadata sin descargar
                info = await asyncio.to_thread(
                    lambda: YoutubeDL(ydl_opts).extract_info(url, download=False)
                )

                # 2) Obtener la URL directa de streaming
                stream_url = info.get('url')
                if not stream_url and 'formats' in info:
                    # elegir el formato de mayor altura disponible
                    fmts = sorted(
                        info['formats'],
                        key=lambda f: f.get('height') or 0,
                        reverse=True
                    )
                    stream_url = fmts[0].get('url')

                if not stream_url:
                    raise RuntimeError("No stream_url encontrado")

                # 3) Extraer el frame con ffmpeg
                cmd = [
                    'ffmpeg',
                    '-ss', str(time),
                    '-i', stream_url,
                    '-frames:v', '1',
                    '-q:v', '2',
                    '-y',
                    frame_path
                ]
                await asyncio.to_thread(
                    lambda: subprocess.run(
                        cmd,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                )

                print(f"✅ Frame guardado: {frame_name}")

            except Exception as e:
                print(f"❌ Error en worker: {e}")

            finally:
                queue.task_done()

    # Inicia el worker sin bloquear el startup
    asyncio.create_task(worker())

@app.post("/api/processvideosignal")
async def process_signal(sig: VideoSignal):
    url  = str(sig.url)
    time = sig.time

    # Calcula el nombre de frame que se generará
    key        = f"{url}|{time:.3f}"
    frame_name = hashlib.md5(key.encode()).hexdigest() + ".jpg"

    # Encola la señal y responde de inmediato
    await queue.put({'url': url, 'time': time})
    print(f"🟢 Señal encolada: {url} @ {time:.2f}s → {frame_name}")
    return {"status": "queued", "frameName": frame_name}

# ──────────────────────────── Entrada ────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", default=8888, type=int)
    p.add_argument("--reload", action="store_true")
    args = p.parse_args()

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["."],
    )
