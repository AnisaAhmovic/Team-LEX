import time
from functools import lru_cache

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from retrieval import (
    QuestionValidationError,
    RetrievalUnavailableError,
    fallback_response,
)

from api.audit import AuditingPolicyRetriever, public_evidence, save_audit


@lru_cache(maxsize=1)
def get_policy_retriever():
    """Reuse the Qdrant client and cached BGE-M3 model between requests."""
    # AuditingPolicyRetriever is COPL-184's PolicyRetriever with the chunk ids
    # kept on, so the audit log can record which chunks were used. The extra
    # fields are taken back off before we reply, so the response is unchanged.
    return AuditingPolicyRetriever()


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

    retriever = get_policy_retriever()
    start = time.time()

    # Every search gets an audit record, including the ones that fail. A search
    # that is missing from the log is a hole in the trail.
    try:
        result = retriever.retrieve(question)
    except QuestionValidationError as exc:
        result = fallback_response(question, "invalid_question")
        result["validation_error"] = str(exc)
        save_audit(question, result, time_taken_ms=_ms_since(start),
                   error=str(exc), retriever=retriever)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    except RetrievalUnavailableError:
        result = fallback_response(question, "retrieval_unavailable")
        save_audit(question, result, time_taken_ms=_ms_since(start),
                   error="retrieval_unavailable", retriever=retriever)
        return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    log = save_audit(question, result, time_taken_ms=_ms_since(start),
                     retriever=retriever)

    # Strip the audit-only fields so the response stays exactly the shape
    # COPL-184 defined, then add the audit id so a reply can be traced back.
    result = dict(result)
    result["evidence"] = public_evidence(result.get("evidence") or [])
    result["audit_id"] = log.id

    return Response(result, status=status.HTTP_200_OK)


def _ms_since(start):
    return int((time.time() - start) * 1000)
