from complaints_pipeline.form_mapping import normalize_fields


def test_normalize_fields_maps_question_titles():
    raw = {
        "First Name": "Ada",
        "Last Name": "Lovelace",
        "Complaint Description": "X",
        "Timestamp": "2025-01-01T00:00:00Z",
    }
    out = normalize_fields(raw)
    assert out["first_name"] == "Ada"
    assert out["last_name"] == "Lovelace"
    assert out["complaint_description"] == "X"
    assert out["submission_timestamp"] == "2025-01-01T00:00:00Z"
