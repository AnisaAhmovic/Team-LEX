from django.test import SimpleTestCase

from api.groundedness import preserves_policy_constraints


class PolicyConstraintTests(SimpleTestCase):
    def assertPreserved(self, claim, quote):
        preserved, details = preserves_policy_constraints(claim, [quote])
        self.assertTrue(preserved, details)

    def assertRejected(self, claim, quote):
        preserved, details = preserves_policy_constraints(claim, [quote])
        self.assertFalse(preserved, details)

    def test_mandatory_requirement_preserved(self):
        self.assertPreserved(
            "Staff must return University property before departure.",
            "Staff are required to return University property before departure.",
        )

    def test_mandatory_requirement_cannot_be_weakened_to_permission(self):
        self.assertRejected(
            "Staff may return University property before departure.",
            "Staff must return University property before departure.",
        )

    def test_approval_prerequisite_preserved(self):
        self.assertPreserved(
            "Staff may use a fleet vehicle where prior authorisation has been granted.",
            "Staff may use a fleet vehicle where prior approval has been granted.",
        )

    def test_approval_prerequisite_cannot_be_removed(self):
        self.assertRejected(
            "Staff may use a fleet vehicle.",
            "Staff may use a fleet vehicle where prior approval has been granted.",
        )

    def test_consent_prerequisite_preserved(self):
        self.assertPreserved(
            "The material may be disclosed with permission from the owner.",
            "The material may be disclosed with consent from the owner.",
        )

    def test_consent_prerequisite_cannot_be_removed(self):
        self.assertRejected(
            "The material may be disclosed.",
            "The material may be disclosed with consent from the owner.",
        )

    def test_exception_preserved(self):
        self.assertPreserved(
            "The activity must not occur unless approval is granted.",
            "The activity is prohibited unless approval is granted.",
        )

    def test_exception_cannot_be_removed(self):
        self.assertRejected(
            "The activity is prohibited.",
            "The activity must not occur unless approval is granted.",
        )


    def test_concessive_even_if_does_not_create_required_conditionality(self):
        self.assertPreserved(
            "A person must not approve their own recommendation.",
            "Even if a person has the appropriate authority, they must not approve their own recommendation.",
        )

    def test_genuine_if_condition_cannot_be_removed(self):
        self.assertRejected(
            "A person must obtain approval.",
            "If the expenditure exceeds the threshold, a person must obtain approval.",
        )


class SemanticGroundednessTests(SimpleTestCase):
    def test_faithful_paraphrase_is_supported(self):
        from api.groundedness import is_semantically_supported

        supported, probabilities = is_semantically_supported(
            "Costing is the process of determining and calculating all expenses "
            "associated with conducting a research project.",
            [
                "Costing: the process of determining and calculating all the expenses "
                "associated with conducting a research project. This includes both "
                "Direct Costs and Indirect Costs."
            ],
        )

        self.assertTrue(supported, probabilities)

    def test_unsupported_subject_qualifier_is_rejected(self):
        from api.groundedness import is_semantically_supported

        supported, probabilities = is_semantically_supported(
            "A road safety audit is the systematic and independent examination of "
            "documents or process to ascertain a true and fair view of the risk "
            "controls under review.",
            [
                "Audit: is the systematic and independent examination of documents "
                "or process to ascertain a true and fair view of the risk controls "
                "under review."
            ],
        )

        self.assertFalse(supported, probabilities)


    def test_trusted_context_can_resolve_institutional_reference(self):
        from api.groundedness import is_semantically_supported

        supported, probabilities = is_semantically_supported(
            "La Trobe University expects research to be conducted responsibly, "
            "ethically, and with integrity.",
            [
                "The University expects research to be conducted responsibly, "
                "ethically and with integrity."
            ],
            trusted_context=(
                "This evidence is from an authoritative La Trobe University policy source."
            ),
        )

        self.assertTrue(supported, probabilities)

    def test_trusted_context_does_not_authorise_actor_generalisation(self):
        from api.groundedness import is_semantically_supported

        supported, probabilities = is_semantically_supported(
            "All staff and students who engage in research are expected to adhere "
            "to responsible research practices as established by the University.",
            [
                "La Trobe research staff and students are expected to adhere to "
                "the responsible research practices as established by the University."
            ],
            trusted_context=(
                "This evidence is from an authoritative La Trobe University policy source."
            ),
        )

        self.assertFalse(supported, probabilities)
