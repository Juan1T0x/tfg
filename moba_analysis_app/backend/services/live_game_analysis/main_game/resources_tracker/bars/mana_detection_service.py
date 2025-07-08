#!/usr/bin/env python3
# services/live_game_analysis/main_game/resources_tracker/bars/mana_detection_service.py
"""
Mana-bar detector
-----------------

Measures the **mana percentage** of every champion visible in a single
broadcast frame.

The detector first crops the two team resource-areas defined in
*main_overlay_rois.json*, then:

1. Converts each crop to HSV and thresholds a narrow *blue* range
   (`_LOWER_BLUE … _UPPER_BLUE`).
2. Removes noise with OPEN→CLOSE morphology and discards blobs that are
   too small (`_AREA_MIN`) or too square (`_ELONG_RATIO`).
3. Interprets the widest bar of each team as *100 %* and expresses every
   other width as a percentage of that reference.

Returned structure
~~~~~~~~~~~~~~~~~~
```json
{
  "blue": {"TOP": 100.0, "JUNGLE": 83.5, ...},
  "red" : {"TOP": 100.0, "JUNGLE": null, ...}
}

Public API
~~~~~~~~~~
``detect_mana_bars(frame: np.ndarray,
                  roi_template: dict | None = None) -> dict``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

# --------------------------------------------------------------------- #
# Paths & template                                                      #
# --------------------------------------------------------------------- #
_BACKEND_DIR = Path(__file__).resolve().parents[5]
_ROI_TEMPLATE = (
    _BACKEND_DIR
    / "services"
    / "live_game_analysis"
    / "roi_templates"
    / "main_overlay_rois.json"
)

# --------------------------------------------------------------------- #
# Tunables                                                              #
# --------------------------------------------------------------------- #
_LOWER_BLUE = np.array([95, 50, 50])
_UPPER_BLUE = np.array([125, 255, 255])
_AREA_MIN   = 300                      # px²   – minimum blob area
_ELONG_RATIO = 0.5                     # height/width ratio threshold

_ROLE_ORDER = ["TOP", "JUNGLE", "MID", "BOT", "SUPPORT"]

Coord = Tuple[float, float]


# --------------------------------------------------------------------- #
# Template helpers                                                      #
# --------------------------------------------------------------------- #
def _load_rois(custom: Path | None) -> tuple[dict[str, List[Coord]], tuple[int, int] | None]:
    """Return ROIs as ``{"team1": [...], "team2": [...]}`` plus reference size."""
    tpl_path = custom or _ROI_TEMPLATE
    tpl = json.loads(Path(tpl_path).read_text(encoding="utf-8"))
    return {
        "team1": tpl["team1ChampionsResourcesRoi"],
        "team2": tpl["team2ChampionsResourcesRoi"],
    }, tpl.get("reference_size")


def _scale_pts(
    pts: List[Coord],
    fw: int,
    fh: int,
    ref: tuple[int, int] | None,
) -> List[Tuple[int, int]]:
    """Normalised → absolute px, reference-based → scaled, absolute → unchanged."""
    if all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in pts):
        return [(int(x * fw), int(y * fh)) for x, y in pts]

    if ref:
        rw, rh = ref
        return [(int(x * fw / rw), int(y * fh / rh)) for x, y in pts]

    return [(int(x), int(y)) for x, y in pts]


def _bbox(pts: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


# --------------------------------------------------------------------- #
# Vision helpers                                                        #
# --------------------------------------------------------------------- #
def _blue_runs(crop: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Return elongated blue rectangles inside *crop* (x, y, w, h)."""
    hsv   = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask  = cv2.inRange(hsv, _LOWER_BLUE, _UPPER_BLUE)
    mask  = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  np.ones((3, 3), np.uint8))
    mask  = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects   = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > _AREA_MIN]
    return [(x, y, w, h) for x, y, w, h in rects if h < _ELONG_RATIO * w]


# --------------------------------------------------------------------- #
# Public detector                                                       #
# --------------------------------------------------------------------- #
def detect_mana_bars(
    frame: np.ndarray,
    roi_template: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, float | None]]:
    """
    Parameters
    ----------
    frame:
        Full RGB/BGR broadcast frame.
    roi_template:
        Pre-parsed template dictionary; if *None* the default JSON on disk is
        loaded.

    Returns
    -------
    dict
        ``{"blue": {"TOP": 100.0, …}, "red": {...}}`` where missing bars are
        *None*.
    """
    if not isinstance(frame, np.ndarray):
        raise TypeError("frame must be a numpy.ndarray")

    fh, fw = frame.shape[:2]
    tpl, ref = (
        _load_rois(Path(roi_template))            # type: ignore[arg-type]
        if isinstance(roi_template, (str, Path))
        else _load_rois(None)
        if roi_template is None
        else (roi_template, roi_template.get("reference_size"))
    )

    scaled = {k: _scale_pts(v, fw, fh, ref) for k, v in tpl.items()}
    boxes  = {k: _bbox(v) for k, v in scaled.items()}

    detected: Dict[str, List[Tuple[int, int, int, int]]] = {"blue": [], "red": []}
    for idx, (key, (x0, y0, x1, y1)) in enumerate(boxes.items(), 1):
        team = "blue" if idx == 1 else "red"
        rects = _blue_runs(frame[y0:y1, x0:x1])
        detected[team] = [(x + x0, y + y0, w, h) for x, y, w, h in rects]

    out: Dict[str, Dict[str, float | None]] = {"blue": {}, "red": {}}
    for team in ("blue", "red"):
        rows  = sorted(detected[team], key=lambda r: r[1])   # sort by y-coord
        ref_w = max((w for _, _, w, _ in rows), default=None)

        for i, role in enumerate(_ROLE_ORDER):
            if i < len(rows) and ref_w:
                _, _, w, _ = rows[i]
                out[team][role] = round(w / ref_w * 100, 1)
            else:
                out[team][role] = None

    return out


__all__ = ["detect_mana_bars"]