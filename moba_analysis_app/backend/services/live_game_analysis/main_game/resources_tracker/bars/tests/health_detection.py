# -*- coding: utf-8 -*-
"""
Detecta barras VERDES (vida) y **guarda todas las etapas** del proceso,
etiquetando cada archivo como “health” para identificar el algoritmo:

    • <timestamp>_health_<team>_crop.png
    • <timestamp>_health_<team>_mask0_hsv.png
    • <timestamp>_health_<team>_mask1_open.png
    • <timestamp>_health_<team>_mask2_close.png
    • healthbars_detected_<timestamp>.jpg          ← resultado final

Ejemplo:
    python detect_healthbars.py --frame source.jpg --rois rois.json
"""
import json
import cv2
import numpy as np
import argparse
from pathlib import Path
from datetime import datetime

# ───────── Configuración ─────────
LOWER_GREEN = np.array([30, 40, 40])
UPPER_GREEN = np.array([80, 250, 250])
AREA_MIN    = 300
ELONG_RATIO = 0.5

ROLE_LABELS = ["vida top", "vida jungle", "vida mid", "vida bot", "vida support"]

# ───────── Utilidades ─────────
def load_rois(template_path: Path):
    with template_path.open("r", encoding="utf-8") as f:
        tpl = json.load(f)
    return {
        "team1": tpl["team1ChampionsResourcesRoi"],
        "team2": tpl["team2ChampionsResourcesRoi"],
    }, tpl.get("reference_size")


def scale_points(pts, W, H, ref):
    if all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts):
        return [(int(x*W), int(y*H)) for x, y in pts]
    if ref:
        rw, rh = ref
        return [(int(x*W/rw), int(y*H/rh)) for x, y in pts]
    return [(int(x), int(y)) for x, y in pts]


def bounds(pts):
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


def detectar_barras(crop, out_prefix):
    hsv   = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask0 = cv2.inRange(hsv, LOWER_GREEN, UPPER_GREEN)
    cv2.imwrite(f"{out_prefix}_mask0_hsv.png", mask0)

    k = np.ones((3, 3), np.uint8)
    mask1 = cv2.morphologyEx(mask0, cv2.MORPH_OPEN,  k)
    cv2.imwrite(f"{out_prefix}_mask1_open.png", mask1)

    mask2 = cv2.morphologyEx(mask1, cv2.MORPH_CLOSE, k)
    cv2.imwrite(f"{out_prefix}_mask2_close.png", mask2)

    cnts, _ = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > AREA_MIN]
    return [(x, y, w, h) for x, y, w, h in rects if h < ELONG_RATIO * w]


# ───────── Programa principal ─────────
def main():
    ap = argparse.ArgumentParser(description="Detección paso a paso de barras de vida.")
    ap.add_argument("--frame", required=True, help="Imagen a analizar.")
    ap.add_argument("--rois",  required=True, help="JSON de ROIs.")
    args = ap.parse_args()

    frame = cv2.imread(args.frame)
    if frame is None:
        print("❌ No se pudo cargar la imagen.")
        return

    H, W = frame.shape[:2]
    rois_raw, ref_size = load_rois(Path(args.rois))
    scaled = {k: scale_points(v, W, H, ref_size) for k, v in rois_raw.items()}
    boxes  = {k: bounds(v) for k, v in scaled.items()}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    detections, full_w = {"azul": [], "rojo": []}, {}

    for idx, (key, (x0, y0, x1, y1)) in enumerate(boxes.items(), 1):
        team = "azul" if idx == 1 else "rojo"
        crop = frame[y0:y1, x0:x1]

        base = f"{ts}_health_{team}"
        cv2.imwrite(f"{base}_crop.png", crop)

        rects = detectar_barras(crop, base)
        for x, y, w, h in rects:
            gx, gy = x + x0, y + y0
            detections[team].append((gy, gx, w, h))
            cv2.rectangle(frame, (gx, gy), (gx+w, gy+h), (0, 255, 0), 2)
        cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 165, 255), 2)
        full_w[team] = max((w for _, _, w, _ in detections[team]), default=None)

    # Consola
    for team in ("azul", "rojo"):
        print(f"\nROI equipo {team}:")
        rows = sorted(detections[team], key=lambda t: t[0])
        for i, label in enumerate(ROLE_LABELS):
            if i < len(rows):
                y, x, w, h = rows[i]
                pct = f"{(w/full_w[team]*100):5.1f}%" if full_w[team] else " ?.?%"
                print(f"    {label:<12}: (x={x}, y={y}, w={w}, h={h}) → {pct}")
            else:
                print(f"    {label:<12}: no detectado →  ?.?%")

    final_name = f"healthbars_detected_{ts}.jpg"
    cv2.imwrite(final_name, frame)
    print(f"\n✔ Resultado final guardado en: {final_name}")

    cv2.imshow("Barras de vida (verde)", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
