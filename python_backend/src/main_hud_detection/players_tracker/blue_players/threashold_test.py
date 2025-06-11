#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Explorador de rangos HSV para las barras AZULES.

Muestra exclusivamente la máscara binaria:
    • Blanco: dentro del rango HSV y del ROI
    • Negro : fuera del rango o fuera del ROI

Uso:
    python hsv_range_picker.py --image captura.png --template rois.json
"""
from __future__ import annotations
import cv2, json, argparse, numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# ───────── Tipos ─────────
Coord    = Tuple[float, float]
HSVRange = Tuple[int, int, int, int, int]      # h_lo, h_hi, s_min, v_min, area_ref

# ───────── Utilidades plantilla ─────────
def load_rois(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text("utf-8"))

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
                      rois_polys: List[np.ndarray],
                      h_lo:int, h_hi:int, s_min:int, v_min:int) -> np.ndarray:
    """Devuelve una máscara 0/255 limitada a los ROIs."""
    lower = np.array([h_lo, s_min, v_min], np.uint8)
    upper = np.array([h_hi, 255, 255],    np.uint8)
    mask_color = cv2.inRange(frame_hsv, lower, upper)

    roi_mask = np.zeros(frame_hsv.shape[:2], np.uint8)
    for poly in rois_polys:
        cv2.fillPoly(roi_mask, [poly], 255)

    return cv2.bitwise_and(mask_color, mask_color, mask=roi_mask)

# ───────── main ─────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image",    required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--save",     default="hsv_ok.json")
    args = ap.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        raise FileNotFoundError(args.image)

    tpl  = load_rois(Path(args.template))
    ref  = tpl.get("reference_size")
    H, W = img.shape[:2]

    # Escalar polígonos ROI
    rois_polys = [np.array(scale_pts(pts, W, H, ref), np.int32)
                  for n, pts in tpl.items() if n != "reference_size"]

    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    rangos  = generar_rangos()
    ok: List[HSVRange] = []

    print(f"Total de combinaciones: {len(rangos)}")
    print("Pulsa 1 (aceptar) · 0 (rechazar) · q (salir)\n")

    for idx, (h0, h1, s, v, area_ref) in enumerate(rangos, 1):
        mask = mascara_por_rango(hsv_img, rois_polys, h0, h1, s, v)

        # ---------- Visualización binaria ----------
        vis = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)  # para poder escribir texto
        cv2.putText(vis,
                    f"#{idx}/{len(rangos)}  H:[{h0},{h1}]  S>={s}  V>={v}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1,
                    (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow("Máscara binaria", vis)

        # ---------- Entrada de usuario ----------
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

    # ───────── Salida ─────────
    if ok:
        print("\n=== Rangos aceptados ===")
        for r in ok:
            print(f"  low  = [{r[0]}, {r[2]}, {r[3]}]   "
                  f"high = [{r[1]}, 255, 255]   area_ref = {r[4]}")
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(ok, f, indent=2)
        print(f"\nGuardado en {args.save}")
    else:
        print("\nNo se aceptó ningún rango.")

if __name__ == "__main__":
    main()
