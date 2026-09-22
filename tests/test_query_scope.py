"""Metadata scope tests with real Qdrant; no model downloads or inference."""

from unittest import TestCase

from qdrant_client import QdrantClient, models

from retrieval import PolicyRetriever
from retrieval.query_scope import resolve_scope
from tests.test_retrieval_qdrant import vector


class QueryScopeTests(TestCase):
    def setUp(self):
        self.catalogue = [
            {"policy_title": "Assessment Policy", "section": "Section 2 - Purpose"},
            {"policy_title": "Assessment Policy", "section": "Section 7 - Definitions"},
            {"policy_title": "Research Human Ethics Procedure", "subsection": "Part A - Purpose"},
            {"policy_title": "Student Assessment Policy", "section": "Section 2 - Purpose"},
        ]

    def test_explicit_title_and_purpose_resolve_only_to_indexed_metadata(self):
        scope = resolve_scope("What is the purpose of the assessment policy?", self.catalogue)
        self.assertEqual(scope["policy_titles"], ["Assessment Policy"])
        self.assertEqual(scope["heading_filters"], {"section": ["Section 2 - Purpose"]})

    def test_longest_title_match_does_not_include_a_different_shorter_policy(self):
        scope = resolve_scope("What is the purpose of Student Assessment Policy?", self.catalogue)
        self.assertEqual(scope["policy_titles"], ["Student Assessment Policy"])

    def test_multiple_policies_keep_their_actual_heading_levels(self):
        scope = resolve_scope("What are the purposes of Assessment Policy and Research Human Ethics Procedure?", self.catalogue)
        self.assertEqual(scope["policy_titles"], ["Assessment Policy", "Research Human Ethics Procedure"])
        self.assertEqual(scope["heading_filters"], {"section": ["Section 2 - Purpose"], "subsection": ["Part A - Purpose"]})

    def test_no_section_guess_for_general_questions_or_invented_titles(self):
        for question in ("What is the purpose of a degree?", "What does the Imaginary Policy say?"):
            scope = resolve_scope(question, self.catalogue)
            self.assertEqual(scope["policy_titles"], [])
            self.assertEqual(scope["heading_filters"], {})
        scope = resolve_scope("Assessment Policy feedback requirements", self.catalogue)
        self.assertEqual(scope["policy_titles"], ["Assessment Policy"])
        self.assertEqual(scope["heading_filters"], {})

    def test_missing_or_ambiguous_section_does_not_drop_a_requested_policy(self):
        catalogue = self.catalogue + [{"policy_title": "Other Policy", "section": "Introduction"}]
        for question in ("Purpose of Assessment Policy and Other Policy?",
                         "What are the purpose of and scope of Assessment Policy?"):
            self.assertEqual(resolve_scope(question, catalogue)["heading_filters"], {})

    def test_real_index_scope_reaches_purpose_and_preserves_threshold_and_scores(self):
        client = QdrantClient(":memory:")
        self.addCleanup(client.close)
        name = "scope_test"
        client.create_collection(name, vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE))

        def payload(chunk_id, title, section, status="Current"):
            return {"chunk_id": chunk_id, "policy_title": title, "section": section,
                    "status": status, "text": "This policy assures assessment quality.",
                    "source_url": "https://policies.latrobe.edu.au/document/view.php?id=216"}

        rows = [
            (1, vector(), payload("216-7", "Assessment Policy", "Section 7 - Definitions")),
            (2, vector(.1), payload("other-1", "Other Policy", "Section 2 - Purpose")),
            (3, vector(.2), payload("216-2", "Assessment Policy", "Section 2 - Purpose")),
            (4, vector(), payload("old", "Assessment Policy", "Section 2 - Purpose", "Superseded")),
            (5, vector(3), payload("weak", "Assessment Policy", "Section 2 - Purpose")),
            (6, vector(.3), payload("112-2", "Research Human Ethics Procedure", "Section 2 - Purpose")),
        ]
        client.upsert(name, points=[models.PointStruct(id=i, vector=v, payload=p) for i, v, p in rows])
        retriever = PolicyRetriever(client=client, collection_name=name, embedder=lambda _: vector())
        result = retriever.retrieve("What is the purpose of the Assessment Policy?")
        self.assertEqual([c["chunk_id"] for c in result["evidence"]], ["216-2"])
        self.assertEqual([c["chunk_id"] for c in result["_trace"]["candidates"]], ["216-2", "weak"])
        self.assertEqual(result["_trace"]["candidates"][1]["exclusion_reason"], "below_threshold")
        self.assertEqual(result["minimum_similarity_score"], .55)
        self.assertGreater(result["evidence"][0]["similarity_score"], .55)
        result = retriever.retrieve("What are the purposes of Assessment Policy and Research Human Ethics Procedure?")
        self.assertEqual([c["chunk_id"] for c in result["evidence"]], ["216-2", "112-2"])

    def test_catalogue_is_paginated_and_only_reads_current_title_and_heading_metadata(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        client = Mock()
        client.scroll.side_effect = [
            ([SimpleNamespace(payload=self.catalogue[0])], "next-page"),
            ([SimpleNamespace(payload=self.catalogue[2])], None),
        ]
        client.query_points.return_value = SimpleNamespace(points=[])
        retriever = PolicyRetriever(client=client, embedder=lambda _: vector())
        retriever.retrieve("What is the purpose of Assessment Policy?")
        retriever.retrieve("What is the purpose of Research Human Ethics Procedure?")
        self.assertEqual(client.scroll.call_count, 2)
        first, second = client.scroll.call_args_list
        self.assertIsNone(first.kwargs["offset"])
        self.assertEqual(second.kwargs["offset"], "next-page")
        self.assertFalse(first.kwargs["with_vectors"])
        self.assertNotIn("text", first.kwargs["with_payload"])
        self.assertEqual(first.kwargs["scroll_filter"].must[0].match.value, "Current")
