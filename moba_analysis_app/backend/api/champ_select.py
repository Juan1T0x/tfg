#!/usr/bin/env python3
"""
REST API para el módulo de reconocimiento de campeones (*champ‑select*).

Rutas
-----
GET  /api/champselect/wrappers
POST /api/champselect/process
POST /api/champselect/process/best
"""
from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.live_game_analysis.champion_select import champion_matcher as tm

router = APIRouter(prefix="/api/champselect", tags=["champselect"])

# ───────────────────────── Helpers ──────────────────────────
_MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def _load_image(data: bytes) -> np.ndarray:
    """Valida y decodifica la imagen en BGR."""
    if len(data) > _MAX_SIZE:
        raise ValueError("Imagen demasiado grande (>10 MB).")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("El archivo no es una imagen válida.")
    return img


def _get_wrapper(name: str):
    fn = getattr(tm, name, None)
    if fn is None or not name.startswith("process_champion_select_"):
        raise KeyError(f"Wrapper '{name}' no existe.")
    return fn

# Carpeta global para evidencias
RESULTS_DIR: Path = (
    Path(__file__).resolve().parent / "results"
)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ───────────────────────── Endpoints ─────────────────────────
@router.get("/wrappers", response_model=List[str])
async def list_wrappers() -> List[str]:
    """Lista de wrappers disponibles (detector + estrategia)."""
    return sorted(
        n for n in dir(tm) if n.startswith("process_champion_select_")
    )


@router.post("/process")
async def process_champ_select(
    file: UploadFile = File(..., description="Screenshot JPEG/PNG"),
    wrapper: str = Form(..., description="Nombre exacto del wrapper"),
    ref_src: tm.ReferenceSource = Form(
        tm.ReferenceSource.ICONS, description="Fuente de imágenes"
    ),
    roi_name: str = Form(
        "champ_select_rois", description="Nombre del template ROI (sin .json)"
    ),
    store_evidence: bool = Form(False, description="Guardar evidencias visuales"),
):
    """Ejecuta el wrapper indicado y (opcionalmente) guarda evidencias."""
    try:
        frame = _load_image(await file.read())
        fn = _get_wrapper(wrapper)
        roi_tpl = tm.load_roi_template(roi_name)

        kwargs = dict(save_root=RESULTS_DIR, tag=wrapper) if store_evidence else {}
        result = fn(frame, roi_template=roi_tpl, ref_src=ref_src, **kwargs)

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "wrapper": wrapper,
        "ref_src": ref_src.value,
        "roi": roi_name,
        "stored": store_evidence,
        "result": result,
        "status": "ok",
    }


@router.post("/process/best")
async def process_best_champ_select(
    file: UploadFile = File(..., description="Screenshot JPEG/PNG"),
    roi_name: str = Form(
        "champ_select_rois", description="Nombre del template ROI (sin .json)"
    ),
):
    """Ruta rápida con parámetros por defecto y evidencias siempre on."""
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

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "wrapper": WRAPPER_NAME,
        "ref_src": DEFAULT_SRC.value,
        "roi": roi_name,
        "stored": True,
        "result": result,
        "status": "ok",
    }
