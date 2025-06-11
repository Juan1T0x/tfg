#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detecta **barras AZULES** (health bars de aliados) **dentro de los polígonos
ROI** definidos en un fichero JSON de plantilla.

Ahora **NO se aplica ningún filtrado ni fusión**: se genera un
rectángulo por **cada contorno** que cumpla el área mínima y se imprime su
ancho, alto, posición y relación de aspecto. Todos los rectángulos se dibujan
sobre la imagen con esa misma información en forma de etiqueta.
"""
from __future__ import annotations
import cv2, json, argparse, numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# ───────── Constantes de calibración (referencia 1920×1080) ─────────
REF_W, REF_H = 1920, 1080
BLUE_HSV_LIST = [
    (np.array([95, 50, 50]), np.array([125, 255, 255]), 300)  # low, high, área_ref
]

# ───────── Tipos ─────────
Coord = Tuple[float, float]
BRect = Tuple[int, int, int, int]  # x,y,w,h

# ───────── Utilidades plantilla ─────────

def load_rois(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text("utf-8"))

def scale_pts(pts: List[Coord], W: int, H: int, ref: Optional[Tuple[int,int]]):
    if ref:
        rw, rh = ref; sx, sy = W / rw, H / rh
        return [(int(x * sx), int(y * sy)) for x, y in pts]
    if all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts):
        return [(int(x * W), int(y * H)) for x, y in pts]
    return [(int(x), int(y)) for x, y in pts]

def bbox(pts: List[Coord]):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

# ───────── Detección de barras en un recorte ─────────

def detectar_barras(crop: np.ndarray,
                    hsv_ranges: List[Tuple[np.ndarray, np.ndarray, int]],
                    area_scale: float) -> List[BRect]:
    """Devuelve TODAS las bounding-boxes detectadas (sin filtros ni fusión)."""
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    # Debug: mostrar el HSV del recorte
    cv2.imshow("HSV Crop", hsv)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    rects: List[BRect] = []
    for low, up, area_ref in hsv_ranges:
        area_thr = int(round(area_ref * area_scale))
        mask = cv2.inRange(hsv, low, up)

        # Debug: mostrar la máscara
        cv2.imshow("Mask", mask)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        k = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

        # Debug: mostrar la máscara después de morfología
        cv2.imshow("Mask Morphology", mask)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            if cv2.contourArea(c) < area_thr:
                continue
            x, y, w, h = cv2.boundingRect(c)
            rects.append((x, y, w, h))
    return rects

# ───────── Visual helpers ─────────

def screen_res(default=(1920,1080)):
    try:
        import tkinter as tk; r=tk.Tk(); r.withdraw(); w,h=r.winfo_screenwidth(),r.winfo_screenheight(); r.destroy(); return w,h
    except Exception:
        return default

def show_full(win: str, img: np.ndarray):
    w, h = screen_res(); cv2.namedWindow(win, cv2.WINDOW_NORMAL); cv2.resizeWindow(win, w, h); cv2.moveWindow(win, 0, 0); cv2.imshow(win, img)

# ───────── main ─────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image",    required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--output",   default="blue_bars_all_rects.png")
    args = ap.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(args.image)
    H, W = frame.shape[:2]
    tpl = load_rois(Path(args.template))
    ref = tpl.get("reference_size")

    area_scale = (W*H) / (REF_W*REF_H)

    out = frame.copy()
    font, fscale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1

    for name, pts in tpl.items():
        if name == "reference_size":
            continue
        sc = scale_pts(pts, W, H, ref)
        x0, y0, x1, y1 = bbox(sc)
        crop = frame[y0:y1, x0:x1]

        rects = detectar_barras(crop, BLUE_HSV_LIST, area_scale)
        if not rects:
            print(f"[{name}] → sin rectángulos detectados")
            continue

        print(f"=== ROI: {name} ===")
        for i, (bx, by, bw, bh) in enumerate(rects, 1):
            ax, ay = x0 + bx, y0 + by
            ar = bw / bh if bh else 0
            label = f"{name}-{i} | {bw}×{bh}px | ({ax},{ay}) | AR={ar:.2f}"
            print(label)
            cv2.rectangle(out, (ax, ay), (ax+bw, ay+bh), (255,0,0), 2)
            (tw, th), _ = cv2.getTextSize(label, font, fscale, thick)
            ty = ay - 5 if ay - th - 5 >= 0 else ay + bh + th + 5
            cv2.putText(out, label, (ax, ty), font, fscale, (255,0,0), thick, cv2.LINE_AA)

        # dibuja contorno del ROI
        cv2.polylines(out, [np.array(sc)], True, (0,255,0), 1)

    show_full("Todos los rectángulos de barras azules", out)
    cv2.waitKey(0); cv2.destroyAllWindows()

    if args.output:
        cv2.imwrite(args.output, out)
        print(f"Resultado guardado en {args.output}")


if __name__ == "__main__":
    main()