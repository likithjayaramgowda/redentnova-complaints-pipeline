from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from .schema import SHEET_COLUMNS
from .sheets import read_all_complaints


def backup_to_csv(ws, out_dir: str, *, strict_header: bool = True) -> Path:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    csv_path = Path(out_dir) / f"complaints_backup_utc_{ts}.csv"

    rows = read_all_complaints(ws, strict_header=strict_header)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in SHEET_COLUMNS})

    return csv_path
