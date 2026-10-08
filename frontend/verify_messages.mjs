// verify_messages.mjs
// Task 8 checks: answers, fallbacks and errors must all look different, and an
// error must never look like a policy answer.
//
// Run with:  npm run test:messages

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({ optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true } });

try {
  const { makeBotReply, makeConnectionErrorReply } = await server.ssrLoadModule("/src/botReply.js");
  const { default: Message } = await server.ssrLoadModule("/src/components/Message.jsx");

  let html;
  // M3-BQ-01: Chatbot must propagate server-owned assurance to Message.
  // This guards the integration seam that component-only rendering tests missed.
  const chatbotSource = await readFile(
    new URL("./src/components/Chatbot.jsx", import.meta.url),
    "utf8"
  );
  assert.ok(
    chatbotSource.includes("assurance={message.assurance}"),
    "Chatbot must pass message.assurance to Message"
  );
  console.log("M3-BQ-01 assurance wiring ...... ok");

  // --- Test 1: a supported answer keeps its answer, claims and sources ---
  const answer = makeBotReply(true, 200, {
    status: "supported",
    answer: "Group work can be at most 40% of the grade.",
    claims: [{ claim_id: "C1", text: "Group work can be at most 40% of the grade.", source_ids: ["S1"], support: [] }],
    sources: [{ source_id: "S1", policy_title: "Assessment Standards", section: "Section 6", source_url: "https://policies.latrobe.edu.au/document/view.php?id=363" }],
  });
  assert.equal(answer.type, "answer");
  assert.equal(answer.sources.length, 1);
  console.log("1. supported answer ........... ok");
  // --- M3: supported answers expose server-owned assurance results ---
  const assuredAnswer = makeBotReply(true, 200, {
    status: "supported",
    answer: "Students normally receive feedback within 15 business days.",
    claims: [{
      claim_id: "C1",
      text: "Students normally receive feedback within 15 business days.",
      source_ids: ["S1"],
      support: [],
    }],
    sources: [{
      source_id: "S1",
      policy_title: "Assessment Standards",
      section: "Section 6",
      source_url: "https://policies.latrobe.edu.au/document/view.php?id=363",
    }],
    assurance: {
      question_coverage: {
        covered: 2,
        enforced: 2,
        unknown: 0,
        percentage: 100,
      },
      supported_by_current_policy: true,
      policy_conditions_preserved: true,
      sources_verified: true,
    },
  });

  assert.equal(assuredAnswer.assurance.question_coverage.percentage, 100);

  html = renderToStaticMarkup(React.createElement(Message, {
    sender: "bot",
    messageId: "assured",
    ...assuredAnswer,
  }));

  assert.ok(html.includes("Answer checks"), "supported answer should show assurance panel");
  assert.ok(html.includes("Question coverage"), "assurance panel should identify question coverage");
  assert.ok(html.includes("100%"), "fully assessed coverage should show percentage");
  assert.ok(html.includes("2 of 2 verified requirements addressed"), "coverage denominator should be explicit");
  assert.ok(html.includes("Supported by current policy"), "policy support should be visible");
  assert.ok(html.includes("Policy conditions preserved"), "constraint preservation should be visible");
  assert.ok(html.includes("Sources verified"), "source verification should be visible");

  // Unknown requirements must never be hidden behind a reassuring percentage.
  const partiallyAssessed = {
    ...assuredAnswer,
    assurance: {
      ...assuredAnswer.assurance,
      question_coverage: {
        covered: 2,
        enforced: 2,
        unknown: 1,
        percentage: null,
      },
    },
  };

  html = renderToStaticMarkup(React.createElement(Message, {
    sender: "bot",
    messageId: "partial",
    ...partiallyAssessed,
  }));

  assert.ok(!html.includes("100%"), "unknown requirements must suppress coverage percentage");
  assert.ok(html.includes("2 verified requirements addressed"), "verified count should remain visible");
  assert.ok(html.includes("1 not automatically assessed"), "unknown requirement must be disclosed");


  // A requirement that RCV cannot automatically enforce must not look failed.
  const notEnforcedAnswer = {
    ...assuredAnswer,
    assurance: {
      ...assuredAnswer.assurance,
      question_coverage: {
        covered: 0,
        enforced: 0,
        unknown: 1,
        percentage: null,
      },
    },
  };

  html = renderToStaticMarkup(React.createElement(Message, {
    sender: "bot",
    messageId: "not-enforced",
    ...notEnforcedAnswer,
  }));

  assert.ok(
    html.includes("Requirement not automatically assessed"),
    "not-enforced requirement should be described as not automatically assessed"
  );
  assert.ok(
    !html.includes("0 verified requirements addressed"),
    "not-enforced requirement must not look like failed question coverage"
  );
  // --- Test 2: not enough evidence is a fallback and keeps the escalation link ---
  const fallbackData = {
    status: "fallback",
    message: "I could not find enough current, authoritative La Trobe policy evidence to answer that question.",
    fallback_reason: "insufficient_evidence",
    escalation: { message: "Check the official La Trobe Policy Library.", url: "https://policies.latrobe.edu.au/" },
  };
  const fallback = makeBotReply(true, 200, fallbackData);
  assert.equal(fallback.type, "fallback");
  assert.equal(fallback.escalation.url, "https://policies.latrobe.edu.au/");

  html = renderToStaticMarkup(React.createElement(Message, { sender: "bot", messageId: "f", ...fallback }));
  assert.ok(html.includes("fallback-message"), "fallback should have its own style");
  assert.ok(html.includes("No policy answer found"), "fallback should be labelled");
  assert.ok(html.includes('href="https://policies.latrobe.edu.au/"'), "escalation link should be shown");
  assert.ok(!html.includes("Sources"), "a fallback must not show any sources");
  console.log("2. insufficient evidence ...... ok");

  // --- Test 3: a bad escalation link is not shown ---
  const badLink = makeBotReply(true, 200, { ...fallbackData, escalation: { message: "x", url: "https://latrobe.edu.au.evil.test/" } });
  html = renderToStaticMarkup(React.createElement(Message, { sender: "bot", messageId: "b", ...badLink }));
  assert.ok(!html.includes("evil.test"), "non-La Trobe links must not be shown");
  console.log("3. unsafe escalation link ..... ok");

  // --- Test 4: a 400 shows the backend's reason instead of "try again" ---
  const invalid = makeBotReply(false, 400, {
    status: "fallback",
    validation_error: "Provide a question containing 3 to 500 characters, including letters or numbers.",
  });
  assert.equal(invalid.type, "error");
  assert.ok(invalid.message.includes("3 to 500 characters"));
  console.log("4. invalid question (400) ..... ok");

  // --- Test 5: Qwen3 or search being down is an error, not a policy answer ---
  for (const status of [500, 502, 503]) {
    const error = makeBotReply(false, status, { status: "fallback", message: "I could not find enough evidence." });
    assert.equal(error.type, "error");
    // The backend's fallback wording must not leak into a technical error,
    // otherwise it reads like the policies were checked and had no answer.
    assert.ok(!error.message.includes("evidence"));

    html = renderToStaticMarkup(React.createElement(Message, { sender: "bot", messageId: "e", ...error }));
    assert.ok(html.includes("error-message"), "errors should have their own style");
    assert.ok(html.includes("This is not a policy answer"), "errors should say they are not policy answers");
  }
  console.log("5. backend/model failure ...... ok");

  // --- Test 6: can't reach Django at all ---
  const offline = makeConnectionErrorReply();
  assert.equal(offline.type, "error");
  console.log("6. backend unreachable ........ ok");

  console.log("All Task 8 message checks passed.");
} finally {
  await server.close();
}

