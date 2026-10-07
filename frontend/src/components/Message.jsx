import LexBotIcon from "./LexBotIcon";

function authoritativeUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password &&
      (!url.port || url.port === "443") &&
      (url.hostname === "latrobe.edu.au" || url.hostname.endsWith(".latrobe.edu.au"));
  } catch {
    return false;
  }
}

function Message({ message, sender, time, messageId, claims = [], sources = [], type, escalation, assurance }) {
  const isBot = sender === "bot";

  // Pick the style for the bubble. Fallbacks and errors look different from
  // real answers so nobody mistakes them for policy advice.
  let bubbleClass = "message";
  if (isBot) {
    bubbleClass = bubbleClass + " bot-message";
  } else {
    bubbleClass = bubbleClass + " user-message";
  }
  if (type === "fallback") {
    bubbleClass = bubbleClass + " fallback-message";
  }
  if (type === "error") {
    bubbleClass = bubbleClass + " error-message";
  }

  // Only show the Policy Library link if it really is a La Trobe link
  let showEscalation = false;
  if (type === "fallback" && escalation && authoritativeUrl(escalation.url)) {
    showEscalation = true;
  }

  return (
    <div className={`message-row ${isBot ? "bot-row" : "user-row"}`}>
      {isBot && <div className="bot-avatar" aria-hidden="true"><LexBotIcon /></div>}
      <div className={bubbleClass}>
        {type === "fallback" && <strong className="message-label">No policy answer found</strong>}
        {type === "error" && <strong className="message-label">Something went wrong. This is not a policy answer.</strong>}
        {isBot && claims.length > 0 ? claims.map((claim) => (
          <p key={claim.claim_id}>
            {claim.text}{" "}
            {claim.source_ids.map((id) => (
              <a className="claim-citation" key={id} href={`#source-${messageId}-${id}`} aria-label={`View source ${id}`}>[{id}]</a>
            ))}
          </p>
        )) : <p>{message}</p>}
        {isBot && type === "answer" && assurance && (
          <section className="answer-checks" aria-label="Answer checks">
            <strong>Answer checks <span aria-hidden="true">{"\u2713"}</span></strong>

            <div className="answer-check">
              <span aria-hidden="true">{"\u2713"}</span>{" "}
              <strong>Question coverage:</strong>{" "}
              {assurance.question_coverage?.percentage != null ? (
                <>
                  <strong>{assurance.question_coverage.percentage}%</strong>
                  {" \u2014 "}
                  {assurance.question_coverage.covered} of {assurance.question_coverage.enforced} verified requirements addressed
                </>
              ) : assurance.question_coverage?.enforced === 0 ? (
                <>Requirement not automatically assessed</>
              ) : (
                <>
                  {assurance.question_coverage?.covered ?? 0} verified requirements addressed
                  {assurance.question_coverage?.unknown > 0 &&
                    <>{" \u00B7 "}{assurance.question_coverage.unknown} not automatically assessed</>}
                </>
              )}
            </div>

            {assurance.supported_by_current_policy && (
              <div className="answer-check"><span aria-hidden="true">{"\u2713"}</span> Supported by current policy</div>
            )}
            {assurance.policy_conditions_preserved && (
              <div className="answer-check"><span aria-hidden="true">{"\u2713"}</span> Policy conditions preserved</div>
            )}
            {assurance.sources_verified && (
              <div className="answer-check"><span aria-hidden="true">{"\u2713"}</span> Sources verified</div>
            )}
          </section>
        )}
        {isBot && sources.length > 0 && (
          <section className="policy-sources" aria-label="Policy sources">
            <strong>Sources</strong>
            <ul>
              {sources.map((source) => (
                <li id={`source-${messageId}-${source.source_id}`} key={source.source_id}>
                  <span>[{source.source_id}] </span>
                  {authoritativeUrl(source.source_url) ? (
                    <a href={source.source_url} target="_blank" rel="noopener noreferrer">{source.policy_title}</a>
                  ) : <span>{source.policy_title}</span>}
                  <div>{[source.section, source.subsection, source.topic, source.subtopic].filter(Boolean).filter((v, i, values) => values.indexOf(v) === i).join(" / ")}</div>
                  {source.paragraph_start != null && <div>Paragraphs {source.paragraph_start}{source.paragraph_end !== source.paragraph_start ? `–${source.paragraph_end}` : ""}</div>}
                  <div className="source-currency">
                    {[
                      source.status && `Recorded status: ${source.status}`,
                      source.effective_date && `Effective: ${source.effective_date}`,
                      source.review_date && `Review: ${source.review_date}`,
                      source.version != null && `Version: ${source.version}`,
                    ].filter(Boolean).join(" · ")}
                  </div>
                  <details>
                    <summary>Supporting excerpts</summary>
                    {claims.flatMap((claim) => claim.support.filter((s) => s.source_id === source.source_id).map((s, i) => (
                      <blockquote key={`${claim.claim_id}-${i}`}>{s.quote}</blockquote>
                    )))}
                  </details>
                </li>
              ))}
            </ul>
          </section>
        )}
        {showEscalation && (
          <p className="escalation">
            {escalation.message}{" "}
            <a href={escalation.url} target="_blank" rel="noopener noreferrer">Open the La Trobe Policy Library</a>
          </p>
        )}
        {time && <span className="message-time">{time}</span>}
      </div>
    </div>
  );
}

export default Message;
