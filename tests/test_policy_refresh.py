from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch

from ingestion.policy_refresh import refresh_document


class PolicyRefreshTests(TestCase):

    @patch("ingestion.policy_refresh.index_chunks")
    @patch("ingestion.policy_refresh.delete_document")
    @patch("ingestion.policy_refresh.get_client")
    @patch("ingestion.policy_refresh.chunk_policy")
    @patch("ingestion.policy_refresh.process_corpus_document")
    @patch("ingestion.policy_refresh.build_processing_input")
    @patch("ingestion.policy_refresh.load_corpus_manifest")
    def test_refresh_document_replaces_one_document_after_successful_processing(
        self,
        mock_load_manifest,
        mock_build_input,
        mock_process,
        mock_chunk,
        mock_get_client,
        mock_delete,
        mock_index,
    ):
        document = {
            "document_id": "216",
            "policy_title": "Assessment Policy",
            "document_type": "Policy",
            "source_url": "https://policies.latrobe.edu.au/document/view.php?id=216",
            "discovery_source_url": "https://policies.latrobe.edu.au/browse",
        }
        processing_input = {
            "document_id": "216",
            "output_file": "data/processed/corpus/216.json",
        }
        policy_data = {
            "document_id": "216",
            "policy_title": "Assessment Policy",
        }
        chunks = [
            {
                "chunk_id": "216-1",
                "document_id": "216",
                "text": "Updated policy evidence",
            }
        ]
        client = MagicMock()

        mock_load_manifest.return_value = [document]
        mock_build_input.return_value = processing_input
        mock_process.return_value = policy_data
        mock_chunk.return_value = chunks
        mock_get_client.return_value = client

        with TemporaryDirectory() as temporary_directory:
            with patch("ingestion.policy_refresh.CHUNKS_DIRECTORY", Path(temporary_directory)):
                result = refresh_document("216")

        mock_build_input.assert_called_once_with(document)
        mock_process.assert_called_once_with(processing_input)
        mock_chunk.assert_called_once_with(policy_data)
        mock_delete.assert_called_once_with(client, "216")
        mock_index.assert_called_once_with(client, chunks)

        self.assertEqual(result["document_id"], "216")
        self.assertEqual(result["chunks_indexed"], 1)

    @patch("ingestion.policy_refresh.delete_document")
    @patch("ingestion.policy_refresh.chunk_policy")
    @patch("ingestion.policy_refresh.process_corpus_document")
    @patch("ingestion.policy_refresh.build_processing_input")
    @patch("ingestion.policy_refresh.load_corpus_manifest")
    def test_refresh_document_does_not_delete_index_when_processing_fails(
        self,
        mock_load_manifest,
        mock_build_input,
        mock_process,
        mock_chunk,
        mock_delete,
    ):
        document = {
            "document_id": "216",
            "policy_title": "Assessment Policy",
        }
        processing_input = {
            "document_id": "216",
            "output_file": "data/processed/corpus/216.json",
        }

        mock_load_manifest.return_value = [document]
        mock_build_input.return_value = processing_input
        mock_process.side_effect = RuntimeError("authoritative processing failed")

        with self.assertRaises(RuntimeError):
            refresh_document("216")

        mock_chunk.assert_not_called()
        mock_delete.assert_not_called()

    @patch("ingestion.policy_refresh.process_corpus_document")
    @patch("ingestion.policy_refresh.load_corpus_manifest")
    def test_refresh_document_rejects_unknown_document(
        self,
        mock_load_manifest,
        mock_process,
    ):
        mock_load_manifest.return_value = [
            {"document_id": "216", "policy_title": "Assessment Policy"}
        ]

        with self.assertRaisesRegex(
            ValueError,
            "Document ID 999 was not found",
        ):
            refresh_document("999")

        mock_process.assert_not_called()

    @patch("ingestion.policy_refresh.delete_document")
    @patch("ingestion.policy_refresh.chunk_policy")
    @patch("ingestion.policy_refresh.process_corpus_document")
    @patch("ingestion.policy_refresh.build_processing_input")
    @patch("ingestion.policy_refresh.load_corpus_manifest")
    def test_refresh_document_does_not_delete_index_when_no_chunks_produced(
        self,
        mock_load_manifest,
        mock_build_input,
        mock_process,
        mock_chunk,
        mock_delete,
    ):
        document = {
            "document_id": "216",
            "policy_title": "Assessment Policy",
        }
        processing_input = {
            "document_id": "216",
            "output_file": "data/processed/corpus/216.json",
        }

        mock_load_manifest.return_value = [document]
        mock_build_input.return_value = processing_input
        mock_process.return_value = {
            "document_id": "216",
            "policy_title": "Assessment Policy",
        }
        mock_chunk.return_value = []

        with self.assertRaisesRegex(ValueError, "produced no chunks"):
            refresh_document("216")

        mock_delete.assert_not_called()

    @patch("ingestion.policy_refresh.delete_document")
    @patch("ingestion.policy_refresh.write_chunks")
    @patch("ingestion.policy_refresh.chunk_policy")
    @patch("ingestion.policy_refresh.process_corpus_document")
    @patch("ingestion.policy_refresh.build_processing_input")
    @patch("ingestion.policy_refresh.load_corpus_manifest")
    def test_refresh_document_does_not_delete_index_when_chunk_write_fails(
        self,
        mock_load_manifest,
        mock_build_input,
        mock_process,
        mock_chunk,
        mock_write,
        mock_delete,
    ):
        document = {
            "document_id": "216",
            "policy_title": "Assessment Policy",
        }
        processing_input = {
            "document_id": "216",
            "output_file": "data/processed/corpus/216.json",
        }
        policy_data = {
            "document_id": "216",
            "policy_title": "Assessment Policy",
        }
        chunks = [
            {
                "chunk_id": "216-1",
                "document_id": "216",
                "text": "Updated policy evidence",
            }
        ]

        mock_load_manifest.return_value = [document]
        mock_build_input.return_value = processing_input
        mock_process.return_value = policy_data
        mock_chunk.return_value = chunks
        mock_write.side_effect = OSError("chunk persistence failed")

        with self.assertRaises(OSError):
            refresh_document("216")

        mock_delete.assert_not_called()

    @patch("ingestion.qdrant_indexer.embed_texts")
    def test_document_replacement_removes_stale_chunks_and_preserves_other_documents(
        self,
        mock_embed_texts,
    ):
        from qdrant_client import QdrantClient

        from ingestion.embedding_config import QDRANT_COLLECTION_NAME
        from ingestion.qdrant_indexer import (
            delete_document,
            ensure_collection,
            index_chunks,
        )

        def vector(value):
            from ingestion.embedding_config import EMBEDDING_DIMENSION

            result = [0.0] * EMBEDDING_DIMENSION
            result[0] = value
            return result

        def make_chunk(chunk_id, document_id, text):
            return {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "policy_title": f"Policy {document_id}",
                "heading_level": "h1",
                "section": "Section 1",
                "subsection": None,
                "topic": None,
                "subtopic": None,
                "paragraph_start": 1,
                "paragraph_end": 1,
                "source_url": (
                    "https://policies.latrobe.edu.au/document/view.php"
                    f"?id={document_id}"
                ),
                "status_details_url": None,
                "status": "Current",
                "effective_date": None,
                "review_date": None,
                "approval_authority": None,
                "approval_date": None,
                "version": None,
                "text": text,
            }

        client = QdrantClient(":memory:")
        ensure_collection(client, recreate=False)

        old_chunks = [
            make_chunk("216-1", "216", "Old evidence one"),
            make_chunk("216-2", "216", "Old evidence two"),
            make_chunk("216-3", "216", "Stale orphan evidence"),
            make_chunk("321-1", "321", "Unrelated policy evidence"),
        ]
        mock_embed_texts.return_value = [
            vector(1.0),
            vector(0.9),
            vector(0.8),
            vector(0.7),
        ]
        index_chunks(client, old_chunks)

        new_chunks = [
            make_chunk("216-1", "216", "Replacement evidence one"),
            make_chunk("216-2", "216", "Replacement evidence two"),
        ]
        mock_embed_texts.return_value = [
            vector(1.0),
            vector(0.9),
        ]

        delete_document(client, "216")
        index_chunks(client, new_chunks)

        points, _ = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=10,
            with_payload=True,
            with_vectors=False,
        )

        payloads = {
            point.payload["chunk_id"]: point.payload
            for point in points
        }

        self.assertEqual(
            set(payloads),
            {"216-1", "216-2", "321-1"},
        )
        self.assertNotIn("216-3", payloads)
        self.assertEqual(
            payloads["216-1"]["text"],
            "Replacement evidence one",
        )
        self.assertEqual(
            payloads["216-2"]["text"],
            "Replacement evidence two",
        )
        self.assertEqual(
            payloads["321-1"]["text"],
            "Unrelated policy evidence",
        )
