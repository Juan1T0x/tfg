import cv2
import numpy as np
import json
import argparse
import tkinter as tk
import os
from tkinter import messagebox, filedialog

# --------------------------
# CLASE PARA MANEJO DE ROIs
# --------------------------
class ROIGenerator:
    def __init__(self, frame):
        # Frame base sobre el que se dibujará
        self.base_frame = frame.copy()
        # ROI actual (lista de puntos [x,y] que se está dibujando)
        self.current_roi = []
        # Lista de ROIs finalizadas (cada ROI es una lista de puntos)
        self.roi_template = []
        # Pila para deshacer/rehacer puntos en la ROI actual
        self.undo_stack = []

    def add_point(self, point):
        self.current_roi.append(point)
        # Cada vez que se añade un punto se limpia la pila de redo
        self.undo_stack.clear()

    def undo(self):
        if self.current_roi:
            pt = self.current_roi.pop()
            self.undo_stack.append(pt)

    def redo(self):
        if self.undo_stack:
            pt = self.undo_stack.pop()
            self.current_roi.append(pt)

    def finalize_current_roi(self):
        # Se requiere al menos 3 puntos para considerar un ROI válido
        if len(self.current_roi) < 3:
            return False

        # Confirmación mediante ventana emergente
        root = tk.Tk()
        root.withdraw()
        result = messagebox.askyesno("Confirm ROI", "¿Desea guardar este ROI?")
        root.destroy()

        if result:
            # Se guarda una copia de la ROI actual en la plantilla
            self.roi_template.append(self.current_roi.copy())
            # Se limpia la ROI actual y la pila de deshacer
            self.current_roi.clear()
            self.undo_stack.clear()
            return True
        return False

    def get_drawing(self):
        """
        Retorna una imagen (copia del frame base) con:
         - Los ROIs ya finalizados dibujados en verde.
         - La ROI actual (en proceso) dibujada en rojo.
        """
        img = self.base_frame.copy()
        # Dibujar ROIs finalizadas (cerradas)
        for roi in self.roi_template:
            pts = np.array(roi, np.int32).reshape((-1, 1, 2))
            cv2.polylines(img, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
        # Dibujar la ROI en construcción (líneas y puntos)
        if self.current_roi:
            pts = np.array(self.current_roi, np.int32).reshape((-1, 1, 2))
            cv2.polylines(img, [pts], isClosed=False, color=(0, 0, 255), thickness=2)
            for pt in self.current_roi:
                cv2.circle(img, tuple(pt), 4, (0, 0, 255), -1)
        return img

# --------------------------
# CALLBACK DEL MOUSE
# --------------------------
def roi_mouse_callback(event, x, y, flags, param):
    """
    Cada clic izquierdo añade un punto a la ROI actual.
    """
    roi_gen = param  # Instancia de ROIGenerator
    if event == cv2.EVENT_LBUTTONDOWN:
        roi_gen.add_point([x, y])

# --------------------------
# FUNCIÓN PARA MODO ROI
# --------------------------
def run_roi_mode(frame):
    """
    Modo de edición de ROIs:
      - Se muestra el frame congelado.
      - El usuario dibuja ROIs haciendo clic izquierdo.
      - 'z' deshace el último punto, 'y' lo rehace.
      - 'c' confirma la ROI actual (se requiere al menos 3 puntos).
      - 's' guarda la plantilla completa (se abre un diálogo para elegir nombre).
      - 'q' cancela el modo y se reanuda el video.
    """
    roi_gen = ROIGenerator(frame)
    window_name = "ROI Editor - [c: confirmar ROI | s: guardar plantilla | q: cancelar | z: deshacer | y: rehacer]"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, roi_mouse_callback, roi_gen)

    while True:
        img = roi_gen.get_drawing()
        cv2.imshow(window_name, img)
        key = cv2.waitKey(20) & 0xFF

        if key == ord('z'):
            roi_gen.undo()
        elif key == ord('y'):
            roi_gen.redo()
        elif key == ord('c'):
            # Confirmar la ROI actual (se requiere mínimo 3 puntos)
            if len(roi_gen.current_roi) < 3:
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo("Error", "Se requieren al menos 3 puntos para un ROI.")
                root.destroy()
            else:
                roi_gen.finalize_current_roi()
        elif key == ord('s'):
            # Guardar la plantilla de ROIs
            if len(roi_gen.roi_template) == 0:
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo("Info", "No hay ROIs para guardar.")
                root.destroy()
            else:
                root = tk.Tk()
                root.withdraw()
                result = messagebox.askyesno("Guardar Plantilla", "¿Está conforme con los ROIs definidos y desea guardarlos?")
                root.destroy()
                if result:
                    # Crear carpeta "output" si no existe
                    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
                    os.makedirs(output_dir, exist_ok=True)

                    root = tk.Tk()
                    root.withdraw()
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".json",
                        title="Guardar plantilla ROI",
                        filetypes=[("JSON files", "*.json")],
                        initialdir=output_dir
                    )
                    root.destroy()
                    if filename:
                        # Se arma un diccionario con las ROIs: roi1, roi2, …
                        data = {}
                        for i, roi in enumerate(roi_gen.roi_template):
                            key_name = f"roi{i+1}"
                            data[key_name] = roi
                        try:
                            with open(filename, "w") as f:
                                json.dump(data, f, indent=4)
                            root = tk.Tk()
                            root.withdraw()
                            messagebox.showinfo("Éxito", f"Plantilla guardada en:\n{filename}")
                            root.destroy()
                        except Exception as e:
                            root = tk.Tk()
                            root.withdraw()
                            messagebox.showerror("Error", f"No se pudo guardar la plantilla:\n{e}")
                            root.destroy()
                    # Al guardar, se sale del modo ROI y se reanuda el video.
                    break

        elif key == ord('q') or key == 27:
            # Cancelar el modo ROI sin guardar
            break

    cv2.destroyWindow(window_name)

# --------------------------
# FUNCIÓN PRINCIPAL
# --------------------------
def main():
    parser = argparse.ArgumentParser(
        description="ROI Generator: Defina plantillas de ROIs para un video."
    )
    parser.add_argument("video_path", help="Ruta al video")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        print("❌ Error: No se pudo abrir el video.")
        return

    window_name = "Video - [r: definir ROIs | m: avanzar 10s | q: salir]"
    cv2.namedWindow(window_name)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow(window_name, frame)
        key = cv2.waitKey(30) & 0xFF

        if key == ord('r'):
            # Pausar y entrar en modo ROI usando el frame actual
            run_roi_mode(frame)
        elif key == ord('m'):
            # Avanzar 10 segundos en el video
            current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            cap.set(cv2.CAP_PROP_POS_MSEC, current_msec + 10000)
        elif key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
