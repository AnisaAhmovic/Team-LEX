# Sprint 4: policy citations and interaction audit trail

Implements **S4-06** and **S4-10** from the supplied Sprint 4 backlog. This extends the COPL-255 answer endpoint on main, preserving the existing Django, BGE-M3, Qdrant and local Ollama architecture. No ingestion rebuild, new model weights or database migration is required for these changes.

## Provenance review and citation behaviour

`policy_chunker.py` retains document/chunk IDs, title, heading hierarchy, paragraph range, authoritative view/details URLs, recorded status, effective/review/approval dates and available version. `embedding_config.PAYLOAD_FIELDS` and `qdrant_indexer.index_chunks` already preserve them in Qdrant. The retrieval layer previously returned only text/title/section/URL/score. It now retains provenance and a private candidate trace.

The retrieval query still requests exactly five current candidates. Post-query selection excludes low/non-finite scores, non-current content, incomplete provenance, untrusted URLs and duplicate evidence, recording a reason for each exclusion. Documents beginning at h2 can use their actual subsection heading. Unknown optional metadata stays null; no date, title, clause, version or URL is generated to fill a gap.

For explicitly named documents, retrieval resolves full titles against a catalogue of current titles/headings read from the same Qdrant collection. It scopes the vector query to those titles. An explicit question about the purpose, scope or definitions also scopes to matching indexed headings when every named document has that heading. Multiple named documents remain in the query. General questions retain collection-wide semantic search. This uses Qdrant payload filters, preserves the original similarity scores and 0.55 threshold, and needs no re-embedding. The catalogue is cached per retriever; restart the backend after refreshing the index. Catalogue records are lookup metadata, not extra supporting candidates. Only the returned ranked Top-5 can become evidence. The resolved scope is recorded in `retrieval.query_scope`.

The answer pipeline freezes up to five eligible chunks, each capped at 800 characters. Qwen receives request-local IDs, retrieved titles/headings and those exact text snippets, plus the question. Titles/headings identify the documents; the output schema still has no source metadata fields. It returns JSON claims with evidence IDs and supporting quotations. A named policy in a claim must match the metadata of evidence supporting that claim. The API rejects unknown IDs, missing support, invented quotations, quotations outside the bounded context, model-written URLs/reference markers, extra source fields and incomplete generation. An empty claims array means abstention. Invalid output produces a safe fallback with no answer or citations.

The server builds sources exclusively from metadata for evidence actually cited by a validated claim. A selected chunk which the model did not use is not a supporting source. Different sections, paragraph ranges or versions of one URL remain distinct. Identical source metadata can be grouped without losing internal chunk mappings. A claim can refer to multiple policies.

**Validation limit:** matching an exact quote establishes traceability; it does not prove that a paraphrase follows logically from that quote, or that a relevant policy was retrieved. Live model quality and semantic support still need evaluation. The 800-character limit can omit a later relevant passage; the audit records the exact snippet and truncation. Recorded currency describes the indexed snapshot, not a fresh website check on every request.

## Public API contract

`POST /api/answer/` accepts `{"question": "..."}`. A supported response keeps `answer` separate from `sources` and adds `claims` and `interaction_id`:

```json
{
  "status": "supported",
  "question": "What is the purpose of the assessment policy?",
  "answer": "It sets principles for assessment quality. [S1]",
  "claims": [{
    "claim_id": "C1",
    "text": "It sets principles for assessment quality.",
    "source_ids": ["S1"],
    "support": [{"source_id": "S1", "quote": "This Policy provides the principles for assuring the quality of student assessment at La Trobe."}]
  }],
  "sources": [{
    "source_id": "S1",
    "policy_title": "Assessment Policy",
    "section": "Section 2 - Purpose",
    "subsection": null,
    "topic": null,
    "subtopic": null,
    "paragraph_start": 1,
    "paragraph_end": 2,
    "source_url": "https://policies.latrobe.edu.au/document/view.php?id=216",
    "status_details_url": "https://policies.latrobe.edu.au/document/status-and-details.php?id=216",
    "status": "Current",
    "effective_date": "7th September 2021",
    "review_date": "22nd April 2027",
    "approval_date": "11th August 2021",
    "version": null,
    "similarity_score": 0.91
  }],
  "evidence_sufficient": true,
  "model": "qwen3:4b",
  "latency_seconds": 0.0,
  "interaction_id": "server-generated-uuid"
}
```

This is an illustrative response with a fixture score and latency. IDs `C1`, `E1` (internal) and `S1` are scoped to one interaction. The actual field sets are defined in `api/citations.py` (`SOURCE_FIELDS`, `generation_schema`, `build_cited_answer`).

| Source field | Meaning and origin |
| --- | --- |
| `source_id` | Server-issued display identifier, referenced by `claims[].source_ids` |
| `policy_title`, `section`, `source_url` | Required retrieved title, actual heading and HTTPS La Trobe URL |
| `subsection`, `topic`, `subtopic` | Available retrieved hierarchy, otherwise null |
| `paragraph_start`, `paragraph_end` | Available range for the source chunk, otherwise null |
| `status_details_url` | Retrieved details link, accepted only on an authoritative La Trobe host |
| `status`, `effective_date`, `review_date`, `approval_date`, `version` | Recorded currency/version values, null when unavailable |
| `similarity_score` | Original score of the first cited chunk for this grouped source; all chunk scores remain in the audit |

Chunk/point/document IDs stay in retrieval/audit data, outside public answer sources. `/api/retrieve/` still returns evidence without generation and also gets an interaction ID. Private `_trace` candidate diagnostics are removed from API and CLI output.

Fallbacks from `/api/answer/` always have `answer: null`, `claims: []`, `sources: []`, a reason and the existing official-policy escalation link. HTTP status: 200 for insufficient evidence, abstention or rejected citations; 400 for invalid input; 503 for retrieval or audit-storage failure; 502 for generation service failure; 500 for unexpected internal failures. No exception message is exposed.

The React interface now calls this endpoint. Claim markers link to source entries. Entries show authoritative links, hierarchy, available currency and supporting excerpts. React renders text safely; it does not interpret generated HTML or Markdown URLs. The existing interface styling and contribution attribution remain in place.

## Minimum audit record

Records use schema `lex-interaction-v1` and are written for both policy endpoints, including supported, fallback, validation, retrieval, generation, citation-validation and unexpected-error paths.

| Record field | Reconstruction purpose |
| --- | --- |
| `interaction_id`, `timestamp_utc`, `endpoint` | Correlate one request and its returned ID, without identifying a person |
| `question` | Normalised question, redacted and bounded to 500 characters |
| `retrieval.outcome`, `retrieval.config` | Retrieval result, top-k, threshold, current-status filter, embedding identity/dimension, collection and selection version |
| `retrieval.query_scope` | Scope version, matched indexed titles, requested overview section and exact heading filters applied before ranking |
| `retrieval.candidates[]` | All returned Top-5 candidates, original order/rank and score, chunk/point/document IDs, source/currency metadata, full-text hash, eligibility and exclusion reason |
| `selection.selected_context[]` | Exact bounded context supplied to generation, evidence IDs, chunk IDs, metadata, hashes and truncation flags |
| `selection.excluded[]` | Candidate IDs/ranks excluded by evidence rules or the context limit, with reasons |
| `selection.source_evidence[]` | Source ID to evidence ID/chunk ID/rank mapping for returned citations |
| `selection.uncited_context_ids` | Context supplied but not used for a returned supporting citation |
| `generation` | Whether attempted, provider, model tag, prompt/schema version, generation options, completion and validation information, available latency/token counts |
| `outcome`, `http_status`, `error` | Supported/fallback/error and fixed error stage/code, without exception text |
| `response` | Returned answer, claims, sources, fallback reason, model and other safe response fields |
| `privacy` | Redaction version and paths of redacted/truncated fields, never original sensitive values |

Selected-context hashes describe the pre-redaction snippets. If a snippet was redacted, the stored text deliberately differs and the privacy field records that fact. Rejected raw model output is not persisted; its fixed validation reason is retained. Accepted generated claims and the resulting answer are retained in `response`.

`model` records the actual tag reported by Ollama. `/api/generate` does not provide an immutable weights digest, so `model_digest` is explicitly null. This trail supports review, not bit-for-bit inference replay. Prompt version `lex-claims-v2`, selection version `current-authoritative-threshold-v3`, scope version `indexed-title-section-v1`, temperature 0, seed 0, context limit and inference options are recorded. See [Ollama's generation API](https://docs.ollama.com/api/generate) for the schema and options fields.

Citation-text failures have distinct fixed validation codes: `generated_url`, `generated_reference_marker`, `generated_section_reference`, `generated_source_list` and `unverified_policy_title`. Raw rejected model text is still not persisted. The public message for `unverifiable_generation` says that retrieved evidence was found but the generated answer could not be verified; it does not misreport this as a missing index.

## Storage, access and privacy

The prototype uses Python's standard-library SQLite at `var/audit/interactions.sqlite3`, separate from Django's application database. It is created on first interaction. Each request commits one complete JSON record transactionally; concurrent writers use SQLite locking. POSIX file mode is 0600, and a new audit directory is created with mode 0700. Windows access is governed by the local account's filesystem permissions. The application offers no public audit-reader endpoint.

`AUDIT_DB_PATH` and `AUDIT_RETENTION_DAYS` in `mysite/settings.py` configure the path and default 30-day retention. New writes purge expired records with SQLite secure deletion enabled. An inactive deployment needs an explicit purge, using the command below. Review and delete local copies/backups separately. The database and `var/` are excluded from Git.

No names, account IDs, user/session tracking, IP addresses, headers, cookies, credentials, connection URLs, raw request bodies or environment dumps are added to the audit schema. Pattern redaction covers emails, common phone/student identifiers, labelled secrets, bearer/basic tokens, common API tokens, JWTs, credential-bearing URLs and private keys in free text. It is best effort, not guaranteed anonymisation: unlabelled secrets, names, health information or other identifying prose can remain. Users are asked not to enter personal information. Limit local file access and use synthetic questions for demonstrations.

A failed audit write returns a safe 503 instead of a supported answer. Only a fixed error message goes to application logging, never the database path or request content. A process termination before final commit cannot produce a complete record. Records are not encrypted by this application, tamper-evident or immutable, and this work does not claim production compliance.

## Reproduce and inspect

Use Python 3.12+ and the existing local setup. These tests do not download BGE-M3 or Qwen weights:

```bash
python -m pip install -r requirements.txt -r requirements-llm.txt qdrant-client==1.12.1
SECRET_KEY=local-tests-only python manage.py test api tests.test_policy_retriever tests.test_retrieval_qdrant tests.test_citations_audit tests.test_query_scope
npm --prefix frontend install
npm --prefix frontend run test:sources
npm --prefix frontend run build
```

`SECRET_KEY=local-tests-only` is an ephemeral test setting, not a deployment key.

Generate four representative interactions and retrieve their records:

```bash
SECRET_KEY=local-tests-only python verify_citations_audit.py
python inspect_audit.py --path var/audit/demo.sqlite3 --limit 4
python inspect_audit.py --path var/audit/demo.sqlite3 --id <returned-interaction-id>
```

The demo uses repository policy chunks `216-2` and `112-2`, plus fixture rankings, embeddings and generation responses. It runs the actual retrieval rules, endpoint, citation validation and SQLite audit writer. It covers a supported two-policy answer, insufficient evidence, a generation failure and an invalid citation. Assertions compare source metadata with the original chunk records and reconstruct each stored record. It is not evidence of live model quality or retrieval relevance. The records remain local and can be regenerated; do not commit live logs.

For ordinary interactions, `python inspect_audit.py --id <returned-interaction-id>` reads the default database. To remove expired records during inactivity:

```bash
python inspect_audit.py --purge-expired --retention-days 30
```

For compact diagnostics, run `python inspect_audit.py --limit 1 --summary`. This reads existing records without opening Qdrant and can run alongside the backend. Omit `--summary` to inspect the exact stored context, response and citations.

For a live smoke test, start the indexed local retrieval stack, `ollama` with the configured Qwen model and Django (`python manage.py runserver --noreload`), then start the frontend. Ask a supported policy question and an unrelated question, follow the displayed links, and inspect their returned interaction IDs locally. The full corpus/index setup remains in the existing COPL-183/COPL-292 guides.

## Live-test follow-up, 22 September 2026

The supplied local interaction for "What is the purpose of the Assessment Policy?" had five candidates above 0.55, completed Qwen generation, and then `generated_citation_text` / `unverifiable_generation`. Its stored Top-5 omitted `216-2`, the Purpose section. The record establishes the failing stage but does not contain the rejected answer, so the precise offending string cannot be recovered.

A separate reproduction using a valid purpose quotation and the genuine title "Assessment Policy" confirmed a validator false positive. The follow-up accepts a title only when backed by that claim's cited metadata, provides document identity in the prompt, scopes explicit title/section questions using indexed metadata, and records more specific failure diagnostics. Invented titles, titles belonging only to another claim, URLs, manual references and source fields are still rejected.

63 backend tests passed, including the attribution regression, multi-source attribution, scope pagination and real in-memory Qdrant tests for purpose retrieval, current status and unchanged threshold/exclusion behaviour. A valid Assessment Policy purpose claim was also checked against the repository's real `216-2` metadata. These are deterministic checks, not a live BGE-M3/Qwen pass. The follow-up must still be retested on the local model setup.

Retest the same question first. The expected source is Assessment Policy, Section 2 - Purpose, with the authoritative `view.php?id=216` URL and a quote about assuring assessment quality. Inspect the new audit record for `query_scope`, the actual candidate scores, selected chunk `216-2`, generation validation and returned sources. A low score or model abstention must still produce a fallback. Then test Research Human Ethics Procedure, a question naming both policies, an unrelated question, and an unavailable Ollama service. Verify every displayed claim against its actual quotation and official source before marking the live checks complete.

## Verification recorded on 21 September 2026

- 50 backend tests passed, including real in-memory Qdrant retrieval, candidate provenance, multi-source and multi-section citations, untrusted/forged references, truncated context, source deduplication, supported/fallback/error logging, redaction, concurrency, retention and audit failure handling.
- Four representative fixture interactions were stored, read back by ID and reconstructed successfully.
- Frontend citation rendering/link-safety checks and the production build passed.
- Live BGE-M3/Qwen inference was not run in the implementation environment. No full-corpus regression or model-quality result is claimed.

The following authoritative view and details pages were opened and compared with the committed chunk metadata. Both titles, purpose headings and recorded currency matched. Neither chunk supplied a version number, so the output preserves null.

| Chunk | Title/section checked | Authoritative page | Currency checked against details |
| --- | --- | --- | --- |
| `216-2` | Assessment Policy, Section 2 (Purpose), paragraphs 1–2 | [View policy](https://policies.latrobe.edu.au/document/view.php?id=216) | [Details](https://policies.latrobe.edu.au/document/status-and-details.php?id=216): Current, effective 7 September 2021, review 22 April 2027, approval 11 August 2021 |
| `112-2` | Research Human Ethics Procedure, Section 2 (Purpose), paragraphs 1–2 | [View procedure](https://policies.latrobe.edu.au/document/view.php?id=112) | [Details](https://policies.latrobe.edu.au/document/status-and-details.php?id=112): Current, effective/approval 4 December 2025, review 19 November 2028 |

## Backlog traceability

| Task/subtasks | Implementation/evidence |
| --- | --- |
| S4-06 provenance review, retrieved metadata as truth, source schema, title/section/URL/currency, internal IDs | `retrieval/policy_retriever.py`, `api/citations.py`, public contract above |
| S4-06 separate answer/sources, claim association, weak-candidate exclusion, multiple genuine sources, prevent generated metadata | Structured claim contract, exact supporting quotes, source allowlist and validation, `tests/test_citations_audit.py`, frontend source component |
| S4-06 representative citation and URL checks, tests | Two verified authoritative policies above, `verify_citations_audit.py`, backend/frontend checks |
| S4-10 schema, reconstruction fields, Top-5, selected/excluded context, rankings, answer/citations/outcome, configuration | Audit schema above, retriever trace and `api/views.py` |
| S4-10 storage, data minimisation, secrets exclusion | `api/audit.py`, settings, ignored SQLite files, redaction and privacy limits above |
| S4-10 supported/fallback/failure records, sample generation, manual retrieval, reconstruction and gap checks | All endpoint outcomes tested; `verify_citations_audit.py`, `inspect_audit.py`; real stored sample records read back by ID |
| S4-10 logging/privacy documentation | This guide and frontend notice |

Task requirement references supplied in the backlog: S4-06, FR6/FR7, NFR2/NFR6/NFR9, UC7; S4-10, FR12/FR18/FR19, NFR11, UC4. This mapping does not claim that these broader requirements are fully satisfied outside the two tasks. Future guardrail branches should use the same audited response path.

## CPU embedding retest (22 September 2026)

The live scoped Assessment Policy Purpose query found chunk `216-2` but scored
0.263078, below the unchanged 0.55 threshold. Generation was not attempted.
A user-run CPU diagnostic against that same stored vector scored 0.582859;
re-embedding its payload on CPU also scored 0.582859. Stored/fresh vector cosine
was approximately 1.0. This validates that one stored vector against CPU output,
not the entire index. The prior automatically selected device was not recorded,
so an MPS-specific root cause is suspected, not proven.

The shared index/query embedder now explicitly constructs BGE-M3 on CPU.
Configuration records and retrieval audit configuration include embedding_device.
The existing index can be used for the next retest; no threshold reduction or
re-index is required for this verified chunk. CPU execution may be slower.
Restart Django, repeat the Purpose question and inspect the new audit. A supported
answer with verified citations still requires live Qwen validation.
