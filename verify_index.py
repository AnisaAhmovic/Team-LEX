"""
COPL-183 - quick verification that indexing worked.

Run from the repository root, with the venv active:

    python verify_index.py
"""

from ingestion.qdrant_indexer import get_client

client = get_client()

count = client.count("latrobe_policy_chunks", exact=True)
print(count)

points, _ = client.scroll("latrobe_policy_chunks", limit=1, with_payload=True)
print(points[0].payload["policy_title"], "-", points[0].payload["section"])
