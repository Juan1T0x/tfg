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

# Cargar la imagen (asegúrate que 'source.jpg' esté en el path correcto)
frame = cv2.imread('source.jpg')
if frame is None:
    print("No se pudo cargar la imagen. Revisa el path.")
    exit()

# Definir las listas de candidatos para cada color
parametros = {
    'green': {
        'lower_candidates': [
            np.array([30, 40, 40]),
            np.array([35, 50, 50]),
            np.array([40, 60, 60])
        ],
        'upper_candidates': [
            np.array([80, 250, 250]),
            np.array([85, 255, 255]),
            np.array([90, 255, 255])
        ]
    },
    'blue': {
        'lower_candidates': [
            np.array([95, 50, 50]),
            np.array([100, 50, 50]),
            np.array([105, 50, 50])
        ],
        'upper_candidates': [
            np.array([125, 255, 255]),
            np.array([130, 255, 255]),
            np.array([135, 255, 255])
        ]
    },
    'red': {
        # Para el rojo se usan rangos típicos (en una de las dos zonas)
        'lower_candidates': [
            np.array([0, 50, 50]),
            np.array([5, 50, 50]),
            np.array([10, 50, 50])
        ],
        'upper_candidates': [
            np.array([10, 255, 255]),
            np.array([15, 255, 255]),
            np.array([20, 255, 255])
        ]
    }
}

# Lista de umbrales mínimos de área para filtrar contornos
area_thresholds = [300, 500, 700]

print("Para seleccionar una combinación, presiona 's'.")
print("Presiona 'c' para pasar al siguiente color, 'q' para salir en cualquier momento.\n")

# Iterar sobre los colores disponibles
for color in ['green', 'blue', 'red']:
    print(f"\nProbando parámetros para color: {color}")
    # Flag para saltar el resto de combinaciones del color actual
    saltar_color = False
    for lower in parametros[color]['lower_candidates']:
        if saltar_color:
            break
        for upper in parametros[color]['upper_candidates']:
            if saltar_color:
                break
            for area_thresh in area_thresholds:
                # Crear copia del frame para dibujar sobre él
                frame_copy = frame.copy()
                rois, mask = detectar_roi_barra(frame_copy, lower, upper, area_thresh)
                # Dibujar rectángulos con las ROI encontradas
                for (x, y, w, h) in rois:
                    cv2.rectangle(frame_copy, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # Mostrar los parámetros utilizados en la imagen
                parametros_texto = f"{color} | lower: {lower.tolist()} | upper: {upper.tolist()} | area_thresh: {area_thresh}"
                cv2.putText(frame_copy, parametros_texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 255, 255), 2)
                
                # Mostrar la imagen resultante
                cv2.imshow("Combinacion de Parametros", frame_copy)
                # Opcional: también se puede mostrar la máscara
                # cv2.imshow("Mask", mask)
                
                key = cv2.waitKey(0) & 0xFF
                if key == ord('s'):
                    print("Seleccionado:", parametros_texto)
                elif key == ord('c'):
                    print(f"Saltando a siguiente color desde {color}")
                    saltar_color = True
                    break  # Sale del bucle de area_thresh
                elif key == ord('q'):
                    cv2.destroyAllWindows()
                    exit()
# Finalizar
cv2.destroyAllWindows()
print("Pruebas finalizadas.")