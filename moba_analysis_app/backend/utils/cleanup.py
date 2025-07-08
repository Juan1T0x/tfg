"""
utils.cleanup
=============

Utility invoked at application start-up to ensure the folder that
temporarily stores extracted video frames is empty.  It can also be run
manually:

    python -m utils.cleanup
"""
from __future__ import annotations

from pathlib import Path
import shutil

# Absolute path to backend/frames  (created by the worker)
FRAMES_DIR = Path(__file__).resolve().parents[1] / "frames"


def cleanup_frames() -> int:
    """
    Remove every file and directory inside :pydata:`FRAMES_DIR`.

    Returns
    -------
    int
        Number of entries successfully deleted.
    """
    if not FRAMES_DIR.exists():
        return 0

    deleted = 0
    for item in FRAMES_DIR.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            else:                                   # directory
                shutil.rmtree(item)
            deleted += 1
        except Exception as exc:
            # Keep going even if one entry cannot be removed.
            print(f"⚠️  unable to delete {item}: {exc}")

    return deleted


if __name__ == "__main__":
    print(f"frames deleted: {cleanup_frames()}")
