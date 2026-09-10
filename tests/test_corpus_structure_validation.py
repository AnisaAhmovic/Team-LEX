import json
from pathlib import Path
from unittest import TestCase


CORPUS_DIRECTORY = Path("data/processed/corpus")
CORPUS_PROCESSING_REPORT_PATH = Path(
    "data/corpus/corpus_processing_report.json"
)

REPRESENTATIVE_DOCUMENTS = {
    "278": "Guideline",
    "389": "Schedule",
    "71": "Code",
    "225": "Charter",
    "390": "Standard",
    "374": "Policy",
    "331": "Procedure",
    "338": "Procedure",
    "69": "Policy",
    "305": "Policy",
}


def load_processed_document(document_id):
    document_path = CORPUS_DIRECTORY / f"{document_id}.json"

    with open(document_path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


class CorpusStructureValidationTests(TestCase):
    def test_processed_corpus_matches_processing_report(self):
        corpus_files = list(CORPUS_DIRECTORY.glob("*.json"))

        with open(
            CORPUS_PROCESSING_REPORT_PATH,
            "r",
            encoding="utf-8",
        ) as input_file:
            processing_report = json.load(input_file)

        self.assertEqual(
            len(corpus_files),
            processing_report["documents_processed"],
        )

    def test_all_processed_documents_have_required_structure(self):
        corpus_files = list(CORPUS_DIRECTORY.glob("*.json"))

        for corpus_file in corpus_files:
            with self.subTest(document=corpus_file.name):
                with open(corpus_file, "r", encoding="utf-8") as input_file:
                    document = json.load(input_file)

                self.assertTrue(document.get("document_id"))
                self.assertTrue(document.get("policy_title"))
                self.assertTrue(document.get("document_type"))
                self.assertTrue(document.get("status"))
                self.assertTrue(document.get("headings"))
                self.assertTrue(
                    str(document.get("content", "")).strip()
                )

    def test_representative_document_types_are_preserved(self):
        for document_id, expected_type in REPRESENTATIVE_DOCUMENTS.items():
            with self.subTest(document_id=document_id):
                document = load_processed_document(document_id)

                self.assertEqual(
                    document["document_type"],
                    expected_type,
                )

    def test_representative_documents_preserve_heading_variation(self):
        expected_heading_levels = {
            "278": {"h1"},
            "389": {"h2"},
            "71": {"h1"},
            "225": {"h1", "h2"},
            "390": {"h1", "h2", "h3", "h4"},
            "331": {"h1", "h2"},
            "338": {"h1", "h2", "h3", "h4"},
            "69": {"h1", "h3", "h4"},
            "305": {"h1", "h2", "h3", "h4"},
        }

        for document_id, expected_levels in expected_heading_levels.items():
            with self.subTest(document_id=document_id):
                document = load_processed_document(document_id)

                actual_levels = {
                    heading["level"]
                    for heading in document["headings"]
                }

                self.assertEqual(actual_levels, expected_levels)

    def test_representative_documents_have_usable_content(self):
        for document_id in REPRESENTATIVE_DOCUMENTS:
            with self.subTest(document_id=document_id):
                document = load_processed_document(document_id)

                self.assertTrue(document["policy_title"].strip())
                self.assertTrue(document["headings"])
                self.assertTrue(document["content"].strip())
                self.assertEqual(document["status"], "Current")