import cv2
import numpy as np

def detectar_roi_barra(frame, lower, upper, area_thresh, kernel_size=3):
    """
    Función que detecta las regiones de interés (ROI) de una barra 
    dado un rango de color y un umbral de área.

    Parámetros:
      - frame: imagen de entrada en BGR.
      - lower: límite inferior (en HSV) (np.array).
      - upper: límite superior (en HSV) (np.array).
      - area_thresh: área mínima (en píxeles) para considerar un contorno.
      - kernel_size: tamaño del kernel para operaciones morfológicas.

    Retorna:
      - rois: lista de tuplas (x, y, w, h) de las ROI detectadas.
      - mask: la máscara binaria obtenida (útil para debug).
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)
    
    # Operaciones morfológicas para limpiar la máscara
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    # Detección de contornos
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    rois = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > area_thresh:
            x, y, w, h = cv2.boundingRect(cnt)
            rois.append((x, y, w, h))
            
    return rois, mask

# Cargar la imagen (asegúrate de que 'source.jpg' esté en el path correcto)
frame = cv2.imread('source.jpg')
if frame is None:
    print("No se pudo cargar la imagen. Revisa el path.")
    exit()

# Generar candidatos automáticamente para el color rojo
# Se muestrean valores para H, S y V para el lower; upper se define como lower + delta en H y saturación/valor fijos.
delta_h = 10  # incremento para H en el upper
lower_candidates = []
upper_candidates = []
# Se usan 5 valores para H en [0, 15] y 3 valores para S y V cada uno en los rangos indicados
for h in np.linspace(0, 15, num=5, dtype=int):
    for s in np.linspace(50, 150, num=3, dtype=int):
        for v in np.linspace(50, 150, num=3, dtype=int):
            lower = np.array([int(h), int(s), int(v)])
            # El candidato superior: H se incrementa en delta_h, Saturation y Value se fijan en 255 para forzar intensidad
            upper = np.array([int(h) + delta_h, 255, 255])
            lower_candidates.append(lower)
            upper_candidates.append(upper)

# Lista de umbrales mínimos de área para filtrar contornos
area_thresholds = [300, 500, 700]

print("Pruebas para el color ROJO con muchas combinaciones.")
print("Control: 's' para seleccionar (imprime la combinación), 'c' para pasar al siguiente candidato, 'q' para salir.\n")

# Iterar sobre los candidatos generados y los umbrales de área
total_combinaciones = len(lower_candidates) * len(area_thresholds)
contador = 0
for lower, upper in zip(lower_candidates, upper_candidates):
    # Para cada par de lower/upper iteramos sobre cada umbral de área
    saltar_par = False  # Flag para saltar a la siguiente pareja de lower/upper
    for area_thresh in area_thresholds:
        contador += 1
        # Crear copia del frame para dibujar sobre él
        frame_copy = frame.copy()
        rois, mask = detectar_roi_barra(frame_copy, lower, upper, area_thresh)
        # Dibujar rectángulos con las ROI encontradas
        for (x, y, w, h) in rois:
            cv2.rectangle(frame_copy, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # Mostrar los parámetros utilizados en la imagen
        parametros_texto = f"ROJO | lower: {lower.tolist()} | upper: {upper.tolist()} | area_thresh: {area_thresh} (Combi: {contador}/{total_combinaciones})"
        cv2.putText(frame_copy, parametros_texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 255), 2)
        
        # Mostrar la imagen resultante (puedes descomentar para ver también la máscara)
        cv2.imshow("Combinacion de Parametros - ROJO", frame_copy)
        # cv2.imshow("Mask - ROJO", mask)
        
        key = cv2.waitKey(0) & 0xFF
        if key == ord('s'):
            print("Seleccionado:", parametros_texto)
        elif key == ord('c'):
            print("Saltando al siguiente candidato para ROJO.")
            saltar_par = True
            break
        elif key == ord('q'):
            cv2.destroyAllWindows()
            exit()
    if saltar_par:
        continue

cv2.destroyAllWindows()
print("Pruebas finalizadas.")
