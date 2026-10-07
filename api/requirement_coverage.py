"""
Requirement Coverage Validator (RCV).

Production-facing boundary for the validated RCV-03E-18H requirement
extractor plus bounded requirement-fulfilment validation.

The structural parser remains isolated in .rcv_stanza_venv so that its
validated Stanza dependency stack does not alter the main LEX runtime.

Current production enforcement is deliberately bounded:
- RCV-03E-18H identifies structural requirements.
- A single OPEN "how long" requirement is enforceable as duration.
- Duration fulfilment requires an explicit duration value.
- Other requirement shapes remain UNKNOWN and are not falsely treated
  as covered.
"""

import json
from pathlib import Path
import re
import subprocess


_ROOT = Path(__file__).resolve().parent.parent

_RCV_PYTHON = (
    _ROOT
    / ".rcv_stanza_venv"
    / "Scripts"
    / "python.exe"
)

_RCV_RUNNER = _ROOT / "rcv_runtime_bridge.py"

_RCV_TIMEOUT_SECONDS = 180

_NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|"
    "eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
    "seventeen|eighteen|nineteen|twenty|thirty|forty|"
    "fifty|sixty|seventy|eighty|ninety|hundred"
)

_TIME_UNITS = (
    "second|seconds|minute|minutes|hour|hours|day|days|"
    "week|weeks|month|months|year|years"
)

_DURATION_VALUE = re.compile(
    rf"\b(?:\d+|{_NUMBER_WORDS})\s+"
    rf"(?:{_TIME_UNITS})\b",
    re.IGNORECASE,
)


def extract_requirements(question):
    """
    Extract information requirements using the validated RCV-03E-18H
    structural parser running in its dedicated environment.

    Returns dictionaries containing:
        kind  - OPEN or POLAR
        owner - question-bearing predicate
        gap   - requested open-value phrase or BOOLEAN_STATUS
    """
    text = (question or "").strip()

    if not text:
        return []

    if not _RCV_PYTHON.exists():
        raise RuntimeError(
            "Dedicated RCV Python runtime is unavailable."
        )

    if not _RCV_RUNNER.exists():
        raise RuntimeError(
            "RCV runtime bridge is unavailable."
        )

    payload = json.dumps(
        {"question": text},
        ensure_ascii=False,
    )

    try:
        completed = subprocess.run(
            [str(_RCV_PYTHON), str(_RCV_RUNNER)],
            input=payload,
            text=True,
            capture_output=True,
            cwd=str(_ROOT),
            timeout=_RCV_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "RCV requirement extraction timed out."
        ) from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip()

        raise RuntimeError(
            "RCV requirement extraction failed"
            + (f": {detail}" if detail else ".")
        )

    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "RCV runtime returned invalid JSON."
        ) from exc

    requirements = response.get("requirements")

    if not isinstance(requirements, list):
        raise RuntimeError(
            "RCV runtime returned an invalid requirement payload."
        )

    return requirements


def _claim_texts(claims):
    """Normalise validated claim dictionaries or strings to claim text."""
    texts = []

    for claim in claims or []:
        if isinstance(claim, str):
            text = claim.strip()
        elif isinstance(claim, dict):
            value = claim.get("text")
            text = value.strip() if isinstance(value, str) else ""
        else:
            text = ""

        if text:
            texts.append(text)

    return texts


def _requirement_type(requirement):
    if not isinstance(requirement, dict):
        return ""

    return str(
        requirement.get("requirement_type") or ""
    ).casefold().strip()


def _is_definition_requirement(requirement):
    """Return True only for an explicitly classified DEFINITION requirement."""
    if not isinstance(requirement, dict):
        return False

    kind = str(requirement.get("kind") or "").casefold().strip()
    owner = str(requirement.get("owner") or "").casefold().strip()
    gap = str(requirement.get("gap") or "").casefold().strip()

    return (
        kind == "open"
        and bool(owner)
        and gap == "what"
        and _requirement_type(requirement) == "definition"
    )


def _is_purpose_requirement(requirement):
    """Return True only for the qualified relational PURPOSE requirement."""
    if not isinstance(requirement, dict):
        return False

    kind = str(requirement.get("kind") or "").casefold().strip()
    owner = str(requirement.get("owner") or "").casefold().strip()
    gap = str(requirement.get("gap") or "").casefold().strip()

    return (
        kind == "open"
        and owner == "purpose"
        and gap == "what"
        and _requirement_type(requirement) == "purpose"
    )


def _is_conditional_action_requirement(requirement):
    """Return True only for a qualified CONDITIONAL_ACTION requirement."""
    if not isinstance(requirement, dict):
        return False

    kind = str(requirement.get("kind") or "").casefold().strip()
    owner = str(requirement.get("owner") or "").casefold().strip()
    gap = str(requirement.get("gap") or "").casefold().strip()

    return (
        kind == "open"
        and bool(owner)
        and gap == "what"
        and _requirement_type(requirement) == "conditional_action"
        and isinstance(requirement.get("condition_signature"), dict)
    )


def _is_open_what_requirement(requirement):
    """
    Return True only for the bounded verbal OPEN 'what' requirement shape.

    Explicit DEFINITION requirements use their own fulfilment contract.
    """
    if not isinstance(requirement, dict):
        return False

    kind = str(requirement.get("kind") or "").casefold().strip()
    owner = str(requirement.get("owner") or "").casefold().strip()
    gap = str(requirement.get("gap") or "").casefold().strip()

    return (
        kind == "open"
        and bool(owner)
        and gap == "what"
        and _requirement_type(requirement)
            not in {"definition", "purpose", "conditional_action"}
    )


def analyse_requirement_coverage_inputs(question, claims):
    """
    Extract requirements and bounded claim syntax in one isolated RCV run.

    The bridge reports linguistic structure only. Coverage and acceptance
    decisions remain in this module and the Django request path.
    """
    claim_texts = _claim_texts(claims)

    payload = json.dumps(
        {
            "coverage_analysis": {
                "question": str(question or ""),
                "texts": claim_texts,
            }
        },
        ensure_ascii=False,
    )

    try:
        completed = subprocess.run(
            [str(_RCV_PYTHON), str(_RCV_RUNNER)],
            input=payload,
            text=True,
            capture_output=True,
            cwd=str(_ROOT),
            timeout=_RCV_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "RCV coverage analysis timed out."
        ) from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip()
        raise RuntimeError(
            "RCV coverage analysis failed"
            + (f": {detail}" if detail else ".")
        )

    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "RCV coverage analysis returned invalid JSON."
        ) from exc

    requirements = response.get("requirements")
    analyses = response.get("analyses")

    if not isinstance(requirements, list):
        raise RuntimeError(
            "RCV coverage analysis returned invalid requirements."
        )

    if not isinstance(analyses, list):
        raise RuntimeError(
            "RCV coverage analysis returned invalid analyses."
        )

    return requirements, analyses

def _analyse_claims_for_owners(claim_texts, owners):
    """
    Ask the isolated Stanza runtime for bounded linguistic observations.

    The bridge reports syntax only; coverage decisions remain in this module.
    """
    payload = json.dumps(
        {
            "claim_analysis": {
                "texts": list(claim_texts),
                "owners": list(owners),
            }
        },
        ensure_ascii=False,
    )

    try:
        completed = subprocess.run(
            [str(_RCV_PYTHON), str(_RCV_RUNNER)],
            input=payload,
            text=True,
            capture_output=True,
            cwd=str(_ROOT),
            timeout=_RCV_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "RCV claim analysis timed out."
        ) from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip()

        raise RuntimeError(
            "RCV claim analysis failed"
            + (f": {detail}" if detail else ".")
        )

    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "RCV claim analysis returned invalid JSON."
        ) from exc

    analyses = response.get("analyses")

    if not isinstance(analyses, list):
        raise RuntimeError(
            "RCV claim analysis returned an invalid payload."
        )

    return analyses


def _conditional_action_fulfilled(requirement, analyses):
    """
    Require an already-validated claim to supply a consequence under the
    same conservatively matched fixed condition.
    """
    expected_condition = requirement.get("condition_signature")

    if not isinstance(expected_condition, dict):
        return False

    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue

        observations = analysis.get("conditional_action_observations")

        if not isinstance(observations, list):
            continue

        for observation in observations:
            if not isinstance(observation, dict):
                continue

            if (
                observation.get("condition_signature") == expected_condition
                and observation.get("consequence_present") is True
            ):
                return True

    return False


def _open_what_fulfilled(requirement, analyses):
    """
    Require an owner predicate with an explicit answer-bearing obj/xcomp.

    Claim truth and policy support have already been validated upstream.
    """
    owner = str(requirement.get("owner") or "").casefold().strip()

    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue

        observations = analysis.get("observations")

        if not isinstance(observations, list):
            continue

        for observation in observations:
            if not isinstance(observation, dict):
                continue

            if (
                str(observation.get("owner") or "").casefold().strip()
                == owner
                and observation.get("answer_present") is True
            ):
                return True

    return False


def _is_duration_requirement(requirement):
    """Return True only for the validated OPEN 'how long' requirement shape."""
    if not isinstance(requirement, dict):
        return False

    kind = str(requirement.get("kind") or "").casefold().strip()
    gap = str(requirement.get("gap") or "").casefold().strip()

    return kind == "open" and gap == "how long"


def _duration_fulfilled(claim_texts):
    """
    Apply the validated RCV-01B-02 explicit duration-value contract.

    This contract establishes requested-value presence only. Grounding,
    citation, attribution and policy-constraint validation occur upstream.
    """
    return any(
        _DURATION_VALUE.search(text)
        for text in claim_texts
    )


def _purpose_fulfilled(requirement, analyses):
    """
    Require a bounded explicit PURPOSE relationship in an already-validated
    claim.
    """
    owner = str(requirement.get("owner") or "").casefold().strip()

    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue

        observations = analysis.get("purpose_observations")

        if not isinstance(observations, list):
            continue

        for observation in observations:
            if not isinstance(observation, dict):
                continue

            observed_owner = str(
                observation.get("owner") or ""
            ).casefold().strip()

            if (
                observed_owner == owner
                and observation.get("purpose_answer") is True
            ):
                return True

    return False


def _definition_fulfilled(requirement, analyses):
    """
    Require the requested nominal owner to participate as the subject of a
    bounded copular nominal definition in an already-validated claim.
    """
    owner = str(requirement.get("owner") or "").casefold().strip()

    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue

        observations = analysis.get("definition_observations")

        if not isinstance(observations, list):
            continue

        for observation in observations:
            if not isinstance(observation, dict):
                continue

            observed_owner = str(
                observation.get("owner") or ""
            ).casefold().strip()

            if (
                observed_owner == owner
                and observation.get("copular_definition") is True
            ):
                return True

    return False


def validate_requirement_coverage(requirements, claims, analyses=None):
    """
    Validate the currently enforceable subset of extracted requirements.

    Supported bounded shapes:
    - exactly one OPEN "how long" requirement -> explicit duration value
    - OPEN "what" requirements with a unique owner -> owner predicate must
      govern an explicit answer-bearing obj/xcomp in a validated claim

    Unsupported or ambiguous requirement shapes remain UNKNOWN.
    """
    requirements = list(requirements or [])
    claim_texts = _claim_texts(claims)

    duration_indexes = [
        index
        for index, requirement in enumerate(requirements)
        if _is_duration_requirement(requirement)
    ]

    enforce_duration = len(duration_indexes) == 1
    duration_index = (
        duration_indexes[0]
        if enforce_duration
        else None
    )

    definition_indexes = {
        index
        for index, requirement in enumerate(requirements)
        if _is_definition_requirement(requirement)
    }

    purpose_indexes = {
        index
        for index, requirement in enumerate(requirements)
        if _is_purpose_requirement(requirement)
    }

    conditional_action_indexes = {
        index
        for index, requirement in enumerate(requirements)
        if _is_conditional_action_requirement(requirement)
    }

    open_what_indexes = [
        index
        for index, requirement in enumerate(requirements)
        if (
            _is_open_what_requirement(requirement)
            and index not in definition_indexes
        )
    ]

    owner_counts = {}

    for index in open_what_indexes:
        owner = str(
            requirements[index].get("owner") or ""
        ).casefold().strip()

        owner_counts[owner] = owner_counts.get(owner, 0) + 1

    enforceable_open_what_indexes = [
        index
        for index in open_what_indexes
        if owner_counts[
            str(
                requirements[index].get("owner") or ""
            ).casefold().strip()
        ] == 1
    ]

    open_what_owners = [
        str(
            requirements[index].get("owner") or ""
        ).casefold().strip()
        for index in enforceable_open_what_indexes
    ]

    if analyses is None:
        analyses = (
            _analyse_claims_for_owners(
                claim_texts,
                open_what_owners,
            )
            if open_what_owners
            else []
        )
    elif not isinstance(analyses, list):
        raise TypeError("RCV analyses must be a list.")

    details = []

    for index, requirement in enumerate(requirements):
        item = dict(requirement)

        if index == duration_index:
            covered = _duration_fulfilled(claim_texts)

            item.update({
                "requirement_type": "duration",
                "coverage_status": (
                    "covered"
                    if covered
                    else "uncovered"
                ),
                "covered": covered,
            })

        elif index in purpose_indexes:
            covered = _purpose_fulfilled(
                requirement,
                analyses,
            )

            item.update({
                "requirement_type": "purpose",
                "coverage_status": (
                    "covered"
                    if covered
                    else "uncovered"
                ),
                "covered": covered,
            })

        elif index in definition_indexes:
            covered = _definition_fulfilled(
                requirement,
                analyses,
            )

            item.update({
                "requirement_type": "definition",
                "coverage_status": (
                    "covered"
                    if covered
                    else "uncovered"
                ),
                "covered": covered,
            })

        elif index in conditional_action_indexes:
            covered = _conditional_action_fulfilled(
                requirement,
                analyses,
            )

            item.update({
                "requirement_type": "conditional_action",
                "coverage_status": (
                    "covered"
                    if covered
                    else "uncovered"
                ),
                "covered": covered,
            })

        elif index in enforceable_open_what_indexes:
            covered = _open_what_fulfilled(
                requirement,
                analyses,
            )

            item.update({
                "requirement_type": "open_what",
                "coverage_status": (
                    "covered"
                    if covered
                    else "uncovered"
                ),
                "covered": covered,
            })

        else:
            item.update({
                "requirement_type": (
                    "duration"
                    if _is_duration_requirement(requirement)
                    else (
                        "purpose"
                        if _is_purpose_requirement(requirement)
                        else (
                            "definition"
                            if _is_definition_requirement(requirement)
                            else (
                                "open_what"
                                if _is_open_what_requirement(requirement)
                                else "unsupported"
                            )
                        )
                    )
                ),
                "coverage_status": "unknown",
                "covered": None,
            })

        details.append(item)

    uncovered = [
        item
        for item in details
        if item["coverage_status"] == "uncovered"
    ]

    covered_count = sum(
        item["coverage_status"] == "covered"
        for item in details
    )

    unknown_count = sum(
        item["coverage_status"] == "unknown"
        for item in details
    )

    enforced_count = sum(
        item["coverage_status"] in {"covered", "uncovered"}
        for item in details
    )

    if uncovered:
        status = "incomplete"
        complete = False
    elif enforced_count:
        status = "complete"
        complete = True
    else:
        status = "not_enforced"
        complete = True

    return complete, {
        "status": status,
        "requirement_count": len(details),
        "covered_count": covered_count,
        "unknown_count": unknown_count,
        "enforced_count": enforced_count,
        "requirements": details,
    }
