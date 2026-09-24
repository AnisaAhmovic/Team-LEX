# S4-07 - Generation Fallback and Guardrail Validation

## Purpose

S4-07 extends the Sprint 3 retrieval fallback and evidence guardrails through the Qwen3 generation stage so that unsupported questions cannot be converted into unsupported policy advice.

## Implemented control flow

The implemented RAG flow preserves the established Sprint 3 retrieval controls:

1. Retrieve Current authoritative La Trobe policy evidence.
2. Retain the minimum similarity threshold of 0.55.
3. Return fallback when retrieval does not produce supported evidence.
4. Bypass Qwen3 generation when retrieval status is not `supported`.
5. Select bounded evidence only from supported retrieval results.
6. Instruct Qwen3 to use only supplied evidence and to abstain when evidence is insufficient.
7. Constrain generated support to server-supplied evidence IDs and allowed quotes.
8. Validate generated evidence references and source provenance on the server.
9. Return safe fallback when generation abstains, fails or cannot be verified.
10. Preserve authoritative escalation to the La Trobe Policy Library.

## S4-07 validation evidence

| Requirement | Validation evidence |
| --- | --- |
| Review existing guardrails | Retrieval, generation gate, prompt/schema and server-side citation validation inspected. |
| Retain 0.55 initially | Retriever retains `minimum_similarity_score = 0.55`. |
| Use supported/fallback as generation gate | `/api/answer/` proceeds to generation only when retrieval status is `supported`. |
| Allow constrained generation only when supported | Supported endpoint test confirms generation path; fallback test confirms bypass. |
| Bypass generation when evidence is insufficient | `test_fallback_retrieval_bypasses_generation` verifies Qwen3 is not called. |
| Preserve fallback wording | Fallback responses remain centrally controlled by `fallback_response()` and fixed fallback messages. |
| Preserve escalation | Fallback responses retain authoritative escalation to the official La Trobe Policy Library. |
| Supported question | `test_supported_question_returns_complete_current_policy_evidence` and supported answer endpoint test pass. |
| Out-of-domain question | Weather question below threshold returns safe fallback in `test_unsupported_question_returns_safe_fallback_below_threshold`. |
| No sufficient policy evidence | Below-threshold evidence produces fallback with no evidence returned. |
| Partial evidence | `test_partial_evidence_does_not_create_support_for_missing_facts` confirms missing facts do not enter the allowed support universe and the prompt requires abstention when evidence is insufficient. |
| Ambiguity | `test_missing_or_ambiguous_section_does_not_drop_a_requested_policy` verifies ambiguous section requests do not trigger guessed section scope. |
| Attempts to force guessing/general knowledge | `test_question_instructions_cannot_expand_the_evidence_contract` verifies hostile question instructions cannot expand server-defined evidence IDs or allowed support quotes. |
| No unsupported advice | Existing tests reject unknown evidence, invented quotes, forged metadata, fictional policy attribution, out-of-context quotes and invalid citations; unverifiable generation falls back safely. |
| Record threshold weaknesses | S4-04 validation showed useful evidence can occur at rank 5 and similarity scores may cluster near the threshold; no higher threshold or smaller retrieval depth was justified. |
| Add tests | Two targeted tests were added for partial evidence and attempts to force general-knowledge generation. |

## Targeted validation result

Ten targeted S4-07 tests passed:

- 2 new partial-evidence and hostile-instruction evidence-contract tests.
- 4 retrieval/query-scope guardrail tests.
- 4 generation-gate, invalid-citation and model-abstention tests.

All targeted tests passed with no Django system-check issues.

## Safe fallback behaviour

The generation layer preserves controlled fallback behaviour:

- insufficient retrieval evidence - generation is not attempted;
- empty model claims - `generation_insufficient_evidence`;
- unverifiable generated evidence/citations - `unverifiable_generation`;
- generation service failure - `generation_unavailable`;
- fallback responses contain no answer, claims or supporting sources;
- authoritative escalation remains available through the official La Trobe Policy Library.

## Known limitation

Server-side citation validation verifies evidence provenance and exact quote membership, but it does not independently prove full semantic entailment between every generated paraphrase and its cited quote. The layered controls reduce this risk through evidence-only prompting, bounded context, constrained evidence IDs and quotes, abstention instructions, deterministic generation settings and server-side provenance validation.

This residual limitation should remain visible in responsible-AI testing and system documentation rather than being represented as fully eliminated.

## Definition of Done

The implemented generation pipeline prevents unsupported retrieval results from reaching Qwen3, constrains supported generation to selected authoritative evidence, rejects unverifiable evidence references and preserves safe fallback and authoritative escalation.

Targeted S4-07 behavioural validation passed.
