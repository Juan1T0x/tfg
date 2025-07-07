#!/usr/bin/env python3
"""
Arranca con:
    python main.py --reload
"""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import api_router
from utils.cleanup import cleanup_frames

# ─────────────────── limpieza inicial ───────────────────
deleted = cleanup_frames()
print(f"Frames eliminados al iniciar: {deleted}")

# ─────────────────────  FastAPI app  ─────────────────────
app = FastAPI(title="TFG MOBA ANALYSIS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────  montajes de ficheros estáticos  ────────────────
IMG_BASE = Path(__file__).resolve().parent / "assets" / "images"
app.mount("/static/icons",           StaticFiles(directory=IMG_BASE / "icons"),           name="icons")
app.mount("/static/splash_arts",     StaticFiles(directory=IMG_BASE / "splash_arts"),     name="splash_arts")
app.mount("/static/loading_screens", StaticFiles(directory=IMG_BASE / "loading_screens"), name="loading")

# ───────────────  NUEVO: sirve los resultados dinámicos  ────────────────
MATCHES_HISTORY = Path(__file__).resolve().parent / "matches_history"

@app.get("/results/{match}/{file_path:path}")
async def serve_result_asset(match: str, file_path: str):
    """
    Devuelve cualquier recurso generado por los servicios de visualización.
    URL pública      → /results/<match>/<categoria>/…/img.png
    Ruta en disco    → matches_history/<match>/results/<categoria>/…/img.png
    """
    full = MATCHES_HISTORY / match / "results" / file_path
    if not full.is_file():
        # Devuelve 404 sin stack-trace
        return Response(status_code=404)
    return FileResponse(full)

# ───────────────  rutas REST normales  ────────────────
app.include_router(api_router)

# ─────────────────────  punto de entrada  ─────────────────────
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
