"""PDF and DOCX text extraction for the resume parser.

Uses PyMuPDF (fitz) for PDFs and python-docx for DOCX files.
Both normalise whitespace so the LLM sees clean, compact text.
"""
from __future__ import annotations

import re
from pathlib import Path


def extract_text(file_path: str) -> str:
    """Extract plain text from a PDF or DOCX file."""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(file_path)
    elif suffix == ".docx":
        return _extract_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type '{suffix}'. Only .pdf and .docx are accepted.")


def _extract_pdf(path: str) -> str:
    import fitz  # PyMuPDF — lazy import so unit tests can mock without the package

    doc = fitz.open(path)
    pages: list[str] = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return _clean_text("\n".join(pages))


def _extract_docx(path: str) -> str:
    from docx import Document  # python-docx — lazy import

    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return _clean_text("\n".join(paragraphs))


def _clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)       # collapse horizontal whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)    # at most two consecutive blank lines
    return text.strip()
