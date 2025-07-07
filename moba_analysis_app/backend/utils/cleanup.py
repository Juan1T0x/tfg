"""
utils/cleanup.py
================
Elimina TODO el contenido de la carpeta ``backend/frames``.
Se puede ejecutar en solitario:

    python -m utils.cleanup
"""

from __future__ import annotations

from pathlib import Path
import shutil

FRAMES_DIR = Path(__file__).resolve().parents[1] / "frames"


def cleanup_frames() -> int:
    """
    Borra archivos y sub-carpetas de ``FRAMES_DIR``.
    Devuelve cuántos ítems se han eliminado.
    """
    if not FRAMES_DIR.exists():
        return 0

    deleted = 0
    for item in FRAMES_DIR.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            else:
                shutil.rmtree(item)
            deleted += 1
        except Exception as exc:
            # No abortamos si algo falla; simplemente lo registramos.
            print(f"⚠️  No se pudo eliminar {item}: {exc}")

    return deleted


if __name__ == "__main__":
    n = cleanup_frames()
    print(f"Frames limpiados: {n}")
