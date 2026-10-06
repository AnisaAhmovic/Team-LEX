exec(
    open(
        "rcv_stanza_boundary_correction_08i.py",
        encoding="utf-8-sig",
    ).read()
)

print()
print("=" * 100)
print("RCV-01A-08J: EXCLUSIVE BOUNDARY OWNERSHIP")
print()


def promoted_constituency_ownership(
    sentence,
    predicates,
):
    """
    Return token IDs exclusively owned by candidates that were
    introduced by the constituency-assisted 08F promotion.

    Mapping is recorded per promoted predicate.
    """
    original_ids = original_candidate_ids(sentence)
    ownership = {}

    for predicate in predicates:
        if predicate.id in original_ids:
            continue

        for span in independent_sq_spans(sentence):
            if (
                span["start"]
                <= predicate.id
                <= span["end"]
            ):
                ownership[predicate.id] = set(
                    range(
                        span["start"],
                        span["end"] + 1,
                    )
                )
                break

    return ownership


def corrected_boundary_08j(
    sentence,
    predicate,
    all_predicates,
    promoted_ownership,
):
    # Promoted candidate: use the constituency span that
    # justified its introduction.
    if predicate.id in promoted_ownership:
        owned_ids = promoted_ownership[predicate.id]

        words = words_by_ids(
            sentence,
            owned_ids,
        )

        return {
            "source": "constituency",
            "ids": owned_ids,
            "text": " ".join(
                word.text
                for word in words
                if word.upos != "PUNCT"
            ),
        }

    # Ordinary candidate: retain dependency isolation.
    ids = isolated_dependency_ids(
        sentence,
        predicate,
        all_predicates,
    )

    # A constituency-promoted requirement has exclusive
    # ownership of its structural clause span. Remove those
    # tokens from every other requirement boundary.
    for promoted_id, owned_ids in (
        promoted_ownership.items()
    ):
        if promoted_id == predicate.id:
            continue

        ids -= owned_ids

    words = words_by_ids(
        sentence,
        ids,
    )

    return {
        "source": "dependency",
        "ids": ids,
        "text": " ".join(
            word.text
            for word in words
            if word.upos != "PUNCT"
        ),
    }


summary = []

for case_id, question, expected in QUESTIONS:
    print("=" * 100)
    print(case_id)
    print("QUESTION:", question)

    doc = nlp(question)
    requirements = []

    for sentence_number, sentence in enumerate(
        doc.sentences,
        start=1,
    ):
        if not is_question_sentence(sentence):
            print(
                f"CONTEXT SENTENCE {sentence_number}: "
                f"{sentence.text}"
            )
            continue

        predicates = candidate_predicates_08f(
            sentence
        )

        retained = []

        for predicate in predicates:
            features = interrogative_features(
                sentence,
                predicate,
            )

            if (
                predicate.deprel != "root"
                and predicate.deprel != "advcl"
                and not features["wh"]
                and not features["modal_aux"]
            ):
                continue

            retained.append(predicate)

        ownership = promoted_constituency_ownership(
            sentence,
            retained,
        )

        for predicate in retained:
            boundary = corrected_boundary_08j(
                sentence,
                predicate,
                retained,
                ownership,
            )

            requirements.append(
                {
                    "predicate": predicate.text,
                    "deprel": predicate.deprel,
                    "source": boundary["source"],
                    "ids": sorted(boundary["ids"]),
                    "text": boundary["text"],
                }
            )

    for index, requirement in enumerate(
        requirements,
        start=1,
    ):
        print()
        print(f"R{index}")
        print(
            f"  predicate: {requirement['predicate']}"
        )
        print(
            f"  deprel:   {requirement['deprel']}"
        )
        print(
            f"  boundary: {requirement['source']}"
        )
        print(
            f"  ids:      {requirement['ids']}"
        )
        print(
            f"  text:     {requirement['text']}"
        )

    # Check for overlapping ownership between final
    # requirement boundaries.
    overlaps = []

    for left in range(len(requirements)):
        for right in range(
            left + 1,
            len(requirements),
        ):
            overlap = (
                set(requirements[left]["ids"])
                & set(requirements[right]["ids"])
            )

            if overlap:
                overlaps.append(
                    (
                        left + 1,
                        right + 1,
                        sorted(overlap),
                    )
                )

    if overlaps:
        print()
        print("OVERLAPS:", overlaps)
    else:
        print()
        print("OVERLAPS: none")

    count_pass = (
        len(requirements) == expected
    )

    ownership_pass = not overlaps

    passed = (
        count_pass
        and ownership_pass
    )

    print(
        "RESULT:",
        "PASS" if passed else "FAIL",
        f"(expected {expected}, "
        f"found {len(requirements)}, "
        f"overlaps={len(overlaps)})",
    )

    summary.append(
        (
            case_id,
            expected,
            len(requirements),
            len(overlaps),
            passed,
        )
    )

print()
print("=" * 100)
print("08J SUMMARY")
print()

passes = 0

for (
    case_id,
    expected,
    found,
    overlaps,
    passed,
) in summary:
    passes += int(passed)

    print(
        f"{case_id}: "
        f"{'PASS' if passed else 'FAIL'} "
        f"(expected {expected}, "
        f"found {found}, "
        f"overlaps={overlaps})"
    )

print()
print(
    f"STRUCTURAL MATCHES: "
    f"{passes}/{len(summary)}"
)
print()
print(
    "MANUAL CHECK S8:"
)
print(
    "R1 = Are all health and safety incidents investigated"
)
print(
    "R2 = what determines the level of investigation"
)
print(
    "R3 = when are Community Sport injuries excluded "
    "from investigation"
)
print()
print(
    "No final requirement boundaries should overlap."
)
print()
print("RCV-01A-08J COMPLETE")
