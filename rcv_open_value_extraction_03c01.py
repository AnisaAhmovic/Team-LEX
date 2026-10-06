"""RCV-03C-01: Open-value information-gap extraction.

Architectural question:
Can genuine open-value information gaps be mechanically extracted from
frozen full LEX questions while contextual WH-like structures are excluded,
using general structural relationships rather than policy-specific phrases?

Scope:
- open-value gaps only
- polar BOOLEAN_STATUS requests deliberately excluded
- diagnostic only
- no production changes
- no 08J changes
- no policy/question-specific phrase rules
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_08J = ROOT / "rcv_stanza_boundary_ownership_08j.py"


def load_frozen_stanza_definitions():
    """Reuse the established Stanza pipeline without executing 08J tests."""
    lines = SOURCE_08J.read_text(
        encoding="utf-8-sig"
    ).splitlines()

    definition_source = "\n".join(lines[:105])

    namespace = {
        "__file__": str(SOURCE_08J),
        "__name__": "rcv_03c01_frozen_stanza",
    }

    exec(
        compile(
            definition_source,
            str(SOURCE_08J),
            "exec",
        ),
        namespace,
    )

    return namespace


CASES = [
    {
        "id": "T02",
        "question": (
            "Can I approve my own procurement "
            "if I have the right delegation?"
        ),
        # Polar request deliberately outside 03C-01.
        "expected": [],
    },
    {
        "id": "T04",
        "question": (
            "What must staff and students avoid "
            "when publishing research involving Exploitable IP?"
        ),
        "expected": [
            ("what", "avoid"),
        ],
    },
    {
        "id": "T08",
        "question": (
            "When publishing research involving Exploitable IP, "
            "what must staff and students avoid, "
            "and how long may publication be delayed "
            "once Exploitable IP is declared?"
        ),
        "expected": [
            ("what", "avoid"),
            ("how long", "delayed"),
        ],
    },
    {
        "id": "T13",
        "question": (
            "When publishing research involving Exploitable IP, "
            "what must staff and students avoid, "
            "what will the University do once it is declared, "
            "and how long may publication be delayed?"
        ),
        "expected": [
            ("what", "avoid"),
            ("what", "do"),
            ("how long", "delayed"),
        ],
    },
    {
        "id": "T17",
        "question": (
            "What should I do "
            "if I think my manager is treating me unfairly?"
        ),
        "expected": [
            ("what", "do"),
        ],
    },
    {
        "id": "P01",
        "question": (
            "Before a La Trobe procurement activity commences, "
            "what financial approval and budget requirements apply, "
            "what expenditure must be considered when seeking approval, "
            "and can an Authorised Signatory approve "
            "their own procurement recommendation?"
        ),
        "expected": [
            ("what financial approval and budget requirements", "apply"),
            ("what expenditure", "considered"),
        ],
    },
]


ns = load_frozen_stanza_definitions()
nlp = ns["nlp"]


def by_id(sentence):
    return {
        word.id: word
        for word in sentence.words
    }


def children(sentence, word_id):
    return [
        word
        for word in sentence.words
        if word.head == word_id
    ]


def ancestors(sentence, word):
    """Return ancestors from immediate head upward."""
    lookup = by_id(sentence)
    result = []

    current_head = word.head

    while current_head:
        parent = lookup[current_head]
        result.append(parent)
        current_head = parent.head

    return result


def is_inside_subordinate_clause(sentence, word):
    """
    Identify whether the WH token belongs to a subordinate clause.

    We do not classify words such as 'when' by vocabulary. Instead,
    inspect whether the token's governing path enters a subordinate
    predicate before reaching a principal proposition.
    """
    subordinate_relations = {
        "advcl",
        "acl",
        "acl:relcl",
        "ccomp",
        "xcomp",
    }

    for ancestor in ancestors(sentence, word):
        if ancestor.deprel in subordinate_relations:
            return True

    return False


def wh_phrase(sentence, word):
    """
    Recover the requested WH phrase without policy-specific vocabulary.

    Examples:
      what -> "what"
      what(det)->noun phrase -> "what expenditure"
      how -> "how long"
    """
    lookup = by_id(sentence)

    # Interrogative determiner: include the nominal phrase it determines.
    if word.deprel == "det" and word.head:
        noun = lookup[word.head]

        phrase_ids = {word.id, noun.id}

        for child in children(sentence, noun.id):
            if child.id < noun.id and child.deprel in {
                "amod",
                "compound",
                "conj",
                "cc",
            }:
                phrase_ids.add(child.id)

                # Include dependants of coordinated nominal material.
                for grandchild in children(sentence, child.id):
                    if grandchild.id < noun.id and grandchild.deprel in {
                        "amod",
                        "compound",
                        "cc",
                    }:
                        phrase_ids.add(grandchild.id)

        # For coordinated nominal phrases, include relevant material
        # attached to the first nominal head.
        for child in children(sentence, noun.id):
            if child.deprel == "conj":
                phrase_ids.add(child.id)

                for grandchild in children(sentence, child.id):
                    if grandchild.deprel in {
                        "amod",
                        "compound",
                        "cc",
                    }:
                        phrase_ids.add(grandchild.id)

        return " ".join(
            token.text.casefold()
            for token in sentence.words
            if token.id in phrase_ids
        )

    # "how long" and structurally similar WH-adverb combinations.
    if word.text.casefold() == "how":
        direct_children = children(
            sentence,
            word.id,
        )

        if direct_children:
            ids = {
                word.id,
                *[
                    child.id
                    for child in direct_children
                    if child.deprel == "advmod"
                ],
            }

            if len(ids) > 1:
                return " ".join(
                    token.text.casefold()
                    for token in sentence.words
                    if token.id in ids
                )

        # Stanza commonly analyses:
        # how -> long -> governing predicate.
        if word.head:
            head = lookup[word.head]

            if head.upos in {
                "ADV",
                "ADJ",
            }:
                return (
                    f"{word.text.casefold()} "
                    f"{head.text.casefold()}"
                )

    return word.text.casefold()


def governing_predicate(sentence, word):
    """
    Find the predicate whose proposition owns the requested gap.

    For 'how long', climb through the intermediate modifier.
    For WH determiners, start from their nominal head.
    Otherwise follow the dependency path upward.
    """
    lookup = by_id(sentence)

    current = word

    if word.deprel == "det" and word.head:
        current = lookup[word.head]

    visited = set()

    while current.head:
        if current.id in visited:
            break

        visited.add(current.id)
        parent = lookup[current.head]

        if parent.upos in {
            "VERB",
            "AUX",
        }:
            return parent

        current = parent

    if current.upos in {
        "VERB",
        "AUX",
    }:
        return current

    return None


def extract_open_value_gaps(sentence):
    results = []

    for word in sentence.words:
        if not (
            word.feats
            and "PronType=Int" in word.feats
        ):
            continue

        # 03C-01 asks whether structural ownership can exclude
        # contextual WH-like material.
        if is_inside_subordinate_clause(
            sentence,
            word,
        ):
            continue

        predicate = governing_predicate(
            sentence,
            word,
        )

        if predicate is None:
            continue

        results.append(
            (
                wh_phrase(
                    sentence,
                    word,
                ),
                predicate.text.casefold(),
            )
        )

    return results


print()
print("=" * 110)
print("RCV-03C-01: OPEN-VALUE INFORMATION-GAP EXTRACTION")
print("=" * 110)
print()
print(
    "Polar BOOLEAN_STATUS requests are intentionally "
    "outside this experiment."
)
print()


total_expected = 0
total_found = 0
case_passes = 0


for case in CASES:
    print("=" * 110)
    print(case["id"])
    print("QUESTION:")
    print(case["question"])
    print()

    extracted = []

    doc = nlp(case["question"])

    for sentence in doc.sentences:
        extracted.extend(
            extract_open_value_gaps(
                sentence,
            )
        )

    expected = [
        (
            phrase.casefold(),
            predicate.casefold(),
        )
        for phrase, predicate in case["expected"]
    ]

    total_expected += len(expected)
    total_found += len(extracted)

    passed = extracted == expected

    if passed:
        case_passes += 1

    print("EXPECTED:")
    if expected:
        for index, item in enumerate(
            expected,
            start=1,
        ):
            print(
                f"  R{index}: "
                f"gap={item[0]!r} "
                f"predicate={item[1]!r}"
            )
    else:
        print("  <none in 03C-01 scope>")

    print()
    print("EXTRACTED:")
    if extracted:
        for index, item in enumerate(
            extracted,
            start=1,
        ):
            print(
                f"  R{index}: "
                f"gap={item[0]!r} "
                f"predicate={item[1]!r}"
            )
    else:
        print("  <none>")

    print()
    print(
        "RESULT:",
        "PASS" if passed else "FAIL",
    )
    print()


print("=" * 110)
print("RCV-03C-01 SUMMARY")
print("=" * 110)
print()

print(
    f"QUESTION MATCHES: "
    f"{case_passes}/{len(CASES)}"
)
print(
    f"EXPECTED GAPS:    {total_expected}"
)
print(
    f"EXTRACTED GAPS:   {total_found}"
)
print()

print(
    "Interpretation:"
)
print(
    "- Exact matches support information-gap-first extraction."
)
print(
    "- False contextual gaps indicate structural ownership is "
    "still insufficient."
)
print(
    "- Missing genuine gaps indicate the extraction mechanism "
    "needs further architectural investigation."
)
print(
    "- Do not tune against individual question wording."
)
print()

print("RCV-03C-01 COMPLETE")
