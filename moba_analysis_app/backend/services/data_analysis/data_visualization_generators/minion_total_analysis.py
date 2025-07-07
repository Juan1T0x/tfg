from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import plotly.graph_objects as go

_WINDOWS: list[tuple[int, int, str]] = [
    (0, 14 * 60_000, "00:00-14:00"),
    (14 * 60_000, 25 * 60_000, "14:00-25:00"),
    (25 * 60_000, float("inf"), "25:00-Fin"),
    (0, float("inf"), "00:00-Fin"),
]

_PAIR_IDS: list[tuple[int, int, str]] = [
    (1, 6, "p1_vs_p6"),
    (2, 7, "p2_vs_p7"),
    (3, 8, "p3_vs_p8"),
    (4, 9, "p4_vs_p9"),
    (5, 10, "p5_vs_p10"),
]

_METRICS: dict[str, str] = {
    "minions": "minionsKilled",
    "jungleMinions": "jungleMinionsKilled",
}

_COLORS = {"blue": "royalblue", "red": "firebrick"}


def _load_timeline(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pair_series(frames: List[Dict], blue: int, red: int, field: str) -> Tuple[List[float], List[float], List[float]]:
    xs, ys_b, ys_r = [], [], []
    for f in frames:
        t = f["timestamp"] / 60_000
        pb, pr = f["participantFrames"].get(str(blue)), f["participantFrames"].get(str(red))
        if pb and pr:
            xs.append(t)
            ys_b.append(pb[field])
            ys_r.append(pr[field])
    return xs, ys_b, ys_r


def _team_series(frames: List[Dict], field: str) -> Tuple[List[float], List[float], List[float]]:
    xs, ys_b, ys_r = [], [], []
    for f in frames:
        t = f["timestamp"] / 60_000
        blue = sum(p[field] for pid, p in f["participantFrames"].items() if int(pid) <= 5)
        red = sum(p[field] for pid, p in f["participantFrames"].items() if int(pid) > 5)
        xs.append(t)
        ys_b.append(blue)
        ys_r.append(red)
    return xs, ys_b, ys_r


def _crop(xs: List[float], b: List[float], r: List[float], start: int, end: int) -> Tuple[List[float], List[float], List[float]]:
    if not xs:
        return [], [], []
    s, e = start / 60_000, (end / 60_000 if end != float("inf") else float("inf"))
    sub = [(x, yb, yr) for x, yb, yr in zip(xs, b, r) if s <= x < e]
    if not sub:
        return [], [], []
    xs2, b2, r2 = zip(*sub)
    return list(xs2), list(b2), list(r2)


def _figure(xs: List[float], b: List[float], r: List[float], title: str, ylabel: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=b, mode="lines", name="Azul", line=dict(color=_COLORS["blue"])))
    fig.add_trace(go.Scatter(x=xs, y=r, mode="lines", name="Rojo", line=dict(color=_COLORS["red"])))
    fig.update_layout(
        title=title,
        xaxis_title="Minuto",
        yaxis_title=ylabel,
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.98),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig


def generate_minion_total(timeline_path: str | Path, output_dir: str | Path = "cs_total") -> None:
    timeline_path = Path(timeline_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tl = _load_timeline(timeline_path)
    frames = tl["frames"]

    pair_dirs = {
        tag: {m: output_dir / tag / m for m in _METRICS} for *_, tag in _PAIR_IDS
    }
    for dmap in pair_dirs.values():
        for d in dmap.values():
            d.mkdir(parents=True, exist_ok=True)

    team_dirs = {m: output_dir / "team" / m for m in _METRICS}
    for d in team_dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    for blue, red, tag in _PAIR_IDS:
        for mkey, field in _METRICS.items():
            xs_all, b_all, r_all = _pair_series(frames, blue, red, field)
            if not xs_all:
                continue
            for start, end, lbl in _WINDOWS:
                xs, b, r = _crop(xs_all, b_all, r_all, start, end)
                if not xs:
                    continue
                fig = _figure(xs, b, r, f"{tag} – {mkey} {lbl}", f"{mkey} acumulados")
                base = pair_dirs[tag][mkey] / f"{tag}_{mkey}_{lbl}".replace(":", "")
                fig.write_html(base.with_suffix(".html"))
                fig.write_image(base.with_suffix(".png"), scale=2)

    for mkey, field in _METRICS.items():
        xs_all, b_all, r_all = _team_series(frames, field)
        for start, end, lbl in _WINDOWS:
            xs, b, r = _crop(xs_all, b_all, r_all, start, end)
            if not xs:
                continue
            fig = _figure(xs, b, r, f"Equipo – {mkey} {lbl}", f"{mkey} acumulados")
            base = team_dirs[mkey] / f"team_{mkey}_{lbl}".replace(":", "")
            fig.write_html(base.with_suffix(".html"))
            fig.write_image(base.with_suffix(".png"), scale=2)

    print(f"Gráficas CS total generadas en: {output_dir.resolve()}")


__all__ = ["generate_minion_total"]
