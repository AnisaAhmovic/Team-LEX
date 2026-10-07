"""Policy retrieval and RAG endpoints with metadata citations and local audit records."""

import logging
import sqlite3
from functools import lru_cache

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.response import Response

from retrieval import PolicyRetriever, QuestionValidationError, RetrievalUnavailableError, fallback_response
from llm import QwenService, LLMServiceError
from api.audit import AuditStore, new_record
from api.requirement_coverage import analyse_requirement_coverage_inputs, validate_requirement_coverage
from api.citations import (
    CitationValidationError, GENERATION_OPTIONS, MAX_CHUNK_CHARS,
    MAX_EVIDENCE_CHUNKS, PROMPT_VERSION, SYSTEM_PROMPT,
    build_cited_answer, build_prompt,
    generation_schema, select_context,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_policy_retriever():
    return PolicyRetriever()


@lru_cache(maxsize=1)
def get_qwen_service():
    return QwenService()


def get_audit_store():
    return AuditStore(settings.AUDIT_DB_PATH, settings.AUDIT_RETENTION_DAYS)


def _fallback(question, reason):
    return {**fallback_response(question, reason), "answer": None, "claims": [], "sources": []}


def _respond(record, result, http_status=200):
    # Private retrieval trace is never returned to users as supporting evidence.
    result = {key: value for key, value in result.items() if not key.startswith("_")}
    record["outcome"] = "error" if http_status >= 400 else result["status"]
    record["http_status"] = http_status
    record["response"] = {key: result.get(key) for key in (
        "status", "evidence_sufficient", "answer", "claims", "sources",
        "fallback_reason", "model", "latency_seconds", "message", "validation_error",
    )}
    try:
        interaction_id = get_audit_store().append(record)
    except (OSError, sqlite3.Error, ValueError, TypeError, UnicodeError):
        # Fail closed rather than claiming an unaudited answer was successful.
        # Do not leak the database path, question or exception to application logs.
        logger.error("Interaction audit write failed")
        return Response(_fallback(result.get("question"), "audit_unavailable"), status=503)
    result["interaction_id"] = interaction_id
    return Response(result, status=http_status)


def _record_retrieval(record, result):
    trace = result.get("_trace", {})
    record["retrieval"]["outcome"] = result.get("status")
    if trace.get("config"):
        record["retrieval"]["config"] = trace["config"]
    record["retrieval"]["candidates"] = trace.get("candidates", [])
    record["retrieval"]["query_scope"] = trace.get("query_scope", {})
    record["selection"]["excluded"] = [
        {"rank": c["rank"], "chunk_id": c.get("chunk_id"), "reason": c["exclusion_reason"]}
        for c in trace.get("candidates", []) if not c["eligible"]
    ]


def _policy_request(request, generate):
    record = new_record("answer" if generate else "retrieve")
    question, stage = None, "validation"
    try:
        data = request.data
        question = data.get("question") if hasattr(data, "get") else None
        record["question"] = question if isinstance(question, str) else None
        stage = "retrieval"
        retriever = get_policy_retriever()
        record["retrieval"]["config"] = retriever.audit_config()
        result = retriever.retrieve(question)
        record["question"] = result.get("question", record["question"])
        _record_retrieval(record, result)
        if not generate:
            record["selection"]["mode"] = "retrieval_only"
            record["selection"]["returned_evidence"] = [
                {"rank": c.get("rank"), "chunk_id": c.get("chunk_id")}
                for c in result.get("evidence", [])
            ]
            return _respond(record, result)
        if result.get("status") != "supported":
            return _respond(record, {**result, "answer": None, "claims": [], "sources": []})

        stage = "selection"
        evidence = result.get("evidence", [])
        candidate_pool_size = len(evidence)
        selected = select_context(
            evidence,
            max_evidence_chunks=candidate_pool_size,
            question=result["question"],
        )
        record["selection"].update({
            "mode": "rag_context", "prompt_version": PROMPT_VERSION,
            "candidate_pool_size": candidate_pool_size,
            "max_chunks": candidate_pool_size,
            "max_chunk_chars": MAX_CHUNK_CHARS,
            "selected_context": [{k: v for k, v in c.items() if k != "policy_text"} for c in selected],
        })
        if not selected:
            return _respond(record, _fallback(question, "insufficient_evidence"))

        stage = "generation"
        service = get_qwen_service()
        record["generation"].update({
            "attempted": True, "provider": "ollama", "model": service.model,
            "model_digest": None,  # Ollama /generate does not return an immutable model digest.
            "prompt_version": PROMPT_VERSION, "think": False,
            "options": GENERATION_OPTIONS, "response_format": PROMPT_VERSION,
        })
        generation = service.generate(
            build_prompt(
                result["question"],
                selected,
                query_scope=result.get("_trace", {}).get("query_scope"),
            ), system=SYSTEM_PROMPT,
            response_format=generation_schema(selected), options=GENERATION_OPTIONS,
        )
        record["generation"].update({key: generation.get(key) for key in (
            "model", "latency_seconds", "done", "done_reason", "prompt_eval_count", "eval_count",
        )})
        stage = "citation_validation"
        if generation.get("done") is False or generation.get("done_reason") == "length":
            raise CitationValidationError("incomplete_generation")
        answer, links = build_cited_answer(generation.get("text"), selected)
        record["selection"]["source_evidence"] = links
        cited = {link["evidence_id"] for link in links}
        record["selection"]["uncited_context_ids"] = [c["evidence_id"] for c in selected if c["evidence_id"] not in cited]
        if not answer["claims"]:
            record["generation"]["validation"] = "model_abstained"
            return _respond(record, _fallback(question, "generation_insufficient_evidence"))
        stage = "requirement_coverage"
        requirements, analyses = analyse_requirement_coverage_inputs(
            question,
            answer["claims"],
        )
        coverage_complete, coverage = validate_requirement_coverage(
            requirements,
            answer["claims"],
            analyses=analyses,
        )

        if not coverage_complete:
            record["generation"]["validation"] = "requirement_coverage_incomplete"
            return _respond(
                record,
                _fallback(question, "generation_insufficient_evidence"),
            )

        record["generation"]["validation"] = "accepted"
        return _respond(record, {
            "status": "supported", "question": result["question"], **answer,
            "evidence_sufficient": True, "model": generation.get("model"),
            "latency_seconds": generation.get("latency_seconds"),
        })
    except (ParseError, UnsupportedMediaType):
        record["error"] = {"stage": "validation", "code": "invalid_request"}
        return _respond(record, _fallback(None, "invalid_request"), 400)
    except QuestionValidationError:
        record["error"] = {"stage": "validation", "code": "invalid_question"}
        result = _fallback(question, "invalid_question")
        result["validation_error"] = "Provide a question containing 3 to 500 characters, including letters or numbers."
        return _respond(record, result, 400)
    except RetrievalUnavailableError:
        record["retrieval"]["outcome"] = "error"
        record["error"] = {"stage": stage, "code": "retrieval_unavailable"}
        return _respond(record, _fallback(question, "retrieval_unavailable"), 503)
    except LLMServiceError as exc:
        record["error"] = {"stage": stage, "code": "generation_unavailable", "type": type(exc).__name__}
        return _respond(record, _fallback(question, "generation_unavailable"), 502)
    except CitationValidationError as exc:
        # Reasons are fixed codes owned by api.citations, never generated text.
        record["generation"]["validation"] = str(exc)
        return _respond(record, _fallback(question, "unverifiable_generation"))
    except Exception as exc:
        # Unexpected service failures still have a record, without exception text.
        record["error"] = {
            "stage": stage,
            "code": "internal_error",
            "type": type(exc).__name__,
        }
        return _respond(record, _fallback(question, "internal_error"), 500)


@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok", "message": "Lex AI Django API is running"})


@api_view(["POST"])
def policy_evidence(request):
    return _policy_request(request, generate=False)


@api_view(["POST"])
def policy_answer(request):
    return _policy_request(request, generate=True)
