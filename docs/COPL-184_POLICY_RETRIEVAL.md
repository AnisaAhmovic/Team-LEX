# COPL-184: Current policy evidence retrieval

This component accepts a natural-language question and returns relevant,
current La Trobe policy evidence with authoritative source URLs. It reuses
the BGE-M3 model, Qdrant collection and payload structure implemented for
COPL-183.

## What is included

- `retrieval/policy_retriever.py`: reusable validation, embedding, Qdrant
  search, evidence formatting and guardrails.
- `retrieve_policy.py`: command-line interface.
- `POST /api/retrieve/`: basic Django REST endpoint.
- `verify_retrieval.py`: supported and unsupported verification samples.
- `tests/`: unit tests and an in-memory Qdrant integration test.

## Guardrails

The retriever:

1. requires a text question between 3 and 500 characters;
2. creates a normalised 1,024-dimension BGE-M3 question embedding;
3. asks Qdrant for exactly the five most similar chunks;
4. applies a Qdrant payload filter of `status = Current`;
5. applies a default cosine-similarity threshold of `0.55`;
6. checks the status again after retrieval;
7. rejects incomplete evidence or a source URL outside the official
   `latrobe.edu.au` domain; and
8. returns no evidence, a safe fallback and escalation guidance when the
   evidence is insufficient or unavailable.

A result includes only:

- `policy_text`
- `policy_title`
- `section`
- `source_url`
- `similarity_score`

The threshold is an initial prototype setting. It should be reviewed against
a larger labelled question set before production use.

## Set up and index the policies

From the repository root:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-embeddings.txt
python -m ingestion.qdrant_indexer --recreate
```

On Windows PowerShell, activate the environment with:

```powershell
venv\Scripts\Activate.ps1
```

The first indexing run downloads `BAAI/bge-m3` and creates the local
`qdrant_storage/` collection. See
`docs/COPL-183_EMBEDDING_AND_INDEXING_SETUP.md` for server-mode options.

## Command-line use

Supported sample:

```bash
python retrieve_policy.py "What does the Assessment Policy say about feedback on assessment tasks?"
```

Unsupported sample:

```bash
python retrieve_policy.py "What will the weather be in Melbourne tomorrow?"
```

The supported question should return one or more evidence objects. The
unsupported question should return `status: fallback`, no evidence and a link
to the official Policy Library.

Run both samples as a repeatable check:

```bash
python verify_retrieval.py
```

## Django endpoint

Start Django after completing the normal project setup:

```bash
python manage.py runserver
```

Then send a JSON request:

```bash
curl -X POST http://127.0.0.1:8000/api/retrieve/ \
  -H "Content-Type: application/json" \
  -d '{"question":"What does the Assessment Policy say about feedback?"}'
```

Response behaviour:

- `200`: retrieval completed, with either supported evidence or an
  insufficient-evidence fallback;
- `400`: invalid or missing question; and
- `503`: the embedding model, Qdrant storage or collection is unavailable.

## Tests

Run the retrieval tests without downloading BGE-M3:

```bash
python -m unittest discover -s tests -v
```

Run the Django endpoint tests:

```bash
python manage.py test api
```

The automated coverage includes question validation, BGE-M3 vector-dimension
validation, a supported question, an unsupported below-threshold question,
current-policy filtering, the five-result limit, required citation fields,
untrusted or missing source rejection, Qdrant failure handling and endpoint
status codes.
