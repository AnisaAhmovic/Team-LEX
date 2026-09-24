# S4-04 Constrained RAG Prompt Construction and Evidence Selection

## Purpose

S4-04 implements and validates the separation between policy retrieval, evidence selection, and constrained Qwen3 generation. The objective is to ensure that Qwen3 receives only selected, validated policy evidence and that generated claims remain constrained to that evidence.

## Evidence Selection Rule

LEX AI applies the following evidence flow:

1. Retrieve the Top-5 candidate policy chunks from the Current authoritative corpus.
2. Validate candidate evidence using the established minimum similarity threshold of 0.55 and provenance/current-policy controls.
3. Exclude candidates that fail evidence validation.
4. Pass eligible evidence to a separate context-selection step.
5. Select up to five eligible evidence chunks and bound each selected chunk to a maximum of 800 characters.
6. Construct the generation prompt using only the selected evidence.
7. Require Qwen3 to return structured claims supported by supplied evidence IDs and permitted evidence quotes.
8. Validate generated claims and citations server-side before returning an answer.
9. If retrieval or generation cannot produce a supported answer, return the safe fallback rather than speculative policy advice.

No additional relative-score, score-drop, or smaller effective-K rule is applied.

## Selection Rationale

Retrieval testing showed that relevant policy evidence is not always concentrated at rank 1.

For the broad Safe Driving query, all five candidates exceeded the 0.55 threshold and had closely clustered similarity scores. The directly useful University Vehicle Fleet evidence appeared at rank 5. Reducing the effective context to Top-1 or Top-3, or applying an arbitrary score-drop rule, could therefore remove useful evidence.

Policy-specific retrieval also demonstrated that relevant evidence may span multiple sections of the same policy. Explicit indexed policy-title scoping is retained where the user names a policy, rather than introducing additional score-based pruning.

The final approach therefore retains the established absolute eligibility controls and separates retrieval from bounded context selection.

## Behavioural Validation

### Broad Safe Driving query

Question:

"What does La Trobe University policy say about safe driving?"

Real retrieval returned five eligible candidates, including related and tangential evidence. The directly useful University Vehicle Fleet evidence was ranked fifth.

A live Qwen3 generation using the selected Top-5 context completed successfully and produced a claim that drivers must complete the registration process before driving a University Fleet Vehicle. The model supported the claim using the corresponding E5 evidence.

The generated claim was manually compared with the supplied E5 text and was directly supported by it. Tangential Workplace Behaviours and Student Behaviours evidence supplied in the same context was not used in the generated claim.

This supports retaining validated Top-5 evidence rather than introducing a smaller fixed K or score-drop rule.

### Policy-specific Safe Driving retrieval

The query:

"According to the Health and Safety Procedure - Safe Driving, what must drivers do when driving on university-related business?"

correctly scoped retrieval to the named indexed policy and returned complementary evidence across multiple Safe Driving sections.

Automated tests provide generation and validation coverage for multi-section and multi-source evidence. A live end-to-end generation attempt for this case returned the safe generation-unavailable fallback, so this attempt is not recorded as a successful live multi-source generation.

### Excluded and unsupported evidence

Automated guardrail tests verify that generated output cannot be accepted using unknown evidence IDs, invented quotes, forged metadata, unused evidence, or material outside the selected bounded context.

The server performs citation and evidence validation after generation. Invalid or unverifiable generation is not returned as a supported policy answer.

## Prompt Constraints

The constrained generation prompt:

- treats the question and evidence as data rather than instructions;
- requires answers to use only supplied evidence;
- prohibits general-knowledge gap filling;
- prohibits invented citations and policy metadata;
- requires substantive claims to reference supplied evidence IDs and permitted quotes;
- allows an empty claims result when supplied evidence is insufficient; and
- leaves final citation construction and validation to the server.

Generation uses deterministic options including temperature 0 and seed 0.

## Refinement Decision

The selection and prompt approach was reviewed following retrieval, live-generation, and automated guardrail testing.

No evidence-selection refinement was required for S4-04.

In particular, the testing did not justify a smaller effective K, a higher similarity threshold, or a relative score/drop-off rule. These approaches could remove useful lower-ranked evidence without providing a reliable relevance boundary.

The existing architecture is retained:

Current authoritative corpus -> Top-5 retrieval -> evidence validation -> bounded context selection -> constrained generation -> server-side claim/citation validation -> supported answer or safe fallback.

## Runtime Observation

Live structured Qwen3 generation on the tested CPU-only development environment exceeded the original 60-second Ollama timeout. After the local timeout was increased to 180 seconds, a full constrained generation completed successfully in approximately 133 seconds.

A subsequent end-to-end generation attempt returned `generation_unavailable` despite the increased timeout. The endpoint failed closed: no answer, claims, or sources were returned and the user was directed to the authoritative La Trobe Policy Library.

This is recorded as a runtime/reproducibility limitation rather than an evidence-selection defect. Environment and setup implications are to be addressed separately through project setup and reproducibility documentation.

## S4-04 Validation Summary

- Retrieval and generation remain separate stages.
- Only validated selected evidence is supplied to Qwen3.
- Useful evidence may occur below the highest retrieval ranks.
- Live generation demonstrated selection of relevant evidence while ignoring tangential supplied evidence.
- Generated claims were checked against supplied evidence.
- Automated tests protect against excluded, invented, or out-of-context evidence.
- Unsupported retrieval and generation failures fail safely.
- No additional evidence-selection or prompt refinement was required following validation.
