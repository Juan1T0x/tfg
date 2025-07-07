#!/usr/bin/env python3
# koi_last_lec_timeline.py

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from mwrogue.esports_client import EsportsClient


def safe_filename(text: str, maxlen: int = 120) -> str:
    """Quita caracteres ilegales para nombres de archivo Windows/*nix."""
    return re.sub(r'[\\/:*?"<>|]+', "_", text).strip()[:maxlen]


# ─── parámetros clave ─────────────────────────────────────────────────
LEAGUE = "LoL EMEA Championship"   # LEC
TEAM   = "Movistar KOI"            # nombre según Leaguepedia
site   = EsportsClient("lol")      # lectura anónima

# ─── 1. Buscamos la ÚLTIMA partida del equipo, con Post-game si existe ─
rows = site.cargo_client.query(
    tables="ScoreboardGames=SG, Tournaments=T, PostgameJsonMetadata=PG",
    join_on=(
        "SG.OverviewPage=T.OverviewPage, "
        "SG.GameId=PG.GameId"        # puede quedar NULL si aún no se cargó
    ),
    fields=(
        "SG.GameId, SG.MatchHistory, "
        "PG.TimelinePage, PG.RiotPlatformGameId"
    ),
    where=(
        f"T.League='{LEAGUE}' "
        f"AND (SG.Team1='{TEAM}' OR SG.Team2='{TEAM}')"
    ),
    order_by="SG.DateTime_UTC DESC",
    limit=1,
)

if not rows:
    sys.exit("⚠️  Movistar KOI no tiene partidas registradas en la LEC.")

row = rows[0]

# ─── 2. Preferimos el JSON interno de Leaguepedia ────────────────────
if row.get("TimelinePage"):
    timeline_page = row["TimelinePage"]
    raw_url = f"https://lol.fandom.com/wiki/{timeline_page}?action=raw"
    print(f"⬇️  Descargando timeline desde Leaguepedia ({timeline_page})…")
    timeline = json.loads(requests.get(raw_url, timeout=15).text)
    file_tag = row.get("RiotPlatformGameId") or safe_filename(timeline_page)

    # Imprimir la url completa a la que se accedió
    print(f"URL completa: {raw_url}")

# ─── 3. Si no existe, usamos el enlace MatchHistory → ACS ─────────────
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

    tl_url  = (
        f"https://acs.leagueoflegends.com/v1/stats/game/"
        f"{server}/{game_id}/timeline?gameHash={ghash}"
    )
    print("⬇️  Descargando timeline desde ACS…")
    timeline = requests.get(tl_url, timeout=15).json()
    file_tag = game_id

    # Imprimir la url completa a la que se accedió
    print(f"URL completa: {tl_url}")

else:
    sys.exit("⚠️  La partida aún no tiene TimelinePage ni MatchHistory disponible.")

# ─── 4. Guardamos en disco ────────────────────────────────────────────
out = Path(f"{safe_filename(file_tag)}_timeline.json")
out.write_text(json.dumps(timeline, indent=2, ensure_ascii=False))
print(f"✅  Timeline guardado en {out.resolve()}")
