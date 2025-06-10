import requests
import os
from pathlib import Path
from riot_versions import get_latest_version

# Obtener la última versión desde Riot
version = get_latest_version()
print(f"🌍 Usando versión de Riot: {version}")

# URL de campeones
url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
response = requests.get(url)
response.raise_for_status()
data = response.json()
champions_data = data['data']

# Rutas base para guardar imágenes
BASE_DIR = Path(__file__).resolve().parents[1] / "assets" / "images"
ICON_DIR = BASE_DIR / "icons"
SPLASH_DIR = BASE_DIR / "splash_arts"
LOADING_DIR = BASE_DIR / "loading_screens"

# Crear directorios si no existen
for path in [ICON_DIR, SPLASH_DIR, LOADING_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# Descargar imágenes por campeón
for champion_name, champion_info in champions_data.items():
    champion_id = champion_info['id']

    # URLs de imagen
    icon_url = f"http://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{champion_id}.png"
    splash_url = f"http://ddragon.leagueoflegends.com/cdn/img/champion/splash/{champion_id}_0.jpg"
    loading_url = f"http://ddragon.leagueoflegends.com/cdn/img/champion/loading/{champion_id}_0.jpg"

    # Paths destino
    icon_path = ICON_DIR / f"{champion_name}_icon.png"
    splash_path = SPLASH_DIR / f"{champion_name}_splash.jpg"
    loading_path = LOADING_DIR / f"{champion_name}_loading.jpg"

    # Descargar y guardar cada imagen
    try:
        with open(icon_path, 'wb') as f:
            f.write(requests.get(icon_url).content)

        with open(splash_path, 'wb') as f:
            f.write(requests.get(splash_url).content)

        with open(loading_path, 'wb') as f:
            f.write(requests.get(loading_url).content)

        print(f"✔ {champion_name}: icon, splash, loading descargados.")

    except Exception as e:
        print(f"❌ Error descargando imágenes de {champion_name}: {e}")

print("🎉 Todas las imágenes descargadas correctamente.")
