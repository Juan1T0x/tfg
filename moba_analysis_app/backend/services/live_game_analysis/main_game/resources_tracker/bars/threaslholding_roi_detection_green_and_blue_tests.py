# -*- coding: utf-8 -*-
"""
Ajuste interactivo de parámetros HSV para detectar barras de color
(verde, azul o rojo) en League of Legends.

Uso:
    python tune_bars.py --frame source.jpg
    python tune_bars.py --frame source.jpg --roi 100,200,300,80
    python tune_bars.py --frame source.jpg --roi roi.json
"""
import cv2
import numpy as np
import argparse
import json
from pathlib import Path
from typing import Tuple, List


# ───────── Parámetros de búsqueda ─────────
PARAM_SETS = {
    "green": {
        "lower": [np.array([30, 40, 40]),
                  np.array([35, 50, 50]),
                  np.array([40, 60, 60])],
        "upper": [np.array([80, 250, 250]),
                  np.array([85, 255, 255]),
                  np.array([90, 255, 255])],
    },
    "blue": {
        "lower": [np.array([95, 50, 50]),
                  np.array([100, 50, 50]),
                  np.array([105, 50, 50])],
        "upper": [np.array([125, 255, 255]),
                  np.array([130, 255, 255]),
                  np.array([135, 255, 255])],
    },
    "red": {
        "lower": [np.array([0, 50, 50]),
                  np.array([5, 50, 50]),
                  np.array([10, 50, 50])],
        "upper": [np.array([10, 255, 255]),
                  np.array([15, 255, 255]),
                  np.array([20, 255, 255])],
    },
}
AREA_THRESHOLDS = [300, 500, 700]


# ───────── Funciones ─────────
def detectar_roi_barra(frame: np.ndarray,
                       lower: np.ndarray,
                       upper: np.ndarray,
                       area_thresh: int,
                       kernel_size: int = 3) -> Tuple[List[Tuple[int, int, int, int]], np.ndarray]:
    """Devuelve rectángulos (x, y, w, h) y la máscara binaria."""
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


# ───────── Main CLI ─────────
def main():
    ap = argparse.ArgumentParser(description="Calibrador de barras (verde/azul/roja).")
    ap.add_argument("--frame", required=True, help="Imagen a analizar.")
    ap.add_argument("--roi",   help="ROI como 'x,y,w,h' o archivo JSON con {'roi':{x,y,w,h}}.")
    args = ap.parse_args()

    frame = cv2.imread(args.frame)
    if frame is None:
        print("❌ No se pudo leer la imagen.")
        return

    # Recorta al ROI si se indicó
    if args.roi:
        x, y, w, h = parse_roi_arg(args.roi)
        frame = frame[y:y+h, x:x+w]
        print(f"Usando ROI: x={x}, y={y}, w={w}, h={h}")

    print("Presiona 's' para seleccionar, 'c' para pasar al siguiente color, 'q' para salir.\n")

    for color in ["green", "blue", "red"]:
        print(f"\nProbando color: {color}")
        skip_color = False
        lowers = PARAM_SETS[color]["lower"]
        uppers = PARAM_SETS[color]["upper"]

        for lower in lowers:
            if skip_color:
                break
            for upper in uppers:
                if skip_color:
                    break
                for area in AREA_THRESHOLDS:
                    img = frame.copy()
                    rois, mask = detectar_roi_barra(img, lower, upper, area)
                    for (x, y, w, h) in rois:
                        cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)

                    text = f"{color} | low:{lower.tolist()} | up:{upper.tolist()} | area:{area}"
                    cv2.putText(img, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (0, 255, 255), 2)
                    cv2.imshow("Param test", img)
                    key = cv2.waitKey(0) & 0xFF

                    if key == ord('s'):
                        print("✔ Seleccionado:", text)
                    elif key == ord('c'):
                        print("→ Siguiente color")
                        skip_color = True
                        break
                    elif key == ord('q'):
                        cv2.destroyAllWindows()
                        return

    cv2.destroyAllWindows()
    print("Pruebas finalizadas.")


if __name__ == "__main__":
    main()
