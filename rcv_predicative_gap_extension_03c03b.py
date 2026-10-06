"""RCV-03C-03B: Predicative-complement extraction extension.

Architectural question:
Can the frozen open-value extractor be extended with one generic
copular-predicative ownership rule so that non-verbal information gaps
are recovered without regressing existing extraction or introducing
contextual false positives?

This is an experimental extension only.
Production code and all frozen prior experiments remain unchanged.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_03C01 = ROOT / "rcv_open_value_extraction_03c01.py"


# ---------------------------------------------------------------------------
# Load frozen 03C-01 definitions without executing its experiment.
# ---------------------------------------------------------------------------

source = SOURCE_03C01.read_text(encoding="utf-8-sig")

marker = (
    'print()\n'
    'print("=" * 110)\n'
    'print("RCV-03C-01: OPEN-VALUE INFORMATION-GAP EXTRACTION")'
)

if marker not in source:
    raise RuntimeError(
        "Could not locate frozen 03C-01 execution boundary. "
        "Do not modify 03C-01."
    )

definition_source = source.split(marker, 1)[0]

namespace = {
    "__file__": str(SOURCE_03C01),
    "__name__": "rcv_03c03b_frozen_base",
}

exec(
    compile(
        definition_source,
        str(SOURCE_03C01),
        "exec",
    ),
    namespace,
)

nlp = namespace["nlp"]
frozen_extract = namespace["extract_open_value_gaps"]
frozen_governing_predicate = namespace["governing_predicate"]
wh_phrase = namespace["wh_phrase"]
is_inside_subordinate_clause = namespace[
    "is_inside_subordinate_clause"
]


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


# ---------------------------------------------------------------------------
# ONE EXPERIMENTAL EXTENSION
# ---------------------------------------------------------------------------

def predicative_owner(sentence, interrogative):
    """
    Return a non-verbal copular predicate that owns this interrogative
    information gap, or None.

    Structural contract:
    - owner is ADJ;
    - owner participates in a copular proposition;
    - interrogative itself, or the nominal it determines, is the
      subject of that owner;
    - owner is not subordinate contextual material.

    No lexical adjective lists are used.
    """
    words = lookup(sentence)

    if interrogative.deprel == "det":
        if not interrogative.head:
            return None
        subject_candidate = words[interrogative.head]
    else:
        subject_candidate = interrogative

    if not subject_candidate.head:
        return None

    owner = words[subject_candidate.head]

    if owner.upos != "ADJ":
        return None

    if not subject_candidate.deprel.startswith("nsubj"):
        return None

    has_copula = any(
        child.deprel == "cop"
        for child in children(
            sentence,
            owner.id,
        )
    )

    if not has_copula:
        return None

    if owner.deprel in {
        "advcl",
        "acl",
        "acl:relcl",
        "ccomp",
        "xcomp",
    }:
        return None

    return owner


def extract_open_value_gaps_extended(sentence):
    """
    Preserve the frozen 03C-01 extractor and add only the validated
    predicative-complement ownership path.
    """
    results = list(
        frozen_extract(sentence)
    )

    existing = {
        (
            gap.casefold(),
            predicate.casefold(),
        )
        for gap, predicate in results
    }

    for word in sentence.words:
        if not (
            word.feats
            and "PronType=Int" in word.feats
        ):
            continue

        if is_inside_subordinate_clause(
            sentence,
            word,
        ):
            continue

        # If the frozen verbal path already owns this interrogative,
        # no extension is needed.
        verbal_owner = frozen_governing_predicate(
            sentence,
            word,
        )

        if verbal_owner is not None:
            continue

        owner = predicative_owner(
            sentence,
            word,
        )

        if owner is None:
            continue

        item = (
            wh_phrase(
                sentence,
                word,
            ),
            owner.text.casefold(),
        )

        normalised = (
            item[0].casefold(),
            item[1].casefold(),
        )

        if normalised not in existing:
            results.append(item)
            existing.add(normalised)

    return results


# ---------------------------------------------------------------------------
# FROZEN 03C-03 POSITIVE / NEGATIVE CONTROLS
# ---------------------------------------------------------------------------

PREDICATIVE_CASES = [
    (
        "P01",
        "Who is responsible for reviewing the application?",
        [("who", "responsible")],
    ),
    (
        "P02",
        "Who is eligible for the program?",
        [("who", "eligible")],
    ),
    (
        "P03",
        "What is necessary for the application?",
        [("what", "necessary")],
    ),
    (
        "P04",
        "Which option is appropriate for this situation?",
        [("which option", "appropriate")],
    ),
    (
        "P05",
        "Who is accountable for the final decision?",
        [("who", "accountable")],
    ),
    (
        "N01",
        "What confidential records must be retained?",
        [("what confidential records", "retained")],
    ),
    (
        "N02",
        "Which authorised officer must approve the request?",
        [("which authorised officer", "approve")],
    ),
    (
        "N03",
        (
            "What should staff do when confidential information "
            "is accidentally disclosed?"
        ),
        [("what", "do")],
    ),
    (
        "N04",
        (
            "The procedure explains who to contact "
            "when immediate action is necessary."
        ),
        [],
    ),
    (
        "N05",
        (
            "If additional approval is necessary, "
            "who must provide it?"
        ),
        [("who", "provide")],
    ),
]


# ---------------------------------------------------------------------------
# ORIGINAL 03C-01 DESIGN REGRESSION
#
# Semantic comparison deliberately ignores the known P01 surface-only
# conjunction reconstruction difference.
# ---------------------------------------------------------------------------

DESIGN_CASES = [
    (
        "T02",
        "Can I approve my own procurement if I have the right delegation?",
        [],
    ),
    (
        "T04",
        (
            "What must staff and students avoid "
            "when publishing research involving Exploitable IP?"
        ),
        [("what", "avoid")],
    ),
    (
        "T08",
        (
            "When publishing research involving Exploitable IP, "
            "what must staff and students avoid, "
            "and how long may publication be delayed "
            "once Exploitable IP is declared?"
        ),
        [
            ("what", "avoid"),
            ("how long", "delayed"),
        ],
    ),
    (
        "T13",
        (
            "When publishing research involving Exploitable IP, "
            "what must staff and students avoid, "
            "what will the University do once it is declared, "
            "and how long may publication be delayed?"
        ),
        [
            ("what", "avoid"),
            ("what", "do"),
            ("how long", "delayed"),
        ],
    ),
    (
        "T17",
        (
            "What should I do "
            "if I think my manager is treating me unfairly?"
        ),
        [("what", "do")],
    ),
    (
        "P01",
        (
            "Before a La Trobe procurement activity commences, "
            "what financial approval and budget requirements apply, "
            "what expenditure must be considered when seeking approval, "
            "and can an Authorised Signatory approve "
            "their own procurement recommendation?"
        ),
        [
            # Frozen extractor omits surface conjunction "and".
            ("what financial approval budget requirements", "apply"),
            ("what expenditure", "considered"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# FROZEN 03C-02 HOLDOUT REGRESSION
# ---------------------------------------------------------------------------

HOLDOUT_CASES = [
    (
        "H01",
        "Who is responsible for reviewing the application?",
        [("who", "responsible")],
    ),
    (
        "H02",
        "When must the report be submitted?",
        [("when", "submitted")],
    ),
    (
        "H03",
        "Where should the completed form be sent?",
        [("where", "sent")],
    ),
    (
        "H04",
        "Why must the incident be reported?",
        [("why", "reported")],
    ),
    (
        "H05",
        "Which documents must the researcher retain?",
        [("which documents", "retain")],
    ),
    (
        "H06",
        "How should confidential records be stored?",
        [("how", "stored")],
    ),
    (
        "H07",
        (
            "Who must approve the request, "
            "and when must approval be recorded?"
        ),
        [
            ("who", "approve"),
            ("when", "recorded"),
        ],
    ),
    (
        "H08",
        (
            "What should a researcher do "
            "when an unexpected conflict arises?"
        ),
        [("what", "do")],
    ),
    (
        "H09",
        (
            "When a safety issue is identified, "
            "who must be notified?"
        ),
        [("who", "notified")],
    ),
    (
        "H10",
        (
            "What evidence must be retained "
            "when deciding whether an exception applies?"
        ),
        [("what evidence", "retained")],
    ),
    (
        "H11",
        (
            "When should the matter be escalated "
            "if the issue cannot be resolved locally?"
        ),
        [("when", "escalated")],
    ),
    (
        "H12",
        "The procedure explains when approval is required.",
        [],
    ),
]


def normalise(items):
    return [
        (
            gap.casefold(),
            predicate.casefold(),
        )
        for gap, predicate in items
    ]


def run_suite(name, cases):
    print()
    print("=" * 112)
    print(name)
    print("=" * 112)

    passes = 0
    missing_total = 0
    false_positive_total = 0

    for case_id, question, expected in cases:
        extracted = []

        doc = nlp(question)

        for sentence in doc.sentences:
            extracted.extend(
                extract_open_value_gaps_extended(
                    sentence,
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
            not missing
            and not false_positive
            and len(expected_n) == len(extracted_n)
        )

        if passed:
            passes += 1

        missing_total += len(missing)
        false_positive_total += len(false_positive)

        print()
        print(case_id)
        print("  EXPECTED:", expected_n)
        print("  EXTRACTED:", extracted_n)

        if missing:
            print("  MISSING:", missing)

        if false_positive:
            print(
                "  FALSE POSITIVE:",
                false_positive,
            )

        print(
            "  RESULT:",
            "PASS" if passed else "FAIL",
        )

    print()
    print(
        f"SUITE RESULT: {passes}/{len(cases)}"
    )
    print(
        f"MISSING: {missing_total}"
    )
    print(
        f"FALSE POSITIVES: {false_positive_total}"
    )

    return {
        "passes": passes,
        "total": len(cases),
        "missing": missing_total,
        "false_positive": false_positive_total,
    }


print()
print("=" * 112)
print(
    "RCV-03C-03B: PREDICATIVE-COMPLEMENT "
    "EXTRACTION EXTENSION"
)
print("=" * 112)
print()
print(
    "Frozen 03C-01 remains unchanged."
)
print(
    "One generic experimental extension is under test."
)


predicative_result = run_suite(
    "A. 03C-03 PREDICATIVE CONTROLS",
    PREDICATIVE_CASES,
)

design_result = run_suite(
    "B. 03C-01 DESIGN REGRESSION",
    DESIGN_CASES,
)

holdout_result = run_suite(
    "C. 03C-02 FROZEN HOLDOUT REGRESSION",
    HOLDOUT_CASES,
)


all_pass = (
    predicative_result["passes"]
    == predicative_result["total"]
    and design_result["passes"]
    == design_result["total"]
    and holdout_result["passes"]
    == holdout_result["total"]
)

total_false_positives = (
    predicative_result["false_positive"]
    + design_result["false_positive"]
    + holdout_result["false_positive"]
)


print()
print("=" * 112)
print("RCV-03C-03B ACCEPTANCE SUMMARY")
print("=" * 112)
print()

print(
    "Predicative controls: "
    f"{predicative_result['passes']}/"
    f"{predicative_result['total']}"
)

print(
    "03C-01 design regression: "
    f"{design_result['passes']}/"
    f"{design_result['total']}"
)

print(
    "03C-02 holdout regression: "
    f"{holdout_result['passes']}/"
    f"{holdout_result['total']}"
)

print(
    "Total false positives:",
    total_false_positives,
)

print()

if all_pass and total_false_positives == 0:
    print(
        "DECISION: PASS / ADVANCE"
    )
    print(
        "The generic predicative-complement extension "
        "recovers the known structural gap without "
        "regressing frozen open-value controls."
    )
else:
    print(
        "DECISION: DO NOT ACCEPT EXTENSION"
    )
    print(
        "Inspect the structural failure class. "
        "Do not tune against individual cases."
    )

print()
print("RCV-03C-03B COMPLETE")
