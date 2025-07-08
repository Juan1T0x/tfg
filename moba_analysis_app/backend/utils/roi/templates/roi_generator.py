#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
roi_generator.py
================

Interactive tool to create *Region-of-Interest* (ROI) templates for a video.
While the video is playing, press **r** to pause on the current frame and
start drawing polygons that describe the ROIs.  The resulting template is
stored as a JSON file that maps ``roi1``, ``roi2``, … to a list of points
in screen coordinates.

Keyboard shortcuts
------------------
Global player:
    r   enter ROI editor on the current frame  
    m   skip 10 seconds forward  
    q   quit

ROI editor:
    left-click   add vertex  
    z            undo last vertex  
    y            redo  
    c            close current polygon and confirm  
    s            save all confirmed polygons to JSON  
    q | Esc      cancel editor without saving
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox

# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #
Point = Tuple[int, int]
ROI   = List[Point]                # a polygon
Tpl   = List[ROI]                  # template = list of polygons


# --------------------------------------------------------------------------- #
# ROI helper
# --------------------------------------------------------------------------- #
class ROIGenerator:
    """
    Helper object that keeps track of the polygon being drawn and all
    previously confirmed polygons.

    Parameters
    ----------
    frame :
        The BGR image that serves as a backdrop while editing.

    Attributes
    ----------
    base_frame :
        Original frame (never modified).
    current_roi :
        List of vertices the user has added for the ROI in progress.
    roi_template :
        List of ROIs that have already been confirmed.
    _redo_stack :
        Auxiliary stack to support *redo* after an *undo*.
    """

    def __init__(self, frame: np.ndarray) -> None:
        self.base_frame: np.ndarray = frame.copy()
        self.current_roi: ROI = []
        self.roi_template: Tpl = []
        self._redo_stack: ROI = []

    # ---------- editing primitives ---------------------------------------- #
    def add_point(self, pt: Point) -> None:
        """Append *pt* to :pyattr:`current_roi` and clear the redo stack."""
        self.current_roi.append(pt)
        self._redo_stack.clear()

    def undo(self) -> None:
        """Remove the last vertex, pushing it onto :pyattr:`_redo_stack`."""
        if self.current_roi:
            self._redo_stack.append(self.current_roi.pop())

    def redo(self) -> None:
        """Pop a vertex from :pyattr:`_redo_stack` back onto the polygon."""
        if self._redo_stack:
            self.current_roi.append(self._redo_stack.pop())

    # ---------- finalisation --------------------------------------------- #
    def finalise(self) -> bool:
        """
        Close and **confirm** the current polygon.  A confirmation dialog
        is shown; if the user accepts, the polygon is moved to
        :pyattr:`roi_template`.

        Returns ``True`` on success, ``False`` otherwise.
        """
        if len(self.current_roi) < 3:
            return False

        root = tk.Tk(); root.withdraw()
        ok = messagebox.askyesno("Confirm ROI", "Guardar este polígono?")
        root.destroy()

        if not ok:
            return False

        self.roi_template.append(self.current_roi.copy())
        self.current_roi.clear()
        self._redo_stack.clear()
        return True

    # ---------- visualisation -------------------------------------------- #
    def render(self) -> np.ndarray:
        """
        Return a copy of :pyattr:`base_frame` with:

        * confirmed polygons in **green**
        * the polygon in progress in **red**
        """
        img = self.base_frame.copy()

        # confirmed polygons
        for roi in self.roi_template:
            pts = np.array(roi, np.int32).reshape(-1, 1, 2)
            cv2.polylines(img, [pts], True, (0, 255, 0), 2)

        # current polygon
        if self.current_roi:
            pts = np.array(self.current_roi, np.int32).reshape(-1, 1, 2)
            cv2.polylines(img, [pts], False, (0, 0, 255), 2)
            for x, y in self.current_roi:
                cv2.circle(img, (x, y), 4, (0, 0, 255), -1)

        return img


# --------------------------------------------------------------------------- #
# Mouse callback
# --------------------------------------------------------------------------- #
def _mouse_callback(event: int, x: int, y: int, _flags, roi_gen: ROIGenerator):
    if event == cv2.EVENT_LBUTTONDOWN:
        roi_gen.add_point((x, y))


# --------------------------------------------------------------------------- #
# ROI editor UI
# --------------------------------------------------------------------------- #
def edit_rois(frame: np.ndarray) -> None:
    roi_gen = ROIGenerator(frame)
    win = ("ROI Editor | c: close ROI  s: save template  "
           "z/y: undo/redo  q/Esc: quit")

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, _mouse_callback, roi_gen)

    while True:
        cv2.imshow(win, roi_gen.render())
        key = cv2.waitKey(20) & 0xFF

        if key == ord("z"):
            roi_gen.undo()
        elif key == ord("y"):
            roi_gen.redo()
        elif key == ord("c"):
            if len(roi_gen.current_roi) < 3:
                _info("Se necesitan al menos 3 vértices.")
            else:
                roi_gen.finalise()
        elif key == ord("s"):
            _save_template(roi_gen.roi_template)
            break
        elif key in (ord("q"), 27):
            break

    cv2.destroyWindow(win)


def _save_template(template: Tpl) -> None:
    if not template:
        _info("No hay ROIs para guardar.")
        return

    root = tk.Tk(); root.withdraw()
    if not messagebox.askyesno("Guardar", "Guardar las ROIs definidas?"):
        root.destroy(); return
    root.destroy()

    default_dir = Path(__file__).with_suffix("") / "output"
    default_dir.mkdir(parents=True, exist_ok=True)

    dlg = tk.Tk(); dlg.withdraw()
    filename = filedialog.asksaveasfilename(
        defaultextension=".json",
        title="Guardar plantilla ROI",
        initialdir=default_dir,
        filetypes=[("JSON", "*.json")],
    )
    dlg.destroy()
    if not filename:
        return

    data = {f"roi{i + 1}": roi for i, roi in enumerate(template)}
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        _info(f"Plantilla guardada en:\n{filename}", title="Éxito")
    except Exception as exc:
        _info(f"No se pudo guardar la plantilla:\n{exc}", title="Error", err=True)


def _info(msg: str, *, title: str = "Info", err: bool = False) -> None:
    root = tk.Tk(); root.withdraw()
    (messagebox.showerror if err else messagebox.showinfo)(title, msg)
    root.destroy()


# --------------------------------------------------------------------------- #
# Video player
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive ROI template creator")
    parser.add_argument("video_path", help="Ruta al vídeo")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        print("❌ No se pudo abrir el vídeo.")
        return

    win = "Player | r: ROI editor  m: +10 s  q/Esc: quit"
    cv2.namedWindow(win)

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        cv2.imshow(win, frame)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("r"):
            edit_rois(frame)
        elif key == ord("m"):
            cap.set(cv2.CAP_PROP_POS_MSEC,
                    cap.get(cv2.CAP_PROP_POS_MSEC) + 10_000)
        elif key in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
