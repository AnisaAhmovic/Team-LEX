"""RCV-03D-02: Polar / BOOLEAN_STATUS information-gap extraction.

Architectural question:
Can a policy-independent proposition-local extractor identify genuine
BOOLEAN_STATUS information gaps using structural inversion, while excluding
open-value-owned, subordinate, embedded and declarative propositions?

Scope:
- experimental only
- frozen 03D-01 design controls
- no production changes
- no policy-specific vocabulary
- no unseen holdout tuning
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_03C03B = ROOT / "rcv_predicative_gap_extension_03c03b.py"


# ---------------------------------------------------------------------------
# Load the accepted 03C-03B definitions without executing its experiment.
# ---------------------------------------------------------------------------

source = SOURCE_03C03B.read_text(
    encoding="utf-8-sig"
)

marker = (
    'print()\n'
    'print("=" * 112)\n'
    'print(\n'
    '    "RCV-03C-03B: PREDICATIVE-COMPLEMENT "'
)

if marker not in source:
    raise RuntimeError(
        "Could not locate the 03C-03B execution boundary. "
        "Do not modify the frozen experiment."
    )

definition_source = source.split(
    marker,
    1,
)[0]

namespace = {
    "__file__": str(SOURCE_03C03B),
    "__name__": "rcv_03d02_frozen_open_value_base",
}

exec(
    compile(
        definition_source,
        str(SOURCE_03C03B),
        "exec",
    ),
    namespace,
)

nlp = namespace["nlp"]
extract_open_value_gaps = namespace[
    "extract_open_value_gaps_extended"
]


SUBORDINATE_RELATIONS = {
    "advcl",
    "acl",
    "acl:relcl",
    "ccomp",
    "xcomp",
}


def lookup(sentence):
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


def proposition_candidates(sentence):
    """
    Candidate independently question-bearing propositions.

    For this bounded experiment:
    - sentence root;
    - coordinated predicates attached to root/candidate propositions.

    Subordinate/contextual relations are excluded.
    """
    words = lookup(sentence)

    roots = [
        word
        for word in sentence.words
        if word.head == 0
    ]

    if not roots:
        return []

    candidates = []
    queue = list(roots)
    seen = set()

    while queue:
        candidate = queue.pop(0)

        if candidate.id in seen:
            continue

        seen.add(candidate.id)

        if candidate.deprel not in SUBORDINATE_RELATIONS:
            candidates.append(candidate)

        for child in children(
            sentence,
            candidate.id,
        ):
            if child.deprel in {
                "conj",
                "parataxis",
            }:
                queue.append(child)

    return candidates


def local_subjects(sentence, proposition):
    return [
        child
        for child in children(
            sentence,
            proposition.id,
        )
        if child.deprel.startswith(
            "nsubj"
        )
    ]


def local_auxiliaries(sentence, proposition):
    return [
        child
        for child in children(
            sentence,
            proposition.id,
        )
        if (
            child.upos == "AUX"
            or child.deprel.startswith("aux")
            or child.deprel == "cop"
        )
    ]


def open_value_owner_ids(sentence):
    """
    Identify proposition owners already carrying an open-value gap.

    We deliberately reuse the accepted open-value extractor rather than
    inferring ownership from modal vocabulary.
    """
    extracted = extract_open_value_gaps(
        sentence
    )

    owner_ids = set()

    for _gap, predicate_text in extracted:
        matches = [
            word
            for word in sentence.words
            if (
                word.text.casefold()
                == predicate_text.casefold()
            )
        ]

        # The frozen controls contain repeated predicate text in P09.
        # Therefore text matching alone is insufficient. Resolve ownership
        # structurally from interrogative tokens as an additional safeguard.
        for word in matches:
            interrogative_children = [
                child
                for child in children(
                    sentence,
                    word.id,
                )
                if (
                    child.feats
                    and "PronType=Int"
                    in child.feats
                )
            ]

            interrogative_nominal_subjects = []

            for child in children(
                sentence,
                word.id,
            ):
                if not child.deprel.startswith(
                    "nsubj"
                ):
                    continue

                dets = [
                    det
                    for det in children(
                        sentence,
                        child.id,
                    )
                    if (
                        det.feats
                        and "PronType=Int"
                        in det.feats
                    )
                ]

                if dets:
                    interrogative_nominal_subjects.append(
                        child
                    )

            if (
                interrogative_children
                or interrogative_nominal_subjects
            ):
                owner_ids.add(word.id)

    # General structural ownership pass for open-value interrogatives.
    # This catches object/adverbial WH ownership as well as subjects.
    words = lookup(sentence)

    for word in sentence.words:
        if not (
            word.feats
            and "PronType=Int" in word.feats
        ):
            continue

        current = word
        visited = set()

        while current.head:
            if current.id in visited:
                break

            visited.add(current.id)
            current = words[current.head]

            if current.deprel in SUBORDINATE_RELATIONS:
                break

            if current.upos in {
                "VERB",
                "ADJ",
            }:
                owner_ids.add(current.id)
                break

    return owner_ids


def extract_polar_gaps(sentence):
    """
    Extract BOOLEAN_STATUS information gaps.

    Structural contract:
    1. proposition is root or coordinated independent candidate;
    2. proposition is not already owned by an open-value gap;
    3. proposition has a local subject;
    4. proposition has a local AUX/COP;
    5. at least one local AUX/COP precedes the local subject.

    No modal-word list is used.
    """
    results = []

    open_owners = open_value_owner_ids(
        sentence
    )

    for proposition in proposition_candidates(
        sentence
    ):
        if proposition.id in open_owners:
            continue

        subjects = local_subjects(
            sentence,
            proposition,
        )

        auxiliaries = local_auxiliaries(
            sentence,
            proposition,
        )

        if not subjects or not auxiliaries:
            continue

        earliest_subject = min(
            subject.id
            for subject in subjects
        )

        inverted_auxiliaries = [
            aux
            for aux in auxiliaries
            if aux.id < earliest_subject
        ]

        if not inverted_auxiliaries:
            continue

        results.append(
            (
                "BOOLEAN_STATUS",
                proposition.text.casefold(),
            )
        )

    return results


# ---------------------------------------------------------------------------
# FROZEN RCV-03D-01 DESIGN SET
# ---------------------------------------------------------------------------

CASES = [
    (
        "P01",
        "Can I approve my own procurement?",
        [("BOOLEAN_STATUS", "approve")],
    ),
    (
        "P02",
        "Are all health and safety incidents investigated?",
        [("BOOLEAN_STATUS", "investigated")],
    ),
    (
        "P03",
        "Is prior approval necessary?",
        [("BOOLEAN_STATUS", "necessary")],
    ),
    (
        "P04",
        "Does the requirement apply to students?",
        [("BOOLEAN_STATUS", "apply")],
    ),
    (
        "P05",
        "Should the incident be reported immediately?",
        [("BOOLEAN_STATUS", "reported")],
    ),
    (
        "P06",
        "Must the researcher obtain approval first?",
        [("BOOLEAN_STATUS", "obtain")],
    ),
    (
        "P07",
        (
            "Can I approve the request "
            "if I have the required delegation?"
        ),
        [("BOOLEAN_STATUS", "approve")],
    ),
    (
        "P08",
        (
            "When an incident occurs, "
            "must it be reported immediately?"
        ),
        [("BOOLEAN_STATUS", "reported")],
    ),
    (
        "P09",
        (
            "Can I approve my own procurement, "
            "and who must approve it instead?"
        ),
        [("BOOLEAN_STATUS", "approve")],
    ),
    (
        "P10",
        (
            "Who must review the application, "
            "and can that person approve it?"
        ),
        [("BOOLEAN_STATUS", "approve")],
    ),
    (
        "N01",
        "Staff can approve requests within their delegation.",
        [],
    ),
    (
        "N02",
        "All incidents are investigated.",
        [],
    ),
    (
        "N03",
        "Prior approval is necessary.",
        [],
    ),
    (
        "N04",
        (
            "What should I do "
            "if I can approve the request?"
        ),
        [],
    ),
    (
        "N05",
        (
            "The procedure explains whether "
            "the request can be approved."
        ),
        [],
    ),
    (
        "N06",
        (
            "Staff may ask whether approval is required."
        ),
        [],
    ),
]


def normalise(items):
    return [
        (
            slot.casefold(),
            owner.casefold(),
        )
        for slot, owner in items
    ]


def run_case(
    case_id,
    text,
    expected,
):
    doc = nlp(text)

    extracted = []

    for sentence in doc.sentences:
        extracted.extend(
            extract_polar_gaps(
                sentence
            )
        )

    expected_n = normalise(expected)
    extracted_n = normalise(extracted)

    missing = [
        item
        for item in expected_n
        if item not in extracted_n
    ]

    false_positive = [
        item
        for item in extracted_n
        if item not in expected_n
    ]

    passed = (
        len(expected_n)
        == len(extracted_n)
        and not missing
        and not false_positive
    )

    print()
    print(case_id)
    print("  TEXT:", text)
    print("  EXPECTED:", expected_n)
    print("  EXTRACTED:", extracted_n)

    if missing:
        print(
            "  MISSING:",
            missing,
        )

    if false_positive:
        print(
            "  FALSE POSITIVE:",
            false_positive,
        )

    print(
        "  RESULT:",
        "PASS" if passed else "FAIL",
    )

    return (
        passed,
        len(missing),
        len(false_positive),
    )


print()
print("=" * 112)
print(
    "RCV-03D-02: POLAR / BOOLEAN_STATUS "
    "INFORMATION-GAP EXTRACTION"
)
print("=" * 112)
print()
print(
    "Frozen 03D-01 design controls only."
)
print(
    "No unseen holdout has been used to design this extractor."
)


passes = 0
missing_total = 0
false_positive_total = 0

for case_id, text, expected in CASES:
    passed, missing, false_positive = run_case(
        case_id,
        text,
        expected,
    )

    if passed:
        passes += 1

    missing_total += missing
    false_positive_total += false_positive


print()
print("=" * 112)
print("RCV-03D-02 ACCEPTANCE SUMMARY")
print("=" * 112)
print()
print(
    f"DESIGN CASES: {passes}/{len(CASES)}"
)
print(
    "MISSING:",
    missing_total,
)
print(
    "FALSE POSITIVES:",
    false_positive_total,
)
print()

if (
    passes == len(CASES)
    and missing_total == 0
    and false_positive_total == 0
):
    print("DECISION: PASS / FREEZE FOR HOLDOUT")
    print(
        "The proposition-local polar mechanism passes "
        "the frozen design set."
    )
else:
    print("DECISION: DO NOT FREEZE")
    print(
        "Inspect the structural failure class. "
        "Do not tune individual wording."
    )

print()
print("RCV-03D-02 COMPLETE")
