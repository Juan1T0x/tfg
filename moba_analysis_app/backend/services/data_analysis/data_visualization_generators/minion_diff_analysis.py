# ------------------------------------------------------------------------------
# minion_diff_analysis.py
# ------------------------------------------------------------------------------
# Generates “CS difference” charts (lane + jungle) for each lane-to-lane match-up
# and for the two teams as a whole, based on Riot’s timeline JSON.
#
# * Output tree (one PNG + HTML per figure):
#       <output_dir>/
#           p1_vs_p6/              # TOP
#               minions/…
#               jungleMinions/…
#           …
#           team/
#               minions/…
#               jungleMinions/…
#
# * Windows analysed:
#       00:00-14:00 · 14:00-25:00 · 25:00-End · 00:00-End
#
# The module exposes a single public entry-point:
#     generate_minion_diff(timeline_path: str | Path,
#                          output_dir: str | Path = "cs_diff") -> None
# ------------------------------------------------------------------------------

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import plotly.graph_objects as go

# ──────────────────────────── Time windows ──────────────────────────────
_WINDOWS: list[tuple[int, int, str]] = [
    (0, 14 * 60_000, "00:00-14:00"),
    (14 * 60_000, 25 * 60_000, "14:00-25:00"),
    (25 * 60_000, float("inf"), "25:00-Fin"),
    (0, float("inf"), "00:00-Fin"),
]

# (blue_id, red_id, folder_name)
_PAIR_IDS: list[tuple[int, int, str]] = [
    (1, 6, "p1_vs_p6"),   # TOP
    (2, 7, "p2_vs_p7"),   # JUNGLE
    (3, 8, "p3_vs_p8"),   # MID
    (4, 9, "p4_vs_p9"),   # BOT
    (5, 10, "p5_vs_p10"), # SUPPORT
]

# metric_key -> field name inside participantFrame
_METRICS: dict[str, str] = {
    "minions":        "minionsKilled",
    "jungleMinions":  "jungleMinionsKilled",
}

# ──────────────────────────── Helpers ───────────────────────────────────
def _load_timeline(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _series_pair(
    frames: List[Dict], blue: int, red: int, field: str
) -> Tuple[List[float], List[float]]:
    """Gold/CS diff for a specific lane pair (blue-id vs red-id)."""
    xs, ys = [], []
    for f in frames:
        t  = f["timestamp"] / 60_000          # convert ms → minutes
        pb = f["participantFrames"].get(str(blue))
        pr = f["participantFrames"].get(str(red))
        if pb and pr:
            xs.append(t)
            ys.append(pb[field] - pr[field])
    return xs, ys


def _series_team(frames: List[Dict], field: str) -> Tuple[List[float], List[float]]:
    """Team-wide diff (sum of blue P1-P5 minus red P6-P10)."""
    xs, ys = [], []
    for f in frames:
        t = f["timestamp"] / 60_000
        blue = sum(p[field] for pid, p in f["participantFrames"].items() if int(pid) <= 5)
        red  = sum(p[field] for pid, p in f["participantFrames"].items() if int(pid) > 5)
        xs.append(t)
        ys.append(blue - red)
    return xs, ys


def _crop(
    xs: List[float], ys: List[float], start: int, end: int
) -> Tuple[List[float], List[float]]:
    """Slice a series to the requested time window (ms)."""
    if not xs:
        return [], []
    s = start / 60_000
    e = end / 60_000 if end != float("inf") else float("inf")
    sub = [(x, y) for x, y in zip(xs, ys) if s <= x < e]
    if not sub:
        return [], []
    x_out, y_out = zip(*sub)
    return list(x_out), list(y_out)


def _plot(xs: List[float], ys: List[float], title: str, ylabel: str) -> go.Figure:
    """Plot a single time-series with a zero reference line."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="royalblue")))
    fig.add_hline(y=0, line_dash="dash", line_color="grey")
    fig.update_layout(
        title=title,
        xaxis_title="Minuto",
        yaxis_title=ylabel,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig

# ──────────────────────────── Public API ────────────────────────────────
def generate_minion_diff(
    timeline_path: str | Path, output_dir: str | Path = "cs_diff"
) -> None:
    """
    Create lane-to-lane and team CS-difference charts (minions & jungle minions).

    Parameters
    ----------
    timeline_path : str | Path
        Riot timeline JSON file.
    output_dir : str | Path, default "cs_diff"
        Destination folder; sub-directories will be created automatically.
    """
    timeline_path = Path(timeline_path)
    output_dir    = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tl      = _load_timeline(timeline_path)
    frames  = tl["frames"]

    # One folder per pair × metric
    pair_dirs: dict[str, dict[str, Path]] = {
        name: {m: output_dir / name / m for m in _METRICS} for *_, name in _PAIR_IDS
    }
    for dmap in pair_dirs.values():
        for d in dmap.values():
            d.mkdir(parents=True, exist_ok=True)

    # Team folders
    team_dirs = {m: output_dir / "team" / m for m in _METRICS}
    for d in team_dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    # ── Lane-to-lane figures ────────────────────────────────────────────
    for blue, red, tag in _PAIR_IDS:
        for mkey, field in _METRICS.items():
            xs_all, ys_all = _series_pair(frames, blue, red, field)
            if not xs_all:
                continue
            for start, end, lbl in _WINDOWS:
                xs, ys = _crop(xs_all, ys_all, start, end)
                if not xs:
                    continue
                title = f"{tag} – diff {mkey} {lbl}"
                base  = pair_dirs[tag][mkey] / f"{tag}_{mkey}_{lbl}".replace(":", "")
                _plot(xs, ys, title, f"Diferencia {mkey} (azul – rojo)")\
                    .write_html(base.with_suffix(".html"))
                _plot(xs, ys, title, f"Diferencia {mkey} (azul – rojo)")\
                    .write_image(base.with_suffix(".png"), scale=2)

    # ── Team-wide figures ──────────────────────────────────────────────
    for mkey, field in _METRICS.items():
        xs_all, ys_all = _series_team(frames, field)
        for start, end, lbl in _WINDOWS:
            xs, ys = _crop(xs_all, ys_all, start, end)
            if not xs:
                continue
            title = f"Equipo – diff {mkey} {lbl}"
            base  = team_dirs[mkey] / f"team_{mkey}_{lbl}".replace(":", "")
            _plot(xs, ys, title, f"Diferencia {mkey} (azul – rojo)")\
                .write_html(base.with_suffix(".html"))
            _plot(xs, ys, title, f"Diferencia {mkey} (azul – rojo)")\
                .write_image(base.with_suffix(".png"), scale=2)

    print(f"✔ Gráficas CS diff generadas en: {output_dir.resolve()}")

# Re-export for `from … import *`
__all__ = ["generate_minion_diff"]
