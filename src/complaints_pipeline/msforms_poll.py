from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .form_mapping import normalize_fields
from .graph import (
    GraphApp,
    get_default_drive_id,
    get_site_id,
    get_token,
    session_with_retries,
    upload_file_put_content,
)
from .notify import send_mail_with_attachments
from .pdf_report import build_pdf_bytes
from .util import iso_date_parts, safe_filename, utc_ts


log = logging.getLogger("complaints_pipeline.msforms_poll")


# Columns MS Forms typically auto-add to the Excel table
SYSTEM_COLS = {"id", "start time", "completion time", "email", "name"}

# Your tracking column
PROCESSED_COL_CANDIDATES = {"processed", "is processed", "done"}


@dataclass(frozen=True)
class MsFormsExcelTarget:
    site_path: str            # e.g. /sites/ProjectManagementengineeringteam
    drive_name: str           # e.g. Shared Documents (not strictly needed if using default drive)
    file_path: str            # e.g. Complaints/Customer Complaint Form 1.xlsx
    table_name: str           # e.g. Table1


def _require(name: str, value: Optional[str]) -> str:
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def _encode_path(path: str) -> str:
    # Encode each segment safely for Graph /root:/{path}:
    parts = [p for p in path.split("/") if p]
    return "/".join(quote(p, safe="") for p in parts)


def _workbook_base(drive_id: str, file_path: str) -> str:
    p = _encode_path(file_path.strip("/"))
    return f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{p}:/workbook"


def _graph_get(token: str, url: str) -> Dict[str, Any]:
    s = session_with_retries()
    r = s.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    r.raise_for_status()
    return r.json()


def _graph_patch(token: str, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    s = session_with_retries()
    r = s.patch(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=60,
    )
    r.raise_for_status()
    return r.json() if r.text else {}


def _get_table_columns(token: str, wb_base: str, table_name: str) -> List[str]:
    # Returns column names in order
    url = f"{wb_base}/tables/{quote(table_name)}/columns?$top=200"
    data = _graph_get(token, url)
    cols = []
    for c in data.get("value", []):
        cols.append(str(c.get("name", "")))
    if not cols:
        raise RuntimeError(f"No columns found for table '{table_name}'.")
    return cols


def _get_table_rows(token: str, wb_base: str, table_name: str, top: int = 5000) -> List[Dict[str, Any]]:
    url = f"{wb_base}/tables/{quote(table_name)}/rows?$top={top}"
    data = _graph_get(token, url)
    return data.get("value", []) or []


def _update_row_values(token: str, wb_base: str, table_name: str, row_index: int, values: List[Any]) -> None:
    # Update a whole row via its range
    # Endpoint: .../rows/itemAt(index=...)/range
    url = f"{wb_base}/tables/{quote(table_name)}/rows/itemAt(index={row_index})/range"
    _graph_patch(token, url, {"values": [values]})


def _split_emails(s: str) -> List[str]:
    return [e.strip() for e in (s or "").split(",") if e.strip()]


def run_msforms_poll(backup_dir: str = "backups") -> int:
    ts = utc_ts()

    # Graph app auth
    tenant_id = _require("MS_TENANT_ID", os.getenv("MS_TENANT_ID"))
    client_id = _require("MS_CLIENT_ID", os.getenv("MS_CLIENT_ID"))
    client_secret = _require("MS_CLIENT_SECRET", os.getenv("MS_CLIENT_SECRET"))

    # SharePoint upload target (existing pipeline settings)
    sp_hostname = _require("SP_HOSTNAME", os.getenv("SP_HOSTNAME"))
    sp_site_path = _require("SP_SITE_PATH", os.getenv("SP_SITE_PATH"))
    sp_folder = _require("SP_FOLDER", os.getenv("SP_FOLDER"))

    # MS Forms Excel location
    msform_site_path = _require("MSFORM_SITE_PATH", os.getenv("MSFORM_SITE_PATH"))
    msform_drive_name = os.getenv("MSFORM_DRIVE_NAME", "Shared Documents").strip()
    msform_file_path = _require("MSFORM_FILE_PATH", os.getenv("MSFORM_FILE_PATH"))
    msform_table_name = _require("MSFORM_TABLE_NAME", os.getenv("MSFORM_TABLE_NAME"))

    # Email
    sender_upn = (os.getenv("MAIL_SENDER_UPN") or "").strip()
    notify_to = _split_emails(os.getenv("COMPLAINT_EMAIL_TO", os.getenv("BACKUP_EMAIL_TO", "")))

    app = GraphApp(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
    token = get_token(app)

    # Drive for uploads (where PDFs/JSON go)
    upload_site_id = get_site_id(token, sp_hostname, sp_site_path)
    upload_drive_id = get_default_drive_id(token, upload_site_id)

    # Drive for responses Excel (usually the same default drive; we keep msform_site_path separate anyway)
    forms_site_id = get_site_id(token, sp_hostname, msform_site_path)
    forms_drive_id = get_default_drive_id(token, forms_site_id)

    wb_base = _workbook_base(forms_drive_id, msform_file_path)

    cols = _get_table_columns(token, wb_base, msform_table_name)
    cols_norm = [c.strip().lower() for c in cols]

    # Find "Processed" column index
    processed_idx = None
    for i, c in enumerate(cols_norm):
        if c in PROCESSED_COL_CANDIDATES:
            processed_idx = i
            break
    if processed_idx is None:
        # exact match fallback
        for i, c in enumerate(cols_norm):
            if c == "processed":
                processed_idx = i
                break
    if processed_idx is None:
        raise RuntimeError("Could not find a 'Processed' column in the MS Forms table.")

    rows = _get_table_rows(token, wb_base, msform_table_name)

    out_dir = Path(backup_dir) / "msforms_submissions"
    out_dir.mkdir(parents=True, exist_ok=True)

    processed_count = 0

    for row in rows:
        row_index = int(row.get("index", -1))
        values = (row.get("values") or [[]])[0]
        if row_index < 0 or not isinstance(values, list) or not values:
            continue

        # Skip if already processed
        already = str(values[processed_idx]).strip().lower() if processed_idx < len(values) else ""
        if already in {"yes", "true", "1", "y", "done"}:
            continue

        # Build dict from columns -> values
        raw_row: Dict[str, Any] = {}
        for c_name, v in zip(cols, values):
            raw_row[c_name] = v

        # Pull some system fields we can use
        submission_id = str(raw_row.get("Id") or raw_row.get("id") or f"row-{row_index}")
        completion_time = str(raw_row.get("Completion time") or raw_row.get("completion time") or "")
        start_time = str(raw_row.get("Start time") or raw_row.get("start time") or "")
        timestamp = completion_time or start_time

        # Remove system columns and Processed column from the fields we map
        cleaned_fields: Dict[str, Any] = {}
        for k, v in raw_row.items():
            kn = str(k).strip().lower()
            if kn in SYSTEM_COLS:
                continue
            if kn in PROCESSED_COL_CANDIDATES:
                continue
            cleaned_fields[k] = v

        # Normalize to pipeline schema
        norm = normalize_fields(cleaned_fields)

        # If your MS Form doesn't have "date", set it from timestamp if possible
        if not norm.get("date") and timestamp:
            # keep as raw string (PDF just prints it). If you want strict formatting later, adjust here.
            norm["date"] = timestamp

        # Carry timestamp into system column
        if not norm.get("submission_timestamp") and timestamp:
            norm["submission_timestamp"] = timestamp

        # Build PDF
        pdf_bytes = build_pdf_bytes("Customer Complaint Form", norm)

        safe_id = safe_filename(f"MSF-{submission_id}")
        pdf_path = out_dir / f"complaint_{safe_id}.pdf"
        pdf_path.write_bytes(pdf_bytes)

        meta_path = out_dir / f"complaint_{safe_id}.json"
        meta_path.write_text(
            json.dumps(
                {
                    "source": "msforms_excel_poll",
                    "submission_id": submission_id,
                    "row_index": row_index,
                    "timestamp": timestamp,
                    "fields": norm,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        # Upload to SharePoint
        y, m, d = iso_date_parts(norm.get("submission_timestamp", "") or timestamp or "")
        remote_folder = f"{sp_folder}/Submissions/{y}/{m}/{d}"

        uploaded_pdf = upload_file_put_content(token, upload_drive_id, pdf_path, remote_folder, content_type="application/pdf")
        uploaded_json = upload_file_put_content(token, upload_drive_id, meta_path, remote_folder, content_type="application/json")

        # Email (optional)
        if sender_upn and notify_to:
            subject = f"New complaint submission: MSF-{submission_id}"
            body = "\n".join(
                [
                    "A new complaint was submitted via Microsoft Forms.",
                    f"Submission id: MSF-{submission_id}",
                    f"Timestamp: {timestamp}",
                    f"Uploaded PDF driveItem id: {uploaded_pdf.get('id', 'n/a')}",
                    f"Uploaded JSON driveItem id: {uploaded_json.get('id', 'n/a')}",
                ]
            )
            # Attach PDF + JSON locally
            send_mail_with_attachments(
                token=token,
                sender_upn=sender_upn,
                to_emails=notify_to,
                subject=subject,
                body_text=body,
                attachments=[pdf_path, meta_path],
            )

        # Mark row as processed
        if processed_idx < len(values):
            values[processed_idx] = "Yes"
        else:
            # pad if somehow shorter
            values.extend([""] * (processed_idx - len(values) + 1))
            values[processed_idx] = "Yes"

        _update_row_values(token, wb_base, msform_table_name, row_index, values)

        processed_count += 1
        log.info("Processed row index=%s submission_id=%s", row_index, submission_id)

    log.info("MS Forms poll finished. processed_count=%s", processed_count)
    return 0
