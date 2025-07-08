from __future__ import annotations

import json, unicodedata, copy, re
from pathlib import Path
from typing import Dict, Any

from .game_state import Role, GameTimeline, GameSnapshot, to_json_compat

# ───────────── paths ─────────────
_BASE = Path(__file__).resolve().parents[3]          # …/backend
_HISTORY = _BASE / "matches_history"
_HISTORY.mkdir(parents=True, exist_ok=True)

_ROLE_LIST: list[Role] = [
    Role.TOP,
    Role.JUNGLE,
    Role.MID,
    Role.BOT,
    Role.SUPPORT,
]

# ───────────── helpers ─────────────
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
    tl.static_game_info.red.team_name = sg.get("red", {}).get("team_name", "")
    tl.static_game_info.blue.champions = sg.get("blue", {}).get("champions", {})
    tl.static_game_info.red.champions = sg.get("red", {}).get("champions", {})
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
    out: Dict[str, str] = {r.name: "" for r in Role}
    for k, v in src.items():
        key = k.name if isinstance(k, Role) else str(k).upper()
        if key in Role.__members__:
            out[key] = v
    return out


def _read_raw(title: str) -> Dict[str, Any]:
    fp = _path_for(title)
    if not fp.exists():
        raise FileNotFoundError(f"Partida «{title}» no encontrada.")
    return json.loads(fp.read_text(encoding="utf-8"))

# ───────────── operaciones principales ─────────────
def start_game(
    match_title: str,
    blue_team_name: str,
    blue_champions: Dict[Any, str],
    red_team_name: str,
    red_champions: Dict[Any, str],
) -> None:
    tl = GameTimeline()
    tl.static_game_info.blue.team_name = blue_team_name
    tl.static_game_info.red.team_name = red_team_name
    tl.static_game_info.blue.champions = _norm_champions(blue_champions)
    tl.static_game_info.red.champions  = _norm_champions(red_champions)
    tl.live_game_info["startGame"] = to_json_compat(GameSnapshot())
    _save(match_title, tl)


def add_or_update_snapshot(
    match_title: str,
    timer: str | int | float,
    snapshot_dict: Dict[str, Any],
) -> None:
    tl = _load(match_title)
    if isinstance(timer, (int, float)):
        secs = int(timer)
        key  = f"{secs//60:02d}:{secs%60:02d}"
    else:
        key  = timer
    tl.live_game_info[key] = _deep_merge(tl.live_game_info.get(key, {}), snapshot_dict)
    _save(match_title, tl)


def end_game(match_title: str, winner: int) -> None:
    tl   = _load(match_title)
    keys = [k for k in tl.live_game_info if k not in ("startGame", "endGame")]
    if not keys:
        raise RuntimeError("No hay snapshots para duplicar.")
    last_key = max(keys, key=lambda k: int(k.split(":")[0]) * 60 + int(k.split(":")[1]))
    tl.live_game_info["endGame"] = copy.deepcopy(tl.live_game_info[last_key])
    tl.live_game_info["winner"]  = "BLUE" if winner == 0 else "RED"
    _save(match_title, tl)


def get_game_state(match_title: str) -> Dict[str, Any]:
    return _read_raw(match_title)


def get_all_game_states() -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for match_dir in _HISTORY.iterdir():
        if not match_dir.is_dir():
            continue
        gs = match_dir / "game_state.json"
        tl = match_dir / "time_line.json"
        path: Path | None = gs if gs.is_file() else tl if tl.is_file() else None
        if path is None:
            continue
        try:
            result[match_dir.name] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return result


def create_snapshot_from_detection(
    match_title: str, health: dict, mana: dict, stats: dict
) -> bool:
    timer = stats.get("time", {}).get("parsed")
    if not (isinstance(timer, str) and re.fullmatch(r"\d{1,2}:\d{2}", timer)):
        return False

    def _player(team: str, idx: int) -> dict:
        role = _ROLE_LIST[idx].name
        out: dict[str, Any] = {}
        hp = health.get(team, {}).get(role)
        mp = mana.get(team, {}).get(role)
        if hp is not None:
            out["health_pct"] = hp
        if mp is not None:
            out["mana_pct"] = mp
        kda = stats.get(f"{team}Player{idx+1}kda", {}).get("parsed")
        if isinstance(kda, dict):
            out.update(kills=kda["k"], deaths=kda["d"], assists=kda["a"])
        cs = stats.get(f"{team}Player{idx+1}creeps", {}).get("parsed")
        if cs is not None:
            out["cs"] = cs
        return out

    def _team_stats(team: str) -> dict:
        out: dict[str, Any] = {}
        gold = stats.get(f"{team}Gold", {}).get("parsed")
        if isinstance(gold, str) and gold.endswith("K"):
            try:
                out["total_gold"] = int(float(gold[:-1]) * 1000)
            except ValueError:
                pass
        elif isinstance(gold, (int, float)):
            out["total_gold"] = int(gold)
        towers = stats.get(f"{team}Towers", {}).get("parsed")
        if towers is not None:
            out["towers"] = towers
        return out

    snapshot = {
        "blue": {
            "players": {r.name: _player("blue", i) for i, r in enumerate(_ROLE_LIST)},
            "stats": _team_stats("blue"),
        },
        "red": {
            "players": {r.name: _player("red", i) for i, r in enumerate(_ROLE_LIST)},
            "stats": _team_stats("red"),
        },
        "global_": {},
    }

    add_or_update_snapshot(match_title, timer, snapshot)
    return True


# alias más corto
update_game = create_snapshot_from_detection

# ───────────── exports ─────────────
__all__: list[str] = []
__all__.extend(
    [
        "start_game",
        "add_or_update_snapshot",
        "end_game",
        "get_game_state",
        "get_all_game_states",
        "create_snapshot_from_detection",
        "update_game",
    ]
)
