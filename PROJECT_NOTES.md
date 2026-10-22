# Project notes for interview preparation

## What is implemented in this starter

- FastAPI app and browser UI
- PDF/TXT/Markdown text extraction
- Character-based overlapping chunking
- Sentence Transformers embeddings
- Persistent ChromaDB storage and semantic retrieval
- Optional OpenAI grounded answer generation
- Extractive fallback when no OpenAI key is configured
- Display of source filename, chunk number, excerpt, and cosine distance

## Important wording for an interview

Only describe the parts you have actually run and verified as implemented and tested. A safe explanation after you run the project is:

"PrepRAG is a document-grounded placement preparation application. It extracts text from uploaded study material, splits it into overlapping chunks, generates embeddings with Sentence Transformers, and stores the chunks and vectors in ChromaDB. When a user asks a question, the system embeds the query, retrieves relevant chunks, and uses those chunks as context for answer generation. If an LLM API key is not configured, the current starter uses an extractive fallback and shows source excerpts."

Do not claim measured accuracy or production readiness without an evaluation process.

## Retrieval details

- The same Sentence Transformers model is used for document chunks and user queries.
- ChromaDB collection uses cosine distance.
- Lower cosine distance means closer vectors for this configuration.
- Retrieval distance is not model confidence.
- The threshold in `app/main.py` is a starter heuristic and should be validated against test questions.

## Main files

- `app/main.py`: FastAPI routes and application entry point
- `app/documents.py`: text extraction and chunking
- `app/vector_store.py`: embedding generation and ChromaDB operations
- `app/answering.py`: optional LLM generation and local fallback
- `app/schemas.py`: request/response models
- `app/static/`: frontend


## Additional study features in this version

- Quizzes are generated locally from sentences in indexed chunks. The current question style checks source recall; it does not use an LLM to invent concept questions. Explanations refer to the source filename and chunk.
- Company mock interviews use a small curated question bank for common fresher interview themes. Company-specific prompts are practice material and are not claimed to be official questions.
- Quiz results are stored in SQLite. Weak-topic flags are heuristic: at least two answers for a topic and below 70% accuracy.
- Mock-practice tracking stores the selected company, category, question, self-rating, and optional notes.
- Progress data stays local in `data/progress.db`; it is not tied to a user account.


## Quiz-generation update (2026-10-22)
- Replaced quote-recognition quiz prompts with topic-aware conceptual and scenario-based MCQs for common DBMS, RAG/AI, OS, networking, and ML concepts.
- Explanations include source context for traceability. The current offline generator uses predefined question templates matched to concepts found in uploaded chunks; it is not a general-purpose LLM quiz writer.
- For topics not recognized by the template bank, it uses a basic grounded fallback or reports insufficient recognizable content. Expand the template bank or add an LLM-backed generation path for broader coverage.
