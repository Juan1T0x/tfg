from __future__ import annotations

from pathlib import Path
import traceback

from services.data_analysis.data_visualization_generators import (
    gold_diff_analysis    as _gold,
    minion_diff_analysis  as _cs_diff,
    minion_total_analysis as _cs_total,
    create_heatmaps       as _heatmaps,
)


def _run_safe(label: str, fn, *, timeline_path: Path, output_dir: Path,
              errors: list[str]) -> None:
    """
    Ejecuta `fn` atrapando cualquier excepción.
    Si algo falla, se registra en `errors` y continúa la ejecución.
    """
    try:
        fn(timeline_path=timeline_path, output_dir=output_dir)
    except Exception as exc:                               # pragma: no cover
        traceback.print_exc()
        errors.append(f"[{label}] {exc}")


def generar_analisis_timeline(carpeta_timeline: str | Path) -> None:
    """
    Genera todas las visualizaciones a partir de la carpeta que contiene
    `time_line.json`.

    El directorio de salida será `<carpeta_timeline>/results`.

    En caso de que alguno de los sub-servicios falle, el error se muestra por
    pantalla, se continúa con los demás y al final se imprime un resumen.
    """
    carpeta = Path(carpeta_timeline).expanduser().resolve()
    if not carpeta.is_dir():
        raise NotADirectoryError(carpeta)

    tl_path = carpeta / "time_line.json"
    if not tl_path.is_file():
        raise FileNotFoundError(f"No se encontró {tl_path}")

    out_root = carpeta / "results"
    out_root.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []

    _run_safe("gold_diff",   _gold.generate_gold_diff,
              timeline_path=tl_path, output_dir=out_root / "gold_diff",
              errors=errors)

    _run_safe("minion_diff", _cs_diff.generate_minion_diff,
              timeline_path=tl_path, output_dir=out_root / "cs_diff",
              errors=errors)

    _run_safe("minion_total", _cs_total.generate_minion_total,
              timeline_path=tl_path, output_dir=out_root / "cs_total",
              errors=errors)

    _run_safe("heat_maps",   _heatmaps.generate_heatmaps,
              timeline_path=tl_path, output_dir=out_root / "heat_maps",
              errors=errors)

    print(f"✔ Análisis completo en: {out_root.resolve()}")

    if errors:
        print("\n⚠ Se produjeron errores en algunos generadores:")
        for err in errors:
            print("   •", err)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Servicio principal: genera todas las gráficas de una carpeta de timeline."
    )
    parser.add_argument("carpeta", type=Path, help="Carpeta que contiene time_line.json")
    args = parser.parse_args()

    generar_analisis_timeline(args.carpeta)
