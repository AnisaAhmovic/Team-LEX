"""S5-04 RCV linguistic-boundary and bounded coverage regression tests."""

from django.test import SimpleTestCase

from api.requirement_coverage import (
    analyse_requirement_coverage_inputs,
    validate_requirement_coverage,
)


def _analysis(text, *, answer_present, relation=None):
    """Build the verified bridge observation contract for validator tests."""
    answer_relations = [relation] if relation else []

    return {
        "text": text,
        "observations": [
            {
                "owner": "avoid",
                "predicate_relation": "root",
                "answer_relations": answer_relations,
                "answer_present": answer_present,
            }
        ],
    }


def _no_avoid_analysis(text):
    """Represent a claim with no qualifying avoid-predicate observation."""
    return {
        "text": text,
        "observations": [],
    }


class RequirementLinguisticIntegrationTests(SimpleTestCase):
    """Protect the real isolated RCV linguistic boundary."""

    def test_combined_boundary_extracts_requirements_and_claim_syntax(self):
        question = (
            "When publishing research involving Exploitable IP, what must La Trobe "
            "staff and students avoid, and how long will a delay in public disclosure "
            "normally last?"
        )

        claims = [
            {
                "text": (
                    "Staff must avoid premature disclosure of research results."
                )
            },
            {
                "text": (
                    "Staff must avoid disclosing research results prematurely."
                )
            },
            {
                "text": "Staff must avoid."
            },
            {
                "text": "The policy explains what staff must avoid."
            },
            {
                "text": "Staff must protect research results."
            },
        ]

        requirements, analyses = analyse_requirement_coverage_inputs(
            question,
            claims,
        )

        self.assertEqual(
            requirements,
            [
                {
                    "kind": "OPEN",
                    "owner": "avoid",
                    "gap": "what",
                },
                {
                    "kind": "OPEN",
                    "owner": "last",
                    "gap": "how long",
                },
            ],
        )

        self.assertEqual(len(analyses), 5)

        self.assertEqual(
            analyses[0]["observations"],
            [
                {
                    "owner": "avoid",
                    "predicate_relation": "root",
                    "answer_relations": ["obj"],
                    "answer_present": True,
                }
            ],
        )

        self.assertEqual(
            analyses[1]["observations"],
            [
                {
                    "owner": "avoid",
                    "predicate_relation": "root",
                    "answer_relations": ["xcomp"],
                    "answer_present": True,
                }
            ],
        )

        self.assertEqual(
            analyses[2]["observations"],
            [
                {
                    "owner": "avoid",
                    "predicate_relation": "root",
                    "answer_relations": [],
                    "answer_present": False,
                }
            ],
        )

        self.assertEqual(
            analyses[3]["observations"],
            [
                {
                    "owner": "avoid",
                    "predicate_relation": "acl:relcl",
                    "answer_relations": [],
                    "answer_present": False,
                }
            ],
        )

        self.assertEqual(
            analyses[4]["observations"],
            [],
        )


class RequirementCoverageTests(SimpleTestCase):
    """Protect deterministic bounded requirement-coverage decisions."""

    def setUp(self):
        self.requirements = [
            {
                "kind": "OPEN",
                "owner": "avoid",
                "gap": "what",
            },
            {
                "kind": "OPEN",
                "owner": "last",
                "gap": "how long",
            },
        ]

    def test_grounded_but_incomplete_duration_answer_is_rejected(self):
        claims = [
            {
                "text": (
                    "La Trobe staff and students must avoid premature disclosure "
                    "of research results when publishing research involving "
                    "Exploitable IP."
                )
            },
            {
                "text": (
                    "A delay in public disclosure of Exploitable IP will normally "
                    "last only the time reasonably necessary to assess and protect "
                    "the Exploitable IP."
                )
            },
        ]

        analyses = [
            _analysis(
                claims[0]["text"],
                answer_present=True,
                relation="obj",
            ),
            _no_avoid_analysis(claims[1]["text"]),
        ]

        complete, details = validate_requirement_coverage(
            self.requirements,
            claims,
            analyses=analyses,
        )

        self.assertFalse(complete, details)
        self.assertEqual(details["status"], "incomplete")
        self.assertEqual(details["requirement_count"], 2)
        self.assertEqual(details["covered_count"], 1)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 2)
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "covered",
        )
        self.assertEqual(
            details["requirements"][1]["coverage_status"],
            "uncovered",
        )

    def test_complete_duration_answer_is_accepted(self):
        claims = [
            {
                "text": (
                    "La Trobe staff and students must avoid premature disclosure "
                    "of research results when publishing research involving "
                    "Exploitable IP."
                )
            },
            {
                "text": (
                    "A delay in public disclosure of Exploitable IP will normally "
                    "not exceed three months."
                )
            },
        ]

        analyses = [
            _analysis(
                claims[0]["text"],
                answer_present=True,
                relation="obj",
            ),
            _no_avoid_analysis(claims[1]["text"]),
        ]

        complete, details = validate_requirement_coverage(
            self.requirements,
            claims,
            analyses=analyses,
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "complete")
        self.assertEqual(details["covered_count"], 2)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 2)
        self.assertEqual(
            details["requirements"][1]["coverage_status"],
            "covered",
        )

    def test_numeric_duration_is_accepted(self):
        requirements = [
            {
                "kind": "OPEN",
                "owner": "last",
                "gap": "how long",
            },
        ]

        complete, details = validate_requirement_coverage(
            requirements,
            [{"text": "The delay may last up to 90 days."}],
            analyses=[],
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "complete")

    def test_vague_duration_language_is_not_accepted(self):
        requirements = [
            {
                "kind": "OPEN",
                "owner": "last",
                "gap": "how long",
            },
        ]

        complete, details = validate_requirement_coverage(
            requirements,
            [{"text": "Any delay should be kept to the minimum necessary."}],
            analyses=[],
        )

        self.assertFalse(complete, details)
        self.assertEqual(details["status"], "incomplete")

    def test_unsupported_requirement_shape_is_not_falsely_covered(self):
        requirements = [
            {
                "kind": "OPEN",
                "owner": "occur",
                "gap": "where",
            },
        ]

        complete, details = validate_requirement_coverage(
            requirements,
            [{"text": "The event occurs at the University."}],
            analyses=[],
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "not_enforced")
        self.assertEqual(details["covered_count"], 0)
        self.assertEqual(details["unknown_count"], 1)
        self.assertEqual(details["enforced_count"], 0)
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "unknown",
        )

    def test_conditional_action_fulfilment_real_boundary(self):
        """A qualified conditional action requires the same fixed condition."""
        question = (
            "What should happen if feedback on an assessment task is delayed?"
        )

        cases = [
            (
                "positive_same_condition",
                "If feedback on an assessment task is delayed, staff must notify students.",
                True,
            ),
            (
                "positive_reordered",
                "Staff must notify students if feedback on an assessment task is delayed.",
                True,
            ),
            (
                "timing_only",
                "Feedback should normally be provided within 15 business days.",
                False,
            ),
            (
                "wrong_condition",
                "If a student submits an assessment late, a penalty applies.",
                False,
            ),
            (
                "related_wrong_condition",
                "If an assessment task is submitted late, staff may apply a penalty.",
                False,
            ),
            (
                "condition_only",
                "Feedback on an assessment task may be delayed.",
                False,
            ),
        ]

        claims = [
            {"text": claim_text}
            for _label, claim_text, _expected in cases
        ]

        requirements, analyses = analyse_requirement_coverage_inputs(
            question,
            claims,
        )

        self.assertEqual(len(requirements), 1, requirements)
        self.assertEqual(
            requirements[0].get("requirement_type"),
            "conditional_action",
        )
        self.assertEqual(len(analyses), len(cases), analyses)

        for index, (label, claim_text, expected_covered) in enumerate(cases):
            with self.subTest(label=label):
                complete, report = validate_requirement_coverage(
                    requirements,
                    [{"text": claim_text}],
                    [analyses[index]],
                )

                self.assertEqual(
                    len(report["requirements"]),
                    1,
                    report,
                )

                requirement_result = report["requirements"][0]

                self.assertEqual(
                    requirement_result.get("requirement_type"),
                    "conditional_action",
                )
                self.assertEqual(
                    requirement_result.get("coverage_status"),
                    "covered" if expected_covered else "uncovered",
                )
                self.assertEqual(
                    requirement_result.get("covered"),
                    expected_covered,
                )
                self.assertEqual(
                    complete,
                    expected_covered,
                )


    def test_conditional_action_question_real_boundary(self):
        """An OPEN-WHAT governing an if-marked advcl is conditional action."""
        question = (
            "What should happen if feedback on an assessment task is delayed?"
        )

        requirements, _analyses = analyse_requirement_coverage_inputs(
            question,
            [],
        )

        self.assertEqual(len(requirements), 1, requirements)
        self.assertEqual(
            requirements[0].get("kind"),
            "OPEN",
            requirements,
        )
        self.assertEqual(
            requirements[0].get("owner"),
            "happen",
            requirements,
        )
        self.assertEqual(
            requirements[0].get("gap"),
            "what",
            requirements,
        )
        self.assertEqual(
            requirements[0].get("requirement_type"),
            "conditional_action",
            requirements,
        )

        ordinary_requirements, _ordinary_analyses = (
            analyse_requirement_coverage_inputs(
                "What does the Assessment Policy provide?",
                [],
            )
        )

        self.assertEqual(
            len(ordinary_requirements),
            1,
            ordinary_requirements,
        )
        self.assertIsNone(
            ordinary_requirements[0].get("requirement_type"),
            ordinary_requirements,
        )
    def test_nominal_copular_purpose_real_boundary(self):
        question = "What is the purpose of the Assessment Policy?"

        positive_claim = {
            "text": (
                "The purpose of the Assessment Policy is to provide the "
                "principles for assuring the quality of student assessment "
                "at La Trobe."
            )
        }

        non_purpose_claim = {
            "text": (
                "The Assessment Policy provides principles for assuring "
                "the quality of student assessment at La Trobe."
            )
        }

        purpose_mention_claim = {
            "text": (
                "The purpose of the Assessment Policy was discussed by "
                "the University."
            )
        }

        combined_claims = [
            positive_claim,
            non_purpose_claim,
            purpose_mention_claim,
        ]

        requirements, analyses = analyse_requirement_coverage_inputs(
            question,
            combined_claims,
        )

        self.assertEqual(len(requirements), 1, requirements)
        self.assertEqual(
            requirements[0].get("requirement_type"),
            "purpose",
            requirements,
        )
        self.assertEqual(
            requirements[0].get("owner"),
            "purpose",
            requirements,
        )
        self.assertEqual(len(analyses), 3, analyses)

        complete, details = validate_requirement_coverage(
            requirements,
            [positive_claim],
            analyses=[analyses[0]],
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "complete")
        self.assertEqual(details["covered_count"], 1)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 1)
        self.assertEqual(
            details["requirements"][0]["requirement_type"],
            "purpose",
        )
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "covered",
        )

        complete, details = validate_requirement_coverage(
            requirements,
            [non_purpose_claim],
            analyses=[analyses[1]],
        )

        self.assertFalse(complete, details)
        self.assertEqual(details["status"], "incomplete")
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "uncovered",
        )

        complete, details = validate_requirement_coverage(
            requirements,
            [purpose_mention_claim],
            analyses=[analyses[2]],
        )

        self.assertFalse(complete, details)
        self.assertEqual(details["status"], "incomplete")
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "uncovered",
        )

    def test_nominal_copular_definition_real_boundary(self):
        question = "What is an inspection?"

        positive_claim = {
            "text": (
                "An inspection is an examination of the workplace to "
                "check for hazards and seek assurance that operational "
                "safety standards are being maintained."
            )
        }

        negative_claim = {
            "text": (
                "Inspections are conducted by La Trobe University."
            )
        }

        combined_claims = [
            positive_claim,
            negative_claim,
        ]

        requirements, analyses = analyse_requirement_coverage_inputs(
            question,
            combined_claims,
        )

        self.assertEqual(len(requirements), 1, requirements)
        self.assertEqual(
            requirements[0].get("requirement_type"),
            "definition",
            requirements,
        )
        self.assertEqual(
            requirements[0].get("owner"),
            "inspection",
            requirements,
        )

        self.assertEqual(len(analyses), 2, analyses)

        complete, details = validate_requirement_coverage(
            requirements,
            [positive_claim],
            analyses=[analyses[0]],
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "complete")
        self.assertEqual(details["covered_count"], 1)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 1)
        self.assertEqual(
            details["requirements"][0]["requirement_type"],
            "definition",
        )
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "covered",
        )

        complete, details = validate_requirement_coverage(
            requirements,
            [negative_claim],
            analyses=[analyses[1]],
        )

        self.assertFalse(complete, details)
        self.assertEqual(details["status"], "incomplete")
        self.assertEqual(details["covered_count"], 0)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 1)
        self.assertEqual(
            details["requirements"][0]["requirement_type"],
            "definition",
        )
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "uncovered",
        )
    def test_definition_with_nominal_copular_answer_is_covered(self):
        requirement = {
            "kind": "OPEN",
            "owner": "inspection",
            "gap": "what",
            "requirement_type": "definition",
        }

        text = (
            "An inspection is an examination of the workplace to check for "
            "hazards and seek assurance that operational safety standards "
            "are being maintained."
        )

        analyses = [
            {
                "text": text,
                "observations": [],
                "definition_observations": [
                    {
                        "owner": "inspection",
                        "predicate_relation": "root",
                        "copular_definition": True,
                    }
                ],
            }
        ]

        complete, details = validate_requirement_coverage(
            [requirement],
            [{"text": text}],
            analyses=analyses,
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "complete")
        self.assertEqual(details["covered_count"], 1)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 1)
        self.assertEqual(
            details["requirements"][0]["requirement_type"],
            "definition",
        )
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "covered",
        )

    def test_definition_without_definitional_relationship_is_uncovered(self):
        requirement = {
            "kind": "OPEN",
            "owner": "inspection",
            "gap": "what",
            "requirement_type": "definition",
        }

        text = "Inspections are conducted by La Trobe University."

        analyses = [
            {
                "text": text,
                "observations": [],
                "definition_observations": [],
            }
        ]

        complete, details = validate_requirement_coverage(
            [requirement],
            [{"text": text}],
            analyses=analyses,
        )

        self.assertFalse(complete, details)
        self.assertEqual(details["status"], "incomplete")
        self.assertEqual(details["covered_count"], 0)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 1)
        self.assertEqual(
            details["requirements"][0]["requirement_type"],
            "definition",
        )
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "uncovered",
        )
    def test_open_what_with_explicit_object_is_covered(self):
        text = "Staff must avoid premature disclosure of research results."

        complete, details = validate_requirement_coverage(
            [
                {
                    "kind": "OPEN",
                    "owner": "avoid",
                    "gap": "what",
                },
            ],
            [{"text": text}],
            analyses=[
                _analysis(
                    text,
                    answer_present=True,
                    relation="obj",
                )
            ],
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "complete")
        self.assertEqual(details["covered_count"], 1)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 1)
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "covered",
        )

    def test_open_what_without_supplied_value_is_uncovered(self):
        text = "Staff must avoid."

        complete, details = validate_requirement_coverage(
            [
                {
                    "kind": "OPEN",
                    "owner": "avoid",
                    "gap": "what",
                },
            ],
            [{"text": text}],
            analyses=[
                _analysis(
                    text,
                    answer_present=False,
                )
            ],
        )

        self.assertFalse(complete, details)
        self.assertEqual(details["status"], "incomplete")
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "uncovered",
        )

    def test_open_what_unresolved_interrogative_is_uncovered(self):
        text = "The policy explains what staff must avoid."

        complete, details = validate_requirement_coverage(
            [
                {
                    "kind": "OPEN",
                    "owner": "avoid",
                    "gap": "what",
                },
            ],
            [{"text": text}],
            analyses=[
                {
                    "text": text,
                    "observations": [
                        {
                            "owner": "avoid",
                            "predicate_relation": "acl:relcl",
                            "answer_relations": [],
                            "answer_present": False,
                        }
                    ],
                }
            ],
        )

        self.assertFalse(complete, details)
        self.assertEqual(details["status"], "incomplete")
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "uncovered",
        )

    def test_open_what_with_xcomp_is_covered(self):
        text = "Staff must avoid disclosing research results prematurely."

        complete, details = validate_requirement_coverage(
            [
                {
                    "kind": "OPEN",
                    "owner": "avoid",
                    "gap": "what",
                },
            ],
            [{"text": text}],
            analyses=[
                _analysis(
                    text,
                    answer_present=True,
                    relation="xcomp",
                )
            ],
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "complete")
        self.assertEqual(details["covered_count"], 1)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 1)
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "covered",
        )

    def test_open_what_wrong_predicate_is_uncovered(self):
        text = "Staff must protect research results."

        complete, details = validate_requirement_coverage(
            [
                {
                    "kind": "OPEN",
                    "owner": "avoid",
                    "gap": "what",
                },
            ],
            [{"text": text}],
            analyses=[
                _no_avoid_analysis(text)
            ],
        )

        self.assertFalse(complete, details)
        self.assertEqual(details["status"], "incomplete")
        self.assertEqual(details["covered_count"], 0)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 1)
        self.assertEqual(
            details["requirements"][0]["coverage_status"],
            "uncovered",
        )

    def test_compound_open_what_and_duration_are_both_covered(self):
        claims = [
            {
                "text": (
                    "La Trobe staff and students must avoid premature disclosure "
                    "of research results."
                )
            },
            {
                "text": (
                    "A delay in public disclosure of Exploitable IP will normally "
                    "not exceed three months."
                )
            },
        ]

        analyses = [
            _analysis(
                claims[0]["text"],
                answer_present=True,
                relation="obj",
            ),
            _no_avoid_analysis(claims[1]["text"]),
        ]

        complete, details = validate_requirement_coverage(
            self.requirements,
            claims,
            analyses=analyses,
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "complete")
        self.assertEqual(details["requirement_count"], 2)
        self.assertEqual(details["covered_count"], 2)
        self.assertEqual(details["unknown_count"], 0)
        self.assertEqual(details["enforced_count"], 2)
        self.assertEqual(
            [item["coverage_status"] for item in details["requirements"]],
            ["covered", "covered"],
        )

    def test_multiple_duration_requirements_are_not_unsafely_mapped(self):
        requirements = [
            {
                "kind": "OPEN",
                "owner": "last",
                "gap": "how long",
            },
            {
                "kind": "OPEN",
                "owner": "remain",
                "gap": "how long",
            },
        ]

        complete, details = validate_requirement_coverage(
            requirements,
            [{"text": "One period is three months."}],
            analyses=[],
        )

        self.assertTrue(complete, details)
        self.assertEqual(details["status"], "not_enforced")
        self.assertEqual(details["enforced_count"], 0)
        self.assertEqual(details["unknown_count"], 2)
