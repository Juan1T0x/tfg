from __future__ import annotations
from dataclasses import dataclass, field, asdict, is_dataclass
from enum import Enum, auto
from typing import Optional, Dict, Any
from datetime import timedelta, datetime
import json, pathlib

# ─────────────────── Enums ────────────────────
class TeamColor(Enum):
    BLUE = auto()
    RED  = auto()

class Role(Enum):
    TOP     = auto()
    JUNGLE  = auto()
    MID     = auto()
    BOT     = auto()
    SUPPORT = auto()

# ───────────── Entidades básicas ──────────────
@dataclass
class PlayerStats:
    health_pct: Optional[float]      = None
    mana_pct:   Optional[float]      = None
    position:   Optional[tuple[int, int]] = None  # (x, y)
    kills:      Optional[int]        = None
    deaths:     Optional[int]        = None
    assists:    Optional[int]        = None
    cs:         Optional[int]        = None
    gold:       Optional[int]        = None

@dataclass
class TeamStats:
    total_kills: Optional[int] = None
    total_gold:  Optional[int] = None
    towers:      Optional[int] = None
    objectives:  Optional[int] = None

# ───────────── Estado global ─────────────
@dataclass
class GlobalTimers:
    dragon_timer:   Optional[timedelta] = None
    baron_timer:    Optional[timedelta] = None
    herald_timer:   Optional[timedelta] = None
    voidgrub_timer: Optional[timedelta] = None
    atahkan_timer:  Optional[timedelta] = None

@dataclass
class Team:
    color: TeamColor
    players: Dict[Role, PlayerStats] = field(
        default_factory=lambda: {r: PlayerStats() for r in Role}
    )
    stats:   TeamStats = field(default_factory=TeamStats)

# ─────────── info estática (draft) ────────────
@dataclass
class StaticTeamInfo:
    color: TeamColor
    team_name: str = ""
    champions: Dict[Role, str] = field(
        default_factory=lambda: {r: "" for r in Role}
    )

@dataclass
class StaticGameInfo:
    blue: StaticTeamInfo = field(default_factory=lambda: StaticTeamInfo(TeamColor.BLUE))
    red:  StaticTeamInfo = field(default_factory=lambda: StaticTeamInfo(TeamColor.RED))

# ─────────── fotograma dinámico ────────────
@dataclass
class GameSnapshot:
    blue:   Team          = field(default_factory=lambda: Team(TeamColor.BLUE))
    red:    Team          = field(default_factory=lambda: Team(TeamColor.RED))
    global_: GlobalTimers = field(default_factory=GlobalTimers)

# ─────────── línea temporal completa ─────────
@dataclass
class GameTimeline:
    static_game_info: StaticGameInfo = field(default_factory=StaticGameInfo)
    live_game_info: Dict[str, GameSnapshot] = field(default_factory=dict)

    @staticmethod
    def _fmt(ts: float | timedelta | str) -> str:
        if isinstance(ts, timedelta):
            total = int(ts.total_seconds())
        elif isinstance(ts, (int, float)):
            total = int(ts)
        else:
            return ts                         # ya es "MM:SS"
        return f"{total//60:02d}:{total%60:02d}"

    def add_snapshot(self, match_timer: float | timedelta | str,
                     snapshot: GameSnapshot) -> None:
        self.live_game_info[self._fmt(match_timer)] = snapshot

# ────────────────── Serializador ──────────────────
def to_json_compat(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: to_json_compat(v) for k, v in asdict(obj).items()}

    if isinstance(obj, Enum):
        return obj.name

    if isinstance(obj, timedelta):
        return int(obj.total_seconds())

    if isinstance(obj, dict):
        return {to_json_compat(k): to_json_compat(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [to_json_compat(v) for v in obj]

    return obj