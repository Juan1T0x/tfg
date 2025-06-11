#!/usr/bin/env python3
# template_matcher_with_ranking_scaled.py
r"""Versión independiente de resolución del evaluador de *template-matching*.

• Escala los ROIs de champion-select al tamaño real del *screenshot*.
• Tolera coordenadas:
    – Normalizadas 0-1
    – En píxeles con `reference_size` (se reescalan)
    – En píxeles ya válidos para la imagen actual.
• Corrige el bug del `ValueError` en `extract_and_match` usando un bucle seguro
  sobre los pares devueltos por `knnMatch`.
"""

from __future__ import annotations
import os, glob, json
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

# ─────────────────────────────── Config ───────────────────────────────
BASE_DIR    = Path(__file__).parent
OUTPUT_ROOT = Path("output")
LOG_PATH    = OUTPUT_ROOT / "matching_ranking.log"

GROUND_TRUTH = {
    "blue": ["yorick", "pantheon", "taliyah", "kaisa", "rell"],
    "red":  ["ambessa", "vi", "ahri", "xayah", "rakan"],
}

RESIZE_SETTINGS = [
    (True,  False, "resize_bbox_only"),
    (False, True,  "resize_db_only"),
    (True,  True,  "resize_both"),
    (False, False, "resize_none"),
]

# ──────────────────────────── Utilidades ROIs ──────────────────────────
Coordinate = Tuple[float, float]
Template   = Dict[str, List[Coordinate]]


def scale_points(points: List[Coordinate], fw: int, fh: int,
                 ref_size: Tuple[int, int] | None) -> List[Tuple[int, int]]:
    """Convierte *points* a píxeles absolutos del frame (fw×fh)."""
    if all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in points):
        return [(int(x * fw), int(y * fh)) for x, y in points]

    if ref_size is not None:
        ref_w, ref_h = ref_size
        sx, sy = fw / ref_w, fh / ref_h
        return [(int(x * sx), int(y * sy)) for x, y in points]

    return [(int(x), int(y)) for x, y in points]


def get_scaled_rois(template: Template, fw: int, fh: int):
    """Devuelve los bounding-boxes escalados de los dos ROIs de campeones."""
    ref = template.get("reference_size")

    def bbox(pts):
        xs, ys = zip(*pts); return min(xs), min(ys), max(xs), max(ys)

    b1 = bbox(scale_points(template["team1ChampionsRoi"], fw, fh, ref))
    b2 = bbox(scale_points(template["team2ChampionsRoi"], fw, fh, ref))
    return b1, b2


# ────────────────────────────── Otros helpers ──────────────────────────

def load_roi_templates(folder: str):
    return {Path(fp).stem: json.load(open(fp, "r", encoding="utf-8"))
            for fp in glob.glob(os.path.join(folder, "*.json"))}


def subdivide_roi(bbox, subdivisions: int = 5):
    x1, y1, x2, y2 = bbox
    width  = x2 - x1
    sub_w  = width // subdivisions
    return [(x1 + i * sub_w, y1, x1 + (i + 1) * sub_w if i < subdivisions - 1 else x2, y2)
            for i in range(subdivisions)]


def load_champion_images(folder: str):
    imgs = {}
    for fp in glob.glob(os.path.join(folder, "*")):
        if fp.lower().endswith((".png", ".jpg", ".jpeg")):
            name = Path(fp).stem.split("_")[0].lower()
            im   = cv2.imread(fp)
            if im is not None:
                imgs[name] = im
    return imgs


def normalize_name(n: str) -> str:
    return n.lower().split("_")[0]


def resize_if_needed(img, flag: bool):
    return cv2.resize(img, (100, 100)) if flag else img


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


# ───────────────────── Safe matching (bugfix incluido) ─────────────────────

def extract_and_match(det_name: str, detector, query, targets):
    """Devuelve los 5 mejores matches [(nombre, score)]."""
    kp_q, des_q = detector.detectAndCompute(query, None)
    if des_q is None or not kp_q:
        return []

    norm = cv2.NORM_L2 if det_name in ("SIFT", "SURF", "KAZE") else cv2.NORM_HAMMING
    bf   = cv2.BFMatcher(norm)
    out  = []

    for name, img in targets.items():
        kp_t, des_t = detector.detectAndCompute(img, None)
        if des_t is None or not kp_t:
            continue
        try:
            pairs = bf.knnMatch(des_q, des_t, k=2)
            good  = []
            for pair in pairs:
                if len(pair) < 2:  # evita ValueError cuando solo hay un match
                    continue
                m, n = pair
                if m.distance < 0.75 * n.distance:
                    good.append(m)
            out.append((name, len(good)))
        except cv2.error:
            continue

    return sorted(out, key=lambda x: x[1], reverse=True)[:5]


# ─────────────────────────────── Programa principal ───────────────────────────────

def main():
    OUTPUT_ROOT.mkdir(exist_ok=True)

    screenshot = cv2.imread("screenshot.png")
    if screenshot is None:
        raise FileNotFoundError("screenshot.png no encontrado")
    H, W = screenshot.shape[:2]

    templates = load_roi_templates("../roi/templates/output")
    tpl = templates["champ_select_rois"]

    b1, b2 = get_scaled_rois(tpl, W, H)
    boxes  = subdivide_roi(b1, 5) + subdivide_roi(b2, 5)
    gt     = GROUND_TRUTH["blue"] + GROUND_TRUTH["red"]

    detectors = create_detectors()
    sources   = {
        "icons":           load_champion_images("../assets/images/icons"),
        "loading_screens": load_champion_images("../assets/images/loading_screens"),
        "splash_arts":     load_champion_images("../assets/images/splash_arts"),
    }

    detailed: List[Tuple[str, str, str, int, int]] = []

    for src, champ_imgs in sources.items():
        print(f"\n=== Procesando fuente: {src} ===")
        for resize_bbox, resize_db, strat in RESIZE_SETTINGS:
            print(f"\n  Estrategia: {strat}")
            db_imgs = {normalize_name(n): resize_if_needed(img, resize_db) for n, img in champ_imgs.items()}
            scores  = {d: {"top1": 0, "top5": 0} for d in detectors}

            for idx, (x1, y1, x2, y2) in enumerate(boxes):
                if idx >= len(gt):
                    break
                patch  = screenshot[y1:y2, x1:x2]
                patch  = resize_if_needed(patch, resize_bbox)
                target = gt[idx]

                for det_name, det in detectors.items():
                    preds = [normalize_name(n) for n, _ in extract_and_match(det_name, det, patch, db_imgs)]
                    if preds:
                        if preds[0] == target:
                            scores[det_name]["top1"] += 1
                        if target in preds:
                            scores[det_name]["top5"] += 1

            for det_name, sc in scores.items():
                print(f"    {det_name}: top1 = {sc['top1']}, top5 = {sc['top5']}")
                detailed.append((src, strat, det_name, sc['top1'], sc['top5']))

    detailed.sort(key=lambda x: (x[3], x[4]), reverse=True)

    with LOG_PATH.open("w", encoding="utf-8") as log:
        print("\n=== Ranking global: ===\n")
        log.write("Ranking global (fuente,estrategia,detector: top1,top5)\n\n")
        for i, (src, strat, det, t1, t5) in enumerate(detailed, 1):
            line = f"{i:2d}. {src} | {strat} | {det}: top1={t1}, top5={t5}"
            print(line)
            log.write(line + "\n")

    print(f"\n✔ Ranking global guardado en: {LOG_PATH.resolve()}")


if __name__ == "__main__":
    main()
