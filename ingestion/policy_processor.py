import json
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


POLICIES = [
    {
        "document_id": "1",
        "url": "https://policies.latrobe.edu.au/document/view.php?id=1",
        "output_file": "data/processed/privacy_policy.json"
    },
    {
        "document_id": "216",
        "url": "https://policies.latrobe.edu.au/document/view.php?id=216",
        "output_file": "data/processed/assessment_policy.json"
    },
    {
        "document_id": "363",
        "url": "https://policies.latrobe.edu.au/document/view.php?id=363",
        "output_file": "data/processed/assessment_standards.json"
    },
    {
        "document_id": "417",
        "url": "https://policies.latrobe.edu.au/document/view.php?id=417",
        "output_file": "data/processed/responsible_ai_adoption_policy.json"
    },
    {
        "document_id": "160",
        "url": "https://policies.latrobe.edu.au/document/view.php?id=160&version=7",
        "output_file": "data/processed/student_complaints_management_policy.json"
    }
]

print("Project Lex Multi-Policy Processor")
print("----------------------------------")


def get_status_metadata(document_id):
    """
    Retrieve authoritative status and currency metadata
    from the La Trobe Policy Library Status and Details page.
    """

    status_url = (
        f"https://policies.latrobe.edu.au/document/"
        f"status-and-details.php?id={document_id}"
    )

    response = requests.get(status_url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    metadata = {
        "status_details_url": status_url,
        "status": None,
        "effective_date": None,
        "review_date": None,
        "approval_authority": None,
        "approval_date": None,
        "version": None
    }

    field_mapping = {
        "Status": "status",
        "Effective Date": "effective_date",
        "Review Date": "review_date",
        "Approval Authority": "approval_authority",
        "Approval Date": "approval_date"
    }

    for label, metadata_key in field_mapping.items():
        label_element = soup.find(
            lambda tag: tag.get_text(" ", strip=True) == label
        )

        if label_element:
            value_element = label_element.find_next()

            while value_element:
                value_text = value_element.get_text(" ", strip=True)

                if value_text and value_text != label:
                    metadata[metadata_key] = value_text
                    break

                value_element = value_element.find_next()

    return metadata

def process_policy(document_id, policy_url, output_file):
    """
    Retrieve, clean and structure one La Trobe policy.
    """

    print(f"\nRetrieving policy from: {policy_url}")

    # 1. Retrieve the policy webpage
    response = requests.get(policy_url, timeout=30)
    response.raise_for_status()

    # 2. Parse the returned HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # 3. Extract the policy title
    title_element = soup.find("h1")

    if not title_element:
        raise ValueError(
            f"Policy title could not be identified for document {document_id}."
        )

    policy_title = title_element.get_text(strip=True)

    # Retrieve authoritative policy status and currency metadata
    status_metadata = get_status_metadata(document_id)   

    # 4. Locate the actual policy document content
    document_content = soup.find("div", id="sliph-document-content")

    if not document_content:
        raise ValueError(
            f"Policy document content could not be located for document {document_id}."
        )

    # Extract the document heading hierarchy
    headings = []

    for heading in document_content.find_all(["h1", "h2", "h3", "h4"]):
        heading_text = heading.get_text(" ", strip=True)

        if heading_text:
            headings.append({
                "level": heading.name,
                "text": heading_text
            })

    # 5. Extract and clean the policy text
    raw_policy_text = document_content.get_text("\n", strip=True)

    excluded_lines = [
        "Top of Page",
        "This is the current version of this document. To view historic versions, click the link in the document's navigation bar."
    ]

    clean_lines = []

    for line in raw_policy_text.splitlines():
        line = line.strip()

        if line and line not in excluded_lines:
            clean_lines.append(line)

    clean_policy_text = "\n".join(clean_lines)

    # 6. Create structured policy data
    policy_data = {
    "document_id": document_id,
    "policy_title": policy_title,
    "source_url": policy_url,
    "status_details_url": status_metadata["status_details_url"],
    "source_system": "La Trobe University Policy Library",
    "retrieved_at": datetime.now(timezone.utc).isoformat(),
    "status": status_metadata["status"],
    "effective_date": status_metadata["effective_date"],
    "review_date": status_metadata["review_date"],
    "approval_authority": status_metadata["approval_authority"],
    "approval_date": status_metadata["approval_date"],
    "version": status_metadata["version"],
    "headings": headings,
    "content": clean_policy_text
}
    # 7. Save the structured output
    with open(output_file, "w", encoding="utf-8") as output:
        json.dump(
            policy_data,
            output,
            ensure_ascii=False,
            indent=4
        )

    # 8. Report successful completion
    print("Policy successfully processed.")
    print(f"Policy title: {policy_title}")
    print(f"HTTP status: {response.status_code}")
    print(f"Clean content characters: {len(clean_policy_text)}")
    print(f"Structured output saved to: {output_file}")


# Process every policy in the manifest
for policy in POLICIES:
    process_policy(
        document_id=policy["document_id"],
        policy_url=policy["url"],
        output_file=policy["output_file"]
    )


print("\nAll selected policies processed successfully.")