"""
Lex AI Django API views (COPL-255).

Endpoints
---------
GET  /api/health/    — liveness check (unchanged)
POST /api/retrieve/  — retrieval only, no generation (unchanged from Sprint 3)
POST /api/answer/    — full RAG: retrieve → select evidence → build prompt
                       → generate with Qwen3 → return structured JSON
"""

from functools import lru_cache

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from retrieval import (
    PolicyRetriever,
    QuestionValidationError,
    RetrievalUnavailableError,
    fallback_response,
)
from llm import QwenService, LLMServiceError

# ── Singletons ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_policy_retriever():
    """Reuse the Qdrant client and cached BGE-M3 model between requests."""
    return PolicyRetriever()


@lru_cache(maxsize=1)
def get_qwen_service():
    """Reuse the Ollama/Qwen3 client between requests."""
    return QwenService()


# ── Prompt construction ───────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are Lex, a policy assistant for La Trobe University. "
    "Answer only from the policy evidence provided. "
    "Do not use your own knowledge. "
    "If the evidence does not support a clear answer, say so directly."
)

_MAX_EVIDENCE_CHUNKS = 5
_MAX_CHUNK_CHARS = 800


def _build_prompt(question: str, evidence: list[dict]) -> str:
    """
    Build a constrained RAG prompt from the question and retrieved evidence.

    Only the top _MAX_EVIDENCE_CHUNKS chunks are included, each capped at
    _MAX_CHUNK_CHARS characters, so the combined prompt stays within Qwen3's
    context window even for long policy sections.
    """
    lines = [
        "Answer the question below using only the policy evidence provided.",
        "Cite the policy title and section for every claim.",
        "",
        f"Question: {question}",
        "",
        "Policy evidence:",
    ]

    for i, chunk in enumerate(evidence[:_MAX_EVIDENCE_CHUNKS], start=1):
        text = chunk.get("policy_text", "")[:_MAX_CHUNK_CHARS]
        title = chunk.get("policy_title", "Unknown policy")
        section = chunk.get("section", "")
        url = chunk.get("source_url", "")

        lines.append(
            f"\n[{i}] {title} — {section}\n"
            f"URL: {url}\n"
            f"{text}"
        )

    lines += ["", "Answer:"]
    return "\n".join(lines)


def _build_sources(evidence: list[dict]) -> list[dict]:
    """Return a deduplicated source list from the evidence payload."""
    seen = set()
    sources = []
    for chunk in evidence:
        url = chunk.get("source_url", "")
        if url and url not in seen:
            seen.add(url)
            sources.append(
                {
                    "policy_title": chunk.get("policy_title"),
                    "section": chunk.get("section"),
                    "source_url": url,
                    "similarity_score": chunk.get("similarity_score"),
                }
            )
    return sources


# ── Views ─────────────────────────────────────────────────────────────────────

@api_view(["GET"])
def health_check(request):
    """Return a simple response confirming the Lex AI backend is running."""
    return Response(
        {
            "status": "ok",
            "message": "Lex AI Django API is running",
        }
    )


@api_view(["POST"])
def policy_evidence(request):
    """Retrieve source-grounded current policy evidence for one question."""
    question = request.data.get("question") if hasattr(request.data, "get") else None

    try:
        result = get_policy_retriever().retrieve(question)
    except QuestionValidationError as exc:
        result = fallback_response(question, "invalid_question")
        result["validation_error"] = str(exc)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    except RetrievalUnavailableError:
        result = fallback_response(question, "retrieval_unavailable")
        return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
def policy_answer(request):
    """
    Full RAG pipeline: retrieve evidence → generate answer with Qwen3.

    Request body
    ------------
    { "question": "..." }

    Response (200 - supported answer)
    ----------------------------------
    {
        "status": "supported",
        "question": "...",
        "answer": "...",
        "sources": [
            {
                "policy_title": "...",
                "section": "...",
                "source_url": "...",
                "similarity_score": 0.82
            }
        ],
        "evidence_sufficient": true,
        "model": "qwen3:4b",
        "latency_seconds": 1.23
    }

    Response (200 - fallback, no sufficient evidence)
    --------------------------------------------------
    {
        "status": "fallback",
        "question": "...",
        "answer": null,
        "evidence_sufficient": false,
        "message": "...",
        "escalation": { "message": "...", "url": "..." }
    }

    Error responses
    ---------------
    400 — invalid question (validation failed)
    503 — Qdrant/retrieval unavailable
    502 — Qwen3/Ollama unavailable
    """
    question = request.data.get("question") if hasattr(request.data, "get") else None

    # 1. Validate and retrieve evidence.
    try:
        retrieval_result = get_policy_retriever().retrieve(question)
    except QuestionValidationError as exc:
        result = fallback_response(question, "invalid_question")
        result["validation_error"] = str(exc)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    except RetrievalUnavailableError:
        result = fallback_response(question, "retrieval_unavailable")
        return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # 2. Fallback path — bypass generation entirely when evidence is insufficient.
    if retrieval_result.get("status") == "fallback":
        result = {**retrieval_result, "answer": None}
        return Response(result, status=status.HTTP_200_OK)

    # 3. Supported path — build the constrained prompt and call Qwen3.
    evidence = retrieval_result.get("evidence", [])
    normalised_question = retrieval_result.get("question", "")

    prompt = _build_prompt(normalised_question, evidence)

    try:
        generation = get_qwen_service().generate(
            prompt,
            system=_SYSTEM_PROMPT,
        )
    except LLMServiceError:
        # Generation failed — return a safe error without leaking internal detail.
        result = fallback_response(normalised_question, "generation_unavailable")
        result["answer"] = None
        return Response(result, status=status.HTTP_502_BAD_GATEWAY)

    return Response(
        {
            "status": "supported",
            "question": normalised_question,
            "answer": generation["text"],
            "sources": _build_sources(evidence),
            "evidence_sufficient": True,
            "model": generation.get("model"),
            "latency_seconds": generation.get("latency_seconds"),
        },
        status=status.HTTP_200_OK,
    )
