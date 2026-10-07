"""Claim-level semantic groundedness and policy-constraint validation."""

from functools import lru_cache
import re

NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-xsmall"


@lru_cache(maxsize=1)
def _get_nli_model():
    """Load the local NLI cross-encoder once per application process."""
    from sentence_transformers import CrossEncoder

    return CrossEncoder(NLI_MODEL_NAME, device="cpu")


def semantic_entailment(claim, supporting_quotes, trusted_context=None):
    """Return NLI probabilities for a claim against trusted context and exact quotes."""
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim must be non-empty")
    if not supporting_quotes or not all(
        isinstance(quote, str) and quote.strip() for quote in supporting_quotes
    ):
        raise ValueError("supporting_quotes must contain non-empty strings")
    if trusted_context is not None and (
        not isinstance(trusted_context, str) or not trusted_context.strip()
    ):
        raise ValueError("trusted_context must be a non-empty string when supplied")

    quote_premise = " ".join(quote.strip() for quote in supporting_quotes)
    premise = (
        f"{trusted_context.strip()} {quote_premise}"
        if trusted_context is not None
        else quote_premise
    )

    model = _get_nli_model()
    scores = model.predict([[premise, claim.strip()]], apply_softmax=True)[0]

    labels = {
        int(index): str(label).lower()
        for index, label in model.model.config.id2label.items()
    }
    probabilities = {
        labels[index]: float(scores[index])
        for index in range(len(scores))
    }

    return probabilities


def is_semantically_supported(
    claim,
    supporting_quotes,
    trusted_context=None,
    interpretive_context=None,
):
    """Accept direct entailment or contextual resolution without evidence substitution."""
    direct_probabilities = semantic_entailment(
        claim,
        supporting_quotes,
        trusted_context=trusted_context,
    )
    if "entailment" not in direct_probabilities:
        raise ValueError("NLI model did not return an entailment label")

    direct_predicted = max(direct_probabilities, key=direct_probabilities.get)
    if direct_predicted == "entailment" or interpretive_context is None:
        return direct_predicted == "entailment", direct_probabilities

    if not isinstance(interpretive_context, str) or not interpretive_context.strip():
        raise ValueError(
            "interpretive_context must be a non-empty string when supplied"
        )

    anchor_text = " ".join(quote.strip() for quote in supporting_quotes)
    contextual_probabilities = semantic_entailment(
        claim,
        [f"{interpretive_context.strip()} {anchor_text}"],
        trusted_context=trusted_context,
    )
    context_only_probabilities = semantic_entailment(
        claim,
        [interpretive_context.strip()],
        trusted_context=trusted_context,
    )

    contextual_predicted = max(
        contextual_probabilities,
        key=contextual_probabilities.get,
    )
    context_only_predicted = max(
        context_only_probabilities,
        key=context_only_probabilities.get,
    )

    supported = (
        contextual_predicted == "entailment"
        and context_only_predicted != "entailment"
    )

    if supported:
        mode = "contextual"
    elif context_only_predicted == "entailment":
        mode = "context_substitution_rejected"
    else:
        mode = "contextual_rejected"

    return supported, {
        "mode": mode,
        "direct": direct_probabilities,
        "context_plus_anchor": contextual_probabilities,
        "context_only": context_only_probabilities,
    }


_POLICY_CONSTRAINT_PATTERNS = {
    "prohibition": (
        r"\bmust\s+not\b",
        r"\bshall\s+not\b",
        r"\bprohibited\b",
        r"\bnot\s+permitted\b",
        r"\bnot\s+allowed\b",
        r"\bcannot\b",
        r"\bcan't\b",
    ),
    "mandatory": (
        r"\bmust\b",
        r"\bshall\b",
        r"\brequired\s+to\b",
        r"\bis\s+required\b",
        r"\bare\s+required\b",
    ),
    "permission": (
        r"\bmay\b",
        r"\bpermitted\b",
        r"\ballowed\b",
    ),
    "approval_authorisation": (
        r"\bapproval\b",
        r"\bapproved\b",
        r"\bapprove\b",
        r"\bapproves\b",
        r"\bapproving\b",
        r"\bauthorisation\b",
        r"\bauthorization\b",
        r"\bauthorised\b",
        r"\bauthorized\b",
    ),
    "consent_permission": (
        r"\bconsent\b",
        r"\bwith\s+permission\b",
        r"\bpermission\s+(?:from|of)\b",
    ),
    "conditionality": (
        r"(?<!even )\bif\b",
        r"\bwhere\b",
        r"\bwhen\b",
        r"\bprovided\s+that\b",
        r"\bsubject\s+to\b",
    ),
    "exception": (
        r"\bunless\b",
        r"\bexcept\b",
        r"\bexcept\s+where\b",
    ),
    "exclusivity": (
        r"\bonly\b",
        r"\bsolely\b",
        r"\bexclusively\b",
    ),
    "timing": (
        r"\bbefore\b",
        r"\bprior\s+to\b",
        r"\bafter\b",
    ),
    "dependency": (
        r"\bwithout\b",
    ),
}


def _policy_constraints(text):
    """Return explicit policy-critical constraint categories present in text."""
    lowered = text.casefold()
    found = set()

    for category, patterns in _POLICY_CONSTRAINT_PATTERNS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            found.add(category)

    # Negative obligation is treated as prohibition, not positive obligation.
    if "prohibition" in found:
        found.discard("mandatory")

    return found


def preserves_policy_constraints(claim, supporting_quotes):
    """Reject paraphrases that drop or weaken explicit policy constraints."""
    premise = " ".join(quote.strip() for quote in supporting_quotes)
    evidence_constraints = _policy_constraints(premise)
    claim_constraints = _policy_constraints(claim)

    missing = evidence_constraints - claim_constraints

    weakened = (
        "mandatory" in evidence_constraints
        and "permission" in claim_constraints
        and "mandatory" not in claim_constraints
    )

    return not missing and not weakened, {
        "evidence_constraints": sorted(evidence_constraints),
        "claim_constraints": sorted(claim_constraints),
        "missing_constraints": sorted(missing),
        "weakened": weakened,
    }
