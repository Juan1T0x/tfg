# -*- coding: utf-8 -*-
"""
Detecta barras AZULES en 'source.jpg' y muestra la imagen procesada
(ROI dibujadas) a pantalla completa.
"""
import cv2
import numpy as np


def detectar_roi_barra(frame, lower, upper, area_thresh, kernel=3):
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)
    k    = np.ones((kernel, kernel), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > area_thresh]


def get_screen_resolution(default=(1920, 1080)):
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        return w, h
    except Exception:
        return default


def show_fullscreen(name, img):
    scr_w, scr_h = get_screen_resolution()
    cv2.namedWindow(name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(name, scr_w, scr_h)
    cv2.moveWindow(name, 0, 0)
    cv2.imshow(name, img)


def main():
    lower_blue  = np.array([95, 50, 50])
    upper_blue  = np.array([125, 255, 255])
    area_thresh = 300
    elong_ratio = 0.5

    frame = cv2.imread("source.jpg")
    if frame is None:
        print("Error: no se encontró 'source.jpg'.")
        return

    rois = detectar_roi_barra(frame, lower_blue, upper_blue, area_thresh)
    for x, y, w, h in rois:
        if h < elong_ratio * w:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

    show_fullscreen("AZUL | ROI", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
