"""Retrieve current La Trobe policy evidence from Qdrant.

The retriever validates a natural-language question, embeds it with the
BGE-M3 helper supplied by COPL-183, queries Qdrant for the top five current
policy chunks, and returns only complete evidence above the configured
similarity threshold.
"""

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from ingestion.embedding_config import EMBEDDING_DIMENSION, QDRANT_COLLECTION_NAME

TOP_K = 5
DEFAULT_MIN_SIMILARITY_SCORE = 0.55
MIN_QUESTION_LENGTH = 3
MAX_QUESTION_LENGTH = 500
CURRENT_POLICY_STATUS = "Current"
POLICY_LIBRARY_URL = "https://policies.latrobe.edu.au/"

FALLBACK_MESSAGE = (
    "I could not find enough current, authoritative La Trobe policy evidence "
    "to answer that question. I have not provided an unsupported answer."
)
ESCALATION_MESSAGE = (
    "Check the official La Trobe Policy Library or contact the relevant "
    "University office for clarification."
)


class QuestionValidationError(ValueError):
    """Raised when a question cannot safely be embedded."""


class RetrievalUnavailableError(RuntimeError):
    """Raised when the embedding model or Qdrant cannot be used."""


def validate_question(question: Any) -> str:
    """Return a normalised question or raise a validation error."""
    if not isinstance(question, str):
        raise QuestionValidationError("Question must be provided as text.")

    normalised = " ".join(question.split())
    if len(normalised) < MIN_QUESTION_LENGTH:
        raise QuestionValidationError(
            f"Question must contain at least {MIN_QUESTION_LENGTH} characters."
        )
    if len(normalised) > MAX_QUESTION_LENGTH:
        raise QuestionValidationError(
            f"Question must not exceed {MAX_QUESTION_LENGTH} characters."
        )
    if not any(character.isalnum() for character in normalised):
        raise QuestionValidationError("Question must contain letters or numbers.")
    return normalised


def fallback_response(question: Any, reason: str) -> dict[str, Any]:
    """Build the common safe response used when evidence cannot be returned."""
    safe_question = None
    if isinstance(question, str):
        safe_question = " ".join(question.split())[:MAX_QUESTION_LENGTH]

    return {
        "status": "fallback",
        "question": safe_question,
        "evidence_sufficient": False,
        "evidence": [],
        "message": FALLBACK_MESSAGE,
        "fallback_reason": reason,
        "escalation": {
            "message": ESCALATION_MESSAGE,
            "url": POLICY_LIBRARY_URL,
        },
    }


def _default_embedder(question: str) -> list[float]:
    # Lazy imports keep validation and unit tests independent of the 2 GB model.
    from ingestion.embedder import embed_text

    return embed_text(question)


def _default_client_factory():
    from ingestion.qdrant_indexer import get_client

    return get_client()


def _current_policy_filter():
    from qdrant_client.http import models as qmodels

    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="status",
                match=qmodels.MatchValue(value=CURRENT_POLICY_STATUS),
            )
        ]
    )


def _is_authoritative_url(value: str) -> bool:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and (hostname == "latrobe.edu.au" or hostname.endswith(".latrobe.edu.au"))
    )


def _text_field(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


class PolicyRetriever:
    """Semantic retrieval with current-policy, citation and evidence guardrails."""

    def __init__(
        self,
        *,
        client=None,
        client_factory: Callable[[], Any] | None = None,
        embedder: Callable[[str], Sequence[float]] | None = None,
        collection_name: str = QDRANT_COLLECTION_NAME,
        min_similarity_score: float = DEFAULT_MIN_SIMILARITY_SCORE,
        top_k: int = TOP_K,
    ) -> None:
        if not 0.0 <= float(min_similarity_score) <= 1.0:
            raise ValueError("Similarity threshold must be between 0 and 1.")
        if top_k != TOP_K:
            raise ValueError(f"Policy retrieval must query exactly {TOP_K} results.")

        self._client = client
        self._client_factory = client_factory or _default_client_factory
        self._embedder = embedder or _default_embedder
        self.collection_name = collection_name
        self.min_similarity_score = float(min_similarity_score)
        self.top_k = top_k

    def retrieve(self, question: Any) -> dict[str, Any]:
        """Return supported policy evidence or a safe fallback response."""
        normalised_question = validate_question(question)
        embedding = self._embed_question(normalised_question)
        points = self._query_qdrant(embedding)

        evidence = []
        for point in points:
            item = self._normalise_evidence(point)
            if item is not None:
                evidence.append(item)

        if not evidence:
            return fallback_response(normalised_question, "insufficient_evidence")

        return {
            "status": "supported",
            "question": normalised_question,
            "evidence_sufficient": True,
            "minimum_similarity_score": self.min_similarity_score,
            "result_count": len(evidence),
            "evidence": evidence,
        }

    def _embed_question(self, question: str) -> list[float]:
        try:
            embedding = self._embedder(question)
            if embedding is None or len(embedding) != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Expected a {EMBEDDING_DIMENSION}-dimension BGE-M3 embedding."
                )
            return [float(value) for value in embedding]
        except Exception as exc:
            raise RetrievalUnavailableError(
                "The question embedding could not be generated."
            ) from exc

    def _get_client(self):
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _query_qdrant(self, embedding: list[float]) -> list[Any]:
        try:
            client = self._get_client()
            current_filter = _current_policy_filter()

            if hasattr(client, "query_points"):
                response = client.query_points(
                    collection_name=self.collection_name,
                    query=embedding,
                    query_filter=current_filter,
                    limit=self.top_k,
                    with_payload=True,
                    with_vectors=False,
                )
                return list(response.points)

            # Compatibility with older Qdrant clients used by some team setups.
            return list(
                client.search(
                    collection_name=self.collection_name,
                    query_vector=embedding,
                    query_filter=current_filter,
                    limit=self.top_k,
                    with_payload=True,
                    with_vectors=False,
                )
            )
        except Exception as exc:
            raise RetrievalUnavailableError(
                "Current policy evidence could not be retrieved."
            ) from exc

    def _normalise_evidence(self, point: Any) -> dict[str, Any] | None:
        if isinstance(point, Mapping):
            raw_score = point.get("score")
            payload = point.get("payload")
        else:
            raw_score = getattr(point, "score", None)
            payload = getattr(point, "payload", None)

        if not isinstance(payload, Mapping):
            return None

        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(score) or score < self.min_similarity_score:
            return None

        status = _text_field(payload, "status")
        policy_text = _text_field(payload, "text")
        policy_title = _text_field(payload, "policy_title")
        section = _text_field(payload, "section")
        source_url = _text_field(payload, "source_url")

        if status is None or status.casefold() != CURRENT_POLICY_STATUS.casefold():
            return None
        if not all((policy_text, policy_title, section, source_url)):
            return None
        if not _is_authoritative_url(source_url):
            return None

        return {
            "policy_text": policy_text,
            "policy_title": policy_title,
            "section": section,
            "source_url": source_url,
            "similarity_score": round(score, 6),
        }
