"""
Isolated runtime bridge for the validated RCV-03E-18H extractor.

This module is executed by the dedicated .rcv_stanza_venv interpreter.

Single-question input:
    {"question": "..."}
Single-question output:
    {"requirements": [...]}

Batch input:
    {"questions": ["...", "..."]}
Batch output:
    {"results": [{"requirements": [...]}, ...]}
"""

import contextlib
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
RCV_18H_SOURCE = ROOT / "rcv_unified_integration_03e18h.py"

CENSUS_BOUNDARY = (
    "# ---------------------------------------------------------------------------\n"
    "# 7. Load frozen real-census CASES without executing 03E-01."
)


def load_validated_extractor():
    source = RCV_18H_SOURCE.read_text(encoding="utf-8-sig")

    if source.count(CENSUS_BOUNDARY) != 1:
        raise RuntimeError(
            "RCV-03E-18H runtime boundary mismatch."
        )

    extractor_source = source.split(
        CENSUS_BOUNDARY,
        1,
    )[0]

    namespace = {
        "__name__": "lex_rcv_03e18h_runtime",
        "__file__": str(RCV_18H_SOURCE),
    }

    # Frozen experimental definitions emit diagnostic text while loading.
    # stdout must remain clean because it is the JSON IPC channel.
    with contextlib.redirect_stdout(io.StringIO()):
        exec(
            compile(
                extractor_source,
                str(RCV_18H_SOURCE),
                "exec",
            ),
            namespace,
        )

    nlp = namespace.get("nlp")
    extractor = namespace.get("extract_03e17_sentence")

    if not callable(nlp):
        raise RuntimeError(
            "Validated RCV Stanza pipeline unavailable."
        )

    if not callable(extractor):
        raise RuntimeError(
            "Validated RCV extractor unavailable."
        )

    return nlp, extractor


def extract_question(question, nlp, extractor):
    question = str(question or "").strip()

    if not question:
        return []

    requirements = []

    doc = nlp(question)

    for sentence in doc.sentences:
        requirements.extend(
            extractor(sentence)
        )

    return requirements


def analyse_claims(texts, owners, nlp):
    """
    Return bounded linguistic observations for validated claim text.

    This layer reports syntax only. It does not decide requirement coverage.
    """
    if not isinstance(texts, list):
        raise RuntimeError(
            "RCV claim analysis 'texts' must be a list."
        )

    if not isinstance(owners, list):
        raise RuntimeError(
            "RCV claim analysis 'owners' must be a list."
        )

    normalised_owners = {
        str(owner or "").casefold().strip()
        for owner in owners
        if str(owner or "").strip()
    }

    analyses = []

    for text in texts:
        claim_text = str(text or "").strip()
        observations = []

        if claim_text:
            doc = nlp(claim_text)

            for sentence in doc.sentences:
                for word in sentence.words:
                    lemma = str(word.lemma or "").casefold().strip()

                    if (
                        word.upos != "VERB"
                        or lemma not in normalised_owners
                    ):
                        continue

                    answer_relations = [
                        child.deprel
                        for child in sentence.words
                        if (
                            child.head == word.id
                            and child.deprel in {"obj", "xcomp"}
                        )
                    ]

                    observations.append({
                        "owner": lemma,
                        "predicate_relation": word.deprel,
                        "answer_relations": answer_relations,
                        "answer_present": bool(answer_relations),
                    })

        analyses.append({
            "text": claim_text,
            "observations": observations,
        })

    return analyses


def main():
    payload = json.load(sys.stdin)
    if "coverage_analysis" in payload:
        request = payload.get("coverage_analysis")

        if not isinstance(request, dict):
            raise RuntimeError(
                "RCV 'coverage_analysis' must be an object."
            )

        question = str(
            request.get("question") or ""
        ).strip()

        texts = request.get("texts")

        if not isinstance(texts, list):
            raise RuntimeError(
                "RCV coverage analysis 'texts' must be a list."
            )

        nlp, extractor = load_validated_extractor()

        requirements = (
            extract_question(
                question,
                nlp,
                extractor,
            )
            if question
            else []
        )

        owner_counts = {}

        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue

            kind = str(
                requirement.get("kind") or ""
            ).casefold().strip()

            owner = str(
                requirement.get("owner") or ""
            ).casefold().strip()

            gap = str(
                requirement.get("gap") or ""
            ).casefold().strip()

            if kind == "open" and owner and gap == "what":
                owner_counts[owner] = owner_counts.get(owner, 0) + 1

        owners = [
            owner
            for owner, count in owner_counts.items()
            if count == 1
        ]

        analyses = (
            analyse_claims(
                texts,
                owners,
                nlp,
            )
            if owners
            else []
        )

        json.dump(
            {
                "requirements": requirements,
                "analyses": analyses,
            },
            sys.stdout,
            ensure_ascii=False,
        )
        return

    if "claim_analysis" in payload:
        request = payload.get("claim_analysis")

        if not isinstance(request, dict):
            raise RuntimeError(
                "RCV 'claim_analysis' must be an object."
            )

        texts = request.get("texts")
        owners = request.get("owners")

        nlp, _extractor = load_validated_extractor()

        json.dump(
            {
                "analyses": analyse_claims(
                    texts,
                    owners,
                    nlp,
                )
            },
            sys.stdout,
            ensure_ascii=False,
        )
        return

    if "questions" in payload:
        questions = payload.get("questions")

        if not isinstance(questions, list):
            raise RuntimeError(
                "RCV batch input 'questions' must be a list."
            )

        if not questions:
            json.dump(
                {"results": []},
                sys.stdout,
            )
            return

        nlp, extractor = load_validated_extractor()

        results = [
            {
                "requirements": extract_question(
                    question,
                    nlp,
                    extractor,
                )
            }
            for question in questions
        ]

        json.dump(
            {"results": results},
            sys.stdout,
            ensure_ascii=False,
        )
        return

    question = str(
        payload.get("question") or ""
    ).strip()

    if not question:
        json.dump(
            {"requirements": []},
            sys.stdout,
        )
        return

    nlp, extractor = load_validated_extractor()

    requirements = extract_question(
        question,
        nlp,
        extractor,
    )

    json.dump(
        {"requirements": requirements},
        sys.stdout,
        ensure_ascii=False,
    )


if __name__ == "__main__":
    main()
