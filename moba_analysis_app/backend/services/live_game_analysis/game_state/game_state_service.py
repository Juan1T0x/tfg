"""Game-State Service – gestiona `game_state.json` por partida."""
from __future__ import annotations

import json, re, unicodedata, copy
from pathlib import Path
from datetime import timedelta
from typing import Dict, Any

from .game_state import (          # modelos
    Role, GameTimeline, GameSnapshot, to_json_compat
)

# ───────────── paths ─────────────
_BASE = Path(__file__).resolve().parents[3]          # …/backend
_HISTORY = _BASE / "matches_history"
_HISTORY.mkdir(parents=True, exist_ok=True)

# ───────────── utilidades ─────────
def _slugify(text: str) -> str:
    txt = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9.\-]+", "-", txt).strip("-").lower() or "match"

def _path_for(title: str) -> Path:
    return _HISTORY / _slugify(title) / "game_state.json"

def _deep_merge(dst: Dict[str, Any], inc: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in inc.items():
        dst[k] = _deep_merge(dst.get(k, {}), v) if isinstance(v, dict) else v
    return dst

def _dict_to_timeline(d: Dict[str, Any]) -> GameTimeline:
    tl = GameTimeline()
    sg = d.get("static_game_info", {})
    tl.static_game_info.blue.team_name = sg.get("blue", {}).get("team_name", "")
    tl.static_game_info.red.team_name  = sg.get("red",  {}).get("team_name", "")
    tl.static_game_info.blue.champions = sg.get("blue", {}).get("champions", {})
    tl.static_game_info.red.champions  = sg.get("red",  {}).get("champions", {})
    tl.live_game_info = d.get("live_game_info", {})
    return tl

def _load(title: str) -> GameTimeline:
    fp = _path_for(title)
    if not fp.exists():
        raise FileNotFoundError(f"Partida «{title}» no iniciada.")
    return _dict_to_timeline(json.loads(fp.read_text("utf-8")))

def _save(title: str, tl: GameTimeline) -> None:
    fp = _path_for(title)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(to_json_compat(tl), indent=4, ensure_ascii=False))

def _norm_champions(src: Dict[Any, str]) -> Dict[str, str]:
    """
    Convierte un dict que puede venir con claves `Role` **o** str a:
        { "TOP": "Gwen", … }
    Se ignoran claves que no sean posiciones válidas.
    """
    out: Dict[str, str] = {r.name: "" for r in Role}          # plantilla
    for k, v in src.items():
        key = k.name if isinstance(k, Role) else str(k).upper()
        if key in Role.__members__:
            out[key] = v
    return out

def _read_raw(title: str) -> Dict[str, Any]:
    """Devuelve el JSON (dict) tal cual está almacenado en disco."""
    fp = _path_for(title)
    if not fp.exists():
        raise FileNotFoundError(f"Partida «{title}» no encontrada.")
    return json.loads(fp.read_text(encoding="utf-8"))

# ═════════════ API PÚBLICA ═════════════
def start_game(
    match_title:    str,
    blue_team_name: str,
    blue_champions: Dict[Any, str],      # <── Any → acepta Role o str
    red_team_name:  str,
    red_champions:  Dict[Any, str],
) -> None:
    """Crea/reescribe `game_state.json` para la partida *match_title*."""
    tl = GameTimeline()
    tl.static_game_info.blue.team_name = blue_team_name
    tl.static_game_info.red.team_name  = red_team_name

    # ⬇️  normalizamos los diccionarios
    tl.static_game_info.blue.champions = _norm_champions(blue_champions)
    tl.static_game_info.red.champions  = _norm_champions(red_champions)

    tl.live_game_info["startGame"] = to_json_compat(GameSnapshot())
    _save(match_title, tl)

def add_or_update_snapshot(
    match_title: str,
    timer: str | int | float,
    snapshot_dict: Dict[str, Any],
) -> None:
    """Inserta o fusiona (deep-merge) un fotograma en la partida."""
    tl = _load(match_title)

    # normaliza clave MM:SS
    if isinstance(timer, (int, float)):
        secs = int(timer)
        key = f"{secs//60:02d}:{secs%60:02d}"
    else:
        key = timer

    tl.live_game_info[key] = _deep_merge(tl.live_game_info.get(key, {}), snapshot_dict)
    _save(match_title, tl)

def end_game(match_title: str, winner: int) -> None:
    """Copia el último snapshot en «endGame» y marca el ganador."""
    tl = _load(match_title)

    keys = [k for k in tl.live_game_info if k not in ("startGame", "endGame")]
    if not keys:
        raise RuntimeError("No hay snapshots para duplicar.")
    last_key = max(keys, key=lambda k: int(k.split(":")[0])*60 + int(k.split(":")[1]))
    tl.live_game_info["endGame"] = copy.deepcopy(tl.live_game_info[last_key])
    tl.live_game_info["winner"]  = "BLUE" if winner == 0 else "RED"
    _save(match_title, tl)

def get_game_state(match_title: str) -> Dict[str, Any]:
    """Carga y devuelve el *game_state.json* de `match_title`."""
    return _read_raw(match_title)

def get_all_game_states() -> Dict[str, Dict[str, Any]]:
    """
    Recorre `matches_history/` y para cada subcarpeta carga, por orden
    de preferencia, el `game_state.json` o –si no existe– el `time_line.json`.

    Devuelve:
        { "slug-partida": <contenido JSON>, ... }
    """
    result: Dict[str, Dict[str, Any]] = {}

    for match_dir in _HISTORY.iterdir():
        if not match_dir.is_dir():
            continue                                     # ignora ficheros sueltos

        gs_path = match_dir / "game_state.json"
        tl_path = match_dir / "time_line.json"

        path: Path | None = None
        if gs_path.is_file():
            path = gs_path
        elif tl_path.is_file():
            path = tl_path

        if path is None:
            continue                                     # carpeta vacía / sin JSON

        try:
            result[match_dir.name] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:                                # JSON corrupto → lo salta
            continue

    return result
