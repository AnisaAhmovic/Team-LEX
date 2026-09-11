# COPL-292 — Corpus Processing and Refresh

## Purpose

This document provides the technical handover for the Project Lex Policy Database corpus ingestion and refresh capability delivered under Sprint 4 Task 2.

It documents how the La Trobe University Policy Library corpus is discovered, processed, chunked, embedded, indexed and refreshed, including the governance considerations, exceptions, limitations and validation evidence established during implementation.

## Scope

This document covers the Task 2 corpus pipeline only:

- authoritative Policy Library discovery;
- corpus scope and document identity;
- policy processing;
- provenance and currency metadata;
- hierarchical chunking;
- BGE-M3 embedding;
- Qdrant indexing;
- repeatable corpus refresh;
- corpus metrics and reconciliation;
- representative retrieval validation;
- known exceptions and technical limitations.

Full prototype installation, environment setup and end-to-end startup instructions are outside the scope of COPL-292 and will be completed during Sprint 4 integration and closeout.

## Authoritative Source and Corpus Discovery

### Authoritative source

The corpus is systematically discovered from the La Trobe University Policy Library Browse A-Z page:

`https://policies.latrobe.edu.au/browse`

The discovery implementation is contained in `ingestion/policy_discovery.py`. It retrieves the authoritative Browse A-Z page and identifies links matching the Policy Library document pattern `document/view.php?id=`. This replaces the Sprint 3 prototype approach of maintaining a hard-coded set of policy URLs and allows the corpus definition to be regenerated from the authoritative source.

### Document identity and discovery metadata

The La Trobe `document_id` extracted from each Policy Library document URL is used as the authoritative document identity. Discovery produces one record per unique `document_id`.

Each discovered record contains:

- `document_id`;
- `policy_title`;
- `document_type`;
- `source_url`;
- `discovery_source_url`.

`document_type` is a preliminary classification inferred from the authoritative document title for corpus inventory purposes. The implementation explicitly treats this classification as supporting metadata rather than a replacement for authoritative source metadata.

### Discovery outputs

A discovery run generates two corpus-control artefacts under `data/corpus/`:

- `corpus_manifest.json` — machine-readable manifest of the discovered authoritative corpus;
- `corpus_inventory.csv` — human-readable inventory used to record the discovery baseline.

The manifest records the source system, authoritative discovery URL, UTC discovery timestamp, document count and discovered document records.

The inventory initially records each document as `Discovered`, while processing, chunking and indexing statuses are initialised as `Not run`. Discovery alone therefore does not imply successful downstream processing or indexing.

### Current corpus baseline

The current committed manifest was generated on 7 September 2026 and records 215 unique documents discovered from the La Trobe University Policy Library.

This manifest is the processing input baseline for the subsequent corpus-processing stage. A future discovery run may legitimately produce a different document count as the authoritative Policy Library changes.

## Corpus Processing

### Processing architecture

Corpus-wide processing is orchestrated by `ingestion/corpus_processor.py`.

The processor loads the current `data/corpus/corpus_manifest.json`, validates that it contains a document list and that the declared `document_count` matches the number of manifest records, then converts each discovered document into a processing input.

Each processing input retains:

- authoritative `document_id`;
- discovered policy title;
- document type;
- authoritative source URL;
- discovery source URL;
- deterministic output path based on `document_id`.

Processed corpus documents are written to:

`data/processed/corpus/<document_id>.json`

The corpus processor reuses the validated Sprint 3 `process_policy()` implementation in `ingestion/policy_processor.py`. The legacy `POLICIES` list retained in that module supports the original Sprint 3 execution path and does not define the Sprint 4 corpus. Sprint 4 corpus processing is driven by the dynamically generated corpus manifest.

### Authoritative retrieval and structured output

For each document, `process_policy()` retrieves the authoritative Policy Library document and verifies that the final response remains on the `policies.latrobe.edu.au` host.

The processor then:

1. parses the returned HTML;
2. extracts the authoritative document title;
3. retrieves status and currency metadata from the Policy Library Status and Details page;
4. locates the Policy Library document-content container;
5. captures the document heading hierarchy;
6. extracts and cleans document text;
7. writes the structured document as JSON.

The structured output preserves retrieval and provenance information including:

- `document_id`;
- `policy_title`;
- `document_type`;
- `source_url`;
- `discovery_source_url`;
- `status_details_url`;
- `source_system`;
- `retrieved_at`;
- `status`;
- `effective_date`;
- `review_date`;
- `approval_authority`;
- `approval_date`;
- `version`;
- heading hierarchy;
- cleaned document content.

This metadata is carried forward so later chunking, indexing and retrieval stages can retain authoritative document identity, provenance and currency information.

### Processing outcomes and failure isolation

Corpus processing isolates individual document outcomes so one unsuccessful document does not terminate the remaining corpus run.

Each attempted document is classified using the established processing terminology:

- `Processed` — the authoritative document was successfully retrieved, structured and written;
- `Access Restricted` — retrieval was redirected outside the public Policy Library and raised `AuthoritativeSourceAccessError`;
- `Failed` — another processing exception occurred.

`Access Restricted` is retained as a distinct processing outcome and is not treated as an exclusion.

For every attempted document, the run report preserves document identity, title, document type, source URL, discovery source URL, processing status, intended output path and any recorded error.

The completed processing report is written to:

`data/corpus/corpus_processing_report.json`

### Full-refresh output cleanup

A full corpus refresh clears existing processed corpus JSON files before processing the newly validated manifest.

`corpus_processor.main()` performs the refresh in this order:

1. load and validate the current corpus manifest;
2. build processing inputs from the validated manifest;
3. remove existing `data/processed/corpus/*.json` outputs;
4. process the current manifest documents;
5. save the new processing run report.

This ensures that processed JSON from an earlier corpus definition cannot survive a later full refresh and subsequently be chunked or re-indexed after the document has disappeared from authoritative discovery or can no longer be processed successfully.

The cleanup is deliberately performed by the full-run orchestration rather than inside the reusable `process_corpus()` helper, preserving support for controlled partial and test processing.

### Current processing outcome baseline

The current corpus processing run attempted all 215 documents in the committed manifest.

Recorded outcomes were:

- `Processed`: 214;
- `Access Restricted`: 1;
- `Failed`: 0.

The single access-restricted document is:

- `document_id`: `268`;
- title: `Investment Policy`;
- document type: `Policy`;
- source URL: `https://policies.latrobe.edu.au/document/view.php?id=268`;
- status: `Access Restricted`.

The processing report records that authoritative retrieval for document 268 was redirected outside the public Policy Library to `login.microsoftonline.com`, causing `AuthoritativeSourceAccessError`.

This document is therefore recorded as an access-restricted processing exception rather than a processing failure or an exclusion.

## Hierarchical Chunking

### Chunking implementation

Corpus chunking is implemented in `ingestion/policy_chunker.py`.

The chunker reads the successfully processed corpus documents from:

`data/processed/corpus/`

Processed documents are discovered from `*.json` files and handled in deterministic numeric `document_id` order.

Before a full chunk rebuild, existing chunk JSON files under:

`data/processed/chunks/`

are removed. This prevents stale or obsolete chunk artefacts from remaining after the processed corpus changes.

Each processed corpus document is converted into hierarchical chunks using the document heading structure captured during processing.

The chunker tracks the current heading hierarchy across:

- `h1` — section;
- `h2` — subsection;
- `h3` — topic;
- `h4` — subtopic.

Chunks are created from document content associated with the active heading hierarchy. Heading-only content is not emitted as a standalone chunk.

### Chunk metadata

Each chunk preserves the information required for later retrieval and source traceability, including:

- `chunk_id`;
- `document_id`;
- `policy_title`;
- `heading_level`;
- `section`;
- `subsection`;
- `topic`;
- `subtopic`;
- `paragraph_start`;
- `paragraph_end`;
- `source_url`;
- `status_details_url`;
- `status`;
- `effective_date`;
- `review_date`;
- `approval_authority`;
- `approval_date`;
- `version`;
- chunk text.

Chunk identifiers are deterministic within each document and use the form:

`<document_id>-<chunk_sequence>`

Where numbered policy paragraphs are present, the chunker also records the first and last paragraph numbers detected in the chunk.

### Current chunking baseline

The current processed corpus contains 214 successfully processed documents.

The current chunk output contains:

- 214 chunk files;
- 3,937 hierarchical chunks.

Each successfully processed document therefore has a corresponding chunk artefact in `data/processed/chunks/`.

## Embedding and Qdrant Indexing

### Embedding configuration

Embedding and indexing configuration is centralised in `ingestion/embedding_config.py` so the indexing and retrieval components use the same model and collection settings.

The current configuration uses:

- embedding model: `BAAI/bge-m3`;
- provider: `sentence-transformers`;
- dense embedding dimension: `1024`;
- distance metric: `Cosine`;
- maximum sequence length: `8192`;
- normalized embeddings: enabled.

The resolved embedding configuration can also be written to:

`data/processed/embedding_config.json`

This provides a reviewable record of the model and indexing settings used by the pipeline.

### Qdrant configuration

The default configuration uses embedded local Qdrant mode.

Current settings are:

- Qdrant mode: `local`;
- persistent storage path: `qdrant_storage`;
- collection name: `latrobe_policy_chunks`.

Local mode does not require a separately running Qdrant server or Docker instance.

The configuration also supports server mode through the configured Qdrant host and port where required.

### Indexing implementation

Indexing is implemented in `ingestion/qdrant_indexer.py`.

Chunk JSON files are loaded from:

`data/processed/chunks/`

For each chunk, the chunk text is embedded using BGE-M3 and the resulting vector is stored in Qdrant together with the configured chunk metadata payload.

The Qdrant payload preserves:

- chunk and document identity;
- policy title;
- heading hierarchy;
- paragraph range;
- source and status-detail URLs;
- policy status and currency metadata;
- approval metadata;
- version;
- chunk text.

Each `chunk_id` is deterministically mapped to a stable UUID. Re-indexing the same chunk therefore upserts the existing Qdrant point rather than creating a duplicate.

### Full index rebuild

A clean full re-index is performed with:

`python -m ingestion.qdrant_indexer --recreate`

The `--recreate` option deletes the existing `latrobe_policy_chunks` collection, recreates it using the configured 1024-dimensional cosine vector configuration, then embeds and indexes all available chunk files.

The indexer also supports controlled incremental operations:

- `--file FILE` — index a specified chunk file;
- `--replace-document DOCUMENT_ID` — remove existing points for one document before re-indexing it when chunk boundaries have changed.

### Current indexing baseline

The current chunk corpus contains 3,937 hierarchical chunks.

The validated Qdrant collection contains 3,937 indexed points, providing a one-to-one indexed representation of the current chunk corpus.

## Corpus Metrics, Reconciliation and Retrieval Validation

### Corpus metrics

The current Sprint 4 corpus baseline was recorded in:

`data/corpus/corpus_metrics.json`

The recorded metrics are:

- documents discovered: 215;
- documents processed: 214;
- documents access restricted: 1;
- documents failed: 0;
- total hierarchical chunks: 3,937;
- total vectors indexed in Qdrant: 3,937.

The Qdrant collection is:

`latrobe_policy_chunks`

These metrics confirm that all successfully processed corpus content has been chunked and indexed.

### Corpus reconciliation

Corpus completeness was reconciled in:

`data/corpus/corpus_reconciliation.json`

The reconciliation confirmed:

- 215 documents discovered;
- 214 documents chunked;
- 214 documents indexed;
- 1 document recorded as Access Restricted;
- no chunked-but-not-indexed documents;
- no indexed-but-not-chunked documents;
- no unexpected indexed documents.

The only discovered document not indexed is:

- document ID `268`;
- `Investment Policy`;
- outcome: `Access Restricted`.

The reconciliation status is recorded as:

`Reconciled`

This confirms that the difference between discovered and indexed document counts is fully explained by the documented access restriction rather than an ingestion or indexing failure.

### Representative retrieval validation

Representative retrieval checks were recorded in:

`data/corpus/corpus_retrieval_checks.json`

The validation used the established Sprint 3 retrieval configuration:

- Top K: `5`;
- minimum similarity score: `0.55`;
- current-policy filtering.

Six checks were executed:

- five representative expanded-corpus policy queries;
- one unsupported control query.

Results were:

- 5 of 6 checks passed overall;
- 4 of 5 representative expanded-corpus queries retrieved the expected policy within the Top 5;
- the unsupported weather query correctly returned the safe fallback with no evidence.

Successful expanded-corpus checks included:

- Travel Management Policy — expected policy ranked 1;
- Research Data Management Policy — expected policy ranked 3;
- Graduate Research Supervision Policy — expected policy ranked 1;
- Student Support Policy — expected policy ranked 1.

The Safe Driving query did not return the expected policy in the Top 5 and was investigated separately under COPL-290.

### Retrieval compatibility investigation

The COPL-289 Safe Driving mismatch was investigated and recorded in:

`data/corpus/retrieval_code_compatibility.json`

The investigation confirmed that document `321`, `Health and Safety Procedure - Safe Driving`, was:

- successfully processed into 16 chunks;
- fully indexed in Qdrant with 16 points;
- stored with `Current` status and valid payload content.

For the original broad query, the expected policy was not returned in the Top 5 or Top 20. However, three Safe Driving chunks scored above the `0.55` similarity threshold, with a best score of `0.581032`, but were outranked by other semantically related corpus content.

When the intended policy was explicitly identified in the query, the existing retrieval pipeline returned document 321 at ranks:

- 1;
- 2;
- 3;
- 5.

The best similarity score for the policy-specific query was `0.740699`.

The investigation concluded that the mismatch was caused by semantic ranking sensitivity for a broad query, not by:

- missing corpus content;
- processing failure;
- indexing failure;
- status filtering;
- or the configured similarity threshold.

No policy-specific retrieval-code changes were required to support the expanded corpus.

The existing retrieval pipeline is therefore compatible with newly indexed policies without requiring policy-specific retrieval logic.

Broader semantic ranking behaviour remains an evaluation concern for the later Sprint 4 retrieval-quality testing task and should not be tuned from this single example.

## Repeatable Corpus Refresh Procedure

The Sprint 4 corpus pipeline is designed to be rerun against the authoritative La Trobe University Policy Library without requiring policy-specific retrieval-code changes.

A full corpus refresh should be performed from the repository root with the project virtual environment active.

### Step 1 — Rediscover the authoritative corpus

Run:

`python -m ingestion.policy_discovery`

This queries the authoritative Policy Library Browse A-Z source and rebuilds the discovery artefacts:

- `data/corpus/corpus_manifest.json`;
- `data/corpus/corpus_inventory.csv`.

The discovery stage dynamically identifies Policy Library document links and uses the authoritative `document_id` as the stable document identity.

Because the Policy Library can change over time, the number of discovered documents in a future refresh may differ from the current 215-document baseline.

### Step 2 — Process the discovered corpus

Run:

`python -m ingestion.corpus_processor`

The processor:

1. loads and validates the current corpus manifest;
2. constructs processing inputs from the discovered corpus;
3. clears existing processed corpus JSON files;
4. retrieves and processes each currently discovered document;
5. isolates per-document processing outcomes;
6. writes the current successful processed outputs;
7. records the processing run report.

Processed documents are written to:

`data/processed/corpus/`

The processing report is written to:

`data/corpus/corpus_processing_report.json`

Possible processing outcomes are:

- `Processed`;
- `Access Restricted`;
- `Failed`.

Clearing the previous processed corpus before the full run prevents documents that are no longer present, or are no longer successfully accessible, from surviving as stale processed artefacts.

### Step 3 — Rebuild hierarchical chunks

Run:

`python -m ingestion.policy_chunker`

The chunking stage:

1. clears existing chunk JSON files;
2. discovers the current successfully processed corpus files;
3. processes them in deterministic document-ID order;
4. rebuilds hierarchical chunks;
5. writes the resulting chunk files to:

`data/processed/chunks/`

Because the chunk stage reads the current processed corpus rather than a fixed policy list, newly discovered and successfully processed policies are incorporated without policy-specific chunking changes.

### Step 4 — Rebuild the Qdrant collection

Run:

`python -m ingestion.qdrant_indexer --recreate`

The `--recreate` option performs a clean full rebuild of the configured Qdrant collection.

It:

1. deletes the existing `latrobe_policy_chunks` collection if present;
2. recreates the collection using the configured vector settings;
3. loads all current chunk files;
4. generates BGE-M3 embeddings;
5. indexes the current chunk corpus;
6. records the embedding/indexing configuration.

A clean collection rebuild prevents vectors belonging to removed or no-longer-processable documents from remaining in the active index.

BGE-M3 model startup and embedding can take noticeable time during this stage.

### Step 5 — Verify the rebuilt index

Run:

`python verify_index.py`

The verification utility checks the configured Qdrant collection and reports its indexed point count together with a sample stored payload.

The indexed vector count should reconcile with the current total chunk count.

### Step 6 — Reconcile corpus completeness

After the refresh, discovered, processed, chunked and indexed document counts should be reconciled.

Any difference between the authoritative discovered corpus and the indexed corpus must be explicitly explained by a recorded processing outcome such as `Access Restricted` or `Failed`.

Unexpected conditions requiring investigation include:

- a successfully processed document with no chunk artefact;
- a chunked document with no indexed points;
- indexed documents not represented by the current chunk corpus;
- unexpected indexed document IDs;
- unexplained differences between discovered and indexed document counts.

The current validated baseline is:

- discovered: 215;
- processed: 214;
- Access Restricted: 1;
- failed: 0;
- chunk files: 214;
- indexed documents: 214;
- chunks/vectors: 3,937.

These figures represent the current validated corpus only and should not be treated as permanently fixed expected values.

### Step 7 — Run representative retrieval validation

Run:

`python verify_corpus_retrieval.py`

Representative retrieval checks should confirm that:

- content from the expanded corpus can be retrieved;
- Current-policy filtering remains effective;
- the established Top-5 retrieval behaviour continues to operate;
- the current similarity threshold remains applied;
- unsupported questions continue to return the safe fallback.

Retrieval-quality findings should be recorded for the dedicated retrieval evaluation task rather than used to make ad hoc threshold or ranking changes during routine corpus refresh.

## Governance, Exceptions and Known Limitations

### Governance considerations

The corpus pipeline is intentionally anchored to the authoritative La Trobe University Policy Library rather than maintaining a manually curated policy list.

Key governance controls are:

- policy discovery begins from the authoritative Policy Library Browse A-Z source;
- the Policy Library `document_id` is retained as the stable document identity;
- source URLs are preserved through processing, chunking and indexing;
- policy status and available currency metadata are retained with the processed document and chunk payload;
- retrieval operates against indexed policy evidence rather than policy-specific hard-coded knowledge;
- corpus-processing outcomes are explicitly recorded rather than silently dropping inaccessible documents;
- discovered-versus-indexed completeness is reconciled so omissions can be explained;
- repeatable refresh uses clean processed, chunk and full-index rebuild stages to prevent stale corpus content from surviving into a new corpus state.

The pipeline processes content available through the authoritative source. It does not attempt to bypass authentication or access controls.

### Access-restricted document

Document `268`, `Investment Policy`, is the single known Access Restricted document in the current corpus baseline.

During processing, the authoritative Policy Library request redirected to:

`login.microsoftonline.com`

The processor correctly rejected the redirected host rather than treating authenticated or non-authoritative content as public policy source material.

The document is therefore recorded as:

`Access Restricted`

It is not classified as `Failed` or `Excluded`.

No successful processed artefact, chunk artefact or Qdrant index content is expected for document 268 under the current publicly accessible corpus workflow.

### Known limitations and deferred technical debt

The following findings are deliberately outside the scope of COPL-292 remediation.

#### Corpus inventory downstream statuses

`data/corpus/corpus_inventory.csv` is created during discovery with downstream processing, chunking and indexing states initially recorded as `Not run`.

The current downstream pipeline does not synchronise those inventory status fields after later processing and indexing stages.

Authoritative run outcomes are instead available from the processing, metrics and reconciliation artefacts.

Synchronising the inventory status fields is recorded separately as Sprint 4 technical debt and should not be implemented as an undocumented change within COPL-292.

#### Hard-coded corpus-size expectation in automated testing

An existing chunker test contains an expectation based on the current 214 successfully processed documents.

Because corpus size can change when the authoritative Policy Library changes, this fixed expectation is a maintainability issue and is recorded separately for technical-debt remediation.

The current 214-document value must not be treated as a permanent corpus-size requirement.

#### BGE-M3 startup latency

Loading `BAAI/bge-m3` can introduce noticeable startup latency for commands that initialise the embedding model.

This was observed during manual retrieval and indexer command execution.

Performance investigation or optimisation is a separate Sprint 4 technical-debt item and is not part of the corpus-documentation task.

#### Semantic ranking sensitivity

Representative retrieval testing identified ranking sensitivity for the broad Safe Driving query even though the intended document was correctly processed, indexed and capable of being retrieved with the existing pipeline.

This is a retrieval-quality evaluation concern rather than a corpus-ingestion defect.

Broader evaluation of ranking behaviour, Top K and similarity-threshold effectiveness belongs to the dedicated Sprint 4 retrieval-quality testing task. These settings should not be tuned from a single representative example.

### Current corpus baseline is a point-in-time state

The recorded values of 215 discovered documents, 214 processed/indexed documents and 3,937 chunks represent the validated Sprint 4 corpus at the time the metrics were recorded.

They are not permanent system constants.

Future authoritative Policy Library changes may legitimately alter:

- discovered document count;
- processing outcomes;
- chunk count;
- indexed vector count;
- policy status or currency information.

A future refresh should therefore be validated by reconciliation against that refresh's authoritative discovery and processing results rather than by forcing the corpus to match the current numerical baseline.

## Operational Handover

The Task 2 corpus capability is implemented through the following primary components:

- `ingestion/policy_discovery.py` — authoritative Policy Library discovery;
- `ingestion/corpus_processor.py` — corpus-wide policy processing and outcome reporting;
- `ingestion/policy_processor.py` — reusable policy retrieval and structured extraction;
- `ingestion/policy_chunker.py` — hierarchical chunk generation;
- `ingestion/embedding_config.py` — shared embedding and Qdrant configuration;
- `ingestion/qdrant_indexer.py` — embedding and Qdrant indexing;
- `verify_index.py` — index-count and payload verification;
- `verify_corpus_retrieval.py` — representative expanded-corpus retrieval verification.

Key corpus evidence artefacts include:

- `data/corpus/corpus_manifest.json`;
- `data/corpus/corpus_inventory.csv`;
- `data/corpus/corpus_processing_report.json`;
- `data/corpus/corpus_metrics.json`;
- `data/corpus/corpus_reconciliation.json`;
- `data/corpus/corpus_retrieval_checks.json`;
- `data/corpus/retrieval_code_compatibility.json`;
- `data/processed/embedding_config.json`.

Processed and chunked corpus artefacts are stored under:

- `data/processed/corpus/`;
- `data/processed/chunks/`.

The active vector collection is:

`latrobe_policy_chunks`

The Task 2 corpus pipeline is now documented as a repeatable sequence from authoritative discovery through processing, hierarchical chunking, BGE-M3 embedding, Qdrant indexing, reconciliation and representative retrieval verification.

Full project installation, environment configuration, React/Django/Ollama startup sequence and end-to-end prototype operation remain part of Sprint 4 integration and closeout documentation rather than COPL-292.
