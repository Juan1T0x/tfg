#!/usr/bin/env python3
# extract_red_health_features.py
"""
Extrae características básicas de red_health.png y las guarda en JSON.

Uso:
    python extract_red_health_features.py \
        --img   assets/images/health_bars/red_health.png \
        --out   output/red_health_features.json
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import cv2
import numpy as np

# ────────────────────────── utilidades color ──────────────────────────
def hsv_stats(img_hsv: np.ndarray, mask: np.ndarray):
    masked = img_hsv[mask > 0]
    out    = {}
    for i, ch in enumerate("hsv"):
        arr = masked[:, i].astype(np.float32)
        out[f"{ch}_mean"] = float(arr.mean())
        out[f"{ch}_std"]  = float(arr.std())
    return out

def hsv_histogram(img_hsv: np.ndarray, mask: np.ndarray, bins=8):
    h, s, v = cv2.split(img_hsv)
    sample  = np.stack([h[mask > 0], s[mask > 0], v[mask > 0]], axis=1)
    hist, _ = np.histogramdd(
        sample,
        bins=(bins, bins, bins),
        range=((0, 180), (0, 256), (0, 256)),
        density=True,
    )
    return hist.flatten().round(6).tolist()

# ────────────────────────── utilidades ORB ────────────────────────────
def orb_signature(img_bgr: np.ndarray, mask: np.ndarray, max_kp=128):
    orb = cv2.ORB_create(max_kp)
    kp, des = orb.detectAndCompute(img_bgr, mask)
    if des is None:
        return [], []
    pts = [(int(k.pt[0]), int(k.pt[1]), k.size, k.angle) for k in kp]
    return pts, des.astype(int).tolist()

# ───────────────────────────── main ─────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img",  required=True, help="ruta a red_health.png")
    ap.add_argument("--out",  required=True, help="JSON de salida")
    ap.add_argument("--auxdir", default="output", help="carpeta para miniaturas/máscara")
    args = ap.parse_args()

    img_path = Path(args.img)
    out_path = Path(args.out)
    aux_dir  = Path(args.auxdir); aux_dir.mkdir(exist_ok=True)

    img_bgr = cv2.imread(str(img_path))
    if img_bgr is None:
        raise FileNotFoundError(img_path)

    h, w = img_bgr.shape[:2]
    hsv  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # Máscara rápida del rojo: H 0–10 ∪ 170–180 con S,V > 50
    mask = cv2.inRange(hsv, (0, 50, 50), (10, 255, 255))
    mask |= cv2.inRange(hsv, (170, 50, 50), (180, 255, 255))
    mask  = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    # Bounding box y geometría
    ys, xs = np.where(mask > 0)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    w_roi, h_roi   = x1 - x0 + 1, y1 - y0 + 1
    ar             = w_roi / h_roi

    data = {
        "geometry": {
            "full_size": [w, h],
            "bbox": [x0, y0, x1, y1],
            "bbox_wh": [w_roi, h_roi],
            "aspect_ratio": round(ar, 3),
            "area_px": int(mask.sum() / 255),
        },
        "color": {
            **hsv_stats(hsv, mask),
            "hsv_hist_8x8x8": hsv_histogram(hsv, mask),
        },
    }

    # ORB keypoints + descriptores
    kp, des = orb_signature(img_bgr, mask)
    data["orb"] = {"keypoints": kp, "descriptors": des}

    # Archivos auxiliares
    thumb     = cv2.resize(img_bgr, (100, int(100 * h / w)), cv2.INTER_AREA)
    mask_rgb  = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    cv2.imwrite(str(aux_dir / "red_bar_thumb.png"), thumb)
    cv2.imwrite(str(aux_dir / "red_bar_mask.png"),  mask_rgb)

    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print("✔ Características guardadas en:", out_path.resolve())
    print("   Miniatura:", aux_dir / "red_bar_thumb.png")
    print("   Máscara  :", aux_dir / "red_bar_mask.png")

if __name__ == "__main__":
    main()
