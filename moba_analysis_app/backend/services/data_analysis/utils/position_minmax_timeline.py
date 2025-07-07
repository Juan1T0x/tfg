#!/usr/bin/env python3
"""
find_min_max_positions.py

Dado un archivo *timeline* de la API de Riot, recorre todos los `participantFrames`
para localizar los valores mínimos y máximos de coordenadas `(x, y)` observados en
toda la partida.

Uso básico:
    python tools/find_min_max_positions.py --timeline path/a/partida.json

Opcionalmente:
    --include-events      Incluye las posiciones que aparecen en la lista `events`
                          (cuando existan) además de las de `participantFrames`.

Salida ejemplo:
    Min X: -120, Max X: 14870
    Min Y: -120, Max Y: 14980

Requisitos:
    Sólo usa la librería estándar de Python.
"""
import argparse
import json
from pathlib import Path
from typing import Tuple


def process_frames(frames, *, include_events: bool = False) -> Tuple[int, int, int, int]:
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for frame in frames:
        # participantFrames
        for pf in frame.get("participantFrames", {}).values():
            pos = pf.get("position")
            if pos:
                x, y = pos["x"], pos["y"]
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)

        if include_events:
            for ev in frame.get("events", []):
                pos = ev.get("position")
                if pos:
                    x, y = pos["x"], pos["y"]
                    min_x, max_x = min(min_x, x), max(max_x, x)
                    min_y, max_y = min(min_y, y), max(max_y, y)

    if min_x == float("inf"):
        raise ValueError("No se encontraron posiciones en la timeline.")

    return int(min_x), int(min_y), int(max_x), int(max_y)


def main():
    parser = argparse.ArgumentParser(description="Calcula min y max de posiciones en una timeline de LoL.")
    parser.add_argument("--timeline", required=True, type=Path, help="Ruta al archivo JSON de la timeline")
    parser.add_argument(
        "--include-events",
        action="store_true",
        help="Incluye posiciones definidas en los eventos (events[*].position)",
    )
    args = parser.parse_args()

    with args.timeline.open("r", encoding="utf-8") as f:
        timeline = json.load(f)

    frames = timeline.get("frames", [])
    if not frames:
        raise SystemExit("El archivo JSON no contiene frames.")

    mn_x, mn_y, mx_x, mx_y = process_frames(frames, include_events=args.include_events)

    print(f"Min X: {mn_x}\nMin Y: {mn_y}\nMax X: {mx_x}\nMax Y: {mx_y}")


if __name__ == "__main__":
    main()
