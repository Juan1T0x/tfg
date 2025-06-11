# -*- coding: utf-8 -*-
r"""
Detecta barras VERDES (vida) en los ROIs de recursos de campeones ― versión
independiente de resolución.

• Carga automáticamente los ROIs desde la plantilla
    C:\Users\juan_\Desktop\tfg\python_backend\src\roi\templates\output\main_overlay_rois.json
  y utiliza únicamente:
      • team1ChampionsResourcesRoi
      • team2ChampionsResourcesRoi

• Los ROIs pueden estar:
      a) normalizados (0–1) → se escalan directo a píxeles.
      b) en píxeles, con campo "reference_size" en la plantilla → el script los
         reescala al tamaño del frame.
      c) en píxeles de la resolución actual → no necesitan ajuste.

• La lógica de detección y reporte de barras de vida se mantiene intacta.
"""

import json
import cv2
import numpy as np
from pathlib import Path

# ───────── Configuración ─────────
TEMPLATE_FILE = Path(r"C:\Users\juan_\Desktop\tfg\python_backend\src\roi\templates\output\main_overlay_rois.json")
FRAME_PATH    = "source.jpg"  # imagen a analizar (puedes cambiarlo a vídeo)

LOWER_GREEN = np.array([30, 40, 40])
UPPER_GREEN = np.array([80, 250, 250])
AREA_MIN    = 300            # área mínima del contorno verde
ELONG_RATIO = 0.5            # relación h/w para descartar barras casi cuadradas

ROLE_LABELS     = ["vida top", "vida jungle", "vida mid", "vida bot", "vida support"]
REFERENCE_BLUE  = "vida jungle"   # la barra que vale 100 % para el equipo azul

# ───────── Utilidades ─────────

def load_rois(template_path: Path):
    """Devuelve los dos ROIs de campeones y la resolución de referencia (o None)."""
    with template_path.open("r", encoding="utf-8") as f:
        tpl = json.load(f)

    ref_size = tpl.get("reference_size")  # None si no existe
    rois = {
        "team1ChampionsResourcesRoi": tpl["team1ChampionsResourcesRoi"],
        "team2ChampionsResourcesRoi": tpl["team2ChampionsResourcesRoi"],
    }
    return rois, ref_size


def scale_points(points, frame_w, frame_h, ref_size):
    """Convierte las coordenadas del ROI a píxeles del frame actual."""
    # Caso 1: normalizados 0–1
    if all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in points):
        return [(int(x * frame_w), int(y * frame_h)) for x, y in points]

    # Caso 2: píxeles con reference_size
    if ref_size is not None:
        ref_w, ref_h = ref_size
        sx, sy = frame_w / ref_w, frame_h / ref_h
        return [(int(x * sx), int(y * sy)) for x, y in points]

    # Caso 3: ya en píxeles de la resolución actual
    return [(int(x), int(y)) for x, y in points]


def bounds(pts):
    """x0, y0, x1, y1 del rectángulo que envuelve pts."""
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


def detectar_barras(img):
    """Devuelve [(x, y, w, h)] de barras verdes aceptadas."""
    hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_GREEN, UPPER_GREEN)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > AREA_MIN]
    return [(x, y, w, h) for x, y, w, h in rects if h < ELONG_RATIO * w]

# ───────── Programa principal ─────────

def main():
    frame = cv2.imread(FRAME_PATH)
    if frame is None:
        print("❌ No se encontró la imagen '", FRAME_PATH, "'.", sep="")
        return

    H_img, W_img = frame.shape[:2]

    # Cargar y escalar los ROIs
    template_rois, ref_size = load_rois(TEMPLATE_FILE)
    scaled_rois = {
        name: scale_points(pts, W_img, H_img, ref_size)
        for name, pts in template_rois.items()
    }

    # Bounding boxes de cada ROI (rectángulos mínimos)
    boxes = [bounds(scaled_rois["team1ChampionsResourcesRoi"]),
             bounds(scaled_rois["team2ChampionsResourcesRoi"])]

    print("Coordenadas escaladas de los ROIs:")
    for name, pts in scaled_rois.items():
        print(f"  {name}: {pts}")

    detections = {"azul": [], "rojo": []}

    # Analiza cada ROI
    for idx, (x0, y0, x1, y1) in enumerate(boxes, 1):
        team = "azul" if idx == 1 else "rojo"
        crop = frame[y0:y1, x0:x1]

        for x, y, w, h in detectar_barras(crop):
            gx, gy = x + x0, y + y0   # convierte a coords globales
            detections[team].append((gy, gx, w, h))
            cv2.rectangle(frame, (gx, gy), (gx + w, gy + h), (0, 255, 0), 2)
        # contorno del ROI
        cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 165, 255), 2)

    # ── Calcular referencia 100 % por equipo ──
    full_width = {}

    # Equipo azul: usa la barra "vida jungle" si se detectó
    blue_sorted = sorted(detections["azul"], key=lambda t: t[0])
    if blue_sorted and len(blue_sorted) >= ROLE_LABELS.index(REFERENCE_BLUE) + 1:
        full_width["azul"] = blue_sorted[ROLE_LABELS.index(REFERENCE_BLUE)][2]
    else:
        full_width["azul"] = max((w for _, _, w, _ in detections["azul"]), default=None)

    # Equipo rojo: simplemente la más ancha
    full_width["rojo"] = max((w for _, _, w, _ in detections["rojo"]), default=None)

    # ── Salida por consola ──
    for team in ("azul", "rojo"):
        print(f"\nROI equipo {team}:")
        det_sorted = sorted(detections[team], key=lambda t: t[0])
        for i, label in enumerate(ROLE_LABELS):
            if i < len(det_sorted):
                y, x, w, h = det_sorted[i]
                pct_txt = " ?.?%"
                if full_width[team]:
                    pct_txt = f"{(w / full_width[team] * 100):5.1f}%"
                print(f"    {label:<12}: (x={x}, y={y}, w={w}, h={h}) → {pct_txt}")
            else:
                print(f"    {label:<12}: no detectado →  ?.?%")

    # Muestra la imagen a pantalla completa
    try:
        import tkinter as _tk
        r = _tk.Tk(); r.withdraw()
        W_scr, H_scr = r.winfo_screenwidth(), r.winfo_screenheight(); r.destroy()
    except Exception:
        W_scr, H_scr = 1920, 1080

    cv2.namedWindow("Barras de vida (verde)", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Barras de vida (verde)", W_scr, H_scr)
    cv2.moveWindow("Barras de vida (verde)", 0, 0)
    cv2.imshow("Barras de vida (verde)", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
