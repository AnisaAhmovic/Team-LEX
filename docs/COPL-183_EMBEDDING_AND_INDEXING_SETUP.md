# COPL-183: Embedding + Qdrant Indexing Setup

Covers: local Python environment, running Qdrant locally, loading BGE-M3
and recording its configuration, and indexing policy chunks
(`data/processed/chunks/`) with support for re-indexing/replacement.

**Docker is not required.** By default this pipeline runs Qdrant in
**embedded mode** - it runs inside the Python process and persists to a
`qdrant_storage/` folder on disk, no separate service to install or
start. This keeps the team's tech stack as-is (just `pip install`, no
new tool). Docker is only needed if someone specifically wants the
Qdrant web dashboard, or wants two processes able to query the same
running instance at once - see section 4b.

## 1. Prerequisites

- Repository cloned and on the branch with ingestion/chunking work
  merged into `main`, so `data/processed/chunks/*.json` exist.
- The base project virtual environment set up per `docs/SETUP.md`
  (Python 3.10+, `venv` created and activated).
- Docker is optional - only needed for section 4b.

## 2. Add the embedding/indexing files

Copy the following new files into the repository, preserving the paths:

```
ingestion/embedding_config.py
ingestion/embedder.py
ingestion/qdrant_indexer.py
requirements-embeddings.txt
docker-compose.qdrant.yml
docs/COPL-183_EMBEDDING_AND_INDEXING_SETUP.md
```

Add one line to `.gitignore` so the local Qdrant data directory isn't
committed:

```
qdrant_storage/
```

## 3. Install the additional Python dependencies

With the project virtual environment active (see `docs/SETUP.md` steps 2-4):

```bash
pip install -r requirements.txt -r requirements-embeddings.txt
```

This installs `sentence-transformers` (used to load BGE-M3) and
`qdrant-client` (used to talk to Qdrant, in either mode below). `torch`
is pulled in automatically as a dependency of `sentence-transformers`.

## 4. Run Qdrant locally

### 4a. Default: embedded mode (no Docker needed)

Nothing to start manually. `ingestion/embedding_config.py` has
`QDRANT_MODE = "local"` set by default, so the first time the indexer
(section 6) runs, it creates a `qdrant_storage/` folder in the repo root
and stores everything there directly - no server, no extra terminal, no
Docker.

This is the recommended mode for everyone on the team unless you
specifically need the dashboard below.

### 4b. Optional: server mode with a dashboard (requires Docker)

If you want the visual Qdrant dashboard, or need two processes to query
the same live instance at once, switch `QDRANT_MODE = "server"` in
`ingestion/embedding_config.py`, then from the repository root:

```bash
docker compose -f docker-compose.qdrant.yml up -d
```

Verify it's up:

```bash
curl http://localhost:6333/
```

A JSON response containing `"title":"qdrant - vector search engine"` and a
version number confirms Qdrant is running. The dashboard is viewable in a
browser at `http://localhost:6333/dashboard`.

To stop it later: `docker compose -f docker-compose.qdrant.yml down`
(data persists in `./qdrant_storage` between runs; delete that folder to
start from a clean slate).

Note: embedded mode and server mode both use the same
`./qdrant_storage` folder format, but don't run them against the same
folder at the same time from two different processes - pick one mode
and stick with it for a given `qdrant_storage/` folder.

## 5. Embedding model and configuration

Model: **BAAI/bge-m3**, loaded via `sentence-transformers`.

| Setting | Value |
|---|---|
| Model | `BAAI/bge-m3` |
| Provider | `sentence-transformers` |
| Embedding dimension | 1024 |
| Distance metric | Cosine |
| Max sequence length | 8192 tokens |
| Normalize embeddings | Yes |

These values live in `ingestion/embedding_config.py` as the single source
of truth (used by both the indexer and, later, the query-time retriever
so they stay in agreement).

To load the model once and write the current configuration to
`data/processed/embedding_config.json` as a standalone evidence artifact:

```bash
python -m ingestion.embedding_config
```

The first run downloads the model (~2GB) from Hugging Face Hub to the
local cache; later runs reuse the cached copy, so no repeated download.

## 6. Index chunks

Full index (first run, or a clean rebuild of the whole collection):

```bash
python -m ingestion.qdrant_indexer --recreate
```

This creates the `latrobe_policy_chunks` Qdrant collection, embeds the
`text` field of every chunk in `data/processed/chunks/`, and upserts one
Qdrant point per chunk. The remaining chunk fields (`chunk_id`,
`document_id`, `policy_title`, `section`, `source_url`, `status`,
`effective_date`, etc.) are stored as the point's payload, which is what
later supports traceable citations back to the source policy.

Re-running without `--recreate` is safe and just re-embeds and re-upserts
everything (each `chunk_id` maps to the same Qdrant point ID, so repeats
overwrite rather than duplicate):

```bash
python -m ingestion.qdrant_indexer
```

Index (or replace) a single policy's chunk file only:

```bash
python -m ingestion.qdrant_indexer --file assessment_policy_chunks.json
```

If policy reprocessed and the chunk boundaries change (so some
`chunk_id`s from the old version no longer exist), clear that document's
old points first so nothing stale is left behind, then re-index it:

```bash
python -m ingestion.qdrant_indexer --replace-document 216 --file assessment_policy_chunks.json
```

(`216` is the La Trobe policy `document_id`, visible in the chunk JSON
and in the source policy URL, e.g.
`https://policies.latrobe.edu.au/document/view.php?id=216`.)

## 7. Verify the index

```bash
python3 -c "
from ingestion.qdrant_indexer import get_client
client = get_client()
print(client.count('latrobe_policy_chunks', exact=True))
points, _ = client.scroll('latrobe_policy_chunks', limit=1, with_payload=True)
print(points[0].payload['policy_title'], '-', points[0].payload['section'])
"
```

Using `get_client()` here (instead of hardcoding a host/port) means this
check works the same way regardless of which `QDRANT_MODE` you're using.

Expect a count of 85 (matching the 85 chunks reported in
handover guide, unless the chunk files have changed since) and a sample
payload showing a real policy title and section.

## 8. Evidence to link on COPL-183

- `data/processed/embedding_config.json` generated in step 5 (commit or
  attach it — it's a small, reviewable record of the exact model/config
  used, including which `qdrant_mode` was active).
- Terminal output of the `--recreate` indexing run from step 6, showing
  the chunk counts per file and the final "Collection ... now holds 85
  points" line.
- Output of the verification query in step 7.
- If you used server mode (4b): terminal output of `docker compose ... up
  -d` and the `curl` health check, plus a screenshot of the Qdrant
  dashboard showing the `latrobe_policy_chunks` collection with 85
  points and vector size 1024.
