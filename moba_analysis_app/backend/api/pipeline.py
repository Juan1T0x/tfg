from __future__ import annotations

import asyncio, hashlib, traceback
from typing import Dict, List

import cv2
import re
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from services.video.frame_extractor import async_extract_frame
from services.live_game_analysis.champion_select.champion_matcher import (
    process_champion_select_ORB_resize_none as detect_champs,
    ReferenceSource,
)
from services.live_game_analysis.game_state.game_state_service import (
    start_game, Role,
)
from core.worker import ensure_worker_started, queue

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

_POS_ORDER: List[Role] = [
    Role.TOP, Role.JUNGLE, Role.MID, Role.BOT, Role.SUPPORT,
]


class StartCSReq(BaseModel):
    match_title: str
    youtube_url: HttpUrl
    minute: int = Field(..., ge=0)
    second: int = Field(..., ge=0, lt=60)

    @property
    def time_pos(self) -> float:
        return self.minute * 60 + self.second


class StartCSResp(BaseModel):
    status: str
    match_title: str
    frame_file: str
    champions: Dict[str, List[str]]


class ProcessMainGameResp(BaseModel):
    status: str
    match_title: str
    frame_file: str


def _roles_dict(champs: List[str]) -> Dict[str, str]:
    return {r.name: (champs[i] if i < len(champs) else "") for i, r in enumerate(_POS_ORDER)}


def _default_team_names(title: str) -> tuple[str, str]:

    m = re.match(
        r"""^\s*
            (.*?)                       # equipo 1 (lazy)
            \s+vs\s+                    # 'vs' (case-insensitive)
            (.*?)                       # equipo 2 (lazy)
            (?:\s*[-–|].*)?             # opcional: resto tras separador
            $""",
        title,
        flags=re.IGNORECASE | re.VERBOSE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "Blue Team", "Red Team"

@router.post("/startChampionSelect", response_model=StartCSResp, status_code=201)
async def start_champion_select_ep(p: StartCSReq):
    try:
        fpath = await async_extract_frame(str(p.youtube_url), p.time_pos)

        def _detect():
            frame = cv2.imread(str(fpath)); 0/0 if frame is None else None
            return detect_champs(frame, ref_src=ReferenceSource.SPLASH_ARTS)

        champs = await asyncio.to_thread(_detect)
        b_name, r_name = _default_team_names(p.match_title)
        start_game(p.match_title, b_name, _roles_dict(champs["blue"]), r_name, _roles_dict(champs["red"]))
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e)) from e

    return StartCSResp(status="created", match_title=p.match_title, frame_file=fpath.name, champions=champs)


@router.post("/processMainGame", response_model=ProcessMainGameResp, status_code=202)
async def process_main_game_ep(p: StartCSReq):
    try:
        await ensure_worker_started()
        job_hash = hashlib.md5(f"{p.youtube_url}|{p.time_pos:.3f}".encode()).hexdigest()
        await queue.put({"url": str(p.youtube_url), "time": p.time_pos, "match": p.match_title})
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e)) from e

    return ProcessMainGameResp(status="queued", match_title=p.match_title, frame_file=f"{job_hash}.jpg")
