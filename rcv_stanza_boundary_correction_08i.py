exec(
    open(
        "rcv_stanza_requirement_candidates_08f.py",
        encoding="utf-8-sig",
    ).read()
)

print()
print("=" * 100)
print("RCV-01A-08I: PROMOTED-CANDIDATE BOUNDARY CORRECTION")
print()


def isolated_dependency_ids(
    sentence,
    predicate,
    all_predicates,
):
    own_ids = descendants(
        sentence,
        predicate.id,
    )

    for other in all_predicates:
        if other.id == predicate.id:
            continue

        if other.id in own_ids:
            own_ids -= descendants(
                sentence,
                other.id,
            )

    return own_ids


def constituency_leaf_records(
    node,
    start=0,
    ancestors=(),
):
    children = getattr(
        node,
        "children",
        None,
    ) or []

    if not children:
        return start + 1, []

    cursor = start
    records = []

    for child in children:
        child_end, child_records = (
            constituency_leaf_records(
                child,
                cursor,
                ancestors + (node,),
            )
        )

        cursor = child_end
        records.extend(child_records)

    records.append(
        (
            node,
            start,
            cursor,
            ancestors,
        )
    )

    return cursor, records


def independent_sq_spans(sentence):
    _, records = constituency_leaf_records(
        sentence.constituency
    )

    spans = []

    for node, start, end, ancestors in records:
        if getattr(node, "label", None) != "SQ":
            continue

        ancestor_labels = [
            getattr(ancestor, "label", None)
            for ancestor in ancestors
        ]

        if "SBAR" in ancestor_labels:
            continue

        spans.append(
            {
                "start": start + 1,
                "end": end,
                "text": " ".join(
                    node.leaf_labels()
                ),
            }
        )

    return spans


def original_candidate_ids(sentence):
    return {
        word.id
        for word in candidate_predicates(
            sentence
        )
    }


def corrected_boundary(
    sentence,
    predicate,
    all_predicates,
):
    original_ids = original_candidate_ids(
        sentence
    )

    # Ordinary dependency-discovered candidates retain
    # the already-tested dependency isolation path.
    if predicate.id in original_ids:
        ids = isolated_dependency_ids(
            sentence,
            predicate,
            all_predicates,
        )

        words = words_by_ids(
            sentence,
            ids,
        )

        return {
            "source": "dependency",
            "text": " ".join(
                word.text
                for word in words
                if word.upos != "PUNCT"
            ),
        }

    # Only candidates newly promoted by 08F are eligible
    # for constituency-supplied boundary correction.
    for span in independent_sq_spans(sentence):
        if (
            span["start"]
            <= predicate.id
            <= span["end"]
        ):
            return {
                "source": "constituency",
                "text": span["text"],
            }

    # Diagnostic fallback: should not occur in frozen suite.
    return {
        "source": "UNRESOLVED",
        "text": predicate.text,
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

        for predicate in retained:
            boundary = corrected_boundary(
                sentence,
                predicate,
                retained,
            )

            requirements.append(
                {
                    "predicate": predicate.text,
                    "deprel": predicate.deprel,
                    "source": boundary["source"],
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
            f"  text:     {requirement['text']}"
        )

    passed = len(requirements) == expected

    summary.append(
        (
            case_id,
            expected,
            len(requirements),
            passed,
        )
    )

    print()
    print(
        "COUNT:",
        "PASS" if passed else "FAIL",
        f"(expected {expected}, "
        f"found {len(requirements)})",
    )

print()
print("=" * 100)
print("08I SUMMARY")
print()

passes = 0

for case_id, expected, found, passed in summary:
    passes += int(passed)

    print(
        f"{case_id}: "
        f"{'PASS' if passed else 'FAIL'} "
        f"(expected {expected}, found {found})"
    )

print()
print(
    f"COUNT MATCHES: "
    f"{passes}/{len(summary)}"
)
print()
print(
    "MANUAL CHECK: S8 R1 must use constituency boundary "
    "and read 'Are all health and safety incidents investigated'."
)
print()
print(
    "MANUAL CHECK: S1-S7 must remain on dependency boundaries."
)
print()
print("RCV-01A-08I COMPLETE")
