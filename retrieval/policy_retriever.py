"""Retrieve current La Trobe policy evidence from Qdrant.

The retriever validates a natural-language question, embeds it with the
BGE-M3 helper supplied by COPL-183, queries Qdrant for the top five current
policy chunks, and returns only complete evidence above the configured
similarity threshold.
"""

import hashlib
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from ingestion.embedding_config import (
    EMBEDDING_DEVICE, EMBEDDING_DIMENSION, EMBEDDING_MODEL_NAME, QDRANT_COLLECTION_NAME,
)
from retrieval.query_representation import secondary_query_representation
from retrieval.query_scope import HEADING_FIELDS, QUERY_SCOPE_VERSION, apply_scope, resolve_scope

SELECTION_VERSION = "current-authoritative-threshold-v3"
PROVENANCE_FIELDS = (
    "chunk_id", "document_id", "policy_title", "section", "subsection",
    "topic", "subtopic", "paragraph_start", "paragraph_end", "source_url",
    "status_details_url", "status", "effective_date", "review_date",
    "approval_date", "version",
)
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
FALLBACK_MESSAGES = {
    "generation_unavailable": (
        "Answer generation is temporarily unavailable. Please try again shortly."
    ),
    "unverifiable_generation": (
        "I retrieved policy evidence, but could not verify the generated answer against it. "
        "Check the official policy or try rephrasing your question."
    ),
}
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
        "message": FALLBACK_MESSAGES.get(reason, FALLBACK_MESSAGE),
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
    if not isinstance(value, str) or any(c.isspace() for c in value) or "\\" in value:
        return False
    try:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and (hostname == "latrobe.edu.au" or hostname.endswith(".latrobe.edu.au"))
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443)
        )
    except ValueError:
        return False


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
        self._catalogue = None
        self._client_factory = client_factory or _default_client_factory
        self._embedder = embedder or _default_embedder
        self.collection_name = collection_name
        self.min_similarity_score = float(min_similarity_score)
        self.top_k = top_k

    def retrieve(self, question: Any) -> dict[str, Any]:
        """Return supported policy evidence or a safe fallback response."""
        normalised_question = validate_question(question)

        original_embedding = self._embed_question(normalised_question)
        secondary_question = secondary_query_representation(normalised_question)
        secondary_embedding = self._embed_question(secondary_question)

        client = self._get_client()
        query_scope = resolve_scope(
            normalised_question,
            self._load_catalogue(client),
        )
        current_filter = apply_scope(_current_policy_filter(), query_scope)

        discovery_paths = (
            (
                "original",
                self._query_qdrant_with_filter(
                    original_embedding,
                    current_filter,
                    client=client,
                ),
            ),
            (
                "secondary",
                self._query_qdrant_with_filter(
                    secondary_embedding,
                    current_filter,
                    client=client,
                ),
            ),
        )

        evidence, candidates = [], []
        seen_evidence = set()
        candidate_by_identity = {}

        for discovery_source, points in discovery_paths:
            for rank, point in enumerate(points[:self.top_k], start=1):
                item, candidate = self._evaluate_point(point, rank)
                candidate["discovery_source"] = discovery_source
                candidate["discoveries"] = [
                    {
                        "source": discovery_source,
                        "rank": rank,
                        "similarity_score": candidate["similarity_score"],
                    }
                ]

                identity = (
                    candidate.get("chunk_id"),
                    candidate["text_sha256"],
                    candidate.get("source_url"),
                )

                existing_candidate = candidate_by_identity.get(identity)
                if existing_candidate is not None:
                    discoveries = existing_candidate["discoveries"]
                    discoveries.extend(candidate["discoveries"])

                    if candidate["eligible"] and not existing_candidate["eligible"]:
                        candidate["discoveries"] = discoveries
                        candidate_by_identity[identity] = candidate
                        candidates[candidates.index(existing_candidate)] = candidate
                else:
                    candidate_by_identity[identity] = candidate
                    candidates.append(candidate)

                if item is not None:
                    if identity not in seen_evidence:
                        seen_evidence.add(identity)
                        evidence.append(item)

        trace = {
            "config": self.audit_config(),
            "candidates": candidates,
            "query_scope": query_scope,
            "retrieval_representations": {
                "original": normalised_question,
                "secondary": secondary_question,
            },
        }

        if not evidence:
            return {
                **fallback_response(
                    normalised_question,
                    "insufficient_evidence",
                ),
                "_trace": trace,
            }

        return {
            "status": "supported",
            "question": normalised_question,
            "evidence_sufficient": True,
            "minimum_similarity_score": self.min_similarity_score,
            "result_count": len(evidence),
            "evidence": evidence,
            "_trace": trace,
        }

    def audit_config(self):
        """Explicit safe configuration, never connection URLs or environment dumps."""
        return {
            "selection_version": SELECTION_VERSION,
            "query_scope_version": QUERY_SCOPE_VERSION,
            "top_k": self.top_k,
            "minimum_similarity_score": self.min_similarity_score,
            "current_status_filter": CURRENT_POLICY_STATUS,
            "collection_name": self.collection_name,
            "embedding_model": EMBEDDING_MODEL_NAME,
            "embedding_device": EMBEDDING_DEVICE,
            "embedding_dimension": EMBEDDING_DIMENSION,
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

    def _load_catalogue(self, client):
        """Cache current titles/headings from this index until the backend restarts."""
        if self._catalogue is None:
            catalogue, offset = [], None
            # Retain compatibility with injected search-only clients.
            if not hasattr(client, "scroll"):
                return []
            while True:
                records, offset = client.scroll(
                    collection_name=self.collection_name, scroll_filter=_current_policy_filter(),
                    limit=256, offset=offset,
                    with_payload=["policy_title", *HEADING_FIELDS], with_vectors=False,
                )
                for record in records:
                    payload = record.payload or {}
                    title = _text_field(payload, "policy_title")
                    if title:
                        catalogue.append({"policy_title": title, **{
                            field: _text_field(payload, field) for field in HEADING_FIELDS
                        }})
                if offset is None:
                    break
            self._catalogue = catalogue
        return self._catalogue

    def _query_qdrant(self, embedding: list[float], question: str) -> tuple[list[Any], dict]:
        """Compatibility wrapper that resolves scope from the supplied question."""
        try:
            client = self._get_client()
            scope = resolve_scope(question, self._load_catalogue(client))
            current_filter = apply_scope(_current_policy_filter(), scope)
            return (
                self._query_qdrant_with_filter(
                    embedding,
                    current_filter,
                    client=client,
                ),
                scope,
            )
        except RetrievalUnavailableError:
            raise
        except Exception as exc:
            raise RetrievalUnavailableError(
                "Current policy evidence could not be retrieved."
            ) from exc

    def _query_qdrant_with_filter(
        self,
        embedding: list[float],
        query_filter,
        *,
        client=None,
    ) -> list[Any]:
        """Run one bounded Top-K search using an already verified query filter."""
        try:
            client = client or self._get_client()

            if hasattr(client, "query_points"):
                response = client.query_points(
                    collection_name=self.collection_name,
                    query=embedding,
                    query_filter=query_filter,
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
                    query_filter=query_filter,
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
        # Kept for callers that normalise an individual point.
        return self._evaluate_point(point, 1)[0]

    def _evaluate_point(self, point: Any, rank: int):
        getter = point.get if isinstance(point, Mapping) else lambda k: getattr(point, k, None)
        payload = getter("payload")
        payload = payload if isinstance(payload, Mapping) else {}
        try:
            score = float(getter("score"))
            score = score if math.isfinite(score) else None
        except (TypeError, ValueError):
            score = None
        # Only scalar provenance is retained, never arbitrary payload fields.
        metadata = {}
        for field in PROVENANCE_FIELDS:
            value = payload.get(field)
            if isinstance(value, str):
                value = value.strip() or None
            elif not isinstance(value, (int, float)) or isinstance(value, bool):
                value = None
            elif isinstance(value, float) and not math.isfinite(value):
                value = None
            metadata[field] = value
        # Some corpus documents start at h2 rather than h1.
        metadata["section"] = next(
            (_text_field(payload, key) for key in ("section", "subsection", "topic", "subtopic")
             if _text_field(payload, key)), None,
        )
        policy_text = _text_field(payload, "text")
        point_id = getter("id")
        candidate = {
            "rank": rank, "point_id": str(point_id) if point_id is not None else None,
            **metadata, "similarity_score": score,
            "text_sha256": hashlib.sha256(policy_text.encode()).hexdigest() if policy_text else None,
            "eligible": False, "exclusion_reason": None,
        }
        reason = None
        if score is None:
            reason = "invalid_score"
        elif score < self.min_similarity_score:
            reason = "below_threshold"
        elif str(metadata["status"]).casefold() != CURRENT_POLICY_STATUS.casefold():
            reason = "not_current"
        elif not all((policy_text, _text_field(payload, "policy_title"), metadata["section"], _text_field(payload, "source_url"))):
            reason = "missing_provenance"
        elif not _is_authoritative_url(metadata["source_url"]):
            reason = "untrusted_source_url"
        if reason:
            candidate["exclusion_reason"] = reason
            return None, candidate
        # An optional details link is displayed only if it is authoritative too.
        if not _is_authoritative_url(metadata["status_details_url"]):
            metadata["status_details_url"] = None
            candidate["status_details_url"] = None
        candidate["eligible"] = True
        return {
            **metadata, "rank": rank, "point_id": candidate["point_id"],
            "policy_text": policy_text, "similarity_score": score,
        }, candidate
