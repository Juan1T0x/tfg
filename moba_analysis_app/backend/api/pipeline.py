# backend/api/pipeline.py
"""
Pipeline API
============

Motor de la aplicación que encadena varios servicios internos:

1. **/startChampionSelect**
   • Extrae un fotograma de YouTube con *yt-dlp + ffmpeg*  
   • Reconoce los campeones mostrados en la pantalla de *champ-select*
     empleando *SIFT + resize_bbox_only* **con las splash-arts** como
     referencias.  
   • Crea el `game_state.json` inicial de la partida.

El resto del flujo se gestiona con los end-points de **api/game_state.py**.
"""
from __future__ import annotations

import asyncio
import traceback
from typing import Dict, List

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

# ───────────────────── servicios internos ──────────────────────
from services.video.frame_extractor import async_extract_frame

# wrapper de detección  + Enum del origen de referencias
from services.live_game_analysis.champion_select.champion_matcher import (
    process_champion_select_ORB_resize_none as detect_champs,
    ReferenceSource,
)
from services.live_game_analysis.game_state.game_state_service import (
    start_game,
    Role,
)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# ═════════════════════ modelos ═════════════════════
class StartCSReq(BaseModel):
    """Payload para **POST /api/pipeline/startChampionSelect**"""
    match_title: str
    youtube_url: HttpUrl
    minute: int = Field(..., ge=0)
    second: int = Field(..., ge=0, lt=60)

    @property
    def time_pos(self) -> float:           # minuto + segundo → segundos decimales
        return self.minute * 60 + self.second


class StartCSResp(BaseModel):
    status: str
    match_title: str
    frame_file: str
    champions: Dict[str, List[str]]        # {'blue': [...], 'red': [...]}

# ═════════════════════ utilidades internas ═════════════════════
_POS_ORDER: List[Role] = [
    Role.TOP, Role.JUNGLE, Role.MID, Role.BOT, Role.SUPPORT
]

def _roles_dict(champs: List[str]) -> Dict[str, str]:
    """['Gwen', 'Lee Sin', …] → {'TOP': 'Gwen', 'JUNGLE': 'Lee Sin', …}"""
    return {role.name: (champs[i] if i < len(champs) else "")
            for i, role in enumerate(_POS_ORDER)}

def _default_team_names(title: str) -> tuple[str, str]:
    """
    Si *title* contiene « vs », lo separa en 2 nombres.
    De lo contrario usa 'Blue Team' y 'Red Team'.
    """
    if " vs " in title.lower():
        left, right = title.split(" vs ", 1)
        return left.strip(), right.strip()
    return "Blue Team", "Red Team"

# ═════════════════════ END-POINTS ═════════════════════
@router.post(
    "/startChampionSelect",
    response_model=StartCSResp,
    status_code=201,
)
async def start_champion_select_ep(payload: StartCSReq):
    """
    1. Extrae el fotograma indicado de YouTube.  
    2. Detecta campeones con **SIFT + resize_bbox_only** utilizando las
       *splash-arts* como conjunto de referencia.  
    3. Crea el `game_state.json` inicial.
    """
    try:
        # ─── 1) extracción del fotograma ────────────────────────────────
        frame_path = await async_extract_frame(
            str(payload.youtube_url), payload.time_pos
        )

        # ─── 2) detección de campeones (I/O pesado → thread) ────────────
        def _detect() -> Dict[str, List[str]]:
            frame = cv2.imread(str(frame_path))       # BGR
            if frame is None:
                raise RuntimeError("No se pudo leer el fotograma extraído.")
            return detect_champs(
                frame,
                ref_src=ReferenceSource.SPLASH_ARTS   # ← **forzamos splash-arts**
            )

        champs = await asyncio.to_thread(_detect)     # {'blue': [...], 'red': [...]}

        # ─── 3) escritura del game_state inicial ───────────────────────
        blue_name, red_name = _default_team_names(payload.match_title)

        start_game(
            payload.match_title,
            blue_name, _roles_dict(champs["blue"]),
            red_name,  _roles_dict(champs["red"]),
        )

    except Exception as exc:                          # pragma: no cover
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return StartCSResp(
        status="created",
        match_title=payload.match_title,
        frame_file=str(frame_path.name),
        champions=champs,
    )
