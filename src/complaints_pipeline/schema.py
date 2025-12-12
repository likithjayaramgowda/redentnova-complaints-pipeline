from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# QAF-12-01 (rev 04) aligned header order.
# We add a technical column at the end for tracing/idempotency.
SHEET_COLUMNS: List[str] = [
    "date",
    "complaint_received_by",
    "first_name",
    "last_name",
    "phone_no",
    "email_address",
    "address",
    "product_name",
    "product_size",
    "lot_serial_no",
    "quantity",
    "purchased_from_distributor",
    "country",
    "complaint_description",
    "complaint_evaluation_level",
    "report_to_authorities",
    "used_on_patient",
    "cleaned_before_sending_back_to_rn",
    "system_kind",
    "primary_solution",
    "comments",
    "complaint_no",
    "date_received_at_qa",
    "submission_timestamp",
]

# PDF layout sections: (title, keys)
PDF_SECTIONS: List[Tuple[str, List[str]]] = [
    ("Customer Complaint Form", ["date", "complaint_received_by"]),
    (
        "Contact Information / Complainant Details",
        ["first_name", "last_name", "phone_no", "email_address", "address"],
    ),
    (
        "Product Details",
        [
            "product_name",
            "product_size",
            "lot_serial_no",
            "quantity",
            "purchased_from_distributor",
            "country",
        ],
    ),
    ("Complaint", ["complaint_description"]),
    (
        "Complaint Evaluation",
        [
            "complaint_evaluation_level",
            "report_to_authorities",
            "used_on_patient",
            "cleaned_before_sending_back_to_rn",
            "system_kind",
        ],
    ),
    ("Additional Information", ["primary_solution", "comments"]),
    ("QA Manager", ["complaint_no", "date_received_at_qa"]),
    ("System", ["submission_timestamp"]),
]

# Mapping from possible Google Form question strings -> normalized keys.
# Python side mapping is a safety belt; Apps Script should already normalize.
QUESTION_MAP: Dict[str, str] = {
    "date": "date",
    "complaint received by": "complaint_received_by",
    "first name": "first_name",
    "last name": "last_name",
    "phone number": "phone_no",
    "phone no": "phone_no",
    "email address": "email_address",
    "address": "address",
    "product name": "product_name",
    "product size": "product_size",
    "lot / serial number": "lot_serial_no",
    "lot / serial no": "lot_serial_no",
    "lot/serial no": "lot_serial_no",
    "quantity": "quantity",
    "purchased from (distributer)": "purchased_from_distributor",
    "purchased from (distributor)": "purchased_from_distributor",
    "country": "country",
    "complaint description": "complaint_description",
    "complaint type": "complaint_evaluation_level",
    "should this complaint be reported to authorities ?": "report_to_authorities",
    "was the device used on a patient?": "used_on_patient",
    "was the device cleaned before sending back to rn?": "cleaned_before_sending_back_to_rn",
    "what kind of system is this?": "system_kind",
    "primary solution (if provided)": "primary_solution",
    "comments (if applicable)": "comments",
    "complaint no.": "complaint_no",
    "complaint no": "complaint_no",
    "date complaint received at qa": "date_received_at_qa",
    "timestamp": "submission_timestamp",
    "submission_timestamp": "submission_timestamp",
}

def normalize_question(q: str) -> str:
    return " ".join(q.strip().lower().split())
