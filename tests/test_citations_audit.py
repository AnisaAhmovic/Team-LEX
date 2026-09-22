"""S4-06/S4-10 behavioural tests, no BGE-M3 weights or Ollama required."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from api.audit import AuditStore, new_record, sanitise_record
from api.citations import (
    CitationValidationError, MAX_CHUNK_CHARS, SOURCE_FIELDS,
    build_cited_answer, build_prompt, select_context,
)
from llm import LLMConnectionError, QwenService
from retrieval import PolicyRetriever
from tests.test_policy_retriever import FakeClient, current_point, embedding


def point(index=1, score=0.82, **overrides):
    return current_point(score=score, chunk_id=f"216-{index}", document_id="216",
                         effective_date="7th September 2021", review_date="22nd April 2027",
                         version=None, **overrides)


def retrieve(points):
    return PolicyRetriever(client=FakeClient(points), embedder=lambda _: embedding())


def model_text(*refs):
    return json.dumps({"claims": [
        {"text": f"Supported claim {i}.", "support": [{"evidence_id": eid, "quote": quote}]}
        for i, (eid, quote) in enumerate(refs, 1)
    ]})


def generation(text):
    return {"text": text, "model": "qwen3:4b", "done": True, "latency_seconds": 0.01}


class CitationTests(TestCase):
    def setUp(self):
        self.evidence = retrieve([point()]).retrieve("What does the policy say?")["evidence"]
        self.context = select_context(self.evidence)
        self.quote = self.context[0]["context_text"]

    def test_source_fields_are_copied_from_metadata_and_ids_stay_internal(self):
        result, links = build_cited_answer(model_text(("E1", self.quote)), self.context)
        source = result["sources"][0]
        for field in SOURCE_FIELDS:
            self.assertEqual(source[field], self.evidence[0].get(field))
        self.assertIsNone(source["version"])
        self.assertNotIn("chunk_id", source)
        self.assertEqual(links[0]["chunk_id"], "216-1")
        self.assertEqual(result["claims"][0]["source_ids"], ["S1"])
        self.assertTrue(result["answer"].endswith("[S1]"))

    def test_prompt_identifies_evidence_without_asking_for_source_objects(self):
        prompt = build_prompt("What does the policy say?", self.context)
        self.assertIn('"evidence_id": "E1"', prompt)
        self.assertNotIn(self.evidence[0]["source_url"], prompt)
        self.assertIn('"policy_title": "Assessment Policy"', prompt)
        self.assertIn(self.evidence[0]["section"], prompt)
        self.assertNotIn('"source_url"', prompt)

    def test_known_policy_title_in_a_supported_claim_is_accepted(self):
        for claim_text in ("The Assessment Policy requires timely feedback.",
                           "Under Assessment Policy, feedback is timely.",
                           "This Policy requires timely feedback."):
            value = json.loads(model_text(("E1", self.quote)))
            value["claims"][0]["text"] = claim_text
            with self.subTest(text=claim_text):
                result, _ = build_cited_answer(json.dumps(value), self.context)
                self.assertEqual(result["claims"][0]["text"], claim_text)
                self.assertEqual(result["sources"][0]["policy_title"], "Assessment Policy")

    def test_titles_from_unused_or_other_claims_evidence_are_not_attributions(self):
        evidence = [self.evidence[0], {**self.evidence[0], "policy_title": "Research Human Ethics Procedure"}]
        context = select_context(evidence)
        for claim_text in ("The Research Human Ethics Procedure requires feedback.",
                           "The Fictional Assessment Policy requires feedback."):
            value = json.loads(model_text(("E1", self.quote), ("E2", self.quote)))
            value["claims"][0]["text"] = claim_text
            with self.subTest(text=claim_text), self.assertRaisesRegex(CitationValidationError, "unverified_policy_title"):
                build_cited_answer(json.dumps(value), context)

    def test_one_claim_may_name_both_policies_it_actually_cites(self):
        second = {**self.evidence[0], "policy_title": "Research Human Ethics Procedure"}
        value = {"claims": [{"text": "The Assessment Policy and Research Human Ethics Procedure require this.",
                            "support": [{"evidence_id": "E1", "quote": self.quote},
                                        {"evidence_id": "E2", "quote": self.quote}]}]}
        result, _ = build_cited_answer(json.dumps(value), select_context([self.evidence[0], second]))
        self.assertEqual(len(result["sources"]), 2)

    def test_citation_text_rejections_have_distinct_safe_reason_codes(self):
        cases = {"See https://example.test": "generated_url",
                 "See [E1]": "generated_reference_marker",
                 "See Section 2": "generated_section_reference",
                 "Sources: Assessment Policy": "generated_source_list",
                 "The Fictional Policy says so.": "unverified_policy_title"}
        for claim_text, reason in cases.items():
            value = json.loads(model_text(("E1", self.quote)))
            value["claims"][0]["text"] = claim_text
            with self.subTest(text=claim_text), self.assertRaisesRegex(CitationValidationError, reason):
                build_cited_answer(json.dumps(value), self.context)

    def test_multiple_sections_of_one_url_remain_distinct(self):
        evidence = [self.evidence[0], {**self.evidence[0], "section": "Section 6", "chunk_id": "216-2"}]
        result, _ = build_cited_answer(model_text(("E1", self.quote), ("E2", self.quote)), select_context(evidence))
        self.assertEqual(len(result["sources"]), 2)
        self.assertEqual(result["claims"][1]["source_ids"], ["S2"])

    def test_identical_source_metadata_deduplicates_without_losing_links(self):
        evidence = [self.evidence[0], {**self.evidence[0], "chunk_id": "216-2"}]
        result, links = build_cited_answer(model_text(("E1", self.quote), ("E2", self.quote)), select_context(evidence))
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(len(links), 2)

    def test_unused_context_is_not_cited(self):
        evidence = [self.evidence[0], {**self.evidence[0], "section": "Unused section"}]
        result, links = build_cited_answer(model_text(("E1", self.quote)), select_context(evidence))
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(len(links), 1)

    def test_one_claim_can_rely_on_two_policies(self):
        second = {**self.evidence[0], "source_url": "https://policies.latrobe.edu.au/document/view.php?id=112", "policy_title": "Research Human Ethics Procedure"}
        text = json.dumps({"claims": [{"text": "A claim relying on both documents.", "support": [
            {"evidence_id": "E1", "quote": self.quote}, {"evidence_id": "E2", "quote": self.quote},
        ]}]})
        result, _ = build_cited_answer(text, select_context([self.evidence[0], second]))
        self.assertEqual(result["claims"][0]["source_ids"], ["S1", "S2"])
        self.assertEqual(len(result["sources"]), 2)

    def test_unknown_evidence_forged_metadata_and_unlinked_claims_are_rejected(self):
        valid = json.loads(model_text(("E1", self.quote)))
        cases = ["plain uncited answer", '{"claims": [], "claims": []}',
                 json.dumps({**valid, "sources": [{"source_url": "https://invented.test"}]}),
                 model_text(("E5", self.quote)), model_text(("E1", "This quote was invented.")),
                 '{"claims":[{"text":"No support", "support":[]}]}',
                 '{"claims":[{"text":"False source", "support":[{"evidence_id":[],"quote":"An invented quote"}]}]}']
        for text in cases:
            with self.subTest(text=text), self.assertRaises(CitationValidationError):
                build_cited_answer(text, self.context)

    def test_inline_model_citations_are_not_displayed(self):
        for claim_text in ("Look at https://evil.test", "Invented [S9]", "See Section 999", "<a>Policy</a>", "The Fictional Policy requires this.", "Source: an invented document"):
            value = json.loads(model_text(("E1", self.quote)))
            value["claims"][0]["text"] = claim_text
            with self.subTest(text=claim_text), self.assertRaises(CitationValidationError):
                build_cited_answer(json.dumps(value), self.context)

    def test_quote_cannot_refer_to_text_outside_truncated_context(self):
        evidence = [{**self.evidence[0], "policy_text": "a" * MAX_CHUNK_CHARS + " An excluded later statement."}]
        context = select_context(evidence)
        self.assertTrue(context[0]["context_truncated"])
        with self.assertRaises(CitationValidationError):
            build_cited_answer(model_text(("E1", "An excluded later statement.")), context)

    def test_missing_mandatory_metadata_cannot_be_filled_by_the_model(self):
        for key in ("policy_title", "section", "source_url"):
            context = deepcopy(self.context)
            context[0][key] = None
            with self.subTest(field=key), self.assertRaises(CitationValidationError):
                build_cited_answer(model_text(("E1", self.quote)), context)


class ProvenanceTests(TestCase):
    def test_rank_scores_and_all_exclusion_reasons_are_retained(self):
        points = [point(), point(2, score=0.2), point(3, status="Superseded"),
                  point(4, section=None), point(5, source_url="https://example.org")]
        result = retrieve(points).retrieve("What does the policy say?")
        candidates = result["_trace"]["candidates"]
        self.assertEqual([c["rank"] for c in candidates], [1, 2, 3, 4, 5])
        self.assertEqual([c["exclusion_reason"] for c in candidates],
                         [None, "below_threshold", "not_current", "missing_provenance", "untrusted_source_url"])
        self.assertEqual(candidates[1]["similarity_score"], 0.2)
        self.assertEqual(result["evidence"][0]["chunk_id"], "216-1")
        self.assertEqual(result["_trace"]["config"]["minimum_similarity_score"], 0.55)

    def test_fallback_retains_rejected_candidates_and_nonfinite_scores_are_safe(self):
        result = retrieve([point(score=float("nan")), point(2, score=0.2)]).retrieve("Unsupported question")
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(len(result["_trace"]["candidates"]), 2)
        self.assertIsNone(result["_trace"]["candidates"][0]["similarity_score"])
        json.dumps(result, allow_nan=False)

    def test_documents_starting_at_h2_retain_their_actual_heading(self):
        result = retrieve([point(section=None, subsection="Part A - Purpose")]).retrieve("What is its purpose?")
        self.assertEqual(result["evidence"][0]["section"], "Part A - Purpose")

    def test_duplicate_candidates_are_excluded(self):
        result = retrieve([point(), point()]).retrieve("What does the policy say?")
        self.assertEqual(len(result["evidence"]), 1)
        self.assertEqual(result["_trace"]["candidates"][1]["exclusion_reason"], "duplicate_evidence")

    def test_malformed_credentialled_and_lookalike_urls_are_excluded(self):
        for url in ("https://policies.latrobe.edu.au.evil.test", "https://user:secret@latrobe.edu.au", "http://latrobe.edu.au", "https://[broken", "https://latrobe.edu.au:bad", "https://evil.test@latrobe.edu.au"):
            with self.subTest(url=url):
                self.assertEqual(retrieve([point(source_url=url)]).retrieve("Is this policy current?")["status"], "fallback")


class AuditStoreTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = AuditStore(Path(temporary.name) / "audit" / "interactions.sqlite3")

    def test_concurrent_requests_are_individually_retrievable(self):
        records = [{**new_record("answer"), "outcome": "supported"} for _ in range(12)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(self.store.append, records))
        self.assertEqual(len(self.store.read(limit=20)), 12)
        for interaction_id in ids:
            self.assertEqual(self.store.read(interaction_id)[0]["interaction_id"], interaction_id)
        if os.name == "posix":
            self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)

    def test_personal_data_secrets_and_long_questions_are_redacted_or_bounded(self):
        record = {**new_record("answer"), "outcome": "supported", "question": "Contact student@example.test or 0412 345 678, student ID 12345678. password=very-secret", "response": {"answer": "Bearer abc.def.ghi and sk-testing-secret-key"}}
        self.store.append(record)
        saved = self.store.read()[0]
        text = json.dumps(saved)
        for value in ("student@example.test", "0412 345 678", "12345678", "very-secret", "abc.def.ghi", "sk-testing-secret-key"):
            self.assertNotIn(value, text)
        self.assertTrue(saved["privacy"]["redacted_fields"])
        safe = sanitise_record({"question": "x" * 1000})
        self.assertEqual(len(safe["question"]), 500)
        self.assertEqual(safe["privacy"]["truncated_fields"], ["question"])

    def test_correlation_id_survives_redaction_and_plain_language_secrets_do_not(self):
        record = {**new_record("answer"), "outcome": "fallback",
                  "interaction_id": "12345678-1234-4234-8234-123456789012",
                  "question": "My api key is a-private-value"}
        self.store.append(record)
        saved = self.store.read(record["interaction_id"])[0]
        self.assertEqual(saved["interaction_id"], record["interaction_id"])
        self.assertNotIn("a-private-value", json.dumps(saved))

    def test_expired_records_are_removed(self):
        old = {**new_record("answer"), "outcome": "fallback", "timestamp_utc": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()}
        self.store.append(old)
        self.store.append({**new_record("answer"), "outcome": "supported"})
        self.assertEqual(len(self.store.read()), 1)
        self.assertEqual(self.store.read()[0]["outcome"], "supported")


class InteractionAuditTests(SimpleTestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "audit.sqlite3"
        settings = override_settings(AUDIT_DB_PATH=self.path)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client = APIClient()

    def request(self, retriever, text=None, error=None, question="What does the policy say?", endpoint="answer"):
        with patch("api.views.get_policy_retriever", return_value=retriever), patch("api.views.get_qwen_service") as service:
            service.return_value.model = "qwen3:4b"
            service.return_value.generate.return_value = generation(text or "")
            service.return_value.generate.side_effect = error
            response = self.client.post(f"/api/{endpoint}/", {"question": question}, format="json", HTTP_AUTHORIZATION="Bearer never-log-this", HTTP_COOKIE="secret-session", REMOTE_ADDR="192.0.2.5")
        return response, AuditStore(self.path).read(response.data.get("interaction_id"))[0]

    def test_supported_request_can_be_reconstructed_without_private_trace_in_response(self):
        retriever = retrieve([point(), point(2, score=0.1)])
        quote = point().payload["text"]
        response, record = self.request(retriever, model_text(("E1", quote)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "supported")
        self.assertEqual(record["question"], "What does the policy say?")
        self.assertEqual(len(record["retrieval"]["candidates"]), 2)
        self.assertEqual(record["selection"]["excluded"][0]["reason"], "below_threshold")
        self.assertEqual(record["selection"]["selected_context"][0]["context_text"], quote)
        self.assertEqual(record["selection"]["source_evidence"][0]["chunk_id"], "216-1")
        self.assertEqual(record["response"]["answer"], response.data["answer"])
        self.assertEqual(record["response"]["sources"], response.data["sources"])
        self.assertEqual(record["generation"]["model"], "qwen3:4b")
        self.assertNotIn("_trace", response.data)
        for value in ("never-log-this", "secret-session", "192.0.2.5", "base_url", "SECRET_KEY"):
            self.assertNotIn(value, json.dumps(record))

    def test_fallback_logs_rejected_evidence_without_generation(self):
        response, record = self.request(retrieve([point(score=0.1)]))
        self.assertEqual(response.data["status"], "fallback")
        self.assertEqual(record["outcome"], "fallback")
        self.assertFalse(record["generation"]["attempted"])
        self.assertEqual(len(record["retrieval"]["candidates"]), 1)
        self.assertEqual(response.data["sources"], [])

    def test_generation_failure_retains_selected_context_without_exception_details(self):
        response, record = self.request(retrieve([point()]), error=LLMConnectionError("password=do-not-log"))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(record["outcome"], "error")
        self.assertEqual(record["error"]["stage"], "generation")
        self.assertEqual(len(record["selection"]["selected_context"]), 1)
        self.assertNotIn("do-not-log", json.dumps(record))
        self.assertEqual(response.data["sources"], [])

    def test_retrieval_failure_and_invalid_input_are_logged(self):
        retriever = PolicyRetriever(client=FakeClient(error=RuntimeError("connection secret")), embedder=lambda _: embedding())
        response, record = self.request(retriever)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(record["retrieval"]["outcome"], "error")
        self.assertNotIn("connection secret", json.dumps(record))
        response, record = self.request(retrieve([]), question=None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(record["error"]["code"], "invalid_question")

    def test_invalid_citations_fall_back_and_are_logged(self):
        response, record = self.request(retrieve([point()]), model_text(("E9", point().payload["text"])))
        self.assertEqual(response.data["fallback_reason"], "unverifiable_generation")
        self.assertEqual(record["generation"]["validation"], "unknown_evidence")
        self.assertIsNone(response.data["answer"])
        self.assertEqual(response.data["sources"], [])
        self.assertIn("could not verify", response.data["message"])
        self.assertNotIn("could not find", response.data["message"])

    def test_named_policy_claim_and_query_scope_can_be_reconstructed(self):
        base = retrieve([point()])
        result = base.retrieve("What is the purpose of the Assessment Policy?")
        scope = {"policy_titles": ["Assessment Policy"], "requested_section": "purpose",
                 "heading_filters": {"section": ["Section 2 - Purpose"]}}
        result["_trace"]["query_scope"] = scope
        retriever = SimpleNamespace(retrieve=lambda _: result, audit_config=base.audit_config)
        value = json.loads(model_text(("E1", point().payload["text"])))
        value["claims"][0]["text"] = "The Assessment Policy requires timely feedback."
        response, record = self.request(retriever, json.dumps(value))
        self.assertEqual(response.data["status"], "supported")
        self.assertEqual(record["retrieval"]["query_scope"], scope)
        self.assertEqual(record["generation"]["validation"], "accepted")
        self.assertEqual(record["generation"]["prompt_version"], "lex-claims-v2")

    def test_specific_attribution_rejection_is_audited_without_raw_model_text(self):
        value = json.loads(model_text(("E1", point().payload["text"])))
        value["claims"][0]["text"] = "The Fictional Policy says this."
        response, record = self.request(retrieve([point()]), json.dumps(value))
        self.assertEqual(response.data["fallback_reason"], "unverifiable_generation")
        self.assertEqual(record["generation"]["validation"], "unverified_policy_title")
        self.assertNotIn("Fictional", json.dumps(record))

    def test_model_abstention_is_a_fallback(self):
        response, record = self.request(retrieve([point()]), '{"claims":[]}')
        self.assertEqual(response.data["fallback_reason"], "generation_insufficient_evidence")
        self.assertEqual(record["generation"]["validation"], "model_abstained")

    def test_retrieve_endpoint_is_logged_and_does_not_leak_candidate_trace(self):
        response, record = self.request(retrieve([point()]), endpoint="retrieve")
        self.assertEqual(record["endpoint"], "retrieve")
        self.assertEqual(record["selection"]["mode"], "retrieval_only")
        self.assertNotIn("_trace", response.data)

    def test_parse_errors_are_logged_without_storing_raw_bodies(self):
        response = self.client.post("/api/answer/", '{"password": "never-store",', content_type="application/json")
        self.assertEqual(response.status_code, 400)
        record = AuditStore(self.path).read(response.data["interaction_id"])[0]
        self.assertEqual(record["error"]["code"], "invalid_request")
        self.assertNotIn("never-store", json.dumps(record))

    def test_unexpected_failures_are_logged(self):
        with patch("api.views.get_policy_retriever", side_effect=RuntimeError("private path")):
            response = self.client.post("/api/answer/", {"question": "A question"}, format="json")
        self.assertEqual(response.status_code, 500)
        record = AuditStore(self.path).read(response.data["interaction_id"])[0]
        self.assertEqual(record["error"]["code"], "internal_error")
        self.assertNotIn("private path", json.dumps(record))

    def test_storage_failure_never_returns_an_unaudited_supported_answer(self):
        with patch("api.views.get_audit_store", side_effect=OSError("private path")):
            with patch("api.views.get_policy_retriever", return_value=retrieve([])):
                response = self.client.post("/api/answer/", {"question": "A question"}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["fallback_reason"], "audit_unavailable")
        self.assertNotIn("interaction_id", response.data)
        self.assertNotIn("private path", str(response.data))


class QwenFormatTests(TestCase):
    @patch("llm.client.requests.post")
    def test_schema_and_options_are_sent_to_ollama_without_breaking_plain_generation(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"response": '{"claims":[]}', "done": True}
        service = QwenService()
        service.generate("prompt", response_format={"type": "object"}, options={"temperature": 0})
        self.assertEqual(post.call_args.kwargs["json"]["format"], {"type": "object"})
        self.assertEqual(post.call_args.kwargs["json"]["options"], {"temperature": 0})
        service.generate("plain prompt")
        self.assertNotIn("format", post.call_args.kwargs["json"])
