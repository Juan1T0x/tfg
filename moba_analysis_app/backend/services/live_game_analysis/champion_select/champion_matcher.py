#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Champion-Select Recognition
===========================

A thin wrapper around OpenCV feature detectors that identifies the five
champions shown for each team during the draft phase (*champ-select*).

Four public helpers are generated on-the-fly for **every** detector
available in the local OpenCV build (SIFT, ORB, …) combined with four
pre-defined resize strategies:

    process_champion_select_<DETECTOR>_<STRATEGY>(frame, /, *,
        roi_template: dict | None = None,
        ref_src: ReferenceSource = ReferenceSource.ICONS) -> {
            "blue": [c_top, c_jng, c_mid, c_bot, c_sup],
            "red" : [c_top, c_jng, c_mid, c_bot, c_sup],
        }

`<STRATEGY>` can be one of:

    • resize_none         – no resizing at all
    • resize_bbox_only    – resize the query patch to 100×100 px
    • resize_db_only      – resize every reference image to 100×100 px
    • resize_both         – resize both query and references

The reference images are downloaded automatically from Data-Dragon on
first use and cached under *assets/images/*.

Only the raw predictions are returned – all former “evidence saving”
logic has been dropped to keep the API side-effect free.
"""

from __future__ import annotations

import glob
import json
import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

# --------------------------------------------------------------------------- #
# Riot assets                                                                 #
# --------------------------------------------------------------------------- #
from services.riot_api.riot_versions import get_latest_version
from services.riot_api.riot_champions_images import (
    download_all_images,
    get_icons_path,
    get_splash_arts_path,
    get_loading_screens_path,
)

# --------------------------------------------------------------------------- #
# Configuration / paths                                                       #
# --------------------------------------------------------------------------- #
class ReferenceSource(str, Enum):
    """Location of the reference artwork used for matching."""
    ICONS           = "icons"          # square ability icons (small)
    SPLASH_ARTS     = "splash_arts"    # full-size splash arts
    LOADING_SCREENS = "loading_screens"

BASE_DIR = Path(__file__).resolve().parents[3]                 # …/backend
ROI_ROOT = BASE_DIR / "services" / "live_game_analysis" / "roi_templates"

_SRC_TO_PATH_FN = {
    ReferenceSource.ICONS:           get_icons_path,
    ReferenceSource.SPLASH_ARTS:     get_splash_arts_path,
    ReferenceSource.LOADING_SCREENS: get_loading_screens_path,
}

# --------------------------------------------------------------------------- #
# ROI helpers                                                                 #
# --------------------------------------------------------------------------- #
Coordinate = Tuple[float, float]
Template   = Dict[str, List[Coordinate]]

def scale_points(
    points: List[Coordinate], fw: int, fh: int,
    ref_size: Tuple[int, int] | None
) -> List[Tuple[int, int]]:
    """
    Convert a list of points of **any** supported type to absolute pixels:

    * normalised  (0-1)                  → multiply by frame size
    * absolute    (reference resolution) → scale to current resolution
    * already abs (no ref_size & not 0-1)→ returned untouched
    """
    if all(0.0 <= x <= 1.0 for x, _ in points):
        return [(int(x * fw), int(y * fh)) for x, y in points]
    if ref_size is not None:
        rw, rh = ref_size
        sx, sy = fw / rw, fh / rh
        return [(int(x * sx), int(y * sy)) for x, y in points]
    return [(int(x), int(y)) for x, y in points]

def get_scaled_rois(tpl: Template, fw: int, fh: int) -> Tuple[Tuple[int, int, int, int], ...]:
    """Return the bounding boxes for the blue and red team champion rows."""
    ref = tpl.get("reference_size")

    def bbox(pts):
        xs, ys = zip(*pts)
        return min(xs), min(ys), max(xs), max(ys)

    b1 = bbox(scale_points(tpl["team1ChampionsRoi"], fw, fh, ref))
    b2 = bbox(scale_points(tpl["team2ChampionsRoi"], fw, fh, ref))
    return b1, b2

def subdivide_roi(box: Tuple[int, int, int, int], n: int = 5) -> List[Tuple[int, int, int, int]]:
    """Split a horizontal champion row into *n* equal rectangles."""
    x1, y1, x2, y2 = box
    step = (x2 - x1) // n
    return [
        (x1 + i * step, y1,
         x1 + (i + 1) * step if i < n - 1 else x2, y2)
        for i in range(n)
    ]

def load_roi_template(name: str = "champ_select_rois") -> Template:
    """Load the given template from *roi_templates/*.json*."""
    return json.loads((ROI_ROOT / f"{name}.json").read_text(encoding="utf-8"))

# --------------------------------------------------------------------------- #
# Reference images & detectors                                                #
# --------------------------------------------------------------------------- #
def _ensure_refs_ready(src: ReferenceSource) -> Path:
    """Download Data-Dragon artwork the first time it is requested."""
    folder = Path(_SRC_TO_PATH_FN[src]())
    if not any(folder.iterdir()):
        print(f"↻ No local artwork found ({src.value}); downloading …")
        download_all_images(get_latest_version())
    return folder

def load_reference_images(src: ReferenceSource) -> Dict[str, np.ndarray]:
    """Return {champion_key → BGR image} for the chosen source."""
    folder = _ensure_refs_ready(src)
    out: Dict[str, np.ndarray] = {}
    for fp in glob.glob(os.path.join(folder, "*")):
        if fp.lower().endswith((".png", ".jpg", ".jpeg")):
            name = Path(fp).stem.split("_")[0].lower()
            img  = cv2.imread(fp)
            if img is not None:
                out[name] = img
    return out

def _create_detectors() -> Dict[str, cv2.Feature2D]:
    """Create every detector available in the current OpenCV build."""
    det: Dict[str, cv2.Feature2D] = {}
    if hasattr(cv2, "SIFT_create"):  det["SIFT"]  = cv2.SIFT_create()
    if hasattr(cv2, "ORB_create"):   det["ORB"]   = cv2.ORB_create()
    if hasattr(cv2, "AKAZE_create"): det["AKAZE"] = cv2.AKAZE_create()
    if hasattr(cv2, "BRISK_create"): det["BRISK"] = cv2.BRISK_create()
    if hasattr(cv2, "KAZE_create"):  det["KAZE"]  = cv2.KAZE_create()
    try: det["SURF"] = cv2.xfeatures2d.SURF_create()            # type: ignore[attr-defined]
    except Exception: pass
    return det

_DETECTORS = _create_detectors()

# --------------------------------------------------------------------------- #
# Matching                                                                    #
# --------------------------------------------------------------------------- #
def _extract_and_match(
    det_name: str,
    detector: cv2.Feature2D,
    query: np.ndarray,
    targets: Dict[str, np.ndarray],
    *,
    top_k: int = 5
) -> List[Tuple[str, int]]:
    """Return up to *top_k* matches sorted by number of good correspondences."""
    kp_q, des_q = detector.detectAndCompute(query, None)
    if des_q is None or not kp_q:
        return []

    norm = cv2.NORM_L2 if det_name in ("SIFT", "SURF", "KAZE") else cv2.NORM_HAMMING
    matcher = cv2.BFMatcher(norm)

    scores: List[Tuple[str, int]] = []
    for name, img in targets.items():
        kp_t, des_t = detector.detectAndCompute(img, None)
        if des_t is None or not kp_t:
            continue
        pairs = matcher.knnMatch(des_q, des_t, k=2)
        good  = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
        if good:
            scores.append((name, len(good)))

    return sorted(scores, key=lambda x: x[1], reverse=True)[:top_k]

# --------------------------------------------------------------------------- #
# Core routine                                                                #
# --------------------------------------------------------------------------- #
def _process_champion_select(
    det_name: str,
    resize_bbox: bool,
    resize_db: bool,
    frame: np.ndarray,
    roi_template: Template | None = None,
    ref_src: ReferenceSource = ReferenceSource.ICONS,
) -> Dict[str, List[str]]:
    """Shared implementation behind every auto-generated helper."""
    if det_name not in _DETECTORS:
        raise ValueError(f"Detector '{det_name}' is not available.")

    tpl   = roi_template or load_roi_template()
    H, W  = frame.shape[:2]
    boxes = subdivide_roi(get_scaled_rois(tpl, W, H)[0], 5) + \
            subdivide_roi(get_scaled_rois(tpl, W, H)[1], 5)

    resize = (lambda im, f: cv2.resize(im, (100, 100)) if f else im)
    refs   = {
        k: resize(v, resize_db)
        for k, v in load_reference_images(ref_src).items()
    }
    det = _DETECTORS[det_name]

    preds: List[str] = []
    for x1, y1, x2, y2 in boxes:
        patch   = resize(frame[y1:y2, x1:x2], resize_bbox)
        matches = _extract_and_match(det_name, det, patch, refs)
        preds.append(matches[0][0] if matches else "?")

    return {"blue": preds[:5], "red": preds[5:]}

# --------------------------------------------------------------------------- #
# Public helpers (auto-generated)                                             #
# --------------------------------------------------------------------------- #
_STRATS = {
    "resize_none":       (False, False),
    "resize_bbox_only":  (True,  False),
    "resize_db_only":    (False, True),
    "resize_both":       (True,  True),
}

for _det_name in _DETECTORS:
    for _strat, (_rb, _rd) in _STRATS.items():
        _fname = f"process_champion_select_{_det_name}_{_strat}"

        def _factory(det=_det_name, rb=_rb, rd=_rd):
            return lambda frame, roi_template=None, ref_src=ReferenceSource.ICONS: (
                _process_champion_select(det, rb, rd, frame, roi_template, ref_src)
            )

        globals()[_fname] = _factory()
        globals()[_fname].__name__ = _fname
        globals()[_fname].__doc__  = (
            f"Champion-select detection using **{_det_name}** ({_strat}). "
            "Returns ``{'blue': […], 'red': […]}``."
        )

# clean temporary loop variables
del _factory, _fname, _det_name, _strat, _rb, _rd
