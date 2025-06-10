# -*- coding: utf-8 -*-
"""
Detecta barras ROJAS en 'source.jpg', fusiona ROI solapadas o cercanas
y conserva únicamente las que tienen AR entre 4 y 6.
Encima de cada rectángulo se imprime:
  nombre | tamaño | posición | relación de aspecto
También se muestra la posición por consola.
"""
import cv2
import numpy as np


# ───────────── Helper functions ──────────────
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


# ──────────────── Main ────────────────
def main():
    # Rango(s) HSV y parámetros
    red_params = [
        (np.array([0,  50, 100]), np.array([10, 255, 255]), 300),
        (np.array([0, 100, 100]), np.array([10, 255, 255]), 300),
        (np.array([0, 100, 100]), np.array([10, 255, 255]), 500),
        (np.array([0, 150,  50]), np.array([10, 255, 255]), 300),
        (np.array([0, 150, 100]), np.array([10, 255, 255]), 300)
    ]
    ELONG_RATIO  = 0.5   # Altura < 0.5 × Anchura
    PROX_PX      = 4     # Máx. separación entre barras para fusionar
    AR_MIN, AR_MAX = 3, 7  # Filtro de relación de aspecto

    frame = cv2.imread("source.jpg")
    if frame is None:
        print("Error: no se encontró 'source.jpg'.")
        return

    # 1) Detectar todas las ROI candidatas
    rects = []
    for low, up, area in red_params:
        rects += detectar_roi_barra(frame, low, up, area)

    # 2) Filtrar por forma de barra
    rects = [(x, y, w, h) for x, y, w, h in rects if h < ELONG_RATIO * w]
    if not rects:
        print("No se detectaron barras rojas con forma alargada.")
        return

    # 3) Máscara con todas las barras
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    for x, y, w, h in rects:
        cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)

    # 4) Dilatar para fusionar barras cercanas
    k_size = 2 * PROX_PX + 1
    kernel = np.ones((k_size, k_size), np.uint8)
    mask   = cv2.dilate(mask, kernel, iterations=1)

    # 5) Contornos → rectángulos fusionados
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects_f = [cv2.boundingRect(c) for c in cnts]

    # 6) Filtro por relación de aspecto (4 ≤ AR ≤ 6)
    rects_filtered = []
    for x, y, w, h in rects_f:
        ar = w / h if h else 0
        if AR_MIN <= ar <= AR_MAX:
            rects_filtered.append((x, y, w, h))

    if not rects_filtered:
        print(f"No se encontraron barras con AR entre {AR_MIN} y {AR_MAX}.")
        return

    # 7) Dibujar y etiquetar los rectángulos seleccionados
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1
    for i, (x, y, w, h) in enumerate(rects_filtered, 1):
        ar = w / h
        label = f"Rect{i} | {w}x{h}px | ({x},{y}) | AR={ar:.2f}"
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # Posicionar texto
        (tw, th), _ = cv2.getTextSize(label, font, scale, thickness)
        tx, ty = x, y - 5
        if ty - th < 0:            # si no cabe arriba
            ty = y + h + th + 5    # lo ponemos debajo
        cv2.putText(frame, label, (tx, ty),
                    font, scale, (0, 0, 255), thickness, cv2.LINE_AA)

        print(label)               # imprimir en consola

    # 8) Mostrar resultado
    show_fullscreen("ROJO | ROI AR 4-6", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
