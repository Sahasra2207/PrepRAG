import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("PREPRAG_DATA_DIR", PROJECT_ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma"
COLLECTION_NAME = os.getenv("PREPRAG_COLLECTION", "preprag_documents")

# The embedding model downloads on first use if it is not already cached.
EMBEDDING_MODEL = os.getenv("PREPRAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Optional: set OPENAI_API_KEY in .env to enable LLM-generated answers.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MAX_UPLOAD_MB = int(os.getenv("PREPRAG_MAX_UPLOAD_MB", "10"))
CHUNK_SIZE = int(os.getenv("PREPRAG_CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("PREPRAG_CHUNK_OVERLAP", "150"))
TOP_K = int(os.getenv("PREPRAG_TOP_K", "4"))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
