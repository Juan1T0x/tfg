"""
Arranca con:
    python main.py --reload
"""
import argparse, uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_router        # importa todos los routers

app = FastAPI(title="TFG MOBA ANALYSIS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

app.include_router(api_router)    # monta /api/…

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
