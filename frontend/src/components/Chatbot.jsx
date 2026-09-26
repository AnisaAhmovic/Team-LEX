import { useEffect, useRef, useState } from "react";
import Message from "./Message";
import ChatInput from "./ChatInput";
import Disclaimer from "./Disclaimer";
import LexBotIcon from "./LexBotIcon";
import { makeBotReply, makeConnectionErrorReply } from "../botReply";

function Chatbot() {
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isTyping]);

  const handleSendMessage = async (text) => {
    if (isTyping || !text.trim()) return;

    const userMessage = {
      id: crypto.randomUUID(),
      sender: "user",
      message: text,
      time: getCurrentTime(),
    };

    setMessages((previous) => [...previous, userMessage]);
    setIsTyping(true);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 195000);

    try {
      const response = await fetch("/api/answer/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
        signal: controller.signal,
      });

      const data = await response.json();

      // Work out if this is an answer, a fallback or an error (see botReply.js)
      const botMessage = makeBotReply(response.ok, response.status, data);
      botMessage.id = crypto.randomUUID();
      botMessage.sender = "bot";
      botMessage.time = getCurrentTime();

      setMessages((previous) => [...previous, botMessage]);
    } catch {
      // We couldn't reach Django at all, or it didn't send back JSON
      const botMessage = makeConnectionErrorReply();
      botMessage.id = crypto.randomUUID();
      botMessage.sender = "bot";
      botMessage.time = getCurrentTime();

      setMessages((previous) => [...previous, botMessage]);
    } finally {
      clearTimeout(timeout);
      setIsTyping(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  const isWelcomeState = messages.length === 0 && !isTyping;

  return (
    <div className="chatbot">
      <header className="chat-header">
        <div className="chat-header-left">
          <div className="header-avatar" aria-hidden="true">
            <LexBotIcon />
          </div>

          <div className="product-identity">
            <h1>LEX AI</h1>
            <p className="product-subtitle">La Trobe Policy Assistant</p>
            <div className="online-status">
              <span className="online-dot"></span>
              Ready
            </div>
          </div>
        </div>

        <button
          className="clear-button"
          onClick={clearChat}
          disabled={isTyping || messages.length === 0}
          title="Clear conversation"
        >
          Clear
        </button>
      </header>

      <main className={`messages-container ${isWelcomeState ? "welcome-mode" : ""}`}>
        {isWelcomeState && (
          <section className="welcome-state" aria-labelledby="welcome-heading">
            <div className="welcome-bot" aria-hidden="true">
              <LexBotIcon />
            </div>

            <h2 id="welcome-heading">How can I help with La Trobe policy?</h2>

            <p className="welcome-intro">
              Ask a question about University policy and LEX AI will find
              relevant information and show you the sources used.
            </p>

            <div className="example-prompts" aria-label="Example policy questions">
              <div className="example-prompt">
                <span className="example-label">University vehicles</span>
                <span>What are the requirements for driving a University vehicle?</span>
              </div>

              <div className="example-prompt">
                <span className="example-label">Workplace behaviour</span>
                <span>What does the policy say about workplace behaviour?</span>
              </div>

              <div className="example-prompt">
                <span className="example-label">Health &amp; safety</span>
                <span>What are my health and safety responsibilities?</span>
              </div>
            </div>
          </section>
        )}

        {messages.map((message) => (
          <Message
            key={message.id}
            messageId={message.id}
            claims={message.claims}
            sources={message.sources}
            type={message.type}
            escalation={message.escalation}
            message={message.message}
            sender={message.sender}
            time={message.time}
          />
        ))}

        {isTyping && (
          <div className="message-row bot-row">
            <div className="bot-avatar" aria-hidden="true">
              <LexBotIcon />
            </div>

            <div className="typing-indicator" aria-label="LEX AI is processing your question">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef}></div>
      </main>

      {/* Outside the message list so it never scrolls away */}
      <Disclaimer />

      <p className="privacy-notice">
        Questions and responses are logged locally for quality review. Avoid
        sharing personal information.
      </p>

      <ChatInput
        onSend={handleSendMessage}
        disabled={isTyping}
      />
    </div>
  );
}

function getCurrentTime() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default Chatbot;
