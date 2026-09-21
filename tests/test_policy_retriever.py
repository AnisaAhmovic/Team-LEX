from types import SimpleNamespace
from unittest import TestCase

from retrieval import (
    PolicyRetriever,
    QuestionValidationError,
    RetrievalUnavailableError,
    validate_question,
)


def embedding():
    return [0.01] * 1024


def current_point(score=0.82, **payload_overrides):
    payload = {
        "text": "Feedback on assessment tasks is timely, constructive and formative.",
        "policy_title": "Assessment Policy",
        "section": "Section 5 - Policy Statement",
        "source_url": "https://policies.latrobe.edu.au/document/view.php?id=216",
        "status": "Current",
    }
    payload.update(payload_overrides)
    return SimpleNamespace(score=score, payload=payload)


class FakeClient:
    def __init__(self, points=None, error=None):
        self.points = points or []
        self.error = error
        self.call = None

    def query_points(self, **kwargs):
        self.call = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(points=self.points)


class QuestionValidationTests(TestCase):
    def test_normalises_a_natural_language_question(self):
        self.assertEqual(
            validate_question("  What   is the assessment policy?  "),
            "What is the assessment policy?",
        )

    def test_rejects_missing_or_non_text_questions(self):
        for value in (None, "", "  ", "??", 42):
            with self.subTest(value=value):
                with self.assertRaises(QuestionValidationError):
                    validate_question(value)

    def test_rejects_excessively_long_questions(self):
        with self.assertRaises(QuestionValidationError):
            validate_question("a" * 501)


class PolicyRetrieverTests(TestCase):
    def test_supported_question_returns_complete_current_policy_evidence(self):
        client = FakeClient([current_point()])
        embedded_questions = []
        retriever = PolicyRetriever(
            client=client,
            embedder=lambda question: embedded_questions.append(question) or embedding(),
        )

        result = retriever.retrieve(
            "  What does the Assessment Policy say about feedback?  "
        )

        self.assertEqual(result["status"], "supported")
        self.assertTrue(result["evidence_sufficient"])
        self.assertEqual(result["result_count"], 1)
        self.assertTrue(
            {
                "policy_text",
                "policy_title",
                "section",
                "source_url",
                "similarity_score",
                "chunk_id",
                "version",
                "effective_date",
                "rank",
            }.issubset(result["evidence"][0]),
        )
        self.assertEqual(
            embedded_questions,
            ["What does the Assessment Policy say about feedback?"],
        )
        self.assertEqual(client.call["limit"], 5)
        self.assertTrue(client.call["with_payload"])
        self.assertFalse(client.call["with_vectors"])
        current_condition = client.call["query_filter"].must[0]
        self.assertEqual(current_condition.key, "status")
        self.assertEqual(current_condition.match.value, "Current")

    def test_unsupported_question_returns_safe_fallback_below_threshold(self):
        retriever = PolicyRetriever(
            client=FakeClient([current_point(score=0.30)]),
            embedder=lambda _question: embedding(),
        )

        result = retriever.retrieve("What will the weather be tomorrow?")

        self.assertEqual(result["status"], "fallback")
        self.assertFalse(result["evidence_sufficient"])
        self.assertEqual(result["evidence"], [])
        self.assertIn("official La Trobe Policy Library", result["escalation"]["message"])
        self.assertEqual(
            result["escalation"]["url"], "https://policies.latrobe.edu.au/"
        )

    def test_post_query_guardrails_reject_non_current_or_untrusted_evidence(self):
        points = [
            current_point(score=0.99, status="Superseded"),
            current_point(score=0.98, source_url="https://example.com/policy"),
            current_point(score=0.97, section=None),
        ]
        retriever = PolicyRetriever(
            client=FakeClient(points), embedder=lambda _question: embedding()
        )

        result = retriever.retrieve("Can I rely on this policy evidence?")

        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["evidence"], [])

    def test_embedding_dimension_mismatch_is_not_treated_as_evidence(self):
        retriever = PolicyRetriever(
            client=FakeClient([current_point()]), embedder=lambda _question: [0.1]
        )

        with self.assertRaises(RetrievalUnavailableError):
            retriever.retrieve("What is the assessment policy?")

    def test_qdrant_failure_is_hidden_behind_safe_service_error(self):
        retriever = PolicyRetriever(
            client=FakeClient(error=RuntimeError("local storage detail")),
            embedder=lambda _question: embedding(),
        )

        with self.assertRaisesRegex(
            RetrievalUnavailableError, "Current policy evidence could not be retrieved"
        ):
            retriever.retrieve("What is the assessment policy?")

