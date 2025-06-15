# api/champion_select_api.py
"""
REST API para el módulo de reconocimiento de campeones (*champ-select*).

Rutas principales
-----------------
GET  /api/champselect/wrappers
    → Devuelve todas las combinaciones detector + estrategia disponibles.

POST /api/champselect/process
    Cuerpo multipart/form-data
        • file:    imagen (screenshot)  ≤ 10 MB
        • wrapper: nombre exacto devuelto por /wrappers
        • ref_src (opcional): icons | splash_arts | loading_screens
                              (por defecto icons)
        • roi_name (opcional): nombre del JSON dentro de
                               services/live_game_analysis/roi_templates
                               (por defecto champ_select_rois)

    → Respuesta:
        {
          "wrapper": "...",
          "ref_src": "icons",
          "roi":     "champ_select_rois",
          "result":  { "blue": [...], "red": [...] }
        }
"""

from __future__ import annotations

import io
from typing import List

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile, status, Form

from services.live_game_analysis.champion_select import champion_matcher as tm

router = APIRouter(prefix="/api/champselect", tags=["champselect"])

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
_MAX_SIZE = 10 * 1024 * 1024   # 10 MB


def _load_image(data: bytes) -> np.ndarray:
    """Bytes → np.ndarray (BGR).  Lanza ValueError si no es imagen."""
    if len(data) > _MAX_SIZE:
        raise ValueError("Imagen demasiado grande (>10 MB).")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("El archivo no es una imagen válida.")
    return img


def _get_wrapper(name: str):
    fn = getattr(tm, name, None)
    if fn is None or not name.startswith("process_champion_select_"):
        raise KeyError(f"Wrapper '{name}' no existe.")
    return fn


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------
@router.get("/wrappers", response_model=List[str])
async def list_wrappers() -> List[str]:
    """
    Devuelve los nombres de todos los *wrappers* generados
    (detector + estrategia).  Ej. `process_champion_select_SIFT_resize_none`
    """
    return sorted(
        n for n in dir(tm)
        if n.startswith("process_champion_select_")
    )


@router.post("/process")
async def process_champ_select(
    file: UploadFile = File(..., description="Screenshot JPEG/PNG"),
    wrapper: str = Form(...,  description="Nombre exacto del wrapper"),
    ref_src: tm.ReferenceSource = Form(
        tm.ReferenceSource.ICONS, description="Fuente de imágenes"
    ),
    roi_name: str = Form(
        "champ_select_rois",
        description="Nombre del template ROI (sin .json)",
    ),
):
    """
    Ejecuta el wrapper indicado sobre la imagen subida y devuelve los
    campeones detectados por equipo.
    """
    try:
        img_bytes = await file.read()
        frame = _load_image(img_bytes)

        fn = _get_wrapper(wrapper)
        roi_tpl = tm.load_roi_template(roi_name)
        result = fn(frame, roi_template=roi_tpl, ref_src=ref_src)

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:                      # fallback
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {
        "wrapper": wrapper,
        "ref_src": ref_src.value,
        "roi": roi_name,
        "result": result,
        "status": "ok",
    }

@router.post("/process/best")
async def process_best_champ_select(
    file: UploadFile = File(..., description="Screenshot JPEG/PNG"),
    roi_name: str = Form(
        "champ_select_rois",
        description="Nombre del template ROI (sin .json)",
    ),
):
    """
    Versión rápida: usa por defecto  
    **wrapper = process_champion_select_SIFT_resize_bbox_only**  
    y **ref_src = splash_arts**.

    Solo hay que enviar la imagen (campo *file*).
    """
    WRAPPER_NAME = "process_champion_select_SIFT_resize_bbox_only"
    DEFAULT_SRC  = tm.ReferenceSource.SPLASH_ARTS

    try:
        img_bytes = await file.read()
        frame = _load_image(img_bytes)

        fn = _get_wrapper(WRAPPER_NAME)
        roi_tpl = tm.load_roi_template(roi_name)
        result = fn(frame, roi_template=roi_tpl, ref_src=DEFAULT_SRC)

    except KeyError:
        # improbable (wrapper de fábrica), pero por coherencia
        raise HTTPException(
            status_code=500, detail="Wrapper de detección no disponible."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {
        "wrapper": WRAPPER_NAME,
        "ref_src": DEFAULT_SRC.value,
        "roi": roi_name,
        "result": result,
        "status": "ok",
    }