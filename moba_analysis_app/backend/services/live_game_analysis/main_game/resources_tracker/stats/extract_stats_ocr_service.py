#!/usr/bin/env python3
# services/live_game_analysis/ocr_main_hud_service.py
"""
OCR de la HUD principal (marcador superior).

Función pública
---------------
process_main_hud_stats(frame: np.ndarray,
                       roi_template: dict | None = None) -> dict

Devuelve un diccionario con la forma:

{
  "time":       { "raw": "12:34", "parsed": "12:34" },
  "blueGold":   { "raw": "24.5K", "parsed": "24.5K" },
  "redGold":    { "raw": "21.9K", "parsed": "21.9K" },
  "blueTowers": { "raw": "3",     "parsed": 3       },
  ...
}

La plantilla por defecto se toma de:

    backend/services/live_game_analysis/roi_templates/ocr_main_hud_rois.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Callable

import cv2
import numpy as np
import pytesseract

# ─────────────────────────── paths ────────────────────────────
_BACKEND_DIR      = Path(__file__).resolve().parents[5]
_ROI_TEMPLATE_PATH = (
    _BACKEND_DIR / "services" / "live_game_analysis" /
    "roi_templates" / "ocr_main_hud_rois.json"
)

# ───────────────────────── tipos ──────────────────────────────
Coord      = Tuple[float, float]
BinFun     = Callable[[np.ndarray], np.ndarray]
ParseFun   = Callable[[str], Any]

# ────────────────────── carga & helpers ROI ───────────────────
def _load_rois(path: Path | None) -> Dict[str, Any]:
    tpl_path = Path(path) if path else _ROI_TEMPLATE_PATH
    return json.loads(tpl_path.read_text(encoding="utf-8"))


def _scale_pts(pts: List[Coord], W: int, H: int, ref: Tuple[int, int] | None):
    if ref:
        rw, rh = ref
        sx, sy = W / rw, H / rh
        return [(int(x * sx), int(y * sy)) for x, y in pts]
    if all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in pts):
        return [(int(x * W), int(y * H)) for x, y in pts]
    return [(int(x), int(y)) for x, y in pts]


def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

# ───────────────────── binarizaciones ─────────────────────────
def _bin_white(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (0, 0, 180), (180, 60, 255))


def _bin_yellow(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (18, 60, 130), (30, 255, 255))


def _bin_otsu(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return th

# ──────────────────────── OCR ─────────────────────────────────
def _ocr(bin_img: np.ndarray, whitelist: str) -> str:
    cfg = f"--oem 1 --psm 7 -c tessedit_char_whitelist={whitelist}"
    return pytesseract.image_to_string(bin_img, config=cfg).strip()

# ────────────────────── parsers ───────────────────────────────
_p_int  : ParseFun = lambda t: int(m.group()) if (m := re.search(r"\d+", t)) else None
_p_gold : ParseFun = lambda t: m.group() if (m := re.search(r"\d+\.?\d*K", t)) else None
_p_time : ParseFun = lambda t: m.group() if (m := re.search(r"\d{1,2}:\d{2}", t)) else None

def _p_kda(t: str):
    m = re.search(r"(\d+)/(\d+)/(\d+)", t)
    return {"k": int(m[1]), "d": int(m[2]), "a": int(m[3])} if m else None

_p_cs: ParseFun = lambda t: int(m.group()) if (m := re.search(r"\d+$", t)) else None
_parse_default: ParseFun = lambda t: t.strip() if t else None

# ─────────────────────── reglas ───────────────────────────────
_RULES: list[tuple[Callable[[str], bool], BinFun, str, ParseFun]] = [
    (lambda k: k.endswith("kda"),          _bin_white,  "0123456789/", _p_kda),
    (lambda k: k.endswith("creeps"),       _bin_yellow, "0123456789",  _p_cs),
    (lambda k: k in ("blueGold", "redGold"), _bin_otsu, "0123456789K.", _p_gold),
    (lambda k: k in ("blueTowers", "redTowers"), _bin_otsu, "0123456789", _p_int),
    (lambda k: k == "time",                _bin_otsu,   "0123456789:", _p_time),
]


def _rule_for(key: str) -> tuple[BinFun, str, ParseFun]:
    for cond, binner, wl, parser in _RULES:
        if cond(key):
            return binner, wl, parser
    return _bin_otsu, "0123456789K:/", _parse_default

# ───────────────────── función pública ───────────────────────
def process_main_hud_stats(frame: np.ndarray,
                           roi_template: dict | None = None
                           ) -> Dict[str, Dict[str, Any]]:
    """
    Extrae todas las estadísticas visibles en la HUD principal.

    Parámetros
    ----------
    frame : np.ndarray
        Fotograma en BGR (tal cual lo carga OpenCV).
    roi_template : dict | None
        Plantilla de ROIs si se quiere usar una diferente de la predeterminada.

    Devuelve
    --------
    Dict[str, Dict[str, Any]]
        Por cada ROI una clave con:
            { "raw": "<texto OCR>", "parsed": <valor interpretado> }
    """
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("El frame debe ser un np.ndarray BGR válido.")

    tpl = roi_template or _load_rois(None)
    ref = tpl.get("reference_size")
    H, W = frame.shape[:2]

    results: Dict[str, Dict[str, Any]] = {}

    for key, pts in tpl.items():
        if key == "reference_size":
            continue

        sc = _scale_pts(pts, W, H, ref)
        x0, y0, x1, y1 = _bbox(sc)

        # ligero ensanchado para los creeps
        if key.endswith("creeps"):
            x0 = max(0, x0 - 6)
            x1 = min(W, x1 + 6)

        crop = frame[y0:y1, x0:x1]

        binner, whitelist, parser = _rule_for(key)
        bin_img = binner(crop)
        raw_text = _ocr(bin_img, whitelist)
        parsed_val = parser(raw_text)

        results[key] = {"raw": raw_text, "parsed": parsed_val}

    return results


__all__ = ["process_main_hud_stats"]
