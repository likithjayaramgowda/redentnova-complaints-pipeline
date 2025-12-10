from pathlib import Path
from unittest.mock import patch

from complaints_pipeline.backup import backup_to_csv


def test_backup_to_csv_writes_header_and_rows(tmp_path: Path):
    fake_ws = object()
    rows = [
        {"first_name": "A", "last_name": "B", "complaint_description": "X"},
        {"first_name": "C", "last_name": "D", "complaint_description": "Y"},
    ]
    with patch("complaints_pipeline.backup.read_all_complaints", return_value=rows):
        out = backup_to_csv(fake_ws, out_dir=str(tmp_path))

    text = out.read_text(encoding="utf-8")
    assert "first_name" in text
    assert "complaint_description" in text
    assert "X" in text and "Y" in text
