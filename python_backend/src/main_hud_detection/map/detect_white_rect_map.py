import cv2
import json
import argparse
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

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
    """Busca un contorno rectangular completo (4 lados)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            if w < 20 or h < 20:  # descarta pequeños
                continue
            # centro oscuro → hueco interior
            if gray[y + h//2, x + w//2] < 50:
                return (x, y), (w, h)
    return None


def complete_rectangle_from_lines(lines: np.ndarray) -> np.ndarray:
    """A partir de ≥3 líneas (HoughLinesP Nx4) genera las 4 líneas de un rectángulo.
    Devuelve array (4×4) con [x1,y1,x2,y2] en el mismo sistema de coords que *img*"""
    pts = lines.reshape(-1, 4)
    xs = np.concatenate([pts[:,0], pts[:,2]])
    ys = np.concatenate([pts[:,1], pts[:,3]])
    x_left, x_right = xs.min(), xs.max()
    y_top, y_bottom = ys.min(), ys.max()
    rect_lines = np.array([
        [x_left,  y_top,    x_right, y_top   ],  # top
        [x_left,  y_bottom, x_right, y_bottom],  # bottom
        [x_left,  y_top,    x_left,  y_bottom],  # left
        [x_right, y_top,    x_right, y_bottom]   # right
    ], dtype=np.int32)
    return rect_lines


def detect_white_lines(img: np.ndarray) -> Optional[np.ndarray]:
    """Devuelve líneas blancas detectadas con HoughLinesP o None."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    lines = cv2.HoughLinesP(thresh, 1, np.pi/180, threshold=50,
                            minLineLength=max(30, img.shape[1]//5),
                            maxLineGap=10)
    return lines  # puede ser None

# ───────── main ─────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--output", default="output.png")
    args = ap.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(args.image)

    H, W = frame.shape[:2]
    tpl = load_rois(Path(args.template))
    ref = tpl.get("reference_size")
    roi_pts = scale_pts(tpl["mapRoi"], W, H, ref)
    x0, y0, x1, y1 = bbox(roi_pts)
    roi = frame[y0:y1, x0:x1]

    # 1️⃣ contorno cerrado
    rect = find_white_rectangle(roi)

    # 2️⃣ o líneas Hough + completar
    if rect is None:
        lines = detect_white_lines(roi)
        if lines is not None and len(lines) >= 3:
            rect_lines = complete_rectangle_from_lines(lines)
            # convierte a bbox
            x_left, y_top, x_right, y_bottom = rect_lines[:,[0,1,2,3]].reshape(-1,4).min(axis=0)[0], rect_lines[:,1].min(), rect_lines[:,2].max(), rect_lines[:,3].max()
            rect = ((x_left, y_top), (x_right - x_left, y_bottom - y_top))
        else:
            rect = None

    if rect is None:
        print("No white rectangle found in map ROI.")
        return

    (rx, ry), (rw, rh) = rect
    top_left = (x0 + rx, y0 + ry)
    print(f"Rectangle position: {top_left}, size: {(rw, rh)}")

    # dibuja resultados
    out = frame.copy()
    cv2.polylines(out, [np.array(roi_pts)], True, (0, 255, 0), 1)
    cv2.rectangle(out, top_left, (top_left[0] + rw, top_left[1] + rh), (0, 255, 0), 2)
    cv2.putText(out, "Map ROI", (x0, y0 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    cv2.imwrite(args.output, out)
    print(f"Saved result → {args.output}")
    cv2.imshow("Detected Rectangle", out)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
