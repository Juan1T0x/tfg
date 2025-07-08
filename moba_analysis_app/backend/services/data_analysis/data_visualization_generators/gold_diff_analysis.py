#!/usr/bin/env python3
"""
generate_gold_diff
==================

Builds **gold–difference** curves from a `time_line.json` produced by Riot.

Two types of series are exported:

1. **Lane-to-lane** comparisons – five fixed pairs  
   (TOP vs TOP, JUNGLE vs JUNGLE, … SUPPORT vs SUPPORT).
2. **Whole-team** comparison – the sum of the five players on each side.

For every series four time windows are rendered:

=========  ===============  ===============
start (ms) end (ms)         label
=========  ===============  ===============
0          14 min           ``00:00-14:00``
14 min     25 min           ``14:00-25:00``
25 min     ∞                ``25:00-End``
0          ∞                ``00:00-End``
=========  ===============  ===============

Each plot is saved both as an interactive **HTML** file and as a high-resolution
**PNG** inside

``<output_dir>/<pair | team>/<file>.{html,png}``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import plotly.graph_objects as go

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# (start-ms, end-ms, label) – order matters for the output file names
_WINDOWS: list[tuple[int, int, str]] = [
    (0, 14 * 60_000, "00:00-14:00"),
    (14 * 60_000, 25 * 60_000, "14:00-25:00"),
    (25 * 60_000, float("inf"), "25:00-End"),
    (0, float("inf"), "00:00-End"),
]

# (blue-pid, red-pid, sub-folder)
_PAIR_IDS: list[tuple[int, int, str]] = [
    (1, 6, "p1_vs_p6"),   # TOP
    (2, 7, "p2_vs_p7"),   # JUNGLE
    (3, 8, "p3_vs_p8"),   # MID
    (4, 9, "p4_vs_p9"),   # BOT
    (5, 10, "p5_vs_p10"), # SUPPORT
]

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _load_timeline(path: Path) -> Dict:
    """Return the raw timeline as a Python dict."""
    return json.loads(path.read_text(encoding="utf-8"))


def _series_pair(
    frames: List[Dict], blue_pid: int, red_pid: int
) -> Tuple[List[float], List[float]]:
    """
    Gold advantage (blue – red) for a single duo-lane.

    Returns
    -------
    xs : list[float]
        Minutes since match start.
    ys : list[float]
        Gold difference for the lane (blue – red).
    """
    xs, ys = [], []
    for fr in frames:
        t_min = fr["timestamp"] / 60_000
        pb = fr["participantFrames"].get(str(blue_pid))
        pr = fr["participantFrames"].get(str(red_pid))
        if pb and pr:
            xs.append(t_min)
            ys.append(pb["totalGold"] - pr["totalGold"])
    return xs, ys


def _series_team(frames: List[Dict]) -> Tuple[List[float], List[float]]:
    """Gold advantage (blue – red) for the **whole team**."""
    xs, ys = [], []
    for fr in frames:
        t_min = fr["timestamp"] / 60_000
        blue = sum(pf["totalGold"] for pid, pf in fr["participantFrames"].items() if int(pid) <= 5)
        red  = sum(pf["totalGold"] for pid, pf in fr["participantFrames"].items() if int(pid) > 5)
        xs.append(t_min)
        ys.append(blue - red)
    return xs, ys


def _crop(
    xs: List[float], ys: List[float], start_ms: int, end_ms: int
) -> Tuple[List[float], List[float]]:
    """Restrict a series to the window ``start_ms <= t < end_ms``."""
    if not xs:
        return [], []

    s_min = start_ms / 60_000
    e_min = end_ms / 60_000 if end_ms != float("inf") else float("inf")

    chunk = [(x, y) for x, y in zip(xs, ys) if s_min <= x < e_min]
    if not chunk:
        return [], []

    xs_sub, ys_sub = zip(*chunk)
    return list(xs_sub), list(ys_sub)


def _plot(xs: List[float], ys: List[float], title: str) -> go.Figure:
    """Create a Plotly figure with the project’s default styling."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="gold")))
    fig.add_hline(y=0, line_dash="dash", line_color="grey")
    fig.update_layout(
        title=title,
        xaxis_title="Minute",
        yaxis_title="Gold diff (blue – red)",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig


# --------------------------------------------------------------------------- #
# Public entry-point
# --------------------------------------------------------------------------- #


def generate_gold_diff(timeline_path: str | Path, output_dir: str | Path) -> None:
    """
    Generate all gold-difference plots for the supplied timeline.

    Parameters
    ----------
    timeline_path : str | Path
        Path to Riot’s ``time_line.json``.
    output_dir    : str | Path
        Destination folder – sub-directories are created automatically.
    """
    timeline_path = Path(timeline_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames = _load_timeline(timeline_path)["frames"]

    # Pair-wise output folders
    pair_dirs = {tag: output_dir / tag for *_, tag in _PAIR_IDS}
    for d in pair_dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    # Team series
    team_dir = output_dir / "team"
    team_dir.mkdir(parents=True, exist_ok=True)

    # ----------- lane-to-lane curves ------------------------------------ #
    for blue_pid, red_pid, tag in _PAIR_IDS:
        xs_all, ys_all = _series_pair(frames, blue_pid, red_pid)
        if not xs_all:
            continue

        for start, end, lbl in _WINDOWS:
            xs, ys = _crop(xs_all, ys_all, start, end)
            if not xs:
                continue

            fig = _plot(xs, ys, f"{tag} – gold diff {lbl}")
            base = pair_dirs[tag] / f"{tag}_{lbl}".replace(":", "")
            fig.write_html(base.with_suffix(".html"))
            fig.write_image(base.with_suffix(".png"), scale=2)

    # ----------- whole-team curves -------------------------------------- #
    xs_all, ys_all = _series_team(frames)
    for start, end, lbl in _WINDOWS:
        xs, ys = _crop(xs_all, ys_all, start, end)
        if not xs:
            continue

        fig = _plot(xs, ys, f"Team – gold diff {lbl}")
        base = team_dir / f"team_{lbl}".replace(":", "")
        fig.write_html(base.with_suffix(".html"))
        fig.write_image(base.with_suffix(".png"), scale=2)

    print(f"✔ Gold-difference plots saved to: {output_dir.resolve()}")


__all__ = ["generate_gold_diff"]
