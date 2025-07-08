#!/usr/bin/env python3
# extract_stats_specific.py  (versión full-debug)
"""
Extrae cualquier estadística visible en los ROIs y guarda *todas* las imágenes
intermedias:

┌─ Por cada ROI (excepto reference_size)
│   • <ts>_stats_<roi>_crop.png   ← recorte original
│   • <ts>_stats_<roi>_bin.png    ← binarización aplicada
└─ Vista global con todos los ROIs:
    <ts>_stats_rois.png

También imprime, para cada ROI:
    { "roi": { "raw": "<texto OCR>", "parsed": <valor> } }

Uso:
    python extract_stats_specific.py --image frame.jpg --template rois.json
"""
import re, json, cv2, pytesseract, argparse, numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any
from datetime import datetime

Coord = Tuple[float, float]

# ╭───────────────── Utilidades plantilla ─────────────────╮
def load_rois(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def scale_pts(pts: List[Coord], W:int, H:int, ref:Tuple[int,int]|None):
    if ref:
        rw,rh = ref; sx,sy = W/rw, H/rh
        return [(int(x*sx), int(y*sy)) for x,y in pts]
    if all(0<=x<=1 and 0<=y<=1 for x,y in pts):
        return [(int(x*W), int(y*H)) for x,y in pts]
    return [(int(x), int(y)) for x,y in pts]

def bbox(pts):
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys)

# ╭───────────────── Binarizaciones ─────────────────╮
def bin_white(img):
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv,(0,0,180),(180,60,255))

def bin_yellow(img):
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv,(18,60,130),(30,255,255))

def bin_otsu(img):
    g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    _,th=cv2.threshold(g,0,255,cv2.THRESH_BINARY|cv2.THRESH_OTSU)
    return th

def ocr(img, wl):
    cfg=f"--oem 1 --psm 7 -c tessedit_char_whitelist={wl}"
    return pytesseract.image_to_string(img,config=cfg).strip()

# ╭───────────────── Parsers ─────────────────╮
p_int  = lambda t: int(m.group()) if (m:=re.search(r"\d+",t)) else None
p_gold = lambda t: m.group() if (m:=re.search(r"\d+\.?\d*K",t)) else None
p_time = lambda t: m.group() if (m:=re.search(r"\d{1,2}:\d{2}",t)) else None
def p_kda(t):
    m=re.search(r"(\d+)/(\d+)/(\d+)",t)
    return {"k":int(m[1]),"d":int(m[2]),"a":int(m[3])} if m else None
p_cs = lambda t: int(m.group()) if (m:=re.search(r"\d+$",t)) else None
parse_default = lambda t: t.strip() if t else None

# ╭───────────────── Tabla de reglas ─────────────────╮
RULES = [
    (lambda k: k.endswith("kda"),     bin_white,  "0123456789/",     p_kda),
    (lambda k: k.endswith("creeps"),  bin_yellow, "0123456789",      p_cs),
    (lambda k: k in ("blueGold","redGold"), bin_otsu,"0123456789K.", p_gold),
    (lambda k: k in ("blueTowers","redTowers"),bin_otsu,"0123456789",p_int),
    (lambda k: k=="time",            bin_otsu,    "0123456789:",     p_time),
]

def choose_rule(key:str):
    for cond, binner, wl, parser in RULES:
        if cond(key):
            return binner, wl, parser
    return bin_otsu, "0123456789K:/", parse_default

# ╭───────────────── Main ─────────────────╮
def main():
    ag = argparse.ArgumentParser()
    ag.add_argument("--image",    required=True)
    ag.add_argument("--template", required=True)
    ag.add_argument("--tesseract", help="Ruta a tesseract.exe si no está en PATH")
    args = ag.parse_args()

    if args.tesseract:
        pytesseract.pytesseract.tesseract_cmd = str(Path(args.tesseract))

    frame=cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(args.image)
    H,W = frame.shape[:2]

    tpl = load_rois(Path(args.template))
    ref = tpl.get("reference_size")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Vista general con ROIs ──
    disp = frame.copy()
    for name,pts in tpl.items():
        if name=="reference_size": continue
        sc = scale_pts(pts,W,H,ref)
        cv2.polylines(disp,[np.array(sc)],True,(0,255,0),2)
        x0,y0,_,_ = bbox(sc)
        cv2.putText(disp,name,(x0,y0-3),cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,255,0),1)
    rois_img = f"{ts}_stats_rois.png"
    cv2.imwrite(rois_img,disp)
    print(f"✔ Guardada vista ROIs → {rois_img}")

    # ── Extraer y procesar todos los ROIs ──
    results: Dict[str, Dict[str,Any]] = {}

    for key, pts in tpl.items():
        if key=="reference_size": continue

        sc = scale_pts(pts,W,H,ref)
        x0,y0,x1,y1 = bbox(sc)

        # ampliación mínima para creeps
        if key.endswith("creeps"):
            x0 = max(0, x0-6); x1 = min(W, x1+6)

        crop = frame[y0:y1, x0:x1]
        crop_path = f"{ts}_stats_{key}_crop.png"
        cv2.imwrite(crop_path, crop)

        binner, wl, parser = choose_rule(key)
        bin_img  = binner(crop)
        bin_path = f"{ts}_stats_{key}_bin.png"
        cv2.imwrite(bin_path, bin_img)

        raw_text   = ocr(bin_img, wl)
        parsed_val = parser(raw_text)

        results[key] = {"raw": raw_text, "parsed": parsed_val}
        print(f"✔ {key}: guardados {crop_path} y {bin_path}")

    print("\n=== Resultados OCR ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
