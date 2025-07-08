#!/usr/bin/env python3
"""
core/worker.py
==============

Asynchronous worker in charge of **Main-Game** analysis.

The worker continually receives extraction jobs through an `asyncio.Queue`,
downloads the requested video frame, applies several computer-vision analyses
(health bars, mana bars, HUD OCR) and merges the results into the persistent
*game_state.json* of the corresponding match.

Public helpers
--------------
ensure_worker_started()      –  idempotently launches the background task
queue                        –  `asyncio.Queue[Job]` used by the API layer

Typical flow
------------
1.  `processMainGame` endpoint pushes a `Job` into `queue`.
2.  The `_worker_loop` coroutine pulls the job, downloads the frame and runs
    the detectors.
3.  Parsed data are forwarded to `game_state_service.update_game`, which
    decides whether a new snapshot should be stored.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any, TypedDict

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

# ---------------------------------------------------------------------------–
# Paths
# ---------------------------------------------------------------------------–
BASE_DIR   = Path(__file__).resolve().parents[1]          # …/backend
FRAMES_DIR = BASE_DIR / "frames"                         # temporary JPGs
FRAMES_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------–
# Types
# ---------------------------------------------------------------------------–
class Job(TypedDict):
    """Unit of work sent by the API to the worker queue."""
    url:   str   # full YouTube URL
    time:  float # timestamp (s) for the frame to extract
    match: str   # match title – used as key for game_state.json


# ---------------------------------------------------------------------------–
# Runtime globals
# ---------------------------------------------------------------------------–
queue: "asyncio.Queue[Job]" = asyncio.Queue()
_worker_task: asyncio.Task[Any] | None = None

# ---------------------------------------------------------------------------–
# Internal helpers
# ---------------------------------------------------------------------------–
async def _worker_loop() -> None:
    """
    Endless loop that processes extraction jobs one at a time.

    Every iteration:
    1. Pull job from `queue`.
    2. Extract (or reuse) the frame and load it into memory.
    3. Run the three CV modules.
    4. Try to insert a snapshot – `update_game` silently drops it if the
       in-game timer could not be parsed.
    5. Always mark the task as done so that `queue.join()` works correctly.
    """
    while True:
        job = await queue.get()
        url, t, match = job["url"], job["time"], job["match"]

        # Deterministic filename for the extracted frame – handy for caching.
        frame_hash = hashlib.md5(f"{url}|{t:.3f}".encode()).hexdigest()
        print(f"▶ [{match}] extracting {url} @ {t:.2f}s → {frame_hash}.jpg")

        try:
            # --- 1. download / cache -------------------------------------------------
            frame_path: Path = await async_extract_frame(url, t)

            # --- 2. load -------------------------------------------------------------
            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise RuntimeError("failed to read extracted frame")

            # --- 3. analyse ----------------------------------------------------------
            health = detect_health_bars(frame)
            mana   = detect_mana_bars(frame)
            stats  = process_main_hud_stats(frame)

            # --- 4. persist ----------------------------------------------------------
            if update_game(match, health, mana, stats):
                ts = stats.get("time", {}).get("parsed")
                print(f"✔ snapshot added → {match} @ {ts}")
            else:
                print("⏩ snapshot skipped (invalid or missing timer)")

        except Exception as exc:                      # pragma: no cover
            # Any unexpected error is logged but does *not* stop the loop.
            print(f"❌ Worker error ({match}): {exc}")

        finally:
            queue.task_done()

# ---------------------------------------------------------------------------–
# Public API
# ---------------------------------------------------------------------------–
async def ensure_worker_started() -> None:
    """
    Launch the background worker once; safe to call multiple times.

    The reference to the running task is kept in `_worker_task` so that only
    one instance of the loop exists per process.
    """
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())

