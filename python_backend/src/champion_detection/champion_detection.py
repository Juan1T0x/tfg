import cv2
import numpy as np
import json
import argparse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import glob
from PIL import Image, ImageTk

def load_templates(folder):
    """
    Carga todos los archivos JSON de la carpeta especificada.
    Retorna un diccionario con la siguiente estructura:
    {
        "nombre_plantilla1": { "roi1": [[x,y], ...], ... },
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
    """
    for roi_key, points in template.items():
        try:
            pts = np.array(points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
        except Exception as e:
            print(f"Error dibujando {roi_key}: {e}")
    return frame

def get_bounding_box(points):
    """
    Dado una lista de puntos [[x,y], ...], devuelve (min_x, min_y, max_x, max_y).
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)

def subdivide_roi(bbox, subdivisions=5):
    """
    Dado un bounding box (min_x, min_y, max_x, max_y) de un ROI, 
    subdivide horizontalmente en 'subdivisions' sub-regiones.
    Retorna una lista de sub-boxes, cada una como (x1, y1, x2, y2).
    """
    min_x, min_y, max_x, max_y = bbox
    width = max_x - min_x
    sub_width = width // subdivisions
    sub_boxes = []
    for i in range(subdivisions):
        x1 = min_x + i * sub_width
        # Para la última subdivisión, usamos max_x para asegurar que no queden píxeles sueltos
        x2 = min_x + (i+1) * sub_width if i < subdivisions - 1 else max_x
        sub_boxes.append((x1, min_y, x2, max_y))
    return sub_boxes

def load_champion_images(champion_folder):
    """
    Carga las imágenes de campeón de la carpeta dada.
    Retorna un diccionario: { champion_name: image, ... }
    """
    champ_templates = {}
    pattern = os.path.join(champion_folder, "*")
    for filepath in glob.glob(pattern):
        if os.path.isfile(filepath) and filepath.lower().endswith(('.jpg', '.jpeg', '.png')):
            base = os.path.basename(filepath)
            # Se asume que el nombre es "Aatrox_loading_high_res.jpg" y se extrae "Aatrox"
            name = base.split('_')[0]
            img = cv2.imread(filepath)
            if img is not None:
                champ_templates[name] = img
    return champ_templates

def detect_top_candidates(subregion, champ_templates, top_n=5):
    """
    Realiza una comparación basada en feature matching (ORB) para cada campeón
    y retorna una lista de los top_n candidatos ordenados por "score" (de mayor a menor).
    
    El 'score' se define como la cantidad de "buenos matches" entre la subregión y la
    imagen del campeón. Antes de extraer features, se escala la imagen del campeón
    si ésta es más grande que la subregión.
    """
    # Preprocesamiento de la subregión
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5,-1], [0, -1, 0]])
    sharpened = cv2.filter2D(subregion, -1, sharpen_kernel)
    gray = cv2.cvtColor(sharpened, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    sub_gray = clahe.apply(gray)

    cv2.imshow("Subregion", sub_gray)
    cv2.waitKey(1)  # Para actualizar la ventana de OpenCV

    sub_h, sub_w = sub_gray.shape[:2]

    # Creamos el detector/descriptor ORB
    orb = cv2.ORB_create()

    # Detectamos y extraemos descriptores en la subregión
    keypoints_sub, descriptors_sub = orb.detectAndCompute(sub_gray, None)
    if descriptors_sub is None:
        # Si no hay descriptores en la subregión, retornamos lista vacía
        return []

    # Creamos el objeto BFMatcher (para descriptores binarios tipo ORB, NORM_HAMMING)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    scores = []
    for champ, template in champ_templates.items():
        # Escalamos la imagen del campeón si es más grande que la subregión
        temp_h, temp_w = template.shape[:2]
        scale_factor = min(sub_w / temp_w, sub_h / temp_h)

        if scale_factor < 1.0:
            new_w = max(1, int(temp_w * scale_factor))
            new_h = max(1, int(temp_h * scale_factor))
            resized_template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            resized_template = template

        # Convertimos a gris y detectamos/caracterizamos features
        temp_gray = cv2.cvtColor(resized_template, cv2.COLOR_BGR2GRAY)
        keypoints_temp, descriptors_temp = orb.detectAndCompute(temp_gray, None)
        if descriptors_temp is None:
            # Si no hay descriptores, score=0
            scores.append((champ, 0))
            continue

        # Emparejamos descriptores
        matches = bf.match(descriptors_sub, descriptors_temp)
        # Ordenamos por distancia ascendente (los mejores primero)
        matches = sorted(matches, key=lambda x: x.distance)

        # Definimos un criterio para considerar "buenos" matches
        # Por ejemplo, todos aquellos con distancia < 50
        good_matches = [m for m in matches if m.distance < 50]

        # El score puede ser simplemente la cantidad de buenos matches
        score = len(good_matches)

        scores.append((champ, score))

    # Ordenamos los campeones por score en orden descendente
    scores = sorted(scores, key=lambda x: x[1], reverse=True)
    return scores[:top_n]

def confirm_candidate(sub_region, candidates, champ_templates):
    """
    Muestra una ventana emergente con el trozo de frame (sub_region) y 5 candidatos (con sus scores),
    mostrando los keypoints y descriptores sobre la imagen de la subregión y sobre los candidatos.
    Además, incluye un botón para mostrar las líneas del BFMatcher entre la subregión y cada candidato.
    - Botón "Siguiente (Aceptar)" -> selecciona el primer candidato.
    - Botón "Elección Manual" -> el usuario elige del dropdown.
    Retorna el campeón seleccionado.
    """
    selected_candidate = {"champion": None}
    window = tk.Toplevel()
    window.title("Confirmar Campeón")

    orb = cv2.ORB_create()

    # Procesar la subregión: dibujar keypoints

    # Preprocesamiento del ROI

    # Enfocar con kernel sharpen
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5,-1], [0, -1, 0]])
    sharpened = cv2.filter2D(sub_region, -1, sharpen_kernel)
    # Convertir a gris
    gray = cv2.cvtColor(sharpened, cv2.COLOR_BGR2GRAY)
    # Aplicar CLAHE (mejora contraste local adaptativo)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    sub_gray = clahe.apply(gray)
    cv2.imshow("Subregion", sub_gray)
    cv2.waitKey(1)  # Para actualizar la ventana de OpenCV

    kp_sub, des_sub = orb.detectAndCompute(sub_gray, None)
    sub_kp_image = cv2.drawKeypoints(sub_region, kp_sub, None, color=(0, 255, 0), flags=0)
    sub_rgb = cv2.cvtColor(sub_kp_image, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(sub_rgb).resize((200, 200))
    tk_img = ImageTk.PhotoImage(pil_img)
    label_sub = tk.Label(window, image=tk_img)
    label_sub.image = tk_img
    label_sub.pack(side=tk.LEFT, padx=10, pady=10)

    # Frame derecho
    frame_candidates = tk.Frame(window)
    frame_candidates.pack(side=tk.RIGHT, padx=10, pady=10)

    # Mostrar cada uno de los 5 mejores candidatos con keypoints
    for champ, score in candidates:
        candidate_frame = tk.Frame(frame_candidates)
        candidate_frame.pack(fill=tk.X, pady=2)
        template_img = champ_templates.get(champ)
        if template_img is not None:
            temp_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
            kp_temp, _ = orb.detectAndCompute(temp_gray, None)
            temp_kp_image = cv2.drawKeypoints(template_img, kp_temp, None, color=(0, 255, 0), flags=0)
            temp_rgb = cv2.cvtColor(temp_kp_image, cv2.COLOR_BGR2RGB)
            pil_template = Image.fromarray(temp_rgb).resize((80, 80))
            tk_template = ImageTk.PhotoImage(pil_template)
            label_img = tk.Label(candidate_frame, image=tk_template)
            label_img.image = tk_template
            label_img.pack(side=tk.LEFT)
        label_text = tk.Label(candidate_frame, text=f"{champ}: {score}")
        label_text.pack(side=tk.LEFT, padx=5)

    # ---------------------
    # Vista previa dinámica
    # ---------------------
    manual_var = tk.StringVar(window)
    manual_var.set(candidates[0][0] if candidates else "Unknown")

    # Frame para el dropdown y vista previa
    dropdown = tk.OptionMenu(frame_candidates, manual_var, *champ_templates.keys())
    dropdown.pack(pady=5)

    preview_frame = tk.Frame(frame_candidates)
    preview_frame.pack(pady=10)

    tk.Label(preview_frame, text="Vista previa del seleccionado:").pack()

    preview_label = tk.Label(preview_frame)
    preview_label.pack()

    def update_preview(*args):
        champ_name = manual_var.get()
        img = champ_templates.get(champ_name)
        if img is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            kp, _ = orb.detectAndCompute(gray, None)
            img_with_kp = cv2.drawKeypoints(img, kp, None, color=(0, 255, 0), flags=0)
            rgb = cv2.cvtColor(img_with_kp, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb).resize((100, 100))
            tk_img = ImageTk.PhotoImage(pil_img)
            preview_label.config(image=tk_img)
            preview_label.image = tk_img

    manual_var.trace_add("write", update_preview)
    update_preview()

    # ---------------------
    # Botón para mostrar matches visuales
    # ---------------------
    def show_matches():
        match_window = tk.Toplevel(window)
        match_window.title("Matches")
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        for champ, score in candidates:
            template_img = champ_templates.get(champ)
            if template_img is None:
                continue
            temp_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
            kp_temp, des_temp = orb.detectAndCompute(temp_gray, None)
            if des_sub is None or des_temp is None:
                continue
            matches = bf.match(des_sub, des_temp)
            good_matches = [m for m in matches if m.distance < 50]
            match_img = cv2.drawMatches(sub_region, kp_sub, template_img, kp_temp, good_matches, None, flags=2)
            match_img = cv2.cvtColor(match_img, cv2.COLOR_BGR2RGB)
            pil_match = Image.fromarray(match_img).resize((400, 200))
            tk_match = ImageTk.PhotoImage(pil_match)
            frame = tk.Frame(match_window)
            frame.pack(padx=5, pady=5)
            tk.Label(frame, text=f"Matches para {champ}").pack()
            label_img = tk.Label(frame, image=tk_match)
            label_img.image = tk_match
            label_img.pack()

    tk.Button(window, text="Mostrar Matches", command=show_matches).pack(pady=5)

    # ---------------------
    # Botones inferior
    # ---------------------
    btn_frame = tk.Frame(window)
    btn_frame.pack(side=tk.BOTTOM, pady=10)

    tk.Button(btn_frame, text="Siguiente (Aceptar)", command=lambda: (
    selected_candidate.update({"champion": candidates[0][0] if candidates else "Unknown"}),
    window.destroy()
    )).pack(side=tk.LEFT, padx=5)

    tk.Button(btn_frame, text="Elección Manual", command=lambda: (
        selected_candidate.update({"champion": manual_var.get()}),
        window.destroy()
    )).pack(side=tk.LEFT, padx=5)

    window.grab_set()
    window.wait_window()

    return selected_candidate["champion"]

def main():
    parser = argparse.ArgumentParser(description="Detectar campeones seleccionados en Champion Select.")
    parser.add_argument("video_path", help="Ruta al video")
    parser.add_argument("json_folder", help="Carpeta con plantillas ROI (JSON) de champion select")
    parser.add_argument("champion_folder", help="Carpeta con imágenes de campeones (high res)")
    args = parser.parse_args()

    # Cargar plantillas ROI desde JSON
    templates = load_templates(args.json_folder)
    template_names = list(templates.keys())
    if not template_names:
        print("No se encontraron plantillas JSON en la carpeta especificada.")
        return

    # Se asume que la plantilla de champion select tiene las claves:
    # "team1ChampionsRoi" y "team2ChampionsRoi"
    current_template_name = template_names[0]
    current_template = templates[current_template_name]

    # Cargar imágenes de campeones
    champ_templates = load_champion_images(args.champion_folder)
    if not champ_templates:
        print("No se encontraron imágenes de campeones en la carpeta especificada.")
        return

    # Ventana Tkinter para seleccionar la plantilla (similar a showROI.py)
    root = tk.Tk()
    root.title("Seleccionar Plantilla de ROIs")
    selected_template_var = tk.StringVar(root)
    selected_template_var.set(current_template_name)
    tk.Label(root, text="Plantilla de ROIs:").pack(side=tk.LEFT, padx=5, pady=5)
    dropdown = tk.OptionMenu(root, selected_template_var, *template_names)
    dropdown.pack(side=tk.LEFT, padx=5, pady=5)

    def on_template_change(*args):
        nonlocal current_template, current_template_name
        sel = selected_template_var.get()
        if sel in templates:
            current_template_name = sel
            current_template = templates[sel]

    selected_template_var.trace("w", on_template_change)

    # Se abre el video con un objeto cv2.VideoCapture
    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        print("❌ No se pudo abrir el video.")
        root.destroy()
        return

    # Se crea una ventana de OpenCV para mostrar el video
    window_name = "Video - [n: avanzar 10s | m: avanzar 100s | p: detectar campeones | c: captura | q: salir]"
    cv2.namedWindow(window_name)

    # Variables para almacenar el estado de la detección
    detection_result = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Mostrar opcionalmente los ROIs
        if current_template is not None:
            draw_rois(frame, current_template)

        # Redimensionar solo para visualización si el frame es muy alto
        max_display_height = 720
        frame_h, frame_w = frame.shape[:2]
        if frame_h > max_display_height:
            scale = max_display_height / frame_h
            display_frame = cv2.resize(frame, (int(frame_w * scale), max_display_height), interpolation=cv2.INTER_AREA)
        else:
            display_frame = frame

        cv2.imshow(window_name, display_frame)
        key = cv2.waitKey(30) & 0xFF

        if key == ord('n'):
            current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            cap.set(cv2.CAP_PROP_POS_MSEC, current_msec + 10000)

        elif key == ord('m'):
            current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            cap.set(cv2.CAP_PROP_POS_MSEC, current_msec + 100000)

        elif key == ord('c'):
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
        elif key == ord('p'):
            # Proceso visual de detección de campeones usando la plantilla ROI
            # Si la plantilla actual no contiene las claves "team1ChampionsRoi" y "team2ChampionsRoi"
            # se muestra un mensaje de error
            if "team1ChampionsRoi" not in current_template or "team2ChampionsRoi" not in current_template:
                print("La plantilla actual no contiene las claves 'team1ChampionsRoi' y 'team2ChampionsRoi'.")
            else:
                teams = {"blue": "team1ChampionsRoi", "red": "team2ChampionsRoi"}
                detection_result = {"blue_team_champions": [], "red_team_champions": []}
               
                # Para cada equipo, se recorre cada subregión (cada uno de los 5 campeones)
                # Habra una iteración por cada equipo (blue y red)
                for team_key, roi_key in teams.items():
                    points = current_template[roi_key]
                    bbox = get_bounding_box(points)
                    # Subdividir el ROI en 5 sub-regiones del mismo tamaño
                    sub_boxes = subdivide_roi(bbox, subdivisions=5)
                    team_champions = []
                   
                    # Para cada sub-box (cada campeón en pantalla), se extrae la subregión
                    # y se realiza la detección de campeones
                    # Habrá 5 iteraciones por cada equipo
                    for sub_box in sub_boxes:
                        x1, y1, x2, y2 = sub_box
                        sub_region = frame[y1:y2, x1:x2]
                        # Obtener los 5 candidatos más probables mediante feature matching
                        candidates = detect_top_candidates(sub_region, champ_templates, top_n=5)
                        # Ventana emergente para confirmar o elegir manualmente
                        selected_champion = confirm_candidate(sub_region, candidates, champ_templates)
                        team_champions.append(selected_champion if selected_champion is not None else "Unknown")

                    if team_key == "blue":
                        detection_result["blue_team_champions"] = team_champions
                    else:
                        detection_result["red_team_champions"] = team_champions

                print("Detección de campeones:")
                print(detection_result)

                # Preguntar al usuario si desea guardar el resultado en JSON
                temp_root = tk.Tk()
                temp_root.withdraw()
                result = messagebox.askyesno("Guardar detección", "¿Desea guardar la detección de campeones?")
                temp_root.destroy()
                if result:
                    temp_root = tk.Tk()
                    temp_root.withdraw()
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".json",
                        title="Guardar detección de campeones",
                        filetypes=[("JSON files", "*.json")]
                    )
                    temp_root.destroy()
                    if filename:
                        try:
                            with open(filename, "w") as f:
                                json.dump(detection_result, f, indent=4)
                            print(f"Detección guardada en: {filename}")
                        except Exception as e:
                            print(f"Error al guardar la detección: {e}")


        elif key == ord('q') or key == 27:
            break

        root.update()

    cap.release()
    cv2.destroyAllWindows()
    root.destroy()

if __name__ == "__main__":
    main()
