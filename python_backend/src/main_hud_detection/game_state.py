from __future__ import annotations
from dataclasses import dataclass, field, asdict, is_dataclass
from enum import Enum, auto
from typing import Optional, Dict, Any
from datetime import timedelta
import json

# ─────────────────── Enums ────────────────────
class TeamColor(Enum):
    BLUE = auto()
    RED  = auto()

class Role(Enum):
    TOP      = auto()
    JUNGLE   = auto()
    MID      = auto()
    BOT      = auto()
    SUPPORT  = auto()

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
    color:   TeamColor
    players: Dict[Role, PlayerStats] = field(
        default_factory=lambda: {r: PlayerStats() for r in Role}
    )
    stats:   TeamStats = field(default_factory=TeamStats)

@dataclass
class GameState:
    blue:   Team          = field(default_factory=lambda: Team(TeamColor.BLUE))
    red:    Team          = field(default_factory=lambda: Team(TeamColor.RED))
    global_: GlobalTimers = field(default_factory=GlobalTimers)

# ────────────────── Serializador ──────────────────
def to_json_compat(obj: Any) -> Any:
    """Convierte dataclasses/Enum/timedelta a estructuras JSON-compatibles."""
    if is_dataclass(obj):
        return {k: to_json_compat(v) for k, v in asdict(obj).items()}

    if isinstance(obj, Enum):
        return obj.name

    if isinstance(obj, timedelta):
        return int(obj.total_seconds())  # segundos

    if isinstance(obj, dict):
        return {to_json_compat(k): to_json_compat(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [to_json_compat(v) for v in obj]

    return obj  # int, str, float, bool, None, …

# ───────────── Ejemplo de uso ─────────────
if __name__ == "__main__":
    state = GameState()

    # Actualizar stats de prueba
    jungle_blue = state.blue.players[Role.JUNGLE]
    jungle_blue.health_pct = 100.0
    jungle_blue.mana_pct   = 75.0

    state.red.stats.total_kills = (state.red.stats.total_kills or 0) + 1
    state.red.stats.total_gold  = (state.red.stats.total_gold  or 0) + 300

    state.global_.dragon_timer = timedelta(minutes=2, seconds=15)

    # Mostrar y guardar
    print(state)

    with open("game_state.json", "w", encoding="utf-8") as f:
        json.dump(to_json_compat(state), f, indent=4, ensure_ascii=False)
