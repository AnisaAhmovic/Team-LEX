// verify_messages.mjs
// Task 8 checks: answers, fallbacks and errors must all look different, and an
// error must never look like a policy answer.
//
// Run with:  npm run test:messages

import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({ optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true } });

try {
  const { makeBotReply, makeConnectionErrorReply } = await server.ssrLoadModule("/src/botReply.js");
  const { default: Message } = await server.ssrLoadModule("/src/components/Message.jsx");

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

  let html = renderToStaticMarkup(React.createElement(Message, { sender: "bot", messageId: "f", ...fallback }));
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
