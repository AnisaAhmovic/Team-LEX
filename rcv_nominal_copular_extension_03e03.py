"""RCV-03E-03: Nominal copular open-value controlled extension.

Architectural question:
Can one generic nominal-copular ownership rule recover open-value nominal
requests without regressing the frozen open-value or polar mechanisms?

Experimental only:
- RCV-03C-03B remains unchanged
- RCV-03D-02 remains unchanged
- no production changes
- no lexical noun lists
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
OPEN_SOURCE = ROOT / "rcv_predicative_gap_extension_03c03b.py"
POLAR_SOURCE = ROOT / "rcv_polar_gap_extraction_03d02.py"
POLAR_HOLDOUT_SOURCE = ROOT / "rcv_polar_gap_holdout_03d03.py"


# ---------------------------------------------------------------------------
# Load frozen RCV-03C-03B definitions only.
# Exact execution boundary was inspected before this experiment.
# ---------------------------------------------------------------------------

open_source = OPEN_SOURCE.read_text(
    encoding="utf-8-sig"
)

open_marker = (
    'print()\n'
    'print("=" * 112)\n'
)

if open_marker not in open_source:
    raise RuntimeError(
        "Could not locate inspected RCV-03C-03B execution boundary."
    )

open_definition_source = open_source.split(
    open_marker,
    1,
)[0]

open_ns = {
    "__file__": str(OPEN_SOURCE),
    "__name__": "rcv_03e03_open_frozen",
}

exec(
    compile(
        open_definition_source,
        str(OPEN_SOURCE),
        "exec",
    ),
    open_ns,
)

nlp = open_ns["nlp"]
lookup = open_ns["lookup"]
children = open_ns["children"]
extract_open_value_gaps_extended = open_ns[
    "extract_open_value_gaps_extended"
]

PREDICATIVE_CASES = open_ns["PREDICATIVE_CASES"]
DESIGN_CASES = open_ns["DESIGN_CASES"]
HOLDOUT_CASES = open_ns["HOLDOUT_CASES"]


# ---------------------------------------------------------------------------
# Load frozen RCV-03D-02 definitions only.
# ---------------------------------------------------------------------------

polar_source = POLAR_SOURCE.read_text(
    encoding="utf-8-sig"
)

polar_marker = (
    'print()\n'
    'print("=" * 112)\n'
    'print(\n'
    '    "RCV-03D-02: POLAR / BOOLEAN_STATUS "'
)

if polar_marker not in polar_source:
    raise RuntimeError(
        "Could not locate frozen RCV-03D-02 execution boundary."
    )

polar_definition_source = polar_source.split(
    polar_marker,
    1,
)[0]

polar_ns = {
    "__file__": str(POLAR_SOURCE),
    "__name__": "rcv_03e03_polar_frozen",
}

exec(
    compile(
        polar_definition_source,
        str(POLAR_SOURCE),
        "exec",
    ),
    polar_ns,
)

extract_polar_gaps = polar_ns[
    "extract_polar_gaps"
]


# ---------------------------------------------------------------------------
# Generic nominal-copular open-value ownership.
#
# Observed RCV-03E-02 signature:
#
#   interrogative PRON, PronType=Int
#       deprel=root
#       + local cop child
#       + nominal nsubj child
#
# Requested owner = nominal nsubj.
#
# No lexical noun knowledge is used.
# ---------------------------------------------------------------------------

def has_feature(word, feature):
    if not word.feats:
        return False

    return feature in word.feats.split("|")


def nominal_copular_owner(
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

    if interrogative.deprel != "root":
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


def extract_open_value_gaps_nominal_extended(
    sentence,
):
    frozen = list(
        extract_open_value_gaps_extended(
            sentence
        )
    )

    results = list(frozen)

    existing = {
        (
            gap.casefold(),
            owner.casefold(),
        )
        for gap, owner in results
    }

    for word in sentence.words:
        owner = nominal_copular_owner(
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
            results.append(candidate)
            existing.add(key)

    return results


# ---------------------------------------------------------------------------
# Nominal-copular design controls from RCV-03E-02.
# ---------------------------------------------------------------------------

NOMINAL_CASES = [
    (
        "R01",
        "What is an inspection?",
        [("what", "inspection")],
    ),
    (
        "R02",
        "What is the purpose of a road safety audit?",
        [("what", "purpose")],
    ),
    (
        "R03",
        (
            "What is La Trobe's best strategy for becoming "
            "Australia's number-one university?"
        ),
        [("what", "strategy")],
    ),
    (
        "P01",
        "What is the deadline?",
        [("what", "deadline")],
    ),
    (
        "P02",
        "Who is the approver?",
        [("who", "approver")],
    ),
    (
        "P03",
        "What is the required document?",
        [("what", "document")],
    ),
    (
        "P04",
        "Who is the responsible officer?",
        [("who", "officer")],
    ),
    (
        "P05",
        "What is the next step?",
        [("what", "step")],
    ),
]


NEGATIVE_CASES = [
    (
        "N01",
        "Is the deadline fixed?",
        [],
    ),
    (
        "N02",
        "Is the approver available?",
        [],
    ),
    (
        "N03",
        "Is this an inspection?",
        [],
    ),
    (
        "N04",
        "Is that the purpose of the audit?",
        [],
    ),
    (
        "N05",
        "Is this the best strategy?",
        [],
    ),
    (
        "N06",
        "The deadline is Friday.",
        [],
    ),
    (
        "N07",
        "The policy explains what an inspection is.",
        [],
    ),
    (
        "N08",
        "The document states who the approver is.",
        [],
    ),
]


def normalise(items):
    return [
        (
            gap.casefold(),
            owner.casefold(),
        )
        for gap, owner in items
    ]


def evaluate_cases(
    name,
    cases,
    extractor,
):
    print()
    print("=" * 112)
    print(name)
    print("=" * 112)

    passes = 0
    missing_total = 0
    false_positive_total = 0

    for case_id, text, expected in cases:
        doc = nlp(text)

        extracted = []

        for sentence in doc.sentences:
            extracted.extend(
                extractor(sentence)
            )

        expected_n = normalise(
            expected
        )
        extracted_n = normalise(
            extracted
        )

        remaining_actual = list(
            extracted_n
        )
        missing = []

        for item in expected_n:
            if item in remaining_actual:
                remaining_actual.remove(
                    item
                )
            else:
                missing.append(
                    item
                )

        remaining_expected = list(
            expected_n
        )
        extra = []

        for item in extracted_n:
            if item in remaining_expected:
                remaining_expected.remove(
                    item
                )
            else:
                extra.append(
                    item
                )

        passed = (
            len(expected_n)
            == len(extracted_n)
            and not missing
            and not extra
        )

        if passed:
            passes += 1

        missing_total += len(
            missing
        )
        false_positive_total += len(
            extra
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
        "MISSING:",
        missing_total,
    )
    print(
        "FALSE POSITIVES:",
        false_positive_total,
    )

    return (
        passes,
        len(cases),
        missing_total,
        false_positive_total,
    )


# ---------------------------------------------------------------------------
# Re-run frozen 03C suites against the NEW experimental extractor.
#
# Existing expected case definitions are reused unchanged.
# ---------------------------------------------------------------------------

def convert_frozen_cases(cases):
    converted = []

    for case in cases:
        # Frozen 03C-03B case shape:
        # case_id, text, expected
        converted.append(
            (
                case[0],
                case[1],
                case[2],
            )
        )

    return converted


# ---------------------------------------------------------------------------
# Polar design and holdout regression.
#
# For this experiment we specifically verify that nominal OPEN ownership
# suppresses the erroneous polar classification for nominal-open questions,
# while the frozen polar mechanism still behaves correctly on its own
# established design and holdout evidence.
# ---------------------------------------------------------------------------

POLAR_DESIGN_CASES = polar_ns["CASES"]


def normalise_polar(items):
    return [
        (
            slot.casefold(),
            owner.casefold(),
        )
        for slot, owner in items
    ]


def run_polar_cases(
    name,
    cases,
):
    print()
    print("=" * 112)
    print(name)
    print("=" * 112)

    passes = 0
    missing_total = 0
    false_positive_total = 0

    for case_id, text, expected in cases:
        doc = nlp(text)
        extracted = []

        for sentence in doc.sentences:
            extracted.extend(
                extract_polar_gaps(
                    sentence
                )
            )

        expected_n = normalise_polar(
            expected
        )
        extracted_n = normalise_polar(
            extracted
        )

        missing = [
            item
            for item in expected_n
            if item not in extracted_n
        ]

        extra = [
            item
            for item in extracted_n
            if item not in expected_n
        ]

        passed = (
            len(expected_n)
            == len(extracted_n)
            and not missing
            and not extra
        )

        if passed:
            passes += 1

        missing_total += len(
            missing
        )
        false_positive_total += len(
            extra
        )

    print(
        f"RESULT: {passes}/{len(cases)}"
    )
    print(
        "MISSING:",
        missing_total,
    )
    print(
        "FALSE POSITIVES:",
        false_positive_total,
    )

    return (
        passes,
        len(cases),
        missing_total,
        false_positive_total,
    )


# ---------------------------------------------------------------------------
# Nominal ownership versus polar ownership integration.
# ---------------------------------------------------------------------------

def integrated_nominal_polar(
    sentence,
):
    open_items = (
        extract_open_value_gaps_nominal_extended(
            sentence
        )
    )

    polar_items = extract_polar_gaps(
        sentence
    )

    # If a nominal-copular OPEN gap owns the interrogative-root proposition,
    # it takes precedence over the polar interpretation of that same
    # proposition.
    nominal_open_present = False

    for word in sentence.words:
        if nominal_copular_owner(
            sentence,
            word,
        ) is not None:
            nominal_open_present = True
            break

    if nominal_open_present:
        polar_items = []

    return open_items, polar_items


INTEGRATION_CASES = [
    (
        "I01",
        "What is an inspection?",
        [("OPEN", "inspection")],
    ),
    (
        "I02",
        "What is the purpose of a road safety audit?",
        [("OPEN", "purpose")],
    ),
    (
        "I03",
        (
            "What is La Trobe's best strategy for becoming "
            "Australia's number-one university?"
        ),
        [("OPEN", "strategy")],
    ),
    (
        "I04",
        "Is this an inspection?",
        [("POLAR", "inspection")],
    ),
    (
        "I05",
        "Is the approver available?",
        [("POLAR", "available")],
    ),
]


def run_integration_cases():
    print()
    print("=" * 112)
    print(
        "NOMINAL OPEN / POLAR OWNERSHIP INTEGRATION"
    )
    print("=" * 112)

    passes = 0
    missing_total = 0
    false_positive_total = 0

    for case_id, text, expected in INTEGRATION_CASES:
        doc = nlp(text)
        actual = []

        for sentence in doc.sentences:
            open_items, polar_items = (
                integrated_nominal_polar(
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

        expected_n = [
            (
                kind,
                owner.casefold(),
            )
            for kind, owner in expected
        ]

        missing = [
            item
            for item in expected_n
            if item not in actual
        ]

        extra = [
            item
            for item in actual
            if item not in expected_n
        ]

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
        false_positive_total += len(
            extra
        )

        print()
        print(case_id)
        print("  TEXT:", text)
        print("  EXPECTED:", expected_n)
        print("  EXTRACTED:", actual)
        print(
            "  RESULT:",
            "PASS" if passed else "FAIL",
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

    return (
        passes,
        len(INTEGRATION_CASES),
        missing_total,
        false_positive_total,
    )


print()
print("=" * 112)
print(
    "RCV-03E-03: NOMINAL COPULAR "
    "CONTROLLED EXTENSION"
)
print("=" * 112)
print()
print(
    "Frozen 03C-03B and 03D-02 source files remain unchanged."
)


nominal_result = evaluate_cases(
    "A. NOMINAL COPULAR POSITIVES",
    NOMINAL_CASES,
    extract_open_value_gaps_nominal_extended,
)

negative_result = evaluate_cases(
    "B. NOMINAL COPULAR NEGATIVES",
    NEGATIVE_CASES,
    extract_open_value_gaps_nominal_extended,
)

predicative_result = evaluate_cases(
    "C. FROZEN 03C PREDICATIVE REGRESSION",
    convert_frozen_cases(
        PREDICATIVE_CASES
    ),
    extract_open_value_gaps_nominal_extended,
)

design_result = evaluate_cases(
    "D. FROZEN 03C DESIGN REGRESSION",
    convert_frozen_cases(
        DESIGN_CASES
    ),
    extract_open_value_gaps_nominal_extended,
)

holdout_result = evaluate_cases(
    "E. FROZEN 03C HOLDOUT REGRESSION",
    convert_frozen_cases(
        HOLDOUT_CASES
    ),
    extract_open_value_gaps_nominal_extended,
)

polar_design_result = run_polar_cases(
    "F. FROZEN 03D POLAR DESIGN REGRESSION",
    POLAR_DESIGN_CASES,
)

integration_result = run_integration_cases()


print()
print("=" * 112)
print("RCV-03E-03 ACCEPTANCE SUMMARY")
print("=" * 112)
print()

results = [
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
    (
        "03D polar design regression",
        polar_design_result,
    ),
    (
        "Nominal/polar integration",
        integration_result,
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
    print("DECISION: PASS / ADVANCE TO UNSEEN HOLDOUT")
    print(
        "The generic nominal-copular extension "
        "recovers the design class without regression."
    )
else:
    print("DECISION: LIMITATION IDENTIFIED")
    print(
        "Do not tune the extension. "
        "Diagnose the failure class first."
    )

print()
print("RCV-03E-03 COMPLETE")
