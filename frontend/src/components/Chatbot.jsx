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

  function getBotResponse(userMessage) {
    const message = userMessage.toLowerCase();

    if (message.includes("hello") || message.includes("hi")) {
      return "Hello! 👋 How can I help you today?";
    }

    if (message.includes("lex")) {
      return "I'm Lex AI, a prototype assistant for questions about La Trobe University policies.";
    }

    if (message.includes("help")) {
      return "Sure! Ask me a question and I'll do my best to help.";
    }

    return "Thanks for your message! Once the Django backend is connected, I'll be able to provide a proper response.";
  }

  const handleSendMessage = (text) => {
    const userMessage = {
      id: Date.now(),
      sender: "user",
      message: text,
      time: getCurrentTime(),
    };

    setMessages((previousMessages) => [
      ...previousMessages,
      userMessage,
    ]);

    setIsTyping(true);

    // Temporary fake response.
    // This will eventually be replaced with the Django API request.
    setTimeout(() => {
      const botMessage = {
        id: Date.now() + 1,
        sender: "bot",
        message: getBotResponse(text),
        time: getCurrentTime(),
      };

      setMessages((previousMessages) => [
        ...previousMessages,
        botMessage,
      ]);

      setIsTyping(false);
    }, 1000);
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
              Online
            </div>
          </div>
        </div>

        <button
          className="clear-button"
          onClick={clearChat}
          title="Clear conversation"
        >
          Clear
        </button>
      </header>

      <main className="messages-container">
        {messages.map((message) => (
          <Message
            key={message.id}
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
