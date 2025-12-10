/**
 * Unified complaints pipeline:
 *   Google Form submission
 *     -> Google Sheet (form responses)
 *     -> Apps Script onFormSubmit:
 *          1) Normalize fields & append into a dedicated worksheet "Complaints" (with exact header order)
 *          2) POST repository_dispatch to GitHub (client_payload contains normalized fields)
 *   GitHub Actions runs Python:
 *     - dispatch mode: PDF + JSON -> SharePoint, optional email
 *     - backup mode:  full sheet CSV backup -> SharePoint, optional admin email
 */

const GITHUB_OWNER  = "YOUR_GH_USERNAME_OR_ORG";
const GITHUB_REPO   = "complaints-pipeline";
const DISPATCH_TYPE = "form_submit";
const COMPLAINTS_SHEET_NAME = "Complaints";

/**
 * Exact header order matching QAF-12-01 (rev 04).
 * We add one technical column at the end: submission_timestamp (UTC/ISO),
 * useful for tracing and idempotency.
 */
const HEADER = [
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
  "submission_timestamp"
];

/**
 * Map Google Form question titles -> normalized keys.
 * IMPORTANT: update the left side strings to match your exact form question text.
 */
const QMAP = {
  "Date": "date",
  "Complaint received by": "complaint_received_by",

  "First Name": "first_name",
  "Last Name": "last_name",
  "Phone No.": "phone_no",
  "Email Address": "email_address",
  "Address": "address",

  "Product Name": "product_name",
  "Product Size": "product_size",
  "LOT / Serial No.": "lot_serial_no",
  "Quantity": "quantity",
  "Purchased From (Distributer)": "purchased_from_distributor",
  "Country": "country",

  "Complaint Description": "complaint_description",

  "Complaint evaluation Level": "complaint_evaluation_level",
  "Was the complaint needs to be reported to the authorities?": "report_to_authorities",
  "Was the device used on a patient?": "used_on_patient",
  "Was the device cleaned before sending back to RN?": "cleaned_before_sending_back_to_rn",
  "What kind of system is this?": "system_kind",

  "Primary Solution (If Provided)": "primary_solution",
  "Comments (If Applicable)": "comments",

  // QA Manager fields usually NOT part of the Google Form, but we keep columns for later editing:
  "Complaint No.": "complaint_no",
  "Date Complaint Received at QA": "date_received_at_qa"
};

function getPat_() {
  const pat = PropertiesService.getScriptProperties().getProperty("GITHUB_PAT");
  if (!pat) throw new Error("Missing Script Property GITHUB_PAT");
  return pat;
}

function getOrCreateComplaintsSheet_(ss) {
  let sh = ss.getSheetByName(COMPLAINTS_SHEET_NAME);
  if (!sh) sh = ss.insertSheet(COMPLAINTS_SHEET_NAME);
  // Ensure header row matches.
  const existing = sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), 1)).getValues()[0];
  const trimmed = existing.filter(String).map(String);
  if (trimmed.length === 0) {
    sh.getRange(1, 1, 1, HEADER.length).setValues([HEADER]);
  } else {
    // If header differs, fail fast so admin can fix (avoid silently shifting columns).
    const same = JSON.stringify(existing.slice(0, HEADER.length)) === JSON.stringify(HEADER);
    if (!same) {
      throw new Error("Complaints sheet header does not match expected HEADER. Please fix header row to match QAF schema.");
    }
  }
  return sh;
}

function normalize_(namedValues) {
  const out = {};
  HEADER.forEach((k) => out[k] = "");
  Object.keys(namedValues).forEach((q) => {
    const v = namedValues[q];
    const val = Array.isArray(v) ? (v.length === 1 ? v[0] : v.join(", ")) : v;
    const key = QMAP[q];
    if (key) out[key] = val;
  });
  out["submission_timestamp"] = new Date().toISOString();
  return out;
}

/**
 * Installable trigger:
 * Apps Script editor -> Triggers -> Add Trigger
 *  - function: onFormSubmit
 *  - event source: From spreadsheet
 *  - event type: On form submit
 */
function onFormSubmit(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const complaintsSheet = getOrCreateComplaintsSheet_(ss);

  const namedValues = (e && e.namedValues) ? e.namedValues : {};
  const normalized = normalize_(namedValues);

  // Append row in exact header order
  const row = HEADER.map((k) => normalized[k] || "");
  complaintsSheet.appendRow(row);

  // Submission id: timestamp + sheet row number in Complaints tab
  const appendedRow = complaintsSheet.getLastRow();
  const submissionId = `${normalized["submission_timestamp"]}#complaints_row${appendedRow}`;

  // Recipients routing rule (EDIT THIS):
  const recipients = ["recipient@company.com"];

  const payload = {
    event_type: DISPATCH_TYPE,
    client_payload: {
      submission_id: submissionId,
      form_title: "Customer Complaint Form",
      timestamp: normalized["submission_timestamp"],
      fields: normalized,
      email_to: recipients
    }
  };

  const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`;

  const res = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    headers: {
      Authorization: "Bearer " + getPat_(),
      Accept: "application/vnd.github+json"
    },
    muteHttpExceptions: true
  });

  const code = res.getResponseCode();
  if (code >= 300) {
    throw new Error("GitHub dispatch failed: " + code + " " + res.getContentText());
  }
}
