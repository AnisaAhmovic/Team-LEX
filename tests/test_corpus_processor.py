from unittest import TestCase
from unittest.mock import patch

from ingestion.corpus_processor import (
    build_processing_input,
    process_corpus,
)


def corpus_document(document_id="216", policy_title="Assessment Policy"):
    return {
        "document_id": document_id,
        "policy_title": policy_title,
        "document_type": "Policy",
        "source_url": (
            "https://policies.latrobe.edu.au/document/view.php"
            f"?id={document_id}"
        ),
        "discovery_source_url": "https://policies.latrobe.edu.au/browse",
    }


class BuildProcessingInputTests(TestCase):
    def test_preserves_discovered_identity_and_provenance(self):
        processing_input = build_processing_input(corpus_document())

        self.assertEqual(processing_input["document_id"], "216")
        self.assertEqual(
            processing_input["policy_title"],
            "Assessment Policy",
        )
        self.assertEqual(processing_input["document_type"], "Policy")
        self.assertEqual(
            processing_input["policy_url"],
            "https://policies.latrobe.edu.au/document/view.php?id=216",
        )
        self.assertEqual(
            processing_input["discovery_source_url"],
            "https://policies.latrobe.edu.au/browse",
        )
        self.assertTrue(
            processing_input["output_file"].endswith("216.json")
        )


class CorpusProcessingOutcomeTests(TestCase):
    @patch("ingestion.corpus_processor.process_corpus_document")
    def test_records_successful_processing_outcome(self, mock_process):
        mock_process.return_value = {
            "document_id": "216",
            "policy_title": "Assessment Policy",
        }

        processing_input = build_processing_input(corpus_document())
        report = process_corpus([processing_input])
        result = report["results"][0]

        self.assertEqual(result["document_id"], "216")
        self.assertEqual(result["policy_title"], "Assessment Policy")
        self.assertEqual(result["document_type"], "Policy")
        self.assertEqual(
            result["source_url"],
            "https://policies.latrobe.edu.au/document/view.php?id=216",
        )
        self.assertEqual(
            result["discovery_source_url"],
            "https://policies.latrobe.edu.au/browse",
        )
        self.assertEqual(result["status"], "Processed")
        self.assertIsNone(result["error"])

        self.assertEqual(report["documents_attempted"], 1)
        self.assertEqual(report["documents_processed"], 1)
        self.assertEqual(report["documents_failed"], 0)
        self.assertEqual(
            report["outcome_summary"],
            {"Processed": 1, "Failed": 0},
        )

    @patch("ingestion.corpus_processor.process_corpus_document")
    def test_records_failed_outcome_without_losing_manifest_title(
        self,
        mock_process,
    ):
        mock_process.side_effect = ValueError(
            "Authoritative source access restricted or redirected."
        )

        processing_input = build_processing_input(
            corpus_document("268", "Investment Policy")
        )
        report = process_corpus([processing_input])
        result = report["results"][0]

        self.assertEqual(result["document_id"], "268")
        self.assertEqual(result["policy_title"], "Investment Policy")
        self.assertEqual(result["document_type"], "Policy")
        self.assertEqual(
            result["source_url"],
            "https://policies.latrobe.edu.au/document/view.php?id=268",
        )
        self.assertEqual(
            result["discovery_source_url"],
            "https://policies.latrobe.edu.au/browse",
        )
        self.assertEqual(result["status"], "Failed")
        self.assertEqual(
            result["error"],
            (
                "ValueError: Authoritative source access restricted "
                "or redirected."
            ),
        )

        self.assertEqual(report["documents_attempted"], 1)
        self.assertEqual(report["documents_processed"], 0)
        self.assertEqual(report["documents_failed"], 1)
        self.assertEqual(
            report["outcome_summary"],
            {"Processed": 0, "Failed": 1},
        )

    @patch("ingestion.corpus_processor.process_corpus_document")
    def test_processing_continues_after_individual_document_failure(
        self,
        mock_process,
    ):
        mock_process.side_effect = [
            ValueError("Test processing failure."),
            {
                "document_id": "216",
                "policy_title": "Assessment Policy",
            },
        ]

        processing_inputs = [
            build_processing_input(
                corpus_document("268", "Investment Policy")
            ),
            build_processing_input(
                corpus_document("216", "Assessment Policy")
            ),
        ]

        report = process_corpus(processing_inputs)

        self.assertEqual(len(report["results"]), 2)
        self.assertEqual(report["results"][0]["status"], "Failed")
        self.assertEqual(report["results"][1]["status"], "Processed")
        self.assertEqual(report["documents_attempted"], 2)
        self.assertEqual(report["documents_processed"], 1)
        self.assertEqual(report["documents_failed"], 1)
        self.assertEqual(
            report["outcome_summary"],
            {"Processed": 1, "Failed": 1},
        )

    def test_empty_corpus_returns_zero_outcome_summary(self):
        report = process_corpus([])

        self.assertEqual(report["documents_attempted"], 0)
        self.assertEqual(report["documents_processed"], 0)
        self.assertEqual(report["documents_failed"], 0)
        self.assertEqual(
            report["outcome_summary"],
            {"Processed": 0, "Failed": 0},
        )
        self.assertEqual(report["results"], [])