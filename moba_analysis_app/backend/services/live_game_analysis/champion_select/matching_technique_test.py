#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Champion-Template Matcher
=========================

End-to-end benchmark for different feature detectors and resize strategies when
matching champion portraits in a *champ-select* screenshot.

The script:

1. Splits the champion rows (5 × blue + 5 × red) using a ROI template.
2. Runs every combination of:
      • detector  – {SIFT, ORB, … all available in OpenCV}
      • strategy  – bbox / DB resizing (see `RESIZE_SETTINGS`)
      • source    – icons, loading screens, splash arts
3. Measures *top-1* and *top-5* accuracy against a fixed ground-truth as well
   as the total processing time.
4. Saves visual match evidence under *results/<source>/<detector>/<strategy>/*.
5. Writes a sortable ranking to *results/matching_ranking.log*.

Adjust `GROUND_TRUTH`, the screenshot path, and template folder as needed.
"""

from __future__ import annotations

import glob
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #
BASE_DIR    = Path(__file__).parent
OUTPUT_ROOT = BASE_DIR / "results"
LOG_PATH    = OUTPUT_ROOT / "matching_ranking.log"

GROUND_TRUTH = {
    "blue": ["yorick", "pantheon", "taliyah", "kaisa", "rell"],
    "red":  ["ambessa", "vi", "ahri", "xayah", "rakan"],
}

# (resize_bbox, resize_db, label)
RESIZE_SETTINGS = [
    (True,  False, "resize_bbox_only"),
    (False, True,  "resize_db_only"),
    (True,  True,  "resize_both"),
    (False, False, "resize_none"),
]

# --------------------------------------------------------------------------- #
# ROI helpers                                                                 #
# --------------------------------------------------------------------------- #
Coordinate = Tuple[float, float]
Template   = Dict[str, List[Coordinate]]

def scale_points(
    pts: List[Coordinate], fw: int, fh: int,
    ref_size: Tuple[int, int] | None,
) -> List[Tuple[int, int]]:
    """Return the points in *absolute* pixels for the current frame size."""
    if all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts):
        return [(int(x * fw), int(y * fh)) for x, y in pts]
    if ref_size:
        rw, rh = ref_size
        sx, sy = fw / rw, fh / rh
        return [(int(x * sx), int(y * sy)) for x, y in pts]
    return [(int(x), int(y)) for x, y in pts]

def _bbox(pts: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)

def get_scaled_rois(tpl: Template, fw: int, fh: int
) -> Tuple[Tuple[int, int, int, int], Tuple[int, int, int, int]]:
    """Return bounding boxes for blue and red champion rows."""
    ref = tpl.get("reference_size")
    b1 = _bbox(scale_points(tpl["team1ChampionsRoi"], fw, fh, ref))
    b2 = _bbox(scale_points(tpl["team2ChampionsRoi"], fw, fh, ref))
    return b1, b2

def subdivide_roi(box: Tuple[int, int, int, int], n: int = 5
) -> List[Tuple[int, int, int, int]]:
    """Split *box* into *n* equal rectangles (left→right)."""
    x1, y1, x2, y2 = box
    step = (x2 - x1) // n
    return [
        (x1 + i * step, y1,
         x1 + (i + 1) * step if i < n - 1 else x2, y2)
        for i in range(n)
    ]

def load_roi_templates(folder: str) -> Dict[str, Template]:
    """Load every *.json* in *folder* into ``{name: template}``."""
    out: Dict[str, Template] = {}
    for fp in glob.glob(os.path.join(folder, "*.json")):
        try:
            out[Path(fp).stem] = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"⚠ Error loading {fp}: {exc}")
    return out

# --------------------------------------------------------------------------- #
# Reference artwork & detectors                                               #
# --------------------------------------------------------------------------- #
def normalize_name(fname: str) -> str:
    """'Ahri_splash' → 'ahri'."""
    return fname.lower().split("_")[0]

def load_champion_images(folder: str) -> Dict[str, np.ndarray]:
    """Return {champion_key → BGR image} for every file in *folder*."""
    out: Dict[str, np.ndarray] = {}
    for fp in glob.glob(os.path.join(folder, "*")):
        if fp.lower().endswith((".png", ".jpg", ".jpeg")):
            img = cv2.imread(fp)
            if img is not None:
                out[normalize_name(Path(fp).stem)] = img
    return out

def resize_if(img: np.ndarray, flag: bool) -> np.ndarray:
    return cv2.resize(img, (100, 100)) if flag else img

def create_detectors() -> Dict[str, cv2.Feature2D]:
    """Instantiate every detector available in this OpenCV build."""
    det: Dict[str, cv2.Feature2D] = {}
    if hasattr(cv2, "SIFT_create"):  det["SIFT"]  = cv2.SIFT_create()
    if hasattr(cv2, "ORB_create"):   det["ORB"]   = cv2.ORB_create()
    if hasattr(cv2, "AKAZE_create"): det["AKAZE"] = cv2.AKAZE_create()
    if hasattr(cv2, "BRISK_create"): det["BRISK"] = cv2.BRISK_create()
    if hasattr(cv2, "KAZE_create"):  det["KAZE"]  = cv2.KAZE_create()
    try:
        det["SURF"] = cv2.xfeatures2d.SURF_create()          # type: ignore[attr-defined]
    except Exception:
        pass
    return det

# --------------------------------------------------------------------------- #
# Matching                                                                    #
# --------------------------------------------------------------------------- #
def extract_and_match(
    det_name: str,
    detector: cv2.Feature2D,
    query: np.ndarray,
    targets: Dict[str, np.ndarray],
    *,
    want_matches: bool = False,
) -> List[Tuple[str, int, list | None, list | None]]:
    """
    Return the best *≤5* matches sorted by number of good correspondences.

    If *want_matches* is True the raw good matches and kp_t are also returned
    for later visualisation.
    """
    kp_q, des_q = detector.detectAndCompute(query, None)
    if des_q is None or not kp_q:
        return []

    norm = cv2.NORM_L2 if det_name in ("SIFT", "SURF", "KAZE") else cv2.NORM_HAMMING
    matcher = cv2.BFMatcher(norm)

    results: List[Tuple[str, int, list | None, list | None]] = []
    for name, img in targets.items():
        kp_t, des_t = detector.detectAndCompute(img, None)
        if des_t is None or not kp_t:
            continue
        try:
            pairs = matcher.knnMatch(des_q, des_t, k=2)
        except cv2.error:
            continue
        good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
        if good:
            results.append((name, len(good), good if want_matches else None, kp_t))

    return sorted(results, key=lambda x: x[1], reverse=True)[:5]

# --------------------------------------------------------------------------- #
# Main benchmark loop                                                         #
# --------------------------------------------------------------------------- #
def main() -> None:
    OUTPUT_ROOT.mkdir(exist_ok=True)

    screenshot = cv2.imread("screenshot.png")
    if screenshot is None:
        raise FileNotFoundError("screenshot.png not found")
    H, W = screenshot.shape[:2]

    tpl = load_roi_templates("../roi_templates")["champ_select_rois"]
    b_blue, b_red = get_scaled_rois(tpl, W, H)
    boxes = subdivide_roi(b_blue) + subdivide_roi(b_red)
    gt    = GROUND_TRUTH["blue"] + GROUND_TRUTH["red"]

    detectors = create_detectors()
    sources = {
        "icons":           load_champion_images("../../assets/images/icons"),
        "loading_screens": load_champion_images("../../assets/images/loading_screens"),
        "splash_arts":     load_champion_images("../../assets/images/splash_arts"),
    }

    ranking: List[Tuple[str, str, str, int, int, float]] = []

    for src_name, full_db in sources.items():
        print(f"\n=== Source: {src_name} ===")
        for resize_bbox, resize_db, strat in RESIZE_SETTINGS:
            print(f"\n  Strategy: {strat}")
            db = {k: resize_if(v, resize_db) for k, v in full_db.items()}

            scores = {d: {"top1": 0, "top5": 0} for d in detectors}
            times  = {d: 0.0 for d in detectors}

            for idx, (x1, y1, x2, y2) in enumerate(boxes):
                target = gt[idx]
                patch  = resize_if(screenshot[y1:y2, x1:x2], resize_bbox)

                for det_name, det in detectors.items():
                    t0 = time.perf_counter()
                    preds = extract_and_match(det_name, det, patch, db)
                    times[det_name] += time.perf_counter() - t0

                    names = [p[0] for p in preds]
                    if names:
                        if names[0] == target:
                            scores[det_name]["top1"] += 1
                        if target in names:
                            scores[det_name]["top5"] += 1

                    # save visual evidence
                    out_dir = OUTPUT_ROOT / src_name / det_name.lower() / strat / target
                    out_dir.mkdir(parents=True, exist_ok=True)
                    detailed = extract_and_match(det_name, det, patch, db, want_matches=True)
                    kp_q, _ = det.detectAndCompute(patch, None)
                    for rank, (cand, _, good, kp_t) in enumerate(detailed, 1):
                        vis = cv2.drawMatches(
                            patch, kp_q,
                            db[cand], kp_t,
                            good or [], None,
                            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
                        )
                        cv2.imwrite(str(out_dir / f"{cand}_{rank}.png"), vis)

            for det_name, sc in scores.items():
                t_sec = times[det_name]
                print(f"    {det_name:<6}: top1={sc['top1']:<2} "
                      f"top5={sc['top5']:<2}  t={t_sec:6.3f}s")
                ranking.append((src_name, strat, det_name,
                                sc["top1"], sc["top5"], t_sec))

    # ------------------------------------------------------------------- #
    # Global ranking                                                      #
    # ------------------------------------------------------------------- #
    ranking.sort(key=lambda x: (x[3], x[4]), reverse=True)  # by top1, then top5
    with LOG_PATH.open("w", encoding="utf-8") as log:
        hdr = "source | strategy | detector : top1  top5  time(s)\n"
        print("\n=== Global ranking ===\n")
        log.write(hdr)
        for i, (src, strat, det, t1, t5, t) in enumerate(ranking, 1):
            line = f"{i:2d}. {src} | {strat} | {det:<6}: {t1:<3} {t5:<3} {t:6.3f}"
            print(line)
            log.write(line + "\n")

    print(f"\n✔ Results saved under: {OUTPUT_ROOT.resolve()}")

# --------------------------------------------------------------------------- #
# Entry-point                                                                 #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main()
