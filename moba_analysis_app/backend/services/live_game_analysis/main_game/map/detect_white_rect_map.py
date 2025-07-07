# -*- coding: utf-8 -*-
"""
Detecta la posición del rectángulo blanco (posición actual) en el minimapa
y **guarda todas las etapas** del proceso, con el prefijo “minimap”:

    • <ts>_minimap_roi.png                 ← ROI recortado
    • <ts>_minimap_thresh.png              ← umbral binario (blancos)
    • <ts>_minimap_lines.png               ← líneas Hough sobre ROI (si las hay)
    • minimap_detected_<ts>.jpg            ← resultado final sobre el frame

Uso:
    python detect_minimap_rect.py --image frame.jpg --template rois.json
"""
import cv2
import json
import argparse
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime

Coord = Tuple[float, float]

# ───────── utilidades de plantilla ─────────
def load_rois(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def scale_pts(pts: List[Coord], W: int, H: int, ref: Tuple[int,int] | None):
    if ref:
        rw, rh = ref; sx, sy = W / rw, H / rh
        return [(int(x * sx), int(y * sy)) for x, y in pts]
    if all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts):
        return [(int(x * W), int(y * H)) for x, y in pts]
    return [(int(x), int(y)) for x, y in pts]

def bbox(pts: List[Coord]) -> Tuple[int, int, int, int]:
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

# ───────── búsquedas de formas ─────────
def find_white_rectangle(img: np.ndarray) -> Optional[Tuple[Tuple[int,int], Tuple[int,int]]]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            if w < 20 or h < 20:
                continue
            if gray[y + h//2, x + w//2] < 50:  # centro oscuro
                return (x, y), (w, h)
    return None

def complete_rectangle_from_lines(lines: np.ndarray) -> np.ndarray:
    pts = lines.reshape(-1, 4)
    xs = np.concatenate([pts[:,0], pts[:,2]])
    ys = np.concatenate([pts[:,1], pts[:,3]])
    x_left, x_right = xs.min(), xs.max()
    y_top, y_bottom = ys.min(), ys.max()
    return np.array([
        [x_left,  y_top,    x_right, y_top   ],
        [x_left,  y_bottom, x_right, y_bottom],
        [x_left,  y_top,    x_left,  y_bottom],
        [x_right, y_top,    x_right, y_bottom]
    ], dtype=np.int32)

def detect_white_lines(img: np.ndarray) -> Optional[np.ndarray]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    return cv2.HoughLinesP(thresh, 1, np.pi/180, threshold=50,
                           minLineLength=max(30, img.shape[1]//5),
                           maxLineGap=10)

# ───────── main ─────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image",    required=True, help="Frame o captura a analizar.")
    ap.add_argument("--template", required=True, help="Plantilla JSON con mapRoi.")
    args = ap.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(args.image)

    H, W = frame.shape[:2]
    tpl   = load_rois(Path(args.template))
    ref   = tpl.get("reference_size")
    roi_pts = scale_pts(tpl["mapRoi"], W, H, ref)
    x0, y0, x1, y1 = bbox(roi_pts)
    roi = frame[y0:y1, x0:x1]

    # ── Guardar ROI recortado ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{ts}_minimap"
    cv2.imwrite(f"{prefix}_roi.png", roi)

    # ── Umbralizar para blancos ──
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    cv2.imwrite(f"{prefix}_thresh.png", thresh)

    # 1️⃣ contorno cerrado
    rect = find_white_rectangle(roi)

    # 2️⃣ o líneas Hough
    if rect is None:
        lines = detect_white_lines(roi)
        if lines is not None and len(lines) >= 3:
            # dibujar líneas para depuración y guardar
            lines_img = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
            for x1,y1,x2,y2 in lines.reshape(-1,4):
                cv2.line(lines_img, (x1,y1), (x2,y2), (0,255,0), 2)
            cv2.imwrite(f"{prefix}_lines.png", lines_img)

            rect_lines = complete_rectangle_from_lines(lines)
            xs = np.concatenate([rect_lines[:,0], rect_lines[:,2]])
            ys = np.concatenate([rect_lines[:,1], rect_lines[:,3]])
            rect = ((xs.min(), ys.min()),
                    (xs.max()-xs.min(), ys.max()-ys.min()))
        else:
            rect = None

    if rect is None:
        print("No se encontró rectángulo blanco en el minimapa.")
        return

    (rx, ry), (rw, rh) = rect
    top_left = (x0 + rx, y0 + ry)
    print(f"Rectángulo: pos={top_left}, size={(rw, rh)}")

    # ── Dibujar resultado ──
    out = frame.copy()
    cv2.polylines(out, [np.array(roi_pts)], True, (0, 255, 0), 1)
    cv2.rectangle(out, top_left, (top_left[0]+rw, top_left[1]+rh), (0, 255, 0), 2)
    cv2.putText(out, "Map ROI", (x0, y0-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,255,0), 1)

    final_name = f"minimap_detected_{ts}.jpg"
    cv2.imwrite(final_name, out)
    print(f"✔ Resultado final guardado en: {final_name}")

    cv2.imshow("Minimap detection", out)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
