#!/usr/bin/env python3
"""
Uso:
    python dragon_spawntime_timeline.py <timeline.json>

Muestra Nº, minuto de aparición y tipo de cada dragón.
"""

import json, sys
from pathlib import Path

FIRST_SPAWN_MS   = 5 * 60 * 1000   # 5 min
RESPAWN_DELAY_MS = 5 * 60 * 1000

def normaliza(subtype: str) -> str:
    return subtype.replace("_DRAGON", "").title().replace("_", " ")

def carga_frames(tl: dict):
    """Devuelve la lista de frames sin importar el formato del timeline."""
    if "info" in tl and "frames" in tl["info"]:      # formato Riot directo
        return tl["info"]["frames"]
    if "frames" in tl:                               # formato Leaguepedia
        return tl["frames"]
    return None                                      # no es un timeline válido

def extrae_dragones(frames):
    """[(spawn_ms, monsterSubType), …] orden cronológico."""
    eventos = [
        ev for fr in frames for ev in fr.get("events", [])
        if ev.get("type") == "ELITE_MONSTER_KILL" and ev.get("monsterType") == "DRAGON"
    ]
    eventos.sort(key=lambda ev: ev["timestamp"])

    proximo = FIRST_SPAWN_MS
    for ev in eventos:
        spawn = min(proximo, ev["timestamp"])
        yield spawn, ev["monsterSubType"]
        proximo = ev["timestamp"] + RESPAWN_DELAY_MS

def main(json_path):
    data   = json.loads(Path(json_path).read_text(encoding="utf-8"))
    frames = carga_frames(data)
    if not frames:
        sys.exit("❌  El archivo no contiene la clave 'frames'; ¿seguro que es un timeline?")

    spawns = list(extrae_dragones(frames))
    if not spawns:
        sys.exit("⚠️  No se encontraron dragones en el timeline.")

    print("Nº  Min  Elemento")
    for i, (ms, subtype) in enumerate(spawns, 1):
        print(f"{i:<2} {ms//60000:>3}  {normaliza(subtype)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python dragon_spawntime_timeline.py <timeline.json>")
    main(sys.argv[1])