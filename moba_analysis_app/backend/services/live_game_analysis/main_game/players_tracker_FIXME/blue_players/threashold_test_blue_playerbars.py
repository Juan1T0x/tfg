#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Explorador de rangos HSV para las barras AZULES.

Muestra exclusivamente la máscara binaria:
    • Blanco: dentro del rango HSV y dentro del ROI
    • Negro : fuera del rango o fuera del ROI

Acepta dos formas de ROI:
    1. Una plantilla JSON con polígonos (opción --template) — igual al script original.
    2. Un ROI “rápido” por CLI con --roi x,y,w,h  (o un JSON {'roi':{x,y,w,h}}).

Uso:
    python hsv_range_picker.py --image captura.png --template rois.json
    python hsv_range_picker.py --image captura.png --roi 100,200,300,80
    python hsv_range_picker.py --image captura.png --roi roi_bbox.json
"""
from __future__ import annotations
import cv2, json, argparse, numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# ───────── Tipos ─────────
Coord    = Tuple[float, float]
HSVRange = Tuple[int, int, int, int, int]   # h_lo, h_hi, s_min, v_min, area_ref

# ───────── Utilidades ROI ─────────
def load_rois_template(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text("utf-8"))

def parse_roi_arg(roi_arg: str) -> Tuple[int, int, int, int]:
    """
    Interpreta 'x,y,w,h' o un JSON con {"roi": {"x":..,"y":..,"w":..,"h":..}}
    y devuelve (x, y, w, h).
    """
    p = Path(roi_arg)
    if p.suffix.lower() == ".json" and p.exists():
        data = json.loads(p.read_text("utf-8"))
        d = data["roi"]
        return d["x"], d["y"], d["w"], d["h"]

    try:
        x, y, w, h = map(int, roi_arg.split(","))
        return x, y, w, h
    except Exception:
        raise argparse.ArgumentTypeError(
            "--roi debe ser 'x,y,w,h' o un .json con {'roi':{x,y,w,h}}"
        )

def scale_pts(pts: List[Coord], W:int, H:int, ref:Optional[Tuple[int,int]]):
    if ref:
        rw, rh = ref; sx, sy = W / rw, H / rh
        return [(int(x*sx), int(y*sy)) for x, y in pts]
    if all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts):
        return [(int(x*W), int(y*H)) for x, y in pts]
    return [(int(x), int(y)) for x, y in pts]

# ───────── Generador de rangos ─────────
def generar_rangos() -> List[HSVRange]:
    h_vals = range(90, 131, 5)     # 90–130
    s_vals = range(40, 101, 20)    # 40–100
    v_vals = range(40, 101, 20)    # 40–100
    rangos: List[HSVRange] = []
    for h_lo in h_vals:
        for h_hi in range(h_lo + 5, min(h_lo + 25, 131), 5):
            for s in s_vals:
                for v in v_vals:
                    rangos.append((h_lo, h_hi, s, v, 300))
    return rangos

# ───────── Máscara por rango ─────────
def mascara_por_rango(frame_hsv: np.ndarray,
                      roi_mask: np.ndarray,
                      h_lo:int, h_hi:int, s_min:int, v_min:int) -> np.ndarray:
    lower = np.array([h_lo, s_min, v_min], np.uint8)
    upper = np.array([h_hi, 255, 255],    np.uint8)
    mask_color = cv2.inRange(frame_hsv, lower, upper)
    return cv2.bitwise_and(mask_color, mask_color, mask=roi_mask)

# ───────── main ─────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image",    required=True, help="Ruta de la imagen de entrada.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--template", help="Plantilla JSON con polígonos de ROI.")
    group.add_argument("--roi",      help="Bounding box 'x,y,w,h' o JSON con {'roi':{x,y,w,h}}.")
    ap.add_argument("--save", default="hsv_ok.json",
                    help="Archivo donde guardar los rangos aceptados.")
    args = ap.parse_args()

    # ---------- Imagen ----------
    img = cv2.imread(args.image)
    if img is None:
        raise FileNotFoundError(args.image)
    H, W = img.shape[:2]
    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # ---------- ROI mask ----------
    roi_mask = np.zeros((H, W), np.uint8)

    if args.template:
        tpl  = load_rois_template(Path(args.template))
        ref  = tpl.get("reference_size")
        polys = [np.array(scale_pts(pts, W, H, ref), np.int32)
                 for n, pts in tpl.items() if n != "reference_size"]
        for poly in polys:
            cv2.fillPoly(roi_mask, [poly], 255)
    else:  # args.roi
        x, y, w, h = parse_roi_arg(args.roi)
        cv2.rectangle(roi_mask, (x, y), (x+w, y+h), 255, -1)

    # ---------- Exploración de rangos ----------
    rangos = generar_rangos()
    ok: List[HSVRange] = []

    print(f"Total de combinaciones: {len(rangos)}")
    print("Pulsa 1 (aceptar) · 0 (rechazar) · q (salir)\n")

    for idx, (h0, h1, s, v, area_ref) in enumerate(rangos, 1):
        mask = mascara_por_rango(hsv_img, roi_mask, h0, h1, s, v)

        vis = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        cv2.putText(vis,
                    f"#{idx}/{len(rangos)}  H:[{h0},{h1}]  S>={s}  V>={v}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1,
                    (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow("Máscara binaria", vis)

        while True:
            k = cv2.waitKey(0) & 0xFF
            if k in (ord('1'), ord('0'), ord('q')):
                tecla = chr(k)
                break

        if tecla == 'q':
            cv2.destroyAllWindows()
            break
        if tecla == '1':
            ok.append((h0, h1, s, v, area_ref))

        cv2.destroyAllWindows()

    # ---------- Guardar selección ----------
    if ok:
        print("\n=== Rangos aceptados ===")
        for r in ok:
            print(f"  low=[{r[0]}, {r[2]}, {r[3]}]  high=[{r[1]}, 255, 255]  area_ref={r[4]}")
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(ok, f, indent=2)
        print(f"\nGuardado en {args.save}")
    else:
        print("\nNo se aceptó ningún rango.")

if __name__ == "__main__":
    main()
