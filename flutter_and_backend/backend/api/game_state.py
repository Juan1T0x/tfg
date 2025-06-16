# backend/api/game_state.py
"""
Game-State API — puente REST ⇆ servicio
=======================================

* **POST** `/api/game_state/start`     → crea partida + draft inicial  
* **POST** `/api/game_state/snapshot` → inserta / fusiona fotograma  
* **POST** `/api/game_state/end`      → cierra partida  

Los cuerpos se envían en JSON y se persisten en
`backend/matches_history/<match-slug>/game_state.json`.
"""
from __future__ import annotations

import traceback
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict

from services.live_game_analysis.game_state.game_state_service import (
    start_game,
    add_or_update_snapshot,
    end_game,
    get_game_state,
    get_all_game_states,
)

router = APIRouter(prefix="/api/game_state", tags=["game_state"])

# ═════════════ MODELOS ═════════════
class TeamDraft(BaseModel):
    """
    Representa el draft de **un** equipo.
    Las claves de `champions` son strings con la posición en mayúsculas:
    `"TOP" | "JUNGLE" | "MID" | "BOT" | "SUPPORT"`.
    """
    team_name: str
    champions: Dict[str, str] = Field(
        default_factory=lambda: {
            "TOP": "", "JUNGLE": "", "MID": "", "BOT": "", "SUPPORT": ""
        }
    )


class StartReq(BaseModel):
    """Payload para `POST …/start`"""
    match_title: str
    blue: TeamDraft
    red:  TeamDraft

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "match_title": "Azure Drakes vs Crimson Foxes",
                "blue": {
                    "team_name": "Azure Drakes",
                    "champions": {
                        "TOP":     "Gwen",
                        "JUNGLE":  "Lee Sin",
                        "MID":     "Orianna",
                        "BOT":     "Jinx",
                        "SUPPORT": "Thresh"
                    }
                },
                "red": {
                    "team_name": "Crimson Foxes",
                    "champions": {
                        "TOP":     "Camille",
                        "JUNGLE":  "Viego",
                        "MID":     "LeBlanc",
                        "BOT":     "Kai'Sa",
                        "SUPPORT": "Rakan"
                    }
                }
            }
        }
    )


class SnapshotReq(BaseModel):
    """Fotograma parcial que se fusionará con el estado existente."""
    match_title: str
    timer: str = Field(..., pattern=r"^\d{2}:\d{2}$|^\d+$", examples=["00:30", "95"])
    data: Dict[str, Any]


class EndReq(BaseModel):
    match_title: str
    winner: int = Field(..., ge=0, le=1, description="0 = BLUE, 1 = RED")

# ═════════════ END-POINTS ═════════════
@router.post("/start", status_code=201)
async def start_endpoint(p: StartReq):
    """Crea o sobre-escribe *game_state.json* para `match_title`."""
    try:
        start_game(
            p.match_title,
            p.blue.team_name, p.blue.champions,
            p.red.team_name,  p.red.champions,
        )
    except Exception as exc:                                # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "created", "match": p.match_title}


@router.post("/snapshot", status_code=202)
async def snapshot_endpoint(p: SnapshotReq):
    """Inserta o actualiza (deep-merge) un fotograma."""
    try:
        add_or_update_snapshot(p.match_title, p.timer, p.data)
    except Exception as exc:                                # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "accepted", "timer": p.timer, "match": p.match_title}


@router.post("/end", status_code=200)
async def end_endpoint(p: EndReq):
    """Duplica el último snapshot como *endGame* y marca el ganador."""
    try:
        end_game(p.match_title, p.winner)
    except Exception as exc:                                # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "status": "finished",
        "winner": "BLUE" if p.winner == 0 else "RED",
        "match":  p.match_title,
    }

@router.get("/all", status_code=200)
async def get_all_matches_endpoint():
    """
    Devuelve **todos** los `game_state.json` presentes en
    `backend/matches_history/`:

    ```json
    {
      "azure-drakes-vs-foxes": { …game_state… },
      "semifinal-2025":        { …game_state… }
    }
    ```
    """
    try:
        all_states = get_all_game_states()
    except Exception as exc:                           # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"matches": all_states}

@router.get("/{match_title}", status_code=200)
async def get_match_endpoint(match_title: str):
    """
    Devuelve el `game_state.json` completo de la partida indicada.
    El **título** se pasa con *URL-encoding* (espacios → `%20`, etc.).
    """
    try:
        state = get_game_state(match_title)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    except Exception as exc:                           # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"match": match_title, "game_state": state}