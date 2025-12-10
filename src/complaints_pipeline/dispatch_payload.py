from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class Submission:
    submission_id: str
    form_title: str
    timestamp: str
    fields: Dict[str, Any]
    email_to: List[str]


def parse_submission(event: Dict[str, Any]) -> Submission:
    payload = (event.get("client_payload") or {})
    email_to = payload.get("email_to") or []
    if isinstance(email_to, str):
        email_to = [email_to]

    sub = Submission(
        submission_id=str(payload.get("submission_id") or "").strip(),
        form_title=str(payload.get("form_title") or "Form Submission").strip(),
        timestamp=str(payload.get("timestamp") or "").strip(),
        fields=dict(payload.get("fields") or {}),
        email_to=[str(x).strip() for x in email_to if str(x).strip()],
    )

    if not sub.submission_id:
        raise ValueError("Missing submission_id in client_payload.")
    return sub
