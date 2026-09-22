// verify_disclaimer.mjs
// Task 9 checks: the AI disclaimer says the right things and always stays on
// screen.
//
// Run with:  npm run test:disclaimer

import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({ optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true } });

try {
  const { default: Disclaimer } = await server.ssrLoadModule("/src/components/Disclaimer.jsx");
  const { default: Chatbot } = await server.ssrLoadModule("/src/components/Chatbot.jsx");
  const { default: Message } = await server.ssrLoadModule("/src/components/Message.jsx");

  const disclaimer = renderToStaticMarkup(React.createElement(Disclaimer));
  const text = disclaimer.toLowerCase();

  // --- Test 1: it says Lex is AI-assisted ---
  assert.ok(text.includes("ai-assisted"), "must say the information is AI-assisted");
  assert.ok(text.includes("uses ai"), "must say Lex uses AI");
  console.log("1. says it is AI-assisted ........... ok");

  // --- Test 2: it says it is not legal advice ---
  assert.ok(text.includes("not legal advice"), "must say it is not legal advice");
  console.log("2. says not legal advice ............ ok");

  // --- Test 3: the official policy is the source of truth, with a real link ---
  assert.ok(text.includes("source of truth"), "must say the official policy is the source of truth");
  assert.ok(disclaimer.includes('href="https://policies.latrobe.edu.au/"'), "must link to the Policy Library");
  assert.ok(disclaimer.includes('rel="noopener noreferrer"'), "external link must be safe");
  console.log("3. points to the official policy ... ok");

  // --- Test 4: screen readers can find it ---
  assert.ok(disclaimer.includes('role="note"'));
  assert.ok(disclaimer.includes('aria-label="AI disclaimer"'));
  console.log("4. accessible label ................ ok");

  // --- Test 5: it is on the page before any question is asked ---
  const page = renderToStaticMarkup(React.createElement(Chatbot));
  assert.ok(page.includes('class="disclaimer"'), "disclaimer must be on the chat page");
  console.log("5. shown before any question ....... ok");

  // --- Test 6: it is OUTSIDE the scrolling message list ---
  // The messages are inside <main>. If the disclaimer comes after </main> it
  // can't scroll away, so it stays visible after every answer and fallback.
  const endOfMessages = page.indexOf("</main>");
  const disclaimerPosition = page.indexOf('class="disclaimer"');
  assert.ok(endOfMessages > 0, "message list should be a <main> element");
  assert.ok(disclaimerPosition > endOfMessages, "disclaimer must not be inside the scrolling message list");
  console.log("6. stays visible after answers ..... ok");

  // --- Test 7: fallbacks still give their own Policy Library guidance ---
  const fallback = renderToStaticMarkup(React.createElement(Message, {
    sender: "bot", messageId: "f", type: "fallback",
    message: "I could not find enough current, authoritative La Trobe policy evidence to answer that question.",
    escalation: { message: "Check the official La Trobe Policy Library.", url: "https://policies.latrobe.edu.au/" },
  }));
  assert.ok(fallback.includes("Open the La Trobe Policy Library"), "fallback must keep its guidance link");
  console.log("7. fallback keeps its guidance ..... ok");

  console.log("All Task 9 disclaimer checks passed.");
} finally {
  await server.close();
}
