import fitz  # PyMuPDF
import docx

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file given its raw bytes."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file given its raw bytes."""
    import io
    doc = docx.Document(io.BytesIO(file_bytes))
    text = "\n".join([para.text for para in doc.paragraphs])
    return text.strip()

def extract_text(file_bytes: bytes, filename: str) -> str:
    """Route to the right extractor based on file extension."""
    filename = filename.lower()
    if filename.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {filename}. Only PDF and DOCX are supported.")