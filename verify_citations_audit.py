"""Produce and reconstruct deterministic S4-06/S4-10 sample interactions.

Uses real repository policy metadata and the actual API/retriever/audit code.
Ranked Qdrant results, embeddings and Qwen responses are fixtures. This does not
measure live BGE-M3 relevance or Qwen answer quality. Records remain under var/.
"""

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="var/audit/demo.sqlite3")
    args = parser.parse_args()

    import django
    django.setup()
    from django.test import override_settings
    from rest_framework.test import APIClient
    from api.audit import AuditStore
    from api.citations import MAX_CHUNK_CHARS, SOURCE_FIELDS
    from llm import LLMConnectionError
    from retrieval import PolicyRetriever

    root = Path(__file__).resolve().parent
    # The supporting quotes below are inside the context limit.
    documents = [json.loads((root / f"data/processed/chunks/{doc}_chunks.json").read_text()) for doc in (216, 112)]
    chunks = [next(c for c in document if c["section"] == "Section 2 - Purpose") for document in documents]
    question = "What are the purposes of the assessment and human research ethics documents?"
    claims = [
        {"text": "The assessment document sets principles for assessment quality.",
         "support": [{"evidence_id": "E1", "quote": "This Policy provides the principles for assuring the quality of student assessment at La Trobe."}]},
        {"text": "The human research document addresses ethical conduct in research involving people.",
         "support": [{"evidence_id": "E2", "quote": "Research conducted with or about people or their data or tissue raises ethical considerations"}]},
    ]
    for chunk, claim in zip(chunks, claims):
        assert claim["support"][0]["quote"] in chunk["text"][:MAX_CHUNK_CHARS]

    def point(chunk, score):
        return SimpleNamespace(id=chunk["chunk_id"], payload=chunk, score=score)

    candidates = [point(chunks[0], .91), point(chunks[1], .88),
                  point({**chunks[0], "chunk_id": "fixture-weak"}, .21),
                  point({**chunks[0], "chunk_id": "fixture-missing", "source_url": None}, .18),
                  point({**chunks[0], "chunk_id": "fixture-lowest"}, .10)]
    cases = [
        ("supported_multi_source", candidates, {"claims": claims}, None, 200, "supported"),
        ("fallback", [point(chunks[0], .2)], None, None, 200, "fallback"),
        ("generation_error", candidates, None, LLMConnectionError("fixture failure"), 502, "fallback"),
        ("invalid_citation", candidates, {"claims": [{**claims[0], "support": [{"evidence_id": "E9", "quote": claims[0]["support"][0]["quote"]}]}]}, None, 200, "fallback"),
    ]
    summaries = []
    with override_settings(AUDIT_DB_PATH=Path(args.path), ALLOWED_HOSTS=["testserver"]):
        for name, points, output, error, expected_http, expected_status in cases:
            client = SimpleNamespace(query_points=lambda **_: SimpleNamespace(points=points))
            retriever = PolicyRetriever(client=client, embedder=lambda _: [0.01] * 1024)
            service = SimpleNamespace(model="qwen3:4b")
            with patch("api.views.get_policy_retriever", return_value=retriever), patch("api.views.get_qwen_service", return_value=service), patch.object(service, "generate", create=True) as generate:
                generate.return_value = {"text": json.dumps(output), "model": "qwen3:4b", "done": True, "latency_seconds": 0.0}
                generate.side_effect = error
                response = APIClient().post("/api/answer/", {"question": question}, format="json")
            assert response.status_code == expected_http, response.data
            assert response.data["status"] == expected_status, response.data
            record = AuditStore(args.path).read(response.data["interaction_id"])[0]
            assert record["question"] == question
            assert len(record["retrieval"]["candidates"]) == len(points)
            assert record["response"]["sources"] == response.data["sources"]
            if name == "supported_multi_source":
                assert len(response.data["sources"]) == 2
                assert len(record["selection"]["selected_context"]) == 2
                assert len(record["selection"]["excluded"]) == 3
                for source, chunk in zip(response.data["sources"], chunks):
                    assert all(source[field] == chunk.get(field) for field in SOURCE_FIELDS)
            summaries.append({"scenario": name, "interaction_id": record["interaction_id"],
                              "http_status": response.status_code, "outcome": record["outcome"],
                              "candidate_count": len(points), "source_count": len(response.data["sources"]),
                              "reconstructed": True})
    print(json.dumps({"mode": "deterministic fixtures, not live inference", "records": summaries}, indent=2))


if __name__ == "__main__":
    main()
