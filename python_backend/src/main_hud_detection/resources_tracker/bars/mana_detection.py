# -*- coding: utf-8 -*-
r"""
Detecta barras AZULES (maná) en los ROIs de recursos de campeones ― independiente de resolución.

• Carga automáticamente los ROIs desde
      C:\Users\juan_\Desktop\tfg\python_backend\src\roi\templates\output\main_overlay_rois.json
  utilizando solo:
      • team1ChampionsResourcesRoi
      • team2ChampionsResourcesRoi

• Los ROIs pueden estar
      a) normalizados (0-1)           → se multiplican por ancho/alto del frame.
      b) en píxeles + reference_size  → se escalan al tamaño del frame.
      c) en píxeles de la resolución actual.

• El 100 % de cada equipo es la barra azul más ancha detectada en su ROI.
"""

import json
import cv2
import numpy as np
from pathlib import Path

# ───────── Configuración ─────────
TEMPLATE_FILE = Path(
    r"C:\Users\juan_\Desktop\tfg\python_backend\src\roi\templates\output\main_overlay_rois.json"
)
FRAME_PATH = "source.jpg"  # imagen o frame a procesar

LOWER_BLUE  = np.array([95, 50, 50])
UPPER_BLUE  = np.array([125, 255, 255])
AREA_MIN    = 300            # área mínima del contorno azul
ELONG_RATIO = 0.5            # h < ELONG_RATIO·w  ⇒ barra “elongada”

ROLE_LABELS = ["mana top", "mana jungle", "mana mid", "mana bot", "mana support"]

# ───────── Utilidades ROIs ─────────
def load_rois(template_path: Path):
    """Devuelve los dos ROIs y (opcional) tamaño de referencia."""
    with template_path.open("r", encoding="utf-8") as f:
        tpl = json.load(f)

    ref_size = tpl.get("reference_size")  # None si no existe
    rois = {
        "team1ChampionsResourcesRoi": tpl["team1ChampionsResourcesRoi"],
        "team2ChampionsResourcesRoi": tpl["team2ChampionsResourcesRoi"],
    }
    return rois, ref_size


def scale_points(points, frame_w, frame_h, ref_size):
    """Escala/convierte los puntos del ROI a píxeles del frame actual."""
    # Coordenadas normalizadas
    if all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in points):
        return [(int(x * frame_w), int(y * frame_h)) for x, y in points]

    # Coordenadas en píxeles de una resolución de referencia
    if ref_size is not None:
        ref_w, ref_h = ref_size
        sx, sy = frame_w / ref_w, frame_h / ref_h
        return [(int(x * sx), int(y * sy)) for x, y in points]

    # Ya están en píxeles de la resolución actual
    return [(int(x), int(y)) for x, y in points]


def bounds(pts):
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


# ───────── Detección de barras azules ─────────
def detectar_barras(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_BLUE, UPPER_BLUE)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > AREA_MIN]
    return [(x, y, w, h) for x, y, w, h in rects if h < ELONG_RATIO * w]


# ───────── Programa principal ─────────
def main():
    frame = cv2.imread(FRAME_PATH)
    if frame is None:
        print(f"❌ No se encontró la imagen '{FRAME_PATH}'.")
        return

    H_img, W_img = frame.shape[:2]

    # 1. ROIs escalados
    rois_raw, ref_size = load_rois(TEMPLATE_FILE)
    scaled_rois = {k: scale_points(v, W_img, H_img, ref_size) for k, v in rois_raw.items()}

    boxes = [
        bounds(scaled_rois["team1ChampionsResourcesRoi"]),
        bounds(scaled_rois["team2ChampionsResourcesRoi"]),
    ]

    # 2. Detección de barras azules
    detections = {"azul": [], "rojo": []}
    for idx, (x0, y0, x1, y1) in enumerate(boxes, 1):
        team = "azul" if idx == 1 else "rojo"
        crop = frame[y0:y1, x0:x1]

        for x, y, w, h in detectar_barras(crop):
            gx, gy = x + x0, y + y0
            detections[team].append((gy, gx, w, h))
            cv2.rectangle(frame, (gx, gy), (gx + w, gy + h), (255, 0, 0), 2)
        cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 255, 0), 2)

    # 3. Anchura máxima (100 %) por equipo
    full_width = {
        team: (max(w for _, _, w, _ in dets) if dets else None)
        for team, dets in detections.items()
    }

    # 4. Consola
    for team in ("azul", "rojo"):
        print(f"\nROI equipo {team}:")
        det_sorted = sorted(detections[team], key=lambda t: t[0])
        for i, label in enumerate(ROLE_LABELS):
            if i < len(det_sorted):
                y, x, w, h = det_sorted[i]
                pct = f"{(w / full_width[team] * 100):5.1f}%" if full_width[team] else " ?.?%"
                print(f"    {label:<13}: (x={x}, y={y}, w={w}, h={h}) → {pct}")
            else:
                print(f"    {label:<13}: no detectado →  ?.?%")

    # 5. Mostrar
    try:
        import tkinter as _tk
        r = _tk.Tk(); r.withdraw()
        W_scr, H_scr = r.winfo_screenwidth(), r.winfo_screenheight(); r.destroy()
    except Exception:
        W_scr, H_scr = 1920, 1080

    cv2.namedWindow("Barras de maná (azul)", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Barras de maná (azul)", W_scr, H_scr)
    cv2.moveWindow("Barras de maná (azul)", 0, 0)
    cv2.imshow("Barras de maná (azul)", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
