"""
services/document_service.py
-----------------------------
Handles everything related to turning an uploaded file into clean,
validated text that is safe (and cheap) to send to the AI.

Responsibilities:
- Extract text from PDF / DOCX / TXT
- Clean whitespace/noise while preserving meaning
- Validate the result is usable study material
- Chunk large documents for cost control (simple, no vector DB yet)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List

from ..config import settings


class DocumentProcessingError(Exception):
    """Raised for any problem extracting or validating uploaded content."""


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: str) -> str:
    """Extract selectable text from a PDF using PyMuPDF (fitz)."""
    try:
        import pymupdf as fitz  # PyMuPDF (new import name; falls back to `fitz` below)
    except ImportError:
        try:
            import fitz  # legacy import name for older PyMuPDF versions
        except ImportError as e:
            raise DocumentProcessingError(
                "PyMuPDF is not installed. Run: pip install pymupdf"
            ) from e

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise DocumentProcessingError(f"Could not open PDF: {e}") from e

    text_parts: List[str] = []
    try:
        for page in doc:
            text_parts.append(page.get_text("text"))
    finally:
        doc.close()

    text = "\n".join(text_parts)

    if not text.strip():
        raise DocumentProcessingError(
            "This PDF has no selectable text (it looks like a scanned document). "
            "Scanned and handwritten PDFs are not supported. "
            "Please upload a text-based PDF, DOCX, or TXT file instead."
        )

    return text


def extract_text_from_docx(file_path: str) -> str:
    """Extract text (paragraphs + table cells) from a DOCX file using python-docx."""
    try:
        import docx
    except ImportError as e:
        raise DocumentProcessingError(
            "python-docx is not installed. Run: pip install python-docx"
        ) from e

    try:
        document = docx.Document(file_path)
    except Exception as e:
        raise DocumentProcessingError(f"Could not open DOCX: {e}") from e

    parts: List[str] = []

    for para in document.paragraphs:
        if para.text.strip():
            # Preserve headings visually by keeping the paragraph on its own line.
            parts.append(para.text.strip())

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    text = "\n".join(parts)

    if not text.strip():
        raise DocumentProcessingError("This DOCX file appears to contain no text.")

    return text


def extract_text_from_txt(file_path: str) -> str:
    """Extract text from a plain .txt file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception as e:
        raise DocumentProcessingError(f"Could not read TXT file: {e}") from e

    if not text.strip():
        raise DocumentProcessingError("This TXT file is empty.")

    return text


def extract_text(file_path: str) -> str:
    """
    Auto-detect file type from extension and dispatch to the correct extractor.
    Validates that the file exists, is non-empty, and has a supported extension.
    """
    if not os.path.exists(file_path):
        raise DocumentProcessingError(f"File not found: {file_path}")

    if os.path.getsize(file_path) == 0:
        raise DocumentProcessingError(f"File is empty: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise DocumentProcessingError(
            f"Unsupported file type '{ext}'. Supported types: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    if ext == ".docx":
        return extract_text_from_docx(file_path)
    if ext == ".txt":
        return extract_text_from_txt(file_path)

    # Should be unreachable given the check above.
    raise DocumentProcessingError(f"Unsupported file type '{ext}'.")


# ---------------------------------------------------------------------------
# Cleaning / validation
# ---------------------------------------------------------------------------

_MULTI_BLANK_LINES = re.compile(r"\n\s*\n\s*(\n\s*)+")
_MULTI_SPACES = re.compile(r"[ \t]+")
_TRAILING_SPACES = re.compile(r"[ \t]+\n")


def clean_text(raw_text: str) -> str:
    """
    Normalise whitespace while preserving paragraph/heading structure:
    - Collapse runs of spaces/tabs to a single space
    - Collapse 3+ blank lines down to a single blank line
    - Strip trailing whitespace on each line
    - Strip leading/trailing whitespace overall
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MULTI_SPACES.sub(" ", text)
    text = _TRAILING_SPACES.sub("\n", text)
    text = _MULTI_BLANK_LINES.sub("\n\n", text)
    text = text.strip()

    return text


def validate_content(text: str, min_length: int | None = None) -> None:
    """
    Raise DocumentProcessingError if the cleaned content is not usable
    study material. Does not return anything -- call it purely for validation.
    """
    min_length = min_length or settings.MIN_CONTENT_CHARS

    if not text or not text.strip():
        raise DocumentProcessingError("Extracted content is empty after cleaning.")

    if len(text) < min_length:
        raise DocumentProcessingError(
            f"Extracted content is too short ({len(text)} characters). "
            f"At least {min_length} characters are required to generate a "
            f"meaningful quiz."
        )


# ---------------------------------------------------------------------------
# Chunking (cost control)
# ---------------------------------------------------------------------------

@dataclass
class TextChunk:
    index: int
    text: str
    char_count: int


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> List[TextChunk]:
    """
    Split large documents into overlapping chunks so we never send an
    unnecessarily huge document to the AI in one request.

    This is intentionally simple (character-based, paragraph-aware) --
    a future version can swap this for embeddings + vector search without
    changing the public function signature.
    """
    chunk_size = settings.CHUNK_SIZE_CHARS if chunk_size is None else chunk_size
    overlap = settings.CHUNK_OVERLAP_CHARS if overlap is None else overlap
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("Require chunk_size > 0 and 0 <= overlap < chunk_size.")
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        segment = text[start:end]
        chunks.append(TextChunk(len(chunks), segment, len(segment)))
        if end == len(text):
            break
        start = end - overlap
    return chunks


def select_relevant_chunks(chunks: List[TextChunk], max_chars: int | None = None) -> str:
    """Bound context strictly; this baseline selects the document's beginning."""
    max_chars = settings.MAX_CONTENT_CHARS if max_chars is None else max_chars
    if max_chars <= 0:
        raise ValueError("max_chars must be positive.")
    selected = []
    remaining = max_chars
    for chunk in chunks:
        separator = 2 if selected else 0
        if remaining <= separator:
            break
        part = chunk.text[:remaining-separator]
        selected.append(part)
        remaining -= len(part) + separator
    return "\n\n".join(selected)


def process_document(file_path: str) -> str:
    """
    Convenience pipeline: extract -> clean -> validate -> chunk/select.
    Returns the final text that is safe to send to the AI.
    """
    raw = extract_text(file_path)
    cleaned = clean_text(raw)
    validate_content(cleaned)

    chunks = chunk_text(cleaned)
    final_text = select_relevant_chunks(chunks)
    return final_text
