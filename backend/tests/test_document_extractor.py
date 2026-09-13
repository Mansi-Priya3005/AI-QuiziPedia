import io

import pytest
from pypdf import PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from document_extractor import DocumentExtractionError, extract_text_from_upload


def _make_real_pdf(lines):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(100, y, line)
        y -= 20
    c.showPage()
    c.save()
    return buf.getvalue()


def test_extracts_text_from_real_pdf():
    pdf_bytes = _make_real_pdf(
        [
            "Ada Lovelace was an English mathematician and writer.",
            "She worked on Charles Babbage's Analytical Engine.",
        ]
    )
    text = extract_text_from_upload("test.pdf", "application/pdf", pdf_bytes)
    assert "Ada Lovelace" in text
    assert "Analytical Engine" in text


def test_extracts_text_from_plain_text_file():
    content = b"Photosynthesis converts light energy into chemical energy."
    text = extract_text_from_upload("notes.txt", "text/plain", content)
    assert "Photosynthesis" in text


def test_rejects_corrupt_pdf():
    with pytest.raises(DocumentExtractionError, match="valid PDF"):
        extract_text_from_upload("bad.pdf", "application/pdf", b"not a real pdf")


def test_rejects_empty_file():
    with pytest.raises(DocumentExtractionError, match="empty"):
        extract_text_from_upload("empty.pdf", "application/pdf", b"")


def test_rejects_unsupported_file_type():
    with pytest.raises(DocumentExtractionError, match="Unsupported file type"):
        extract_text_from_upload("image.png", "image/png", b"fake-bytes")


def test_rejects_oversized_file():
    with pytest.raises(DocumentExtractionError, match="too large"):
        extract_text_from_upload("big.txt", "text/plain", b"x" * (11 * 1024 * 1024))


def test_rejects_encrypted_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("somepassword")
    buf = io.BytesIO()
    writer.write(buf)

    with pytest.raises(DocumentExtractionError, match="password-protected"):
        extract_text_from_upload("locked.pdf", "application/pdf", buf.getvalue())


def test_rejects_pdf_with_no_text_layer():
    """Simulates a scanned/image-only PDF."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)

    with pytest.raises(DocumentExtractionError, match="scanned document or photo"):
        extract_text_from_upload("scanned.pdf", "application/pdf", buf.getvalue())


def test_detects_pdf_by_extension_even_with_wrong_content_type():
    pdf_bytes = _make_real_pdf(["Some real content here."])
    text = extract_text_from_upload("document.pdf", "application/octet-stream", pdf_bytes)
    assert "Some real content" in text
