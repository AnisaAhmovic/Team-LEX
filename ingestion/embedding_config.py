"""
Embedding configuration for Project Lex (COPL-183).

This module is the single source of truth for the embedding model and
Qdrant collection settings, so the chunker/embedder/indexer/retriever all
agree on the same values. It also writes the resolved configuration to
data/processed/embedding_config.json as a timestamped record, which can be
linked as setup evidence on the Jira ticket.

Model choice: BAAI/bge-m3
- Multilingual, supports long inputs (up to 8192 tokens), which suits
  section-aware policy chunks that can be a few paragraphs long.
- Dense embedding dimension: 1024.
- Recommended distance metric for BGE dense embeddings: cosine similarity.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
EMBEDDING_MODEL_PROVIDER = "sentence-transformers"
EMBEDDING_DIMENSION = 1024
DISTANCE_METRIC = "Cosine"
MAX_SEQUENCE_LENGTH = 8192
NORMALIZE_EMBEDDINGS = True


# QDRANT_MODE controls how the indexer connects to Qdrant:
#   "local"  - embedded mode. No server, no Docker. Qdrant runs inside the
#              Python process and persists to QDRANT_LOCAL_PATH on disk.
#              This is the default so nobody on the team needs Docker
#              installed just to run/test the indexing pipeline.
#   "server" - connects to a Qdrant server (e.g. started via
#              docker-compose.qdrant.yml) at QDRANT_HOST:QDRANT_PORT.
#              Only needed if you specifically want the web dashboard at
#              http://localhost:6333/dashboard, or multiple processes
#              need to query the same running instance at once.
QDRANT_MODE = "local"
QDRANT_LOCAL_PATH = "qdrant_storage"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_COLLECTION_NAME = "latrobe_policy_chunks"

CHUNKS_DIRECTORY = Path("data/processed/chunks")
CONFIG_RECORD_PATH = Path("data/processed/embedding_config.json")

# Fields carried over from each chunk record into the Qdrant payload.
# "text" is embedded (not just stored) so it is included here too, since
# it is required to show the cited passage back to the user at query time.
PAYLOAD_FIELDS = [
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
]


def get_config():
    """Return the embedding/indexing configuration as a plain dict."""
    return {
        "embedding_model_name": EMBEDDING_MODEL_NAME,
        "embedding_model_provider": EMBEDDING_MODEL_PROVIDER,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "distance_metric": DISTANCE_METRIC,
        "max_sequence_length": MAX_SEQUENCE_LENGTH,
        "normalize_embeddings": NORMALIZE_EMBEDDINGS,
        "qdrant_mode": QDRANT_MODE,
        "qdrant_local_path": QDRANT_LOCAL_PATH,
        "qdrant_host": QDRANT_HOST,
        "qdrant_port": QDRANT_PORT,
        "qdrant_collection_name": QDRANT_COLLECTION_NAME,
        "payload_fields": PAYLOAD_FIELDS,
    }


def record_config(path=CONFIG_RECORD_PATH):
    """
    Write the current embedding configuration to disk with a timestamp.

    This gives COPL-183 a concrete, reviewable artifact showing exactly
    which model and settings were used, separate from reading the source
    code. Safe to re-run; overwrites the previous record.
    """
    record = get_config()
    record["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    output_path = record_config()
    print(f"Embedding configuration recorded to {output_path}")
    print(json.dumps(get_config(), indent=2))
