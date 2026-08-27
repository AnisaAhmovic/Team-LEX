from unittest import TestCase

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from retrieval import PolicyRetriever


def vector(second_value=0.0):
    result = [0.0] * 1024
    result[0] = 1.0
    result[1] = second_value
    return result


def payload(index, status="Current"):
    return {
        "text": f"Policy evidence {index}",
        "policy_title": f"Policy {index}",
        "section": f"Section {index}",
        "source_url": f"https://policies.latrobe.edu.au/document/view.php?id={index}",
        "status": status,
    }


class RealQdrantRetrievalTests(TestCase):
    def test_real_qdrant_query_filters_current_content_and_limits_results_to_five(self):
        client = QdrantClient(":memory:")
        collection = "test_policy_chunks"
        client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(
                size=1024, distance=qmodels.Distance.COSINE
            ),
        )

        points = [
            qmodels.PointStruct(
                id=index,
                vector=vector(index * 0.03),
                payload=payload(index),
            )
            for index in range(1, 7)
        ]
        points.append(
            qmodels.PointStruct(
                id=99,
                vector=vector(),
                payload=payload(99, status="Superseded"),
            )
        )
        client.upsert(collection_name=collection, points=points)

        retriever = PolicyRetriever(
            client=client,
            collection_name=collection,
            embedder=lambda _question: vector(),
            min_similarity_score=0.55,
        )
        result = retriever.retrieve("What current policy evidence is available?")

        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["result_count"], 5)
        self.assertNotIn(
            "Policy 99", [item["policy_title"] for item in result["evidence"]]
        )
