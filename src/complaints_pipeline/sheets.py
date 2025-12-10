from __future__ import annotations

from typing import Dict, List

from .schema import SHEET_COLUMNS

DEFAULT_WORKSHEET = "Complaints"


def auth_sheets(service_account_json_path: str):
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(service_account_json_path, scopes=scopes)
    return gspread.authorize(creds)


def open_spreadsheet(gc, sheet_id: str):
    return gc.open_by_key(sheet_id)


def get_or_create_worksheet(sh, worksheet_name: str = DEFAULT_WORKSHEET):
    try:
        return sh.worksheet(worksheet_name)
    except Exception:
        # Create with a reasonable default column count
        ws = sh.add_worksheet(title=worksheet_name, rows=2000, cols=max(30, len(SHEET_COLUMNS) + 5))
        return ws


def ensure_header(ws, *, strict: bool = True) -> None:
    """Ensure header exists and matches expected QAF schema order.

    - If empty sheet: writes SHEET_COLUMNS as header.
    - If non-empty:
        - strict=True: raise if mismatch
        - strict=False: do nothing (best-effort)
    """
    header = ws.row_values(1)

    if not header or all(not str(x).strip() for x in header):
        ws.update("A1", [SHEET_COLUMNS])
        return

    expected = SHEET_COLUMNS
    got = [str(x).strip() for x in header[: len(expected)]]
    if got != expected and strict:
        raise RuntimeError(
            "Worksheet header does not match expected QAF schema. "
            f"Expected first {len(expected)} columns: {expected}. Got: {got}."
        )


def read_all_complaints(ws, *, strict_header: bool = True) -> List[Dict]:
    ensure_header(ws, strict=strict_header)
    return ws.get_all_records(expected_headers=SHEET_COLUMNS)
