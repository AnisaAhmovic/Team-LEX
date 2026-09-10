import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from ingestion.policy_chunker import (
    chunk_policy,
    clear_chunk_outputs,
    discover_corpus_files,
)


CORPUS_DIRECTORY = Path("data/processed/corpus")


def load_corpus_document(document_id):
    document_path = CORPUS_DIRECTORY / f"{document_id}.json"

    with open(document_path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


class CorpusDiscoveryTests(TestCase):

    def test_discovers_complete_processed_corpus(self):
        corpus_files = discover_corpus_files()

        self.assertEqual(len(corpus_files), 214)

    def test_corpus_files_are_sorted_by_numeric_document_id(self):
        corpus_files = discover_corpus_files()

        document_ids = [
            int(corpus_file.stem)
            for corpus_file in corpus_files
        ]

        self.assertEqual(
            document_ids,
            sorted(document_ids),
        )

    def test_missing_corpus_raises_clear_error(self):
        with TemporaryDirectory() as temporary_directory:
            empty_directory = Path(temporary_directory)

            with patch(
                "ingestion.policy_chunker.CORPUS_DIRECTORY",
                empty_directory,
            ):
                with self.assertRaises(FileNotFoundError):
                    discover_corpus_files()


class ChunkOutputTests(TestCase):

    def test_clear_chunk_outputs_removes_only_json_files(self):
        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)

            stale_chunk = output_directory / "old_chunks.json"
            unrelated_file = output_directory / "keep_me.txt"

            stale_chunk.write_text("[]", encoding="utf-8")
            unrelated_file.write_text("keep", encoding="utf-8")

            with patch(
                "ingestion.policy_chunker.OUTPUT_DIRECTORY",
                output_directory,
            ):
                clear_chunk_outputs()

            self.assertFalse(stale_chunk.exists())
            self.assertTrue(unrelated_file.exists())


class PolicyChunkingTests(TestCase):

    def test_chunk_policy_preserves_document_identity(self):
        policy_data = load_corpus_document("216")

        chunks = chunk_policy(policy_data)

        self.assertTrue(chunks)

        for chunk in chunks:
            self.assertEqual(
                chunk["document_id"],
                policy_data["document_id"],
            )
            self.assertEqual(
                chunk["policy_title"],
                policy_data["policy_title"],
            )

    def test_chunk_ids_are_unique_and_deterministic(self):
        policy_data = load_corpus_document("216")

        first_run = chunk_policy(policy_data)
        second_run = chunk_policy(policy_data)

        first_ids = [
            chunk["chunk_id"]
            for chunk in first_run
        ]
        second_ids = [
            chunk["chunk_id"]
            for chunk in second_run
        ]

        self.assertEqual(first_ids, second_ids)
        self.assertEqual(len(first_ids), len(set(first_ids)))

    def test_chunks_preserve_required_retrieval_metadata(self):
        policy_data = load_corpus_document("216")

        chunks = chunk_policy(policy_data)

        required_fields = {
            "chunk_id",
            "document_id",
            "policy_title",
            "heading_level",
            "section",
            "subsection",
            "topic",
            "subtopic",
            "paragraph_start",
            "paragraph_end",
            "source_url",
            "status_details_url",
            "status",
            "effective_date",
            "review_date",
            "approval_authority",
            "approval_date",
            "version",
            "text",
        }

        for chunk in chunks:
            with self.subTest(chunk_id=chunk["chunk_id"]):
                self.assertTrue(
                    required_fields.issubset(chunk.keys())
                )
                self.assertTrue(chunk["text"].strip())
                self.assertEqual(chunk["status"], "Current")