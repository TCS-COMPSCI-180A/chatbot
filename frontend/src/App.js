import React, { useState } from 'react';
import '@chatscope/chat-ui-kit-styles/dist/default/styles.min.css';
import {
  MainContainer,
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
  TypingIndicator
} from '@chatscope/chat-ui-kit-react';
import axios from 'axios';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    {
      message: "Hello! I'm here to help with your financial questions. How can I assist you today?",
      sender: "assistant",
      direction: "incoming"
    }
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [conversationId, setConversationId] = useState(null);

  const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const handleSend = async (message) => {
    const newMessage = {
      message: message,
      sender: "user",
      direction: "outgoing"
    };
    setMessages([...messages, newMessage]);
    setIsTyping(true);

    try {
      const response = await axios.post(`${apiUrl}/api/v1/chat`, {
        message: message,
        conversation_id: conversationId
      });

      if (!conversationId) {
        setConversationId(response.data.conversation_id);
      }

      const assistantMessage = {
        message: response.data.assistant_message.content,
        sender: "assistant",
        direction: "incoming"
      };

      setMessages([...messages, newMessage, assistantMessage]);

    } catch (error) {
      console.error("Error sending message:", error);

      const errorMessage = {
        message: "Sorry, there was an error processing your request.",
        sender: "system",
        direction: "incoming"
      };
      setMessages([...messages, newMessage, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="page">

      {/* ── Nav ── */}
      <header className="navbar">
        <div className="navbar-inner">
          <div className="brand">
            <span className="brand-icon">⚖</span>
            <span className="brand-name">EthicChat</span>
          </div>
          <span className="brand-sub">TCS Financial Services · AI Advisor</span>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="hero">
        <h1 className="hero-title">Ethical AI Financial Assistant</h1>
        <p className="hero-desc">
          Context-aware, empathetically guided financial conversations —
          powered by responsible AI that knows when to advise and when to simply listen.
        </p>
        <div className="hero-badges">
          <span className="badge">FCA Consumer Duty Compliant</span>
          <span className="badge">Zero Coercive Language</span>
          <span className="badge">Emotion-Aware</span>
        </div>
      </section>

      {/* ── Chat ── */}
      <section className="chat-section">
        <div className="chat-wrapper">
          <div className="chat-header-bar">
            <span className="chat-status-dot" />
            <span className="chat-header-label">Financial Advisor · Online</span>
          </div>
          <div className="chat-body">
            <MainContainer>
              <ChatContainer>
                <MessageList
                  scrollBehavior="smooth"
                  typingIndicator={isTyping ? <TypingIndicator content="Advisor is thinking..." /> : null}
                >
                  {messages.map((msg, i) => (
                    <Message key={i} model={msg} />
                  ))}
                </MessageList>
                <MessageInput
                  placeholder="Ask a financial question..."
                  onSend={handleSend}
                  attachButton={false}
                />
              </ChatContainer>
            </MainContainer>
          </div>
        </div>
      </section>

      {/* ── About ── */}
      <section className="about-section">
        <h2 className="section-title">About This Project</h2>
        <p className="section-subtitle">
          Bridging the gap between business goals and customer wellbeing through ethical, context-sensitive AI.
        </p>

        <div className="about-grid">

          <div className="about-card">
            <div className="card-icon">⚠</div>
            <h3>The Problem</h3>
            <p>
              With the rise of AI, many enterprises deploy LLM-powered chatbots for customer inquiries.
              Most are generic and insufficiently tuned for high-stakes financial situations — generating
              shallow, one-size-fits-all responses during crucial decision-making moments, leading to
              missed opportunities and poor customer experiences.
            </p>
          </div>

          <div className="about-card">
            <div className="card-icon">🧭</div>
            <h3>The Gap</h3>
            <p>
              In investment management, wealth planning, and retirement services, customer decisions are
              inherently value-driven and sensitive. Current systems lack the ability to understand a
              customer's situation, emotional state, and intent — and whether persuasion is appropriate
              or ethical in that context.
            </p>
          </div>

          <div className="about-card">
            <div className="card-icon">✦</div>
            <h3>Our Approach</h3>
            <p>
              EthicChat assesses each interaction before responding — distinguishing positive, neutral,
              and negative contexts. In sensitive cases like personal loss or financial hardship, the
              system explicitly avoids persuasion and prioritizes empathy. When persuasion is appropriate,
              it uses soft, non-coercive framing grounded in transparency.
            </p>
          </div>

          <div className="about-card">
            <div className="card-icon">🏦</div>
            <h3>Focus &amp; Scope</h3>
            <p>
              Initially focused on Tata Consultancy Services' financial domains — investment, wealth
              management, and retirement — the system is designed to be extensible to broader
              general-purpose applications while maintaining its ethical foundation across all contexts.
            </p>
          </div>

        </div>
      </section>

      {/* ── Pipeline ── */}
      <section className="pipeline-section">
        <h2 className="section-title">How It Works</h2>
        <div className="pipeline">
          {[
            { step: "01", label: "Ethics Gate", desc: "Screens for vulnerability signals — bereavement, hardship, high risk" },
            { step: "02", label: "Classifier", desc: "Detects emotion, intent, and business situation using zero-shot AI" },
            { step: "03", label: "Strategy Selector", desc: "Picks the right approach: informational, authority, social proof, or empathy" },
            { step: "04", label: "LLM Generator", desc: "Generates a compliant response via Gemini 2.5 Flash" },
            { step: "05", label: "Critic", desc: "Scores the response for ethical compliance — rewrites once if needed" },
          ].map(({ step, label, desc }) => (
            <div className="pipeline-step" key={step}>
              <div className="step-number">{step}</div>
              <div className="step-content">
                <strong>{label}</strong>
                <span>{desc}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="footer">
        <p>Built for Tata Consultancy Services · Ethical AI Research Project</p>
        <p className="footer-sub">Grounded in FCA Consumer Duty (2023) · Cialdini's Principles of Influence · Motivational Interviewing</p>
      </footer>

    </div>
  );
}

export default App;
