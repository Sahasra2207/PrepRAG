import pytest
from app.documents import chunk_text, extract_text


def test_chunk_text_creates_chunks():
    text = ("This is a useful sentence about retrieval augmented generation. " * 30).strip()
    chunks = chunk_text(text, chunk_size=250, overlap=40)
    assert len(chunks) > 1
    assert all(chunks)


def test_invalid_overlap_raises():
    with pytest.raises(ValueError):
        chunk_text("x" * 300, chunk_size=100, overlap=100)


def test_text_file_extraction():
    text = extract_text("notes.txt", b"These are sample notes with enough readable text.")
    assert "sample notes" in text


def test_unsupported_extension_raises():
    with pytest.raises(ValueError):
        extract_text("notes.docx", b"some content")
