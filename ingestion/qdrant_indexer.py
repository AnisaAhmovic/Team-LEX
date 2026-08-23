"""
Project Lex - COPL-183
Index policy chunks into a local Qdrant collection using BGE-M3
embeddings.

Usage (run from the repository root, with the virtual environment active):

    # First run / full index of every chunk file in data/processed/chunks
    python -m ingestion.qdrant_indexer --recreate

    # Re-run later without wiping the collection (e.g. after adding a
    # sixth policy's chunk file) - upserts are safe to repeat
    python -m ingestion.qdrant_indexer

    # Index/replace a single chunk file only
    python -m ingestion.qdrant_indexer --file assessment_policy_chunks.json

    # reprocessed one policy and the chunk boundaries changed:
    # remove that policy's old points before re-indexing it, so orphaned
    # chunks from the previous chunk boundaries don't linger
    python -m ingestion.qdrant_indexer --replace-document 216

How chunk IDs map to Qdrant point IDs:
    Each chunk's "chunk_id" (e.g. "216-1") is hashed deterministically into
    a UUID with uuid5. Re-indexing the same chunk_id therefore always
    upserts (overwrites) the same Qdrant point rather than creating a
    duplicate, which is what makes plain re-runs safe.
"""

import argparse
import json
import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ingestion.embedder import embed_texts
from ingestion.embedding_config import (
    CHUNKS_DIRECTORY,
    DISTANCE_METRIC,
    EMBEDDING_DIMENSION,
    PAYLOAD_FIELDS,
    QDRANT_COLLECTION_NAME,
    QDRANT_HOST,
    QDRANT_LOCAL_PATH,
    QDRANT_MODE,
    QDRANT_PORT,
    record_config,
)

# Fixed namespace so chunk_id -> point_id mapping is stable across runs
# and machines.
POINT_ID_NAMESPACE = uuid.UUID("a63e6c2e-6e7f-4f6b-9c9a-2e6a2f8f0c11")

DISTANCE_MAP = {
    "Cosine": qmodels.Distance.COSINE,
    "Dot": qmodels.Distance.DOT,
    "Euclid": qmodels.Distance.EUCLID,
}


def get_client():
    """
    Return a QdrantClient using whichever mode is set in
    ingestion/embedding_config.py.

    "local" (default): embedded mode, no server or Docker required -
    Qdrant runs in-process and persists to QDRANT_LOCAL_PATH on disk.

    "server": connects to a Qdrant server (e.g. started via
    docker-compose.qdrant.yml) at QDRANT_HOST:QDRANT_PORT.
    """
    if QDRANT_MODE == "server":
        print(f"Connecting to Qdrant server at {QDRANT_HOST}:{QDRANT_PORT} ...")
        return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    print(f"Using embedded Qdrant, storing data at ./{QDRANT_LOCAL_PATH} ...")
    return QdrantClient(path=QDRANT_LOCAL_PATH)


def ensure_collection(client, recreate=False):
    """
    Create the collection if it doesn't exist. With recreate=True, drop
    and recreate it (used for a clean full re-index).
    """
    exists = client.collection_exists(QDRANT_COLLECTION_NAME)

    if exists and recreate:
        print(f"Deleting existing collection '{QDRANT_COLLECTION_NAME}' ...")
        client.delete_collection(QDRANT_COLLECTION_NAME)
        exists = False

    if not exists:
        print(f"Creating collection '{QDRANT_COLLECTION_NAME}' ...")
        client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=DISTANCE_MAP[DISTANCE_METRIC],
            ),
        )
    else:
        print(f"Using existing collection '{QDRANT_COLLECTION_NAME}'.")


def chunk_point_id(chunk_id):
    return str(uuid.uuid5(POINT_ID_NAMESPACE, chunk_id))


def load_chunk_files(only_file=None):
    """
    Return a list of Paths to chunk JSON files under data/processed/chunks.
    If only_file is given, return just that one file (name or full path).
    """
    if only_file:
        path = Path(only_file)
        if not path.is_absolute() and not path.exists():
            path = CHUNKS_DIRECTORY / only_file
        if not path.exists():
            raise FileNotFoundError(f"Chunk file not found: {path}")
        return [path]

    files = sorted(CHUNKS_DIRECTORY.glob("*.json"))
    if not files:
        raise FileNotFoundError(
            f"No chunk files found in {CHUNKS_DIRECTORY}. "
            "Confirm chunker output has been pulled from main."
        )
    return files


def load_chunks(files):
    chunks = []
    for file_path in files:
        with open(file_path, encoding="utf-8") as f:
            file_chunks = json.load(f)
        print(f"Loaded {len(file_chunks)} chunks from {file_path.name}")
        chunks.extend(file_chunks)
    return chunks


def delete_document(client, document_id):
    """
    Delete every indexed chunk belonging to one document_id. Used before
    re-indexing a policy whose chunk boundaries have changed, so stale
    points from the previous chunking run don't remain in the collection.
    """
    print(f"Deleting existing points for document_id={document_id!r} ...")
    client.delete(
        collection_name=QDRANT_COLLECTION_NAME,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )


def index_chunks(client, chunks, batch_size=16):
    """Embed and upsert chunks into Qdrant in batches."""
    total = len(chunks)
    for start in range(0, total, batch_size):
        batch = chunks[start:start + batch_size]
        texts = [chunk["text"] for chunk in batch]
        vectors = embed_texts(texts, batch_size=batch_size)

        points = []
        for chunk, vector in zip(batch, vectors):
            payload = {field: chunk.get(field) for field in PAYLOAD_FIELDS}
            points.append(
                qmodels.PointStruct(
                    id=chunk_point_id(chunk["chunk_id"]),
                    vector=vector,
                    payload=payload,
                )
            )

        client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=points)
        print(f"Indexed {min(start + batch_size, total)}/{total} chunks")


def main():
    parser = argparse.ArgumentParser(description="Index policy chunks into Qdrant.")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the collection before indexing (full re-index).",
    )
    parser.add_argument(
        "--file",
        help="Index only this chunk file (e.g. assessment_policy_chunks.json).",
    )
    parser.add_argument(
        "--replace-document",
        metavar="DOCUMENT_ID",
        help="Delete existing points for this document_id before re-indexing "
             "(use when a policy's chunk boundaries have changed).",
    )
    args = parser.parse_args()

    client = get_client()
    ensure_collection(client, recreate=args.recreate)

    if args.replace_document:
        delete_document(client, args.replace_document)

    files = load_chunk_files(only_file=args.file)
    chunks = load_chunks(files)

    index_chunks(client, chunks)

    config_path = record_config()
    count = client.count(QDRANT_COLLECTION_NAME, exact=True).count
    print(f"\nDone. Collection '{QDRANT_COLLECTION_NAME}' now holds {count} points.")
    print(f"Embedding configuration recorded to {config_path}")


if __name__ == "__main__":
    main()
