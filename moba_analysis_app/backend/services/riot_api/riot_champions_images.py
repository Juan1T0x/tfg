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

# ────────────────────────── RUTAS ABSOLUTAS ───────────────────────────

def get_icons_path() -> str:
    """Ruta absoluta a la carpeta de iconos."""
    return str(ICON_DIR.resolve())

def get_splash_arts_path() -> str:
    """Ruta absoluta a la carpeta de splash arts."""
    return str(SPLASH_DIR.resolve())

def get_loading_screens_path() -> str:
    """Ruta absoluta a la carpeta de loading screens."""
    return str(LOADING_DIR.resolve())

# ───────────────────────── HELPERS PARA URLs ───────────────────────────

_BASE_URL = "http://localhost:8888"
_ICON_MOUNT   = "/static/icons"
_SPLASH_MOUNT = "/static/splash_arts"
_LOAD_MOUNT   = "/static/loading_screens"



def _folder_to_urls(folder: Path, mount: str) -> list[str]:
    return [
        f"{_BASE_URL}{mount}/{f.name}"
        for f in folder.iterdir()
        if f.is_file()
    ]

def list_icons_urls()        -> list[str]: 
    return _folder_to_urls(ICON_DIR,   _ICON_MOUNT)

def list_splash_urls()       -> list[str]: 
    return _folder_to_urls(SPLASH_DIR, _SPLASH_MOUNT)

def list_loading_urls()      -> list[str]: 
    return _folder_to_urls(LOADING_DIR,_LOAD_MOUNT)

def champion_images_urls(champion_key: str) -> dict[str, str]:
    """
    Devuelve las tres URLs (icon, splash, loading) de `champion_key`
    – la *key* de Riot usada en los nombres de fichero (Aatrox, DrMundo, …)

    Lanza FileNotFoundError si falta alguna de las tres imágenes.
    """
    icon   = ICON_DIR   / f"{champion_key}_icon.png"
    splash = SPLASH_DIR / f"{champion_key}_splash.jpg"
    load   = LOADING_DIR/ f"{champion_key}_loading.jpg"

    for f in (icon, splash, load):
        if not f.exists():
            raise FileNotFoundError(
                f"{f.name} no encontrado. El campeón {champion_key} no existe o no está en la base de datos."
            )

    return {
        "champion"      : champion_key,
        "icon"          : f"{_BASE_URL}{_ICON_MOUNT}/{icon.name}",
        "splash_art"    : f"{_BASE_URL}{_SPLASH_MOUNT}/{splash.name}",
        "loading_screen": f"{_BASE_URL}{_LOAD_MOUNT}/{load.name}",
    }

