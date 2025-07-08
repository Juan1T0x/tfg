#!/usr/bin/env python3
# services/live_game_analysis/main_game/minimap/minimap_rect_detection.py
"""
Minimap white-rectangle detector
--------------------------------

Given a full broadcast frame and a JSON template that describes the minimap
region, this utility locates the *current-position* white rectangle and writes
an evidence bundle to disk:

    <timestamp>_minimap_roi.png       – cropped minimap
    <timestamp>_minimap_thresh.png    – white threshold inside the minimap
    <timestamp>_minimap_lines.png     – Hough lines (only if fallback used)
    minimap_detected_<timestamp>.jpg  – final overlay on the original frame

Detection strategy
~~~~~~~~~~~~~~~~~~
1. Hard threshold on the minimap ROI to isolate very bright pixels.
2. Two complementary shape finders are tried in order:

   * **Closed contour** – look for a 4-point contour whose centre pixel is
     dark (prevents catching score boxes, timers, etc.).
   * **Hough fallback** – if the contour search fails, use
     :func:`cv2.HoughLinesP` to find up to four white segments and build the
     bounding box from their extrema.

CLI
~~~
::

    python minimap_rect_detection.py --image frame.jpg --template rois.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# --------------------------------------------------------------------- #
# Type aliases                                                          #
# --------------------------------------------------------------------- #
Coord = Tuple[float, float]                      # (x, y) normalised or abs-px
BBox  = Tuple[int, int, int, int]               # x0, y0, x1, y1


# --------------------------------------------------------------------- #
# Template helpers                                                      #
# --------------------------------------------------------------------- #
def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _scale_points(
    pts: List[Coord],
    fw: int,
    fh: int,
    ref: Tuple[int, int] | None,
) -> List[Tuple[int, int]]:
    """Convert the template points to absolute pixel coordinates."""
    if ref:
        rw, rh = ref
        sx, sy = fw / rw, fh / rh
        return [(int(x * sx), int(y * sy)) for x, y in pts]

    if all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts):
        return [(int(x * fw), int(y * fh)) for x, y in pts]

    return [(int(x), int(y)) for x, y in pts]


def _bbox(pts: List[Tuple[int, int]]) -> BBox:
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


# --------------------------------------------------------------------- #
# Geometry detection                                                    #
# --------------------------------------------------------------------- #
def _find_white_rectangle(
    roi: np.ndarray,
) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Try to locate the 4-point closed white contour inside *roi*."""
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in cnts:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) != 4:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        if w < 20 or h < 20:                    # too small → noise
            continue
        if gray[y + h // 2, x + w // 2] < 50:   # inner pixel must be dark
            return (x, y), (w, h)
    return None


def _hough_lines(roi: np.ndarray) -> Optional[np.ndarray]:
    """Fallback rectangle inference via probabilistic Hough."""
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    return cv2.HoughLinesP(
        th,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=max(30, roi.shape[1] // 5),
        maxLineGap=10,
    )


def _rect_from_lines(lines: np.ndarray) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Return top-left + size from the extreme points of *lines*."""
    pts = lines.reshape(-1, 4)
    xs = np.concatenate([pts[:, 0], pts[:, 2]])
    ys = np.concatenate([pts[:, 1], pts[:, 3]])
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    return (x0, y0), (x1 - x0, y1 - y0)


# --------------------------------------------------------------------- #
# Main                                                                  #
# --------------------------------------------------------------------- #
def _parse_cli() -> argparse.Namespace:
    ap = argparse.ArgumentParser("Detect the white-position rectangle on the minimap.")
    ap.add_argument("--image", required=True, help="Broadcast frame.")
    ap.add_argument("--template", required=True, help="JSON with “mapRoi”.")
    return ap.parse_args()


def main() -> None:
    args = _parse_cli()

    frame = cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(args.image)
    fh, fw = frame.shape[:2]

    tpl = _load_json(Path(args.template))
    ref = tpl.get("reference_size")
    roi_points = _scale_points(tpl["mapRoi"], fw, fh, ref)
    x0, y0, x1, y1 = _bbox(roi_points)
    roi = frame[y0:y1, x0:x1]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{ts}_minimap"
    cv2.imwrite(f"{prefix}_roi.png", roi)

    # ----- white threshold (saved for debugging) -----------------------
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    cv2.imwrite(f"{prefix}_thresh.png", thresh)

    # 1️⃣ contour-based
    rect = _find_white_rectangle(roi)

    # 2️⃣ Hough fallback
    if rect is None:
        lines = _hough_lines(roi)
        if lines is not None and len(lines) >= 3:
            dbg = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
            for x1, y1, x2, y2 in lines.reshape(-1, 4):
                cv2.line(dbg, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.imwrite(f"{prefix}_lines.png", dbg)
            rect = _rect_from_lines(lines)

    if rect is None:
        print("No white rectangle found in the minimap.")
        return

    (rx, ry), (rw, rh) = rect
    abs_top_left = (x0 + rx, y0 + ry)
    print(f"White rectangle @ {abs_top_left}, size {(rw, rh)} px")

    # Overlay on the original frame
    vis = frame.copy()
    cv2.polylines(vis, [np.array(roi_points)], True, (0, 255, 0), 1)
    cv2.rectangle(vis, abs_top_left, (abs_top_left[0] + rw, abs_top_left[1] + rh), (0, 255, 0), 2)
    cv2.putText(
        vis,
        "Map ROI",
        (x0, y0 - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (0, 255, 0),
        1,
        cv2.LINE_AA,
    )

    out_name = f"minimap_detected_{ts}.jpg"
    cv2.imwrite(out_name, vis)
    print(f"✔ Result written to {out_name}")

    cv2.imshow("Minimap detection", vis)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
