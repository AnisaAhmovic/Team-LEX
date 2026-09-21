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

function Message({ message, sender, time, messageId, claims = [], sources = [] }) {
  const isBot = sender === "bot";
  return (
    <div className={`message-row ${isBot ? "bot-row" : "user-row"}`}>
      {isBot && <div className="bot-avatar">🤖</div>}
      <div className={`message ${isBot ? "bot-message" : "user-message"}`}>
        {isBot && claims.length > 0 ? claims.map((claim) => (
          <p key={claim.claim_id}>
            {claim.text}{" "}
            {claim.source_ids.map((id) => (
              <a className="claim-citation" key={id} href={`#source-${messageId}-${id}`} aria-label={`View source ${id}`}>[{id}]</a>
            ))}
          </p>
        )) : <p>{message}</p>}
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
        {time && <span className="message-time">{time}</span>}
      </div>
    </div>
  );
}

export default Message;
