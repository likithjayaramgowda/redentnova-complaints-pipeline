from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Tuple


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def safe_filename(name: str, max_len: int = 120) -> str:
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "file"
    return name[:max_len]


def iso_date_parts(ts: str) -> Tuple[str, str, str]:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return (dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d"))
