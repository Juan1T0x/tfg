#!/usr/bin/env python3
"""
Reconocimiento de campeones en la pantalla de *champ-select*.

Se generan automáticamente funciones:

    process_champion_select_<DETECTOR>_<estrategia>(
        frame: np.ndarray,
        roi_template: dict | None = None,
        ref_src: ReferenceSource = ReferenceSource.ICONS,
        *,                     # argumentos que ya no se usan
        save_root: Path | None = None,
        tag: str | None = None,
    ) -> {"blue": [...], "red": [...]}

La lógica de guardado de evidencias visuales se ha eliminado.
"""
from __future__ import annotations

import glob, json, os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

# ──────────────────────────── Servicios Riot ────────────────────────────
from services.riot_api.riot_versions import get_latest_version
from services.riot_api.riot_champions_images import (
    download_all_images,
    get_icons_path,
    get_splash_arts_path,
    get_loading_screens_path,
)

# ───────────────────────────── Enums & paths ────────────────────────────
class ReferenceSource(str, Enum):
    ICONS           = "icons"
    SPLASH_ARTS     = "splash_arts"
    LOADING_SCREENS = "loading_screens"


BASE_DIR = Path(__file__).resolve().parents[3]          # …/backend
ROI_ROOT = BASE_DIR / "services" / "live_game_analysis" / "roi_templates"

_SRC_TO_PATH_FN = {
    ReferenceSource.ICONS:           get_icons_path,
    ReferenceSource.SPLASH_ARTS:     get_splash_arts_path,
    ReferenceSource.LOADING_SCREENS: get_loading_screens_path,
}

# ──────────────────────── helpers ROI ──────────────────────────────────
Coordinate = Tuple[float, float]
Template   = Dict[str, List[Coordinate]]

def scale_points(points: List[Coordinate], fw: int, fh: int,
                 ref_size: Tuple[int, int] | None):
    if all(0.0 <= x <= 1.0 for x, y in points):
        return [(int(x * fw), int(y * fh)) for x, y in points]
    if ref_size is not None:
        rw, rh = ref_size
        sx, sy = fw / rw, fh / rh
        return [(int(x * sx), int(y * sy)) for x, y in points]
    return [(int(x), int(y)) for x, y in points]

def get_scaled_rois(tpl: Template, fw: int, fh: int):
    ref = tpl.get("reference_size")

    def bbox(pts):
        xs, ys = zip(*pts)
        return min(xs), min(ys), max(xs), max(ys)

    b1 = bbox(scale_points(tpl["team1ChampionsRoi"], fw, fh, ref))
    b2 = bbox(scale_points(tpl["team2ChampionsRoi"], fw, fh, ref))
    return b1, b2

def subdivide_roi(bbox, n=5):
    x1, y1, x2, y2 = bbox
    step = (x2 - x1) // n
    return [(x1 + i * step, y1,
             x1 + (i + 1) * step if i < n - 1 else x2, y2) for i in range(n)]

def load_roi_template(name: str = "champ_select_rois") -> Template:
    return json.loads((ROI_ROOT / f"{name}.json").read_text(encoding="utf-8"))

# ───────────────────── assets & detectores ──────────────────────────────
def normalize_name(n: str) -> str:
    return n.lower().split("_")[0]

def _ensure_refs_ready(src: ReferenceSource) -> Path:
    path = Path(_SRC_TO_PATH_FN[src]())
    if not any(path.iterdir()):
        print(f"↻ Descargando imágenes de Riot ({src.value})…")
        download_all_images(get_latest_version())
    return path

def load_reference_images(src: ReferenceSource):
    folder = _ensure_refs_ready(src)
    imgs = {}
    for fp in glob.glob(os.path.join(folder, "*")):
        if fp.lower().endswith((".png", ".jpg", ".jpeg")):
            name = normalize_name(Path(fp).stem)
            im = cv2.imread(fp)
            if im is not None:
                imgs[name] = im
    return imgs

def create_detectors():
    det = {}
    if hasattr(cv2, "SIFT_create"):  det["SIFT"]  = cv2.SIFT_create()
    if hasattr(cv2, "ORB_create"):   det["ORB"]   = cv2.ORB_create()
    if hasattr(cv2, "AKAZE_create"): det["AKAZE"] = cv2.AKAZE_create()
    if hasattr(cv2, "BRISK_create"): det["BRISK"] = cv2.BRISK_create()
    if hasattr(cv2, "KAZE_create"):  det["KAZE"]  = cv2.KAZE_create()
    try:
        det["SURF"] = cv2.xfeatures2d.SURF_create()
    except Exception:
        pass
    return det

_DETECTORS = create_detectors()

def resize_if_needed(img, flag):
    return cv2.resize(img, (100, 100)) if flag else img

# ───────────────────────── matching ─────────────────────────────────────
def _extract_and_match(det_name, detector, query, targets, *, top_k=5):
    kp_q, des_q = detector.detectAndCompute(query, None)
    if des_q is None or not kp_q:
        return []
    norm = cv2.NORM_L2 if det_name in ("SIFT", "SURF", "KAZE") else cv2.NORM_HAMMING
    matcher = cv2.BFMatcher(norm)
    out = []
    for name, img in targets.items():
        kp_t, des_t = detector.detectAndCompute(img, None)
        if des_t is None or not kp_t:
            continue
        pairs = matcher.knnMatch(des_q, des_t, k=2)
        good  = [m for p in pairs if len(p) == 2 for m, n in [p] if m.distance < 0.75 * n.distance]
        if good:
            out.append((name, len(good)))
    return sorted(out, key=lambda x: x[1], reverse=True)[:top_k]

# ─────────────────── función genérica principal ─────────────────────────
def _process_champion_select(det_name: str,
                             resize_bbox: bool,
                             resize_db: bool,
                             frame: np.ndarray,
                             roi_template: Template | None = None,
                             ref_src: ReferenceSource = ReferenceSource.ICONS,
                             *,
                             save_root: Path | None = None,  # se ignoran
                             tag: str | None = None          # se ignoran
                             ) -> Dict[str, List[str]]:
    if det_name not in _DETECTORS:
        raise ValueError(f"Detector {det_name} no disponible en OpenCV.")

    tpl = roi_template or load_roi_template()
    H, W = frame.shape[:2]
    b1, b2 = get_scaled_rois(tpl, W, H)
    boxes = subdivide_roi(b1, 5) + subdivide_roi(b2, 5)

    ref_imgs = {normalize_name(n): resize_if_needed(img, resize_db)
                for n, img in load_reference_images(ref_src).items()}
    detector = _DETECTORS[det_name]
    preds: List[str] = []

    for x1, y1, x2, y2 in boxes:
        patch = resize_if_needed(frame[y1:y2, x1:x2], resize_bbox)
        matches = _extract_and_match(det_name, detector, patch, ref_imgs)
        preds.append(matches[0][0] if matches else "?")

    return {"blue": preds[:5], "red": preds[5:]}

# ─────────────────── wrappers públicos autogenerados ────────────────────
_STRATS = {
    "resize_none":       (False, False),
    "resize_bbox_only":  (True,  False),
    "resize_db_only":    (False, True),
    "resize_both":       (True,  True),
}

globals_dict = globals()
for det_name in _DETECTORS:
    for strat_name, (rb, rd) in _STRATS.items():
        fn_name = f"process_champion_select_{det_name}_{strat_name}"

        def _factory(d=det_name, rb=rb, rd=rd):
            return lambda frame, roi_template=None, ref_src=ReferenceSource.ICONS, *, save_root=None, tag=None: (
                _process_champion_select(d, rb, rd, frame,
                                         roi_template, ref_src,
                                         save_root=save_root, tag=tag)
            )

        globals_dict[fn_name] = _factory()
        globals_dict[fn_name].__name__ = fn_name
        globals_dict[fn_name].__doc__ = (
            f"Detección champion-select con {det_name} | {strat_name}. "
            "Devuelve {'blue': […], 'red': […]}"
        )

# limpiar temporales del espacio global
del globals_dict, _factory, det_name, strat_name, rb, rd
