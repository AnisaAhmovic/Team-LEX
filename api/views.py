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


@lru_cache(maxsize=1)
def get_policy_retriever():
    """Reuse the Qdrant client and cached BGE-M3 model between requests."""
    return PolicyRetriever()


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
