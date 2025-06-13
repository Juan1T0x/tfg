from fastapi import APIRouter
from .db import router as db_router
from .video import router as video_router
from .riot_api import router as riot_router

api_router = APIRouter()
api_router.include_router(db_router)
api_router.include_router(video_router)
api_router.include_router(riot_router)