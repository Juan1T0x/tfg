# -*- coding: utf-8 -*-
"""
roi_viewer_normalized
=====================

Small utility that overlays one or more *Region-of-Interest* (ROI) 
templates on top of a video in real time.  
The same template can be reused for any resolution because coordinates
can be expressed either:

* **Normalised** (0–1 range) – already resolution-agnostic.
* **Absolute** – in the *reference resolution* indicated by the optional
  field ``"reference_size": [W_ref, H_ref]``.

During playback:

* **m** – skip forward 10 s  
* **c** – save a PNG/JPEG of the current frame with the ROIs  
* **q** / **Esc** – quit

Run from the command line:

    python roi_viewer_normalized.py path/to/video.mp4 path/to/templates
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog

# ---------------------------------------------------------------------------#
# Template utilities
# ---------------------------------------------------------------------------#
Coordinate = Tuple[float, float]
Template   = Dict[str, List[Coordinate]]


def load_templates(folder: str) -> Dict[str, Template]:
    """Read every ``*.json`` file in *folder* and return a mapping ``name → template``."""
    templates: Dict[str, Template] = {}
    for fp in glob.glob(os.path.join(folder, "*.json")):
        try:
            with open(fp, encoding="utf-8") as f:
                templates[Path(fp).stem] = json.load(f)
        except Exception as exc:
            print(f"⚠️  cannot load {fp}: {exc}")
    return templates


def _points_are_normalised(pts: List[Coordinate]) -> bool:
    """Return *True* if *all* points are in the range 0–1."""
    return all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in pts)


def _scale_points(
    points: List[Coordinate],
    frame_w: int,
    frame_h: int,
    ref_w: int | None,
    ref_h: int | None,
) -> List[Tuple[int, int]]:
    """
    Convert *points* to absolute pixel coordinates for the current frame.

    Priority
    --------
    1. If *reference_size* is provided → scale from that resolution.
    2. If points look normalised → scale by current ``frame_w/ frame_h``.
    3. Otherwise assume the coordinates are already absolute.
    """
    if ref_w and ref_h:
        sx, sy = frame_w / ref_w, frame_h / ref_h
        return [(int(x * sx), int(y * sy)) for x, y in points]

    if _points_are_normalised(points):
        return [(int(x * frame_w), int(y * frame_h)) for x, y in points]

    return [(int(x), int(y)) for x, y in points]


def draw_rois(frame: np.ndarray, template: Template,
              colour: Tuple[int, int, int] = (0, 255, 0)) -> np.ndarray:
    """Draw every ROI found in *template* on *frame* and label it with its key."""
    h, w = frame.shape[:2]
    ref_w, ref_h = template.get("reference_size", (None, None))

    font, fscale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1

    for key, pts in template.items():
        if key == "reference_size":
            continue

        abs_pts = _scale_points(pts, w, h, ref_w, ref_h)
        cv2.polylines(frame, [np.array(abs_pts, np.int32)], True, colour, 2)

        # Bounding-box to position the label
        xs, ys = zip(*abs_pts)
        x0, y0 = min(xs), min(ys)

        (tw, th), _ = cv2.getTextSize(key, font, fscale, thick)
        ty = y0 - 5 if y0 - th - 5 >= 0 else y0 + th + 5

        # Semi-transparent background for better readability
        overlay = frame.copy()
        cv2.rectangle(overlay, (x0, ty - th - 2), (x0 + tw + 4, ty + 2), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        cv2.putText(frame, key, (x0 + 2, ty), font, fscale, (255, 255, 255), thick,
                    cv2.LINE_AA)
    return frame


# ---------------------------------------------------------------------------#
# Main player
# ---------------------------------------------------------------------------#
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Overlay ROI templates (normalised or absolute) on a video."
    )
    parser.add_argument("video_path",  help="Path to the video file")
    parser.add_argument("json_folder", help="Folder containing *.json templates")
    args = parser.parse_args()

    templates = load_templates(args.json_folder)
    if not templates:
        print("❌ No JSON templates found in the given folder.")
        return

    template_names = list(templates)
    current_template: Template = templates[template_names[0]]

    # Simple Tk drop-down to choose the active template
    root = tk.Tk()
    root.title("ROI template selector")
    tk.Label(root, text="Template:").pack(side=tk.LEFT, padx=5, pady=5)

    sel_var = tk.StringVar(root, template_names[0])
    tk.OptionMenu(root, sel_var, *template_names).pack(side=tk.LEFT, padx=5, pady=5)

    def _change(*_) -> None:
        nonlocal current_template
        current_template = templates[sel_var.get()]

    sel_var.trace_add("write", _change)

    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        print("❌ Unable to open video.")
        root.destroy()
        return

    win = "Video  |  m: +10 s   c: capture   q/ESC: quit"
    cv2.namedWindow(win)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = draw_rois(frame, current_template)
        cv2.imshow(win, frame)

        key = cv2.waitKey(30) & 0xFF
        if key == ord("m"):                              # +10 s
            cap.set(cv2.CAP_PROP_POS_MSEC,
                    cap.get(cv2.CAP_PROP_POS_MSEC) + 10_000)
        elif key == ord("c"):                            # save frame
            dlg = tk.Tk(); dlg.withdraw()
            fname = filedialog.asksaveasfilename(
                defaultextension=".png",
                title="Save frame",
                filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("All", "*.*")],
            )
            dlg.destroy()
            if fname:
                cv2.imwrite(fname, frame)
                print(f"✔ Saved to {fname}")
        elif key in (ord("q"), 27):                      # quit
            break

        root.update()

    cap.release()
    cv2.destroyAllWindows()
    root.destroy()


if __name__ == "__main__":
    main()
