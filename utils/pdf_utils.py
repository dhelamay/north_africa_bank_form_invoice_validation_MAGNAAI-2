"""PDF text extraction utilities — PyPDF2, OCR, and page-to-image conversion."""

from __future__ import annotations
import io
import base64
#import PyPDF2
import pypdf as PyPDF2

# ── Optional OCR dependencies ──
HAS_OCR = False
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    HAS_OCR = True
except ImportError:
    pass


def extract_text_pypdf2(pdf_bytes: bytes) -> str:
    """Extract text from a text-based PDF using PyPDF2."""
    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text and page_text.strip():
            text += f"\n--- Page {i+1} ---\n{page_text}"
    return text.strip()


def extract_text_ocr(pdf_bytes: bytes, dpi: int = 300) -> str:
    """Extract text from a scanned PDF using Tesseract OCR."""
    if not HAS_OCR:
        raise RuntimeError("pytesseract and pdf2image are required for OCR. pip install pytesseract pdf2image")
    images = convert_from_bytes(pdf_bytes, dpi=dpi)
    text = ""
    for i, img in enumerate(images):
        page_text = pytesseract.image_to_string(img)
        if page_text and page_text.strip():
            text += f"\n--- Page {i+1} ---\n{page_text}"
    return text.strip()


def pdf_to_base64_images(pdf_bytes: bytes, max_pages: int = 10, dpi: int = 200) -> list[str]:
    """Convert PDF pages to base64 PNG images."""
    if not HAS_OCR:
        return []
    images = convert_from_bytes(pdf_bytes, dpi=dpi, first_page=1, last_page=max_pages)
    result = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
    return result


def is_scanned_pdf(pdf_bytes: bytes) -> bool:
    """Check if a PDF is scanned (no extractable text)."""
    text = extract_text_pypdf2(pdf_bytes)
    return len(text.strip()) < 50


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    """Get the number of pages in a PDF."""
    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)
