"""
RCV-03E-17A
Controlled unified information-gap integration diagnostic.

Architectural question:
Can the evidence-backed 03E corrections be composed with the established
OPEN and POLAR mechanisms and correctly identify the frozen 19-question /
34-requirement real LEX census?

Scope:
- reuse established 03E-06 proposition-local integration;
- apply frozen Class B correction: xcomp is NOT an automatic context proxy;
- add only the provisional Class C false-subordinate OPEN override;
- preserve advcl / acl / acl:relcl / ccomp as conservative context defaults;
- do not evaluate semantic-slot normalisation;
- do not claim P01 shared-context propagation solved;
- do not modify production code.

This is an experimental diagnostic only.
"""

from pathlib import Path


def load_prefix(
    filename,
    marker,
):
    source = Path(filename).read_text(
        encoding="utf-8-sig"
    )

    if marker not in source:
        raise RuntimeError(
            f"Marker not found in {filename}: "
            f"{marker!r}"
        )

    return source.split(
        marker,
        1,
    )[0]


# ---------------------------------------------------------------------------
# 1. Load the established 03E-06 integration definitions without executing
#    its experiment/reporting section.
# ---------------------------------------------------------------------------

nominal_full_source = Path(
    "rcv_nominal_proposition_local_03e06.py"
).read_text(
    encoding="utf-8-sig"
)

nominal_boundary = (
    '\nprint()\n'
    'print("=" * 112)\n'
    'print(\n'
    '    "RCV-03E-06: PROPOSITION-LOCAL "'
)

if nominal_full_source.count(
    nominal_boundary
) != 1:
    raise RuntimeError(
        "03E-06 execution boundary mismatch: "
        f"expected exactly 1 boundary, found "
        f"{nominal_full_source.count(nominal_boundary)}"
    )

nominal_source = nominal_full_source.split(
    nominal_boundary,
    1,
)[0]

nominal_ns = {
    "__name__": "rcv_03e17_nominal",
    "__file__": str(
        Path(
            "rcv_nominal_proposition_local_03e06.py"
        ).resolve()
    ),
}

exec(
    compile(
        nominal_source,
        "rcv_nominal_proposition_local_03e06.py",
        "exec",
    ),
    nominal_ns,
)


required_nominal_symbols = {
    "nlp",
    "extract_open_local",
    "integrated_local",
    "nominal_copular_owner_local",
}

missing_symbols = (
    required_nominal_symbols
    - set(nominal_ns)
)

if missing_symbols:
    raise RuntimeError(
        "03E-06 interface mismatch. Missing: "
        + ", ".join(
            sorted(missing_symbols)
        )
    )


nlp = nominal_ns["nlp"]


# ---------------------------------------------------------------------------
# 2. Apply the already-frozen Class B correction to every subordinate guard
#    used by the nested OPEN implementation.
#
#    The ONLY structural delta is:
#
#       old: advcl, acl, acl:relcl, ccomp, xcomp
#       new: advcl, acl, acl:relcl, ccomp
#
#    No other dependency relation is relaxed.
# ---------------------------------------------------------------------------

SUBORDINATE_RELATIONS_CLASS_B = {
    "advcl",
    "acl",
    "acl:relcl",
    "ccomp",
}


def make_class_b_subordinate_guard(
    original_guard,
):
    """
    Apply the frozen RCV-03E-15 Class B correction while
    preserving the original guard's established dependency
    helper binding.

    Verified original guards resolve ancestors() directly
    from their own function globals. The only structural
    delta is removal of xcomp from the automatic subordinate
    relation set.
    """
    if not callable(
        original_guard
    ):
        raise RuntimeError(
            "Expected callable original subordinate guard."
        )

    ancestors_fn = (
        original_guard.__globals__.get(
            "ancestors"
        )
    )

    if not callable(
        ancestors_fn
    ):
        raise RuntimeError(
            "Original subordinate guard does not expose "
            "its established callable ancestors()."
        )

    def class_b_guard(
        sentence,
        word,
    ):
        for ancestor in ancestors_fn(
            sentence,
            word,
        ):
            if (
                ancestor.deprel
                in SUBORDINATE_RELATIONS_CLASS_B
            ):
                return True

        return False

    return class_b_guard


def patch_subordinate_guards(
    namespace,
):
    """
    Replace the two verified distinct original guard objects
    while preserving shared wrapper/implementation references.
    """
    if not isinstance(
        namespace,
        dict,
    ):
        raise RuntimeError(
            "Expected nominal namespace dictionary."
        )

    targets = []

    visited = set()

    def collect(
        current,
    ):
        if not isinstance(
            current,
            dict,
        ):
            return

        current_id = id(
            current
        )

        if current_id in visited:
            return

        visited.add(
            current_id
        )

        guard = current.get(
            "is_inside_subordinate_clause"
        )

        if callable(
            guard
        ):
            targets.append(
                (
                    current,
                    guard,
                )
            )

        for value in current.values():
            if isinstance(
                value,
                dict,
            ):
                collect(
                    value
                )

    collect(
        namespace
    )

    original_guards = []

    for _target_namespace, guard in targets:
        if not any(
            guard is existing
            for existing in original_guards
        ):
            original_guards.append(
                guard
            )

    if len(original_guards) != 2:
        raise RuntimeError(
            "Expected exactly two distinct established "
            "subordinate guard objects; found "
            f"{len(original_guards)}."
        )

    replacements = {
        id(original_guard):
            make_class_b_subordinate_guard(
                original_guard
            )
        for original_guard
        in original_guards
    }

    patched = 0

    for target_namespace, original_guard in targets:
        replacement = replacements[
            id(original_guard)
        ]

        target_namespace[
            "is_inside_subordinate_clause"
        ] = replacement

        patched += 1

    return patched


patched_guards = patch_subordinate_guards(
    nominal_ns
)

# Bind Class C to the exact established patched OPEN subordinate guard.
open_subordinate_guard = (
    nominal_ns["ns"]["open_ns"]["namespace"][
        "is_inside_subordinate_clause"
    ]
)

if not callable(
    open_subordinate_guard
):
    raise RuntimeError(
        "Expected established patched OPEN subordinate guard."
    )


if patched_guards < 1:
    raise RuntimeError(
        "Class B correction was not applied "
        "to any subordinate guard."
    )


# ---------------------------------------------------------------------------
# 3. Constituency helpers for provisional Class C.
#
#    This is deliberately NOT the broad 16B rule.
#
#    Default remains subordinate/context.
#    Override requires positive local constituency evidence.
# ---------------------------------------------------------------------------

CORE_ARGUMENT_RELATIONS = {
    "nsubj",
    "nsubj:pass",
    "obj",
    "iobj",
}


def node_label(node):
    return getattr(
        node,
        "label",
        None,
    )


def node_children(node):
    return (
        getattr(
            node,
            "children",
            None,
        )
        or []
    )


def find_target_paths(
    node,
    target_id,
    position_state=None,
    path=(),
):
    """
    Locate the constituency leaf corresponding to a Stanza word ID.

    Word IDs are 1-based token positions for these single-sentence
    diagnostics. We therefore identify the target by leaf position rather
    than surface text, avoiding ambiguity when 'what'/'when' repeats.
    """
    if position_state is None:
        position_state = [0]

    current_path = path + (node,)
    children = node_children(node)

    if not children:
        leaves = node.leaf_labels()

        if len(leaves) != 1:
            return []

        position_state[0] += 1

        if position_state[0] == target_id:
            return [current_path]

        return []

    results = []

    for child in children:
        results.extend(
            find_target_paths(
                child,
                target_id,
                position_state,
                current_path,
            )
        )

    return results


def nearest_ancestor(
    path,
    labels,
):
    for node in reversed(
        path[:-1]
    ):
        if node_label(node) in labels:
            return node

    return None


def direct_child_under(
    path,
    ancestor,
):
    try:
        ancestor_index = path.index(
            ancestor
        )
    except ValueError:
        return None

    child_index = ancestor_index + 1

    if child_index >= len(path):
        return None

    return path[child_index]


def local_question_ownership_evidence(
    sentence,
    word,
    owner,
):
    """
    Return True only when constituency provides positive evidence that a
    dependency-guarded interrogative and its governing predicate belong to
    the same local question-bearing proposition.

    Accepted local forms:
        SBARQ -> WH* + SQ
        SBAR  -> WHNP + S

    Deliberately excluded:
        SBAR  -> WHADVP + S

    The excluded form is used by contextual adverbial clauses such as
    "when publishing ..." and "when conducting ..." in the frozen real
    requirement census.
    """

    if owner is None:
        return False

    constituency = getattr(
        sentence,
        "constituency",
        None,
    )

    if constituency is None:
        return False

    wh_paths = find_target_paths(
        constituency,
        word.id,
    )

    owner_paths = find_target_paths(
        constituency,
        owner.id,
    )

    if (
        len(wh_paths) != 1
        or len(owner_paths) != 1
    ):
        return False

    wh_path = wh_paths[0]
    owner_path = owner_paths[0]

    owner_ancestor_ids = {
        id(node)
        for node in owner_path[:-1]
    }

    shared = None

    for node in reversed(
        wh_path[:-1]
    ):
        if id(node) in owner_ancestor_ids:
            shared = node
            break

    if shared is None:
        return False

    wh_child = direct_child_under(
        wh_path,
        shared,
    )

    owner_child = direct_child_under(
        owner_path,
        shared,
    )

    if (
        wh_child is None
        or owner_child is None
    ):
        return False

    shared_label = node_label(shared)
    wh_label = node_label(wh_child)
    owner_label = node_label(owner_child)

    return (
        (
            shared_label == "SBARQ"
            and wh_label.startswith("WH")
            and owner_label == "SQ"
        )
        or
        (
            shared_label == "SBAR"
            and wh_label == "WHNP"
            and owner_label == "S"
        )
    )


def local_core_argument_evidence(
    sentence,
    word,
    owner,
):
    if owner is None:
        return False

    if word.deprel not in (
        CORE_ARGUMENT_RELATIONS
    ):
        return False

    constituency = getattr(
        sentence,
        "constituency",
        None,
    )

    if constituency is None:
        return False

    word_paths = find_target_paths(
        constituency,
        word.id,
    )

    owner_paths = find_target_paths(
        constituency,
        owner.id,
    )

    if (
        len(word_paths) != 1
        or len(owner_paths) != 1
    ):
        return False

    word_path = word_paths[0]
    owner_path = owner_paths[0]

    word_local = nearest_ancestor(
        word_path,
        {
            "SBAR",
            "SBARQ",
            "S",
            "SQ",
        },
    )

    owner_local = nearest_ancestor(
        owner_path,
        {
            "SBAR",
            "SBARQ",
            "S",
            "SQ",
        },
    )

    if (
        word_local is None
        or owner_local is None
    ):
        return False

    # Positive evidence requires the unresolved core argument and its owner
    # to participate in the same smallest local proposition.
    return word_local is owner_local


# ---------------------------------------------------------------------------
# 4. Resolve established OPEN helper interfaces.
# ---------------------------------------------------------------------------

def find_callable(
    namespace,
    name,
    visited=None,
):
    if visited is None:
        visited = set()

    if not isinstance(
        namespace,
        dict,
    ):
        return None

    namespace_id = id(namespace)

    if namespace_id in visited:
        return None

    visited.add(namespace_id)

    candidate = namespace.get(name)

    if callable(candidate):
        return candidate

    for value in namespace.values():
        if isinstance(value, dict):
            found = find_callable(
                value,
                name,
                visited,
            )

            if found is not None:
                return found

    return None


wh_phrase = find_callable(
    nominal_ns,
    "wh_phrase",
)

governing_predicate = find_callable(
    nominal_ns,
    "governing_predicate",
)

if (
    wh_phrase is None
    or governing_predicate is None
):
    raise RuntimeError(
        "Could not resolve established OPEN "
        "helper interfaces."
    )


# ---------------------------------------------------------------------------
# 5. Provisional Class C recovery.
#
#    We do not alter the conservative Class B subordinate guard.
#    Instead, only rejected interrogative gaps are reconsidered.
# ---------------------------------------------------------------------------

def class_c_open_recoveries(
    sentence,
    established_open,
):
    existing = {
        (
            gap.casefold(),
            owner.casefold(),
        )
        for gap, owner in established_open
    }

    recovered = []

    for word in sentence.words:
        if not (
            word.feats
            and "PronType=Int"
            in word.feats
        ):
            continue

        # Class C only applies when the conservative guard rejects the gap.
        if not open_subordinate_guard(
            sentence,
            word,
        ):
            continue

        owner = governing_predicate(
            sentence,
            word,
        )

        if owner is None:
            continue

        local_question = (
            local_question_ownership_evidence(
                sentence,
                word,
                owner,
            )
        )

        if not local_question:
            continue

        candidate = (
            wh_phrase(
                sentence,
                word,
            ),
            owner.text.casefold(),
        )

        key = (
            candidate[0].casefold(),
            candidate[1].casefold(),
        )

        if key in existing:
            continue

        recovered.append(
            candidate
        )
        existing.add(key)

    return recovered



# ---------------------------------------------------------------------------
# RCV-03E-18H
# Direct-xcomp OPEN-owner duplicate-POLAR suppression.
#
# Architectural question:
# If a POLAR candidate has a direct xcomp child that is already an
# accepted OPEN owner, is the parent POLAR duplicate ownership of the
# same interrogative requirement?
#
# Controlled delta:
# - OPEN extraction unchanged.
# - POLAR candidate discovery unchanged.
# - frozen POLAR subject/AUX/inversion qualification unchanged.
# - suppress only a POLAR candidate whose DIRECT xcomp child is already
#   present in the frozen OPEN-owner set.
#
# No lexical exceptions.
# No generic xcomp exclusion.
# No ADVCL changes.
# No production changes.
# ---------------------------------------------------------------------------

integrated_local = nominal_ns[
    "integrated_local"
]

polar_fn = integrated_local.__globals__.get(
    "extract_polar_frozen"
)

if polar_fn is None:
    raise RuntimeError(
        "STOP: frozen POLAR function not found."
    )

polar_globals = polar_fn.__globals__

original_proposition_candidates = polar_globals.get(
    "proposition_candidates"
)

open_value_owner_ids_frozen = polar_globals.get(
    "open_value_owner_ids"
)

if original_proposition_candidates is None:
    raise RuntimeError(
        "STOP: frozen proposition_candidates not found."
    )

if open_value_owner_ids_frozen is None:
    raise RuntimeError(
        "STOP: frozen open_value_owner_ids not found."
    )


def proposition_candidates_18h(sentence):
    """
    Preserve frozen candidate discovery except where a candidate has a
    direct xcomp child that already owns an accepted OPEN interrogative
    gap.
    """
    candidates = list(
        original_proposition_candidates(
            sentence
        )
    )

    open_owner_ids = (
        open_value_owner_ids_frozen(
            sentence
        )
    )

    filtered = []

    for proposition in candidates:

        direct_xcomp_open_children = [
            word
            for word in sentence.words
            if (
                word.head == proposition.id
                and word.deprel == "xcomp"
                and word.id in open_owner_ids
            )
        ]

        if direct_xcomp_open_children:
            continue

        filtered.append(
            proposition
        )

    return filtered


polar_globals[
    "proposition_candidates"
] = proposition_candidates_18h


print()
print("=" * 112)
print("RCV-03E-18H INTEGRATION")
print(
    "baseline: verified 03E-17C"
)
print(
    "OPEN ownership: unchanged frozen 03D-02"
)
print(
    "POLAR qualification: unchanged frozen 03D-02"
)
print(
    "delta: suppress POLAR candidate only when "
    "direct xcomp child is an accepted OPEN owner"
)
print("=" * 112)
print()

# ---------------------------------------------------------------------------
# 6. Unified 03E-17 extractor.
# ---------------------------------------------------------------------------

def extract_03e17_sentence(
    sentence,
):
    established_open = list(
        nominal_ns[
            "extract_open_local"
        ](
            sentence
        )
    )

    class_c_items = (
        class_c_open_recoveries(
            sentence,
            established_open,
        )
    )

    open_items = (
        established_open
        + class_c_items
    )

    # Reuse 03E-06's established polar integration first.
    _existing_open, polar_items = (
        nominal_ns[
            "integrated_local"
        ](
            sentence
        )
    )

    results = []

    for gap, owner in open_items:
        results.append(
            {
                "kind": "OPEN",
                "owner": owner.casefold(),
                "gap": gap,
            }
        )

    for _slot, owner in polar_items:
        results.append(
            {
                "kind": "POLAR",
                "owner": owner.casefold(),
                "gap": "BOOLEAN_STATUS",
            }
        )

    return results


# ---------------------------------------------------------------------------
# 7. Load frozen real-census CASES without executing 03E-01.
# ---------------------------------------------------------------------------

census_source = Path(
    "rcv_unified_real_census_03e01.py"
).read_text(
    encoding="utf-8-sig"
)

tree_marker = "\ndef lookup(sentence):"

if tree_marker not in census_source:
    raise RuntimeError(
        "03E-01 census marker not found."
    )

census_prefix = census_source.split(
    tree_marker,
    1,
)[0]

census_ns = {
    "__name__": "rcv_03e17_census",
    "__file__": str(
        Path(
            "rcv_unified_real_census_03e01.py"
        ).resolve()
    ),
}

exec(
    compile(
        census_prefix,
        "rcv_unified_real_census_03e01.py",
        "exec",
    ),
    census_ns,
)

CASES = census_ns.get("CASES")

if CASES is None:
    raise RuntimeError(
        "03E-01 CASES not found."
    )

expected_requirement_count = sum(
    len(expected)
    for _case_id, _question, expected
    in CASES
)

if (
    len(CASES) != 19
    or expected_requirement_count != 34
):
    raise RuntimeError(
        "Frozen census mismatch: "
        f"{len(CASES)} questions / "
        f"{expected_requirement_count} requirements."
    )


# ---------------------------------------------------------------------------
# 8. Evaluation.
# ---------------------------------------------------------------------------

def normalise_owner(text):
    return text.casefold().strip()


def expected_signature(expected):
    return [
        (
            kind.casefold(),
            normalise_owner(owner),
        )
        for kind, owner, _slot in expected
    ]


def extracted_signature(extracted):
    return [
        (
            item["kind"].casefold(),
            normalise_owner(
                item["owner"]
            ),
        )
        for item in extracted
    ]


def multiset_missing(
    expected,
    actual,
):
    remaining = list(actual)
    missing = []

    for item in expected:
        if item in remaining:
            remaining.remove(item)
        else:
            missing.append(item)

    return missing


def multiset_extra(
    expected,
    actual,
):
    remaining = list(expected)
    extra = []

    for item in actual:
        if item in remaining:
            remaining.remove(item)
        else:
            extra.append(item)

    return extra


print()
print("=" * 118)
print(
    "RCV-03E-17A: CONTROLLED UNIFIED "
    "REAL-CENSUS INTEGRATION"
)
print("=" * 118)
print()
print(
    f"Class B subordinate guards patched: "
    f"{patched_guards}"
)
print(
    "Automatic subordinate/context relations:",
    sorted(
        SUBORDINATE_RELATIONS_CLASS_B
    ),
)
print(
    "Frozen census:",
    f"{len(CASES)} questions / "
    f"{expected_requirement_count} requirements",
)
print()
print(
    "NOTE: Class C OPEN override remains provisional."
)
print(
    "NOTE: P01 shared-context propagation is not evaluated."
)
print()


question_passes = 0
expected_total = 0
extracted_total = 0
missing_total = 0
extra_total = 0


for case_id, question, expected in CASES:
    doc = nlp(question)

    extracted = []

    for sentence in doc.sentences:
        extracted.extend(
            extract_03e17_sentence(
                sentence
            )
        )

    expected_sig = expected_signature(
        expected
    )

    extracted_sig = extracted_signature(
        extracted
    )

    missing = multiset_missing(
        expected_sig,
        extracted_sig,
    )

    extra = multiset_extra(
        expected_sig,
        extracted_sig,
    )

    passed = (
        len(expected_sig)
        == len(extracted_sig)
        and not missing
        and not extra
    )

    expected_total += len(
        expected_sig
    )
    extracted_total += len(
        extracted_sig
    )
    missing_total += len(missing)
    extra_total += len(extra)

    if passed:
        question_passes += 1

    print()
    print("-" * 118)
    print(case_id)
    print("QUESTION:", question)
    print("EXPECTED:", expected_sig)
    print("EXTRACTED:", extracted_sig)

    if missing:
        print("MISSING:", missing)

    if extra:
        print("EXTRA:", extra)

    print(
        "RESULT:",
        "PASS" if passed else "FAIL",
    )


print()
print("=" * 118)
print("RCV-03E-17A CENSUS SUMMARY")
print("=" * 118)
print()
print(
    f"QUESTION MATCHES: "
    f"{question_passes}/{len(CASES)}"
)
print(
    f"EXPECTED REQUIREMENTS: "
    f"{expected_total}"
)
print(
    f"EXTRACTED REQUIREMENTS: "
    f"{extracted_total}"
)
print(
    f"MISSING REQUIREMENTS: "
    f"{missing_total}"
)
print(
    f"EXTRA REQUIREMENTS: "
    f"{extra_total}"
)
print()

if (
    question_passes == len(CASES)
    and expected_total == 34
    and extracted_total == 34
    and missing_total == 0
    and extra_total == 0
):
    print(
        "INTEGRATION DECISION: "
        "CENSUS PASS / ADVANCE TO FULL REGRESSION"
    )
else:
    print(
        "INTEGRATION DECISION: "
        "RED / CLASSIFY REMAINING FAILURE BEFORE CHANGE"
    )

print()
print(
    "No production code was modified."
)
print(
    "Semantic-slot normalisation and P01 shared-context "
    "propagation remain outside this experiment."
)
print()
print("RCV-03E-17A COMPLETE")
