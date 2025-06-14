"""
Arranca con:
    python main.py --reload
"""
import argparse, uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from api import api_router        # importa todos los routers

app = FastAPI(title="TFG MOBA ANALYSIS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)



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

IMG_BASE   = Path(__file__).resolve().parent / "assets" / "images"
app.mount("/static/icons",           StaticFiles(directory=IMG_BASE / "icons"),           name="icons")
app.mount("/static/splash_arts",     StaticFiles(directory=IMG_BASE / "splash_arts"),     name="splash_arts")
app.mount("/static/loading_screens", StaticFiles(directory=IMG_BASE / "loading_screens"), name="loading")

app.include_router(api_router)