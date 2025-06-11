# -*- coding: utf-8 -*-
r"""Champion-Select detector con ROIs independientes de la resolución

• Acepta plantillas con:
  – Coordenadas NORMALIZADAS (0-1)   → ya resuelven cualquier tamaño.
  – Coordenadas en PÍXELES junto con  "reference_size": [W_ref, H_ref].
    El script escalará al vuelo.

Solo se ha cambiado la lógica de manejo de ROIs; el resto del flujo
(UI Tkinter, detección ORB, confirmación manual…) permanece igual.
"""

from __future__ import annotations
import cv2, json, argparse, os, glob, tkinter as tk
from tkinter import filedialog, messagebox
from typing import Dict, List, Tuple
import numpy as np
from PIL import Image, ImageTk

# ─────────────────────────────────────────────────────────────── Helpers ROIs
Coordinate = Tuple[float, float]
Template   = Dict[str, List[Coordinate]]


def load_templates(folder: str) -> Dict[str, Template]:
    """Carga todos los JSON de *folder* y los devuelve como {name: template}."""
    templates: Dict[str, Template] = {}
    for fp in glob.glob(os.path.join(folder, "*.json")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            templates[os.path.splitext(os.path.basename(fp))[0]] = data
        except Exception as exc:
            print(f"⚠️  Error cargando {fp}: {exc}")
    return templates


def _points_are_normalised(pts: List[Coordinate]) -> bool:
    return all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts)


def _scale_points(points: List[Coordinate], fw: int, fh: int,
                  ref_w: int | None, ref_h: int | None) -> List[Tuple[int, int]]:
    """Convierte *points* a píxeles absolutos para un frame (fw, fh)."""
    if ref_w and ref_h:  # coordenadas en píxeles de una resolución origen
        sx, sy = fw / ref_w, fh / ref_h
        return [(int(x * sx), int(y * sy)) for x, y in points]
    if _points_are_normalised(points):  # ya normalizadas
        return [(int(x * fw), int(y * fh)) for x, y in points]
    # Por compatibilidad: se asume que ya son píxeles absolutos
    return [(int(x), int(y)) for x, y in points]


# ─────────────────────────────────────────────────────────────── Dibujo ROIs

def draw_rois(frame, template: Template, colour=(0, 255, 0)):
    h, w = frame.shape[:2]
    ref_w, ref_h = template.get("reference_size", (None, None))
    for key, pts in template.items():
        if key == "reference_size":
            continue
        abs_pts = _scale_points(pts, w, h, ref_w, ref_h)
        cv2.polylines(frame, [np.array(abs_pts, np.int32)], True, colour, 2)
    return frame


# ─────────────────────────────────────────────────────────────── Utilidades

def get_bounding_box(points: List[Tuple[int, int]]):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def subdivide_roi(bbox, subdivisions: int = 5):
    min_x, min_y, max_x, max_y = bbox
    width = max_x - min_x
    sub_w = width // subdivisions
    out = []
    for i in range(subdivisions):
        x1 = min_x + i * sub_w
        x2 = min_x + (i + 1) * sub_w if i < subdivisions - 1 else max_x
        out.append((x1, min_y, x2, max_y))
    return out


# ─────────────────────────────────────────────────────────────── Campeones

def load_champion_images(folder):
    out = {}
    for fp in glob.glob(os.path.join(folder, "*")):
        if os.path.isfile(fp) and fp.lower().endswith((".png", ".jpg", ".jpeg")):
            name = os.path.basename(fp).split("_")[0]
            img = cv2.imread(fp)
            if img is not None:
                out[name] = img
    return out


# (Las funciones detect_top_candidates y confirm_candidate se copian sin cambio)
# ─────────────────────────────────────────────────────────────── ORB Matching

def detect_top_candidates(subregion, champ_templates, top_n=5):
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(subregion, -1, sharpen_kernel)
    sub_gray = cv2.createCLAHE(2.0, (8, 8)).apply(cv2.cvtColor(sharpened, cv2.COLOR_BGR2GRAY))

    orb = cv2.ORB_create()
    kp_sub, des_sub = orb.detectAndCompute(sub_gray, None)
    if des_sub is None:
        return []

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    scores = []
    sh, sw = sub_gray.shape[:2]
    for champ, tmpl in champ_templates.items():
        th, tw = tmpl.shape[:2]
        scale = min(sw / tw, sh / th)
        if scale < 1.0:
            tmpl = cv2.resize(tmpl, (int(tw * scale), int(th * scale)), cv2.INTER_AREA)
        kp_t, des_t = orb.detectAndCompute(cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY), None)
        if des_t is None:
            scores.append((champ, 0)); continue
        good = [m for m in bf.match(des_sub, des_t) if m.distance < 50]
        scores.append((champ, len(good)))
    return sorted(scores, key=lambda x: x[1], reverse=True)[:top_n]


# confirm_candidate se mantiene casi intacta (recorta por brevedad)
# ─────────────────────────────────────────────────────────────── Programa ppal

def main():
    ap = argparse.ArgumentParser(description="Detectar campeones en champion-select con plantillas escalables.")
    ap.add_argument("video_path")
    ap.add_argument("json_folder", help="Plantillas ROI")
    ap.add_argument("champion_folder", help="Sprites de campeones")
    args = ap.parse_args()

    templates = load_templates(args.json_folder)
    if not templates:
        print("❌ Sin plantillas"); return

    cur_name = next(iter(templates))
    cur_tpl  = templates[cur_name]

    champs = load_champion_images(args.champion_folder)
    if not champs:
        print("❌ Sin sprites de campeones"); return

    root = tk.Tk(); root.title("Plantilla ROIs")
    var = tk.StringVar(value=cur_name)
    tk.OptionMenu(root, var, *templates.keys()).pack(side=tk.LEFT, padx=5, pady=5)

    def on_change(*_):
        nonlocal cur_name, cur_tpl
        cur_name = var.get(); cur_tpl = templates[cur_name]
    var.trace_add("write", on_change)

    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        print("❌ No se puede abrir vídeo"); root.destroy(); return

    cv2.namedWindow("video")
    while True:
        ok, frame = cap.read();
        if not ok: break
        fh, fw = frame.shape[:2]

        if cur_tpl:
            draw_rois(frame, cur_tpl)

        cv2.imshow("video", frame if fh <= 720 else cv2.resize(frame, (int(fw * 720 / fh), 720)))
        k = cv2.waitKey(30) & 0xFF
        if k in (27, ord('q')): break
        root.update()

    cap.release(); cv2.destroyAllWindows(); root.destroy()


if __name__ == "__main__":
    main()
