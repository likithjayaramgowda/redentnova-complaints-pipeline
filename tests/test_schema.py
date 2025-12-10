from complaints_pipeline.schema import PDF_SECTIONS, SHEET_COLUMNS


def test_schema_columns_unique_and_nonempty():
    assert len(SHEET_COLUMNS) == len(set(SHEET_COLUMNS))
    assert len(SHEET_COLUMNS) > 10

def test_pdf_sections_cover_known_keys():
    # Ensure at least some expected keys exist in sections
    keys = {k for _, ks in PDF_SECTIONS for k in ks}
    assert "first_name" in keys
    assert "complaint_description" in keys
