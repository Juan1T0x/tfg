#!/usr/bin/env python3
# extract_stats_specific.py
"""
• Dibuja todos los ROIs sobre la captura  
• Para cada ROI muestra: recorte original  →  binarización usada  
• Aplica OCR con whitelist y parseo específico:

  ▸ kda  : texto blanco → S≤60, V≥180  
  ▸ creeps: amarillo #a29875 → H≈18-28, S≥60, V≥130  
  ▸ torres / oro / tiempo → umbral Otsu

Pulsa una tecla en cada ventana para avanzar al siguiente ROI.
"""

import re, json, cv2, pytesseract, argparse, numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any

Coord = Tuple[float, float]

# ───────── utilidades plantilla ─────────
def load_rois(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def scale_pts(pts: List[Coord], W:int, H:int, ref:Tuple[int,int]|None):
    if ref:
        rw,rh=ref; sx,sy=W/rw,H/rh
        return [(int(x*sx),int(y*sy)) for x,y in pts]
    if all(0<=x<=1 and 0<=y<=1 for x,y in pts):
        return [(int(x*W),int(y*H)) for x,y in pts]
    return [(int(x),int(y)) for x,y in pts]

def bbox(pts): xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; return min(xs),min(ys),max(xs),max(ys)

# ───────── binarizaciones ─────────
def bin_white(img):
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv,(0,0,180),(180,60,255))

def bin_yellow(img):
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    # #a29875 ≈ H 22°, S~78-100, V~160-255  (OpenCV H 0-180)
    return cv2.inRange(hsv,(18,60,130),(30,255,255))

def bin_otsu(img):
    g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    _,th=cv2.threshold(g,0,255,cv2.THRESH_BINARY|cv2.THRESH_OTSU)
    return th

def ocr(img, wl):
    cfg=f"--oem 1 --psm 7 -c tessedit_char_whitelist={wl}"
    return pytesseract.image_to_string(img,config=cfg).strip()

# ───────── parsers ─────────
p_int   = lambda t: int(m.group()) if (m:=re.search(r"\d+",t)) else None
p_gold  = lambda t: m.group() if (m:=re.search(r"\d+\.?\d*K",t)) else None
p_time  = lambda t: m.group() if (m:=re.search(r"\d{1,2}:\d{2}",t)) else None
def p_kda(t):
    m=re.search(r"(\d+)/(\d+)/(\d+)",t)
    return {"k":int(m[1]),"d":int(m[2]),"a":int(m[3])} if m else None
p_cs    = lambda t: int(m.group()) if (m:=re.search(r"(\d+)$",t)) else None

# ───────── main ─────────
def main():
    ag=argparse.ArgumentParser(); ag.add_argument("--image",required=True); ag.add_argument("--template",required=True)
    a=ag.parse_args()

    frame=cv2.imread(a.image); H,W=frame.shape[:2]
    tpl=load_rois(Path(a.template)); ref=tpl.get("reference_size") # tpl stands for 

    # pinta todos los ROIs
    disp=frame.copy()
    for k,pts in tpl.items():
        if k=="reference_size":continue
        sc=scale_pts(pts,W,H,ref)
        cv2.polylines(disp,[np.array(sc)],True,(0,255,0),2)
        x0,y0,_,_=bbox(sc)
        cv2.putText(disp,k,(x0,y0-3),cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,255,0),1)
    cv2.imshow("ROIs",disp); cv2.waitKey(0); cv2.destroyAllWindows()

    results={}
    for key,pts in tpl.items():
        if key=="reference_size": continue
        sc=scale_pts(pts,W,H,ref); x0,y0,x1,y1=bbox(sc)

        # ligero pad horizontal para creeps (nº largos)
        if key.endswith("creeps"): x0=max(0,x0-6); x1=min(W,x1+6)

        crop=frame[y0:y1,x0:x1]
        cv2.imshow(f"{key}-crop",crop)

        if key.endswith("kda"):
            bin_img, wl, parser = bin_white(crop),"0123456789/",p_kda
        elif key.endswith("creeps"):
            bin_img, wl, parser = bin_yellow(crop),"0123456789",p_cs
        elif key in ("blueTowers","redTowers"):
            bin_img, wl, parser = bin_otsu(crop),"0123456789",p_int
        elif key in ("blueGold","redGold"):
            bin_img, wl, parser = bin_otsu(crop),"0123456789K.",p_gold
        elif key=="time":
            bin_img, wl, parser = bin_otsu(crop),"0123456789:",p_time
        else:
            bin_img, wl, parser = bin_otsu(crop),"0123456789K:/",lambda x:x.strip()

        cv2.imshow(f"{key}-bin",bin_img); cv2.waitKey(0); cv2.destroyAllWindows()
        results[key]=parser(ocr(bin_img,wl))

    print(json.dumps(results,indent=2))

if __name__=="__main__":
    main()
