# Lex AI Frontend

This directory contains the initial React chatbot interface for **Lex AI**, the Project LEX policy assistant.

## Contribution attribution

The original React component and styling implementation in `src/` was supplied by a Team LEX teammate as their TS8 frontend contribution. During repository integration, the user-facing name was aligned from `COPL-131 Assistant` to `Lex AI`, and the minimal Vite project scaffold was added so the frontend can be run independently.

## Current status

The chat calls `POST /api/answer/` and displays server-provided claim references, authoritative source links, section details, recorded currency and supporting excerpts. It never parses model-written links or HTML. The Vite development proxy forwards `/api` to `http://127.0.0.1:8000`. Start the Django backend and its local Qdrant/BGE-M3/Ollama dependencies before asking a live question.

Questions and responses are logged locally for quality review. Avoid entering personal information. See [citation and audit documentation](../docs/S4-06-S4-10_CITATIONS_AND_AUDIT.md).

## Run locally

```bash
npm install
npm run dev
```

To create a production build:

```bash
npm run build
```


Check citation rendering and link safety with `npm run test:sources`. For a production deployment, configure the same-origin `/api` route to Django; the Vite development proxy is not part of the static build.
