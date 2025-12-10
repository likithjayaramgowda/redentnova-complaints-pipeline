from unittest.mock import patch
import pytest

from complaints_pipeline.cli import main

def test_cli_requires_subcommand(monkeypatch):
    monkeypatch.setattr("sys.argv", ["prog"])
    with pytest.raises(SystemExit):
        main()

def test_backup_without_sp_or_email_does_not_call_graph(monkeypatch, tmp_path):
    monkeypatch.setenv("GSHEET_ID", "SHEET")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "sa.json")
    monkeypatch.setenv("GSHEET_WORKSHEET", "Complaints")
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["prog", "backup"])

    with patch("complaints_pipeline.cli.auth_sheets") as auth, patch(
        "complaints_pipeline.cli.open_spreadsheet"
    ) as ospr, patch("complaints_pipeline.cli.get_or_create_worksheet") as gow, patch(
        "complaints_pipeline.cli.backup_to_csv", return_value=tmp_path / "x.csv"
    ), patch("complaints_pipeline.cli.get_token") as get_token:
        auth.return_value = object()
        ospr.return_value = object()
        gow.return_value = object()
        rc = main()
        assert rc == 0
        get_token.assert_not_called()
