#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detecta **barras ROJAS** (health bars de enemigos) dentro de los polígonos ROI
especificados por una plantilla JSON.

Para cada contorno que supere un **área mínima** (escalada a la resolución
actual) se calcula su bounding‑box y se imprime:

    ROI‑id‑n | WxHpx | (x,y) | AR=… | R=rango_id

* `AR`  → relación de aspecto (ancho / alto)
* `R`   → índice de la ventana HSV que lo detectó (0‑5, ver `RED_HSV_LIST`)

El rectángulo se dibuja en rojo y la etiqueta se muestra sobre la imagen.

NO hay fusión ni filtros extra: cada contorno válido se reporta tal cual.
"""
from __future__ import annotations
import cv2, json, argparse, numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# ───────── Parámetros base ─────────
REF_W, REF_H = 1920, 1080  # resolución de referencia para area_ref

# Ventanas HSV (rojo)  – enumeradas R0…R5
RED_HSV_LIST = [
    (np.array([0,  10,  40]), np.array([20, 255, 200]),200),      # R0 rojo tenue 
    (np.array([  0,  50,  80]), np.array([ 10, 255, 255]), 300),  # R1 rojo vivo
    (np.array([ 10,  40,  70]), np.array([ 20, 255, 255]), 300),  # R2 anaranjado
    (np.array([  0,  25,  40]), np.array([ 10, 150, 200]), 300),  # R3 tenue oscuro
    (np.array([ 10,  25,  40]), np.array([ 20, 150, 200]), 300),  # R4 tenue naranja
    (np.array([160,  50,  80]), np.array([179, 255, 255]), 300),  # R5 rojo extremo
    (np.array([160,  25,  40]), np.array([179, 150, 200]), 300),  # R6 extremo tenue
]

Coord = Tuple[float, float]
BRectR = Tuple[int, int, int, int, int]  # x,y,w,h,rango_id

# ───────── Helpers plantilla ─────────

def load_rois(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text("utf-8"))

def scale_pts(pts: List[Coord], W: int, H: int, ref: Optional[Tuple[int,int]]):
    if ref:
        rw, rh = ref; sx, sy = W / rw, H / rh
        return [(int(x*sx), int(y*sy)) for x, y in pts]
    if all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts):
        return [(int(x*W), int(y*H)) for x, y in pts]
    return [(int(x), int(y)) for x, y in pts]

def bbox(pts: List[Coord]):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

# ───────── Detección sin fusión ─────────

def detectar_rects(crop: np.ndarray, area_scale: float) -> List[BRectR]:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    out: List[BRectR] = []
    for rid, (low, up, area_ref) in enumerate(RED_HSV_LIST):
        thr = int(round(area_ref * area_scale))
        mask = cv2.inRange(hsv, low, up)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            if cv2.contourArea(c) < thr:
                continue
            x, y, w, h = cv2.boundingRect(c)
            out.append((x, y, w, h, rid))
    return out

# ───────── Visual helpers ─────────

def screen_res(default=(1920,1080)):
    try:
        import tkinter as tk; r = tk.Tk(); r.withdraw()
        w, h = r.winfo_screenwidth(), r.winfo_screenheight(); r.destroy(); return w, h
    except Exception:
        return default

def show_full(win: str, img: np.ndarray):
    w, h = screen_res(); cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, w, h); cv2.moveWindow(win, 0, 0)
    cv2.imshow(win, img)

# ───────── main ─────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image",    required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--output",   default="red_bars_ranges.png")
    args = ap.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(args.image)
    H, W = frame.shape[:2]

    tpl = load_rois(Path(args.template))
    ref = tpl.get("reference_size")
    area_scale = (W * H) / (REF_W * REF_H)

    out = frame.copy(); font, fscale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1

    for roi, pts in tpl.items():
        if roi == "reference_size":
            continue
        sc = scale_pts(pts, W, H, ref)
        x0, y0, x1, y1 = bbox(sc)
        rects = detectar_rects(frame[y0:y1, x0:x1], area_scale)
        if not rects:
            print(f"[{roi}] sin barras")
            continue
        for i, (bx, by, bw, bh, rid) in enumerate(rects, 1):
            ax, ay = x0 + bx, y0 + by; ar = bw / bh
            label = f"{roi}-{i} | {bw}×{bh}px | ({ax},{ay}) | AR={ar:.2f} | R={rid}"
            print(label)
            cv2.rectangle(out, (ax, ay), (ax + bw, ay + bh), (0, 0, 255), 2)
            (tw, th), _ = cv2.getTextSize(label, font, fscale, thick)
            ty = ay - 5 if ay - th - 5 >= 0 else ay + bh + th + 5
            cv2.putText(out, label, (ax, ty), font, fscale, (0, 0, 255), thick, cv2.LINE_AA)
        cv2.polylines(out, [np.array(sc)], True, (0, 255, 0), 1)

    show_full("Barras rojas (rango HSV)", out)
    cv2.waitKey(0); cv2.destroyAllWindows()

    cv2.imwrite(args.output, out)
    print("Guardado", args.output)

if __name__ == "__main__":
    main()
