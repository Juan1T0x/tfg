import os
import subprocess
import sys

def descargar_video(base_dir):
    downloader_script = os.path.join(base_dir, "src", "video", "youtube_video_downloader.py")
    youtube_url = input("No se encontró ningún video. Introduce la URL de YouTube: ").strip()

    if not youtube_url:
        print("No se proporcionó una URL.", file=sys.stderr)
        sys.exit(1)

    python_cmd = sys.executable  # Usa el mismo intérprete activo (del entorno virtual)
    command = [python_cmd, downloader_script, youtube_url]

    print("\nDescargando video con el siguiente comando:")
    print(" ".join(command))
    
    result = subprocess.run(command)
    if result.returncode != 0:
        print("Error al descargar el video", file=sys.stderr)
        sys.exit(result.returncode)

def main():
    # Directorio base del proyecto
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Ruta al script champion_detection.py
    champ_detection_script = os.path.join(base_dir, "src", "champion_detection", "champion_detection.py")

    # Buscar el primer video válido
    video_dir = os.path.join(base_dir, "src", "video", "output")
    video_file = None

    if os.path.exists(video_dir):
        for file in os.listdir(video_dir):
            if file.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                video_file = os.path.join(video_dir, file)
                break

    # Si no se encuentra video, solicitar URL y descargar
    if not video_file:
        descargar_video(base_dir)
        # Buscar de nuevo después de descargar
        for file in os.listdir(video_dir):
            if file.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                video_file = os.path.join(video_dir, file)
                break

        if not video_file:
            print("No se pudo encontrar el video incluso después de descargarlo.", file=sys.stderr)
            sys.exit(1)

    # Rutas a ROI y a imágenes de campeones
    roi_templates_dir = os.path.join(base_dir, "src", "roi", "templates", "output")
    champion_images_dir = os.path.join(base_dir, "src", "data", "images", "icons")

    # Mostrar rutas
    print("Video file:", video_file)
    print("ROI templates directory:", roi_templates_dir)
    print("Champion images directory:", champion_images_dir)

    # Construir comando de ejecución
    python_cmd = sys.executable  # Usa el mismo intérprete activo (del entorno virtual)
    command = [
        python_cmd,
        champ_detection_script,
        video_file,
        roi_templates_dir,
        champion_images_dir
    ]

    print("\nEjecutando comando:")
    print(" ".join(command))

    # Ejecutar el comando
    result = subprocess.run(command)
    if result.returncode != 0:
        print("Error al ejecutar champion_detection.py", file=sys.stderr)
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
