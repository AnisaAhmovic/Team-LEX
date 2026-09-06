"""
Runs every question in retrieval_test_set.json through the retriever,
saves an audit record for each one, works out the Top 1 / Top 3 / Top 5
scores, and writes the Sprint 3 report.

Run from the repo root with the venv turned on:

    python tests/run_retrieval_tests.py --dry-run     just check the test set
    python tests/run_retrieval_tests.py               run everything
    python tests/run_retrieval_tests.py --compare tests/results/<a file>.json

IMPORTANT: close the Django server first. Qdrant is running inside Python
(QDRANT_MODE = "local") so only one program can open the qdrant_storage
folder at a time.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime

# Lets us import from the project when we run this file directly.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TEST_SET_FILE = os.path.join(ROOT, "tests", "retrieval_test_set.json")
RESULTS_FOLDER = os.path.join(ROOT, "tests", "results")
REPORT_FILE = os.path.join(ROOT, "docs", "SPRINT3_RETRIEVAL_TEST_REPORT.md")
CHUNKS_FOLDER = os.path.join(ROOT, "data", "processed", "chunks")

# Only these two categories have a right answer in the policies, so they are
# the only ones we can score Top 1 / Top 3 / Top 5 on. The unsupported and
# ambiguous questions get marked on what the system did instead.
ANSWERABLE = ["supported", "current_policy"]

# When we compare two runs, scores are allowed to move by this much before
# we call it a difference.
SCORE_TOLERANCE = 0.01


def setup_django():
    """Start Django so we can use the AuditLog model from a plain script."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
    import django
    django.setup()


def load_test_set():
    with open(TEST_SET_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_all_chunk_ids():
    """Every chunk id that is in the chunk files right now."""
    chunk_ids = []
    for file_name in sorted(os.listdir(CHUNKS_FOLDER)):
        if not file_name.endswith(".json"):
            continue
        with open(os.path.join(CHUNKS_FOLDER, file_name), encoding="utf-8") as f:
            for chunk in json.load(f):
                chunk_ids.append(chunk["chunk_id"])
    return chunk_ids


def check_test_set(questions):
    """
    Check the test set before we run it. The main thing this catches is
    someone re-running the chunker, which moves the chunk boundaries and
    makes all our expected chunk ids wrong.
    """
    problems = []
    all_chunk_ids = get_all_chunk_ids()

    if len(questions) < 10 or len(questions) > 15:
        problems.append("There are " + str(len(questions)) + " questions, we need 10 to 15.")

    ids_seen = []
    for question in questions:
        q_id = question["id"]

        if q_id in ids_seen:
            problems.append(q_id + " is used twice.")
        ids_seen.append(q_id)

        if question["question"].strip() == "":
            problems.append(q_id + " has no question text.")

        for chunk_id in question["expected_chunk_ids"]:
            if chunk_id not in all_chunk_ids:
                problems.append(q_id + ": chunk " + chunk_id + " is not in the chunk files any more.")

        if question["category"] in ANSWERABLE:
            if len(question["expected_chunk_ids"]) == 0:
                problems.append(q_id + " needs an expected chunk id.")

    return problems


def mark_question(question, results, outcome):
    """Work out Top 1 / Top 3 / Top 5 and whether this question passed."""
    chunk_ids = []
    document_ids = []
    for result in results:
        chunk_ids.append(result["chunk_id"])
        document_ids.append(result["document_id"])

    expected_chunks = question["expected_chunk_ids"]
    expected_documents = question["expected_document_ids"]

    def right_chunk_in_top(how_many):
        for chunk_id in chunk_ids[:how_many]:
            if chunk_id in expected_chunks:
                return True
        return False

    def right_policy_in_top(how_many):
        for document_id in document_ids[:how_many]:
            if document_id in expected_documents:
                return True
        return False

    # Did we hand back anything that isn't the current version of a policy?
    all_current = True
    for result in results:
        if result["status"] != "Current":
            all_current = False

    # How many of the policies we expected turned up in the top 3?
    policies_in_top3 = 0
    for document_id in expected_documents:
        if document_id in document_ids[:3]:
            policies_in_top3 = policies_in_top3 + 1

    marks = {
        "top1_chunk": right_chunk_in_top(1),
        "top3_chunk": right_chunk_in_top(3),
        "top5_chunk": right_chunk_in_top(5),
        "top1_policy": right_policy_in_top(1),
        "top3_policy": right_policy_in_top(3),
        "top5_policy": right_policy_in_top(5),
        "all_current": all_current,
    }

    # Each category passes for a different reason.
    category = question["category"]

    if category == "supported":
        rule = "right chunk in the top 3 and outcome is 'answered'"
        passed = marks["top3_chunk"] and outcome == "answered"

    elif category == "current_policy":
        rule = "right chunk in the top 3, outcome is 'answered', and everything returned says Current"
        passed = marks["top3_chunk"] and outcome == "answered" and all_current

    elif category == "superseded_policy":
        rule = "nothing returned has a status other than Current"
        passed = all_current

    elif category == "ambiguous":
        rule = "outcome is 'ambiguous', or the top 3 covers both policies"
        passed = outcome == "ambiguous" or policies_in_top3 >= 2

    elif category == "unsupported":
        rule = "outcome is 'unsupported' or 'no_results'"
        passed = outcome == "unsupported" or outcome == "no_results"

    else:
        rule = "unknown category"
        passed = False

    marks["rule"] = rule
    marks["passed"] = passed
    return marks


def tidy_up(evidence, rank):
    """
    Turn one piece of evidence from PolicyRetriever into the flat shape the
    marking and the report use. Mostly this just renames similarity_score to
    score and policy_text to text_snippet.
    """
    return {
        "rank": rank,
        "chunk_id": evidence.get("chunk_id"),
        "document_id": evidence.get("document_id"),
        "policy_title": evidence.get("policy_title"),
        "section": evidence.get("section"),
        "subsection": evidence.get("subsection"),
        "source_url": evidence.get("source_url"),
        "status_details_url": evidence.get("status_details_url"),
        "status": evidence.get("status"),
        "effective_date": evidence.get("effective_date"),
        "score": evidence.get("similarity_score"),
        "text_snippet": " ".join((evidence.get("policy_text") or "").split())[:400],
    }


def run_all(questions):
    """Ask every question and mark the answers."""
    # These are imported down here instead of at the top of the file because
    # api.audit uses the Django models, so setup_django() has to run first.
    from retrieval import QuestionValidationError, RetrievalUnavailableError
    from api.audit import AuditingPolicyRetriever, save_audit, work_out_outcome

    # One retriever for the whole run, so the model and the Qdrant connection
    # are only opened once.
    retriever = AuditingPolicyRetriever()

    rows = []

    for question in questions:
        print(question["id"] + "  " + question["question"][:60])

        start = time.time()
        error = ""
        try:
            result = retriever.retrieve(question["question"])
        except (QuestionValidationError, RetrievalUnavailableError) as e:
            # A question the retriever refuses is still a result we want to
            # record, so we don't stop the run.
            result = {"status": "fallback", "question": question["question"],
                      "evidence": [], "fallback_reason": type(e).__name__}
            error = str(e)
        time_taken = int((time.time() - start) * 1000)

        log = save_audit(
            question["question"],
            result,
            source="test",
            test_id=question["id"],
            time_taken_ms=time_taken,
            error=error,
            retriever=retriever,
        )

        outcome = log.outcome

        results = []
        rank = 1
        for evidence in result.get("evidence") or []:
            results.append(tidy_up(evidence, rank))
            rank = rank + 1

        marks = mark_question(question, results, outcome)

        top_score = None
        if len(results) > 0:
            top_score = results[0]["score"]

        if marks["passed"]:
            print("    PASS   outcome=" + outcome + "  top score=" + str(top_score))
        else:
            print("    FAIL   outcome=" + outcome + "  top score=" + str(top_score))

        rows.append({
            "id": question["id"],
            "category": question["category"],
            "question": question["question"],
            "expected_policy": question["expected_policy"],
            "expected_section": question["expected_section"],
            "expected_chunk_ids": question["expected_chunk_ids"],
            "expected_document_ids": question["expected_document_ids"],
            "expected_outcome": question["expected_outcome"],
            "outcome": outcome,
            "top_score": top_score,
            "time_taken_ms": time_taken,
            "audit_id": log.id,
            "config_summary": log.config_summary,
            "results": results,
            "marks": marks,
        })

    return rows


def work_out_totals(rows):
    """Add up the scores for the whole run."""
    # Only the answerable questions count towards Top 1 / 3 / 5.
    answerable = []
    for row in rows:
        if row["category"] in ANSWERABLE:
            answerable.append(row)

    def percent(name):
        if len(answerable) == 0:
            return 0
        got_it = 0
        for row in answerable:
            if row["marks"][name]:
                got_it = got_it + 1
        return round(got_it * 100.0 / len(answerable), 1)

    passed = 0
    for row in rows:
        if row["marks"]["passed"]:
            passed = passed + 1

    # How many passed in each category.
    by_category = {}
    for row in rows:
        category = row["category"]
        if category not in by_category:
            by_category[category] = {"passed": 0, "total": 0}
        by_category[category]["total"] = by_category[category]["total"] + 1
        if row["marks"]["passed"]:
            by_category[category]["passed"] = by_category[category]["passed"] + 1

    return {
        "total_questions": len(rows),
        "answerable_questions": len(answerable),
        "passed": passed,
        "failed": len(rows) - passed,
        "top1_chunk": percent("top1_chunk"),
        "top3_chunk": percent("top3_chunk"),
        "top5_chunk": percent("top5_chunk"),
        "top1_policy": percent("top1_policy"),
        "top3_policy": percent("top3_policy"),
        "top5_policy": percent("top5_policy"),
        "by_category": by_category,
    }


def get_failures(rows):
    """The questions that failed, ready to copy into Jira."""
    failures = []
    for row in rows:
        if row["marks"]["passed"]:
            continue

        if len(row["results"]) > 0:
            top = row["results"][0]
            what_happened = ("outcome was '" + row["outcome"] + "', the top result was "
                             + str(top["chunk_id"]) + " (" + str(top["policy_title"])
                             + ") with a score of " + str(top["score"]))
        else:
            what_happened = "outcome was '" + row["outcome"] + "' and nothing came back"

        if len(row["expected_chunk_ids"]) > 0:
            expected_text = "expected chunk(s): " + ", ".join(row["expected_chunk_ids"])
        else:
            expected_text = "there is no correct chunk, the system should not have answered"

        failures.append({
            "id": row["id"],
            "title": "[" + row["id"] + "] Retrieval failed - " + row["question"][:60],
            "category": row["category"],
            "question": row["question"],
            "expected": row["marks"]["rule"] + ". " + expected_text + ".",
            "actual": what_happened,
            "audit_id": row["audit_id"],
        })

    return failures


def save_results(rows, totals, failures, run_time):
    """Write the JSON and CSV evidence files."""
    if not os.path.exists(RESULTS_FOLDER):
        os.makedirs(RESULTS_FOLDER)

    stamp = run_time.strftime("%Y-%m-%d_%H-%M-%S")

    config_summary = ""
    if len(rows) > 0:
        config_summary = rows[0]["config_summary"]

    everything = {
        "run_time": run_time.strftime("%d/%m/%Y %H:%M:%S"),
        "config_summary": config_summary,
        "totals": totals,
        "rows": rows,
        "failures": failures,
    }

    json_file = os.path.join(RESULTS_FOLDER, "results_" + stamp + ".json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(everything, f, indent=2)

    csv_file = os.path.join(RESULTS_FOLDER, "results_" + stamp + ".csv")
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "category", "question", "expected policy", "expected section",
            "expected chunks", "expected outcome", "actual outcome", "top score",
            "top1 chunk", "top3 chunk", "top5 chunk",
            "top1 policy", "top3 policy", "top5 policy",
            "passed", "audit id",
        ])
        for row in rows:
            marks = row["marks"]
            writer.writerow([
                row["id"], row["category"], row["question"],
                row["expected_policy"] or "", row["expected_section"] or "",
                " ".join(row["expected_chunk_ids"]), row["expected_outcome"],
                row["outcome"], row["top_score"],
                marks["top1_chunk"], marks["top3_chunk"], marks["top5_chunk"],
                marks["top1_policy"], marks["top3_policy"], marks["top5_policy"],
                marks["passed"], row["audit_id"],
            ])

    return json_file, csv_file


def yes_or_no(value):
    if value:
        return "yes"
    return "no"


def write_report(rows, totals, failures, run_time, json_file, csv_file):
    """Write docs/SPRINT3_RETRIEVAL_TEST_REPORT.md."""
    lines = []

    config_summary = ""
    chunks_indexed = ""
    if len(rows) > 0:
        config_summary = rows[0]["config_summary"]
        # the config summary looks like: model stVERSION chunks=85 k=5 min=0.5 gap=0.03
        for part in config_summary.split(" "):
            if part.startswith("chunks="):
                chunks_indexed = part.replace("chunks=", "")

    lines.append("# Sprint 3 Retrieval Test Report - Lex AI")
    lines.append("")
    lines.append("This file is written by tests/run_retrieval_tests.py. Don't edit it by hand,")
    lines.append("run the tests again instead so the numbers still match the audit log.")
    lines.append("")

    lines.append("## 1. About this run")
    lines.append("")
    lines.append("| | |")
    lines.append("| --- | --- |")
    lines.append("| When it was run | " + run_time.strftime("%d/%m/%Y %H:%M:%S") + " (local time) |")
    lines.append("| Questions | " + str(totals["total_questions"]) + " |")
    lines.append("| Chunks indexed | " + str(chunks_indexed) + " |")
    lines.append("| Setup | `" + config_summary + "` |")
    lines.append("")
    lines.append("The setup line has the model, the sentence-transformers version, how many chunks")
    lines.append("were indexed, and the three retrieval settings. If someone else's run has a")
    lines.append("different setup line then their numbers can't be compared to these ones.")
    lines.append("")

    lines.append("## 2. Top 1, Top 3 and Top 5")
    lines.append("")
    lines.append("Worked out from the " + str(totals["answerable_questions"]) + " questions that actually have an answer in our")
    lines.append("policies. The unsupported and ambiguous questions have no correct chunk, so they")
    lines.append("are marked on behaviour in section 3 instead.")
    lines.append("")
    lines.append("| | Top 1 | Top 3 | Top 5 |")
    lines.append("| --- | --- | --- | --- |")
    lines.append("| Found the right chunk | " + str(totals["top1_chunk"]) + "% | "
                 + str(totals["top3_chunk"]) + "% | " + str(totals["top5_chunk"]) + "% |")
    lines.append("| Found the right policy | " + str(totals["top1_policy"]) + "% | "
                 + str(totals["top3_policy"]) + "% | " + str(totals["top5_policy"]) + "% |")
    lines.append("")

    lines.append("## 3. Results by category")
    lines.append("")
    lines.append("| Category | Passed | Total |")
    lines.append("| --- | --- | --- |")
    for category in sorted(totals["by_category"].keys()):
        counts = totals["by_category"][category]
        lines.append("| " + category + " | " + str(counts["passed"]) + " | " + str(counts["total"]) + " |")
    lines.append("")
    lines.append("**" + str(totals["passed"]) + " passed and " + str(totals["failed"])
                 + " failed out of " + str(totals["total_questions"]) + ".**")
    lines.append("")

    lines.append("## 4. Every question")
    lines.append("")
    lines.append("| ID | Category | Question | Expected | Outcome | Top score | Top 1 | Top 3 | Top 5 | Result |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        marks = row["marks"]

        expected = ""
        if row["expected_policy"]:
            expected = row["expected_policy"]
            if row["expected_section"]:
                expected = expected + ", " + row["expected_section"]
        else:
            expected = "not in our policies"

        if marks["passed"]:
            result = "PASS"
        else:
            result = "FAIL"

        lines.append("| " + row["id"] + " | " + row["category"] + " | " + row["question"][:55]
                     + " | " + expected + " | " + row["outcome"] + " | " + str(row["top_score"])
                     + " | " + yes_or_no(marks["top1_chunk"]) + " | " + yes_or_no(marks["top3_chunk"])
                     + " | " + yes_or_no(marks["top5_chunk"]) + " | " + result + " |")
    lines.append("")

    lines.append("## 5. What each question got back")
    lines.append("")
    for row in rows:
        lines.append("### " + row["id"] + " - " + row["question"])
        lines.append("")
        lines.append("Audit id " + str(row["audit_id"]) + ", outcome `" + row["outcome"]
                     + "`, took " + str(row["time_taken_ms"]) + " ms.")
        lines.append("")

        if len(row["results"]) == 0:
            lines.append("Nothing came back.")
            lines.append("")
            continue

        lines.append("| Rank | Chunk | Policy | Section | Status | Score | Link |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for result in row["results"]:
            section = result["section"] or ""
            if result["subsection"]:
                section = section + ", " + result["subsection"]
            lines.append("| " + str(result["rank"]) + " | " + str(result["chunk_id"]) + " | "
                         + str(result["policy_title"]) + " | " + section + " | "
                         + str(result["status"]) + " | " + str(result["score"]) + " | "
                         + str(result["source_url"]) + " |")
        lines.append("")

    lines.append("## 6. Failed tests")
    lines.append("")
    if len(failures) == 0:
        lines.append("Nothing failed in this run.")
        lines.append("")
    else:
        lines.append("Raise each of these as a Jira defect, or write it up as a limitation with")
        lines.append("a reason if the team decides not to fix it this sprint.")
        lines.append("")
        for failure in failures:
            lines.append("### " + failure["title"])
            lines.append("")
            lines.append("- Category: " + failure["category"])
            lines.append("- Question: " + failure["question"])
            lines.append("- Expected: " + failure["expected"])
            lines.append("- What happened: " + failure["actual"])
            lines.append("- Audit id: " + str(failure["audit_id"]))
            lines.append("- To reproduce: close the Django server, then run "
                         "`python tests/run_retrieval_tests.py` and look at " + failure["id"] + ".")
            lines.append("")

    lines.append("## 7. Limitations")
    lines.append("")
    lines.append("- **We have no superseded policies indexed.** Every chunk says `Current`, and")
    lines.append("  COPL-184's retriever filters on `status = Current` in the Qdrant query")
    lines.append("  anyway, so the superseded test (Q15) passes by construction. It proves the")
    lines.append("  system never hands back non-current content, but it cannot prove the system")
    lines.append("  understands policy versions. Testing that needs an older version ingested.")
    lines.append("- **The 0.55 similarity threshold comes from COPL-184, not from measurement.**")
    lines.append("  It decides every unsupported result above. Compare it against the real")
    lines.append("  scores in section 5 before treating these percentages as settled.")
    lines.append("- **Ambiguity is judged on policy title.** COPL-184's evidence does not carry")
    lines.append("  a document id in its public shape, so two chunks count as different policies")
    lines.append("  when their titles differ.")
    lines.append("- **We wrote our own expected answers.** Nobody outside the team checked them.")
    lines.append("")

    lines.append("## 8. Evidence files")
    lines.append("")
    lines.append("- Full results: `" + os.path.relpath(json_file, ROOT).replace("\\", "/") + "`")
    lines.append("- Spreadsheet: `" + os.path.relpath(csv_file, ROOT).replace("\\", "/") + "`")
    lines.append("- Audit log file: `data/audit/audit_log.jsonl`")
    lines.append("- Audit log database: `db.sqlite3`, tables `api_auditlog` and `api_auditchunk`")
    lines.append("- Test set: `tests/retrieval_test_set.json`")
    lines.append("")

    folder = os.path.dirname(REPORT_FILE)
    if not os.path.exists(folder):
        os.makedirs(folder)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def compare(old_file, rows):
    """
    Check that an older run gives the same answers on this computer.
    This is how another team member verifies our results.
    """
    with open(old_file, encoding="utf-8") as f:
        old = json.load(f)

    print("")
    print("Comparing with the run from " + old["run_time"])

    new_config = ""
    if len(rows) > 0:
        new_config = rows[0]["config_summary"]

    if old["config_summary"] != new_config:
        print("  The setups are different, so these two runs can't be compared:")
        print("    old: " + old["config_summary"])
        print("    new: " + new_config)
    else:
        print("  Same setup: " + new_config)

    # Put the old rows in a dictionary so we can look them up by id.
    old_rows = {}
    for row in old["rows"]:
        old_rows[row["id"]] = row

    differences = 0

    for row in rows:
        old_row = old_rows.get(row["id"])
        if old_row is None:
            print("  " + row["id"] + " wasn't in the old run.")
            differences = differences + 1
            continue

        if old_row["outcome"] != row["outcome"]:
            print("  " + row["id"] + ": outcome changed from " + old_row["outcome"]
                  + " to " + row["outcome"])
            differences = differences + 1

        if old_row["marks"]["passed"] != row["marks"]["passed"]:
            print("  " + row["id"] + ": pass/fail changed")
            differences = differences + 1

        # Check the scores for any chunk that turned up in both runs.
        old_scores = {}
        for result in old_row["results"]:
            old_scores[result["chunk_id"]] = result["score"]

        for result in row["results"]:
            if result["chunk_id"] in old_scores:
                difference = abs(old_scores[result["chunk_id"]] - result["score"])
                if difference > SCORE_TOLERANCE:
                    print("  " + row["id"] + ": the score for " + str(result["chunk_id"])
                          + " moved from " + str(old_scores[result["chunk_id"]])
                          + " to " + str(result["score"]))
                    differences = differences + 1

    if differences == 0:
        print("  Everything matched. The old results are verified.")
    else:
        print("  Found " + str(differences) + " difference(s).")


def main():
    dry_run = "--dry-run" in sys.argv

    compare_file = None
    if "--compare" in sys.argv:
        where = sys.argv.index("--compare")
        if where + 1 >= len(sys.argv):
            print("Please put a results file after --compare.")
            return 1
        compare_file = sys.argv[where + 1]

    test_set = load_test_set()
    questions = test_set["questions"]

    problems = check_test_set(questions)
    if len(problems) > 0:
        print("There are problems with the test set:")
        for problem in problems:
            print("  - " + problem)
        return 1

    print("Test set is OK, " + str(len(questions)) + " questions.")

    if dry_run:
        return 0

    setup_django()

    run_time = datetime.now()
    print("")
    print("Running the tests...")
    print("")

    rows = run_all(questions)
    totals = work_out_totals(rows)
    failures = get_failures(rows)
    json_file, csv_file = save_results(rows, totals, failures, run_time)
    write_report(rows, totals, failures, run_time, json_file, csv_file)

    print("")
    print("Passed " + str(totals["passed"]) + " out of " + str(totals["total_questions"]))
    print("Right chunk:  Top 1 " + str(totals["top1_chunk"]) + "%   Top 3 "
          + str(totals["top3_chunk"]) + "%   Top 5 " + str(totals["top5_chunk"]) + "%")
    print("Right policy: Top 1 " + str(totals["top1_policy"]) + "%   Top 3 "
          + str(totals["top3_policy"]) + "%   Top 5 " + str(totals["top5_policy"]) + "%")

    if len(failures) > 0:
        print("")
        print("Failed tests to raise in Jira:")
        for failure in failures:
            print("  - " + failure["title"])

    print("")
    print("Results: " + json_file)
    print("CSV:     " + csv_file)
    print("Report:  " + REPORT_FILE)

    if compare_file is not None:
        compare(compare_file, rows)

    return 0


if __name__ == "__main__":
    sys.exit(main())
