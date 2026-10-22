from pathlib import Path
from pypdf import PdfReader
from io import BytesIO
import re


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


def extract_text(filename: str, content: bytes) -> str:
    """Extract text from PDF, TXT, or Markdown upload bytes."""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported file type. Upload a PDF, TXT, or MD file.")

    if extension == ".pdf":
        try:
            reader = PdfReader(BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ValueError(f"Could not read this PDF: {exc}") from exc
    else:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 20:
        raise ValueError(
            "Not enough readable text was found. If this is a scanned PDF, OCR is not included in this starter version."
        )
    return text


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    """Create overlapping character-based chunks, preferring sentence/space boundaries."""
    if chunk_size < 100:
        raise ValueError("Chunk size must be at least 100 characters.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk overlap must be non-negative and smaller than chunk size.")

    chunks = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            # Prefer a nearby sentence or whitespace boundary.
            boundary = max(text.rfind(". ", start, end), text.rfind("\n", start, end), text.rfind(" ", start, end))
            if boundary > start + int(chunk_size * 0.60):
                end = boundary + 1

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)

    return chunks
