# -*- coding: utf-8 -*-
"""leaguepedia_class_effectiveness_analysis.py

Analiza partidas guardadas en la tabla `leaguepedia_games` midiendo la
“ventaja teórica” entre composiciones.

Uso:
  python leaguepedia_class_effectiveness_analysis.py        # todas
  python leaguepedia_class_effectiveness_analysis.py 1000   # últimas 1 000
  python leaguepedia_class_effectiveness_analysis.py --full # todas técnicas
"""
from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

# ────────────────────────────── Rutas / tablas ─────────────────────────────
BASE_DIR   = os.path.dirname(__file__)
DB_PATH    = os.path.join(BASE_DIR, "..", "database", "moba_analysis.sqlite")
GAMES_TABLE      = "leaguepedia_games"
CHAMPIONS_TABLE  = "champions"

# ─────────────────────────── Parámetros globales ───────────────────────────
ROLE_ORDER = ["top", "jungle", "mid", "bot", "support"]

TECHNIQUE_MODE = 0       # 0 cartesian_product | 1 by_role
SUBTECHNIQUE_MODE = 0    # 0 all | 1 half_secondary | 2 primary_only
TECHNIQUE_NAMES     = {0: "cartesian_product", 1: "by_role"}
SUBTECHNIQUE_NAMES  = {0: "all_classes", 1: "half_secondary", 2: "primary_only"}

EFFECTIVENESS_MATRIX: Dict[str, Dict[str, int]] = {
    "Fighter":  {"Marksman": -1, "Tank": 1},
    "Mage":     {"Marksman":  1, "Assassin": -1},
    "Marksman": {"Fighter":   1, "Mage": -1},
    "Assassin": {"Mage":      1, "Tank": -1},
    "Tank":     {"Fighter":  -1, "Assassin": 1},
    "Support":  {"Fighter":  -1, "Assassin": 1},
}
# ────────────────────────────────────────────────────────────────────────────


# ╭─────────────── Carga de CLASES desde la tabla champions ────────────────╮
def load_champion_classes() -> Dict[str, List[str]]:
    """Lee champion_name y roles de la tabla `champions`."""
    champ_classes: Dict[str, List[str]] = {}
    with sqlite3.connect(DB_PATH) as conn:
        for name, roles in conn.execute(
            f"SELECT champion_name, roles FROM {CHAMPIONS_TABLE}"
        ):
            lst = [r.strip() for r in roles.split(",") if r.strip()] if roles else []
            champ_classes[name] = lst or ["Sin clase"]
    return champ_classes
# ╰──────────────────────────────────────────────────────────────────────────╯


# ╭───────────────── Carga de partidos desde SQLite ─────────────────╮
def load_matches_from_db(limit: int | None = None) -> List[Dict]:
    """
    Devuelve las partidas expandidas a “una fila por jugador”.
    Soporta nombres de columnas insensibles a mayúsculas (`id`, `GameId`, …).
    """
    with sqlite3.connect(DB_PATH) as conn:
        query = f"SELECT * FROM {GAMES_TABLE} ORDER BY rowid DESC"
        if limit:
            query += f" LIMIT {limit}"
        rows = conn.execute(query).fetchall()
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({GAMES_TABLE})")]

    col_map: Dict[str, Tuple[str, int]] = {c.lower(): (c, i)
                                           for i, c in enumerate(cols)}

    pk_name, pk_pos = next(((c, pos) for c, pos in (col_map.get("id", (None, None)),
                                                    col_map.get("gameid", (None, None)))
                            if c), (cols[0], 0))

    def get(row, name: str, default=""):
        key = name.lower()
        if key in col_map:
            col, pos = col_map[key]
            return row[pos]
        return default

    expanded: List[Dict] = []
    for r in rows:
        base = {
            "GameId": get(r, pk_name),
            "Team1":  get(r, "team1"),
            "Team2":  get(r, "team2"),
            "Winner": get(r, "winner"),
        }
        for team_no, team in (("1", base["Team1"]), ("2", base["Team2"])):
            for role in ROLE_ORDER:
                champ = get(r, f"{role}{team_no}", "")
                if champ:
                    expanded.append({
                        **base,
                        "Champion": champ,
                        "Team": team,
                        "Role": role,
                    })
    return expanded
# ╰──────────────────────────────────────────────────────────────╯


# ╭──────────── Helpers (rol, pesos, score) ────────────╮
def normalize_role(role: str) -> str:
    m = {"top": "top", "toplane": "top", "top lane": "top",
         "jungle": "jungle", "jungler": "jungle", "jg": "jungle", "jng": "jungle",
         "mid": "mid", "midlane": "mid", "middle": "mid", "mid lane": "mid",
         "bot": "bot", "bottom": "bot", "adc": "bot", "ad carry": "bot",
         "botlane": "bot", "bottom lane": "bot",
         "support": "support", "supp": "support", "sup": "support"}
    return m.get(role.lower().strip(), role)


def class_weights(classes: List[str], mode: int) -> List[Tuple[str, float]]:
    if mode == 0:
        return [(c, 1.0) for c in classes]
    if mode == 1:
        return [(c, 1.0 if i == 0 else 0.5) for i, c in enumerate(classes[:2])]
    if mode == 2:
        return [(classes[0], 1.0)] if classes else []
    return []


def weighted_score(a, b) -> float:
    return sum(w1 * w2 * EFFECTIVENESS_MATRIX.get(c1, {}).get(c2, 0)
               for c1, w1 in a for c2, w2 in b)
# ╰──────────────────────────────────────────────────────────╯


def cartesian_scores(ch1, ch2, champ_cls, sub):
    a = [cw for c in ch1 for cw in class_weights(champ_cls.get(c, ["Sin clase"]), sub)]
    b = [cw for c in ch2 for cw in class_weights(champ_cls.get(c, ["Sin clase"]), sub)]
    return weighted_score(a, b), weighted_score(b, a)


def by_role_scores(map1, map2, champ_cls, sub):
    s1 = s2 = 0.0
    for role in ROLE_ORDER:
        c1, c2 = map1.get(role), map2.get(role)
        if not c1 or not c2:
            continue
        cw1 = class_weights(champ_cls.get(c1, ["Sin clase"]), sub)
        cw2 = class_weights(champ_cls.get(c2, ["Sin clase"]), sub)
        s1 += weighted_score(cw1, cw2)
        s2 += weighted_score(cw2, cw1)
    return s1, s2


# ────────────── Output minimal (summary + analysis) ──────────────
def create_output_dir(n, tech, sub):
    p = os.path.join("output", str(n), tech, sub)
    os.makedirs(p, exist_ok=True)
    return p


def write_results(stats, diff_stats, n, out_dir):
    with open(os.path.join(out_dir, "summary.log"), "w", encoding="utf-8") as f:
        f.write(
            f"Partidas analizadas: {n}\n"
            f"Aciertos: {stats['acierto']}\n"
            f"Fallos: {stats['fallo']}\n"
            f"Descartes: {stats['sin_datos']}\n"
            f"Empates teóricos: {stats['igualdad']}\n"
        )
    with open(os.path.join(out_dir, "analysis.log"), "w", encoding="utf-8") as f:
        f.write("Diff  aciertos  fallos  total\n")
        for d in sorted(diff_stats):
            ac, fa, tot = (diff_stats[d]["acierto"],
                           diff_stats[d]["fallo"],
                           diff_stats[d]["total"])
            f.write(f"{d:<4} {ac:<8} {fa:<6} {tot}\n")


# ─────────────────── Lógica de análisis ───────────────────
def process_matches(matches, champ_cls):
    games, missing = {}, set()
    for row in matches:
        gid = row["GameId"]
        games.setdefault(gid, {
            "Team1": row["Team1"], "Team2": row["Team2"],
            "Winner": row["Winner"], "Champions": defaultdict(list),
            "Roles": defaultdict(dict)
        })
        champ, team = row["Champion"], row["Team"]
        role = normalize_role(row["Role"])
        if champ and champ not in games[gid]["Champions"][team]:
            games[gid]["Champions"][team].append(champ)
            if champ not in champ_cls:
                missing.add(champ)
        if role:
            games[gid]["Roles"][team][role] = champ
    if missing:
        print("Campeones sin clase:", ", ".join(sorted(missing)))
    return games


def determine_actual_winner(t1, t2, winner):
    if winner == "1": return 1
    if winner == "2": return 2
    wl = winner.lower()
    if any(w in wl for w in t1.lower().split()): return 1
    if any(w in wl for w in t2.lower().split()): return 2
    return 0


def analyze_games(games, champ_cls, tech, sub):
    gstats = {"acierto": 0, "fallo": 0, "sin_datos": 0, "igualdad": 0}
    dstats = defaultdict(lambda: {"acierto": 0, "fallo": 0, "total": 0})
    for gid, d in games.items():
        t1, t2 = d["Team1"], d["Team2"]
        real   = determine_actual_winner(t1, t2, d["Winner"])
        ch1, ch2 = d["Champions"][t1], d["Champions"][t2]
        rm1, rm2 = d["Roles"].get(t1, {}), d["Roles"].get(t2, {})
        if len(ch1) < 5 or len(ch2) < 5:
            gstats["sin_datos"] += 1; dstats[0]["total"] += 1; continue
        s1, s2 = (cartesian_scores(ch1, ch2, champ_cls, sub) if tech == 0
                  else by_role_scores(rm1, rm2, champ_cls, sub))
        diff = abs(s1 - s2)
        pred = 1 if s1 > s2 else 2 if s2 > s1 else 0
        dstats[int(diff)]["total"] += 1
        if pred == real and real:
            gstats["acierto"] += 1; dstats[int(diff)]["acierto"] += 1
        elif pred == 0:
            gstats["igualdad"] += 1
        elif real == 0:
            gstats["sin_datos"] += 1
        else:
            gstats["fallo"] += 1; dstats[int(diff)]["fallo"] += 1
    return gstats, dstats


def run_analysis(n, tech, sub, champ_cls, matches):
    out = create_output_dir(n, TECHNIQUE_NAMES[tech], SUBTECHNIQUE_NAMES[sub])
    games = process_matches(matches, champ_cls)
    stats, diff_stats = analyze_games(games, champ_cls, tech, sub)
    write_results(stats, diff_stats, n, out)


# ─────────────────────────────── CLI ───────────────────────────────
def main():
    p = argparse.ArgumentParser(description="Analiza partidas guardadas en la BD.")
    p.add_argument("num_matches", nargs="?", type=int,
                   help="Nº de partidas (omitir = todas)")
    p.add_argument("--full", action="store_true",
                   help="Ejecutar todas las técnicas y sub-técnicas")
    args = p.parse_args()

    champ_cls = load_champion_classes()
    matches   = load_matches_from_db(args.num_matches)
    n         = args.num_matches or len({m["GameId"] for m in matches})

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    if args.full:
        for t in TECHNIQUE_NAMES:
            for s in SUBTECHNIQUE_NAMES:
                run_analysis(n, t, s, champ_cls, matches)
    else:
        run_analysis(n, TECHNIQUE_MODE, SUBTECHNIQUE_MODE, champ_cls, matches)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
