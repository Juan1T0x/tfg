import argparse
import os
import yt_dlp

def main():
    parser = argparse.ArgumentParser(
        description='Descarga videos de YouTube en la calidad especificada.'
    )
    parser.add_argument('url', help='URL del video de YouTube')
    parser.add_argument('--quality', help='Calidad deseada (ej. 720p, 1080p). Por defecto, máxima calidad disponible.')
    args = parser.parse_args()

    # Procesar el parámetro de calidad
    quality_val = None
    if args.quality:
        try:
            quality_val = int(args.quality.lower().replace("p", ""))
        except Exception:
            print(f"❌ Formato de calidad inválido: {args.quality}. Ejemplo válido: 720p, 1080p, etc.")
            return

    # Directorio actual del script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Ruta de salida para el video descargado
    output_dir = os.path.join(script_dir, 'output')
    os.makedirs(output_dir, exist_ok=True)

    # Ruta al archivo de cookies
    cookies_file = os.path.join(script_dir, 'cookies.txt')

    # Configurar opciones para yt-dlp
    ydl_opts = {
        'outtmpl': os.path.join(output_dir, 'video.mp4'),
        'merge_output_format': 'mp4',
        'tries': 3,
        'retry_sleep': 5,
        'http_chunk_size': 10485760,  # 10 MB
        'ratelimit': None,
        'no_keep_fragments': True,
        'socket_timeout': 60,
    }

    # Usar archivo de cookies si existe
    if os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file
    else:
        print("⚠️ Advertencia: No se encontró cookies.txt. Algunos vídeos pueden no descargarse correctamente.")

    # Definir el formato según la calidad deseada
    if quality_val is None:
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    else:
        if quality_val > 720:
            ydl_opts['format'] = f'bestvideo[height<={quality_val}]+bestaudio/best'
        else:
            ydl_opts['format'] = f'best[height<={quality_val}]'

    # Ejecutar la descarga
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([args.url])
    except Exception as e:
        print(f"❌ Error durante la descarga: {e}")

if __name__ == "__main__":
    main()
