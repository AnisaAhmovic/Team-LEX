// Render the real component to verify citation navigation and safe external links.
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({ optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true } });
try {
  const { default: Message } = await server.ssrLoadModule("/src/components/Message.jsx");
  const html = renderToStaticMarkup(React.createElement(Message, {
    sender: "bot", messageId: "example", message: "A cited answer.",
    claims: [{ claim_id: "C1", text: "A supported statement.", source_ids: ["S1", "S2"], support: [
      { source_id: "S1", quote: "First exact excerpt." },
      { source_id: "S2", quote: "Second exact excerpt." },
    ] }],
    sources: [
      { source_id: "S1", policy_title: "Assessment Policy", section: "Section 2", source_url: "https://policies.latrobe.edu.au/document/view.php?id=216", effective_date: "7th September 2021", version: null },
      { source_id: "S2", policy_title: "<script>untrusted title</script>", section: "Section 3", source_url: "https://latrobe.edu.au.evil.test" },
    ],
  }));
  assert.ok(html.includes('href="#source-example-S1"'));
  assert.ok(html.includes('id="source-example-S1"'));
  assert.ok(html.includes('href="#source-example-S2"'));
  assert.ok(html.includes('href="https://policies.latrobe.edu.au/document/view.php?id=216"'));
  assert.ok(html.includes("7th September 2021"));
  assert.ok(html.includes("Second exact excerpt."));
  assert.ok(!html.includes('href="https://latrobe.edu.au.evil.test"'));
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("Version: null"));
  console.log("Citation rendering and unsafe-link checks passed.");
} finally {
  await server.close();
}
