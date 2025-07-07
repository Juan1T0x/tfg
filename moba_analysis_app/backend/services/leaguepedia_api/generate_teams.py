#!/usr/bin/env python3
# generate_teams.py  – usa el reporte creado por combo_winrate.py
from __future__ import annotations

import argparse, csv, itertools, re, sqlite3, subprocess, sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# ──────────────── rutas / tablas ────────────────
BASE_DIR    = Path(__file__).resolve().parent
DB_PATH     = BASE_DIR.parent / "database" / "moba_analysis.sqlite"
CHAMP_TABLE = "champions"

OUTPUT_ROOT = Path("output")
REPORT_FILE = OUTPUT_ROOT / "combo_winrate_report.log"

ROLE_ORDER  = ["top", "jungle", "mid", "bot", "support"]

# ─────────── 1) asegurarse de tener el log ───────────
def ensure_report(num_matches: int | None, min_games: int, top_k: int) -> Path:
    """Devuelve la ruta al reporte; si no existe, llama a combo_winrate.py."""
    if REPORT_FILE.exists():
        return REPORT_FILE

    cmd = [sys.executable, "combo_winrate.py", "-m", str(min_games), "-k", str(top_k)]
    if num_matches:
        cmd.extend(["-n", str(num_matches)])

    print("⚙  Ejecutando:", " ".join(cmd))
    try:
        subprocess.run(cmd, cwd=BASE_DIR, check=True)
    except subprocess.CalledProcessError:
        sys.exit("❌  combo_winrate.py terminó con error")

    if not REPORT_FILE.exists():
        sys.exit("❌  No se generó combo_winrate_report.log")
    return REPORT_FILE

# ─────────── 2) leer combinaciones del log ───────────
LOG_LINE_RE = re.compile(r"^\s*(\d+)\.\s.*?→\s*(.+)$")
COMBO_RE    = re.compile(r"(\w+)\[([^\]]+)\]")

def extract_combos(lines: List[str]) -> Dict[int, str]:
    combos: Dict[int, str] = {}
    for ln in lines:
        if m := LOG_LINE_RE.match(ln):
            combos[int(m.group(1))] = m.group(2).strip()
    return combos

def parse_combo_string(combo: str) -> Dict[str, List[str]]:
    role_map: Dict[str, List[str]] = {}
    for role, classes in COMBO_RE.findall(combo):
        role_map[role.lower()] = [c.strip().lower() for c in classes.split(",") if c.strip()]
    return role_map

# ─────────── 3) helpers de campeones ───────────
def load_champion_classes() -> Dict[str, List[str]]:
    d: Dict[str, List[str]] = {}
    with sqlite3.connect(DB_PATH) as conn:
        for name, roles in conn.execute(f"SELECT champion_name, roles FROM {CHAMP_TABLE}"):
            d[name] = [r.strip() for r in roles.split(",") if r.strip()] if roles else ["Sin clase"]
    return d

def champions_by_role_exact(role_classes, champ_cls) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for role, needed in role_classes.items():
        out[role] = sorted(
            c for c, cls in champ_cls.items()
            if [x.lower() for x in cls] == needed
        )
    return out

def generate_team_combinations(role_champs) -> List[Dict[str, str]]:
    prod = itertools.product(*(role_champs[r] for r in ROLE_ORDER))
    return [
        {r: c for r, c in zip(ROLE_ORDER, combo)}
        for combo in prod if len(set(combo)) == len(combo)
    ]

# ─────────── 4) main ───────────
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Genera equipos posibles a partir de una combinación del reporte de combo_winrate.py")
    ap.add_argument("-n", "--num-matches", type=int,
                    help="Si el reporte no existe: nº de partidas para combo_winrate")
    ap.add_argument("-m", "--min-games", type=int, default=5,
                    help="Min partidas por combo (parámetro para combo_winrate)")
    ap.add_argument("-k", "--top", type=int, default=40,
                    help="Máx combos listados (parámetro para combo_winrate)")
    args = ap.parse_args()

    report_path = ensure_report(args.num_matches, args.min_games, args.top)
    report_lines = report_path.read_text(encoding="utf-8").splitlines()

    # ── mostrar el log completo ──
    print("\n" + "\n".join(report_lines) + "\n")

    combos = extract_combos(report_lines)
    if not combos:
        sys.exit("❌  El reporte no contiene combinaciones válidas")

    sel = None
    while sel not in combos:
        raw = input(f"Elige índice (1-{max(combos)}): ").strip()
        sel = int(raw) if raw.isdigit() else None

    choice = combos[sel]
    print(f"\n➜  Seleccionada: {choice}\n")

    champ_cls   = load_champion_classes()
    role_classes = parse_combo_string(choice)
    role_champs  = champions_by_role_exact(role_classes, champ_cls)

    for r in ROLE_ORDER:
        print(f"{r.capitalize():<8}: {len(role_champs[r])} , que son: {', '.join(role_champs[r]) or 'Ninguno'}")

    teams = generate_team_combinations(role_champs)
    print(f"\nSe han generado {len(teams):,} equipos posibles.")

    if not teams:
        return

    MAX_PRINT = 200
    if len(teams) <= MAX_PRINT:
        print("\nEjemplos:\n")
        for t in teams:
            print(", ".join(f"{r}={c}" for r, c in t.items()))
    else:
        if input(f"\n¿Guardar los {len(teams):,} equipos en CSV? [s/N]: ").lower().startswith("s"):
            dest = Path(f"teams_idx{sel}.csv")
            with dest.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=ROLE_ORDER)
                writer.writeheader()
                writer.writerows(teams)
            print(f"✔ CSV guardado en {dest.resolve()}")

if __name__ == "__main__":
    main()
