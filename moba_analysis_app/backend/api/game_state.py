from __future__ import annotations

import traceback
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict

# ──────────────────────────── game-state services ───────────────────────────
from services.live_game_analysis.game_state.game_state_service import (
    start_game,
    add_or_update_snapshot,
    end_game,
    get_game_state,
    get_all_game_states,
)

# ─────────────────────────── visualisation services ─────────────────────────
from services.data_analysis.perform_analysis import (
    generar_analisis_timeline as _run_full_analysis,
)
from services.data_analysis.data_visualization import (
    get_cs_diff, get_cs_total, get_gold_diff, get_heat_maps, get_all,
)

router = APIRouter(prefix="/api/game_state", tags=["game_state"])

# ╔═════════════  MODELOS  ═════════════╗
class TeamDraft(BaseModel):
    team_name: str
    champions: Dict[str, str] = Field(
        default_factory=lambda: {
            "TOP": "", "JUNGLE": "", "MID": "", "BOT": "", "SUPPORT": ""
        }
    )


class StartReq(BaseModel):
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
                        "TOP": "Gwen", "JUNGLE": "Lee Sin",
                        "MID": "Orianna", "BOT": "Jinx",
                        "SUPPORT": "Thresh"
                    }
                },
                "red": {
                    "team_name": "Crimson Foxes",
                    "champions": {
                        "TOP": "Camille", "JUNGLE": "Viego",
                        "MID": "LeBlanc", "BOT": "Kai'Sa",
                        "SUPPORT": "Rakan"
                    }
                }
            }
        }
    )


class SnapshotReq(BaseModel):
    match_title: str
    timer: str = Field(..., pattern=r"^\d{2}:\d{2}$|^\d+$", examples=["00:30", "95"])
    data: Dict[str, Any]


class EndReq(BaseModel):
    match_title: str
    winner: int = Field(..., ge=0, le=1)


# ╔═════════════  RUTAS AUXILIARES  ═════════════╗
_MATCHES_ROOT = Path(__file__).resolve().parents[1] / "matches_history"


def _match_folder(title: str) -> Path:
    return _MATCHES_ROOT / title


# ╔═════════════  END-POINTS GAME-STATE  ═════════════╗
@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_endpoint(p: StartReq):
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


@router.post("/snapshot", status_code=status.HTTP_202_ACCEPTED)
async def snapshot_endpoint(p: SnapshotReq):
    try:
        add_or_update_snapshot(p.match_title, p.timer, p.data)
    except Exception as exc:                                # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "accepted", "timer": p.timer, "match": p.match_title}


@router.post("/end", status_code=status.HTTP_200_OK)
async def end_endpoint(p: EndReq):
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


@router.get("/all", status_code=status.HTTP_200_OK)
async def get_all_matches_endpoint():
    try:
        all_states = get_all_game_states()
    except Exception as exc:                                # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"matches": all_states}


@router.get("/{match_title}", status_code=status.HTTP_200_OK)
async def get_match_endpoint(match_title: str):
    try:
        state = get_game_state(match_title)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    except Exception as exc:                                # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"match": match_title, "game_state": state}


# ╔═════════════  END-POINTS VISUALIZACIÓN  ═════════════╗
@router.post("/{match_title}/analysis", status_code=status.HTTP_202_ACCEPTED)
async def generate_analysis_endpoint(match_title: str):
    """
    Ejecuta la generación de **todas** las visualizaciones para la partida.
    """
    folder = _match_folder(match_title)

    try:
        _run_full_analysis(folder)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="No se encontró time_line.json para esa partida",
        )
    except Exception as exc:                                # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "generating",
        "results_dir": str((folder / "results").resolve()),
        "match": match_title,
    }


def _vis_or_404(getter, match_title: str, category: str) -> List[str]:
    try:
        urls = getter(_match_folder(match_title))
    except Exception as exc:                                # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not urls:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontraron imágenes para '{category}' en esa partida.",
        )
    return urls


@router.get("/{match_title}/visuals", status_code=status.HTTP_200_OK)
async def visuals_all(match_title: str):
    """
    Devuelve las URLs de **todas** las imágenes (.png) generadas para la partida.
    """
    return {"match": match_title, "visuals": _vis_or_404(get_all, match_title, "all")}


@router.get("/{match_title}/visuals/cs_diff", status_code=status.HTTP_200_OK)
async def visuals_cs_diff(match_title: str):
    return {"match": match_title, "cs_diff": _vis_or_404(get_cs_diff, match_title, "cs_diff")}


@router.get("/{match_title}/visuals/cs_total", status_code=status.HTTP_200_OK)
async def visuals_cs_total(match_title: str):
    return {"match": match_title, "cs_total": _vis_or_404(get_cs_total, match_title, "cs_total")}


@router.get("/{match_title}/visuals/gold_diff", status_code=status.HTTP_200_OK)
async def visuals_gold_diff(match_title: str):
    return {"match": match_title, "gold_diff": _vis_or_404(get_gold_diff, match_title, "gold_diff")}


@router.get("/{match_title}/visuals/heat_maps", status_code=status.HTTP_200_OK)
async def visuals_heat_maps(match_title: str):
    return {"match": match_title, "heat_maps": _vis_or_404(get_heat_maps, match_title, "heat_maps")}
