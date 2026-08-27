"""Command-line entry point for COPL-184 policy retrieval."""

import argparse
import json

from retrieval import (
    DEFAULT_MIN_SIMILARITY_SCORE,
    PolicyRetriever,
    QuestionValidationError,
    RetrievalUnavailableError,
    fallback_response,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retrieve current La Trobe policy evidence from Qdrant."
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Natural-language policy question. Prompts when omitted.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SIMILARITY_SCORE,
        help="Evidence threshold between 0 and 1 (default: %(default)s).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of indented JSON.",
    )
    args = parser.parse_args()

    question = " ".join(args.question) if args.question else input("Question: ")
    try:
        result = PolicyRetriever(
            min_similarity_score=args.min_score
        ).retrieve(question)
        exit_code = 0
    except QuestionValidationError as exc:
        result = fallback_response(question, "invalid_question")
        result["validation_error"] = str(exc)
        exit_code = 2
    except (RetrievalUnavailableError, ValueError):
        result = fallback_response(question, "retrieval_unavailable")
        exit_code = 3

    print(json.dumps(result, indent=None if args.compact else 2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
