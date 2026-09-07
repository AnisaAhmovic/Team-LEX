"""
Project Lex - COPL-274
Systematic discovery of authoritative La Trobe University Policy Library
documents.

Discovers documents from the authoritative Browse A-Z page rather than
maintaining a hard-coded list of policy URLs.

La Trobe document_id is retained as the authoritative document identity.
"""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup


POLICY_LIBRARY_BROWSE_URL = "https://policies.latrobe.edu.au/browse"
CORPUS_DIRECTORY = Path("data/corpus")
CORPUS_MANIFEST_PATH = CORPUS_DIRECTORY / "corpus_manifest.json"
CORPUS_INVENTORY_PATH = CORPUS_DIRECTORY / "corpus_inventory.csv"


def extract_document_id(url):
    """
    Extract the La Trobe document ID from a Policy Library document URL.

    Example:
        https://policies.latrobe.edu.au/document/view.php?id=208
        -> "208"
    """

    parsed_url = urlparse(url)
    query_parameters = parse_qs(parsed_url.query)

    document_ids = query_parameters.get("id")

    if not document_ids:
        return None

    return document_ids[0]


def infer_document_type(title):
    """
    Infer a preliminary document type from the authoritative document title.

    This classification supports corpus inventory and later inclusion/exclusion
    decisions. It does not replace the authoritative source metadata.
    """

    title_lower = title.lower()

    document_types = [
        ("procedure", "Procedure"),
        ("policy", "Policy"),
        ("standards", "Standard"),
        ("standard", "Standard"),
        ("schedule", "Schedule"),
        ("guidelines", "Guideline"),
        ("guideline", "Guideline"),
        ("code of conduct", "Code"),
        ("charter", "Charter"),
        ("framework", "Framework"),
    ]

    for keyword, document_type in document_types:
        if re.search(rf"\b{keyword}\b", title_lower):
            return document_type

    return "Other"


def discover_documents():
    """
    Discover authoritative documents exposed by the La Trobe Policy Library
    Browse A-Z page.

    Returns one record per unique document_id.
    """

    print("Retrieving authoritative Policy Library document index...")
    print(f"Source: {POLICY_LIBRARY_BROWSE_URL}")

    response = requests.get(POLICY_LIBRARY_BROWSE_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    discovered_documents = {}

    for link in soup.find_all("a", href=True):
        href = link.get("href", "").strip()
        title = link.get_text(" ", strip=True)

        if "document/view.php?id=" not in href:
            continue

        document_id = extract_document_id(href)

        if not document_id or not title:
            continue

        # document_id is deliberately used as the unique identity.
        discovered_documents[document_id] = {
            "document_id": document_id,
            "policy_title": title,
            "document_type": infer_document_type(title),
            "source_url": href,
            "discovery_source_url": POLICY_LIBRARY_BROWSE_URL,
        }

    documents = sorted(
        discovered_documents.values(),
        key=lambda document: document["policy_title"].lower(),
    )

    return documents


def write_corpus_manifest(documents):
    """
    Write the discovered authoritative corpus to a machine-readable manifest.

    The La Trobe document_id remains the authoritative document identity.
    """

    CORPUS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source_system": "La Trobe University Policy Library",
        "discovery_source_url": POLICY_LIBRARY_BROWSE_URL,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "document_count": len(documents),
        "documents": documents,
    }

    with open(CORPUS_MANIFEST_PATH, "w", encoding="utf-8") as output:
        json.dump(
            manifest,
            output,
            ensure_ascii=False,
            indent=4,
        )

    return CORPUS_MANIFEST_PATH


def write_corpus_inventory(documents):
    """
    Write the initial human-readable corpus inventory.

    Processing and indexing fields begin as Not run because discovery alone
    does not prove that a document has been processed or indexed.
    """

    CORPUS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "document_id",
        "policy_title",
        "document_type",
        "source_url",
        "discovery_source_url",
        "discovery_status",
        "processing_status",
        "chunking_status",
        "indexing_status",
        "notes",
    ]

    with open(
        CORPUS_INVENTORY_PATH,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for document in documents:
            writer.writerow(
                {
                    "document_id": document["document_id"],
                    "policy_title": document["policy_title"],
                    "document_type": document["document_type"],
                    "source_url": document["source_url"],
                    "discovery_source_url": document["discovery_source_url"],
                    "discovery_status": "Discovered",
                    "processing_status": "Not run",
                    "chunking_status": "Not run",
                    "indexing_status": "Not run",
                    "notes": "",
                }
            )

    return CORPUS_INVENTORY_PATH


def main():
    documents = discover_documents()

    print("\nProject Lex Policy Library Discovery")
    print("------------------------------------")
    print(f"Unique documents discovered: {len(documents)}")

    type_counts = {}

    for document in documents:
        document_type = document["document_type"]
        type_counts[document_type] = type_counts.get(document_type, 0) + 1

    print("\nPreliminary document-type counts:")

    for document_type in sorted(type_counts):
        print(f"  {document_type}: {type_counts[document_type]}")

    print("\nFirst 10 discovered documents:")

    for document in documents[:10]:
        print(
            f"  {document['document_id']} | "
            f"{document['document_type']} | "
            f"{document['policy_title']}"
        )

    manifest_path = write_corpus_manifest(documents)
    inventory_path = write_corpus_inventory(documents)

    print("\nCorpus control artifacts created:")
    print(f"  Manifest: {manifest_path}")
    print(f"  Inventory: {inventory_path}")


if __name__ == "__main__":
    main()