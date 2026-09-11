"""
Project Lex - COPL-276 / COPL-277 / COPL-278 / COPL-279 / COPL-280

Corpus processing for the La Trobe University Policy Library.

Loads documents discovered by the systematic discovery process from the
corpus manifest, converts them into processing inputs, and processes the
discovered corpus using the reusable Sprint 3 policy processor.

Discovery provenance is carried through the corpus processing interface.
La Trobe document_id remains the authoritative document identity.
Individual document failures do not stop the remaining corpus from processing.
Processing outcomes retain discovered document identity and provenance for
processed, access-restricted and failed documents.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from ingestion.policy_processor import (
    AuthoritativeSourceAccessError,
    process_policy,
)


CORPUS_MANIFEST_PATH = Path("data/corpus/corpus_manifest.json")
CORPUS_OUTPUT_DIRECTORY = Path("data/processed/corpus")
CORPUS_RUN_REPORT_PATH = Path("data/corpus/corpus_processing_report.json")


def clear_corpus_outputs(output_directory=CORPUS_OUTPUT_DIRECTORY):
    """
    Remove existing processed corpus JSON files before a full corpus refresh.
    """
    output_directory.mkdir(parents=True, exist_ok=True)

    for corpus_file in output_directory.glob("*.json"):
        corpus_file.unlink()


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

    The authoritative document identity, title, source URL and discovery
    provenance are retained. The output filename is derived from the La Trobe
    document_id rather than from the document title.
    """

    document_id = document.get("document_id")
    policy_title = document.get("policy_title")
    source_url = document.get("source_url")
    document_type = document.get("document_type")
    discovery_source_url = document.get("discovery_source_url")

    if not document_id:
        raise ValueError("Corpus document is missing document_id.")

    if not source_url:
        raise ValueError(
            f"Corpus document {document_id} is missing source_url."
        )

    if not document_type:
        raise ValueError(
            f"Corpus document {document_id} is missing document_type."
        )

    if not discovery_source_url:
        raise ValueError(
            f"Corpus document {document_id} is missing discovery_source_url."
        )

    output_file = CORPUS_OUTPUT_DIRECTORY / f"{document_id}.json"

    return {
        "document_id": document_id,
        "policy_title": policy_title,
        "policy_url": source_url,
        "document_type": document_type,
        "discovery_source_url": discovery_source_url,
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

    Discovery provenance is passed to the processor together with the
    authoritative document identity and source URL.
    """

    CORPUS_OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    return process_policy(
        document_id=processing_input["document_id"],
        policy_url=processing_input["policy_url"],
        output_file=processing_input["output_file"],
        document_type=processing_input["document_type"],
        discovery_source_url=processing_input["discovery_source_url"]
    )


def process_corpus(processing_inputs):
    """
    Process every corpus input while isolating individual document outcomes.

    Returns a run report containing processed, access-restricted and failed
    outcomes together with the discovered identity and provenance of each
    attempted document.
    """

    started_at = datetime.now(timezone.utc).isoformat()
    results = []

    for position, processing_input in enumerate(processing_inputs, start=1):
        document_id = processing_input["document_id"]

        print(
            f"\n[{position}/{len(processing_inputs)}] "
            f"Processing document {document_id}"
        )

        try:
            process_corpus_document(processing_input)

            results.append({
                "document_id": document_id,
                "policy_title": processing_input["policy_title"],
                "document_type": processing_input["document_type"],
                "source_url": processing_input["policy_url"],
                "discovery_source_url": processing_input[
                    "discovery_source_url"
                ],
                "status": "Processed",
                "output_file": processing_input["output_file"],
                "error": None
            })

        except AuthoritativeSourceAccessError as error:
            print(
                f"Document {document_id} access restricted: {error}"
            )

            results.append({
                "document_id": document_id,
                "policy_title": processing_input["policy_title"],
                "document_type": processing_input["document_type"],
                "source_url": processing_input["policy_url"],
                "discovery_source_url": processing_input[
                    "discovery_source_url"
                ],
                "status": "Access Restricted",
                "output_file": processing_input["output_file"],
                "error": f"{type(error).__name__}: {error}"
            })

        except Exception as error:
            print(
                f"Document {document_id} failed: "
                f"{type(error).__name__}: {error}"
            )

            results.append({
                "document_id": document_id,
                "policy_title": processing_input["policy_title"],
                "document_type": processing_input["document_type"],
                "source_url": processing_input["policy_url"],
                "discovery_source_url": processing_input[
                    "discovery_source_url"
                ],
                "status": "Failed",
                "output_file": processing_input["output_file"],
                "error": f"{type(error).__name__}: {error}"
            })

    processed_count = sum(
        result["status"] == "Processed"
        for result in results
    )
    access_restricted_count = sum(
        result["status"] == "Access Restricted"
        for result in results
    )
    failed_count = sum(
        result["status"] == "Failed"
        for result in results
    )

    outcome_summary = {
        "Processed": processed_count,
        "Access Restricted": access_restricted_count,
        "Failed": failed_count
    }

    return {
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "documents_attempted": len(processing_inputs),
        "documents_processed": processed_count,
        "documents_access_restricted": access_restricted_count,
        "documents_failed": failed_count,
        "outcome_summary": outcome_summary,
        "results": results
    }


def save_corpus_run_report(
    run_report,
    report_path=CORPUS_RUN_REPORT_PATH
):
    """
    Persist the corpus processing run report as JSON.
    """

    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as output_file:
        json.dump(
            run_report,
            output_file,
            ensure_ascii=False,
            indent=4
        )


def main():
    """
    Process the discovered Policy Library corpus and save a run report.
    """

    documents = load_corpus_manifest()
    processing_inputs = build_corpus_processing_inputs(documents)

    print("Project Lex Corpus Processor")
    print("----------------------------")
    print(f"Documents loaded from manifest: {len(documents)}")
    print(f"Processing inputs created: {len(processing_inputs)}")

    clear_corpus_outputs()

    run_report = process_corpus(processing_inputs)
    save_corpus_run_report(run_report)

    print("\nCorpus processing complete.")
    print(f"Documents attempted: {run_report['documents_attempted']}")
    print(f"Documents processed: {run_report['documents_processed']}")
    print(
        "Documents access restricted: "
        f"{run_report['documents_access_restricted']}"
    )
    print(f"Documents failed: {run_report['documents_failed']}")
    print(f"Run report: {CORPUS_RUN_REPORT_PATH}")


if __name__ == "__main__":
    main()