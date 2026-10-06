"""RCV-03D-03: Frozen unseen polar holdout.

The RCV-03D-02 extractor is loaded unchanged.

No holdout case may be used to modify the extractor during this experiment.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "rcv_polar_gap_extraction_03d02.py"


source = SOURCE.read_text(
    encoding="utf-8-sig"
)

marker = (
    'print()\n'
    'print("=" * 112)\n'
    'print(\n'
    '    "RCV-03D-02: POLAR / BOOLEAN_STATUS "'
)

if marker not in source:
    raise RuntimeError(
        "Could not locate frozen RCV-03D-02 execution boundary. "
        "Do not modify RCV-03D-02."
    )

definition_source = source.split(
    marker,
    1,
)[0]

namespace = {
    "__file__": str(SOURCE),
    "__name__": "rcv_03d03_frozen_polar_holdout",
}

exec(
    compile(
        definition_source,
        str(SOURCE),
        "exec",
    ),
    namespace,
)

nlp = namespace["nlp"]
extract_polar_gaps = namespace[
    "extract_polar_gaps"
]


CASES = [
    (
        "H01",
        "Has the application been approved?",
        [("BOOLEAN_STATUS", "approved")],
    ),
    (
        "H02",
        "Will the University notify the researcher?",
        [("BOOLEAN_STATUS", "notify")],
    ),
    (
        "H03",
        "Would this requirement apply to contractors?",
        [("BOOLEAN_STATUS", "apply")],
    ),
    (
        "H04",
        "Could the disclosure be delayed?",
        [("BOOLEAN_STATUS", "delayed")],
    ),
    (
        "H05",
        "Is the researcher eligible to apply?",
        [("BOOLEAN_STATUS", "eligible")],
    ),
    (
        "H06",
        "Were the records retained correctly?",
        [("BOOLEAN_STATUS", "retained")],
    ),
    (
        "H07",
        "Do staff need to complete the training?",
        [("BOOLEAN_STATUS", "need")],
    ),
    (
        "H08",
        "May students access the facility after hours?",
        [("BOOLEAN_STATUS", "access")],
    ),
    (
        "H09",
        (
            "If approval has been obtained, "
            "can the project commence?"
        ),
        [("BOOLEAN_STATUS", "commence")],
    ),
    (
        "H10",
        (
            "Can the project commence "
            "when approval has been obtained?"
        ),
        [("BOOLEAN_STATUS", "commence")],
    ),
    (
        "H11",
        (
            "What happens if the application "
            "has been approved?"
        ),
        [],
    ),
    (
        "H12",
        (
            "The policy states that the University "
            "will notify the researcher."
        ),
        [],
    ),
    (
        "H13",
        (
            "Has the application been approved, "
            "and who must be notified?"
        ),
        [("BOOLEAN_STATUS", "approved")],
    ),
    (
        "H14",
        (
            "Who must be notified, "
            "and has the application been approved?"
        ),
        [("BOOLEAN_STATUS", "approved")],
    ),
    (
        "H15",
        (
            "The researcher asked whether "
            "the application had been approved."
        ),
        [],
    ),
    (
        "H16",
        (
            "If the University will notify the researcher, "
            "what should staff do?"
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


print()
print("=" * 112)
print(
    "RCV-03D-03: FROZEN UNSEEN "
    "POLAR HOLDOUT"
)
print("=" * 112)
print()
print(
    "RCV-03D-02 extractor loaded unchanged."
)
print(
    "No holdout-driven extractor tuning is permitted."
)


passes = 0
missing_total = 0
false_positive_total = 0


for case_id, text, expected in CASES:
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

    if passed:
        passes += 1

    missing_total += len(missing)
    false_positive_total += len(
        false_positive
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


print()
print("=" * 112)
print("RCV-03D-03 HOLDOUT SUMMARY")
print("=" * 112)
print()
print(
    f"HOLDOUT CASES: {passes}/{len(CASES)}"
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
    print("DECISION: PASS / ADVANCE")
    print(
        "The frozen polar mechanism generalises "
        "across the unseen holdout."
    )
else:
    print(
        "DECISION: STRUCTURAL LIMITATION IDENTIFIED"
    )
    print(
        "Do not tune the frozen extractor. "
        "Diagnose the failure class first."
    )

print()
print("RCV-03D-03 COMPLETE")
