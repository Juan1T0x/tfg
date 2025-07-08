#!/usr/bin/env python3
from __future__ import annotations

import asyncio, hashlib
from pathlib import Path
from typing import Any, TypedDict

import cv2
from services.video.frame_extractor import async_extract_frame
from services.live_game_analysis.main_game.resources_tracker.bars.health_detection_service import detect_health_bars
from services.live_game_analysis.main_game.resources_tracker.bars.mana_detection_service import detect_mana_bars
from services.live_game_analysis.main_game.resources_tracker.stats.extract_stats_ocr_service import process_main_hud_stats
from services.live_game_analysis.game_state.game_state_service import update_game

BASE_DIR = Path(__file__).resolve().parents[1]
FRAMES_DIR = BASE_DIR / "frames"
FRAMES_DIR.mkdir(exist_ok=True)


class Job(TypedDict):
    url: str
    time: float
    match: str


queue: "asyncio.Queue[Job]" = asyncio.Queue()
_worker_task: asyncio.Task[Any] | None = None


async def _worker_loop() -> None:
    while True:
        job = await queue.get()
        url, t, match = job["url"], job["time"], job["match"]
        frame_hash = hashlib.md5(f"{url}|{t:.3f}".encode()).hexdigest()
        print(f"▶ [{match}] extracting {url} @ {t:.2f}s → {frame_hash}.jpg")
        try:
            frame_path: Path = await async_extract_frame(url, t)
            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise RuntimeError("Failed to read extracted frame")
            health = detect_health_bars(frame)
            mana = detect_mana_bars(frame)
            stats = process_main_hud_stats(frame)
            if update_game(match, health, mana, stats):
                print(f"✔ snapshot added → {match} @ {stats.get('time',{}).get('parsed')}")
            else:
                print("⏩ snapshot skipped (no valid timer)")
        except Exception as exc:
            print(f"❌ Worker error ({match}): {exc}")
        finally:
            queue.task_done()


async def ensure_worker_started() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())
