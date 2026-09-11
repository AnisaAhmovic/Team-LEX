"""Run representative expanded-corpus retrieval checks for COPL-289."""

from retrieval import PolicyRetriever, RetrievalUnavailableError


REPRESENTATIVE_CHECKS = [
    {
        "label": "Travel Management Policy",
        "question": (
            "Who must follow the Travel Management Policy when travelling "
            "on University business?"
        ),
        "expected_status": "supported",
        "expected_policy": "Travel Management Policy",
    },
    {
        "label": "Health and Safety Procedure - Safe Driving",
        "question": (
            "What does La Trobe require drivers on university-related "
            "business to do to drive safely?"
        ),
        "expected_status": "supported",
        "expected_policy": "Health and Safety Procedure - Safe Driving",
    },
    {
        "label": "Research Data Management Policy",
        "question": "Who does the Research Data Management Policy apply to?",
        "expected_status": "supported",
        "expected_policy": "Research Data Management Policy",
    },
    {
        "label": "Graduate Research Supervision Policy",
        "question": (
            "Who does the Graduate Research Supervision Policy apply to?"
        ),
        "expected_status": "supported",
        "expected_policy": "Graduate Research Supervision Policy",
    },
    {
        "label": "Student Support Policy",
        "question": "What does the Student Support Policy cover?",
        "expected_status": "supported",
        "expected_policy": "Student Support Policy",
    },
    {
        "label": "Unsupported control",
        "question": "What will the weather be in Melbourne tomorrow?",
        "expected_status": "fallback",
        "expected_policy": None,
    },
]


def main() -> int:
    retriever = PolicyRetriever()
    failed_checks = 0

    try:
        for number, check in enumerate(REPRESENTATIVE_CHECKS, start=1):
            result = retriever.retrieve(check["question"])
            actual_status = result["status"]
            evidence = result.get("evidence", [])
            retrieved_policies = [
                item.get("policy_title")
                for item in evidence
                if item.get("policy_title")
            ]

            status_matches = actual_status == check["expected_status"]

            expected_policy = check["expected_policy"]
            if expected_policy is None:
                policy_matches = len(evidence) == 0
                expected_rank = None
            else:
                policy_matches = expected_policy in retrieved_policies
                expected_rank = (
                    retrieved_policies.index(expected_policy) + 1
                    if policy_matches
                    else None
                )

            passed = status_matches and policy_matches

            print(f"\nCHECK {number}: {check['label']}")
            print(f"Question: {check['question']}")
            print(f"Expected status: {check['expected_status']}")
            print(f"Actual status: {actual_status}")
            print(f"Retrieved policies: {retrieved_policies}")

            if expected_policy is not None:
                print(f"Expected policy: {expected_policy}")
                print(
                    "Expected policy rank: "
                    f"{expected_rank if expected_rank is not None else 'Not in Top 5'}"
                )
            else:
                print(f"Evidence returned: {len(evidence)}")

            print(f"Result: {'PASS' if passed else 'FAIL'}")

            if not passed:
                failed_checks += 1

    except RetrievalUnavailableError:
        print(
            "\nRetrieval is unavailable. Confirm that the corpus is indexed "
            "before running COPL-289 verification."
        )
        return 2

    total_checks = len(REPRESENTATIVE_CHECKS)
    passed_checks = total_checks - failed_checks

    print("\nCOPL-289 REPRESENTATIVE RETRIEVAL SUMMARY")
    print(f"Passed: {passed_checks}/{total_checks}")
    print(f"Failed: {failed_checks}/{total_checks}")

    if failed_checks:
        print(
            "Representative retrieval completed with identified retrieval "
            "mismatches requiring documentation or follow-up."
        )
        return 1

    print("All representative retrieval checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
