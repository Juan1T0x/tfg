#!/usr/bin/env python3
# services/data_analysis/data_visualization_generators/create_heatmaps.py
"""
create_heatmaps  –  servicio

Genera, para cada jugador y para cuatro ventanas temporales, las siguientes
representaciones sobre el mapa de la Grieta:

1. Heat-map transparente
2. Scatter coloreado por minuto
3. Trayectoria (path + puntos con minuto)
4. Heat-map arcoíris con **suavizado gaussiano**

Salida:
    <output_dir>/<jugador>/
        density_transparent/*.html|.png
        scatter_timestamp/*.html|.png
        path_timestamp/*.html|.png
        density_rainbow/*.html|.png
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import cv2  # suavizado gaussiano
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image

# ─────────────────────────── Rutas y constantes ─────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parents[3]                 # …/backend
_MAP_PATH    = _BACKEND_DIR / "assets" / "images" / "Summoners_Rift_Map.png"

MIN_X, MIN_Y = -120, -120
MAX_X, MAX_Y = 14_870, 14_980

BINS_RAINBOW   = 120   # menos bins ⇒ celdas mayores
GAUSS_SIGMA_PX = 5     # σ del blur gaussiano

ROLE_MAP = {
    "TOP": "top", "JUNGLE": "jungla", "MIDDLE": "mid",
    "BOTTOM": "bot", "UTILITY": "support",
}
WINDOWS = [
    (0, 14 * 60 * 1000, "00:00-14:00"),
    (14 * 60 * 1000, 25 * 60 * 1000, "14:00-25:00"),
    (25 * 60 * 1000, float("inf"),   "25:00-Fin"),
    (0, float("inf"),                "00:00-Fin"),
]

TRANSPARENT_SCALE = [
    [0.0, "rgba(0,0,0,0)"],
    [0.25, "rgba(63,81,181,0.4)"],
    [0.5, "rgba(103,169,207,0.6)"],
    [0.75, "rgba(244,109,67,0.8)"],
    [1.0, "rgba(255,0,0,1)"],
]
RAINBOW_SCALE = "Turbo"

# ─────────────────────────────── Helpers ────────────────────────────────
Coordinate = Tuple[float, float]
def _scale_to_pixels(x: int, y: int, w: int, h: int) -> Coordinate:
    return (
        (x - MIN_X) * w / (MAX_X - MIN_X),
        h - (y - MIN_Y) * h / (MAX_Y - MIN_Y),
    )


def _load_timeline(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_positions(tl: Dict) -> Dict[int, List[Dict]]:
    pos = {pid: [] for pid in range(1, 11)}
    for frame in tl["frames"]:
        ts = frame["timestamp"]
        for pf in frame["participantFrames"].values():
            if pf.get("position"):
                pos[pf["participantId"]].append(
                    {"t": ts,
                     "x": pf["position"]["x"],
                     "y": pf["position"]["y"]}
                )
    return pos


def _base_layout(fig, w: int, h: int, img):
    fig.update_layout(
        width=w, height=h,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[0, w], constrain="domain"),
        yaxis=dict(visible=False, range=[h, 0], scaleanchor="x", scaleratio=1),
    )
    fig.add_layout_image(
        dict(source=img, xref="x", yref="y",
             x=0, y=0, sizex=w, sizey=h,
             xanchor="left", yanchor="top",
             sizing="stretch", layer="below")
    )


# ───────────────────── generación de las cuatro figuras ─────────────────
def _make_figures(xs, ys, times_ms, title, w, h, img):
    # 1. heat-map transparente
    fig1 = px.density_heatmap(
        x=xs, y=ys, nbinsx=200, nbinsy=200,
        title=title, color_continuous_scale=TRANSPARENT_SCALE
    )
    _base_layout(fig1, w, h, img)

    # 2. scatter por minuto
    minutes = [round(t / 60000, 1) for t in times_ms]
    fig2 = px.scatter(
        x=xs, y=ys, title=f"{title} (puntos)",
        color=minutes, color_continuous_scale="Viridis",
        labels={"color": "min"},
        text=[f"{m:.1f}" for m in minutes],
    )
    _base_layout(fig2, w, h, img)
    fig2.update_traces(textposition="top center", textfont_size=8)

    # 3. trayectoria
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=xs, y=ys, mode="lines",
                              line=dict(color="white", width=1)))
    fig3.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text",
        marker=dict(size=6, color=minutes,
                    colorscale="Viridis", showscale=True),
        text=[f"{m:.1f}" for m in minutes],
        textposition="top center", textfont_size=8,
    ))
    fig3.update_layout(title=f"{title} (trayectoria)")
    _base_layout(fig3, w, h, img)

    # 4. heat-map arcoíris con blur
    z, xedges, yedges = np.histogram2d(
        xs, ys, bins=BINS_RAINBOW, range=[[0, w], [0, h]]
    )
    z = z.T
    if z.max() > 0:
        z = z / z.max()
        z = cv2.GaussianBlur(
            z.astype(np.float32),
            ksize=(0, 0),
            sigmaX=GAUSS_SIGMA_PX,
            sigmaY=GAUSS_SIGMA_PX,
            borderType=cv2.BORDER_REPLICATE,
        )
        z = z / z.max() if z.max() > 0 else z

    fig4 = go.Figure(go.Heatmap(
        z=z, x=xedges, y=yedges,
        colorscale=RAINBOW_SCALE, zsmooth="best",
        opacity=0.75, hoverinfo="skip",
        colorbar=dict(title="freq"),
    ))
    fig4.update_layout(title=f"{title} (arcoíris)")
    _base_layout(fig4, w, h, img)

    return fig1, fig2, fig3, fig4


# ───────────────────────────── API pública ──────────────────────────────
def generate_heatmaps(timeline_path: str | Path,
                       output_dir: str | Path) -> None:
    """
    Genera los cuatro tipos de visualización para cada jugador de `timeline_path`
    y los guarda en `output_dir`.

    Parámetros
    ----------
    timeline_path : str | Path
        Ruta al timeline JSON exportado por Riot.
    output_dir    : str | Path
        Carpeta donde se crearán las subcarpetas y los ficheros .html/.png.
    """
    timeline_path = Path(timeline_path)
    output_dir    = Path(output_dir)

    tl           = _load_timeline(timeline_path)
    participants = {p["participantId"]: p
                    for p in tl.get("participants", [])} or {
        pid: {"participantId": pid,
              "teamId": 100 if pid <= 5 else 200}
        for pid in range(1, 11)
    }

    img  = Image.open(_MAP_PATH)
    w, h = img.size

    positions = _collect_positions(tl)
    output_dir.mkdir(parents=True, exist_ok=True)

    for pid, samples in positions.items():
        meta = participants.get(pid, {})
        role = ROLE_MAP.get(
            meta.get("individualPosition") or meta.get("teamPosition"),
            f"p{pid}"
        )
        team = "azul" if meta.get("teamId", 100 if pid <= 5 else 200) == 100 else "rojo"
        name = meta.get("summonerName", f"Player{pid}")
        label_base = f"{name} ({role}), equipo {team}"

        player_dir = output_dir / name.replace(" ", "_")
        for sub in ["density_transparent", "scatter_timestamp",
                    "path_timestamp", "density_rainbow"]:
            (player_dir / sub).mkdir(parents=True, exist_ok=True)

        for start_ms, end_ms, label in WINDOWS:
            subset = [s for s in samples if start_ms <= s["t"] < end_ms]
            if not subset:
                continue

            xs, ys = zip(*[
                _scale_to_pixels(s["x"], s["y"], w, h) for s in subset
            ])
            times = [s["t"] for s in subset]

            figs = _make_figures(
                list(xs), list(ys), times,
                title=f"{label_base} — {label}",
                w=w, h=h, img=img
            )
            for fig, sub in zip(
                figs,
                ["density_transparent", "scatter_timestamp",
                 "path_timestamp", "density_rainbow"],
            ):
                base = (output_dir / name.replace(" ", "_") / sub /
                        f"{role}_{label}".replace(":", ""))
                fig.write_html(base.with_suffix(".html"))
                fig.write_image(base.with_suffix(".png"), scale=2)

    print(f"✔ Heat-maps guardados en: {output_dir.resolve()}")

# Exporte explícito
__all__ = ["generate_heatmaps"]
