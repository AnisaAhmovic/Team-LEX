"""Inspect local S4-10 records without exposing a public log endpoint."""
import argparse
import json

from api.audit import AuditStore, DEFAULT_AUDIT_PATH


def summarise(record):
    """Compact local diagnostic view without changing the stored audit record."""
    retrieval, selection = record.get("retrieval", {}), record.get("selection", {})
    return {
        **{key: record.get(key) for key in ("interaction_id", "timestamp_utc", "question", "outcome")},
        "fallback_reason": record.get("response", {}).get("fallback_reason"),
        "retrieval_outcome": retrieval.get("outcome"),
        "query_scope": retrieval.get("query_scope"),
        "candidates": [{key: candidate.get(key) for key in (
            "rank", "chunk_id", "policy_title", "section", "similarity_score", "eligible", "exclusion_reason",
        )} for candidate in retrieval.get("candidates", [])],
        "selected_chunks": [chunk.get("chunk_id") for chunk in selection.get("selected_context", [])],
        "generation": record.get("generation", {}),
        "source_count": len(record.get("response", {}).get("sources") or []),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument("--id", help="Interaction ID returned by the API")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--summary", action="store_true", help="Show compact selection and failure diagnostics")
    parser.add_argument("--purge-expired", action="store_true")
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()
    store = AuditStore(args.path, retention_days=args.retention_days)
    if args.purge_expired:
        print(json.dumps({"deleted": store.purge_expired()}))
    else:
        records = store.read(args.id, args.limit)
        print(json.dumps([summarise(r) for r in records] if args.summary else records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
