#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detecta **barras ROJAS** dentro de los ROIs y las agrupa según el tamaño:

* **Grandes** (`w ≥ 90 px`) ⇒ se conservan tal cual.
* **Pequeños** (`w < 90 px`) ⇒ se fusionan si hay al menos **2** a
  ≤ 150 px horizontal y ≤ 15 px vertical; si quedan aislados se descartan.

Cada barra final se imprime con su bounding‑box, AR, rango HSV y color medio
(H,S,V), y se dibuja sobre la captura.
"""
from __future__ import annotations
import cv2, json, argparse, numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# ───────── Constantes ─────────
REF_W, REF_H = 1920, 1080
RED_HSV_LIST = [  # rangos R0‑R7
    (np.array([  0,  10,  40]), np.array([ 20, 255, 200]), 200),
    (np.array([  0,  50,  80]), np.array([ 10, 255, 255]), 300),
    (np.array([ 10,  40,  70]), np.array([ 20, 255, 255]), 300),
    (np.array([  0,  25,  40]), np.array([ 10, 150, 200]), 300),
    (np.array([ 10,  25,  40]), np.array([ 20, 150, 200]), 300),
    (np.array([160,  50,  80]), np.array([179, 255, 255]), 300),
    (np.array([160,  25,  40]), np.array([179, 150, 200]), 300),
    (np.array([140,  40,  60]), np.array([159, 255, 255]), 300),
]
H_MIN, H_MAX = 10, 25
AR_MIN, AR_MAX = 3.0, 10.0
SMALL_W_MAX = 75
X_GAP, Y_GAP = 150, 15

Coord = Tuple[float, float]
Rect = Tuple[int,int,int,int,int,Tuple[int,int,int]]  # x,y,w,h,R,(H,S,V)

# ───────── Utilidades plantilla ─────────

def load_rois(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text("utf-8"))

def scale_pts(pts: List[Coord], W:int, H:int, ref:Optional[Tuple[int,int]]):
    if ref:
        rw,rh = ref; sx,sy = W/rw, H/rh
        return [(int(x*sx), int(y*sy)) for x,y in pts]
    if all(0<=x<=1 and 0<=y<=1 for x,y in pts):
        return [(int(x*W), int(y*H)) for x,y in pts]
    return [(int(x),int(y)) for x,y in pts]

def bbox(pts):
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys)

# ───────── Detección ─────────

def detectar_rects(crop: np.ndarray, scale: float) -> List[Rect]:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    k   = np.ones((3,3), np.uint8)
    rects: List[Rect] = []
    for rid,(lo,hi,area_ref) in enumerate(RED_HSV_LIST):
        thr = int(round(area_ref * scale))
        mask = cv2.inRange(hsv, lo, hi)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
        cnts,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            if cv2.contourArea(c) < thr: continue
            x,y,w,h = cv2.boundingRect(c)
            if not (H_MIN <= h <= H_MAX): continue
            ar = w/h
            if not (AR_MIN <= ar <= AR_MAX): continue
            mh,ms,mv = np.mean(hsv[y:y+h,x:x+w].reshape(-1,3),axis=0).astype(int)
            rects.append((x,y,w,h,rid,(int(mh),int(ms),int(mv))))
    return rects

# ───────── Fusionar pequeños ─────────

def fusionar_pequenos(rects: List[Rect]) -> List[Rect]:
    large   = [r for r in rects if r[2] >= SMALL_W_MAX]
    small   = [r for r in rects if r[2] < SMALL_W_MAX]

    clusters: List[List[Rect]] = []
    used=[False]*len(small)
    for i,r in enumerate(small):
        if used[i]: continue
        grp=[r]; used[i]=True; idx=0
        while idx < len(grp):
            cx,cy,cw,ch,_,_ = grp[idx]; idx+=1
            cx+=cw//2; cy+=ch//2
            for j,s in enumerate(small):
                if used[j]: continue
                sx,sy,sw,sh,_,_ = s; sx+=sw//2; sy+=sh//2
                if abs(cx-sx)<=X_GAP and abs(cy-sy)<=Y_GAP:
                    grp.append(s); used[j]=True
        clusters.append(grp)

    merged: List[Rect] = []
    for grp in clusters:
        if len(grp)==1:  # aislado -> descartar
            continue
        xs=[r[0] for r in grp]; ys=[r[1] for r in grp]
        xe=[r[0]+r[2] for r in grp]; ye=[r[1]+r[3] for r in grp]
        x,y = min(xs), min(ys)
        w,h = max(xe)-x, max(ye)-y
        areas=[r[2]*r[3] for r in grp]; total=sum(areas)
        mh=int(sum(r[5][0]*a for r,a in zip(grp,areas))/total)
        ms=int(sum(r[5][1]*a for r,a in zip(grp,areas))/total)
        mv=int(sum(r[5][2]*a for r,a in zip(grp,areas))/total)
        merged.append((x,y,w,h,grp[0][4],(mh,ms,mv)))
    return large + merged

# ───────── Visual helpers ─────────

def screen_res(default=(1920,1080)):
    try:
        import tkinter as tk; r=tk.Tk(); r.withdraw()
        w,h=r.winfo_screenwidth(),r.winfo_screenheight(); r.destroy(); return w,h
    except Exception:
        return default

def show_full(win:str,img):
    w,h=screen_res(); cv2.namedWindow(win,cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win,w,h); cv2.moveWindow(win,0,0); cv2.imshow(win,img)

# ───────── main ─────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--output", default="red_bars_merged.png")
    args = ap.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(args.image)
    H,W = frame.shape[:2]

    tpl = load_rois(Path(args.template))
    ref = tpl.get("reference_size")
    area_scale = (W*H)/(REF_W*REF_H)

    out = frame.copy(); font,fscale,thick = cv2.FONT_HERSHEY_SIMPLEX,0.45,1

    for roi,pts in tpl.items():
        if roi == "reference_size":
            continue
        sc = scale_pts(pts,W,H,ref); x0,y0,x1,y1 = bbox(sc)
        rects_raw = detectar_rects(frame[y0:y1,x0:x1], area_scale)
        rects = fusionar_pequenos(rects_raw)

        if not rects:
            print(f"[{roi}] sin barras válidas"); continue

        for idx,(bx,by,bw,bh,rid,(mh,ms,mv)) in enumerate(rects,1):
            ax,ay = x0+bx, y0+by; ar = bw/bh
            label=(f"{roi}-{idx} | {bw}×{bh}px | ({ax},{ay}) | AR={ar:.2f} | "
                   f"R={rid} | H={mh} S={ms} V={mv}")
            print(label)
            cv2.rectangle(out,(ax,ay),(ax+bw,ay+bh),(0,0,255),2)
            (tw,th),_ = cv2.getTextSize(label,font,fscale,thick)
            ty = ay-5 if ay-th-5>=0 else ay+bh+th+5
            cv2.putText(out,label,(ax,ty),font,fscale,(0,0,255),thick,cv2.LINE_AA)
        cv2.polylines(out,[np.array(sc)],True,(0,255,0),1)

    show_full("Barras rojas fusionadas",out)
    cv2.waitKey(0); cv2.destroyAllWindows()
    cv2.imwrite(args.output,out); print("Guardado",args.output)

if __name__=='__main__':
    main()
