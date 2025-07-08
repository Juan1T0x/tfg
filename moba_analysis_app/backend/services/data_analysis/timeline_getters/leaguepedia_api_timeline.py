#!/usr/bin/env python3
# koi_last_timelines.py
"""
Descarga los *N* timelines más recientes de Movistar KOI en **cualquier**
liga / torneo registrado en Leaguepedia y los guarda en subcarpetas del
directorio actual con la forma:

    MKOIvs<ENEMY>_<MATCH_CODE>/time_line.json

Ejemplo de uso:
    python koi_last_timelines.py --last 10
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from mwrogue.esports_client import EsportsClient


def safe_filename(text: str, maxlen: int = 120) -> str:
    """Convierte *text* en un nombre válido de fichero para Windows/*nix."""
    return re.sub(r'[\\/:*?"<>|]+', "_", text).strip()[:maxlen]


TEAM = "Movistar KOI"
site = EsportsClient("lol")           # conexión anónima


def fetch_last_games(limit: int) -> None:
    """
    Descarga los *limit* últimos partidos de TEAM (en cualquier liga).
    Se intenta primero el JSON interno de Leaguepedia (`TimelinePage`) y,
    si no existe, se usa el enlace de Match History → ACS.
    """
    rows = site.cargo_client.query(
        tables="ScoreboardGames=SG, PostgameJsonMetadata=PG",
        join_on="SG.GameId=PG.GameId",
        fields=(
            "SG.GameId, SG.Team1, SG.Team2, SG.MatchHistory, "
            "PG.TimelinePage, PG.RiotPlatformGameId"
        ),
        where=f"(SG.Team1='{TEAM}' OR SG.Team2='{TEAM}')",
        order_by="SG.DateTime_UTC DESC",
        limit=limit,
    )

    if not rows:
        sys.exit(f"⚠️  No se encontraron partidas para {TEAM}.")

    for idx, row in enumerate(rows, 1):
        enemy = row["Team2"] if row["Team1"] == TEAM else row["Team1"]

        # ─── 1. JSON “raw” de Leaguepedia  ───────────────────────────────
        if row.get("TimelinePage"):
            tl_page = row["TimelinePage"]
            raw_url = f"https://lol.fandom.com/wiki/{tl_page}?action=raw"
            print(f"[{idx}/{limit}] ⬇️  Leaguepedia → {raw_url}")
            timeline = json.loads(requests.get(raw_url, timeout=15).text)
            match_code = row.get("RiotPlatformGameId") or safe_filename(tl_page)

        # ─── 2. Fallback: ACS a partir de Match History ──────────────────
        elif row.get("MatchHistory"):
            mh_url = (
                row["MatchHistory"].decode()
                if isinstance(row["MatchHistory"], (bytes, bytearray))
                else row["MatchHistory"]
            )
            p       = urlparse(mh_url)
            server  = p.path.split("/")[-2]
            game_id = p.path.split("/")[-1]
            ghash   = parse_qs(p.query)["gameHash"][0]

            tl_url = (
                f"https://acs.leagueoflegends.com/v1/stats/game/"
                f"{server}/{game_id}/timeline?gameHash={ghash}"
            )
            print(f"[{idx}/{limit}] ⬇️  ACS → {tl_url}")
            timeline = requests.get(tl_url, timeout=15).json()
            match_code = game_id

        else:
            print(f"[{idx}/{limit}] ⚠️  Sin TimelinePage ni MatchHistory — salto.")
            continue

        folder = Path(
            safe_filename(f"MKOIvs{enemy}_{match_code}")
        )
        folder.mkdir(parents=True, exist_ok=True)

        out_file = folder / "time_line.json"
        out_file.write_text(json.dumps(timeline, indent=2, ensure_ascii=False))
        print(f"[{idx}/{limit}] ✅  Guardado en {out_file}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Descarga los timelines recientes de Movistar KOI."
    )
    parser.add_argument(
        "--last",
        type=int,
        default=3,
        help="Número de últimas partidas a descargar (por defecto 3)",
    )
    args = parser.parse_args()
    fetch_last_games(max(1, args.last))
