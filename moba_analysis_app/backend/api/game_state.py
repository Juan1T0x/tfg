#!/usr/bin/env python3
# api/game_state.py
# -----------------------------------------------------------------------------
# FastAPI router in charge of **in-game state** management and the associated
# visual-analytics that are generated once a match has finished.
#
# The file is split in three clearly-separated blocks:
#
#   1.  REST helpers (Pydantic models, minor utilities)
#   2.  Pure game-state CRUD routes  (create match, push snapshot …)
#   3.  Routes that trigger or expose *visualisations* (gold diff, heat-maps …)
#
# All heavy, blocking work (file I/O, matplotlib, Plotly, …) is delegated to
# services declared elsewhere; this layer is only a thin HTTP façade with
# correct error handling.
# -----------------------------------------------------------------------------
from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────── Game-state low-level service ──────────────────────
from services.live_game_analysis.game_state.game_state_service import (
    add_or_update_snapshot,
    end_game,
    get_all_game_states,
    get_game_state,
    start_game,
)
# ─────────────────────── Visualisation high-level service ──────────────────
from services.data_analysis.perform_analysis import (
    generar_analisis_timeline as _run_full_analysis,
)
from services.data_analysis.data_visualization import (
    get_all,
    get_cs_diff,
    get_cs_total,
    get_gold_diff,
    get_heat_maps,
)

router = APIRouter(prefix="/api/game_state", tags=["game_state"])

# =============================================================================
# 1. Pydantic models
# =============================================================================
class TeamDraft(BaseModel):
    """
    Minimal information required to describe a team when a match starts.
    """
    team_name: str
    champions: Dict[str, str] = Field(
        default_factory=lambda: {r: "" for r in ["TOP", "JUNGLE", "MID", "BOT", "SUPPORT"]}
    )


class StartReq(BaseModel):
    """Payload for **POST /start** – creates or overwrites a match."""
    match_title: str
    blue: TeamDraft
    red: TeamDraft

    # Provide a full example in the OpenAPI docs
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "match_title": "Azure Drakes vs Crimson Foxes",
                "blue": {
                    "team_name": "Azure Drakes",
                    "champions": {
                        "TOP": "Gwen",
                        "JUNGLE": "Lee Sin",
                        "MID": "Orianna",
                        "BOT": "Jinx",
                        "SUPPORT": "Thresh",
                    },
                },
                "red": {
                    "team_name": "Crimson Foxes",
                    "champions": {
                        "TOP": "Camille",
                        "JUNGLE": "Viego",
                        "MID": "LeBlanc",
                        "BOT": "Kai'Sa",
                        "SUPPORT": "Rakan",
                    },
                },
            }
        }
    )


class SnapshotReq(BaseModel):
    """
    Payload for **POST /snapshot** – pushes OR merges a single frame snapshot.
    """
    match_title: str
    # Accept either a canonical "MM:SS" key or raw integer seconds
    timer: str = Field(..., pattern=r"^\d{2}:\d{2}$|^\d+$", examples=["00:30", "95"])
    data: Dict[str, Any]


class EndReq(BaseModel):
    """
    Payload for **POST /end** – flags a match as finished.
    """
    match_title: str
    winner: int = Field(..., ge=0, le=1, description="0 = blue, 1 = red")

# ----------------------------------------------------------------------------
# Local helpers (pure filesystem utilities, *not* route functions)
# ----------------------------------------------------------------------------
_MATCHES_ROOT = Path(__file__).resolve().parents[1] / "matches_history"
def _match_folder(title: str) -> Path:
    """
    Convert a public *match_title* into its on-disk folder path.
    """
    return _MATCHES_ROOT / title

# =============================================================================
# 2. Game-state CRUD routes
# =============================================================================
@router.post("/start", status_code=status.HTTP_201_CREATED, summary="Create a match")
async def start_endpoint(p: StartReq):
    """
    Create or overwrite a game-state file for *match_title*.
    """
    try:
        start_game(
            p.match_title,
            p.blue.team_name, p.blue.champions,
            p.red.team_name,  p.red.champions,
        )
    except Exception as exc:                       # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "created", "match": p.match_title}


@router.post("/snapshot", status_code=status.HTTP_202_ACCEPTED, summary="Add/merge a snapshot")
async def snapshot_endpoint(p: SnapshotReq):
    """
    Add a *live snapshot* (or deep-merge with an existing one) to the timeline.
    The `timer` field can be given as `"MM:SS"` or raw seconds.
    """
    try:
        add_or_update_snapshot(p.match_title, p.timer, p.data)
    except Exception as exc:                       # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "accepted", "timer": p.timer, "match": p.match_title}


@router.post("/end", status_code=status.HTTP_200_OK, summary="End a match")
async def end_endpoint(p: EndReq):
    """
    Mark the match as finished, copy the last live snapshot to the `endGame`
    key and persist the winner.
    """
    try:
        end_game(p.match_title, p.winner)
    except Exception as exc:                       # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "status": "finished",
        "winner": "BLUE" if p.winner == 0 else "RED",
        "match":  p.match_title,
    }


@router.get("/all", summary="List every stored match")
async def get_all_matches_endpoint():
    """
    Return all `game_state.json` files found under *matches_history/*.
    """
    try:
        return {"matches": get_all_game_states()}
    except Exception as exc:                       # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{match_title}", summary="Fetch the game-state of one match")
async def get_match_endpoint(match_title: str):
    """
    Fetch a single game-state; 404 if the match folder does not exist.
    """
    try:
        state = get_game_state(match_title)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Match not found")
    except Exception as exc:                       # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"match": match_title, "game_state": state}

# =============================================================================
# 3. Visualisation routes
# =============================================================================
@router.post(
    "/{match_title}/analysis",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate every analysis figure for the match",
)
async def generate_analysis_endpoint(match_title: str):
    """
    Run the *full* offline analysis pipeline (gold diff, CS diff, heat-maps …).

    The heavy lifting is done synchronously on purpose; if the request is
    expected to take too long in production, wrap the service call inside
    ``asyncio.to_thread`` or move it to a background task.
    """
    folder = _match_folder(match_title)
    try:
        _run_full_analysis(folder)
    except FileNotFoundError:
        raise HTTPException(404, "time_line.json not found for that match")
    except Exception as exc:                       # pragma: no cover
        traceback.print_exc()
        raise HTTPException(500, str(exc)) from exc

    return {
        "status": "generating",
        "results_dir": str((folder / "results").resolve()),
        "match": match_title,
    }

# Helper shared by every “visuals/*” GET
def _vis_or_404(getter, match_title: str, category: str) -> List[str]:
    try:
        urls = getter(_match_folder(match_title))
    except Exception as exc:                       # pragma: no cover
        traceback.print_exc()
        raise HTTPException(500, str(exc)) from exc
    if not urls:
        raise HTTPException(
            404, detail=f"No images found for '{category}' in that match."
        )
    return urls

# ───────── Collection-level
@router.get("/{match_title}/visuals", summary="List every PNG generated for the match")
async def visuals_all(match_title: str):
    return {"match": match_title, "visuals": _vis_or_404(get_all, match_title, "all")}

# ───────── Individual categories
@router.get("/{match_title}/visuals/cs_diff", summary="Creep-score difference charts")
async def visuals_cs_diff(match_title: str):
    return {"match": match_title, "cs_diff": _vis_or_404(get_cs_diff, match_title, "cs_diff")}


@router.get("/{match_title}/visuals/cs_total", summary="Total creep-score charts")
async def visuals_cs_total(match_title: str):
    return {"match": match_title, "cs_total": _vis_or_404(get_cs_total, match_title, "cs_total")}


@router.get("/{match_title}/visuals/gold_diff", summary="Gold difference charts")
async def visuals_gold_diff(match_title: str):
    return {"match": match_title, "gold_diff": _vis_or_404(get_gold_diff, match_title, "gold_diff")}


@router.get("/{match_title}/visuals/heat_maps", summary="Player heat-map images")
async def visuals_heat_maps(match_title: str):
    return {"match": match_title, "heat_maps": _vis_or_404(get_heat_maps, match_title, "heat_maps")}
