"""
Arranca con:
    python main.py --reload
"""

import os
import argparse
import hashlib
import subprocess
import asyncio
import sqlite3

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
import uvicorn

from yt_dlp import YoutubeDL

# ──────────────────────────── Config ────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
FRAMES_DIR   = os.path.join(BASE_DIR, 'frames')
COOKIES_PATH = os.path.join(BASE_DIR, 'cookies.txt')
DB_PATH = os.path.join(BASE_DIR, "assets", "db", "moba_analysis.sqlite")

os.makedirs(FRAMES_DIR, exist_ok=True)

# Cola de trabajo
queue: asyncio.Queue[dict] = asyncio.Queue()

# ──────────────────────────── Modelos ────────────────────────────
class VideoSignal(BaseModel):
    url:  HttpUrl
    time: float  # segundos

# ─────────────────────── helpers ────────────────────────
def _export_db_to_json() -> dict:
    """Devuelve todas las tablas (excepto las internas) como dict JSON-friendly."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'")
        tables = [row["name"] for row in cur.fetchall()]

        dump: dict[str, list[dict]] = {}
        for t in tables:
            cur.execute(f"SELECT * FROM {t}")
            dump[t] = [dict(r) for r in cur.fetchall()]
    return dump

def _export_single_table(table: str) -> list[dict]:
    """Devuelve todas las filas de una tabla ya validada."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table}")
        return [dict(r) for r in cur.fetchall()]

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

@app.get("/api/database")
async def get_full_database():
    """Devuelve todas las tablas y filas en JSON."""
    data = await asyncio.to_thread(_export_db_to_json)
    return data

# ------------- NUEVO ENDPOINT POR TABLA -------------
VALID_TABLES = {"versions", "champions", "leaguepedia_games"}

@app.get("/api/database/{table_name}")
async def get_table_data(table_name: str):
    """Devuelve las filas de una tabla concreta."""
    if table_name not in VALID_TABLES:
        raise HTTPException(status_code=404, detail="Tabla no encontrada")
    rows = await asyncio.to_thread(_export_single_table, table_name)
    return {table_name: rows}

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
