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
    def __init__(self, points=None, error=None, responses=None):
        self.points = points or []
        self.error = error
        self.responses = list(responses) if responses is not None else None
        self.call = None
        self.calls = []

    def query_points(self, **kwargs):
        self.call = kwargs
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if self.responses is not None:
            index = min(len(self.calls) - 1, len(self.responses) - 1)
            return SimpleNamespace(points=self.responses[index])
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
            [
                "What does the Assessment Policy say about feedback?",
                "about assessment does feedback policy say",
            ],
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

    def test_secondary_query_can_add_eligible_evidence_missed_by_original_top_five(self):
        original_points = [
            current_point(
                score=0.70 - (index * 0.01),
                chunk_id=f"original-{index}",
                text=f"Original evidence {index}",
            )
            for index in range(5)
        ]
        recovered = current_point(
            score=0.61,
            chunk_id="363-9",
            text=(
                "Feedback should normally be provided within 15 business days "
                "of the assessment due date."
            ),
        )
        secondary_points = [
            recovered,
            *[
                current_point(
                    score=0.60 - (index * 0.01),
                    chunk_id=f"secondary-{index}",
                    text=f"Secondary evidence {index}",
                )
                for index in range(4)
            ],
        ]

        client = FakeClient(responses=[original_points, secondary_points])
        embedded_questions = []
        retriever = PolicyRetriever(
            client=client,
            embedder=lambda question: embedded_questions.append(question) or embedding(),
        )

        result = retriever.retrieve(
            "When am I supposed to get feedback on my assessment?"
        )

        self.assertEqual(result["status"], "supported")
        self.assertIn("363-9", [item["chunk_id"] for item in result["evidence"]])
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[0]["limit"], 5)
        self.assertEqual(client.calls[1]["limit"], 5)
        self.assertEqual(
            embedded_questions[0],
            "When am I supposed to get feedback on my assessment?",
        )
        self.assertNotEqual(embedded_questions[1], embedded_questions[0])

    def test_secondary_query_deduplicates_evidence_already_found_by_original_query(self):
        shared = current_point(
            score=0.82,
            chunk_id="363-9",
            text="Feedback should normally be provided within 15 business days.",
        )
        client = FakeClient(responses=[[shared], [shared]])
        retriever = PolicyRetriever(
            client=client,
            embedder=lambda _question: embedding(),
        )

        result = retriever.retrieve(
            "When should I normally get feedback on my assessment?"
        )

        self.assertEqual(result["status"], "supported")
        self.assertEqual(
            [item["chunk_id"] for item in result["evidence"]],
            ["363-9"],
        )

        candidates = result["_trace"]["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["chunk_id"], "363-9")
        self.assertEqual(
            candidates[0]["discoveries"],
            [
                {
                    "source": "original",
                    "rank": 1,
                    "similarity_score": 0.82,
                },
                {
                    "source": "secondary",
                    "rank": 1,
                    "similarity_score": 0.82,
                },
            ],
        )

    def test_same_rank_from_different_representations_keeps_distinct_evidence(self):
        original = current_point(
            score=0.81,
            chunk_id="original-rank-one",
            text="Original rank-one evidence.",
        )
        secondary = current_point(
            score=0.79,
            chunk_id="secondary-rank-one",
            text="Secondary rank-one evidence.",
        )
        client = FakeClient(responses=[[original], [secondary]])
        retriever = PolicyRetriever(
            client=client,
            embedder=lambda _question: embedding(),
        )

        result = retriever.retrieve(
            "When am I supposed to get feedback on my assessment?"
        )

        self.assertEqual(result["status"], "supported")
        self.assertEqual(
            [item["chunk_id"] for item in result["evidence"]],
            ["original-rank-one", "secondary-rank-one"],
        )

        candidates = result["_trace"]["candidates"]
        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            [candidate["chunk_id"] for candidate in candidates],
            ["original-rank-one", "secondary-rank-one"],
        )
        self.assertEqual(
            [candidate["discoveries"][0]["rank"] for candidate in candidates],
            [1, 1],
        )
        self.assertEqual(
            [candidate["discoveries"][0]["source"] for candidate in candidates],
            ["original", "secondary"],
        )

    def test_same_evidence_becomes_eligible_when_any_discovery_is_eligible(self):
        original = current_point(
            score=0.54,
            chunk_id="363-9",
            text="Feedback should normally be provided within 15 business days.",
        )
        secondary = current_point(
            score=0.65,
            chunk_id="363-9",
            text="Feedback should normally be provided within 15 business days.",
        )
        client = FakeClient(responses=[[original], [secondary]])
        retriever = PolicyRetriever(
            client=client,
            embedder=lambda _question: embedding(),
        )

        result = retriever.retrieve(
            "When am I supposed to get feedback on my assessment?"
        )

        self.assertEqual(result["status"], "supported")
        self.assertEqual(
            [item["chunk_id"] for item in result["evidence"]],
            ["363-9"],
        )

        candidates = result["_trace"]["candidates"]
        self.assertEqual(len(candidates), 1)

        candidate = candidates[0]
        self.assertTrue(candidate["eligible"])
        self.assertIsNone(candidate["exclusion_reason"])
        self.assertEqual(candidate["similarity_score"], 0.65)
        self.assertEqual(candidate["discovery_source"], "secondary")
        self.assertEqual(
            candidate["discoveries"],
            [
                {
                    "source": "original",
                    "rank": 1,
                    "similarity_score": 0.54,
                },
                {
                    "source": "secondary",
                    "rank": 1,
                    "similarity_score": 0.65,
                },
            ],
        )

    def test_secondary_query_cannot_bypass_existing_evidence_guardrails(self):
        secondary_points = [
            current_point(
                score=0.54,
                chunk_id="below-threshold",
            ),
            current_point(
                score=0.90,
                chunk_id="superseded",
                status="Superseded",
            ),
            current_point(
                score=0.89,
                chunk_id="untrusted",
                source_url="https://example.com/policy",
            ),
            current_point(
                score=0.88,
                chunk_id="missing-provenance",
                section=None,
            ),
        ]
        client = FakeClient(responses=[[], secondary_points])
        retriever = PolicyRetriever(
            client=client,
            embedder=lambda _question: embedding(),
        )

        result = retriever.retrieve(
            "When am I supposed to get feedback on my assessment?"
        )

        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["evidence"], [])

    def test_secondary_query_uses_same_original_query_scope_filter(self):
        client = FakeClient(responses=[[current_point()], [current_point()]])
        retriever = PolicyRetriever(
            client=client,
            embedder=lambda _question: embedding(),
        )

        retriever.retrieve("What is the purpose of the Assessment Policy?")

        self.assertEqual(len(client.calls), 2)
        self.assertEqual(
            client.calls[0]["query_filter"],
            client.calls[1]["query_filter"],
        )

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

