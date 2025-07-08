#!/usr/bin/env python3
# services/data_analysis/data_visualization_service.py
"""
Generate public URLs for every PNG chart produced by the data–visualisation
pipeline (``cs_diff``, ``cs_total``, ``gold_diff`` and ``heat_maps``).

Directory layout
----------------
Every match has its own folder inside *backend/matches_history/*:

    matches_history/
        <match_slug>/
            results/
                cs_diff/      … PNG files
                cs_total/     … PNG files
                gold_diff/    … PNG files
                heat_maps/    … PNG files

The **static router** in *main.py* exposes that tree under
``http://<host>:<port>/results``.  Public URLs therefore follow the pattern:

    http://localhost:8888/results/<match_slug>/<category>/<subdirs…>/<file>.png
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

# Root URL where FastAPI serves the ``matches_history`` contents
_BASE_URL = "http://localhost:8888"
_RESULTS_MOUNT = "/results"


def _png_urls(match_root: Path, category: str) -> List[str]:
    """
    Return **sorted** URLs for every PNG inside
    ``<match_root>/results/<category>/``.

    Parameters
    ----------
    match_root
        Absolute or relative path to the **match folder**
        (e.g. ``backend/matches_history/g2-vs-fnc-game4``).
    category
        One of: ``cs_diff``, ``cs_total``, ``gold_diff`` or ``heat_maps``.

    Notes
    -----
    * If the category folder does not exist an empty list is returned.
    * Sub-folders are preserved in the generated URL.
    """
    cat_dir = match_root / "results" / category
    if not cat_dir.is_dir():
        return []

    slug = match_root.name
    urls: List[str] = []
    for png in cat_dir.rglob("*.png"):
        # Build a relative path that keeps <category>/<subdirs…>/<file>.png
        rel = Path(slug) / png.relative_to(match_root / "results")
        urls.append(f"{_BASE_URL}{_RESULTS_MOUNT}/{rel.as_posix()}")

    return sorted(urls)


# ─────────────────────────── public helpers ────────────────────────────
def get_cs_diff(match_dir: str | Path) -> List[str]:
    """URLs for *CS difference* charts."""
    return _png_urls(Path(match_dir), "cs_diff")


def get_cs_total(match_dir: str | Path) -> List[str]:
    """URLs for *total CS* charts."""
    return _png_urls(Path(match_dir), "cs_total")


def get_gold_diff(match_dir: str | Path) -> List[str]:
    """URLs for *gold difference* charts."""
    return _png_urls(Path(match_dir), "gold_diff")


def get_heat_maps(match_dir: str | Path) -> List[str]:
    """URLs for positional heat-map images."""
    return _png_urls(Path(match_dir), "heat_maps")


def get_all(match_dir: str | Path) -> Dict[str, List[str]]:
    """
    Convenience wrapper — fetch every category in a single call.

    Returns
    -------
    dict
        ``{
            "cs_diff":   [...],
            "cs_total":  [...],
            "gold_diff": [...],
            "heat_maps": [...]
        }``
    """
    path = Path(match_dir)
    return {
        "cs_diff": get_cs_diff(path),
        "cs_total": get_cs_total(path),
        "gold_diff": get_gold_diff(path),
        "heat_maps": get_heat_maps(path),
    }


__all__ = [
    "get_cs_diff",
    "get_cs_total",
    "get_gold_diff",
    "get_heat_maps",
    "get_all",
]
