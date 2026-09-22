"""Resolve explicitly named policies and overview sections from indexed metadata.

No model-generated names, chunk IDs or URLs participate in query scoping.
"""

import re

QUERY_SCOPE_VERSION = "indexed-title-section-v1"
HEADING_FIELDS = ("section", "subsection", "topic", "subtopic")


def resolve_scope(question, catalogue):
    normalised = " ".join(question.split())
    titles = sorted({item["policy_title"] for item in catalogue}, key=lambda s: (-len(s), s))
    spans, matched = [], []
    for title in titles:
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(w) for w in title.split()) + r"(?!\w)"
        for match in re.finditer(pattern, normalised, re.I):
            if any(match.start() < end and start < match.end() for start, end in spans):
                continue
            matched.append(title)
            spans.append(match.span())
    matched = sorted(set(matched))
    # Section intent must occur outside a policy title and be explicit.
    remaining = list(normalised)
    for start, end in spans:
        remaining[start:end] = " " * (end - start)
    intents = set(re.findall(r"\b(purposes?|scope|definitions?)\s+(?:of|in)\b", "".join(remaining), re.I))
    intents = {word.casefold().removesuffix("s") for word in intents}
    requested = next(iter(intents)) if len(intents) == 1 else None
    headings = {field: set() for field in HEADING_FIELDS}
    covered = set()
    if requested and matched:
        for item in catalogue:
            if item["policy_title"] not in matched:
                continue
            for field in HEADING_FIELDS:
                heading = item.get(field)
                if isinstance(heading, str) and re.search(r"\b" + requested + r"s?\s*$", heading, re.I):
                    headings[field].add(heading)
                    covered.add(item["policy_title"])
    # Do not silently drop one of multiple requested policies if its heading is absent.
    resolved = {field: sorted(values) for field, values in headings.items() if values} if covered == set(matched) else {}
    return {"version": QUERY_SCOPE_VERSION, "policy_titles": matched,
            "requested_section": requested, "heading_filters": resolved}


def apply_scope(current_filter, scope):
    from qdrant_client.http import models as qmodels

    must = list(current_filter.must or [])
    if scope["policy_titles"]:
        must.append(qmodels.FieldCondition(key="policy_title", match=qmodels.MatchAny(any=scope["policy_titles"])))
    if scope["heading_filters"]:
        must.append(qmodels.Filter(should=[
            qmodels.FieldCondition(key=field, match=qmodels.MatchAny(any=values))
            for field, values in scope["heading_filters"].items()
        ]))
    return qmodels.Filter(must=must)
