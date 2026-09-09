"""
Project Lex - COPL-276

Generalised corpus input for the La Trobe University Policy Library.

Loads documents discovered by the systematic discovery process from the
corpus manifest and converts them into processing inputs for the reusable
Sprint 3 policy processor.

La Trobe document_id remains the authoritative document identity.
"""

import json
from pathlib import Path

from ingestion.policy_processor import process_policy


CORPUS_MANIFEST_PATH = Path("data/corpus/corpus_manifest.json")
CORPUS_OUTPUT_DIRECTORY = Path("data/processed/corpus")


def load_corpus_manifest(manifest_path=CORPUS_MANIFEST_PATH):
    """
    Load and validate the discovered Policy Library corpus manifest.

    Returns the list of discovered document records.
    """

    with open(manifest_path, "r", encoding="utf-8") as input_file:
        manifest = json.load(input_file)

    documents = manifest.get("documents")

    if not isinstance(documents, list):
        raise ValueError(
            "Corpus manifest does not contain a valid documents list."
        )

    expected_count = manifest.get("document_count")

    if expected_count is not None and expected_count != len(documents):
        raise ValueError(
            "Corpus manifest document_count does not match the documents list."
        )

    return documents


def build_processing_input(document):
    """
    Convert one discovered document record into processor input.

    The output filename is derived from the authoritative La Trobe document_id
    rather than from the document title.
    """

    document_id = document.get("document_id")
    source_url = document.get("source_url")

    if not document_id:
        raise ValueError("Corpus document is missing document_id.")

    if not source_url:
        raise ValueError(
            f"Corpus document {document_id} is missing source_url."
        )

    output_file = CORPUS_OUTPUT_DIRECTORY / f"{document_id}.json"

    return {
        "document_id": document_id,
        "policy_url": source_url,
        "output_file": str(output_file)
    }


def build_corpus_processing_inputs(documents):
    """
    Build processing inputs for every discovered corpus document.
    """

    return [
        build_processing_input(document)
        for document in documents
    ]


def process_corpus_document(processing_input):
    """
    Process one corpus document using the reusable policy processor.

    This function provides the execution interface for later corpus processing
    without changing the validated document-processing implementation.
    """

    CORPUS_OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    return process_policy(
        document_id=processing_input["document_id"],
        policy_url=processing_input["policy_url"],
        output_file=processing_input["output_file"]
    )


def main():
    """
    Validate the generalised corpus input without processing the full corpus.
    """

    documents = load_corpus_manifest()
    processing_inputs = build_corpus_processing_inputs(documents)

    print("Project Lex Generalised Corpus Input")
    print("------------------------------------")
    print(f"Documents loaded from manifest: {len(documents)}")
    print(f"Processing inputs created: {len(processing_inputs)}")

    if processing_inputs:
        print("\nFirst processing input:")
        print(json.dumps(processing_inputs[0], indent=4))

    print("\nCorpus input prepared successfully.")
    print("Full corpus processing has not been run.")


if __name__ == "__main__":
    main()