#!/usr/bin/env python3
# api/pipeline.py
# -----------------------------------------------------------------------------
# High–level “pipeline” endpoints that orchestrate *both* phases of live-game
# analysis:
#
#   1.  **/startChampionSelect** – grab one YouTube frame, detect the five
#       champions per side, and create the initial *game_state.json*.
#   2.  **/processMainGame**     – enqueue a frame-processing job that runs
#       health / mana / OCR detection in the background worker.
#
# The heavy CV / OCR work is delegated to specialised services; this file is
# a thin FastAPI façade in charge of request validation, short I/O and queue
# management.
# -----------------------------------------------------------------------------
from __future__ import annotations

import asyncio, hashlib, re, traceback
from typing import Dict, List

import cv2
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

# ───────────────────────────── Service layer ─────────────────────────────
from services.video.frame_extractor import async_extract_frame
from services.live_game_analysis.champion_select.champion_matcher import (
    process_champion_select_ORB_resize_none as detect_champs,
    ReferenceSource,
)
from services.live_game_analysis.game_state.game_state_service import (
    Role,
    start_game,
)
from core.worker import ensure_worker_started, queue

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# --------------------------------------------------------------------------
# Internal, module-level helpers
# --------------------------------------------------------------------------
_POS_ORDER: List[Role] = [Role.TOP, Role.JUNGLE, Role.MID, Role.BOT, Role.SUPPORT]


def _roles_dict(champs: List[str]) -> Dict[str, str]:
    """
    Convert ``['Gwen', 'LeeSin', …]`` into
    ``{'TOP':'Gwen', 'JUNGLE':'LeeSin', …}``.
    """
    return {r.name: (champs[i] if i < len(champs) else "") for i, r in enumerate(_POS_ORDER)}


def _default_team_names(title: str) -> tuple[str, str]:
    """
    Extract the two team names from a YouTube video title.  
    Falls back to *Blue Team* / *Red Team* if no reliable split is found.

    Examples recognised::

        MOVISTAR KOI VS ROGUE - MAPA 1 …
        MOVISTAR KOI vs ROGUE | MAPA 1 …

    Any separator «-», «–» or «|» after the second team is ignored.
    """
    m = re.match(
        r"""^\s*
            (.*?)                       # team 1
            \s+vs\s+
            (.*?)                       # team 2
            (?:\s*[-–|].*)?             # optional suffix
            $""",
        title,
        flags=re.IGNORECASE | re.VERBOSE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "Blue Team", "Red Team"

# --------------------------------------------------------------------------
# Pydantic request / response models
# --------------------------------------------------------------------------
class StartCSReq(BaseModel):
    """
    Payload required to kick-off champion-select processing.
    """
    match_title: str
    youtube_url: HttpUrl
    minute: int = Field(..., ge=0, description="Video position – minutes")
    second: int = Field(..., ge=0, lt=60, description="Video position – seconds")

    @property
    def time_pos(self) -> float:          # seconds as *float*
        return self.minute * 60 + self.second


class StartCSResp(BaseModel):
    """
    Successful response for **POST /startChampionSelect**.
    """
    status: str
    match_title: str
    frame_file: str
    champions: Dict[str, List[str]]


class ProcessMainGameResp(BaseModel):
    """
    Response returned immediately after a main-game job is queued.
    """
    status: str
    match_title: str
    frame_file: str

# =============================================================================
#   Endpoints
# =============================================================================
@router.post(
    "/startChampionSelect",
    response_model=StartCSResp,
    status_code=status.HTTP_201_CREATED,
    summary="Detect champions and create the initial game-state",
)
async def start_champion_select_ep(p: StartCSReq):
    """
    * Blocking   : **yes** (frame download + CV matching)  
    * Side-effect: creates ``game_state.json`` with a *startGame* snapshot.

    Workflow
    --------
    1.  Extract one frame at the requested timestamp.
    2.  Run champion-select detection (ORB, no resizing).
    3.  Derive team names from the video title.
    4.  Call :pyfunc:`services.live_game_analysis.game_state.start_game`.
    """
    try:
        # 1) download frame
        fpath = await async_extract_frame(str(p.youtube_url), p.time_pos)

        # 2) detection must run in a thread – OpenCV is CPU-bound
        def _detect() -> Dict[str, List[str]]:
            frame = cv2.imread(str(fpath))
            if frame is None:
                raise RuntimeError("Could not read the extracted frame")
            return detect_champs(frame, ref_src=ReferenceSource.SPLASH_ARTS)

        champs = await asyncio.to_thread(_detect)

        # 3) team names
        blue_name, red_name = _default_team_names(p.match_title)

        # 4) persist draft in game_state.json
        start_game(
            p.match_title,
            blue_name, _roles_dict(champs["blue"]),
            red_name,  _roles_dict(champs["red"]),
        )

    except Exception as exc:                              # pragma: no cover
        traceback.print_exc()
        raise HTTPException(500, detail=str(exc)) from exc

    return StartCSResp(
        status="created",
        match_title=p.match_title,
        frame_file=fpath.name,
        champions=champs,
    )


@router.post(
    "/processMainGame",
    response_model=ProcessMainGameResp,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a main-game frame for background analysis",
)
async def process_main_game_ep(p: StartCSReq):
    """
    Put a *single* frame-extraction + CV/OCR job in the shared `core.worker`
    queue. The worker will later call *update_game* with the detected data.
    """
    try:
        await ensure_worker_started()  # starts the worker lazily
        frame_hash = hashlib.md5(f"{p.youtube_url}|{p.time_pos:.3f}".encode()).hexdigest()
        await queue.put({"url": str(p.youtube_url), "time": p.time_pos, "match": p.match_title})
    except Exception as exc:                               # pragma: no cover
        traceback.print_exc()
        raise HTTPException(500, detail=str(exc)) from exc

    return ProcessMainGameResp(
        status="queued",
        match_title=p.match_title,
        frame_file=f"{frame_hash}.jpg",
    )
