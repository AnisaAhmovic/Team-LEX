from unittest import TestCase
from unittest.mock import patch

from qdrant_client import QdrantClient

from ingestion.embedding_config import (
    EMBEDDING_DIMENSION,
    QDRANT_COLLECTION_NAME,
)
from ingestion.qdrant_indexer import (
    delete_document,
    ensure_collection,
    index_chunks,
)


def vector(value=1.0):
    result = [0.0] * EMBEDDING_DIMENSION
    result[0] = value
    return result


def chunk(chunk_id, document_id, title):
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "policy_title": title,
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
        "text": f"Evidence for {title}",
    }


class QdrantIndexerTests(TestCase):

    def setUp(self):
        self.client = QdrantClient(":memory:")
        ensure_collection(self.client, recreate=False)

    @patch("ingestion.qdrant_indexer.embed_texts")
    def test_index_chunks_writes_expected_payload(self, mock_embed_texts):
        test_chunk = chunk("216-1", "216", "Assessment Policy")
        mock_embed_texts.return_value = [vector()]

        index_chunks(self.client, [test_chunk])

        points, _ = self.client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=10,
            with_payload=True,
            with_vectors=False,
        )

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].payload["chunk_id"], "216-1")
        self.assertEqual(points[0].payload["document_id"], "216")
        self.assertEqual(
            points[0].payload["policy_title"],
            "Assessment Policy",
        )
        self.assertEqual(points[0].payload["status"], "Current")
        self.assertEqual(
            points[0].payload["source_url"],
            "https://policies.latrobe.edu.au/document/view.php?id=216",
        )

    @patch("ingestion.qdrant_indexer.embed_texts")
    def test_reindexing_same_chunk_does_not_create_duplicate(
        self,
        mock_embed_texts,
    ):
        test_chunk = chunk("216-1", "216", "Assessment Policy")
        mock_embed_texts.return_value = [vector()]

        index_chunks(self.client, [test_chunk])
        index_chunks(self.client, [test_chunk])

        count = self.client.count(
            QDRANT_COLLECTION_NAME,
            exact=True,
        ).count

        self.assertEqual(count, 1)

    @patch("ingestion.qdrant_indexer.embed_texts")
    def test_delete_document_removes_only_target_document(
        self,
        mock_embed_texts,
    ):
        chunks = [
            chunk("216-1", "216", "Assessment Policy"),
            chunk("216-2", "216", "Assessment Policy"),
            chunk("321-1", "321", "Health and Safety Procedure - Safe Driving"),
        ]
        mock_embed_texts.return_value = [
            vector(1.0),
            vector(0.9),
            vector(0.8),
        ]

        index_chunks(self.client, chunks)
        delete_document(self.client, "216")

        points, _ = self.client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=10,
            with_payload=True,
            with_vectors=False,
        )

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].payload["document_id"], "321")
        self.assertEqual(points[0].payload["chunk_id"], "321-1")