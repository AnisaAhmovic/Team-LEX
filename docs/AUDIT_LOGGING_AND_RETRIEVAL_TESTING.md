# Audit Logging and Retrieval Testing

How to set up the audit log, run the retrieval tests, and check someone
else's results.

Rename this file with the Jira ticket number when we have it, so it matches
`COPL-183_EMBEDDING_AND_INDEXING_SETUP.md` and `COPL-184_POLICY_RETRIEVAL.md`.

---

## 1. What this adds, and what it doesn't

**This does not do the searching.** COPL-184's `retrieval/policy_retriever.py`
does that. This work wraps it, records what it did, and tests how well it does it.

| File | What it does |
| --- | --- |
| `api/models.py` | The two audit tables: `AuditLog` and `AuditChunk`. |
| `api/audit.py` | `save_audit()` writes a search to the database and to a file. Also holds `AuditingPolicyRetriever`. |
| `api/views.py` | COPL-184's `policy_evidence` view, with audit logging added around it. |
| `api/admin.py` | Lets you look at the audit log in the Django admin site. |
| `tests/retrieval_test_set.json` | The 15 test questions and their expected answers. |
| `tests/run_retrieval_tests.py` | Runs the tests, works out Top 1/3/5, writes the report. |

### Why AuditingPolicyRetriever exists

COPL-184's retriever returns only five fields per piece of evidence:
`policy_text`, `policy_title`, `section`, `source_url` and `similarity_score`.
Its test at `tests/test_policy_retriever.py:76` checks that key set exactly, so
adding fields to it would break that test.

The audit log has to record **chunk identifiers**, so `AuditingPolicyRetriever`
subclasses `PolicyRetriever` and puts `chunk_id`, `document_id`, `subsection`,
`status`, `effective_date` and `status_details_url` back on. The API view then
strips those extra fields off again with `public_evidence()` before replying, so
the `/api/retrieve/` response shape is exactly what COPL-184 built. The only
addition is an `audit_id`, so a reply can be traced back to its audit record.

### Settings that change results

| Setting | Where | Value |
| --- | --- | --- |
| Similarity threshold | `retrieval/policy_retriever.py` (COPL-184) | `0.55` |
| Results per question | `retrieval/policy_retriever.py` (COPL-184) | `5` |
| Ambiguity gap | `api/audit.py` | `0.03` |

Change any of these and the config summary changes, which means old test
results can't be compared to new ones.

---

## 2. What goes in the audit log

Every search saves one `AuditLog` row plus one `AuditChunk` row per chunk:

- the question and the time it was asked
- the chunk ids that came back
- the policy links (`source_url` and `status_details_url`)
- the status and effective date of each chunk
- the similarity score of each chunk
- our outcome (`answered`, `unsupported`, `ambiguous` or `error`) plus what the
  retriever itself said (`supported` / `fallback`, and the fallback reason)
- the model name and the sentence-transformers version
- the retrieval settings, plus a short config summary line

Saved in two places:

- **`db.sqlite3`** so we can query it and browse it in the admin site
- **`data/audit/audit_log.jsonl`**, one line of JSON per search, so it can go on
  a Jira ticket without sending anyone a database file

Failed searches are logged too. A search missing from the log is a hole in the trail.

---

## 3. Setting it up

### 3.1 Before you start

- `docs/SETUP.md` done (venv, `.env`, `python manage.py migrate`)
- `docs/COPL-183_EMBEDDING_AND_INDEXING_SETUP.md` done (the index built)
- **Python 3.10, 3.11 or 3.12.** `sentence-transformers==3.3.1` doesn't install
  properly on 3.13 or newer.

### 3.2 Install

```bash
pip install -r requirements.txt -r requirements-embeddings.txt
```

The first run downloads BGE-M3, about 2.2 GB. Once per computer.

### 3.3 Build the index

```bash
python -m ingestion.qdrant_indexer --recreate
```

Then `python verify_index.py`. It should say **85 points**. A different number
means your results won't match anyone else's.

### 3.4 Make the audit tables

```bash
python manage.py makemigrations api
```

Then `python manage.py migrate`. **Commit the generated migration file**,
otherwise nobody else gets the tables.

If you already had an older version of these models, Django may say
"No migrations to apply" while the tables are still the old shape. Fix it with
`python manage.py migrate api zero` then `python manage.py migrate api`.

### 3.5 Check the test set

```bash
python tests/run_retrieval_tests.py --dry-run
```

Should say `Test set is OK, 15 questions.` It doesn't load the model or open
Qdrant, so it's quick. It fails if the chunker was re-run and the chunk ids moved.

---

## 4. Running the tests

**Close the Django server first.** Qdrant runs inside Python and locks the
`qdrant_storage` folder, so only one program can use it at a time.

```bash
python tests/run_retrieval_tests.py
```

You get:

| File | What's in it |
| --- | --- |
| `tests/results/results_<date>.json` | Everything: evidence, scores, links, audit ids |
| `tests/results/results_<date>.csv` | One row per question, opens in Excel |
| `docs/SPRINT3_RETRIEVAL_TEST_REPORT.md` | The report, rewritten every run |
| `data/audit/audit_log.jsonl` | Added to, not overwritten |
| `db.sqlite3` | 15 new audit rows |

Also run the existing suite to check nothing broke:

```bash
python manage.py test api tests.test_policy_retriever
```

---

## 5. How the marking works

**Top 1 / Top 3 / Top 5** is only worked out on the 10 questions that have an
answer in our policies (9 `supported` plus 1 `current_policy`). The unsupported
and ambiguous questions have no correct chunk, so they're marked on behaviour.

Two versions of the score:

- **right chunk** — was the exact expected chunk in the top 1 / 3 / 5?
- **right policy** — was the right policy there? Easier to pass.

How each category passes:

| Category | Passes when |
| --- | --- |
| `supported` | right chunk in the top 3 and outcome is `answered` |
| `current_policy` | same, and everything returned says `Current` |
| `superseded_policy` | nothing returned has a status other than `Current` |
| `ambiguous` | outcome is `ambiguous`, or the top 3 covers both policies |
| `unsupported` | outcome is `unsupported` |

Note that COPL-184's retriever already filters on `status = Current` inside the
Qdrant query, so the `superseded_policy` test passes by construction. See the
limitations in the report.

---

## 6. Failed tests

Every failure is written into section 6 of the report with the question, what we
expected, what happened, and the audit id for that exact search.

For each one, either raise a **Jira defect** and paste that block in, or write it
up as a **limitation** in the report with the reason we're not fixing it now.

Don't lower the threshold to make tests go green. If it changes, say so in the
report and re-run. The config summary will change, which is how everyone knows
the two runs aren't comparable.

---

## 7. Checking someone else's results

1. Pull the branch and do section 3 on your own computer.
2. Run `python verify_index.py` and check you get the same chunk count.
3. Run:

```bash
python tests/run_retrieval_tests.py --compare tests/results/<their file>.json
```

It reports config drift, any changed outcome, any pass/fail flip, and any score
that moved by more than 0.01. `Everything matched. The old results are verified.`
means it worked.

Embeddings are deterministic for the same question and model, so a same-config
run should match. A difference usually means a different chunk count, a different
model version, or someone changed the threshold.

---

## 8. Looking at the audit log

In the admin site (`/admin/`, needs `python manage.py createsuperuser`) you can
filter by outcome, source and config summary, with the chunks shown inline.

```bash
python manage.py shell
```

```python
from api.models import AuditLog

# how many times the system refused to answer
AuditLog.objects.filter(outcome="unsupported").count()

# one search, start to finish. Use filter().first() rather than get(), because
# every time you run the tests you add another row for the same question.
log = AuditLog.objects.filter(test_id="Q04").first()
for chunk in log.chunks.all():
    print(chunk.rank, chunk.score, chunk.chunk_id, chunk.source_url)
```

Straight out of the file, no database needed:

```bash
python -c "import json; [print(json.loads(line)['outcome'], json.loads(line)['question'][:50]) for line in open('data/audit/audit_log.jsonl', encoding='utf-8')]"
```

---

## 9. If something goes wrong

| What you see | Why | What to do |
| --- | --- | --- |
| `Storage folder qdrant_storage is already accessed by another instance` | The Django server has Qdrant open | Close it, or use `QDRANT_MODE = "server"` with `docker-compose.qdrant.yml` |
| `no such table: api_auditlog` | Migrations not run | `python manage.py makemigrations api` then `migrate` |
| `table api_auditlog has no column named ...` | Old migration still recorded as applied | `python manage.py migrate api zero` then `python manage.py migrate api` |
| `chunk 363-11 is not in the chunk files any more` | Chunker was re-run and ids moved | Fix the expected ids in `tests/retrieval_test_set.json` |
| Everything comes back `unsupported` | The 0.55 threshold is too high for the real scores | Look at section 5 of the report and discuss it with whoever owns COPL-184 |
| First run sits there for ages | BGE-M3 is downloading | Wait, it only happens once |
| `verify_index.py` says 0 points | Index not built, or wrong folder | `python -m ingestion.qdrant_indexer --recreate` from the repo root |

---

## 10. Already in .gitignore

```
data/audit/
tests/results/
```

To attach one particular results file to a ticket, add just that one with
`git add -f`.
