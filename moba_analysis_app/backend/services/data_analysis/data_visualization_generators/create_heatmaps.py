#!/usr/bin/env python3
# services/data_analysis/data_visualization_generators/create_heatmaps.py
"""
Heat-maps and movement plots for Summoner’s Rift matches
=======================================================

For every participant in a *timeline.json* file this module creates, for four
time-windows, the following visualisations on top of a Summoner’s Rift map:

1. **Density heat-map** ­– transparent colours, useful as an overlay.
2. **Scatter plot** coloured by minute marks.
3. **Path plot** – trajectory plus minute labels.
4. **Rainbow heat-map** with Gaussian smoothing.

Directory layout
----------------
Every match has its own folder inside *backend/matches_history/*:

    matches_history/
        <match_slug>/
            results/
                cs_diff/      … PNG files
                cs_total/     … PNG files
                gold_diff/    … PNG files
                heat_maps/    … PNG files

The **static router** in *main.py* exposes that tree under
``http://<host>:<port>/results``.  Public URLs therefore follow the pattern:

    http://localhost:8888/results/<match_slug>/<category>/<subdirs…>/<file>.png
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple, Any

import json

import cv2                          # only for Gaussian blur
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image

# --------------------------------------------------------------------------- #
# Data & asset paths
# --------------------------------------------------------------------------- #
_BACKEND_DIR: Path = Path(__file__).resolve().parents[3]           # …/backend
_MAP_PATH: Path = _BACKEND_DIR / "assets" / "images" / "Summoners_Rift_Map.png"

# Raw map coordinates in Riot’s timeline files
_MIN_X, _MIN_Y = -120, -120
_MAX_X, _MAX_Y = 14_870, 14_980

# Heat-map configuration
_BINS_RAINBOW:   int = 120          # lower → bigger cells
_GAUSS_SIGMA_PX: int = 5            # σ for the Gaussian blur (in pixels)

# Riot roles → human-friendly labels for filenames
_ROLE_MAP = {
    "TOP": "top",
    "JUNGLE": "jungla",
    "MIDDLE": "mid",
    "BOTTOM": "bot",
    "UTILITY": "support",
}

# Time windows (start-ms, end-ms, label)
_WINDOWS: list[Tuple[int, float, str]] = [
    (0,              14 * 60 * 1000, "00:00-14:00"),
    (14 * 60 * 1000, 25 * 60 * 1000, "14:00-25:00"),
    (25 * 60 * 1000, float("inf"),   "25:00-Fin"),
    (0,              float("inf"),   "00:00-Fin"),
]

# Colours
_TRANSPARENT_SCALE = [
    [0.00, "rgba(0,0,0,0)"],
    [0.25, "rgba(63,81,181,0.4)"],
    [0.50, "rgba(103,169,207,0.6)"],
    [0.75, "rgba(244,109,67,0.8)"],
    [1.00, "rgba(255,0,0,1)"],
]
_RAINBOW_SCALE = "Turbo"

# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
Coordinate = Tuple[float, float]


def _timeline_json(path: Path) -> Dict[str, Any]:
    """Load *time_line.json*."""
    return json.loads(path.read_text(encoding="utf-8"))


def _positions_by_participant(tl: Dict[str, Any]) -> Dict[int, List[Dict[str, int]]]:
    """
    Extract the (x, y) positions of each participant across the whole timeline.

    Returns
    -------
    Dict[int, List[Dict[str, int]]]
        {participantId: [{t, x, y}, …], …}
    """
    positions: Dict[int, List[Dict[str, int]]] = {pid: [] for pid in range(1, 11)}

    for frame in tl["frames"]:
        ts = frame["timestamp"]
        for pf in frame["participantFrames"].values():
            pos = pf.get("position")
            if pos:
                positions[pf["participantId"]].append(
                    {"t": ts, "x": pos["x"], "y": pos["y"]}
                )
    return positions


def _map_to_pixels(x: int, y: int, w: int, h: int) -> Coordinate:
    """Convert in-game map coordinates to image-pixel coordinates."""
    return (
        (x - _MIN_X) * w / (_MAX_X - _MIN_X),
        h - (y - _MIN_Y) * h / (_MAX_Y - _MIN_Y),
    )


def _add_base_layout(fig: go.Figure, w: int, h: int, img: Image.Image) -> None:
    """Shared Plotly layout with the background Summoner’s Rift map."""
    fig.update_layout(
        width=w,
        height=h,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[0, w], constrain="domain"),
        yaxis=dict(visible=False, range=[h, 0], scaleanchor="x", scaleratio=1),
    )
    fig.add_layout_image(
        dict(
            source=img,
            xref="x",
            yref="y",
            x=0,
            y=0,
            sizex=w,
            sizey=h,
            xanchor="left",
            yanchor="top",
            sizing="stretch",
            layer="below",
        )
    )


# --------------------------------------------------------------------------- #
# Figure builders
# --------------------------------------------------------------------------- #
def _build_figures(
    xs: List[float],
    ys: List[float],
    times_ms: List[int],
    title: str,
    w: int,
    h: int,
    img: Image.Image,
) -> Tuple[go.Figure, go.Figure, go.Figure, go.Figure]:
    """Create the four figures for a single player & window."""
    # 1) Transparent density heat-map
    fig1 = px.density_heatmap(
        x=xs,
        y=ys,
        nbinsx=200,
        nbinsy=200,
        title=title,
        color_continuous_scale=_TRANSPARENT_SCALE,
    )
    _add_base_layout(fig1, w, h, img)

    # 2) Scatter-timestamp
    minutes = [round(t / 60_000, 1) for t in times_ms]
    fig2 = px.scatter(
        x=xs,
        y=ys,
        title=f"{title} (puntos)",
        color=minutes,
        color_continuous_scale="Viridis",
        labels={"color": "min"},
        text=[f"{m:.1f}" for m in minutes],
    )
    _add_base_layout(fig2, w, h, img)
    fig2.update_traces(textposition="top center", textfont_size=8)

    # 3) Path-timestamp
    fig3 = go.Figure()
    fig3.add_trace(
        go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="white", width=1))
    )
    fig3.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text",
            marker=dict(size=6, color=minutes, colorscale="Viridis", showscale=True),
            text=[f"{m:.1f}" for m in minutes],
            textposition="top center",
            textfont_size=8,
        )
    )
    fig3.update_layout(title=f"{title} (trayectoria)")
    _add_base_layout(fig3, w, h, img)

    # 4) Rainbow density heat-map (Gaussian blur)
    z, xedges, yedges = np.histogram2d(xs, ys, bins=_BINS_RAINBOW, range=[[0, w], [0, h]])
    z = z.T

    if z.max() > 0:  # normalise and smooth
        z = (z / z.max()).astype(np.float32)
        z = cv2.GaussianBlur(
            z,
            ksize=(0, 0),
            sigmaX=_GAUSS_SIGMA_PX,
            sigmaY=_GAUSS_SIGMA_PX,
            borderType=cv2.BORDER_REPLICATE,
        )
        z = z / z.max() if z.max() > 0 else z

    fig4 = go.Figure(
        go.Heatmap(
            z=z,
            x=xedges,
            y=yedges,
            colorscale=_RAINBOW_SCALE,
            zsmooth="best",
            opacity=0.75,
            hoverinfo="skip",
            colorbar=dict(title="freq"),
        )
    )
    fig4.update_layout(title=f"{title} (arcoíris)")
    _add_base_layout(fig4, w, h, img)

    return fig1, fig2, fig3, fig4


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_heatmaps(timeline_path: str | Path, output_dir: str | Path) -> None:
    """
    Generate heat-maps and movement plots for each participant.

    Parameters
    ----------
    timeline_path
        Path to *time_line.json*.
    output_dir
        Destination directory. Sub-folders are created automatically.

    The function writes both *.html* and *.png* versions of every figure.
    """
    timeline_path = Path(timeline_path)
    output_dir = Path(output_dir)

    tl = _timeline_json(timeline_path)

    # Participants metadata may be absent in custom timelines
    participants = {
        p.get("participantId"): p for p in tl.get("participants", [])
    } or {
        pid: {"participantId": pid, "teamId": 100 if pid <= 5 else 200}
        for pid in range(1, 11)
    }

    img = Image.open(_MAP_PATH)
    w, h = img.size

    positions = _positions_by_participant(tl)
    output_dir.mkdir(parents=True, exist_ok=True)

    for pid, samples in positions.items():
        meta = participants.get(pid, {})
        role = _ROLE_MAP.get(
            meta.get("individualPosition") or meta.get("teamPosition"),
            f"p{pid}",
        )
        team = "azul" if meta.get("teamId", 100 if pid <= 5 else 200) == 100 else "rojo"
        summoner = meta.get("summonerName", f"Player{pid}")
        label_prefix = f"{summoner} ({role}), equipo {team}"

        player_dir = output_dir / summoner.replace(" ", "_")
        for sub in (
            "density_transparent",
            "scatter_timestamp",
            "path_timestamp",
            "density_rainbow",
        ):
            (player_dir / sub).mkdir(parents=True, exist_ok=True)

        for start_ms, end_ms, window_label in _WINDOWS:
            subset = [s for s in samples if start_ms <= s["t"] < end_ms]
            if not subset:
                continue

            xs_px, ys_px = zip(
                *(_map_to_pixels(s["x"], s["y"], w, h) for s in subset)
            )
            times_ms = [s["t"] for s in subset]

            figs = _build_figures(
                list(xs_px),
                list(ys_px),
                times_ms,
                title=f"{label_prefix} — {window_label}",
                w=w,
                h=h,
                img=img,
            )

            for fig, sub in zip(
                figs,
                (
                    "density_transparent",
                    "scatter_timestamp",
                    "path_timestamp",
                    "density_rainbow",
                ),
            ):
                base = (
                    player_dir
                    / sub
                    / f"{role}_{window_label}".replace(":", "")
                )
                fig.write_html(base.with_suffix(".html"))
                fig.write_image(base.with_suffix(".png"), scale=2)

    print(f"✔ Heat-maps saved under {output_dir.resolve()}")


# --------------------------------------------------------------------------- #
# CLI helper
# --------------------------------------------------------------------------- #
if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Generate heat-maps for a timeline.")
    parser.add_argument("timeline", type=Path, help="Path to time_line.json")
    parser.add_argument("out_dir", type=Path, help="Output directory")
    args = parser.parse_args()

    generate_heatmaps(args.timeline, args.out_dir)


__all__ = ["generate_heatmaps"]