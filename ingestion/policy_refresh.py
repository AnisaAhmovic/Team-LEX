"""
Project LEX - single-document policy refresh and cleanse.

Refreshes one known Policy Library document from the authoritative source,
rebuilds its chunks, and replaces that document's existing Qdrant points.

Automatic policy-change detection is outside this module's scope.
"""

import argparse
import json
from pathlib import Path

from ingestion.corpus_processor import (
    build_processing_input,
    load_corpus_manifest,
    process_corpus_document,
)
from ingestion.policy_chunker import chunk_policy
from ingestion.qdrant_indexer import (
    delete_document,
    get_client,
    index_chunks,
)


CHUNKS_DIRECTORY = Path("data/processed/chunks")


def find_document(documents, document_id):
    """Return the authoritative manifest record for one document_id."""
    document_id = str(document_id)

    for document in documents:
        if str(document.get("document_id")) == document_id:
            return document

    raise ValueError(
        f"Document ID {document_id} was not found in the corpus manifest."
    )


def write_chunks(document_id, chunks):
    """Persist replacement chunks for one successfully processed document."""
    CHUNKS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_file = CHUNKS_DIRECTORY / f"{document_id}_chunks.json"

    with open(output_file, "w", encoding="utf-8") as output:
        json.dump(chunks, output, ensure_ascii=False, indent=4)

    return output_file


def refresh_document(document_id):
    """Refresh and cleanse one known policy document."""
    document_id = str(document_id)

    documents = load_corpus_manifest()
    document = find_document(documents, document_id)
    processing_input = build_processing_input(document)

    # Complete replacement artifacts before touching the existing index.
    policy_data = process_corpus_document(processing_input)
    chunks = chunk_policy(policy_data)

    if not chunks:
        raise ValueError(
            f"Document {document_id} produced no chunks; "
            "existing Qdrant points were not changed."
        )

    chunk_file = write_chunks(document_id, chunks)

    # Replace indexed content only after fresh artifacts exist.
    client = get_client()
    delete_document(client, document_id)
    index_chunks(client, chunks)

    return {
        "document_id": document_id,
        "policy_title": policy_data["policy_title"],
        "chunks_indexed": len(chunks),
        "processed_file": processing_input["output_file"],
        "chunk_file": str(chunk_file),
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Refresh one known La Trobe policy and replace its indexed chunks."
        )
    )
    parser.add_argument(
        "document_id",
        help="Authoritative La Trobe Policy Library document ID.",
    )
    args = parser.parse_args()

    result = refresh_document(args.document_id)

    print("\nSingle-document policy refresh complete.")
    print(f"Document ID: {result['document_id']}")
    print(f"Policy: {result['policy_title']}")
    print(f"Chunks indexed: {result['chunks_indexed']}")
    print(f"Processed output: {result['processed_file']}")
    print(f"Chunk output: {result['chunk_file']}")


if __name__ == "__main__":
    main()
