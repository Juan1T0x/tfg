#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detecta **barras AZULES** (health bars de aliados) dentro de los polígonos ROI
indicados en un JSON de plantilla.

Se conserva y dibuja **sólo** el contorno que cumpla:
    • Área ≥ área_mínima (escalada a la resolución actual)
    • h < 0.7 · w  (rectángulo muy alargado)
    • 3.5 ≤ (w / h) ≤ 6.5  (relación de aspecto típica de las barras)

Para cada barra aceptada se imprime por consola:
    ROI‑id | WxHpx | (x,y) | AR=…
y se dibuja sobre la captura con la misma etiqueta.
"""
from __future__ import annotations
import cv2, json, argparse, numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# ───────── Constantes base ─────────
REF_W, REF_H = 1920, 1080
BLUE_HSV_LIST = [  # (HSV_low, HSV_high, area_ref en píxeles² a 1920×1080)
    (np.array([95, 50, 50]), np.array([125, 255, 255]), 300)
]
ELONG_RATIO  = 0.7           # h < 0.7·w  → barra alargada
AR_MIN, AR_MAX = 3.5, 6.5    # relación de aspecto aceptada

# ───────── Tipos y helpers ROI ─────────
Coord = Tuple[float,float]
BRect = Tuple[int,int,int,int]

def load_rois(p:Path)->Dict[str,Any]:
    return json.loads(p.read_text("utf-8"))

def scale_pts(pts:List[Coord], W:int, H:int, ref:Optional[Tuple[int,int]]):
    if ref:
        rw,rh=ref; sx,sy=W/rw, H/rh
        return [(int(x*sx), int(y*sy)) for x,y in pts]
    if all(0<=x<=1 and 0<=y<=1 for x,y in pts):
        return [(int(x*W), int(y*H)) for x,y in pts]
    return [(int(x),int(y)) for x,y in pts]

def bbox(pts:List[Coord]):
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys)

# ───────── Detección de barras filtrada ─────────

def detectar_barras(crop:np.ndarray,
                    hsv_ranges:List[Tuple[np.ndarray,np.ndarray,int]],
                    area_scale:float)->List[BRect]:
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    rects:List[BRect]=[]
    for low,up,area_ref in hsv_ranges:
        area_thr=int(round(area_ref*area_scale))
        mask=cv2.inRange(hsv,low,up)
        k=np.ones((3,3),np.uint8)
        mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,k)
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,k)
        cnts,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            if cv2.contourArea(c)<area_thr:  # filtro área mínima
                continue
            x,y,w,h=cv2.boundingRect(c)
            if h>=ELONG_RATIO*w:
                continue                    # no suficientemente alargado
            ar=w/h
            if not (AR_MIN<=ar<=AR_MAX):
                continue                    # AR fuera de rango
            rects.append((x,y,w,h))
    return rects

# ───────── Visual helpers ─────────

def screen_res(default=(1920,1080)):
    try:
        import tkinter as tk; r=tk.Tk(); r.withdraw(); w,h=r.winfo_screenwidth(),r.winfo_screenheight(); r.destroy(); return w,h
    except Exception:
        return default

def show_full(win:str, img:np.ndarray):
    w,h=screen_res(); cv2.namedWindow(win,cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win,w,h); cv2.moveWindow(win,0,0); cv2.imshow(win,img)

# ───────── main ─────────

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--image",required=True)
    ap.add_argument("--template",required=True)
    ap.add_argument("--output",default="blue_bars_filtered.png")
    args=ap.parse_args()

    frame=cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(args.image)
    H,W=frame.shape[:2]

    tpl=load_rois(Path(args.template)); ref=tpl.get("reference_size")
    area_scale=(W*H)/(REF_W*REF_H)

    out=frame.copy(); font,fscale,thick=cv2.FONT_HERSHEY_SIMPLEX,0.45,1

    for name,pts in tpl.items():
        if name=="reference_size": continue
        sc=scale_pts(pts,W,H,ref); x0,y0,x1,y1=bbox(sc); crop=frame[y0:y1,x0:x1]
        rects=detectar_barras(crop,BLUE_HSV_LIST,area_scale)
        if not rects:
            print(f"[{name}] → sin barras válidas"); continue
        for i,(bx,by,bw,bh) in enumerate(rects,1):
            ax,ay=x0+bx, y0+by; ar=bw/bh
            label=f"{name}-{i} | {bw}×{bh}px | ({ax},{ay}) | AR={ar:.2f}"
            print(label)
            cv2.rectangle(out,(ax,ay),(ax+bw,ay+bh),(255,0,0),2)
            (tw,th),_=cv2.getTextSize(label,font,fscale,thick)
            ty=ay-5 if ay-th-5>=0 else ay+bh+th+5
            cv2.putText(out,label,(ax,ty),font,fscale,(255,0,0),thick,cv2.LINE_AA)
        cv2.polylines(out,[np.array(sc)],True,(0,255,0),1)

    show_full("Barras azules filtradas", out)
    cv2.waitKey(0); cv2.destroyAllWindows()

    if args.output:
        cv2.imwrite(args.output,out)
        print(f"Resultado guardado en {args.output}")

if __name__=="__main__":
    main()
