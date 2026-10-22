from collections import Counter
import re
from .config import OPENAI_API_KEY, OPENAI_MODEL


def _extractive_answer(question: str, sources: list[dict]) -> str:
    """Fallback answer: rank source sentences by question-word overlap."""
    if not sources:
        return (
            "I couldn't find any uploaded document content to answer from. "
            "Upload a study document and ask again."
        )

    stopwords = {
        "what", "when", "where", "which", "who", "whom", "why", "how", "does",
        "do", "did", "is", "are", "was", "were", "the", "a", "an", "and", "or",
        "to", "of", "in", "on", "for", "with", "about", "explain", "describe",
        "tell", "me", "please", "can", "you", "it", "this", "that", "from",
    }
    q_terms = {
        token.lower() for token in re.findall(r"[A-Za-z0-9_]+", question)
        if len(token) > 2 and token.lower() not in stopwords
    }

    candidates = []
    for source in sources:
        sentences = re.split(r"(?<=[.!?])\s+|\n+", source["text"])
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 25:
                continue
            terms = {
                token.lower() for token in re.findall(r"[A-Za-z0-9_]+", sentence)
                if len(token) > 2
            }
            overlap = len(q_terms & terms)
            if overlap:
                candidates.append((overlap / max(len(q_terms), 1), sentence, source))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = []
    seen = set()
    for _, sentence, source in candidates:
        normalized = sentence.lower()
        if normalized not in seen:
            selected.append((sentence, source))
            seen.add(normalized)
        if len(selected) == 4:
            break

    if not selected:
        return (
            "I found related document chunks, but the local fallback could not identify "
            "a sentence that directly matches your question. Try rephrasing the question "
            "or upload more specific material."
        )

    answer = "Here are the most relevant statements I found in your uploaded material:\n\n"
    answer += "\n".join(f"- {sentence}" for sentence, _ in selected)
    answer += (
        "\n\nNote: this is an extractive fallback, not an LLM-generated explanation. "
        "Set OPENAI_API_KEY in your .env file to enable grounded LLM answers."
    )
    return answer


def generate_answer(question: str, sources: list[dict]) -> tuple[str, str, str | None]:
    if not sources:
        return _extractive_answer(question, sources), "no_context", None

    if not OPENAI_API_KEY:
        return _extractive_answer(question, sources), "extractive_fallback", None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        context = "\n\n".join(
            f"[Source: {s['filename']}, chunk {s['chunk_index']}]\n{s['text']}"
            for s in sources
        )
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are PrepRAG, a placement-preparation assistant. Answer using "
                        "only the supplied context. If the context does not contain enough "
                        "information, say so clearly. Do not invent facts. Refer to sources "
                        "by filename and chunk number when useful."
                    ),
                },
                {
                    "role": "user",
                    "content": f"QUESTION:\n{question}\n\nCONTEXT:\n{context}",
                },
            ],
        )
        answer = response.choices[0].message.content or "The model returned an empty answer."
        return answer, "llm", None
    except Exception as exc:
        fallback = _extractive_answer(question, sources)
        return fallback, "extractive_fallback", (
            f"LLM request failed, so the local extractive fallback was used. Details: {exc}"
        )
