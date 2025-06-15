"""
Arranca con:
    python main.py --reload
"""
import argparse, uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import api_router
from utils.cleanup import cleanup_frames

# ─────────────────── limpieza inicial ───────────────────
deleted = cleanup_frames()
print(f"Frames eliminados al iniciar: {deleted}")

# ─────────────────── FastAPI app ───────────────────
app = FastAPI(title="TFG MOBA ANALYSIS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static mounts (iconos, splash, loading)
IMG_BASE = Path(__file__).resolve().parent / "assets" / "images"
app.mount("/static/icons",           StaticFiles(directory=IMG_BASE / "icons"),           name="icons")
app.mount("/static/splash_arts",     StaticFiles(directory=IMG_BASE / "splash_arts"),     name="splash_arts")
app.mount("/static/loading_screens", StaticFiles(directory=IMG_BASE / "loading_screens"), name="loading")

# Rutas REST
app.include_router(api_router)

# ─────────────────── punto de entrada ───────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8888, type=int)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["."],
    )
