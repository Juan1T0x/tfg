# -*- coding: utf-8 -*-
"""
ROI Viewer adaptable a cualquier resolución.

Cambios clave frente al script original:
1. Las plantillas pueden contener:
   • Coordenadas NORMALIZADAS (valores 0‒1) que ya son independientes de tamaño.
   • Coordenadas ABSOLUTAS en la resolución de referencia indicada mediante
     el campo "reference_size": [W_ref, H_ref].

2. La función `draw_rois` detecta el tipo de coordenada y escala al vuelo.
3. `load_templates` no cambia; sólo ignora los campos que no son ROIs.

Uso:
    python roi_viewer_normalized.py path/al/video.mp4 path/a/plantillas

Atajos mientras se reproduce el vídeo:
    m – avanza 10 s
    c – captura frame con ROIs (abre diálogo)
    q / ESC – salir
"""

import cv2
import numpy as np
import json
import argparse
import tkinter as tk
from tkinter import filedialog
import os
import glob
from typing import Dict, List, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Utilidades para plantillas
# ──────────────────────────────────────────────────────────────────────────────
Coordinate = Tuple[float, float]
Template   = Dict[str, List[Coordinate]]

def load_templates(folder: str) -> Dict[str, Template]:
    """Carga todos los JSON de la carpeta y devuelve {nombre: plantilla}."""
    templates: Dict[str, Template] = {}
    pattern = os.path.join(folder, "*.json")
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = os.path.splitext(os.path.basename(filepath))[0]
            templates[name] = data
        except Exception as e:
            print(f"⚠️  Error cargando {filepath}: {e}")
    return templates


def _points_are_normalised(pts: List[Coordinate]) -> bool:
    """True si TODOS los puntos están en el rango 0‒1."""
    return all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in pts)


def _scale_points(points: List[Coordinate], frame_w: int, frame_h: int,
                  ref_w: int | None, ref_h: int | None) -> List[Tuple[int, int]]:
    """Escala la lista de puntos a píxeles para el frame actual."""
    scaled: List[Tuple[int, int]] = []

    if ref_w and ref_h:  # Coordenadas en píxeles de una resolución de referencia
        sx, sy = frame_w / ref_w, frame_h / ref_h
        scaled = [(int(x * sx), int(y * sy)) for x, y in points]
    elif _points_are_normalised(points):  # Coordenadas normalizadas 0‒1
        scaled = [(int(x * frame_w), int(y * frame_h)) for x, y in points]
    else:  # Por compatibilidad: se asume que ya están en píxeles de la resolución actual
        scaled = [(int(x), int(y)) for x, y in points]
    return scaled


def draw_rois(frame, template: Template, colour: tuple[int, int, int] = (0, 255, 0)):
    """Dibuja los ROIs del *template* y etiqueta cada uno con su clave."""
    h_frame, w_frame = frame.shape[:2]
    ref_w, ref_h = None, None
    if "reference_size" in template:
        ref_w, ref_h = template["reference_size"]

    font       = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness  = 1

    for roi_key, points in template.items():
        if roi_key == "reference_size":
            continue

        # 1) Escalado al tamaño del frame
        abs_pts = _scale_points(points, w_frame, h_frame, ref_w, ref_h)
        pts     = np.array(abs_pts, np.int32).reshape((-1,1,2))

        # 2) Dibujar la polilínea
        cv2.polylines(frame, [pts], isClosed=True, color=colour, thickness=2)

        # 3) Calcular bounding-box para colocar el texto
        xs = [p[0] for p in abs_pts]
        ys = [p[1] for p in abs_pts]
        x0, y0 = min(xs), min(ys)

        # 4) Ajustar posición del texto por si no cabe arriba
        (tw, th), _ = cv2.getTextSize(roi_key, font, font_scale, thickness)
        ty = y0 - 5
        if ty - th < 0:
            ty = y0 + th + 5

        # 5) Dibujar fondo semitransparente para legibilidad
        overlay = frame.copy()
        cv2.rectangle(overlay, (x0, ty-th-2), (x0+tw+4, ty+2), (0,0,0), -1)
        alpha = 0.6
        cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0, frame)

        # 6) Poner el texto con el nombre del ROI
        cv2.putText(frame, roi_key, (x0+2, ty),
                    font, font_scale, (255,255,255), thickness, cv2.LINE_AA)

    return frame


# ──────────────────────────────────────────────────────────────────────────────
# GUI / Reproductor principal
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mostrar ROIs sobre un vídeo con plantillas independientes de resolución.")
    parser.add_argument("video_path", help="Ruta al vídeo")
    parser.add_argument("json_folder", help="Carpeta con plantillas JSON")
    args = parser.parse_args()

    # Cargar plantillas
    templates = load_templates(args.json_folder)
    if not templates:
        print("❌ No se encontraron plantillas JSON en la carpeta especificada.")
        return

    template_names = list(templates.keys())
    current_template: Template = templates[template_names[0]]

    # Tkinter (selección de plantilla)
    root = tk.Tk()
    root.title("Seleccionar plantilla de ROIs")
    tk.Label(root, text="Plantilla:").pack(side=tk.LEFT, padx=5, pady=5)

    sel_var = tk.StringVar(root, value=template_names[0])
    dropdown = tk.OptionMenu(root, sel_var, *template_names)
    dropdown.pack(side=tk.LEFT, padx=5, pady=5)

    def on_change(*_):
        nonlocal current_template
        name = sel_var.get()
        if name in templates:
            current_template = templates[name]
    sel_var.trace_add("write", on_change)

    # CV2 vídeo
    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        print("❌ No se pudo abrir el vídeo.")
        root.destroy()
        return

    window_name = "Video  •  m: +10 s   c: captura   q/ESC: salir"
    cv2.namedWindow(window_name)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if current_template:
            frame = draw_rois(frame, current_template)

        cv2.imshow(window_name, frame)

        key = cv2.waitKey(30) & 0xFF
        if key == ord("m"):
            # Avanza 10 s (10 000 ms)
            pos = cap.get(cv2.CAP_PROP_POS_MSEC) + 10_000
            cap.set(cv2.CAP_PROP_POS_MSEC, pos)
        elif key == ord("c"):
            # Guarda captura
            tmp = tk.Tk(); tmp.withdraw()
            fname = filedialog.asksaveasfilename(
                defaultextension=".png",
                title="Guardar captura",
                filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("Todos", "*.*")],
            )
            tmp.destroy()
            if fname:
                cv2.imwrite(fname, frame)
                print(f"✔️  Captura guardada en {fname}")
        elif key in (ord("q"), 27):
            break

        root.update()  # mantiene el dropdown responsivo

    cap.release()
    cv2.destroyAllWindows()
    root.destroy()


if __name__ == "__main__":
    main()
