from complaints_pipeline.pdf_report import build_pdf_bytes

def test_pdf_bytes_starts_with_pdf_magic():
    b = build_pdf_bytes("Title", {"first_name": "A"})
    assert b[:4] == b"%PDF"
