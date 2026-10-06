import stanza
import time

QUESTIONS = [
    ("S1", "What must staff and students avoid, and how long may publication be delayed once Exploitable IP is declared?", 2),
    ("S2", "Can I approve my own procurement, and who must provide approval instead?", 2),
    ("S3", "When Exploitable IP is declared, what will the University do and how long can publication be delayed?", 2),
    ("S4", "Are all health and safety incidents investigated, and what determines the level of investigation?", 2),
    ("S5", "What requirements apply when conducting research involving humans, who do they apply to, and what approvals must be obtained?", 3),
    ("S6", "I'm doing research that might have commercial value. Is there anything I shouldn't publish yet, and if publication gets held up, how long can they normally delay it?", 2),
    ("S7", "For a procurement activity, can an authorised signatory approve their own recommendation, who must approve it instead, and when must that approval be obtained?", 3),
    ("S8", "Are all health and safety incidents investigated, what determines the level of investigation, and when are Community Sport injuries excluded from investigation?", 3),
]

WH_WORDS = {"what", "who", "whom", "whose", "which", "when", "where", "why", "how"}

QUESTION_AUX = {
    "be", "can", "could", "do", "does", "did",
    "may", "might", "must", "shall", "should",
    "will", "would",
}


def descendants(sentence, root_id):
    """Return all dependency descendants of root_id, including root_id."""
    children = {}
    for word in sentence.words:
        children.setdefault(word.head, []).append(word.id)

    found = set()
    stack = [root_id]

    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(children.get(current, []))

    return found


def words_by_ids(sentence, ids):
    return [word for word in sentence.words if word.id in ids]


def text_by_ids(sentence, ids):
    words = words_by_ids(sentence, ids)
    return " ".join(word.text for word in words)


def is_question_sentence(sentence):
    return sentence.text.rstrip().endswith("?")


def root_word(sentence):
    return next(word for word in sentence.words if word.head == 0)


def candidate_predicates(sentence):
    """
    Structural POC only.

    Start from the sentence root and top-level verbal structures attached
    through coordination/parataxis. Do not classify semantic requirement type.
    """
    root = root_word(sentence)
    candidates = [root]

    changed = True
    while changed:
        changed = False

        candidate_ids = {word.id for word in candidates}

        for word in sentence.words:
            if (
                word.id not in candidate_ids
                and word.upos in {"VERB", "AUX"}
                and word.deprel in {"conj", "parataxis"}
                and word.head in candidate_ids
            ):
                candidates.append(word)
                changed = True

    # Also admit top-level verbal interrogative structures whose head is
    # already inside a candidate subtree and which carry an explicit WH cue.
    candidate_ids = {word.id for word in candidates}

    for word in sentence.words:
        if word.id in candidate_ids or word.upos not in {"VERB", "AUX"}:
            continue

        subtree = descendants(sentence, word.id)

        has_wh = any(
            child.text.casefold() in WH_WORDS
            for child in words_by_ids(sentence, subtree)
        )

        if has_wh and word.deprel in {"acl:relcl", "conj", "parataxis"}:
            candidates.append(word)

    # Preserve sentence order.
    return sorted(
        {word.id: word for word in candidates}.values(),
        key=lambda word: word.id,
    )


def interrogative_features(sentence, predicate):
    subtree = descendants(sentence, predicate.id)
    subtree_words = words_by_ids(sentence, subtree)

    wh = [
        word.text
        for word in subtree_words
        if word.text.casefold() in WH_WORDS
    ]

    modals = [
        word.text
        for word in subtree_words
        if (
            word.upos == "AUX"
            or word.lemma.casefold() in QUESTION_AUX
        )
    ]

    subjects = [
        word.text
        for word in subtree_words
        if word.deprel.startswith("nsubj")
    ]

    objects = [
        word.text
        for word in subtree_words
        if word.deprel in {"obj", "iobj", "obl"}
    ]

    conditions = []

    for word in sentence.words:
        if word.deprel == "advcl":
            condition_ids = descendants(sentence, word.id)
            condition_words = words_by_ids(sentence, condition_ids)

            markers = [
                item.text.casefold()
                for item in condition_words
                if item.deprel == "mark"
                or item.text.casefold() in {"when", "if", "once", "unless"}
            ]

            if markers:
                conditions.append(text_by_ids(sentence, condition_ids))

    return {
        "predicate": predicate.text,
        "lemma": predicate.lemma,
        "deprel": predicate.deprel,
        "wh": wh,
        "modal_aux": modals,
        "subjects": subjects,
        "objects_or_obliques": objects,
        "conditions_detected": conditions,
        "subtree_text": text_by_ids(sentence, subtree),
    }


print("=== RCV-01A-08B: STRUCTURE-ONLY REQUIREMENT CANDIDATES ===")
print()

start = time.perf_counter()

nlp = stanza.Pipeline(
    "en",
    processors="tokenize,pos,lemma,depparse,constituency",
    use_gpu=False,
    verbose=False,
)

print(f"Pipeline load: {time.perf_counter() - start:.3f}s")
print()

results = []

for case_id, question, expected in QUESTIONS:
    print("=" * 100)
    print(case_id)
    print("QUESTION:", question)
    print("EXPECTED REQUIREMENTS:", expected)

    doc = nlp(question)

    all_candidates = []

    for sentence_number, sentence in enumerate(doc.sentences, start=1):
        print()
        print(f"SENTENCE {sentence_number}: {sentence.text}")

        if not is_question_sentence(sentence):
            print("  Declarative/context sentence — no requirement candidates.")
            continue

        predicates = candidate_predicates(sentence)

        for predicate in predicates:
            features = interrogative_features(sentence, predicate)

            # A root predicate in a question is retained even without a WH cue:
            # this captures yes/no interrogatives such as "Can I approve...?"
            # Non-root candidates need structural interrogative evidence.
            if (
                predicate.deprel != "root"
                and not features["wh"]
                and not features["modal_aux"]
            ):
                continue

            all_candidates.append(
                (sentence_number, predicate.id, features)
            )

    print()
    print(f"FOUND CANDIDATES: {len(all_candidates)}")

    for index, (sentence_number, predicate_id, features) in enumerate(
        all_candidates,
        start=1,
    ):
        print()
        print(f"  R{index}")
        print(f"    sentence:             {sentence_number}")
        print(f"    predicate_id:         {predicate_id}")
        print(f"    predicate:            {features['predicate']}")
        print(f"    lemma:                {features['lemma']}")
        print(f"    dependency:           {features['deprel']}")
        print(f"    WH cue(s):            {features['wh']}")
        print(f"    modal/aux:            {features['modal_aux']}")
        print(f"    subject(s):           {features['subjects']}")
        print(f"    object/oblique(s):    {features['objects_or_obliques']}")
        print(f"    condition(s):         {features['conditions_detected']}")
        print(f"    subtree:              {features['subtree_text']}")

    count_match = len(all_candidates) == expected

    print()
    print(
        "COUNT RESULT:",
        "PASS" if count_match else "FAIL",
        f"(expected {expected}, found {len(all_candidates)})",
    )

    results.append((case_id, expected, len(all_candidates), count_match))

print()
print("=" * 100)
print("SUMMARY")
print()

passes = 0

for case_id, expected, found, passed in results:
    status = "PASS" if passed else "FAIL"
    passes += int(passed)
    print(
        f"{case_id}: {status} "
        f"(expected {expected}, found {found})"
    )

print()
print(f"COUNT MATCHES: {passes}/{len(results)}")
print()
print("IMPORTANT: Count matches alone do not establish correct requirement boundaries.")
print("Manual structural review is still required.")
print()
print("RCV-01A-08B COMPLETE")

# =============================================================================
# RCV-01A-08F
# Constituency-assisted promotion of independent interrogative ADVCL predicates.
#
# This deliberately does NOT promote ADVCL generally.
# An ADVCL predicate is admitted only when its token belongs to an SQ
# constituency that is not itself contained within a subordinate SBAR.
# =============================================================================

def tree_leaf_spans(node, start=0, ancestors=()):
    """
    Yield constituency nodes with their half-open leaf spans and ancestry.

    Returns tuples:
        (node, start_leaf, end_leaf, ancestors)
    """
    children = getattr(node, "children", None) or []

    if not children:
        return start + 1, []

    cursor = start
    records = []

    for child in children:
        child_end, child_records = tree_leaf_spans(
            child,
            cursor,
            ancestors + (node,),
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


def independent_sq_token_positions(sentence):
    """
    Return 1-based token positions belonging to independent SQ constituents.

    An SQ is considered subordinate contextual material when one of its
    ancestors is an SBAR.

    This is a structural POC rule, not a semantic classifier.
    """
    _, records = tree_leaf_spans(sentence.constituency)

    positions = set()

    for node, start, end, ancestors in records:
        if getattr(node, "label", None) != "SQ":
            continue

        ancestor_labels = [
            getattr(ancestor, "label", None)
            for ancestor in ancestors
        ]

        if "SBAR" in ancestor_labels:
            continue

        # Constituency leaves include punctuation and follow sentence order.
        # Convert zero-based half-open leaf span to one-based positions.
        positions.update(
            range(start + 1, end + 1)
        )

    return positions


def candidate_predicates_08f(sentence):
    """
    Existing 08B detector plus one evidence-based extension:

    promote ADVCL only when the predicate token occurs inside an
    independent interrogative SQ constituency.
    """
    candidates = candidate_predicates(sentence)
    candidate_ids = {word.id for word in candidates}

    sq_positions = independent_sq_token_positions(sentence)

    for word in sentence.words:
        if word.id in candidate_ids:
            continue

        if word.upos not in {"VERB", "AUX"}:
            continue

        if (
            word.deprel == "advcl"
            and word.id in sq_positions
        ):
            candidates.append(word)

    return sorted(
        {word.id: word for word in candidates}.values(),
        key=lambda word: word.id,
    )


print()
print("=" * 100)
print("RCV-01A-08F: CONSTITUENCY-ASSISTED ADVCL PROMOTION")
print()

results_08f = []

for case_id, question, expected in QUESTIONS:
    print("=" * 100)
    print(case_id)
    print("QUESTION:", question)
    print("EXPECTED REQUIREMENTS:", expected)

    doc = nlp(question)
    all_candidates = []

    for sentence_number, sentence in enumerate(doc.sentences, start=1):
        if not is_question_sentence(sentence):
            print(
                f"  Sentence {sentence_number}: "
                "declarative/context — ignored"
            )
            continue

        predicates = candidate_predicates_08f(sentence)

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

            all_candidates.append(
                (
                    sentence_number,
                    predicate.id,
                    predicate.text,
                    predicate.deprel,
                )
            )

    print("CANDIDATES:")

    for index, candidate in enumerate(
        all_candidates,
        start=1,
    ):
        sentence_number, word_id, text, deprel = candidate
        print(
            f"  R{index}: "
            f"sentence={sentence_number} "
            f"id={word_id} "
            f"predicate={text!r} "
            f"deprel={deprel}"
        )

    passed = len(all_candidates) == expected

    print(
        "COUNT RESULT:",
        "PASS" if passed else "FAIL",
        f"(expected {expected}, found {len(all_candidates)})",
    )
    print()

    results_08f.append(
        (
            case_id,
            expected,
            len(all_candidates),
            passed,
        )
    )

print("=" * 100)
print("08F SUMMARY")
print()

passes_08f = 0

for case_id, expected, found, passed in results_08f:
    passes_08f += int(passed)

    print(
        f"{case_id}: "
        f"{'PASS' if passed else 'FAIL'} "
        f"(expected {expected}, found {found})"
    )

print()
print(
    f"COUNT MATCHES: "
    f"{passes_08f}/{len(results_08f)}"
)
print()
print(
    "NOTE: 8/8 count is necessary but not sufficient. "
    "Boundary regression must still be checked."
)
print()
print("RCV-01A-08F COMPLETE")
