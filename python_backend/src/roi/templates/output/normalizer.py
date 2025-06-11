#!/usr/bin/env python3
# normalize_rois.py

"""
Normaliza todos los ROIs de un JSON: para cada polígono toma el
bounding‐box mínimo y lo convierte en un rectángulo de cuatro vértices.

Uso:
    python normalize_rois.py \
        --in   path/to/main_overlay_rois.json \
        --out  path/to/main_overlay_rois_normalized.json
"""

import json
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any

Coordinate = Tuple[int,int]
Template   = Dict[str, Any]

def bounding_rectangle(pts: List[Coordinate]) -> List[Coordinate]:
    """Dado un polígono ptos, devuelve [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

def normalize_template(tpl: Template) -> Template:
    out: Template = {}
    # Copiamos reference_size si existe
    if "reference_size" in tpl:
        out["reference_size"] = tpl["reference_size"]
    # Para cada ROI, calculamos su bounding rectangle
    for key, val in tpl.items():
        if key == "reference_size":
            continue
        # asumimos val es lista de [x,y]
        pts = [(int(x), int(y)) for x,y in val]
        out[key] = bounding_rectangle(pts)
    return out

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in",  dest="input",  required=True, help="JSON de entrada")
    p.add_argument("--out", dest="output", required=True, help="JSON de salida")
    args = p.parse_args()

    inp  = Path(args.input)
    outp = Path(args.output)

    tpl = json.loads(inp.read_text(encoding="utf-8"))
    norm_tpl = normalize_template(tpl)

    outp.parent.mkdir(exist_ok=True, parents=True)
    outp.write_text(json.dumps(norm_tpl, indent=4), encoding="utf-8")
    print(f"✓ Plantilla normalizada guardada en {outp}")

if __name__ == "__main__":
    main()
