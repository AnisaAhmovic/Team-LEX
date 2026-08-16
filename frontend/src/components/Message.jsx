function Message({ message, sender, time }) {
  const isBot = sender === "bot";

  return (
    <div className={`message-row ${isBot ? "bot-row" : "user-row"}`}>
      {isBot && <div className="bot-avatar">🤖</div>}

      <div className={`message ${isBot ? "bot-message" : "user-message"}`}>
        <p>{message}</p>
        {time && <span className="message-time">{time}</span>}
      </div>
    </div>
  );
}

export default Message;
