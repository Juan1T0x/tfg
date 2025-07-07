#!/usr/bin/env python3
# download_last_timeline.py
"""
Descarga el timeline de la *última* partida jugada por
«komanche uchiha#elite» (EUW) usando la Riot API.

Ejecuta:
    python download_last_timeline.py
"""

import json
import sys
from pathlib import Path
from urllib.parse import quote

import requests

# ───────────────────────── configuración ─────────────────────────
API_KEY = "RGAPI-377cbe44-99fe-4652-95d3-4a04154bd49a"

GAME_NAME = "komanche uchiha"
TAG_LINE  = "elite"

# Rutas Riot (macro-región y plataforma)
MACRO_REGION = "EUROPE"          # para match-v5 y account-v1
PLATFORM_ID  = "EUW1"            # no se usa aquí, pero lo anoto

HOST = f"https://{MACRO_REGION.lower()}.api.riotgames.com"

HEADERS = {"X-Riot-Token": API_KEY}
TIMEOUT = 15


# ─────────────────────── helpers de peticiones ───────────────────────
def _get(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        return r.json()
    elif r.status_code == 404:
        sys.exit("❌  Recurso no encontrado (404).")
    elif r.status_code == 403:
        sys.exit("❌  API-Key inválida o expirada (403).")
    else:
        sys.exit(f"❌  Error {r.status_code}: {r.text}")


# ───────────────────────── lógica principal ──────────────────────────
def main() -> None:
    # 1) PUUID del jugador ------------------------------------------------
    gn_enc  = quote(GAME_NAME)
    tag_enc = quote(TAG_LINE)
    url_acc = f"{HOST}/riot/account/v1/accounts/by-riot-id/{gn_enc}/{tag_enc}"
    print("🔎  Obteniendo PUUID…")
    account = _get(url_acc)
    puuid   = account["puuid"]

    # 2) Último match ID ---------------------------------------------------
    url_ids = f"{HOST}/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1"
    match_ids = _get(url_ids)
    if not match_ids:
        sys.exit("❌  El jugador no tiene partidas registradas.")
    match_id = match_ids[0]
    print(f"🆔  Último match: {match_id}")

    # 3) Timeline completo -------------------------------------------------
    url_tl = f"{HOST}/lol/match/v5/matches/{match_id}/timeline"
    print("⏬  Descargando timeline…")
    timeline = _get(url_tl)

    # 4) Guardar en disco --------------------------------------------------
    out_file = Path(f"{match_id}_timeline.json")
    out_file.write_text(json.dumps(timeline, indent=2, ensure_ascii=False))
    print(f"✅  Timeline guardado en {out_file.resolve()}")


if __name__ == "__main__":
    main()
