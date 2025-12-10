from __future__ import annotations

import base64
from pathlib import Path
from typing import Iterable, List, Optional

from .graph import session_with_retries


def _file_attachment(path: Path) -> dict:
    content_bytes = path.read_bytes()
    content_b64 = base64.b64encode(content_bytes).decode("ascii")
    return {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": path.name,
        "contentType": "application/octet-stream",
        "contentBytes": content_b64,
    }


def send_mail_with_attachments(
    token: str,
    sender_upn: str,
    to_emails: List[str],
    subject: str,
    body_text: str,
    attachments: Optional[Iterable[Path]] = None,
    save_to_sent_items: bool = True,
) -> None:
    url = f"https://graph.microsoft.com/v1.0/users/{sender_upn}/sendMail"
    atts = [_file_attachment(Path(p)) for p in (attachments or [])]

    to_recipients = [{"emailAddress": {"address": e}} for e in to_emails if e.strip()]
    if not to_recipients:
        raise ValueError("No recipients provided.")

    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": to_recipients,
            "attachments": atts,
        },
        "saveToSentItems": bool(save_to_sent_items),
    }

    s = session_with_retries()
    r = s.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
