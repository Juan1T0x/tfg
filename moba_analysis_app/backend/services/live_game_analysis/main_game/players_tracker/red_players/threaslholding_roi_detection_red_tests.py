# -*- coding: utf-8 -*-
"""
Ajuste exhaustivo de parámetros HSV para detectar barras ROJAS.
Ahora acepta la ruta de la imagen (`--frame`) y, opcionalmente,
un ROI (`--roi`) como en los scripts anteriores.

Uso:
    python tune_red_bars.py --frame source.jpg
    python tune_red_bars.py --frame source.jpg --roi 100,200,300,80
    python tune_red_bars.py --frame source.jpg --roi roi.json
"""
import cv2
import numpy as np
import argparse
import json
from pathlib import Path
from typing import List, Tuple


# ───────── Generación de candidatos para ROJO ─────────
DELTA_H = 10
LOWER_CANDIDATES: List[np.ndarray] = []
UPPER_CANDIDATES: List[np.ndarray] = []

for h in np.linspace(0, 15, num=5, dtype=int):
    for s in np.linspace(50, 150, num=3, dtype=int):
        for v in np.linspace(50, 150, num=3, dtype=int):
            lower = np.array([int(h), int(s), int(v)])
            upper = np.array([int(h) + DELTA_H, 255, 255])
            LOWER_CANDIDATES.append(lower)
            UPPER_CANDIDATES.append(upper)

AREA_THRESHOLDS = [300, 500, 700]


# ───────── Funciones utilitarias ─────────
def detectar_roi_barra(frame: np.ndarray,
                       lower: np.ndarray,
                       upper: np.ndarray,
                       area_thresh: int,
                       kernel_size: int = 3) -> Tuple[List[Tuple[int, int, int, int]], np.ndarray]:
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)

    k = np.ones((kernel_size, kernel_size), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rois = []
    for cnt in contours:
        if cv2.contourArea(cnt) > area_thresh:
            x, y, w, h = cv2.boundingRect(cnt)
            rois.append((x, y, w, h))
    return rois, mask


def parse_roi_arg(roi_arg: str) -> Tuple[int, int, int, int]:
    """Convierte 'x,y,w,h' o JSON → tupla (x,y,w,h)."""
    p = Path(roi_arg)
    if p.suffix.lower() == ".json" and p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        return data["roi"]["x"], data["roi"]["y"], data["roi"]["w"], data["roi"]["h"]
    try:
        x, y, w, h = map(int, roi_arg.split(","))
        return x, y, w, h
    except Exception:
        raise argparse.ArgumentTypeError("--roi debe ser 'x,y,w,h' o un .json válido")


# ───────── Programa principal ─────────
def main():
    ap = argparse.ArgumentParser(description="Calibrador para barras ROJAS.")
    ap.add_argument("--frame", required=True, help="Imagen a analizar.")
    ap.add_argument("--roi",   help="ROI como 'x,y,w,h' o JSON con {'roi':{x,y,w,h}}.")
    args = ap.parse_args()

    frame = cv2.imread(args.frame)
    if frame is None:
        print("❌ No se pudo leer la imagen.")
        return

    # Recortar si se indicó ROI
    if args.roi:
        x, y, w, h = parse_roi_arg(args.roi)
        frame = frame[y:y+h, x:x+w]
        print(f"Usando ROI: x={x}, y={y}, w={w}, h={h}")

    total_combis = len(LOWER_CANDIDATES) * len(AREA_THRESHOLDS)
    print("Pruebas para ROJO. 's'=seleccionar, 'c'=siguiente pareja, 'q'=salir.\n")

    combo = 0
    for lower, upper in zip(LOWER_CANDIDATES, UPPER_CANDIDATES):
        skip_pair = False
        for area in AREA_THRESHOLDS:
            combo += 1
            img = frame.copy()
            rois, mask = detectar_roi_barra(img, lower, upper, area)
            for (x, y, w, h) in rois:
                cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)

            txt = f"ROJO | low:{lower.tolist()} | up:{upper.tolist()} | area:{area} ({combo}/{total_combis})"
            cv2.putText(img, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 255), 2)
            cv2.imshow("Test parámetros - ROJO", img)
            key = cv2.waitKey(0) & 0xFF

            if key == ord('s'):
                print("✔ Seleccionado:", txt)
            elif key == ord('c'):
                skip_pair = True
                break
            elif key == ord('q'):
                cv2.destroyAllWindows()
                return
        if skip_pair:
            continue

    cv2.destroyAllWindows()
    print("Pruebas finalizadas.")


if __name__ == "__main__":
    main()
