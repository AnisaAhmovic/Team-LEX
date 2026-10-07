"""Generic deterministic query representation helpers.

This module contains retrieval-neutral lexical normalization only.
It must not contain policy-specific concept mappings or infer query scope.
"""

import re


RELEVANCE_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for",
    "from", "has", "how", "in", "is", "it", "of", "on", "or", "the",
    "their", "to", "what", "which", "with",
}


def relevance_terms(text: str) -> set[str]:
    """Return deterministic normalized content terms for a text value."""
    terms = []
    for token in re.findall(r"[A-Za-z]+", text.lower()):
        if token in RELEVANCE_STOPWORDS:
            continue

        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and len(token) > 4:
            token = token[:-1]

        terms.append(token)

    return set(terms)


def secondary_query_representation(question: str) -> str:
    """Return the deterministic recall-only secondary retrieval representation."""
    return " ".join(sorted(relevance_terms(question)))
