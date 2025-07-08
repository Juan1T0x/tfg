#!/usr/bin/env python3
# services/live_game_analysis/ocr_main_hud_service.py
"""
OCR utility for the main in-game HUD (upper scoreboard).

Public helper
-------------
process_main_hud_stats(frame, roi_template=None)  ➜  dict

Returned structure:
{
    "time":       {"raw": "12:34", "parsed": "12:34"},
    "blueGold":   {"raw": "24.5K", "parsed": "24.5K"},
    "redGold":    {"raw": "21.9K", "parsed": "21.9K"},
    ...
}

The default ROI template lives at:
backend/services/live_game_analysis/roi_templates/ocr_main_hud_rois.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import cv2
import numpy as np
import pytesseract

# ───────────────────── Paths ─────────────────────
_BACKEND_DIR = Path(__file__).resolve().parents[5]
_ROI_TEMPLATE = (
    _BACKEND_DIR
    / "services"
    / "live_game_analysis"
    / "roi_templates"
    / "ocr_main_hud_rois.json"
)

# ─────────────────── Types ───────────────────────
Coord      = Tuple[float, float]
BinFun     = Callable[[np.ndarray], np.ndarray]
ParseFun   = Callable[[str], Any]

# ────────────── ROI helpers ──────────────────────
def _load_rois(path: Path | None) -> Dict[str, Any]:
    tpl_path = Path(path) if path else _ROI_TEMPLATE
    return json.loads(tpl_path.read_text(encoding="utf-8"))


def _scale_pts(
    pts: List[Coord],
    fw: int,
    fh: int,
    ref: Tuple[int, int] | None,
) -> List[Tuple[int, int]]:
    """Normalised → absolute, reference-based → scaled, absolute → unchanged."""
    if ref:
        rw, rh = ref
        sx, sy = fw / rw, fh / rh
        return [(int(x * sx), int(y * sy)) for x, y in pts]

    if all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in pts):
        return [(int(x * fw), int(y * fh)) for x, y in pts]

    return [(int(x), int(y)) for x, y in pts]


def _bbox(pts: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)

# ────────────── Binarisers ───────────────────────
def _bin_white(img: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (0, 0, 180), (180, 60, 255))


def _bin_yellow(img: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (18, 60, 130), (30, 255, 255))


def _bin_otsu(img: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return th

# ─────────────────── OCR ─────────────────────────
def _ocr(bin_img: np.ndarray, whitelist: str) -> str:
    cfg = f"--oem 1 --psm 7 -c tessedit_char_whitelist={whitelist}"
    return pytesseract.image_to_string(bin_img, config=cfg).strip()

# ────────────── Parsers ──────────────────────────
_p_int   : ParseFun = lambda t: int(m.group()) if (m := re.search(r"\d+", t)) else None
_p_gold  : ParseFun = lambda t: m.group()      if (m := re.search(r"\d+\.?\d*K", t)) else None
_p_time  : ParseFun = lambda t: m.group()      if (m := re.search(r"\d{1,2}:\d{2}", t)) else None
_p_kda   : ParseFun = (
    lambda t: (
        {"k": int(m[1]), "d": int(m[2]), "a": int(m[3])}
        if (m := re.search(r"(\d+)/(\d+)/(\d+)", t))
        else None
    )
)
_p_cs    : ParseFun = lambda t: int(m.group()) if (m := re.search(r"\d+$", t)) else None
_p_keep  : ParseFun = lambda t: t.strip() if t else None

# match-key → (binariser, whitelist, parser) rules
_RULES: List[Tuple[Callable[[str], bool], BinFun, str, ParseFun]] = [
    (lambda k: k.endswith("kda"),           _bin_white,  "0123456789/", _p_kda),
    (lambda k: k.endswith("creeps"),        _bin_yellow, "0123456789",  _p_cs),
    (lambda k: k in ("blueGold", "redGold"), _bin_otsu,  "0123456789K.", _p_gold),
    (lambda k: k in ("blueTowers", "redTowers"), _bin_otsu, "0123456789", _p_int),
    (lambda k: k == "time",                 _bin_otsu,  "0123456789:",  _p_time),
]


def _rule_for(key: str) -> Tuple[BinFun, str, ParseFun]:
    for cond, bin_fn, wl, parser in _RULES:
        if cond(key):
            return bin_fn, wl, parser
    return _bin_otsu, "0123456789K:/", _p_keep

# ────────────── Public API ───────────────────────
def process_main_hud_stats(
    frame: np.ndarray,
    roi_template: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Extract every numeric/text field present in the main HUD.

    Parameters
    ----------
    frame
        Broadcast frame in BGR.
    roi_template
        Optional in-memory template; if *None*, the default JSON is used.

    Returns
    -------
    dict
        ``{ key: {"raw": "<ocr text>", "parsed": <value|None>} }``
    """
    if not isinstance(frame, np.ndarray):
        raise TypeError("frame must be a numpy.ndarray (BGR)")

    tpl = roi_template or _load_rois(None)
    ref = tpl.get("reference_size")
    fh, fw = frame.shape[:2]

    out: Dict[str, Dict[str, Any]] = {}
    for key, pts in tpl.items():
        if key == "reference_size":
            continue

        x0, y0, x1, y1 = _bbox(_scale_pts(pts, fw, fh, ref))

        # Creep score boxes are tight – widen a little
        if key.endswith("creeps"):
            x0 = max(0, x0 - 6)
            x1 = min(fw, x1 + 6)

        crop = frame[y0:y1, x0:x1]

        bin_fn, wl, parser = _rule_for(key)
        raw = _ocr(bin_fn(crop), wl)
        out[key] = {"raw": raw, "parsed": parser(raw)}

    return out


__all__ = ["process_main_hud_stats"]
