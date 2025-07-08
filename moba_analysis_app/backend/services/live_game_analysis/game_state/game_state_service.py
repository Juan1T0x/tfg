"""
services/live_game_analysis/game_state/game_state_service.py
============================================================

High-level helper around :pymod:`services.live_game_analysis.game_state.game_state`
that **persists** a match timeline to disk (``backend/matches_history``).

It exposes a minimal CRUD-like public surface:

* :func:`start_game`               – create a brand-new ``game_state.json``.
* :func:`add_or_update_snapshot`   – merge a new HUD snapshot.
* :func:`end_game`                 – stamp the winner & final frame.
* :func:`get_game_state`           – load a single file.
* :func:`get_all_game_states`      – aggregate every folder.
* :func:`update_game`              – convenience wrapper that turns the raw
  OCR + bar detections produced by the worker into a proper snapshot.

The serializer / deserializer for the nested dataclasses lives in the
sibling module :pymod:`game_state`.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List

from .game_state import GameSnapshot, GameTimeline, Role, to_json_compat

# --------------------------------------------------------------------- #
# Constants & paths                                                     #
# --------------------------------------------------------------------- #
_BASE = Path(__file__).resolve().parents[3]          # …/backend
_HISTORY = _BASE / "matches_history"
_HISTORY.mkdir(parents=True, exist_ok=True)

_ROLE_ORDER: List[Role] = [
    Role.TOP,
    Role.JUNGLE,
    Role.MID,
    Role.BOT,
    Role.SUPPORT,
]

# --------------------------------------------------------------------- #
# Internal helpers                                                      #
# --------------------------------------------------------------------- #
def _slugify(text: str) -> str:
    """Filesystem-safe folder name (latinised, kebab-case, max 1 segment)."""
    txt = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9.\-]+", "-", txt).strip("-").lower() or "match"


def _path_for(title: str) -> Path:
    """Absolute path of the ``game_state.json`` belonging to *title*."""
    return _HISTORY / _slugify(title) / "game_state.json"


def _deep_merge(dst: Dict[str, Any], inc: Dict[str, Any]) -> Dict[str, Any]:
    """Recursive dict merge – *inc* wins on scalar leaves."""
    for k, v in inc.items():
        dst[k] = _deep_merge(dst.get(k, {}), v) if isinstance(v, dict) else v
    return dst


def _dict_to_timeline(raw: Dict[str, Any]) -> GameTimeline:
    """De-serialise plain JSON into a :class:`GameTimeline` instance."""
    tl = GameTimeline()
    sg = raw.get("static_game_info", {})
    tl.static_game_info.blue.team_name = sg.get("blue", {}).get("team_name", "")
    tl.static_game_info.red.team_name = sg.get("red", {}).get("team_name", "")
    tl.static_game_info.blue.champions = sg.get("blue", {}).get("champions", {})
    tl.static_game_info.red.champions = sg.get("red", {}).get("champions", {})
    tl.live_game_info = raw.get("live_game_info", {})
    return tl


def _load(title: str) -> GameTimeline:
    """Read file → timeline object (raises if the match does not exist)."""
    fp = _path_for(title)
    if not fp.exists():
        raise FileNotFoundError(f"Match “{title}” not found.")
    return _dict_to_timeline(json.loads(fp.read_text(encoding="utf-8")))


def _save(title: str, tl: GameTimeline) -> None:
    """Serialise *tl* back to its JSON file."""
    fp = _path_for(title)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(to_json_compat(tl), indent=4, ensure_ascii=False))


def _normalise_champ_dict(src: Dict[Any, str]) -> Dict[str, str]:
    """Accept Role or str keys → always return ``{"TOP": "Gwen", …}``."""
    out: Dict[str, str] = {r.name: "" for r in Role}
    for k, v in src.items():
        key = k.name if isinstance(k, Role) else str(k).upper()
        if key in Role.__members__:
            out[key] = v
    return out


# --------------------------------------------------------------------- #
# Public API                                                            #
# --------------------------------------------------------------------- #
def start_game(
    match_title: str,
    blue_team_name: str,
    blue_champions: Dict[Any, str],
    red_team_name: str,
    red_champions: Dict[Any, str],
) -> None:
    """Create / overwrite the timeline with the immutable draft data."""
    tl = GameTimeline()
    tl.static_game_info.blue.team_name = blue_team_name
    tl.static_game_info.red.team_name = red_team_name
    tl.static_game_info.blue.champions = _normalise_champ_dict(blue_champions)
    tl.static_game_info.red.champions = _normalise_champ_dict(red_champions)
    tl.live_game_info["startGame"] = to_json_compat(GameSnapshot())
    _save(match_title, tl)


def add_or_update_snapshot(
    match_title: str,
    timer: str | int | float,
    snapshot_dict: Dict[str, Any],
) -> None:
    """
    Insert a new frame or merge-update an existing one (idempotent).

    *timer* accepts:

    * ``"MM:SS"`` text,
    * absolute seconds **int / float**,
    * :class:`datetime.timedelta`.
    """
    tl = _load(match_title)

    if isinstance(timer, (int, float)):
        secs = int(timer)
        key = f"{secs // 60:02d}:{secs % 60:02d}"
    else:
        key = str(timer)

    tl.live_game_info[key] = _deep_merge(tl.live_game_info.get(key, {}), snapshot_dict)
    _save(match_title, tl)


def end_game(match_title: str, winner: int) -> None:
    """Copy the last frame into ``endGame`` and register the winning side."""
    tl = _load(match_title)
    usable = [k for k in tl.live_game_info if k not in ("startGame", "endGame")]
    if not usable:
        raise RuntimeError("No snapshots recorded for that match.")
    last_key = max(usable, key=lambda k: int(k.split(":")[0]) * 60 + int(k.split(":")[1]))
    tl.live_game_info["endGame"] = copy.deepcopy(tl.live_game_info[last_key])
    tl.live_game_info["winner"] = "BLUE" if winner == 0 else "RED"
    _save(match_title, tl)


def get_game_state(match_title: str) -> Dict[str, Any]:
    """Return the raw JSON dict for *match_title* (no validation performed)."""
    return json.loads(_path_for(match_title).read_text(encoding="utf-8"))


def get_all_game_states() -> Dict[str, Dict[str, Any]]:
    """
    Walk every sub-folder under ``matches_history`` and load the first
    JSON file found (``game_state.json`` preferred over ``time_line.json``).
    """
    out: Dict[str, Dict[str, Any]] = {}
    for d in _HISTORY.iterdir():
        if not d.is_dir():
            continue
        gs, tl = d / "game_state.json", d / "time_line.json"
        src = gs if gs.is_file() else tl if tl.is_file() else None
        if not src:
            continue
        try:
            out[d.name] = json.loads(src.read_text(encoding="utf-8"))
        except Exception:
            # Corrupted file – skip, but keep the worker running.
            continue
    return out


# --------------------------------------------------------------------- #
# Worker integration: OCR → snapshot                                    #
# --------------------------------------------------------------------- #
def create_snapshot_from_detection(
    match_title: str,
    health: dict,
    mana: dict,
    stats: dict,
) -> bool:
    """
    Transform the raw output from the detection worker into a canonical
    snapshot and merge it into the timeline.

    Returns **True** if the snapshot was accepted (timer parsed) or
    **False** if the line did not contain a recognisable ``MM:SS``.
    """
    timer = stats.get("time", {}).get("parsed")
    if not (isinstance(timer, str) and re.fullmatch(r"\d{1,2}:\d{2}", timer)):
        return False

    # ---- per-player ---------------------------------------------------
    def _player(team: str, idx: int) -> Dict[str, Any]:
        role = _ROLE_ORDER[idx].name
        out: Dict[str, Any] = {}

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

    # ---- team aggregates ---------------------------------------------
    def _team_stats(team: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        gold = stats.get(f"{team}Gold", {}).get("parsed")
        if isinstance(gold, str) and gold.endswith("K"):
            try:
                out["total_gold"] = int(float(gold[:-1]) * 1_000)
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
            "players": {r.name: _player("blue", i) for i, r in enumerate(_ROLE_ORDER)},
            "stats": _team_stats("blue"),
        },
        "red": {
            "players": {r.name: _player("red", i) for i, r in enumerate(_ROLE_ORDER)},
            "stats": _team_stats("red"),
        },
        "global_": {},
    }

    add_or_update_snapshot(match_title, timer, snapshot)
    return True


# Short alias used by the worker
update_game = create_snapshot_from_detection

# --------------------------------------------------------------------- #
# Re-export                                                             #
# --------------------------------------------------------------------- #
__all__: List[str] = [
    "start_game",
    "add_or_update_snapshot",
    "end_game",
    "get_game_state",
    "get_all_game_states",
    "create_snapshot_from_detection",
    "update_game",
]
