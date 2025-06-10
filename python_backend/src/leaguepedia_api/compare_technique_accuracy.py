#!/usr/bin/env python3
"""
compare_technique_accuracy.py

Revisa la carpeta ./output, toma el subdirectorio numérico más alto y compara
las precisiones de todas las técnicas / sub-técnicas encontradas.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

OUTPUT_DIR = Path("output")
SUMMARY_FILE = "summary.log"

AC_REGEX = re.compile(r"Aciertos?:\s*(\d+)", re.I)
FA_REGEX = re.compile(r"Fallos?:\s*(\d+)", re.I)


def newest_batch_folder(base: Path) -> Path | None:
    """Devuelve la ruta con el número de partidas más grande (None si no hay)."""
    numeric = [p for p in base.iterdir() if p.is_dir() and p.name.isdigit()]
    return max(numeric, key=lambda p: int(p.name)) if numeric else None


def extract_accuracy(summary_path: Path) -> Tuple[int, int]:
    """Devuelve (aciertos, fallos) leyendo summary.log (0,0 si no existe)."""
    if not summary_path.exists():
        return 0, 0
    txt = summary_path.read_text(encoding="utf-8")
    ac = int(AC_REGEX.search(txt).group(1)) if AC_REGEX.search(txt) else 0
    fa = int(FA_REGEX.search(txt).group(1)) if FA_REGEX.search(txt) else 0
    return ac, fa


def collect_results(batch_dir: Path) -> List[Tuple[str, str, float, int, int]]:
    """
    Recorre técnica/subtécnica y devuelve lista de
    (técnica, subtécnica, precisión%, aciertos, fallos)
    """
    results = []
    for tech in sorted(p for p in batch_dir.iterdir() if p.is_dir()):
        for sub in sorted(p for p in tech.iterdir() if p.is_dir()):
            aciertos, fallos = extract_accuracy(sub / SUMMARY_FILE)
            total = aciertos + fallos
            acc = (aciertos / total) * 100 if total else 0.0
            results.append((tech.name, sub.name, acc, aciertos, fallos))
    return sorted(results, key=lambda t: t[2], reverse=True)


def print_table(rows: List[Tuple[str, str, float, int, int]]) -> None:
    print(f"{'Técnica':<18} {'Sub-técnica':<15} {'Precisión %':>11}  (A/F)")
    print("-" * 54)
    for tech, sub, acc, ac, fa in rows:
        print(f"{tech:<18} {sub:<15} {acc:>10.2f}  ({ac}/{fa})")


def main() -> None:
    batch = newest_batch_folder(OUTPUT_DIR)
    if not batch:
        print("No se encontró ninguna carpeta numérica en ./output")
        return

    print(f"➜ Analizando resultados de: {batch} …\n")
    rows = collect_results(batch)
    if not rows:
        print("No se encontraron summary.log en las subcarpetas.")
        return
    print_table(rows)


if __name__ == "__main__":
    main()