import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 12000  # matches the Wikipedia scraper's limit
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}


class DocumentExtractionError(Exception):
    """Raised with a specific, user-facing reason a file couldn't be
    turned into quiz-source text."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError as e:
        raise DocumentExtractionError(
            "That file doesn't look like a valid PDF."
        ) from e

    if reader.is_encrypted:
        raise DocumentExtractionError(
            "That PDF is password-protected. Please upload an unlocked copy."
        )

    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception as e:  # pypdf can raise various parser errors per-page
            logger.warning("Failed to extract a page from PDF: %s", e)

    text = " ".join(pages_text)
    text = " ".join(text.split())  # collapse whitespace

    if not text.strip():
        # Most likely a scanned/image-only PDF with no embedded text layer.
        raise DocumentExtractionError(
            "Couldn't find any extractable text in that PDF. If it's a "
            "scanned document or photo, text extraction isn't supported yet."
        )

    return text


def extract_text_from_upload(filename: str, content_type: str, file_bytes: bytes) -> str:
    """Returns cleaned, truncated text from an uploaded PDF or plain-text
    file. Raises DocumentExtractionError with a specific reason on
    failure."""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise DocumentExtractionError(
            f"File is too large (max {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB)."
        )

    if not file_bytes:
        raise DocumentExtractionError("The uploaded file is empty.")

    is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")

    if is_pdf:
        text = extract_text_from_pdf(file_bytes)
    elif content_type == "text/plain" or filename.lower().endswith(".txt"):
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise DocumentExtractionError(
                "Couldn't read that text file (unsupported encoding -- please use UTF-8)."
            ) from e
        text = " ".join(text.split())
    else:
        raise DocumentExtractionError(
            "Unsupported file type. Please upload a PDF or a .txt file."
        )

    if not text.strip():
        raise DocumentExtractionError("That file has no readable text content.")

    return text[:MAX_CONTENT_CHARS]
