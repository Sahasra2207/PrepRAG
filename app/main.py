from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .study_features import generate_quiz, submit_quiz, progress, mock_questions, save_mock

from .answering import generate_answer
from .config import MAX_UPLOAD_MB, UPLOAD_DIR, CHUNK_SIZE, CHUNK_OVERLAP, TOP_K
from .documents import extract_text, chunk_text, SUPPORTED_EXTENSIONS
from .schemas import AskRequest, AskResponse, UploadResponse, SourceItem, DocumentItem
from .vector_store import add_chunks, query_chunks, list_documents, total_chunks

app = FastAPI(
    title="PrepRAG",
    description="A beginner-friendly RAG placement-preparation app.",
    version="1.0.0",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "PrepRAG"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    filename = Path(file.filename or "upload.txt").name
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Supported formats: PDF, TXT, and MD.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_MB} MB limit.")

    try:
        text = extract_text(filename, content)
        chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
        added = add_chunks(filename, chunks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not process document. Check dependencies/model download and try again. Details: {exc}",
        ) from exc

    # Keep an uploaded copy for local demonstration and debugging.
    safe_name = filename.replace("/", "_").replace("\\", "_")
    (UPLOAD_DIR / safe_name).write_bytes(content)

    return UploadResponse(
        message="Document processed and indexed successfully.",
        filename=filename,
        chunks_added=added,
        total_chunks=total_chunks(),
    )


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")

    try:
        matches = query_chunks(question, request.top_k or TOP_K)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not search the vector database. Details: {exc}",
        ) from exc

    # A cosine distance near 0 is closer; larger distances are less similar.
    # This is only a retrieval distance, not an answer confidence score.
    relevant = [item for item in matches if item["distance"] is None or item["distance"] <= 0.75]
    answer, mode, warning = generate_answer(question, relevant)

    sources = [
        SourceItem(
            document=item["filename"],
            chunk=item["chunk_index"],
            excerpt=item["text"][:350] + ("…" if len(item["text"]) > 350 else ""),
            distance=item["distance"],
        )
        for item in relevant
    ]
    if not relevant and matches:
        warning = (
            "The nearest chunks were too distant to treat as relevant. "
            "Try another question or upload a more suitable document."
        )
    return AskResponse(answer=answer, mode=mode, sources=sources, warning=warning)


@app.get("/api/documents", response_model=list[DocumentItem])
def documents():
    try:
        return list_documents()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not list documents: {exc}") from exc


@app.get("/api/stats")
def stats():
    return {"total_chunks": total_chunks(), "documents": len(list_documents())}


@app.get("/api/sample-study-notes")
def sample_study_notes():
    return {
        "filename": "sample_study_notes.txt",
        "text": (
            "Retrieval-Augmented Generation (RAG) combines information retrieval with text generation. "
            "A RAG system retrieves relevant passages from a knowledge source and gives those passages "
            "to a language model as context. This can help the model answer questions using specific "
            "documents instead of relying only on its pre-trained knowledge.\\n\\n"
            "An embedding is a numerical representation of text. An embedding model maps a piece of text "
            "to a vector so that texts with related meanings can be close in vector space. Semantic search "
            "uses these representations to find meaning-related content, even when the query and document "
            "do not use exactly the same words.\\n\\n"
            "ChromaDB is a vector database that can store embeddings along with documents and metadata. "
            "When a user asks a question, the application embeds the question and searches for nearby "
            "document vectors. The retrieved chunks can then be passed to a language model.\\n\\n"
            "Chunking splits long documents into smaller pieces. Chunk overlap repeats a small amount of "
            "text between adjacent chunks to reduce the chance that a useful sentence is split at a boundary. "
            "Top-k retrieval means returning the k nearest matching chunks.\\n\\n"
            "RAG has limitations. Retrieval can return irrelevant text, source documents can be incomplete, "
            "and a language model can still generate unsupported statements. A reliable application should "
            "show sources and say when the available context is insufficient."
        ),
    }


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: list[int]

class MockAttemptRequest(BaseModel):
    company: str = "General"
    category: str = "General"
    question: str = Field(min_length=2, max_length=1000)
    self_rating: int = Field(ge=1, le=5)
    notes: str = Field(default="", max_length=2000)

@app.post("/api/quiz/generate")
def quiz_generate(count: int = 5):
    try:
        return generate_quiz(count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not generate quiz: {exc}") from exc

@app.post("/api/quiz/submit")
def quiz_submit(request: QuizSubmitRequest):
    try:
        return submit_quiz(request.quiz_id, request.answers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/mock/questions")
def mock_get_questions(company: str = "General", category: str = "All", count: int = 5):
    return mock_questions(company, category, count)

@app.post("/api/mock/attempt")
def mock_save_attempt(request: MockAttemptRequest):
    try:
        return save_mock(request.company, request.category, request.question, request.self_rating, request.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/progress")
def learning_progress():
    return progress()
