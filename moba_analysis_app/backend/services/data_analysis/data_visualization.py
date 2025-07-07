#!/usr/bin/env python3
"""
services/data_analysis/data_visualization_service.py
====================================================

Convierte a URLs públicas todas las imágenes PNG generadas por los servicios de
visualización (`cs_diff`, `cs_total`, `gold_diff`, `heat_maps`).

Las URLs devueltas incluyen ahora **el nombre del partido** para reflejar la
ubicación real en el árbol de ficheros estáticos que expone el servidor:

    http://localhost:8888/results/<match>/<categoria>/subcarpetas/…/grafico.png
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

_BASE_URL       = "http://localhost:8888"   # raíz de los ficheros estáticos
_RESULTS_MOUNT  = "/results"                # punto de montaje (estático)


def _png_urls(root: Path, category: str) -> List[str]:
    """
    Devuelve las URLs de todos los PNG encontrados en
    `<root>/results/<category>/…`, anteponiendo el nombre del partido a la URL.
    """
    cat_dir = root / "results" / category
    if not cat_dir.is_dir():
        return []

    match_name = root.name        # carpeta del partido  →  LOLTMNT06_122413_timeline
    urls: List[str] = []
    for png in cat_dir.rglob("*.png"):
        # cs_diff/.../file.png   →  <match_name>/cs_diff/.../file.png
        rel_path = Path(match_name) / png.relative_to(root / "results")
        urls.append(f"{_BASE_URL}{_RESULTS_MOUNT}/{rel_path.as_posix()}")

    return sorted(urls)


def get_cs_diff(match_dir: str | Path) -> List[str]:
    return _png_urls(Path(match_dir), "cs_diff")


def get_cs_total(match_dir: str | Path) -> List[str]:
    return _png_urls(Path(match_dir), "cs_total")


def get_gold_diff(match_dir: str | Path) -> List[str]:
    return _png_urls(Path(match_dir), "gold_diff")


def get_heat_maps(match_dir: str | Path) -> List[str]:
    return _png_urls(Path(match_dir), "heat_maps")


def get_all(match_dir: str | Path) -> Dict[str, List[str]]:
    """
    Devuelve las cuatro listas de URLs agrupadas en un diccionario:
    {
        "cs_diff":   [...],
        "cs_total":  [...],
        "gold_diff": [...],
        "heat_maps": [...]
    }
    """
    match_path = Path(match_dir)
    return {
        "cs_diff":   get_cs_diff(match_path),
        "cs_total":  get_cs_total(match_path),
        "gold_diff": get_gold_diff(match_path),
        "heat_maps": get_heat_maps(match_path),
    }


__all__ = [
    "get_cs_diff",
    "get_cs_total",
    "get_gold_diff",
    "get_heat_maps",
    "get_all",
]
