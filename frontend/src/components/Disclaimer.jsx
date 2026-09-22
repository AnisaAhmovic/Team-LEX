// Disclaimer.jsx
// Task 9: the AI disclaimer.
//
// Chatbot.jsx puts this outside the scrolling message list, so it stays on
// screen before the first question and after every answer.
//
// DRAFT WORDING - the team/client still needs to approve it before release.

const POLICY_LIBRARY_URL = "https://policies.latrobe.edu.au/";

function Disclaimer() {
  return (
    <aside className="disclaimer" role="note" aria-label="AI disclaimer">
      <p>
        <strong>AI-assisted, not legal advice.</strong>{" "}
        Lex uses AI to help you find and understand La Trobe University
        policies, and it can make mistakes. The official policy is always the
        source of truth, so check the{" "}
        <a href={POLICY_LIBRARY_URL} target="_blank" rel="noopener noreferrer">
          La Trobe Policy Library
        </a>{" "}
        or contact the relevant University office.
      </p>
    </aside>
  );
}

export default Disclaimer;
