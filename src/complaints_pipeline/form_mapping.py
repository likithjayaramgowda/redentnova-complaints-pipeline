from __future__ import annotations

from typing import Any, Dict

from .schema import QUESTION_MAP, SHEET_COLUMNS, normalize_question


def normalize_fields(raw_fields: Dict[str, Any]) -> Dict[str, Any]:
    """Map arbitrary form fields into normalized keys, preserving QAF schema keys.

    Apps Script already sends normalized keys, but this keeps Python robust if
    payload fields are still raw question titles.
    """
    out: Dict[str, Any] = {k: "" for k in SHEET_COLUMNS}

    for k, v in (raw_fields or {}).items():
        nk = normalize_question(str(k))
        mapped = QUESTION_MAP.get(nk)
        if mapped:
            out[mapped] = v
        elif k in out:
            out[k] = v

    # If someone sent a top-level 'timestamp' but not the system field
    if not out.get("submission_timestamp") and raw_fields.get("timestamp"):
        out["submission_timestamp"] = raw_fields["timestamp"]
    return out
