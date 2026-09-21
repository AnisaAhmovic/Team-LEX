import { useEffect, useRef, useState } from "react";
import Message from "./Message";
import ChatInput from "./ChatInput";

function Chatbot() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: "bot",
      message: "Hello! 👋 I'm Lex AI. How can I help you with La Trobe University policies?",
      time: getCurrentTime(),
    },
  ]);

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
      id: crypto.randomUUID(), sender: "user", message: text,
      time: getCurrentTime(),
    };
    setMessages((previous) => [...previous, userMessage]);
    setIsTyping(true);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    try {
      const response = await fetch("/api/answer/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
        signal: controller.signal,
      });
      const data = await response.json();
      const supported = response.ok && data.status === "supported";
      setMessages((previous) => [...previous, {
        id: crypto.randomUUID(), sender: "bot", time: getCurrentTime(),
        message: supported ? data.answer : (
          response.ok ? data.message : "The policy service could not complete this request. Please try again."
        ),
        claims: supported ? data.claims : [],
        sources: supported ? data.sources : [],
      }]);
    } catch {
      setMessages((previous) => [...previous, {
        id: crypto.randomUUID(), sender: "bot", time: getCurrentTime(),
        message: "The policy service could not be reached. Please try again.",
      }]);
    } finally {
      clearTimeout(timeout);
      setIsTyping(false);
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: Date.now(),
        sender: "bot",
        message: "Chat cleared. How can I help you?",
        time: getCurrentTime(),
      },
    ]);
  };

  return (
    <div className="chatbot">
      <header className="chat-header">
        <div className="chat-header-left">
          <div className="header-avatar">🤖</div>

          <div>
            <h1>Lex AI</h1>
            <div className="online-status">
              <span className="online-dot"></span>
              Policy assistant
            </div>
          </div>
        </div>

        <button
          className="clear-button"
          onClick={clearChat}
          disabled={isTyping}
          title="Clear conversation"
        >
          Clear
        </button>
      </header>

      <main className="messages-container">
        {messages.map((message) => (
          <Message
            key={message.id}
            messageId={message.id}
            claims={message.claims}
            sources={message.sources}
            message={message.message}
            sender={message.sender}
            time={message.time}
          />
        ))}

        {isTyping && (
          <div className="message-row bot-row">
            <div className="bot-avatar">🤖</div>

            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef}></div>
      </main>

      <p className="privacy-notice">Questions and responses are logged locally for quality review. Avoid sharing personal information.</p>

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

