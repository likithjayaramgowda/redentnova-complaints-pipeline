# Complaints Pipeline (QAF-12-01 rev 04 aligned)
Google Form → Google Sheet (normalized "Complaints" tab) → GitHub Actions → PDF/CSV → SharePoint (+ optional email)

This repository implements **two modes**:

1) **dispatch** (runs on each Google Form submission via `repository_dispatch`)
- Apps Script normalizes the submitted answers into the exact QAF schema key order and appends them to the `Complaints` worksheet.
- GitHub Actions runs `dispatch`:
  - Generates a PDF in the same section order as the QAF form
  - Uploads PDF + JSON metadata to SharePoint
  - Optionally emails recipients (from the dispatch payload) via Microsoft Graph `sendMail`

2) **backup** (runs daily on schedule)
- Reads the `Complaints` worksheet
- Writes a timestamped CSV backup + log
- Uploads CSV (+ log) to SharePoint
- Optionally emails admin recipients (BACKUP_EMAIL_TO)

---

## QAF-aligned Google Sheet header (exact order)
The `Complaints` worksheet MUST have the following header columns in row 1
(Apps Script will create this header automatically if the sheet is empty):

1. date
2. complaint_received_by
3. first_name
4. last_name
5. phone_no
6. email_address
7. address
8. product_name
9. product_size
10. lot_serial_no
11. quantity
12. purchased_from_distributor
13. country
14. complaint_description
15. complaint_evaluation_level
16. report_to_authorities
17. used_on_patient
18. cleaned_before_sending_back_to_rn
19. system_kind
20. primary_solution
21. comments
22. complaint_no
23. date_received_at_qa
24. submission_timestamp  (technical field for traceability / idempotency)

---

## Setup (end-to-end)

### A) Google Form → Google Sheet
- Create the Google Form.
- Link responses to a Google Sheet (Form "Responses" tab → Link to spreadsheet).

### B) Apps Script (normalize + append + dispatch)
1. Open the linked Google Sheet
2. Extensions → Apps Script
3. Paste `apps_script/Code.gs`
4. Set:
   - `GITHUB_OWNER`
   - `GITHUB_REPO`
5. In Script Properties set `GITHUB_PAT`
   - PAT must allow `POST /repos/{owner}/{repo}/dispatches`
6. Add installable trigger:
   - function: `onFormSubmit`
   - event source: From spreadsheet
   - event type: On form submit
7. IMPORTANT: update the `QMAP` keys in Apps Script to exactly match your Google Form question titles.

### C) Google Service Account (for backup mode)
- Create a Google service account JSON and store it as a GitHub secret.
- Share your Google Sheet with the service account email (Editor minimum).
- Set:
  - `GSHEET_ID`
  - `GOOGLE_SA_JSON_B64` (base64 of the service-account JSON)

To create the base64:
`./scripts/encode_google_sa_json_b64.sh /path/to/service_account.json`

### D) Microsoft Graph / SharePoint
Set GitHub secrets:
- `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`
- `SP_HOSTNAME` (e.g., tenant.sharepoint.com)
- `SP_SITE_PATH` (e.g., /sites/Quality)
- `SP_FOLDER` (e.g., Backups/Complaints)

Optional email:
- `MAIL_SENDER_UPN`
- `BACKUP_EMAIL_TO` (comma-separated) for backup emails

---

## Run locally
- Install: `make install`
- Test: `make test`
- Lint: `make lint`
- Backup mode: `make run`
- Dispatch mode (using sample_event.json): `make run-dispatch`

---

## Where files end up in SharePoint
Base folder: `SP_FOLDER`

- Backups:
  - complaints_backup_utc_YYYYmmdd_HHMMSS.csv
  - run_backup_utc_YYYYmmdd_HHMMSS.log

- Submissions:
  - SP_FOLDER/Submissions/YYYY/MM/DD/complaint_<id>.pdf
  - SP_FOLDER/Submissions/YYYY/MM/DD/complaint_<id>.json

---

## Notes
- Backup mode is strict by default: it fails if the worksheet header order differs from QAF schema.
  (You can bypass with `--non-strict-header`, but it’s not recommended.)
