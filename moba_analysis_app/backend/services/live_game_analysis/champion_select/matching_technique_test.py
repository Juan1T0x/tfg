#!/usr/bin/env python3
# template_matcher_with_ranking_scaled.py
"""
Template-matching sobre champion-select con generación de evidencias y
medición de tiempos.

• Escala los ROIs al tamaño real del screenshot.
• Calcula el ranking top-1 / top-5 para detector × estrategia × fuente.
• Guarda las 5 mejores comparaciones por ROI en:

    results/<fuente>/<detector>/<estrategia>/<campeón_gt>/<pred>.png
• Registra en log el tiempo total empleado por cada combinación.
"""
from __future__ import annotations
import os, glob, json, time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

# ───────────────────────────── Configuración ────────────────────────────
BASE_DIR    = Path(__file__).parent
OUTPUT_ROOT = BASE_DIR / "results"
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

# ───────────────────────── Utilidades ROIs ──────────────────────────────
Coordinate = Tuple[float, float]
Template   = Dict[str, List[Coordinate]]

def scale_points(points: List[Coordinate], fw: int, fh: int,
                 ref_size: Tuple[int, int] | None):
    if all(0 <= x <= 1 and 0 <= y <= 1 for x, y in points):
        return [(int(x * fw), int(y * fh)) for x, y in points]
    if ref_size is not None:
        rw, rh = ref_size
        sx, sy = fw / rw, fh / rh
        return [(int(x * sx), int(y * sy)) for x, y in points]
    return [(int(x), int(y)) for x, y in points]

def get_scaled_rois(tpl: Template, fw: int, fh: int):
    ref = tpl.get("reference_size")
    def bbox(pts): xs, ys = zip(*pts); return min(xs), min(ys), max(xs), max(ys)
    b1 = bbox(scale_points(tpl["team1ChampionsRoi"], fw, fh, ref))
    b2 = bbox(scale_points(tpl["team2ChampionsRoi"], fw, fh, ref))
    return b1, b2

def subdivide_roi(bbox, n=5):
    x1, y1, x2, y2 = bbox
    step = (x2 - x1) // n
    return [(x1 + i*step, y1,
             x1 + (i+1)*step if i < n-1 else x2, y2) for i in range(n)]

def load_roi_templates(folder: str):
    return {Path(fp).stem: json.load(open(fp, encoding="utf-8"))
            for fp in glob.glob(os.path.join(folder, "*.json"))}

# ───────────────────── Assets & detectores ──────────────────────────────
def normalize_name(n: str) -> str:
    return n.lower().split("_")[0]

def load_champion_images(folder: str):
    imgs = {}
    for fp in glob.glob(os.path.join(folder, "*")):
        if fp.lower().endswith((".png", ".jpg", ".jpeg")):
            name = normalize_name(Path(fp).stem)
            im   = cv2.imread(fp)
            if im is not None:
                imgs[name] = im
    return imgs

def resize_if_needed(img, flag):
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

# ────────── Safe matching (devuelve good matches opcionalmente) ─────────
def extract_and_match(det_name: str, detector, query, targets, *, want_matches=False):
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
        except cv2.error:
            continue
        good = []
        for pair in pairs:
            if len(pair) < 2:
                continue
            m, n = pair
            if m.distance < 0.75 * n.distance:
                good.append(m)
        if good:
            out.append((name, len(good), good if want_matches else None, kp_t))
    return sorted(out, key=lambda x: x[1], reverse=True)[:5]

# ────────────────────────── Programa principal ──────────────────────────
def main():
    OUTPUT_ROOT.mkdir(exist_ok=True)
    screenshot = cv2.imread("screenshot.png")
    if screenshot is None:
        raise FileNotFoundError("screenshot.png no encontrado")
    H, W = screenshot.shape[:2]

    templates = load_roi_templates("../roi_templates")
    tpl = templates["champ_select_rois"]

    b1, b2 = get_scaled_rois(tpl, W, H)
    boxes  = subdivide_roi(b1, 5) + subdivide_roi(b2, 5)
    gt     = GROUND_TRUTH["blue"] + GROUND_TRUTH["red"]

    detectors = create_detectors()
    sources   = {
        "icons":           load_champion_images("../../assets/images/icons"),
        "loading_screens": load_champion_images("../../assets/images/loading_screens"),
        "splash_arts":     load_champion_images("../../assets/images/splash_arts"),
    }

    detailed: List[Tuple[str, str, str, int, int, float]] = []

    # ─── bucle fuentes/estrategias/detectores ───────────────────────────
    for src_name, champ_imgs_full in sources.items():
        print(f"\n=== Fuente: {src_name} ===")
        for resize_bbox, resize_db, strat in RESIZE_SETTINGS:
            print(f"\n  Estrategia: {strat}")
            champ_imgs = {n: resize_if_needed(im, resize_db)
                          for n, im in champ_imgs_full.items()}

            scores = {d: {"top1": 0, "top5": 0} for d in detectors}
            times  = {d: 0.0 for d in detectors}

            for idx, (x1, y1, x2, y2) in enumerate(boxes):
                if idx >= len(gt):
                    break
                target = gt[idx]
                patch  = resize_if_needed(screenshot[y1:y2, x1:x2], resize_bbox)

                for det_name, det in detectors.items():
                    t0 = time.perf_counter()
                    preds = extract_and_match(det_name, det, patch,
                                              champ_imgs, want_matches=False)
                    times[det_name] += time.perf_counter() - t0

                    pred_names = [p[0] for p in preds]
                    if pred_names:
                        if pred_names[0] == target:
                            scores[det_name]["top1"] += 1
                        if target in pred_names:
                            scores[det_name]["top5"] += 1

                    # ─── evidencias visuales ─────────────────────────
                    out_base = (OUTPUT_ROOT / src_name / det_name.lower() /
                                strat / target)
                    out_base.mkdir(parents=True, exist_ok=True)

                    preds_full = extract_and_match(det_name, det, patch,
                                                   champ_imgs, want_matches=True)
                    kp_q, _ = det.detectAndCompute(patch, None)
                    for rank, (cand, _, good, kp_t) in enumerate(preds_full, 1):
                        ref_img = champ_imgs[cand]
                        vis = cv2.drawMatches(patch, kp_q,
                                              ref_img, kp_t,
                                              good or [], None,
                                              flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
                        cv2.imwrite(str(out_base / f"{cand}_{rank}.png"), vis)

            # ─── métricas y tiempo ────────────────────────────────────
            for det_name, sc in scores.items():
                t_sec = times[det_name]
                print(f"    {det_name}: top1={sc['top1']:<2} "
                      f"top5={sc['top5']:<2}  t={t_sec:6.3f}s")
                detailed.append((src_name, strat, det_name,
                                 sc["top1"], sc["top5"], t_sec))

    # ─── ranking global — log -------------------------------------------
    detailed.sort(key=lambda x: (x[3], x[4]), reverse=True)
    with LOG_PATH.open("w", encoding="utf-8") as log:
        header = "fuente | estrategia | detector : top1, top5, tiempo(s)\n"
        print("\n=== Ranking global ===\n")
        log.write(header)
        for i, (src, strat, det, t1, t5, t) in enumerate(detailed, 1):
            line = f"{i:2d}. {src} | {strat} | {det}: {t1},{t5}, {t:.3f}"
            print(line)
            log.write(line + "\n")

    print(f"\n✔ Evidencias y ranking guardados en: {OUTPUT_ROOT.resolve()}")


if __name__ == "__main__":
    main()
