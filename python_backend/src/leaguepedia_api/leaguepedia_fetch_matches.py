# -*- coding: utf-8 -*-
"""
Descarga partidas recientes de Leaguepedia respetando el rate-limit público:
    • ≤ 500 filas por consulta (no admin)
    • 1-2 s de pausa entre consultas

Guarda los datos en database/moba_analysis.sqlite → tabla `leaguepedia_games`.
"""

from __future__ import annotations
import argparse, difflib, html, logging, sqlite3, time
from pathlib import Path
from typing import Dict, List, Tuple

from mwrogue.esports_client import EsportsClient
from mwclient.errors import APIError

# ───────────── Parámetros globales ─────────────
UA = ("outdated-tfg-moba-analysis/0.1 "
      "(+https://github.com/Juan1T0x/outdated-tfg-moba-analysis; "
      "juan.hernandeza@um.es)")

DB_PATH = Path(__file__).resolve().parents[1] / "database" / "moba_analysis.sqlite"
TABLE   = "leaguepedia_games"

MAX_RETRIES   = 6      # reintentos Cargo
BASE_BACKOFF  = 5      # s inicial ante error 4xx/5xx
FIXED_DELAY   = 1.5    # s entre *cualquier* consulta (dentro del rango 1-2 s)
CHUNK_SIZE    = 50     # 50 GameIds ⇒ ≤ 500 filas en ScoreboardPlayers
MAX_CARGO_ROWS = 500   # hard-limit público
# ────────────────────────────────────────────────


# ╭────────── Normalización de campeones ─────────╮
def _load_canonical_champions() -> Tuple[List[str], set[str]]:
    with sqlite3.connect(DB_PATH) as conn:
        champs = sorted(r[0] for r in conn.execute(
            "SELECT champion_name FROM champions"))
    return champs, set(champs)

_CANONICAL_LIST, _CANONICAL_SET = _load_canonical_champions()

def normalize_champion_name(raw: str) -> str:
    name = html.unescape(raw.strip())
    if name in _CANONICAL_SET:
        return name
    for c in _CANONICAL_LIST:
        if name.lower() == c.lower():
            return c
    m = difflib.get_close_matches(name, _CANONICAL_LIST, n=1, cutoff=0.7)
    return m[0] if m else name
# ╰───────────────────────────────────────────────╯


def get_esports_client() -> EsportsClient:
    return EsportsClient("lol", retry_timeout=30, max_retries=MAX_RETRIES)


def split_overview(overview: str) -> Tuple[str, str, str]:
    parts = overview.split("/")
    if len(parts) >= 3:
        league, season, *rest = parts
        return league, season, "/".join(rest)
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return overview, "", ""


# ╭──────────── Cargo con reintentos ────────────╮
def cargo_query(site: EsportsClient, pause: float = FIXED_DELAY, **kw):
    delay = BASE_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = site.cargo_client.query(**kw)
            time.sleep(pause)            # pausa firme entre *todas* las llamadas
            return res
        except APIError as e:
            logging.warning("APIError %s (%s) intento %d/%d – backoff %.1fs",
                            e.code, e.info, attempt, MAX_RETRIES, delay)
            time.sleep(delay)
            delay *= 2
    return None
# ╰───────────────────────────────────────────────╯


def fetch_recent_games(num_games: int) -> List[Dict]:
    site = get_esports_client()

    # 1) Descargar GameIds (50 por página ⇒ ≤ 500 filas)
    game_ids: List[str] = []
    offset = 0
    while len(game_ids) < num_games:
        batch = cargo_query(site,
            tables="ScoreboardGames", fields="GameId",
            order_by="DateTime_UTC DESC",
            limit=CHUNK_SIZE, offset=offset)
        if not batch:
            break
        game_ids.extend(r["GameId"] for r in batch)
        offset += CHUNK_SIZE
    game_ids = game_ids[:num_games]
    logging.info("GameIds obtenidos: %d", len(game_ids))

    # 2) Metadatos + jugadores
    games: Dict[str, Dict] = {}
    role_alias = {"top": "top", "jungle": "jungle", "mid": "mid",
                  "bot": "bot", "bottom": "bot", "adc": "bot",
                  "support": "support"}

    for i in range(0, len(game_ids), CHUNK_SIZE):
        block = game_ids[i:i+CHUNK_SIZE]
        quoted = ",".join(f'"{gid}"' for gid in block)

        metadata = cargo_query(site,
            tables="ScoreboardGames",
            fields="GameId, Team1, Team2, Winner",
            where=f"GameId IN ({quoted})",
            limit=CHUNK_SIZE)

        meta_by = {m["GameId"]: m for m in metadata or []}

        players = cargo_query(site,
            tables="ScoreboardPlayers",
            fields="GameId, Champion, Team, Role",
            where=f"GameId IN ({quoted})",
            group_by="GameId, Champion, Team, Role",
            limit=min(CHUNK_SIZE*10, MAX_CARGO_ROWS))  # ≤ 500

        # estructura por partida
        for gid, meta in meta_by.items():
            overview, tab, match_n, game_n = gid.rsplit("_", 3)
            league, season, phase = split_overview(overview)
            games[gid] = {
                "id": gid, "league": league, "season": season, "phase": phase,
                "tab": tab, "match_in_tab": int(match_n), "game_in_match": int(game_n),
                "team1": meta["Team1"], "team2": meta["Team2"], "winner": meta["Winner"],
                **{f"{r}{t}": "" for r in ["top", "jungle", "mid", "bot", "support"]
                                           for t in ("1", "2")}
            }

        # asignar campeones
        for p in players or []:
            gid = p["GameId"]
            if gid not in games:
                continue
            suff = "1" if p["Team"].strip() == games[gid]["team1"] else "2"
            role = role_alias.get(p["Role"].lower(), "")
            if role:
                games[gid][f"{role}{suff}"] = normalize_champion_name(p["Champion"])

    return list(games.values())


def save_games(rows: List[Dict]) -> None:
    if not rows:
        logging.info("Nada que guardar")
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
          id TEXT PRIMARY KEY,
          league TEXT, season TEXT, phase TEXT, tab TEXT,
          match_in_tab INTEGER, game_in_match INTEGER,
          team1 TEXT, team2 TEXT, winner TEXT,
          top1 TEXT, jungle1 TEXT, mid1 TEXT, bot1 TEXT, support1 TEXT,
          top2 TEXT, jungle2 TEXT, mid2 TEXT, bot2 TEXT, support2 TEXT)""")
        conn.executemany(f"""
        INSERT OR IGNORE INTO {TABLE} VALUES (
          :id,:league,:season,:phase,:tab,:match_in_tab,:game_in_match,
          :team1,:team2,:winner,
          :top1,:jungle1,:mid1,:bot1,:support1,
          :top2,:jungle2,:mid2,:bot2,:support2)""", rows)
        logging.info("Filas insertadas: %d",
                     conn.execute("SELECT changes()").fetchone()[0])


# ──────────────────────────── Main ────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descarga partidas de Leaguepedia")
    parser.add_argument("num_matches", type=int, help="Nº de partidas a bajar")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    partidas = fetch_recent_games(args.num_matches)
    save_games(partidas)

    if partidas:
        g = partidas[0]
        print(f"\nEjemplo → {g['league']} / {g['season']} / {g['phase']} – {g['tab']}")
        for r in ["top", "jungle", "mid", "bot", "support"]:
            print(f"{r:7} {g[f'{r}1']:<15} | {g[f'{r}2']}")
