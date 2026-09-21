"""
Django API tests (COPL-255).

Covers the existing /api/retrieve/ endpoint (regression) and the new
/api/answer/ endpoint (full RAG pipeline).

All Qdrant, BGE-M3 and Ollama calls are mocked so the tests run without
any local services running — same approach used in the existing test suite.
"""

from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework.test import APITestCase

from retrieval import QuestionValidationError, RetrievalUnavailableError
from llm import LLMConnectionError

# ── Shared test fixtures ──────────────────────────────────────────────────────

SAMPLE_QUESTION = "What is the assessment policy?"

SAMPLE_EVIDENCE = [
    {
        "policy_text": "Feedback on assessment tasks is timely and constructive.",
        "policy_title": "Assessment Policy",
        "section": "Section 5 - Policy Statement",
        "source_url": "https://policies.latrobe.edu.au/document/view.php?id=216",
        "similarity_score": 0.82,
    }
]

SUPPORTED_RETRIEVAL = {
    "status": "supported",
    "question": SAMPLE_QUESTION,
    "evidence_sufficient": True,
    "result_count": 1,
    "evidence": SAMPLE_EVIDENCE,
}

FALLBACK_RETRIEVAL = {
    "status": "fallback",
    "question": SAMPLE_QUESTION,
    "evidence_sufficient": False,
    "evidence": [],
    "message": "I could not find enough current, authoritative La Trobe policy evidence.",
    "fallback_reason": "insufficient_evidence",
    "escalation": {
        "message": "Check the official La Trobe Policy Library.",
        "url": "https://policies.latrobe.edu.au/",
    },
}

SAMPLE_GENERATION = {
    "text": "Assessment feedback must be timely and constructive per Section 5.",
    "model": "qwen3:4b",
    "latency_seconds": 1.23,
    "done": True,
    "prompt_eval_count": 120,
    "eval_count": 40,
}


# ── /api/retrieve/ regression tests (Sprint 3 behaviour must be preserved) ────

class PolicyEvidenceEndpointTests(APITestCase):
    @patch("api.views.get_policy_retriever")
    def test_returns_supported_evidence(self, get_retriever):
        get_retriever.return_value.retrieve.return_value = SUPPORTED_RETRIEVAL

        response = self.client.post(
            reverse("policy-evidence"),
            {"question": SAMPLE_QUESTION},
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
            {"question": SAMPLE_QUESTION},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["fallback_reason"], "retrieval_unavailable")
        self.assertNotIn("internal detail", str(response.data))


# ── /api/answer/ tests ────────────────────────────────────────────────────────

class PolicyAnswerEndpointTests(APITestCase):

    @patch("api.views.get_qwen_service")
    @patch("api.views.get_policy_retriever")
    def test_supported_answer_returns_structured_json(
        self, get_retriever, get_qwen
    ):
        get_retriever.return_value.retrieve.return_value = SUPPORTED_RETRIEVAL
        get_qwen.return_value.generate.return_value = SAMPLE_GENERATION

        response = self.client.post(
            reverse("policy-answer"),
            {"question": SAMPLE_QUESTION},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "supported")
        self.assertEqual(response.data["question"], SAMPLE_QUESTION)
        self.assertIn("answer", response.data)
        self.assertIsNotNone(response.data["answer"])
        self.assertIn("sources", response.data)
        self.assertTrue(response.data["evidence_sufficient"])
        self.assertIn("model", response.data)
        self.assertIn("latency_seconds", response.data)

    @patch("api.views.get_qwen_service")
    @patch("api.views.get_policy_retriever")
    def test_sources_contain_expected_fields(self, get_retriever, get_qwen):
        get_retriever.return_value.retrieve.return_value = SUPPORTED_RETRIEVAL
        get_qwen.return_value.generate.return_value = SAMPLE_GENERATION

        response = self.client.post(
            reverse("policy-answer"),
            {"question": SAMPLE_QUESTION},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        source = response.data["sources"][0]
        self.assertIn("policy_title", source)
        self.assertIn("section", source)
        self.assertIn("source_url", source)
        self.assertIn("similarity_score", source)

    @patch("api.views.get_qwen_service")
    @patch("api.views.get_policy_retriever")
    def test_fallback_retrieval_bypasses_generation(self, get_retriever, get_qwen):
        """When retrieval finds insufficient evidence, Qwen3 must not be called."""
        get_retriever.return_value.retrieve.return_value = FALLBACK_RETRIEVAL

        response = self.client.post(
            reverse("policy-answer"),
            {"question": SAMPLE_QUESTION},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "fallback")
        self.assertIsNone(response.data["answer"])
        get_qwen.return_value.generate.assert_not_called()

    @patch("api.views.get_policy_retriever")
    def test_invalid_question_returns_400(self, get_retriever):
        get_retriever.return_value.retrieve.side_effect = QuestionValidationError(
            "Question must be provided as text."
        )

        response = self.client.post(
            reverse("policy-answer"), {"question": ""}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "fallback")
        self.assertIn("validation_error", response.data)

    @patch("api.views.get_policy_retriever")
    def test_retrieval_failure_returns_503(self, get_retriever):
        get_retriever.return_value.retrieve.side_effect = RetrievalUnavailableError(
            "qdrant is down"
        )

        response = self.client.post(
            reverse("policy-answer"),
            {"question": SAMPLE_QUESTION},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("qdrant is down", str(response.data))

    @patch("api.views.get_qwen_service")
    @patch("api.views.get_policy_retriever")
    def test_generation_failure_returns_502_without_internal_details(
        self, get_retriever, get_qwen
    ):
        get_retriever.return_value.retrieve.return_value = SUPPORTED_RETRIEVAL
        get_qwen.return_value.generate.side_effect = LLMConnectionError(
            "ollama is not running"
        )

        response = self.client.post(
            reverse("policy-answer"),
            {"question": SAMPLE_QUESTION},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["status"], "fallback")
        self.assertNotIn("ollama is not running", str(response.data))

    @patch("api.views.get_qwen_service")
    @patch("api.views.get_policy_retriever")
    def test_missing_question_field_returns_400(self, get_retriever, get_qwen):
        get_retriever.return_value.retrieve.side_effect = QuestionValidationError(
            "Question must be provided as text."
        )

        response = self.client.post(
            reverse("policy-answer"),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("api.views.get_qwen_service")
    @patch("api.views.get_policy_retriever")
    def test_sources_are_deduplicated(self, get_retriever, get_qwen):
        """Two chunks from the same URL should produce only one source entry."""
        duplicate_evidence = SAMPLE_EVIDENCE + [
            {
                **SAMPLE_EVIDENCE[0],
                "section": "Section 6 - Procedures",
                "policy_text": "Another chunk from the same document.",
            }
        ]
        get_retriever.return_value.retrieve.return_value = {
            **SUPPORTED_RETRIEVAL,
            "evidence": duplicate_evidence,
            "result_count": 2,
        }
        get_qwen.return_value.generate.return_value = SAMPLE_GENERATION

        response = self.client.post(
            reverse("policy-answer"),
            {"question": SAMPLE_QUESTION},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["sources"]), 1)
