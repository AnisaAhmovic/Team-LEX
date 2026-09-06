# Sprint 3 Retrieval Test Report - Lex AI

This file is written by tests/run_retrieval_tests.py. Don't edit it by hand,
run the tests again instead so the numbers still match the audit log.

## 1. About this run

| | |
| --- | --- |
| When it was run | 06/09/2026 17:15:53 (local time) |
| Questions | 15 |
| Chunks indexed | 85 |
| Setup | `BAAI/bge-m3 st3.3.1 chunks=85 k=5 min=0.55 gap=0.03` |

The setup line has the model, the sentence-transformers version, how many chunks
were indexed, and the three retrieval settings. If someone else's run has a
different setup line then their numbers can't be compared to these ones.

## 2. Top 1, Top 3 and Top 5

Worked out from the 10 questions that actually have an answer in our
policies. The unsupported and ambiguous questions have no correct chunk, so they
are marked on behaviour in section 3 instead.

| | Top 1 | Top 3 | Top 5 |
| --- | --- | --- | --- |
| Found the right chunk | 80.0% | 80.0% | 90.0% |
| Found the right policy | 90.0% | 90.0% | 90.0% |

## 3. Results by category

| Category | Passed | Total |
| --- | --- | --- |
| ambiguous | 1 | 2 |
| current_policy | 0 | 1 |
| superseded_policy | 1 | 1 |
| supported | 8 | 9 |
| unsupported | 2 | 2 |

**12 passed and 3 failed out of 15.**

## 4. Every question

| ID | Category | Question | Expected | Outcome | Top score | Top 1 | Top 3 | Top 5 | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q01 | supported | What is the maximum percentage of a subject's final gra | Assessment Standards, Section 6 - Standards | answered | 0.724895 | yes | yes | yes | PASS |
| Q02 | supported | By what time on the due date do assignments have to be  | Assessment Standards, Section 6 - Standards | answered | 0.697128 | yes | yes | yes | PASS |
| Q03 | supported | Is attendance at classes mandatory, and when can attend | Assessment Standards, Section 6 - Standards | answered | 0.699572 | yes | yes | yes | PASS |
| Q04 | supported | How do I make a privacy complaint to the University? | Privacy Policy, Section 6 - Procedures | answered | 0.739196 | yes | yes | yes | PASS |
| Q05 | supported | What should a staff member do if they receive a court s | Privacy Policy, Section 6 - Procedures | answered | 0.605919 | yes | yes | yes | PASS |
| Q06 | supported | Can the University give a student's results or personal | Privacy Policy, Section 6 - Procedures | answered | 0.658102 | yes | yes | yes | PASS |
| Q07 | supported | How long does the Student Complaints Office have to tel | Student Complaints Management Policy, Section 6 - Procedures | answered | 0.77863 | yes | yes | yes | PASS |
| Q08 | supported | What can I do if I am unhappy with the outcome of my st | Student Complaints Management Policy, Section 6 - Procedures | answered | 0.704143 | yes | yes | yes | PASS |
| Q09 | supported | Who approves high risk AI use cases at La Trobe? | Responsible AI Adoption Policy, Section 4 - Key Decisions | answered | 0.662059 | no | no | yes | FAIL |
| Q10 | ambiguous | Who oversees assessment? | not in our policies | ambiguous | 0.574157 | no | no | no | PASS |
| Q11 | ambiguous | What are the rules about using AI? | not in our policies | answered | 0.669968 | yes | yes | yes | FAIL |
| Q12 | unsupported | How much does a Bundoora campus parking permit cost? | not in our policies | unsupported | None | no | no | no | PASS |
| Q13 | unsupported | What are the library opening hours during the exam peri | not in our policies | unsupported | None | no | no | no | PASS |
| Q14 | current_policy | What is the current Privacy Policy and when did it take | Privacy Policy, Section 1 - Key Information | unsupported | None | no | no | no | FAIL |
| Q15 | superseded_policy | What did the previous version of the Student Complaints | Student Complaints Management Policy, Section 6 - Procedures | answered | 0.690228 | yes | yes | yes | PASS |

## 5. What each question got back

### Q01 - What is the maximum percentage of a subject's final grade that group assessment can make up?

Audit id 1, outcome `answered`, took 16536 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 363-11 | Assessment Standards | Section 6 - Standards, Part F - Group Assessment Tasks | Current | 0.724895 | https://policies.latrobe.edu.au/document/view.php?id=363 |
| 2 | 363-10 | Assessment Standards | Section 6 - Standards, Part E - Timing and Weighting of Assessment | Current | 0.582174 | https://policies.latrobe.edu.au/document/view.php?id=363 |

### Q02 - By what time on the due date do assignments have to be submitted?

Audit id 2, outcome `answered`, took 208 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 363-15 | Assessment Standards | Section 6 - Standards, Part I - Submission of Assessment Tasks | Current | 0.697128 | https://policies.latrobe.edu.au/document/view.php?id=363 |
| 2 | 363-10 | Assessment Standards | Section 6 - Standards, Part E - Timing and Weighting of Assessment | Current | 0.575094 | https://policies.latrobe.edu.au/document/view.php?id=363 |
| 3 | 160-13 | Student Complaints Management Policy | Section 6 - Procedures, Part E - Outcomes of Complaints | Current | 0.561976 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 4 | 363-8 | Assessment Standards | Section 6 - Standards, Part C - Information to Students | Current | 0.552749 | https://policies.latrobe.edu.au/document/view.php?id=363 |

### Q03 - Is attendance at classes mandatory, and when can attendance be assessed?

Audit id 3, outcome `answered`, took 207 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 363-12 | Assessment Standards | Section 6 - Standards, Part G - Assessment of Attendance | Current | 0.699572 | https://policies.latrobe.edu.au/document/view.php?id=363 |
| 2 | 363-8 | Assessment Standards | Section 6 - Standards, Part C - Information to Students | Current | 0.572428 | https://policies.latrobe.edu.au/document/view.php?id=363 |
| 3 | 363-10 | Assessment Standards | Section 6 - Standards, Part E - Timing and Weighting of Assessment | Current | 0.563868 | https://policies.latrobe.edu.au/document/view.php?id=363 |

### Q04 - How do I make a privacy complaint to the University?

Audit id 4, outcome `answered`, took 283 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-30 | Privacy Policy | Section 6 - Procedures, Part I - Complaints | Current | 0.739196 | https://policies.latrobe.edu.au/document/view.php?id=1 |
| 2 | 160-6 | Student Complaints Management Policy | Section 5 - Policy Statement | Current | 0.679435 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 3 | 160-10 | Student Complaints Management Policy | Section 6 - Procedures, Part C - Submitting a Formal Complaint | Current | 0.676818 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 4 | 160-15 | Student Complaints Management Policy | Section 6 - Procedures, Part F - Review of Complaint Outcomes | Current | 0.67203 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 5 | 1-24 | Privacy Policy | Section 6 - Procedures, Part D - Access to and Correction of Personal Information | Current | 0.650077 | https://policies.latrobe.edu.au/document/view.php?id=1 |

### Q05 - What should a staff member do if they receive a court subpoena or a warrant?

Audit id 5, outcome `answered`, took 197 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-20 | Privacy Policy | Section 6 - Procedures, Part B - Use and Disclosure | Current | 0.605919 | https://policies.latrobe.edu.au/document/view.php?id=1 |
| 2 | 1-18 | Privacy Policy | Section 6 - Procedures, Part B - Use and Disclosure | Current | 0.557294 | https://policies.latrobe.edu.au/document/view.php?id=1 |

### Q06 - Can the University give a student's results or personal information to their parents?

Audit id 6, outcome `answered`, took 204 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-17 | Privacy Policy | Section 6 - Procedures, Part B - Use and Disclosure | Current | 0.658102 | https://policies.latrobe.edu.au/document/view.php?id=1 |
| 2 | 1-15 | Privacy Policy | Section 6 - Procedures, Part B - Use and Disclosure | Current | 0.578315 | https://policies.latrobe.edu.au/document/view.php?id=1 |
| 3 | 1-14 | Privacy Policy | Section 6 - Procedures, Part A - Collection of Personal and/or Health Information | Current | 0.573078 | https://policies.latrobe.edu.au/document/view.php?id=1 |
| 4 | 1-21 | Privacy Policy | Section 6 - Procedures, Part C - Data Quality and Security of Personal Information | Current | 0.569875 | https://policies.latrobe.edu.au/document/view.php?id=1 |
| 5 | 1-13 | Privacy Policy | Section 6 - Procedures, Part A - Collection of Personal and/or Health Information | Current | 0.560969 | https://policies.latrobe.edu.au/document/view.php?id=1 |

### Q07 - How long does the Student Complaints Office have to tell me the outcome of my complaint?

Audit id 7, outcome `answered`, took 207 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 160-14 | Student Complaints Management Policy | Section 6 - Procedures, Part E - Outcomes of Complaints | Current | 0.77863 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 2 | 160-13 | Student Complaints Management Policy | Section 6 - Procedures, Part E - Outcomes of Complaints | Current | 0.724103 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 3 | 160-11 | Student Complaints Management Policy | Section 6 - Procedures, Part D - Complaint Investigation | Current | 0.694537 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 4 | 160-10 | Student Complaints Management Policy | Section 6 - Procedures, Part C - Submitting a Formal Complaint | Current | 0.681419 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 5 | 160-17 | Student Complaints Management Policy | Section 6 - Procedures, Part H - Recording and Reporting of Complaints | Current | 0.658907 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |

### Q08 - What can I do if I am unhappy with the outcome of my student complaint?

Audit id 8, outcome `answered`, took 222 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 160-15 | Student Complaints Management Policy | Section 6 - Procedures, Part F - Review of Complaint Outcomes | Current | 0.704143 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 2 | 160-14 | Student Complaints Management Policy | Section 6 - Procedures, Part E - Outcomes of Complaints | Current | 0.698293 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 3 | 160-10 | Student Complaints Management Policy | Section 6 - Procedures, Part C - Submitting a Formal Complaint | Current | 0.689466 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 4 | 160-13 | Student Complaints Management Policy | Section 6 - Procedures, Part E - Outcomes of Complaints | Current | 0.688356 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 5 | 160-11 | Student Complaints Management Policy | Section 6 - Procedures, Part D - Complaint Investigation | Current | 0.688324 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |

### Q09 - Who approves high risk AI use cases at La Trobe?

Audit id 9, outcome `answered`, took 277 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 417-6 | Responsible AI Adoption Policy | Section 6 - Procedures | Current | 0.662059 | https://policies.latrobe.edu.au/document/view.php?id=417 |
| 2 | 417-5 | Responsible AI Adoption Policy | Section 5 - Policy Statement | Current | 0.649742 | https://policies.latrobe.edu.au/document/view.php?id=417 |
| 3 | 417-2 | Responsible AI Adoption Policy | Section 2 - Purpose | Current | 0.621851 | https://policies.latrobe.edu.au/document/view.php?id=417 |
| 4 | 417-4 | Responsible AI Adoption Policy | Section 4 - Key Decisions | Current | 0.560726 | https://policies.latrobe.edu.au/document/view.php?id=417 |

### Q10 - Who oversees assessment?

Audit id 10, outcome `ambiguous`, took 206 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 363-17 | Assessment Standards | Section 7 - Definitions | Current | 0.574157 | https://policies.latrobe.edu.au/document/view.php?id=363 |
| 2 | 363-9 | Assessment Standards | Section 6 - Standards, Part D - Designing for Learning and Feedback | Current | 0.573721 | https://policies.latrobe.edu.au/document/view.php?id=363 |
| 3 | 216-5 | Assessment Policy | Section 5 - Policy Statement | Current | 0.570945 | https://policies.latrobe.edu.au/document/view.php?id=216 |
| 4 | 363-6 | Assessment Standards | Section 6 - Standards, Part A - Overview | Current | 0.570109 | https://policies.latrobe.edu.au/document/view.php?id=363 |
| 5 | 216-7 | Assessment Policy | Section 7 - Definitions | Current | 0.562197 | https://policies.latrobe.edu.au/document/view.php?id=216 |

### Q11 - What are the rules about using AI?

Audit id 11, outcome `answered`, took 210 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 417-5 | Responsible AI Adoption Policy | Section 5 - Policy Statement | Current | 0.669968 | https://policies.latrobe.edu.au/document/view.php?id=417 |
| 2 | 417-2 | Responsible AI Adoption Policy | Section 2 - Purpose | Current | 0.654421 | https://policies.latrobe.edu.au/document/view.php?id=417 |
| 3 | 417-6 | Responsible AI Adoption Policy | Section 6 - Procedures | Current | 0.647415 | https://policies.latrobe.edu.au/document/view.php?id=417 |
| 4 | 417-7 | Responsible AI Adoption Policy | Section 7 - Definitions | Current | 0.591966 | https://policies.latrobe.edu.au/document/view.php?id=417 |
| 5 | 363-17 | Assessment Standards | Section 7 - Definitions | Current | 0.567892 | https://policies.latrobe.edu.au/document/view.php?id=363 |

### Q12 - How much does a Bundoora campus parking permit cost?

Audit id 12, outcome `unsupported`, took 227 ms.

Nothing came back.

### Q13 - What are the library opening hours during the exam period?

Audit id 13, outcome `unsupported`, took 224 ms.

Nothing came back.

### Q14 - What is the current Privacy Policy and when did it take effect?

Audit id 14, outcome `unsupported`, took 220 ms.

Nothing came back.

### Q15 - What did the previous version of the Student Complaints Management Policy say about complaint pathways?

Audit id 15, outcome `answered`, took 204 ms.

| Rank | Chunk | Policy | Section | Status | Score | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 160-8 | Student Complaints Management Policy | Section 6 - Procedures, Part A - Complaints Pathways | Current | 0.690228 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 2 | 160-6 | Student Complaints Management Policy | Section 5 - Policy Statement | Current | 0.59692 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 3 | 160-10 | Student Complaints Management Policy | Section 6 - Procedures, Part C - Submitting a Formal Complaint | Current | 0.596905 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 4 | 160-2 | Student Complaints Management Policy | Section 2 - Purpose | Current | 0.594633 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |
| 5 | 160-11 | Student Complaints Management Policy | Section 6 - Procedures, Part D - Complaint Investigation | Current | 0.574998 | https://policies.latrobe.edu.au/document/view.php?id=160&version=7 |

## 6. Failed tests

Raise each of these as a Jira defect, or write it up as a limitation with
a reason if the team decides not to fix it this sprint.

### [Q09] Retrieval failed - Who approves high risk AI use cases at La Trobe?

- Category: supported
- Question: Who approves high risk AI use cases at La Trobe?
- Expected: right chunk in the top 3 and outcome is 'answered'. expected chunk(s): 417-4.
- What happened: outcome was 'answered', the top result was 417-6 (Responsible AI Adoption Policy) with a score of 0.662059
- Audit id: 9
- To reproduce: close the Django server, then run `python tests/run_retrieval_tests.py` and look at Q09.

### [Q11] Retrieval failed - What are the rules about using AI?

- Category: ambiguous
- Question: What are the rules about using AI?
- Expected: outcome is 'ambiguous', or the top 3 covers both policies. expected chunk(s): 417-5, 417-2, 363-17.
- What happened: outcome was 'answered', the top result was 417-5 (Responsible AI Adoption Policy) with a score of 0.669968
- Audit id: 11
- To reproduce: close the Django server, then run `python tests/run_retrieval_tests.py` and look at Q11.

### [Q14] Retrieval failed - What is the current Privacy Policy and when did it take effe

- Category: current_policy
- Question: What is the current Privacy Policy and when did it take effect?
- Expected: right chunk in the top 3, outcome is 'answered', and everything returned says Current. expected chunk(s): 1-1.
- What happened: outcome was 'unsupported' and nothing came back
- Audit id: 14
- To reproduce: close the Django server, then run `python tests/run_retrieval_tests.py` and look at Q14.

## 7. Limitations

- **We have no superseded policies indexed.** Every chunk says `Current`, and
  COPL-184's retriever filters on `status = Current` in the Qdrant query
  anyway, so the superseded test (Q15) passes by construction. It proves the
  system never hands back non-current content, but it cannot prove the system
  understands policy versions. Testing that needs an older version ingested.
- **The 0.55 similarity threshold comes from COPL-184, not from measurement.**
  It decides every unsupported result above. Compare it against the real
  scores in section 5 before treating these percentages as settled.
- **Ambiguity is judged on policy title.** COPL-184's evidence does not carry
  a document id in its public shape, so two chunks count as different policies
  when their titles differ.
- **We wrote our own expected answers.** Nobody outside the team checked them.

## 8. Evidence files

- Full results: `tests/results/results_2026-09-06_17-15-53.json`
- Spreadsheet: `tests/results/results_2026-09-06_17-15-53.csv`
- Audit log file: `data/audit/audit_log.jsonl`
- Audit log database: `db.sqlite3`, tables `api_auditlog` and `api_auditchunk`
- Test set: `tests/retrieval_test_set.json`
