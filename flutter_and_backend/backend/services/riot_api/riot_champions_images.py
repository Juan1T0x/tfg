# services/riot_api/riot_champions_images.py
import requests
from pathlib import Path
from typing import Any
from .riot_versions import get_latest_version

BASE_DIR = Path(__file__).resolve().parents[2] / "assets" / "images"
ICON_DIR, SPLASH_DIR, LOADING_DIR = (
    BASE_DIR / "icons",
    BASE_DIR / "splash_arts",
    BASE_DIR / "loading_screens",
)
for p in (ICON_DIR, SPLASH_DIR, LOADING_DIR):
    p.mkdir(parents=True, exist_ok=True)


def _download(url: str, dest: Path) -> bool:
    """
    Descarga `url` en `dest` solo si no existe.
    Devuelve True si realmente descargó.
    """
    if dest.exists():
        return False

    # vuelve a crear el directorio por si lo borraron
    dest.parent.mkdir(parents=True, exist_ok=True)

    r = requests.get(url, timeout=15)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return True


def download_all_images(version: str) -> int:
    meta_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    r = requests.get(meta_url, timeout=15)
    r.raise_for_status()
    champions = r.json()["data"]

    downloaded = 0
    for name, info in champions.items():
        cid = info["id"]
        assets = {
            ICON_DIR / f"{name}_icon.png": (
                f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{cid}.png"
            ),
            SPLASH_DIR / f"{name}_splash.jpg": (
                f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{cid}_0.jpg"
            ),
            LOADING_DIR / f"{name}_loading.jpg": (
                f"https://ddragon.leagueoflegends.com/cdn/img/champion/loading/{cid}_0.jpg"
            ),
        }
        for path, url in assets.items():
            try:
                if _download(url, path):
                    downloaded += 1
            except Exception as e:
                print(f"❌ {name}: {e}")

    if downloaded:
        print(f"✔ Descargadas {downloaded} nuevas imágenes.")
    else:
        print("✔ Biblioteca de imágenes ya al día.")
    return downloaded
