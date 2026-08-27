from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from retrieval import QuestionValidationError, RetrievalUnavailableError


class PolicyEvidenceEndpointTests(APITestCase):
    @patch("api.views.get_policy_retriever")
    def test_returns_supported_evidence(self, get_retriever):
        get_retriever.return_value.retrieve.return_value = {
            "status": "supported",
            "question": "What is the assessment policy?",
            "evidence_sufficient": True,
            "result_count": 1,
            "evidence": [
                {
                    "policy_text": "Evidence",
                    "policy_title": "Assessment Policy",
                    "section": "Section 5",
                    "source_url": "https://policies.latrobe.edu.au/document/view.php?id=216",
                    "similarity_score": 0.82,
                }
            ],
        }

        response = self.client.post(
            reverse("policy-evidence"),
            {"question": "What is the assessment policy?"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "supported")

    @patch("api.views.get_policy_retriever")
    def test_invalid_question_returns_400_fallback(self, get_retriever):
        get_retriever.return_value.retrieve.side_effect = QuestionValidationError(
            "Question must be provided as text."
        )

        response = self.client.post(
            reverse("policy-evidence"), {"question": ""}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "fallback")
        self.assertEqual(response.data["evidence"], [])
        self.assertIn("validation_error", response.data)

    @patch("api.views.get_policy_retriever")
    def test_retrieval_failure_returns_503_without_internal_details(self, get_retriever):
        get_retriever.return_value.retrieve.side_effect = RetrievalUnavailableError(
            "internal detail"
        )

        response = self.client.post(
            reverse("policy-evidence"),
            {"question": "What is the assessment policy?"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["fallback_reason"], "retrieval_unavailable")
        self.assertNotIn("internal detail", str(response.data))
