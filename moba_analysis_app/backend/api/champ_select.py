#!/usr/bin/env python3
# api/champselect.py
# ---------------------------------------------------------------------------–
# Champion-Select Recognition REST layer
# ---------------------------------------------------------------------------–
#
# End-points exposed
# ------------------
# • GET  /api/champselect/wrappers      – list every available wrapper function
# • POST /api/champselect/process       – run a *specific* wrapper
# • POST /api/champselect/process/best  – opinionated “one-click” route
#
# The heavy lifting is delegated to *services.live_game_analysis.champion_select
# .champion_matcher* which dynamically exposes many wrappers named
# `process_champion_select_<DETECTOR>_<STRATEGY>`.
#
# This thin API layer only:
#   1. validates / decodes the uploaded screenshot,
#   2. finds and invokes the requested wrapper,
#   3. (optionally) stores visual evidence under  backend/api/results/
#
# Every route is carefully documented so that FastAPI / Swagger UI shows
# meaningful descriptions for both developers and automatic clients.
# ---------------------------------------------------------------------------–

from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from services.live_game_analysis.champion_select import champion_matcher as tm

router = APIRouter(prefix="/api/champselect", tags=["champ-select"])

# ---------------------------------------------------------------------------–
# Constants & shared helpers
# ---------------------------------------------------------------------------–
_MAX_SIZE = 10 * 1_024 * 1_024  # 10 MiB – hard limit for an uploaded screenshot

RESULTS_DIR: Path = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_image(data: bytes) -> np.ndarray:
    """
    Decode *data* (bytes) into a BGR `np.ndarray`.

    Raises
    ------
    ValueError
        • if the file is larger than `_MAX_SIZE`
        • if OpenCV is unable to decode the buffer
    """
    if len(data) > _MAX_SIZE:
        raise ValueError("Image exceeds 10 MiB limit.")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("File is not a valid image.")
    return img


def _get_wrapper(name: str):
    """
    Return the *callable* matching `name` or raise `KeyError`.

    Only wrappers following the naming convention
    `process_champion_select_*` are admitted.
    """
    fn = getattr(tm, name, None)
    if fn is None or not name.startswith("process_champion_select_"):
        raise KeyError(f"Wrapper '{name}' not found.")
    return fn


# ---------------------------------------------------------------------------–
# Routes
# ---------------------------------------------------------------------------–
@router.get(
    "/wrappers",
    response_model=List[str],
    summary="List available wrappers",
    description="Returns every wrapper exposed by **champion_matcher** "
    "in alphabetical order.",
)
async def list_wrappers() -> List[str]:
    return sorted(
        n for n in dir(tm) if n.startswith("process_champion_select_")
    )


@router.post(
    "/process",
    summary="Run a specific wrapper",
    description=(
        "Execute the chosen *champ-select* wrapper over a screenshot. "
        "If **store_evidence** is `true`, the wrapper receives "
        "`save_root=api/results` and will save every visual artefact there."
    ),
)
async def process_champ_select(
    file: UploadFile = File(..., description="Champion-select screenshot (PNG / JPEG)"),
    wrapper: str = Form(..., description="Exact wrapper name obtained from `/wrappers`"),
    ref_src: tm.ReferenceSource = Form(
        tm.ReferenceSource.ICONS,
        description="Image source used by the matcher (icons / splash arts / loading screens)",
    ),
    roi_name: str = Form(
        "champ_select_rois",
        description="ROI template without the .json extension",
    ),
    store_evidence: bool = Form(
        False,
        description="Store every visual evidence produced by the wrapper",
    ),
):
    try:
        frame = _load_image(await file.read())
        fn = _get_wrapper(wrapper)
        roi_tpl = tm.load_roi_template(roi_name)

        kwargs = dict(save_root=RESULTS_DIR, tag=wrapper) if store_evidence else {}
        result = fn(frame, roi_template=roi_tpl, ref_src=ref_src, **kwargs)

    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "wrapper": wrapper,
        "ref_src": ref_src.value,
        "roi": roi_name,
        "stored": store_evidence,
        "result": result,
        "status": "ok",
    }


@router.post(
    "/process/best",
    summary="Opinionated fastest route",
    description=(
        "Runs the *recommended* wrapper "
        "`process_champion_select_ORB_resize_bbox_only` with **splash arts** as "
        "reference source. Evidence is always stored."
    ),
)
async def process_best_champ_select(
    file: UploadFile = File(..., description="Champion-select screenshot (PNG / JPEG)"),
    roi_name: str = Form(
        "champ_select_rois",
        description="ROI template without the .json extension",
    ),
):
    WRAPPER_NAME = "process_champion_select_ORB_resize_bbox_only"
    DEFAULT_SRC = tm.ReferenceSource.SPLASH_ARTS

    try:
        frame = _load_image(await file.read())
        fn = _get_wrapper(WRAPPER_NAME)
        roi_tpl = tm.load_roi_template(roi_name)

        result = fn(
            frame,
            roi_template=roi_tpl,
            ref_src=DEFAULT_SRC,
            save_root=RESULTS_DIR,
            tag=WRAPPER_NAME,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "wrapper": WRAPPER_NAME,
        "ref_src": DEFAULT_SRC.value,
        "roi": roi_name,
        "stored": True,
        "result": result,
        "status": "ok",
    }
