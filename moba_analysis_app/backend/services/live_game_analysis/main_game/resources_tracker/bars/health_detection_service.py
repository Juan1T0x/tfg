#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

_BACKEND_DIR = Path(__file__).resolve().parents[5]
_ROI_TEMPLATE_PATH = (
    _BACKEND_DIR
    / "services"
    / "live_game_analysis"
    / "roi_templates"
    / "main_overlay_rois.json"
)

_LOWER_GREEN = np.array([30, 40, 40])
_UPPER_GREEN = np.array([80, 250, 250])
_AREA_MIN = 300
_ELONG_RATIO = 0.5
_ROLE_ORDER = ["TOP", "JUNGLE", "MID", "BOT", "SUPPORT"]

Coord = Tuple[float, float]


def _load_rois(p: Path | None) -> tuple[dict[str, List[Coord]], tuple[int, int] | None]:
    tpl_path = Path(p) if p else _ROI_TEMPLATE_PATH
    tpl = json.loads(tpl_path.read_text(encoding="utf-8"))
    ref_size = tpl.get("reference_size")
    return {
        "team1": tpl["team1ChampionsResourcesRoi"],
        "team2": tpl["team2ChampionsResourcesRoi"],
    }, ref_size


def _scale_pts(pts: List[Coord], W: int, H: int, ref):
    if all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in pts):
        return [(int(x * W), int(y * H)) for x, y in pts]
    if ref:
        rw, rh = ref
        return [(int(x * W / rw), int(y * H / rh)) for x, y in pts]
    return [(int(x), int(y)) for x, y in pts]


def _bbox(pts):
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


def _find_green_rects(crop: np.ndarray) -> list[tuple[int, int, int, int]]:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask0 = cv2.inRange(hsv, _LOWER_GREEN, _UPPER_GREEN)
    kernel = np.ones((3, 3), np.uint8)
    mask1 = cv2.morphologyEx(mask0, cv2.MORPH_OPEN, kernel)
    mask2 = cv2.morphologyEx(mask1, cv2.MORPH_CLOSE, kernel)
    cnts, _ = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > _AREA_MIN]
    return [(x, y, w, h) for x, y, w, h in rects if h < _ELONG_RATIO * w]


def detect_health_bars(
    frame: np.ndarray, roi_template: dict | None = None
) -> Dict[str, Dict[str, float | None]]:
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("frame inválido")

    H, W = frame.shape[:2]
    rois_raw, ref_size = (
        _load_rois(None) if roi_template is None else (roi_template, roi_template.get("reference_size"))
    )

    scaled = {k: _scale_pts(v, W, H, ref_size) for k, v in rois_raw.items()}
    boxes = {k: _bbox(v) for k, v in scaled.items()}

    detections: dict[str, list[tuple[int, int, int, int]]] = {"blue": [], "red": []}

    for idx, (k, (x0, y0, x1, y1)) in enumerate(boxes.items(), 1):
        team_key = "blue" if idx == 1 else "red"
        crop = frame[y0:y1, x0:x1]
        rects = _find_green_rects(crop)
        detections[team_key] = [(x + x0, y + y0, w, h) for x, y, w, h in rects]

    out: Dict[str, Dict[str, float | None]] = {"blue": {}, "red": {}}

    for team in ("blue", "red"):
        rows = sorted(detections[team], key=lambda t: t[1])
        max_w = max((w for _, _, w, _ in rows), default=None)

        for i, role in enumerate(_ROLE_ORDER):
            if i < len(rows) and max_w:
                _, _, w, _ = rows[i]
                out[team][role] = round((w / max_w) * 100, 1)
            else:
                out[team][role] = None

    return out


__all__ = ["detect_health_bars"]
