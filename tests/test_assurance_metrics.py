from api.views import _build_assurance


def test_assurance_reports_percentage_when_all_requirements_are_assessed():
    assurance = _build_assurance({
        "covered_count": 2,
        "enforced_count": 2,
        "unknown_count": 0,
    })

    assert assurance["question_coverage"] == {
        "covered": 2,
        "enforced": 2,
        "unknown": 0,
        "percentage": 100,
    }
    assert assurance["supported_by_current_policy"] is True
    assert assurance["policy_conditions_preserved"] is True
    assert assurance["sources_verified"] is True


def test_assurance_suppresses_percentage_when_requirement_is_unknown():
    assurance = _build_assurance({
        "covered_count": 2,
        "enforced_count": 2,
        "unknown_count": 1,
    })

    assert assurance["question_coverage"]["percentage"] is None
    assert assurance["question_coverage"]["covered"] == 2
    assert assurance["question_coverage"]["unknown"] == 1


def test_assurance_suppresses_percentage_when_nothing_is_enforced():
    assurance = _build_assurance({
        "covered_count": 0,
        "enforced_count": 0,
        "unknown_count": 1,
    })

    assert assurance["question_coverage"]["percentage"] is None