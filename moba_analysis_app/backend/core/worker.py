#!/usr/bin/env python3
"""
core/worker.py
==============

Asynchronous worker in charge of **Main-Game** analysis.

The worker receives extraction jobs through an `asyncio.Queue`, downloads the requested video frame, applies several computer‑vision analyses and merges the results into *game_state.json*.

Public helpers
--------------
ensure_worker_started() – idempotently launches the background task(s)
queue                  – shared `asyncio.Queue[Job]`
shutdown_workers()     – cancels the tasks (mainly for tests)
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Any, List, TypedDict

import cv2

from services.video.frame_extractor import async_extract_frame
from services.live_game_analysis.main_game.resources_tracker.bars.health_detection_service import (
    detect_health_bars,
)
from services.live_game_analysis.main_game.resources_tracker.bars.mana_detection_service import (
    detect_mana_bars,
)
from services.live_game_analysis.main_game.resources_tracker.stats.extract_stats_ocr_service import (
    process_main_hud_stats,
)
from services.live_game_analysis.game_state.game_state_service import update_game

# Paths ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
FRAMES_DIR = BASE_DIR / "frames"
FRAMES_DIR.mkdir(exist_ok=True)

# Types ---------------------------------------------------------------------
class Job(TypedDict):
    url: str
    time: float
    match: str

# Globals -------------------------------------------------------------------
queue: "asyncio.Queue[Job]" = asyncio.Queue()
_worker_tasks: List[asyncio.Task[Any]] = []

_DEFAULT_CONC = max(1, (os.cpu_count() or 2) - 1)

# Internal helpers ----------------------------------------------------------
async def _run_detectors(frame):
    h_t = asyncio.to_thread(detect_health_bars, frame)
    m_t = asyncio.to_thread(detect_mana_bars, frame)
    s_t = asyncio.to_thread(process_main_hud_stats, frame)
    return await asyncio.gather(h_t, m_t, s_t)

async def _worker_loop(idx: int) -> None:
    while True:
        job = await queue.get()
        url, t, match = job["url"], job["time"], job["match"]

        frame_hash = hashlib.md5(f"{url}|{t:.3f}".encode()).hexdigest()
        print(f"[{idx}] ▶ {match} @ {t:.2f}s → {frame_hash}.jpg")
        try:
            frame_path: Path = await async_extract_frame(url, t)
            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise RuntimeError("failed to read extracted frame")

            health, mana, stats = await _run_detectors(frame)

            if update_game(match, health, mana, stats):
                ts = stats.get("time", {}).get("parsed")
                print(f"[{idx}] ✔ snapshot added → {match} @ {ts}")
            else:
                print(f"[{idx}] ⏩ snapshot skipped (invalid timer)")
        except Exception as exc:  # pragma: no cover
            print(f"[{idx}] ❌ Worker error ({match}): {exc}")
        finally:
            queue.task_done()

# Public API ----------------------------------------------------------------
async def ensure_worker_started(concurrency: int | None = None) -> None:
    if _worker_tasks:
        return
    n = concurrency or int(os.getenv("WORKER_CONCURRENCY", _DEFAULT_CONC))
    n = max(1, n)
    loop = asyncio.get_running_loop()
    _worker_tasks.extend(loop.create_task(_worker_loop(i)) for i in range(n))
    print(f"Started {n} worker(s)")

async def shutdown_workers() -> None:
    for t in _worker_tasks:
        t.cancel()
    await asyncio.gather(*_worker_tasks, return_exceptions=True)
    _worker_tasks.clear()
