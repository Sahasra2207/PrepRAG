from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=10)


class SourceItem(BaseModel):
    document: str
    chunk: int
    excerpt: str
    distance: float | None = None


class AskResponse(BaseModel):
    answer: str
    mode: str
    sources: list[SourceItem]
    warning: str | None = None


class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int
    total_chunks: int


class DocumentItem(BaseModel):
    filename: str
    chunks: int
