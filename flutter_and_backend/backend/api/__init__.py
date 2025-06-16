from fastapi import APIRouter
from .db import router as db_router
from .video import router as video_router
from .riot_api import router as riot_router
from .champ_select import router as champ_select_router
from .game_state import router as game_state_router
from .pipeline import router as pipeline_router

api_router = APIRouter()
api_router.include_router(db_router)
api_router.include_router(video_router)
api_router.include_router(riot_router)
api_router.include_router(champ_select_router)
api_router.include_router(game_state_router)
api_router.include_router(pipeline_router)