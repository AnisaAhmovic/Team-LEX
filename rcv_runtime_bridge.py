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


def _nominal_copular_definition_owner(sentence):
    """
    Return the owner lemma for the bounded simple nominal-copular
    definition-question shape, otherwise None.

    This preserves linguistic evidence already established by the RCV
    extractor family without changing the frozen extractor itself.
    """
    for word in sentence.words:
        if (
            word.upos != "PRON"
            or str(word.lemma or "").casefold().strip() != "what"
            or word.deprel not in {"root", "conj"}
        ):
            continue

        children = [
            child
            for child in sentence.words
            if child.head == word.id
        ]

        if not any(child.deprel == "cop" for child in children):
            continue

        nominal_subjects = [
            child
            for child in children
            if (
                child.deprel.startswith("nsubj")
                and child.upos in {"NOUN", "PROPN"}
            )
        ]

        if len(nominal_subjects) == 1:
            return str(
                nominal_subjects[0].lemma
                or nominal_subjects[0].text
                or ""
            ).casefold().strip()

    return None


def _nominal_copular_purpose_owner(sentence):
    """
    Return the owner lemma for the bounded relational PURPOSE question shape.

    Qualified shape:
        What is the purpose of X?

    The outer copular structure matches a nominal definition question, but
    the requested nominal owner must also govern an nmod identifying whose
    purpose is being requested.
    """
    for word in sentence.words:
        if (
            word.upos != "PRON"
            or str(word.lemma or "").casefold().strip() != "what"
            or word.deprel not in {"root", "conj"}
        ):
            continue

        children = [
            child
            for child in sentence.words
            if child.head == word.id
        ]

        if not any(
            child.deprel == "cop"
            and str(child.lemma or "").casefold().strip() == "be"
            for child in children
        ):
            continue

        nominal_subjects = [
            child
            for child in children
            if (
                child.deprel.startswith("nsubj")
                and child.upos in {"NOUN", "PROPN"}
                and str(child.lemma or "").casefold().strip() == "purpose"
            )
        ]

        if len(nominal_subjects) != 1:
            continue

        subject = nominal_subjects[0]

        has_relational_nmod = any(
            child.head == subject.id
            and child.deprel == "nmod"
            for child in sentence.words
        )

        if has_relational_nmod:
            return str(
                subject.lemma
                or subject.text
                or ""
            ).casefold().strip()

    return None


def _conditional_condition_signature(sentence):
    """
    Return a conservative structural signature for one explicit if-condition.

    The signature preserves the subordinate predicate plus its nominal
    dependency hierarchy. It reports syntax only; coverage is decided by
    api.requirement_coverage.
    """
    roots = [
        word
        for word in sentence.words
        if word.upos == "VERB" and word.deprel == "root"
    ]

    if len(roots) != 1:
        return None

    root = roots[0]

    conditions = [
        word
        for word in sentence.words
        if word.head == root.id
        and word.deprel == "advcl"
        and any(
            child.head == word.id
            and child.deprel == "mark"
            and str(child.lemma or "").casefold().strip() == "if"
            for child in sentence.words
        )
    ]

    if len(conditions) != 1:
        return None

    condition = conditions[0]

    subjects = [
        word
        for word in sentence.words
        if word.head == condition.id
        and word.deprel in {"nsubj", "nsubj:pass"}
    ]

    if len(subjects) != 1:
        return None

    subject = subjects[0]

    def nominal_children(parent):
        children = []

        for child in sentence.words:
            if child.head != parent.id:
                continue

            if child.upos not in {"NOUN", "PROPN"}:
                continue

            if child.deprel not in {"nmod", "compound"}:
                continue

            children.append({
                "lemma": str(child.lemma or "").casefold().strip(),
                "relation": child.deprel,
                "children": nominal_children(child),
            })

        return children

    return {
        "predicate": str(condition.lemma or "").casefold().strip(),
        "subject": str(subject.lemma or "").casefold().strip(),
        "subject_relation": subject.deprel,
        "subject_children": nominal_children(subject),
    }


def _conditional_action_owner(sentence):
    """
    Return the owner lemma for a bounded CONDITIONAL_ACTION question.

    Qualified shape: root verbal predicate governing exactly one advcl
    whose subordinate predicate is explicitly marked by "if".

    Classification only; this does not decide claim fulfilment.
    """
    for word in sentence.words:
        if word.upos != "VERB" or word.deprel != "root":
            continue

        conditional_predicates = [
            child
            for child in sentence.words
            if (
                child.head == word.id
                and child.deprel == "advcl"
                and any(
                    marker.head == child.id
                    and marker.deprel == "mark"
                    and str(marker.lemma or "").casefold().strip() == "if"
                    for marker in sentence.words
                )
            )
        ]

        if len(conditional_predicates) == 1:
            return str(
                word.lemma or word.text or ""
            ).casefold().strip()

    return None


def extract_question(question, nlp, extractor):
    question = str(question or "").strip()

    if not question:
        return []

    requirements = []
    doc = nlp(question)

    for sentence in doc.sentences:
        sentence_requirements = list(extractor(sentence))
        definition_owner = _nominal_copular_definition_owner(sentence)
        purpose_owner = _nominal_copular_purpose_owner(sentence)
        conditional_action_owner = _conditional_action_owner(sentence)

        for requirement in sentence_requirements:
            item = dict(requirement)

            if (
                conditional_action_owner
                and str(item.get("kind") or "").casefold().strip() == "open"
                and str(item.get("owner") or "").casefold().strip()
                    == conditional_action_owner
                and str(item.get("gap") or "").casefold().strip() == "what"
            ):
                item["requirement_type"] = "conditional_action"
                condition_signature = _conditional_condition_signature(sentence)

                if condition_signature is not None:
                    item["condition_signature"] = condition_signature

            elif (
                purpose_owner
                and str(item.get("kind") or "").casefold().strip() == "open"
                and str(item.get("owner") or "").casefold().strip()
                    == purpose_owner
                and str(item.get("gap") or "").casefold().strip() == "what"
            ):
                item["requirement_type"] = "purpose"

            elif (
                definition_owner
                and str(item.get("kind") or "").casefold().strip() == "open"
                and str(item.get("owner") or "").casefold().strip()
                    == definition_owner
                and str(item.get("gap") or "").casefold().strip() == "what"
            ):
                item["requirement_type"] = "definition"

            requirements.append(item)

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

        definition_observations = []

        if claim_text:
            for sentence in doc.sentences:
                for subject in sentence.words:
                    subject_lemma = str(
                        subject.lemma or ""
                    ).casefold().strip()

                    if (
                        subject_lemma not in normalised_owners
                        or subject.upos not in {"NOUN", "PROPN"}
                        or subject.deprel != "nsubj"
                    ):
                        continue

                    predicate = next(
                        (
                            word
                            for word in sentence.words
                            if word.id == subject.head
                        ),
                        None,
                    )

                    if predicate is None:
                        continue

                    predicate_children = [
                        child
                        for child in sentence.words
                        if child.head == predicate.id
                    ]

                    has_copula = any(
                        child.deprel == "cop"
                        and str(
                            child.lemma or ""
                        ).casefold().strip() == "be"
                        for child in predicate_children
                    )

                    if (
                        has_copula
                        and predicate.upos in {"NOUN", "PROPN"}
                    ):
                        definition_observations.append({
                            "owner": subject_lemma,
                            "predicate_relation": predicate.deprel,
                            "copular_definition": True,
                        })

        purpose_observations = []

        if claim_text and "purpose" in normalised_owners:
            for sentence in doc.sentences:
                for subject in sentence.words:
                    subject_lemma = str(
                        subject.lemma or ""
                    ).casefold().strip()

                    if (
                        subject_lemma != "purpose"
                        or subject.upos not in {"NOUN", "PROPN"}
                        or subject.deprel != "nsubj:outer"
                    ):
                        continue

                    has_relational_nmod = any(
                        child.head == subject.id
                        and child.deprel == "nmod"
                        for child in sentence.words
                    )

                    if not has_relational_nmod:
                        continue

                    predicate = next(
                        (
                            word
                            for word in sentence.words
                            if word.id == subject.head
                        ),
                        None,
                    )

                    if (
                        predicate is None
                        or predicate.upos != "VERB"
                    ):
                        continue

                    predicate_children = [
                        child
                        for child in sentence.words
                        if child.head == predicate.id
                    ]

                    has_copula = any(
                        child.deprel == "cop"
                        and str(
                            child.lemma or ""
                        ).casefold().strip() == "be"
                        for child in predicate_children
                    )

                    has_infinitival_marker = any(
                        child.deprel == "mark"
                        and str(
                            child.lemma or ""
                        ).casefold().strip() == "to"
                        for child in predicate_children
                    )

                    if has_copula and has_infinitival_marker:
                        purpose_observations.append({
                            "owner": subject_lemma,
                            "predicate_relation": predicate.deprel,
                            "purpose_answer": True,
                        })

        conditional_action_observations = []

        if claim_text:
            for sentence in doc.sentences:
                condition_signature = _conditional_condition_signature(sentence)

                if condition_signature is None:
                    continue

                roots = [
                    word
                    for word in sentence.words
                    if word.upos == "VERB" and word.deprel == "root"
                ]

                if len(roots) != 1:
                    continue

                root = roots[0]

                conditional_action_observations.append({
                    "condition_signature": condition_signature,
                    "consequence_owner": str(
                        root.lemma or ""
                    ).casefold().strip(),
                    "consequence_present": True,
                })

        analyses.append({
            "text": claim_text,
            "observations": observations,
            "definition_observations": definition_observations,
            "purpose_observations": purpose_observations,
            "conditional_action_observations": (
                conditional_action_observations
            ),
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
