# S5-06 Policy currency and repeatable update workflow

## Purpose and scope

Validate that an updated policy becomes retrievable and obsolete content cannot
compete as Current evidence. This exercise reuses the existing policy processor,
hierarchical chunker, BGE-M3 embedder, Qdrant indexer CLI and PolicyRetriever.
No production pipeline changes or new application functionality are required.

Base: `92d4647445d42301f7ab44925da23a73008ab354`.
Requirements source: `!!Project Lex - Agile Project Workbook v1.0-3.xlsx`,
`Revised S5 backlog`, row 22, and `3. Requirements`.

## Test policy and controlled change

- Assessment Policy, document ID `216`.
- Source: https://policies.latrobe.edu.au/document/view.php?id=216
- Status: https://policies.latrobe.edu.au/document/status-and-details.php?id=216
- Capture time and exact HTML hashes: [source.json](../tests/fixtures/policy_currency/source.json).
- Original clause: “feedback on assessment tasks is timely, constructive, and formative;”
- Test clause: “S5-06 TEST REVISION ONLY: feedback on assessment tasks is provided within twelve working days through the subject learning platform;”
- Remove section 8 in the test copy, reducing eight chunks to seven. This tests
  deletion of an orphan chunk that a plain upsert would leave behind.

The changed clause and removed section are synthetic test data, not an actual
university revision. Captured HTML is replayed through `process_policy()` for
both versions. The original source URL and Current status are retained solely
to exercise the normal retrieval controls in an isolated test collection.
The source website, application corpus and application index are unchanged.
The parser reports `version: null`, so content hashes identify this test's two
states. No official version number is invented.

## Recorded results

**PASS**, 29 September 2026, 17:59:27 to 18:00:30 AEST (about 63 seconds,
excluding dependency installation, source capture and first model download).
All 25 harness checks passed using real BGE-M3 on CPU, 1024 dimensions, cosine
similarity, top five candidates and the unchanged 0.55 threshold.

Evidence: [result.json](evidence/S5-06/semantic-run/result.json),
[console log](evidence/S5-06/semantic-run/console.log),
[baseline chunks](evidence/S5-06/semantic-run/baseline_chunks.json), and
[revised chunks](evidence/S5-06/semantic-run/revised_chunks.json).

| Subtask | Observed result |
| --- | --- |
| Select test policy | Assessment Policy, document 216, live public source captured and hashed. |
| Record baseline | Eight chunks. Original feedback clause retrieved at rank 1, score 0.642565. |
| Introduce controlled revision/update | Synthetic feedback clause and removal of section 8 recorded in revision HTML. |
| Reprocess | Both HTML states passed through the existing processor. |
| Re-chunk | Existing chunker produced seven revised chunks. |
| Re-embed/re-index | Existing CLI embedded and indexed both states with real BGE-M3. |
| Control obsolete evidence | All document 216 points replaced. Removed chunk 216-8 was absent. A separate control document was unchanged. |
| Retrieve revised content | Revised feedback clause retrieved at rank 1, score 0.650709, with original citation URL and Current status. |
| Verify obsolete content cannot compete as Current | Superseded, Archived and missing-status probe records ranked first without filtering but were absent from all Current retrieval candidates. |
| Record procedure/results | This procedure and machine-readable results include hashes, versions, counts and retrieval traces. |

Repeated replacement and a plain rerun of the unchanged revision preserved the
same eight stored points: seven policy chunks plus one control document. Reopening
the embedded database retained the revised evidence and status filtering.
The temporary database was removed after verification.

The [focused regression run](evidence/S5-06/focused-regression.log) passed 24 tests:

```bash
python -m unittest tests.test_policy_chunker.PolicyChunkingTests tests.test_policy_chunker.ChunkOutputTests tests.test_qdrant_indexer tests.test_policy_retriever tests.test_retrieval_qdrant tests.test_corpus_processor -v
```

An [initial broader run](evidence/S5-06/initial-regression.log) passed 26 tests and
failed the full-corpus discovery count assertion because this validation workspace
contained one policy fixture rather than all 214 processed policies. That is an
explicit coverage limitation, not a full-suite pass. The focused command excludes
that corpus inventory class. Full-corpus acceptance remains with the existing
corpus reconciliation evidence and is not claimed by S5-06.

## Reproduce the validation

Use the repository's Python environment with its base and embedding dependencies.
`requests` must also be installed because the existing processor imports it.

```bash
python -m pip install -r requirements.txt -r requirements-embeddings.txt requests
python verify_policy_currency.py --output /tmp/lex-s5-06-validation
```

Use a new output directory on each run. Existing evidence is never overwritten.
The first semantic run downloads BGE-M3. Later runs can use the cached model.
The test uses a temporary embedded Qdrant database and deletes it after closing.
It never opens the application's `qdrant_storage` directory. Saved evidence
includes processed baseline/revision, chunks, synthetic revision HTML, retrieval
results, configuration, package versions, hashes and individual check results.

For a quick controls test without downloading BGE-M3:

```bash
python verify_policy_currency.py --controls-only --output /tmp/lex-s5-06-controls
```

This uses fixed vectors and reports `PASS_CONTROLS_ONLY`. It does not establish
semantic retrieval or BGE-M3 re-embedding. The semantic run is the DoD evidence.

## Procedure for an actual authorised policy update

1. Confirm the document ID, canonical current policy URL and status/details page.
   Do not use a historical `version=` URL with metadata from the current version.
   Record the baseline query, returned text and metadata, chunk IDs/counts,
   retrieval time and content hashes. Confirm that use of the source is authorised.
2. Schedule a maintenance window. Stop Django and any process holding the embedded
   Qdrant database. Back up the closed database, processed policy JSON, chunk file
   and configuration to a separate directory. Keep the baseline retrieval record.
3. Stage the current policy outside the default corpus/chunk directories. Run the
   existing processor and chunker for the one document. For example:

```python
import json
from pathlib import Path
from ingestion.policy_processor import process_policy
from ingestion.policy_chunker import chunk_policy

stage = Path('/tmp/lex-policy-216-update')
stage.mkdir(exist_ok=False)
policy = process_policy(
    document_id='216',
    policy_url='https://policies.latrobe.edu.au/document/view.php?id=216',
    output_file=str(stage / '216.json'),
    document_type='Policy',
    discovery_source_url='https://policies.latrobe.edu.au/browse',
)
if policy['status'] != 'Current':
    raise ValueError('Do not promote a non-current policy.')
chunks = chunk_policy(policy)
if not chunks or any(c['document_id'] != '216' for c in chunks):
    raise ValueError('Invalid or empty replacement chunks.')
(stage / '216_chunks.json').write_text(
    json.dumps(chunks, ensure_ascii=False, indent=2), encoding='utf-8'
)
```

4. Inspect the staged source, status, content, headings and chunk metadata.
   Confirm the updated clause is present and obsolete text is absent. Ensure
   BGE-M3 is installed/cached before the destructive replacement stage.
5. Replace the complete document, specifying both arguments:

```bash
python -m ingestion.qdrant_indexer --file /tmp/lex-policy-216-update/216_chunks.json --replace-document 216
```

   `--file` limits input to the staged revision. `--replace-document` removes all
   existing points with that document ID before re-embedding and inserting the
   new chunks. Plain upsert alone is insufficient when a revision has fewer
   chunks. Do not use `--recreate` for a single-policy update.
6. Inspect every stored point for document `216`, comparing IDs, count, text and
   status with the staged chunk file. Check that removed IDs and old clause text
   are absent. Verify a separate document is unchanged. Run the baseline question
   through a fresh retriever and record the revised evidence, citation and score.
7. Repeat the index command and confirm stable counts and payloads. The S5-06
   harness also checks that Superseded, Archived and missing-status records cannot
   enter the Current candidate set, even with exact-query vectors.
8. After successful checks, replace the matching maintained files
   `data/processed/corpus/216.json` and `data/processed/chunks/216_chunks.json`
   with the approved staged outputs. Archive old inputs outside all ingestion
   directories so a later full rebuild cannot reintroduce them. Record hashes,
   source retrieval time, operator, results and any exceptions.
9. Restart the backend to refresh its cached title/heading catalogue. Repeat the
   user query through the application before ending the maintenance window.

For withdrawn or superseded documents with no current replacement, remove their
points using `delete_document()` and remove/archive their input files outside the
active corpus. Do not relabel obsolete text as Current. Resolve an inaccessible
source with the policy owner and record the decision rather than claiming it was
refreshed. Follow the existing full-corpus discovery/reconciliation procedure in
[COPL-292](COPL-292_CORPUS_PROCESSING_AND_REFRESH.md) for corpus-wide changes.

### Failure and recovery

Replacement is delete-then-insert, not an atomic transaction. A failed embedding
or insertion can leave the target policy absent or partially indexed. Keep the
application stopped. Resolve the failure and rerun the validated replacement,
then inspect all target records again. Retain the staged approved revision for
this purpose. A database backup can restore a consistent prior state, but must
not be served as Current if its policy is known to be obsolete. Resolve that
currency decision before reopening the application.

## Requirements coverage and limits

| Requirement | Evidence and scope |
| --- | --- |
| FR2 | Existing processor extracts baseline and revised HTML for one representative policy. |
| FR3 | Existing chunker produces searchable units and the existing indexer embeds/indexes both states. |
| FR13 | Reuses the corpus-compatible processing interfaces. This test does not revalidate the complete corpus. |
| FR20 | Document replacement, re-indexing and repeat execution are demonstrated. |
| NFR8 | Public authoritative policy capture with URL/hash provenance, synthetic change confined to the test index. This is not a new governance approval. |
| NFR12 | Existing pipeline functions and CLI perform the update without redevelopment. |
| NFR14 | Revised evidence is retrieved and old evidence excluded after re-indexing. Runtime is recorded, but no full-corpus update SLA is established. |

The test validates one controlled revision with real BGE-M3 and embedded Qdrant.
It does not validate Qdrant server mode, concurrent production updates, generated
answers, full-corpus completeness, or an actual change published by the university.
Currency is a point-in-time source check. The existing processor leaves version
unset and the index payload does not retain source retrieval timestamps or content
hashes. The evidence bundle supplies these for this validation run.
