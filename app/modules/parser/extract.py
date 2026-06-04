"""PDF, DOCX, and image text extraction for the resume parser.

Uses PyMuPDF (fitz) for PDFs, python-docx for DOCX files,
and pytesseract for JPG/PNG images.
Both normalise whitespace so the LLM sees clean, compact text.
"""
from __future__ import annotations

import re
from pathlib import Path


def extract_text(file_path: str) -> str:
    """Extract plain text from a PDF, DOCX, JPG, or PNG file."""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(file_path)
    elif suffix in (".docx", ".doc"):
        return _extract_docx(file_path)
    elif suffix in (".jpg", ".jpeg", ".png"):
        return _extract_image(file_path)
    else:
        raise ValueError(f"Unsupported file type '{suffix}'. Supported: PDF, DOCX, JPG, PNG.")


def _extract_pdf(path: str) -> str:
    import fitz

    doc = fitz.open(path)
    pages: list[str] = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return _clean_text("\n".join(pages))


def _extract_docx(path: str) -> str:
    from docx import Document

    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return _clean_text("\n".join(paragraphs))


def _extract_image(path: str) -> str:
    """Extract text from JPG or PNG using OCR (pytesseract)."""
    from PIL import Image
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    image = Image.open(path)
    text = pytesseract.image_to_string(image)
    return _clean_text(text)


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
