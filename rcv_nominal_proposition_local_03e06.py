"""RCV-03E-06: Proposition-local nominal-copular controlled extension.

Architectural question:
Can nominal-copular OPEN ownership be generalised from root to coordinated
interrogative propositions, with OPEN precedence applied only to the
proposition it owns, while preserving genuine POLAR requirements elsewhere
in the same sentence?

Experimental only:
- RCV-03E-03 remains unchanged
- RCV-03E-04 remains unchanged
- frozen 03C/03D mechanisms remain unchanged
- no production changes
- no lexical noun lists
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "rcv_nominal_copular_extension_03e03.py"


# ---------------------------------------------------------------------------
# Load RCV-03E-03 definitions only.
# Exact execution boundary is already established.
# ---------------------------------------------------------------------------

source = SOURCE.read_text(
    encoding="utf-8-sig"
)

marker = (
    'print()\n'
    'print("=" * 112)\n'
    'print(\n'
    '    "RCV-03E-03: NOMINAL COPULAR "'
)

if marker not in source:
    raise RuntimeError(
        "Could not locate RCV-03E-03 execution boundary."
    )

definition_source = source.split(
    marker,
    1,
)[0]

ns = {
    "__file__": str(SOURCE),
    "__name__": "rcv_03e06_frozen_source",
}

exec(
    compile(
        definition_source,
        str(SOURCE),
        "exec",
    ),
    ns,
)


nlp = ns["nlp"]
children = ns["children"]
has_feature = ns["has_feature"]

extract_open_frozen = ns[
    "extract_open_value_gaps_nominal_extended"
]

extract_polar_frozen = ns[
    "extract_polar_gaps"
]

PREDICATIVE_CASES = ns[
    "PREDICATIVE_CASES"
]

DESIGN_CASES = ns[
    "DESIGN_CASES"
]

HOLDOUT_CASES = ns[
    "HOLDOUT_CASES"
]

NOMINAL_CASES = ns[
    "NOMINAL_CASES"
]

NEGATIVE_CASES = ns[
    "NEGATIVE_CASES"
]

POLAR_DESIGN_CASES = ns[
    "POLAR_DESIGN_CASES"
]


# ---------------------------------------------------------------------------
# Proposition-local nominal-copular ownership.
#
# RCV-03E-05 established that coordinated OPEN propositions retain:
#
#   interrogative PRON PronType=Int
#       + local cop
#       + local nominal nsubj
#
# while deprel changes from root -> conj.
#
# No lexical knowledge is used.
# ---------------------------------------------------------------------------

def nominal_copular_owner_local(
    sentence,
    interrogative,
):
    if interrogative.upos != "PRON":
        return None

    if not has_feature(
        interrogative,
        "PronType=Int",
    ):
        return None

    if interrogative.deprel not in {
        "root",
        "conj",
    }:
        return None

    local_children = children(
        sentence,
        interrogative.id,
    )

    has_copula = any(
        child.deprel == "cop"
        for child in local_children
    )

    if not has_copula:
        return None

    nominal_subjects = [
        child
        for child in local_children
        if child.deprel.startswith("nsubj")
        and child.upos in {
            "NOUN",
            "PROPN",
        }
    ]

    if len(nominal_subjects) != 1:
        return None

    return nominal_subjects[0]


# ---------------------------------------------------------------------------
# Extended OPEN extraction.
#
# Preserve all frozen 03E-03 OPEN results, then add only newly recognised
# coordinated nominal-copular propositions.
# ---------------------------------------------------------------------------

def extract_open_local(
    sentence,
):
    results = list(
        extract_open_frozen(
            sentence
        )
    )

    existing = {
        (
            gap.casefold(),
            owner.casefold(),
        )
        for gap, owner in results
    }

    for word in sentence.words:
        owner = nominal_copular_owner_local(
            sentence,
            word,
        )

        if owner is None:
            continue

        candidate = (
            word.text,
            owner.text,
        )

        key = (
            candidate[0].casefold(),
            candidate[1].casefold(),
        )

        if key not in existing:
            results.append(
                candidate
            )
            existing.add(
                key
            )

    return results


# ---------------------------------------------------------------------------
# Proposition-local OPEN precedence over POLAR.
#
# We must not clear every POLAR result merely because one OPEN nominal
# proposition exists in the sentence.
#
# Instead, identify the token IDs owned by nominal OPEN propositions and
# suppress only a POLAR result whose owner is that same interrogative
# proposition.
# ---------------------------------------------------------------------------

def nominal_open_propositions(
    sentence,
):
    owned = {}

    for word in sentence.words:
        nominal_owner = (
            nominal_copular_owner_local(
                sentence,
                word,
            )
        )

        if nominal_owner is None:
            continue

        owned[word.id] = {
            "interrogative": word,
            "nominal_owner": nominal_owner,
        }

    return owned


def polar_owner_matches_open_proposition(
    sentence,
    polar_owner_text,
    nominal_propositions,
):
    target = polar_owner_text.casefold()

    for info in nominal_propositions.values():
        interrogative = info[
            "interrogative"
        ]

        if (
            interrogative.text.casefold()
            == target
        ):
            return True

    return False


def integrated_local(
    sentence,
):
    open_items = extract_open_local(
        sentence
    )

    polar_items = list(
        extract_polar_frozen(
            sentence
        )
    )

    nominal_propositions = (
        nominal_open_propositions(
            sentence
        )
    )

    filtered_polar = []

    for polar_item in polar_items:
        _slot, polar_owner = polar_item

        if polar_owner_matches_open_proposition(
            sentence,
            polar_owner,
            nominal_propositions,
        ):
            continue

        filtered_polar.append(
            polar_item
        )

    return (
        open_items,
        filtered_polar,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalise_open(items):
    return [
        (
            gap.casefold(),
            owner.casefold(),
        )
        for gap, owner in items
    ]


def multiset_diff(
    expected,
    actual,
):
    remaining_actual = list(
        actual
    )

    missing = []

    for item in expected:
        if item in remaining_actual:
            remaining_actual.remove(
                item
            )
        else:
            missing.append(
                item
            )

    remaining_expected = list(
        expected
    )

    extra = []

    for item in actual:
        if item in remaining_expected:
            remaining_expected.remove(
                item
            )
        else:
            extra.append(
                item
            )

    return missing, extra


def evaluate_open_suite(
    name,
    cases,
):
    print()
    print("=" * 112)
    print(name)
    print("=" * 112)

    passes = 0
    missing_total = 0
    extra_total = 0

    for case in cases:
        case_id = case[0]
        text = case[1]
        expected = case[2]

        doc = nlp(text)

        actual = []

        for sentence in doc.sentences:
            actual.extend(
                extract_open_local(
                    sentence
                )
            )

        expected_n = normalise_open(
            expected
        )

        actual_n = normalise_open(
            actual
        )

        missing, extra = multiset_diff(
            expected_n,
            actual_n,
        )

        passed = (
            len(expected_n)
            == len(actual_n)
            and not missing
            and not extra
        )

        if passed:
            passes += 1

        missing_total += len(
            missing
        )

        extra_total += len(
            extra
        )

        if not passed:
            print()
            print(case_id)
            print("  TEXT:", text)
            print(
                "  EXPECTED:",
                expected_n,
            )
            print(
                "  EXTRACTED:",
                actual_n,
            )
            print(
                "  MISSING:",
                missing,
            )
            print(
                "  FALSE POSITIVE:",
                extra,
            )

    print()
    print(
        f"RESULT: {passes}/{len(cases)}"
    )
    print(
        f"MISSING: {missing_total}"
    )
    print(
        f"FALSE POSITIVES: {extra_total}"
    )

    return (
        passes,
        len(cases),
        missing_total,
        extra_total,
    )


def extract_integrated(text):
    doc = nlp(text)

    actual = []

    for sentence in doc.sentences:
        open_items, polar_items = (
            integrated_local(
                sentence
            )
        )

        for _gap, owner in open_items:
            actual.append(
                (
                    "OPEN",
                    owner.casefold(),
                )
            )

        for _slot, owner in polar_items:
            actual.append(
                (
                    "POLAR",
                    owner.casefold(),
                )
            )

    return actual


def evaluate_integrated_suite(
    name,
    cases,
):
    print()
    print("=" * 112)
    print(name)
    print("=" * 112)

    passes = 0
    missing_total = 0
    extra_total = 0

    for case_id, text, expected in cases:
        expected_n = [
            (
                kind,
                owner.casefold(),
            )
            for kind, owner in expected
        ]

        actual = extract_integrated(
            text
        )

        missing, extra = multiset_diff(
            expected_n,
            actual,
        )

        passed = (
            len(expected_n)
            == len(actual)
            and not missing
            and not extra
        )

        if passed:
            passes += 1

        missing_total += len(
            missing
        )

        extra_total += len(
            extra
        )

        print()
        print(case_id)
        print("  TEXT:", text)
        print(
            "  EXPECTED:",
            expected_n,
        )
        print(
            "  EXTRACTED:",
            actual,
        )

        if missing:
            print(
                "  MISSING:",
                missing,
            )

        if extra:
            print(
                "  FALSE POSITIVE:",
                extra,
            )

        print(
            "  RESULT:",
            "PASS" if passed else "FAIL",
        )

    print()
    print(
        f"RESULT: {passes}/{len(cases)}"
    )
    print(
        f"MISSING: {missing_total}"
    )
    print(
        f"FALSE POSITIVES: {extra_total}"
    )

    return (
        passes,
        len(cases),
        missing_total,
        extra_total,
    )


# ---------------------------------------------------------------------------
# 03E-04 failure cases plus reversed diagnostic controls.
# ---------------------------------------------------------------------------

COORDINATED_CASES = [
    (
        "H17",
        (
            "What is the applicable policy, and "
            "who is the project owner?"
        ),
        [
            ("OPEN", "policy"),
            ("OPEN", "owner"),
        ],
    ),
    (
        "H18",
        (
            "Is this the applicable policy, and "
            "who is the project owner?"
        ),
        [
            ("POLAR", "policy"),
            ("OPEN", "owner"),
        ],
    ),
    (
        "C01",
        (
            "Who is the project owner, and "
            "what is the applicable policy?"
        ),
        [
            ("OPEN", "owner"),
            ("OPEN", "policy"),
        ],
    ),
    (
        "C02",
        (
            "Who is the project owner, and "
            "is this the applicable policy?"
        ),
        [
            ("OPEN", "owner"),
            ("POLAR", "policy"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Original 03E-03 integration controls.
# ---------------------------------------------------------------------------

ORIGINAL_INTEGRATION = ns[
    "INTEGRATION_CASES"
]


print()
print("=" * 112)
print(
    "RCV-03E-06: PROPOSITION-LOCAL "
    "NOMINAL OWNERSHIP EXTENSION"
)
print("=" * 112)
print()
print(
    "03E-03 and 03E-04 remain unchanged."
)
print(
    "Testing proposition-local recognition "
    "and proposition-local OPEN precedence."
)


coordinated_result = (
    evaluate_integrated_suite(
        "A. COORDINATED NOMINAL/POLAR CONTROLS",
        COORDINATED_CASES,
    )
)

original_integration_result = (
    evaluate_integrated_suite(
        "B. ORIGINAL 03E-03 INTEGRATION REGRESSION",
        ORIGINAL_INTEGRATION,
    )
)

nominal_result = evaluate_open_suite(
    "C. ORIGINAL NOMINAL POSITIVE REGRESSION",
    NOMINAL_CASES,
)

negative_result = evaluate_open_suite(
    "D. ORIGINAL NOMINAL NEGATIVE REGRESSION",
    NEGATIVE_CASES,
)

predicative_result = evaluate_open_suite(
    "E. FROZEN 03C PREDICATIVE REGRESSION",
    PREDICATIVE_CASES,
)

design_result = evaluate_open_suite(
    "F. FROZEN 03C DESIGN REGRESSION",
    DESIGN_CASES,
)

holdout_result = evaluate_open_suite(
    "G. FROZEN 03C HOLDOUT REGRESSION",
    HOLDOUT_CASES,
)


print()
print("=" * 112)
print("RCV-03E-06 ACCEPTANCE SUMMARY")
print("=" * 112)
print()

results = [
    (
        "Coordinated controls",
        coordinated_result,
    ),
    (
        "Original integration",
        original_integration_result,
    ),
    (
        "Nominal positives",
        nominal_result,
    ),
    (
        "Nominal negatives",
        negative_result,
    ),
    (
        "03C predicative regression",
        predicative_result,
    ),
    (
        "03C design regression",
        design_result,
    ),
    (
        "03C holdout regression",
        holdout_result,
    ),
]

all_pass = True

for name, result in results:
    passed, total, missing, extra = result

    print(
        f"{name}: "
        f"{passed}/{total}, "
        f"missing={missing}, "
        f"false_positive={extra}"
    )

    if (
        passed != total
        or missing != 0
        or extra != 0
    ):
        all_pass = False


print()

if all_pass:
    print(
        "DECISION: PASS / ADVANCE TO "
        "UNSEEN COORDINATED HOLDOUT"
    )
    print(
        "Proposition-local nominal OPEN ownership "
        "fixed the known coordination limitation "
        "without regressing frozen OPEN evidence."
    )
else:
    print(
        "DECISION: LIMITATION IDENTIFIED"
    )
    print(
        "Do not tune. Diagnose the failing "
        "structural class before changing the mechanism."
    )

print()
print("RCV-03E-06 COMPLETE")
