# audit.py
# Records every policy search that happens, so we can show what evidence the
# system used and prove it came from a real policy.
#
# This does NOT do the searching. COPL-184's PolicyRetriever does that. This
# file wraps it and writes down what it did.
#
# Every search is saved twice:
#   1. into the database (db.sqlite3) so we can look it up later
#   2. into data/audit/audit_log.jsonl so we can attach it to a Jira ticket
#      without having to send someone our database file

import json
import os

from django.conf import settings

from api.models import AuditChunk, AuditLog
from ingestion.embedding_config import QDRANT_COLLECTION_NAME
from retrieval import DEFAULT_MIN_SIMILARITY_SCORE, TOP_K, PolicyRetriever

AUDIT_FILE = os.path.join(settings.BASE_DIR, "data", "audit", "audit_log.jsonl")

# If the top two results come from different policies and their scores are
# this close, we can't tell which policy the person meant.
AMBIGUOUS_GAP = 0.03

# The outcomes we record.
ANSWERED = "answered"
UNSUPPORTED = "unsupported"
AMBIGUOUS = "ambiguous"
ERROR = "error"


class AuditingPolicyRetriever(PolicyRetriever):
    """
    PolicyRetriever that also keeps the chunk id and a few other fields.

    COPL-184's retriever only returns policy_text, policy_title, section,
    source_url and similarity_score, and its tests check for exactly those
    keys. We can't change it without breaking those tests, but the audit log
    has to record chunk identifiers, so we add the extra fields back on here.
    """

    def _normalise_evidence(self, point):
        evidence = super()._normalise_evidence(point)
        if evidence is None:
            return None

        if hasattr(point, "payload"):
            payload = point.payload
        else:
            payload = point.get("payload")
        if payload is None:
            payload = {}

        evidence = dict(evidence)
        evidence["chunk_id"] = payload.get("chunk_id")
        evidence["document_id"] = payload.get("document_id")
        evidence["subsection"] = payload.get("subsection")
        evidence["status"] = payload.get("status")
        evidence["effective_date"] = payload.get("effective_date")
        evidence["status_details_url"] = payload.get("status_details_url")
        return evidence


# The extra fields we add above. The API strips these back off before it
# replies, so the endpoint keeps the exact response shape COPL-184 built.
EXTRA_AUDIT_FIELDS = [
    "chunk_id",
    "document_id",
    "subsection",
    "status",
    "effective_date",
    "status_details_url",
]


def public_evidence(evidence_list):
    """Return the evidence with our extra audit fields taken back off."""
    cleaned = []
    for evidence in evidence_list:
        item = {}
        for key in evidence:
            if key not in EXTRA_AUDIT_FIELDS:
                item[key] = evidence[key]
        cleaned.append(item)
    return cleaned


def safe_text(value, fallback=""):
    """
    Only keep the value if it really is a string.

    The API tests replace the retriever with a mock, and a mock will happily
    hand back a fake object for any attribute you ask for. Those can't be
    saved to the database, so anything that isn't a real string is dropped.
    """
    if isinstance(value, str):
        return value
    return fallback


def safe_number(value, fallback=0.0):
    """Same idea as safe_text, but for the scores and thresholds."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    return float(value)


def get_model_version():
    """Which version of sentence-transformers is installed."""
    try:
        import sentence_transformers
        return sentence_transformers.__version__
    except Exception:
        return "unknown"


def count_chunks_indexed(retriever=None):
    """
    How many chunks were searchable when this question was asked.

    Only asks Qdrant if the retriever already has a connection open, so this
    never opens Qdrant on its own (that would slow the unit tests down and
    fight over the qdrant_storage lock).
    """
    try:
        client = getattr(retriever, "_client", None)
        if client is None:
            return None
        return int(client.count(retriever.collection_name, exact=True).count)
    except Exception:
        return None


def work_out_outcome(result):
    """Turn the retriever's result into one of our audit outcomes."""
    if result.get("status") != "supported":
        return UNSUPPORTED

    evidence = result.get("evidence") or []
    if len(evidence) == 0:
        return UNSUPPORTED

    best = evidence[0]

    # If a chunk from a different policy scored almost as well, we don't know
    # which policy the person meant.
    for item in evidence[1:]:
        if item.get("policy_title") != best.get("policy_title"):
            gap = best.get("similarity_score", 0) - item.get("similarity_score", 0)
            if gap <= AMBIGUOUS_GAP:
                return AMBIGUOUS
            break

    return ANSWERED


def make_config_summary(min_score, model_version, chunks_indexed):
    """A short line describing the setup, e.g.
    BAAI/bge-m3 st3.3.1 chunks=85 k=5 min=0.55 gap=0.03
    """
    return "BAAI/bge-m3 st{} chunks={} k={} min={} gap={}".format(
        model_version, chunks_indexed, TOP_K, min_score, AMBIGUOUS_GAP,
    )


def save_audit(question, result, source="api", test_id="", time_taken_ms=None,
               error="", retriever=None):
    """
    Save one search. `result` is what PolicyRetriever.retrieve() returned.
    Returns the AuditLog row that was created.
    """
    evidence = result.get("evidence") or []

    if error:
        outcome = ERROR
    else:
        outcome = work_out_outcome(result)

    top_score = None
    if len(evidence) > 0:
        top_score = evidence[0].get("similarity_score")
        if not isinstance(top_score, (int, float)) or isinstance(top_score, bool):
            top_score = None

    model_version = get_model_version()
    chunks_indexed = count_chunks_indexed(retriever)
    min_score = safe_number(result.get("minimum_similarity_score"),
                            DEFAULT_MIN_SIMILARITY_SCORE)

    log = AuditLog.objects.create(
        question=safe_text(result.get("question")) or safe_text(question),
        source=source,
        test_id=test_id,
        outcome=outcome,
        retriever_status=safe_text(result.get("status"))[:20],
        fallback_reason=safe_text(result.get("fallback_reason"))[:50],
        top_score=top_score,
        num_results=len(evidence),
        time_taken_ms=time_taken_ms,
        error=safe_text(error),
        model_name="BAAI/bge-m3",
        model_version=model_version,
        collection_name=safe_text(getattr(retriever, "collection_name", None),
                                  QDRANT_COLLECTION_NAME),
        chunks_indexed=chunks_indexed,
        top_k=TOP_K,
        min_score=min_score,
        ambiguous_gap=AMBIGUOUS_GAP,
        config_summary=make_config_summary(min_score, model_version, chunks_indexed),
    )

    rank = 1
    for item in evidence:
        AuditChunk.objects.create(
            audit=log,
            rank=rank,
            chunk_id=safe_text(item.get("chunk_id")),
            document_id=safe_text(item.get("document_id")),
            policy_title=safe_text(item.get("policy_title")),
            section=safe_text(item.get("section")),
            subsection=safe_text(item.get("subsection")),
            source_url=safe_text(item.get("source_url")),
            status_details_url=safe_text(item.get("status_details_url")),
            status=safe_text(item.get("status")),
            effective_date=safe_text(item.get("effective_date")),
            score=safe_number(item.get("similarity_score")),
            text_snippet=" ".join((item.get("policy_text") or "").split())[:400],
        )
        rank = rank + 1

    write_to_file(log, evidence)
    return log


def write_to_file(log, evidence):
    """Add one line to the JSONL audit file."""
    folder = os.path.dirname(AUDIT_FILE)
    if not os.path.exists(folder):
        os.makedirs(folder)

    row = {
        "audit_id": log.id,
        "timestamp": log.created_at.isoformat(),
        "source": log.source,
        "test_id": log.test_id,
        "question": log.question,
        "outcome": log.outcome,
        "retriever_status": log.retriever_status,
        "fallback_reason": log.fallback_reason,
        "top_score": log.top_score,
        "num_results": log.num_results,
        "time_taken_ms": log.time_taken_ms,
        "error": log.error,
        "model_name": log.model_name,
        "model_version": log.model_version,
        "collection_name": log.collection_name,
        "chunks_indexed": log.chunks_indexed,
        "top_k": log.top_k,
        "min_score": log.min_score,
        "ambiguous_gap": log.ambiguous_gap,
        "config_summary": log.config_summary,
        "evidence": evidence,
    }

    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
