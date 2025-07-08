from __future__ import annotations

"""
services/data_analysis/run_timeline_analysis.py
==============================================

Entry-point that builds every data-analysis chart from a single
*time_line.json* folder.

It is merely a thin orchestrator: each chart type lives in its own module
inside ``services.data_analysis.data_visualization_generators``.  
If one of those generators raises, the error is logged but the remaining
tasks continue.

CLI
---
$ python -m services.data_analysis.run_timeline_analysis <match_dir>

where *<match_dir>* is a folder that contains a **time_line.json** file.

Output
------
All artefacts are written under:

    <match_dir>/results/
        ├── cs_diff/
        ├── cs_total/
        ├── gold_diff/
        └── heat_maps/

A final summary is printed to *stdout*.
"""

from pathlib import Path
import traceback
from typing import Callable, List

# ----------------------------------------------------------------------
# individual generators
# ----------------------------------------------------------------------
from services.data_analysis.data_visualization_generators import (
    gold_diff_analysis    as _gold,
    minion_diff_analysis  as _cs_diff,
    minion_total_analysis as _cs_total,
    create_heatmaps       as _heatmaps,
)


def _run_safe(                                        # noqa: D401
    label: str,
    fn: Callable[..., None],
    *,
    timeline_path: Path,
    output_dir: Path,
    errors: List[str],
) -> None:
    """
    Execute *fn* trapping any exception and collecting an error message.

    Parameters
    ----------
    label
        Human-readable tag of the generator (used in log messages).
    fn
        The generator function to call.
    timeline_path
        Absolute path to *time_line.json*.
    output_dir
        Where the generator should write its artefacts.
    errors
        Shared list where errors are appended; not modified if the
        generator succeeds.
    """
    try:
        fn(timeline_path=timeline_path, output_dir=output_dir)
    except Exception as exc:                           # pragma: no cover
        traceback.print_exc()
        errors.append(f"[{label}] {exc}")


# ----------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------
def generar_analisis_timeline(match_folder: str | Path) -> None:
    """
    Build **every** chart type for the given match folder.

    Parameters
    ----------
    match_folder
        Directory that contains ``time_line.json`` for a single match.

    Raises
    ------
    FileNotFoundError
        If *time_line.json* is missing.
    NotADirectoryError
        If *match_folder* is not a directory.

    Notes
    -----
    * A ``results`` directory is created next to the JSON file.
    * After finishing a concise report is printed; failed generators are
      listed individually.
    """
    match_path = Path(match_folder).expanduser().resolve()

    if not match_path.is_dir():
        raise NotADirectoryError(match_path)

    tl_path = match_path / "time_line.json"
    if not tl_path.is_file():
        raise FileNotFoundError(tl_path)

    out_root = match_path / "results"
    out_root.mkdir(parents=True, exist_ok=True)

    errors: List[str] = []

    _run_safe(
        "gold_diff",
        _gold.generate_gold_diff,
        timeline_path=tl_path,
        output_dir=out_root / "gold_diff",
        errors=errors,
    )

    _run_safe(
        "minion_diff",
        _cs_diff.generate_minion_diff,
        timeline_path=tl_path,
        output_dir=out_root / "cs_diff",
        errors=errors,
    )

    _run_safe(
        "minion_total",
        _cs_total.generate_minion_total,
        timeline_path=tl_path,
        output_dir=out_root / "cs_total",
        errors=errors,
    )

    _run_safe(
        "heat_maps",
        _heatmaps.generate_heatmaps,
        timeline_path=tl_path,
        output_dir=out_root / "heat_maps",
        errors=errors,
    )

    print(f"✔ Analysis finished → {out_root.resolve()}")

    if errors:
        print("\n⚠ Some generators failed:")
        for err in errors:
            print(f"   • {err}")


# ----------------------------------------------------------------------
# CLI helper
# ----------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate every data-analysis chart for a match folder."
    )
    parser.add_argument(
        "match_dir",
        type=Path,
        help="Directory that contains time_line.json",
    )
    opts = parser.parse_args()

    generar_analisis_timeline(opts.match_dir)
