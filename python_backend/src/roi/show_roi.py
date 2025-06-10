import cv2
import numpy as np
import json
import argparse
import tkinter as tk
from tkinter import ttk, filedialog
import os
import glob

def load_templates(folder):
    """
    Carga todos los archivos JSON de la carpeta especificada.
    Retorna un diccionario con la siguiente estructura:
    {
        "nombre_plantilla1": { "roi1": [[x,y], [x,y], ...], "roi2": ... },
        "nombre_plantilla2": { ... },
        ...
    }
    """
    templates = {}
    pattern = os.path.join(folder, "*.json")
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            name = os.path.splitext(os.path.basename(filepath))[0]
            templates[name] = data
        except Exception as e:
            print(f"Error cargando {filepath}: {e}")
    return templates

def draw_rois(frame, template):
    """
    Dibuja en el frame los ROIs definidos en la plantilla.
    Cada ROI se espera que sea una lista de puntos (ej. [[x1,y1], [x2,y2], ...]).
    Se dibujan con color verde.
    """
    for roi_key, points in template.items():
        try:
            pts = np.array(points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
        except Exception as e:
            print(f"Error dibujando {roi_key}: {e}")
    return frame

def main():
    parser = argparse.ArgumentParser(description="Mostrar ROIs sobre un video a partir de plantillas JSON.")
    parser.add_argument("video_path", help="Ruta al video")
    parser.add_argument("json_folder", help="Carpeta que contiene archivos JSON con plantillas de ROIs")
    args = parser.parse_args()

    # Cargar plantillas desde la carpeta
    templates = load_templates(args.json_folder)
    template_names = list(templates.keys())
    if not template_names:
        print("No se encontraron plantillas JSON en la carpeta especificada.")
        return

    # Variable para almacenar la plantilla actualmente seleccionada
    current_template = templates[template_names[0]]

    # Crear ventana de Tkinter con dropdown para seleccionar la plantilla
    root = tk.Tk()
    root.title("Seleccionar Plantilla de ROIs")

    selected_template_var = tk.StringVar(root)
    selected_template_var.set(template_names[0])

    tk.Label(root, text="Plantilla de ROIs:").pack(side=tk.LEFT, padx=5, pady=5)
    dropdown = tk.OptionMenu(root, selected_template_var, *template_names)
    dropdown.pack(side=tk.LEFT, padx=5, pady=5)

    # Actualizar la plantilla seleccionada cuando cambie el valor del dropdown
    def on_template_change(*args):
        nonlocal current_template
        sel = selected_template_var.get()
        if sel in templates:
            current_template = templates[sel]
    selected_template_var.trace("w", on_template_change)

    # Abrir el video
    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        print("❌ No se pudo abrir el video.")
        root.destroy()
        return

    window_name = "Video - [m: avanzar 10s | c: captura | q: salir]"
    cv2.namedWindow(window_name)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Dibujar los ROIs si se ha seleccionado una plantilla
        if current_template is not None:
            frame = draw_rois(frame, current_template)

        cv2.imshow(window_name, frame)

        key = cv2.waitKey(30) & 0xFF
        if key == ord('m'):
            # Avanzar 10 segundos en el video
            current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            cap.set(cv2.CAP_PROP_POS_MSEC, current_msec + 10000)
        elif key == ord('c'):
            # Capturar pantalla del frame actual con los ROIs
            # Se abre un diálogo para elegir dónde guardar la imagen.
            temp_root = tk.Tk()
            temp_root.withdraw()
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                title="Guardar captura de pantalla",
                filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("Todos", "*.*")]
            )
            temp_root.destroy()
            if filename:
                cv2.imwrite(filename, frame)
                print(f"Captura guardada en: {filename}")
        elif key == ord('q') or key == 27:
            break

        # Actualizar la ventana de Tkinter para mantener el dropdown activo
        root.update()

    cap.release()
    cv2.destroyAllWindows()
    root.destroy()

if __name__ == "__main__":
    main()
