"""
services/live_game_analysis/game_state/game_state.py
====================================================

Domain model for a single League of Legends match.

The module is intentionally framework-agnostic: no persistence,
network, or external-service code — just plain data-structures that:

* represent the immutable information decided in champion-select
  (``StaticGameInfo``);
* track the in-game, frame-by-frame evolution
  (``GameSnapshot`` → ``GameTimeline``);
* can be **losslessly** serialised to / from JSON using
  :func:`to_json_compat`.

All numeric fields use raw, game units:

* ``health_pct`` / ``mana_pct`` → percentage ``0 – 100``;
* ``position`` → minimap pixel coordinates in the broadcast feed;
* economy counters (``gold`` etc.) are **absolute** values, not deltas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict, is_dataclass
from datetime import timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ─────────────────────────────── Enums ────────────────────────────────
class TeamColor(Enum):
    """Side of the map as rendered in the LEC broadcast (not always camera-true)."""

    BLUE = auto()
    RED = auto()


class Role(Enum):
    """Canonical in-game positions. Order matters for UI grids and reports."""

    TOP = auto()
    JUNGLE = auto()
    MID = auto()
    BOT = auto()
    SUPPORT = auto()


# ───────────────────────────── Base entities ──────────────────────────
@dataclass
class PlayerStats:
    """Per-player dynamic numbers captured from the HUD overlay."""

    health_pct: Optional[float] = None          # 0 – 100
    mana_pct: Optional[float] = None            # 0 – 100 (some champs are mana-less)
    position: Optional[Tuple[int, int]] = None  # (x, y) on the minimap
    kills: Optional[int] = None
    deaths: Optional[int] = None
    assists: Optional[int] = None
    cs: Optional[int] = None                    # creep-score
    gold: Optional[int] = None                  # personal gold


@dataclass
class TeamStats:
    """Aggregated team counters extracted from the top HUD bar."""

    total_kills: Optional[int] = None
    total_gold: Optional[int] = None
    towers: Optional[int] = None
    objectives: Optional[int] = None            # drakes + heralds + barons


# ───────────────────────────── Global timers ──────────────────────────
@dataclass
class GlobalTimers:
    """Respawn timers for neutral objectives (nil → timer hidden)."""

    dragon_timer: Optional[timedelta] = None
    baron_timer: Optional[timedelta] = None
    herald_timer: Optional[timedelta] = None
    voidgrub_timer: Optional[timedelta] = None
    atahkan_timer: Optional[timedelta] = None   # Arena of Atakaan (2024 event)


# ───────────────────────────── Team wrapper ───────────────────────────
@dataclass
class Team:
    """Dynamic team container: five players + rolling counters."""

    color: TeamColor
    players: Dict[Role, PlayerStats] = field(
        default_factory=lambda: {r: PlayerStats() for r in Role}
    )
    stats: TeamStats = field(default_factory=TeamStats)


# ───────────────────────────── Draft section ──────────────────────────
@dataclass
class StaticTeamInfo:
    """Data decided during champion-select and never changes afterwards."""

    color: TeamColor
    team_name: str = ""
    champions: Dict[Role, str] = field(
        default_factory=lambda: {r: "" for r in Role}
    )


@dataclass
class StaticGameInfo:
    """Both sides’ immutable draft information."""

    blue: StaticTeamInfo = field(default_factory=lambda: StaticTeamInfo(TeamColor.BLUE))
    red: StaticTeamInfo = field(default_factory=lambda: StaticTeamInfo(TeamColor.RED))


# ───────────────────────────── Live snapshot ──────────────────────────
@dataclass
class GameSnapshot:
    """All HUD-visible data for a single video frame."""

    blue: Team = field(default_factory=lambda: Team(TeamColor.BLUE))
    red: Team = field(default_factory=lambda: Team(TeamColor.RED))
    global_: GlobalTimers = field(default_factory=GlobalTimers)


# ───────────────────────────── Timeline root ──────────────────────────
@dataclass
class GameTimeline:
    """
    Complete match timeline.

    ``live_game_info`` keys are *match-timer* strings ``MM:SS``
    (or special markers ``"startGame"`` / ``"endGame"``).
    """

    static_game_info: StaticGameInfo = field(default_factory=StaticGameInfo)
    live_game_info: Dict[str, GameSnapshot] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _fmt(ts: float | timedelta | str) -> str:
        """Normalise many timestamp formats to ``MM:SS``."""
        if isinstance(ts, timedelta):
            total = int(ts.total_seconds())
        elif isinstance(ts, (int, float)):
            total = int(ts)
        else:  # already 'MM:SS'
            return ts
        return f"{total // 60:02d}:{total % 60:02d}"

    def add_snapshot(self, match_timer: float | timedelta | str, snapshot: GameSnapshot) -> None:
        """Insert / overwrite a snapshot at ``match_timer``."""
        self.live_game_info[self._fmt(match_timer)] = snapshot


# ───────────────────────────── JSON serialiser ─────────────────────────
def to_json_compat(obj: Any) -> Any:
    """
    Recursively convert dataclasses, Enums, timedeltas… into plain
    JSON-serialisable structures.

    The output is guaranteed to be accepted by :pyfunc:`json.dumps`.
    """
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

    return obj  # primitives are returned unchanged
