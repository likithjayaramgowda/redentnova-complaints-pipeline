from __future__ import annotations
from .msforms_poll import run_msforms_poll

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .backup import backup_to_csv
from .dispatch_payload import parse_submission
from .form_mapping import normalize_fields
from .graph import GraphApp, get_default_drive_id, get_site_id, get_token, upload_file_put_content
from .notify import send_mail_with_attachments
from .pdf_report import build_pdf_bytes
from .sheets import DEFAULT_WORKSHEET, auth_sheets, get_or_create_worksheet, open_spreadsheet
from .util import iso_date_parts, safe_filename, utc_ts


def setup_logging(log_file: Optional[Path], level: str = "INFO") -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=lvl,
        format="%(asctime)sZ %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


@dataclass(frozen=True)
class GraphEnv:
    tenant_id: str
    client_id: str
    client_secret: str
    hostname: str
    site_path: str
    folder: str


def require(name: str, value: str | None) -> str:
    if not value:
        raise SystemExit(f"Missing required value: {name}")
    return value


def split_emails(s: str) -> List[str]:
    return [e.strip() for e in (s or "").split(",") if e.strip()]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="complaints_pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(x):
        x.add_argument("--sp-upload", action="store_true", help="Upload outputs to SharePoint via Graph.")
        x.add_argument("--email", action="store_true", help="Send email notifications (Graph sendMail).")
        x.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
        x.add_argument("--backup-dir", default=os.getenv("BACKUP_DIR", "backups"))

    pb = sub.add_parser("backup", help="Backup Complaints worksheet -> CSV -> SharePoint (+ optional email).")
    add_common(pb)
    pb.add_argument("--sp-upload-log", action="store_true", help="Also upload run log to SharePoint.")

    pb.add_argument("--sheet-id", default=os.getenv("GSHEET_ID"))
    pb.add_argument("--worksheet", default=os.getenv("GSHEET_WORKSHEET", DEFAULT_WORKSHEET))
    pb.add_argument("--sa-json", default=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    pb.add_argument("--backup-email-to", default=os.getenv("BACKUP_EMAIL_TO", ""))
    pb.add_argument("--non-strict-header", action="store_true", help="Do not fail if header differs (not recommended).")

    pd = sub.add_parser("dispatch", help="Process repository_dispatch payload -> PDF -> SharePoint (+ email).")
    add_common(pd)
    pm = sub.add_parser("msforms-poll", help="Poll MS Forms Excel (SharePoint) -> PDF/email -> SharePoint; mark Processed.")
    add_common(pm)

    pd.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH", ""), help="Path to GitHub event JSON.")
    pd.add_argument("--title", default="Customer Complaint Form")

    return p.parse_args()


def load_graph_env() -> GraphEnv:
    return GraphEnv(
        tenant_id=require("MS_TENANT_ID", os.getenv("MS_TENANT_ID")),
        client_id=require("MS_CLIENT_ID", os.getenv("MS_CLIENT_ID")),
        client_secret=require("MS_CLIENT_SECRET", os.getenv("MS_CLIENT_SECRET")),
        hostname=require("SP_HOSTNAME", os.getenv("SP_HOSTNAME")),
        site_path=require("SP_SITE_PATH", os.getenv("SP_SITE_PATH")),
        folder=require("SP_FOLDER", os.getenv("SP_FOLDER")),
    )


def run_backup(args: argparse.Namespace) -> int:
    ts = utc_ts()
    log_path = Path(args.backup_dir) / f"run_backup_utc_{ts}.log"
    setup_logging(log_path, args.log_level)
    log = logging.getLogger("complaints_pipeline.backup")

    sheet_id = require("GSHEET_ID/--sheet-id", args.sheet_id)
    sa_json = require("GOOGLE_APPLICATION_CREDENTIALS/--sa-json", args.sa_json)
    worksheet = require("GSHEET_WORKSHEET/--worksheet", args.worksheet)

    gc = auth_sheets(sa_json)
    sh = open_spreadsheet(gc, sheet_id)
    ws = get_or_create_worksheet(sh, worksheet)

    csv_path = backup_to_csv(ws, out_dir=args.backup_dir, strict_header=not args.non_strict_header)
    log.info("CSV backup written: %s", csv_path)

    if not args.sp_upload and not args.email:
        log.info("No SharePoint upload and no email requested. Done.")
        return 0

    ge = load_graph_env()
    token = get_token(GraphApp(ge.tenant_id, ge.client_id, ge.client_secret))
    site_id = get_site_id(token, ge.hostname, ge.site_path)
    drive_id = get_default_drive_id(token, site_id)

    uploaded_csv = None
    uploaded_log = None

    if args.sp_upload:
        uploaded_csv = upload_file_put_content(token, drive_id, Path(csv_path), ge.folder, content_type="text/plain")
        log.info("Uploaded CSV driveItem id=%s", uploaded_csv.get("id"))

        if args.sp_upload_log:
            uploaded_log = upload_file_put_content(token, drive_id, log_path, ge.folder, content_type="text/plain")
            log.info("Uploaded LOG driveItem id=%s", uploaded_log.get("id"))

    if args.email:
        sender = os.getenv("MAIL_SENDER_UPN", "").strip()
        to_emails = split_emails(args.backup_email_to)
        if not sender or not to_emails:
            log.warning("Email requested but MAIL_SENDER_UPN or BACKUP_EMAIL_TO missing; skipping email.")
        else:
            subject = f"Complaints backup success (UTC {ts})"
            body = "\n".join(
                [
                    "Complaints backup completed successfully.",
                    f"UTC timestamp: {ts}",
                    f"CSV local: {csv_path}",
                    f"Log local: {log_path}",
                    f"SharePoint CSV driveItem id: {(uploaded_csv or {}).get('id', 'n/a')}",
                    f"SharePoint LOG driveItem id: {(uploaded_log or {}).get('id', 'n/a')}",
                ]
            )
            send_mail_with_attachments(
                token=token,
                sender_upn=sender,
                to_emails=to_emails,
                subject=subject,
                body_text=body,
                attachments=[Path(csv_path), log_path],
            )
            log.info("Backup email sent to %s", to_emails)

    log.info("Backup finished OK")
    return 0


def run_dispatch(args: argparse.Namespace) -> int:
    ts = utc_ts()
    log_path = Path(args.backup_dir) / f"run_dispatch_utc_{ts}.log"
    setup_logging(log_path, args.log_level)
    log = logging.getLogger("complaints_pipeline.dispatch")

    event_path = require("GITHUB_EVENT_PATH/--event-path", args.event_path)
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    sub = parse_submission(event)
    log.info("Loaded submission id=%s", sub.submission_id)

    norm = normalize_fields(sub.fields)
    # Ensure we carry timestamp into system column if present at top-level
    if not norm.get("submission_timestamp") and sub.timestamp:
        norm["submission_timestamp"] = sub.timestamp

    pdf_bytes = build_pdf_bytes(args.title, norm)

    safe_id = safe_filename(sub.submission_id)
    out_dir = Path(args.backup_dir) / "submissions"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"complaint_{safe_id}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    log.info("PDF written: %s", pdf_path)

    uploaded_pdf = None
    uploaded_json = None

    token = None
    drive_id = None

    if args.sp_upload or args.email:
        ge = load_graph_env()
        token = get_token(GraphApp(ge.tenant_id, ge.client_id, ge.client_secret))
        site_id = get_site_id(token, ge.hostname, ge.site_path)
        drive_id = get_default_drive_id(token, site_id)

    if args.sp_upload:
        ge = load_graph_env()
        y, m, d = iso_date_parts(norm.get("submission_timestamp", "") or sub.timestamp or "")
        remote_folder = f"{ge.folder}/Submissions/{y}/{m}/{d}"
        uploaded_pdf = upload_file_put_content(token, drive_id, pdf_path, remote_folder, content_type="text/plain")
        log.info("Uploaded PDF driveItem id=%s", uploaded_pdf.get("id"))

        meta_path = out_dir / f"complaint_{safe_id}.json"
        meta_path.write_text(
            json.dumps(
                {
                    "submission_id": sub.submission_id,
                    "form_title": sub.form_title,
                    "timestamp": sub.timestamp,
                    "recipients": sub.email_to,
                    "fields": norm,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        uploaded_json = upload_file_put_content(token, drive_id, meta_path, remote_folder, content_type="text/plain")
        log.info("Uploaded JSON driveItem id=%s", uploaded_json.get("id"))

    if args.email:
        sender = os.getenv("MAIL_SENDER_UPN", "").strip()
        if not sender:
            log.warning("Email requested but MAIL_SENDER_UPN missing; skipping email.")
        elif not sub.email_to:
            log.warning("Email requested but submission has no recipients; skipping email.")
        else:
            subject = f"New complaint submission: {sub.submission_id}"
            body = "\n".join(
                [
                    "A new complaint was submitted.",
                    f"Submission id: {sub.submission_id}",
                    f"Timestamp: {sub.timestamp}",
                    f"Uploaded PDF driveItem id: {(uploaded_pdf or {}).get('id', 'n/a')}",
                ]
            )
            send_mail_with_attachments(
                token=token,
                sender_upn=sender,
                to_emails=sub.email_to,
                subject=subject,
                body_text=body,
                attachments=[pdf_path, log_path],
            )
            log.info("Dispatch email sent to %s", sub.email_to)

    log.info("Dispatch finished OK")
    return 0


def main() -> int:
    args = parse_args()
    if args.cmd == "backup":
        return run_backup(args)
    if args.cmd == "dispatch":
        return run_dispatch(args)
    if args.cmd == "poll":
        return run_poll(args)
    raise SystemExit("Unknown command")
