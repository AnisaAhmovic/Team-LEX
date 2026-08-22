import json
import re
from pathlib import Path


POLICY_FILES = [
    "data/processed/privacy_policy.json",
    "data/processed/assessment_policy.json",
    "data/processed/assessment_standards.json",
    "data/processed/responsible_ai_adoption_policy.json",
    "data/processed/student_complaints_management_policy.json"
]

OUTPUT_DIRECTORY = Path("data/processed/chunks")


print("Project Lex Multi-Policy Hierarchical Chunker")
print("---------------------------------------------")


def extract_paragraph_range(text):
    """
    Extract numbered policy paragraphs such as (42), (43), (44).

    Returns the first and last paragraph numbers found.
    If no numbered paragraphs exist, returns None for both values.
    """

    paragraph_numbers = re.findall(r"(?m)^\((\d+)\)$", text)

    if not paragraph_numbers:
        return None, None

    paragraph_numbers = [int(number) for number in paragraph_numbers]

    return min(paragraph_numbers), max(paragraph_numbers)


def chunk_policy(policy_data):
    """
    Convert one processed policy into hierarchical chunks.
    """

    policy_text = policy_data["content"]
    headings = policy_data["headings"]

    # Build a lookup of heading text and heading level
    heading_lookup = {
        heading["text"]: heading["level"]
        for heading in headings
    }

    # Track the current position within the policy hierarchy
    hierarchy = {
        "h1": None,
        "h2": None,
        "h3": None,
        "h4": None
    }

    chunks = []

    current_lines = []
    current_heading = None
    current_level = None
    current_hierarchy = None

    def save_current_chunk():
        """
        Save the current chunk and attach its source metadata.
        """

        if not current_lines or not current_heading:
            return

        text = "\n".join(current_lines).strip()

        # Do not create chunks containing only a heading
        if len(text.splitlines()) == 1:
            return

        paragraph_start, paragraph_end = extract_paragraph_range(text)

        chunk = {
            "chunk_id": f"{policy_data['document_id']}-{len(chunks) + 1}",
            "document_id": policy_data["document_id"],
            "policy_title": policy_data["policy_title"],
            "heading_level": current_level,
            "section": current_hierarchy.get("h1"),
            "subsection": current_hierarchy.get("h2"),
            "topic": current_hierarchy.get("h3"),
            "subtopic": current_hierarchy.get("h4"),
            "paragraph_start": paragraph_start,
            "paragraph_end": paragraph_end,
            "source_url": policy_data["source_url"],
            "status_details_url": policy_data["status_details_url"],
            "status": policy_data["status"],
            "effective_date": policy_data["effective_date"],
            "review_date": policy_data["review_date"],
            "approval_authority": policy_data["approval_authority"],
            "approval_date": policy_data["approval_date"],
            "version": policy_data["version"],
            "text": text
        }

        chunks.append(chunk)

    # Read the policy line by line
    for line in policy_text.splitlines():
        line = line.strip()

        if not line:
            continue

        if line in heading_lookup:

            # Save the content belonging to the previous heading
            save_current_chunk()

            current_level = heading_lookup[line]

            # Update the hierarchy
            hierarchy[current_level] = line

            # Clear hierarchy levels below the new heading
            if current_level == "h1":
                hierarchy["h2"] = None
                hierarchy["h3"] = None
                hierarchy["h4"] = None

            elif current_level == "h2":
                hierarchy["h3"] = None
                hierarchy["h4"] = None

            elif current_level == "h3":
                hierarchy["h4"] = None

            current_heading = line
            current_hierarchy = hierarchy.copy()
            current_lines = [line]

        else:
            current_lines.append(line)

    # Save the final chunk in the policy
    save_current_chunk()

    return chunks


# Create a separate directory for chunk outputs
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

total_chunks = 0


# Process every policy
for policy_file in POLICY_FILES:

    with open(policy_file, "r", encoding="utf-8") as input_file:
        policy_data = json.load(input_file)

    chunks = chunk_policy(policy_data)

    input_path = Path(policy_file)

    output_file = OUTPUT_DIRECTORY / (
        input_path.stem + "_chunks.json"
    )

    with open(output_file, "w", encoding="utf-8") as output:
        json.dump(
            chunks,
            output,
            ensure_ascii=False,
            indent=4
        )

    total_chunks += len(chunks)

    paragraphs_found = sum(
        1 for chunk in chunks
        if chunk["paragraph_start"] is not None
    )

    print(f"\nPolicy: {policy_data['policy_title']}")
    print(f"Document ID: {policy_data['document_id']}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Chunks with paragraph references: {paragraphs_found}")
    print(f"Output: {output_file}")


print("\n---------------------------------------------")
print(f"Policies processed: {len(POLICY_FILES)}")
print(f"Total chunks created: {total_chunks}")
print("All selected policies chunked successfully.")