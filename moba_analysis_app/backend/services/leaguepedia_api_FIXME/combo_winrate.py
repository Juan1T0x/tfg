#!/usr/bin/env python3
# combo_winrate.py  – versión DB (no necesita match_analysis.log)
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, TextIO

# ─────────────────────────────── Config ───────────────────────────────
BASE_DIR     = Path(__file__).resolve().parent
DB_PATH      = BASE_DIR.parent / "database" / "moba_analysis.sqlite"
GAMES_TABLE  = "leaguepedia_games"
CHAMP_TABLE  = "champions"

OUTPUT_ROOT  = Path("output")
ROLE_ORDER   = ["top", "jungle", "mid", "bot", "support"]

# ────────────────────── 1) Cargar clases de campeones ─────────────────
def load_champion_classes() -> Dict[str, List[str]]:
    """{champion_name: [clase1, clase2, …]} desde la tabla champions."""
    out: Dict[str, List[str]] = {}
    with sqlite3.connect(DB_PATH) as conn:
        for name, roles in conn.execute(f"SELECT champion_name, roles FROM {CHAMP_TABLE}"):
            lst = [r.strip() for r in roles.split(",") if r.strip()] if roles else []
            out[name] = lst or ["Sin clase"]
    return out


# ─────────────── 2) Expandir partidas a “una fila por jugador” ───────────────
def load_matches(limit: int | None = None) -> List[Tuple[str, str]]:
    """
    Devuelve [(combo_winner, combo_loser), …] usando leaguepedia_games.
    `limit` = nº de partidas más recientes (None = todas).
    """
    champ_cls = load_champion_classes()

    cols = ["team1", "team2", "winner"] + \
           [f"{r}{t}" for t in ("1", "2") for r in ROLE_ORDER]
    sel  = ", ".join(cols)
    sql  = f"SELECT {sel} FROM {GAMES_TABLE} ORDER BY rowid DESC"
    if limit:
        sql += f" LIMIT {limit}"

    matches: List[Tuple[str, str]] = []
    with sqlite3.connect(DB_PATH) as conn:
        for row in conn.execute(sql):
            row = list(row)
            team1, team2, winner = row[:3]
            champs = dict(zip(
                [f"{r}{t}" for t in ("1", "2") for r in ROLE_ORDER],
                row[3:]
            ))

            def role_map(team_no: str) -> Dict[str, List[str]]:
                return {role: champ_cls.get(champs[f"{role}{team_no}"], ["Sin clase"])
                        for role in ROLE_ORDER}

            combo1 = build_combo_string(role_map("1"))
            combo2 = build_combo_string(role_map("2"))

            if str(winner) == "1":
                matches.append((combo1, combo2))
            elif str(winner) == "2":
                matches.append((combo2, combo1))
            # si winner no es 1/2 se ignora la partida

    return matches


# ─────────────── 3) Helpers de representación y stats ───────────────
def build_combo_string(role_map: Dict[str, List[str]]) -> str:
    parts = []
    for role in ROLE_ORDER:
        classes = role_map.get(role, [])
        canon   = ",".join(c.lower() for c in classes) if classes else "None"
        parts.append(f"{role}[{canon}]")
    return ", ".join(parts)


def compute_stats(matches: List[Tuple[str, str]]) -> Dict[str, Dict[str, int]]:
    stats = defaultdict(lambda: {"wins": 0, "total": 0})
    for w, l in matches:
        stats[w]["wins"]  += 1
        stats[w]["total"] += 1
        stats[l]["total"] += 1
    return stats


# ─────────────── 4) Impresión de rankings ───────────────
def top_winrate(stats, min_games: int, k: int, out: TextIO) -> None:
    out.write(f"\n🏆  Top {k} combinaciones por win-rate (≥ {min_games} partidas):\n\n")
    rows = [
        (wr := d["wins"] / d["total"] * 100, d["wins"], d["total"], c)
        for c, d in stats.items() if d["total"] >= min_games
    ]
    rows.sort(reverse=True)
    for i, (wr, w, t, c) in enumerate(rows[:k], 1):
        out.write(f"{i:2d}. ({w}/{t}\tvict)  {wr:5.1f}%  →  {c}\n")


def top_freq(stats, min_games: int, k: int, start_idx: int, out: TextIO) -> None:
    out.write(f"\n📈  Top {k} combinaciones más jugadas (≥ {min_games} partidas):\n\n")
    rows = [
        (d["total"], d["wins"] / d["total"] * 100, d["wins"], c)
        for c, d in stats.items() if d["total"] >= min_games
    ]
    rows.sort(reverse=True)
    for i, (tot, wr, wins, c) in enumerate(rows[:k], start_idx):
        out.write(f"{i:2d}. {tot:4d}\taparic - {wr:5.1f}% WR  ({wins}/{tot})  →  {c}\n")


# ─────────────────────────────────── CLI ───────────────────────────────────
def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Genera ranking de combinaciones desde la BD")
    ap.add_argument("-n", "--num-matches", type=int, help="Nº de partidas más recientes (todas si se omite)")
    ap.add_argument("-m", "--min-games", type=int, default=5, help="Mínimo de partidas por combinación")
    ap.add_argument("-k", "--top", type=int, default=20, help="Entradas a mostrar en cada ranking")
    args = ap.parse_args(argv)

    matches = load_matches(args.num_matches)
    if not matches:
        sys.exit("❌  No se encontraron partidas válidas en la base de datos")

    stats = compute_stats(matches)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_ROOT / "combo_winrate_report.log"

    with report_path.open("w", encoding="utf-8") as f:
        for stream in (sys.stdout, f):  # imprimir en pantalla y archivo
            total = args.num_matches or "TODAS"
            stream.write(f"Partidas analizadas: {total}\n")
            top_winrate(stats, args.min_games, args.top, stream)
            top_freq(stats, args.min_games, args.top, 21, stream)

    print(f"\n✔  Reporte guardado en: {report_path}")


if __name__ == "__main__":
    main()
