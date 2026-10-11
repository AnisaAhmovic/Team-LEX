# Team LEX Local Development Setup

This guide sets up the current Project LEX prototype for local development.

Project LEX is a policy question-answering prototype that retrieves evidence from the current policy corpus and generates constrained answers using locally hosted AI models. Authoritative policy evidence, rather than the language model, is the source of truth.

## Current architecture

The current answer path is:

```text
Current policy corpus
-> structured policy chunks with provenance/current-status metadata
-> BGE-M3 embeddings
-> embedded Qdrant retrieval
-> evidence selection
-> Qwen3 constrained generation
-> semantic groundedness and policy-constraint validation
-> Requirement Coverage Validation (RCV)
-> cited answer or safe fallback
-> audit logging
-> Django API
-> React/Vite interface
```

Key components:

- Django backend/API
- React/Vite frontend
- BGE-M3 embeddings
- embedded Qdrant vector store
- Qwen3 `qwen3:4b-instruct` through Ollama
- DeBERTa NLI model `cross-encoder/nli-deberta-v3-xsmall`
- isolated Stanza-based Requirement Coverage Validator (RCV)

The verified Qdrant corpus/index baseline contains 3,937 points/chunks.

## Prerequisites

- Git
- Python for the main application environment
- Python 3.13.15 for the validated isolated RCV environment
- Node.js 20.19+ or 22.12+
- npm
- Ollama

The repository contains two application parts:

- Django backend at the repository root
- React/Vite frontend in `frontend/`

## 1. Clone the repository

```bash
git clone https://github.com/AnisaAhmovic/Team-LEX.git
cd Team-LEX
```

For an existing checkout, update it using the team's normal Git workflow.

## 2. Create the main Python virtual environment

macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

The `venv/` directory is ignored by Git and should remain local.

## 3. Configure backend environment variables

Create a local `.env` file from the example.

macOS/Linux:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Replace the example `SECRET_KEY` with a local development value. Do not commit `.env`.

The current production-generation baseline is:

```text
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b-instruct
OLLAMA_TIMEOUT_SECONDS=300
OLLAMA_KEEP_ALIVE=5m
```

Use `.env.example` as the tracked configuration reference.

## 4. Install main application dependencies

With the main virtual environment active:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-embeddings.txt -r requirements-llm.txt
```

The dependency sets are deliberately separated:

- `requirements.txt` - Django/backend dependencies
- `requirements-embeddings.txt` - BGE-M3, Qdrant and sentence-transformers
- `requirements-llm.txt` - Qwen/Ollama service dependencies
- `requirements-rcv.txt` - isolated RCV dependencies; do not install these into the main environment as a substitute for the RCV environment

The DeBERTa NLI validator is loaded through `sentence-transformers`, supplied by `requirements-embeddings.txt`.

## 5. Install the Qwen3 generation model

Project LEX uses Ollama to serve the generation model locally.

Install the verified production model:

```bash
ollama pull qwen3:4b-instruct
```

Confirm it is available:

```bash
ollama list
```

The production model is `qwen3:4b-instruct`, not `qwen3:4b`.

Project LEX uses the instruction-tuned model as supplied through Ollama; it does not rely on project-specific Qwen fine-tuning.

## 6. Set up the local database

The development backend uses SQLite.

For a new local environment:

```bash
python manage.py migrate
```

This creates/updates `db.sqlite3` locally. The database file is ignored by Git.

Optional admin account:

```bash
python manage.py createsuperuser
```

## 7. Set up the Requirement Coverage Validator (RCV)

The RCV uses a separate Python environment so its validated linguistic dependency set remains isolated from the main Team LEX backend environment.

Validated RCV runtime:

- Python 3.13.15
- Stanza 1.15.0
- dependencies pinned in `requirements-rcv.txt`
- local environment directory `.rcv_stanza_venv/`

Do not commit `.rcv_stanza_venv/`.

Windows PowerShell:

```powershell
py -3.13 -m venv .rcv_stanza_venv
.\.rcv_stanza_venv\Scripts\python.exe -m pip install --upgrade pip
.\.rcv_stanza_venv\Scripts\python.exe -m pip install -r requirements-rcv.txt
```

Verify the isolated runtime:

```powershell
.\.rcv_stanza_venv\Scripts\python.exe --version
.\.rcv_stanza_venv\Scripts\python.exe -c "import stanza; print(stanza.__version__)"
```

The validated versions are Python 3.13.15 and Stanza 1.15.0.

The Django backend invokes production RCV through `api/requirement_coverage.py` and `rcv_runtime_bridge.py`. The bridge uses the isolated RCV runtime and has a 180-second production timeout.

## 8. Policy corpus and embedded Qdrant

LEX retrieves policy evidence using BGE-M3 embeddings and an embedded Qdrant vector store.

Runtime retrieval filters policy evidence to current documents.

The verified corpus/index baseline contains 3,937 Qdrant points/chunks.

### Embedded Qdrant warning

When Django is running, its process owns the `qdrant_storage` lock.

Do not start another process that independently opens the same embedded Qdrant store while Django is running. For example, do not instantiate another embedded Qdrant client from a separate `manage.py shell` process.

A storage-lock conflict in this situation is an environment/process conflict, not evidence of a retrieval defect.

A complete index rebuild, when deliberately required, is available through:

```bash
python -m ingestion.qdrant_indexer --recreate
```

Do not perform a full rebuild merely to start the normal prototype.

## 9. Run the Django backend

With the main Python environment active:

```bash
python manage.py runserver
```

The backend normally runs at:

`http://127.0.0.1:8000`

Useful endpoints include:

- API health check: `http://127.0.0.1:8000/api/health/`
- Answer pathway: `http://127.0.0.1:8000/api/answer/`
- Django admin: `http://127.0.0.1:8000/admin/`

The `/api/answer/` pathway performs retrieval, evidence selection, constrained generation, validation, RCV, citation/fallback handling and audit logging.

## 10. Install and run the React frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite normally serves the frontend at:

`http://localhost:5173`

The React frontend is integrated with the Django/RAG answer pathway.

## 11. Verification commands

### Backend

From the repository root with the main Python environment active:

```bash
python manage.py check
```

Run the established backend regression suites relevant to any backend component being changed.

The full Qwen-backed `/api/answer/` pathway is materially more expensive than a lightweight health/configuration check and should not be repeatedly invoked merely to confirm that Django starts.

### Frontend

From `frontend/`:

```bash
npm run test:messages
npm run build
```

A successful message verification run ends with:

```text
All Task 8 message checks passed.
```

`npm run build` provides the production-style frontend build check.

## 12. Safe fallback and validation behaviour

LEX is designed to prefer a safe fallback over presenting an unsupported or insufficiently validated policy answer.

Generated content is checked against authoritative retrieved evidence using semantic groundedness, policy-constraint validation and requirement coverage controls.

UNKNOWN requirement coverage represents a validation/capability boundary; it does not by itself mean that the application has crashed.

Validator controls must not be weakened merely to increase answer rates.

## 13. BQ-05 - production model reproducibility

**Status: CLOSED / ADOPTED**

BQ-05 corrected a reproducibility gap between the effective production runtime and tracked configuration/setup material.

The verified production baseline is:

```text
OLLAMA_MODEL=qwen3:4b-instruct
OLLAMA_TIMEOUT_SECONDS=300
OLLAMA_KEEP_ALIVE=5m
```

Tracked configuration and setup material now reflect the production `qwen3:4b-instruct` model rather than the older `qwen3:4b` fallback.

## 14. BQ-06 - suppress unverified answer content

**Status: CLOSED / ADOPTED**

BQ-06 extends the existing frontend safety boundary for answers where:

```text
assurance.question_coverage.unknown > 0
```

For this state:

- generated answer content is suppressed;
- the alternative message-rendering path cannot expose that content;
- supporting policy sources remain suppressed; and
- the existing Answer Checks explanation remains visible.

Fully validated answers continue to display normally.

BQ-06 was delivered through PR #44 and verified using the established frontend message harness and production build.

## 15. Policy refresh boundary

The currently verified refresh capability is operator-triggered refresh of a known policy document.

The verified workflow retrieves authoritative policy content, rebuilds its processed/chunked representation, removes the previous document points from Qdrant, indexes the refreshed document, preserves unrelated indexed documents and makes the refreshed current-policy evidence available to retrieval.

Automatic policy-change detection and automatic refresh triggering are not verified production capabilities and must not be represented as such.

## 16. Known handover notes

- `qwen3:4b-instruct` is the current production generation model.
- Qdrant is embedded and must not be opened concurrently by separate application processes.
- RCV uses its own validated Python/Stanza environment.
- DeBERTa NLI validation uses `cross-encoder/nli-deberta-v3-xsmall`.
- UNKNOWN requirement coverage causes unverified answer content and its policy sources to be suppressed by the frontend.
- A known Health & Safety incident-investigation hard case remains parked for future engineering rather than being addressed by weakening validation.
- Policy-constraint validation remains deliberately conservative; finer proposition-level validation is a future enhancement area.
- Automatic policy-change detection remains unverified.

## Git workflow

See [`BRANCHING_STRATEGY.md`](BRANCHING_STRATEGY.md) for the Team LEX branch and pull request process.

## Repository structure

```text
Team-LEX/
|-- api/                         Django application/API and validation
|-- frontend/                    React/Vite interface
|-- ingestion/                   policy processing/indexing
|-- retrieval/                   policy retrieval
|-- docs/                        project documentation
|-- manage.py                    Django management entry point
|-- requirements.txt             base backend dependencies
|-- requirements-embeddings.txt embedding/retrieval dependencies
|-- requirements-llm.txt         LLM service dependencies
|-- requirements-rcv.txt         isolated RCV dependencies
|-- .env.example                 local environment template
`-- README.md                    project overview
```

## Common setup problems

### Django reports that `SECRET_KEY` is missing

Confirm `.env` exists in the repository root and contains a `SECRET_KEY`.

### Frontend cannot call the backend

Confirm Django is running on port 8000 and the frontend origin is included in `CORS_ALLOWED_ORIGINS` in `.env`.

### Qwen generation is unavailable

Confirm Ollama is running and:

```bash
ollama list
```

contains:

```text
qwen3:4b-instruct
```

Also confirm the effective Ollama settings match the tracked production baseline.

### Embedded Qdrant reports a storage lock

Confirm another process is not already using the repository's embedded Qdrant storage. In normal development, allow the running Django process to own that store.

### RCV runtime cannot start

Verify:

```powershell
.\.rcv_stanza_venv\Scripts\python.exe --version
.\.rcv_stanza_venv\Scripts\python.exe -c "import stanza; print(stanza.__version__)"
```

The validated runtime is Python 3.13.15 with Stanza 1.15.0.

### Python package import errors

Confirm the main virtual environment is active and reinstall the main application dependency sets:

```bash
pip install -r requirements.txt -r requirements-embeddings.txt -r requirements-llm.txt
```

### Frontend dependency errors

From `frontend/`:

```bash
npm install
```
