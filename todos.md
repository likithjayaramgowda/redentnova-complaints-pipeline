# TODOs / Improvements (Always-Free-Tier Compatible)

## Schema / Data Quality
- [ ] Lock down the Google Form question titles to match Apps Script `QMAP` keys exactly.
- [ ] Add a schema migration helper (one-time) that can:
      - create the Complaints worksheet with the correct header
      - optionally copy historical responses from "Form Responses 1" into "Complaints" with mapping

## Dispatch idempotency (high value)
- [ ] Store processed submission IDs on SharePoint:
      - SP_FOLDER/state/processed_ids.json  (or daily partitioned files)
      - skip a dispatch if already processed
- [ ] Include SharePoint driveItem webUrl in the email body.

## Backup retention (compliance)
- [ ] Retention policy:
      - list items in SP_FOLDER
      - delete backups older than N days
      - keep last K snapshots minimum

## Notifications
- [ ] Add "email-on-failure" to admins:
      - on exception: upload log first (best effort), then email admins with the log attached

## Security / Permissions
- [ ] Prefer `Sites.Selected` + explicit site grant over broad `Sites.ReadWrite.All`.
- [ ] Document required Graph permissions in docs/permissions.md.

## Observability
- [ ] Upload a small run_summary.json for each run (counts, durations, ids).
