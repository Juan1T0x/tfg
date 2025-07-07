#!/usr/bin/env python3
"""
parse_ranking_log_to_excel.py

Convierte matching_ranking.log → ranking.xlsx
Columnas de salida:
    fuente | estrategia | detector | top1 | tiempo(s)
"""
import re
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------
LOG_PATH   = Path("results") / "matching_ranking.log"
EXCEL_PATH = Path("results") / "ranking.xlsx"

# Expresión regular para las líneas del log:
#  1. splash_arts | resize_bbox_only | SIFT: 9,9, 165.679
LINE_RE = re.compile(
    r"""
    ^\s*\d+\.\s*                     # índice (1.)
    (?P<fuente>[^|]+)\s*\|\s*        # fuente
    (?P<estrategia>[^|]+)\s*\|\s*    # estrategia
    (?P<detector>[^:]+):\s*          # detector
    (?P<top1>\d+),\d+,\s*            # top1  (top5 se ignora)
    (?P<tiempo>[0-9.]+)              # tiempo
    """,
    re.VERBOSE,
)

records = []
with LOG_PATH.open(encoding="utf-8") as fh:
    for line in fh:
        m = LINE_RE.match(line)
        if m:
            records.append(
                {
                    "fuente":      m.group("fuente").strip(),
                    "estrategia":  m.group("estrategia").strip(),
                    "detector":    m.group("detector").strip(),
                    "top1":        int(m.group("top1")),
                    "tiempo(s)":   float(m.group("tiempo")),
                }
            )

if not records:
    raise RuntimeError("No se encontraron entradas válidas en el log.")

df = pd.DataFrame(records)
df.to_excel(EXCEL_PATH, index=False)
print(f"✔ Exportado a: {EXCEL_PATH.resolve()}")
