"""Run one supported and one unsupported COPL-184 verification question."""

import json

from retrieval import PolicyRetriever, RetrievalUnavailableError

SAMPLE_QUESTIONS = [
    (
        "supported",
        "What does the Assessment Policy say about feedback on assessment tasks?",
        "supported",
    ),
    (
        "unsupported",
        "What will the weather be in Melbourne tomorrow?",
        "fallback",
    ),
]


def main() -> int:
    retriever = PolicyRetriever()
    failed = False

    try:
        for label, question, expected_status in SAMPLE_QUESTIONS:
            result = retriever.retrieve(question)
            print(f"\n{label.upper()} SAMPLE")
            print(json.dumps(result, indent=2))
            if result["status"] != expected_status:
                failed = True
                print(
                    f"Expected status {expected_status!r}, "
                    f"received {result['status']!r}."
                )
    except RetrievalUnavailableError:
        print(
            "Retrieval is unavailable. Index policies first with "
            "'python -m ingestion.qdrant_indexer --recreate'."
        )
        return 2

    if failed:
        print("\nVerification failed. Review the similarity threshold and index.")
        return 1
    print("\nVerification passed for supported and unsupported questions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
