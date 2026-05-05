import React, { useState, useRef } from 'react';
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

const TCSLogo = () => (
  <img
    src="https://www.tcs.com/content/dam/global-tcs/en/images/home/tcs-logo-1.svg"
    alt="TCS Logo"
    style={{ height: '36px', width: 'auto' }}
  />
);

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
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const dragCounter = useRef(0);

  const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const handleSend = async (message) => {
    const newMessage = { message, sender: "user", direction: "outgoing" };
    setMessages(prev => [...prev, newMessage]);
    setIsTyping(true);

    try {
      const response = await axios.post(`${apiUrl}/api/v1/chat`, {
        message,
        conversation_id: conversationId
      });

      if (!conversationId) setConversationId(response.data.conversation_id);

      const assistantMessage = {
        message: response.data.assistant_message.content,
        sender: "assistant",
        direction: "incoming"
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error sending message:", error);
      setMessages(prev => [...prev, {
        message: "Sorry, there was an error processing your request.",
        sender: "system",
        direction: "incoming"
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    dragCounter.current += 1;
    if (dragCounter.current === 1) setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current === 0) setIsDragOver(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    dragCounter.current = 0;
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      setUploadedFiles(prev => [...prev, ...files]);
      const names = files.map(f => f.name).join(', ');
      setMessages(prev => [...prev, {
        message: `Document${files.length > 1 ? 's' : ''} uploaded: ${names}`,
        sender: "system",
        direction: "incoming"
      }]);
    }
  };

  return (
    <div className="page">

      {/* ── Nav ── */}
      <header className="navbar">
        <div className="navbar-inner">
          <div className="brand">
            <TCSLogo />
          </div>
          <span className="brand-sub">Financial Services · Ethical AI Advisor</span>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="hero">
        <div className="hero-inner">
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
        </div>
      </section>

      {/* ── Chat ── */}
      <section className="chat-section">
        <div
          className={`chat-wrapper${isDragOver ? ' drag-over' : ''}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div className="chat-header-bar">
            <span className="chat-status-dot" />
            <span className="chat-header-label">Financial Advisor · Online</span>
          </div>

          {isDragOver && (
            <div className="drag-overlay">
              <svg width="48" height="48" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M26 6L26 34M26 6L18 14M26 6L34 14" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M8 38V42C8 43.1 8.9 44 10 44H42C43.1 44 44 43.1 44 42V38" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              <p className="drag-title">Upload Documents</p>
              <p className="drag-sub">Drop files here to attach them to your conversation</p>
            </div>
          )}

          <div className={`chat-body${isDragOver ? ' chat-body-faded' : ''}`}>
            <MainContainer>
              <ChatContainer>
                <MessageList
                  scrollBehavior="smooth"
                  typingIndicator={isTyping ? <TypingIndicator content="Advisor is typing..." /> : null}
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

          {uploadedFiles.length > 0 && (
            <div className="file-chips">
              {uploadedFiles.map((f, i) => (
                <span key={i} className="file-chip">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                  {f.name}
                </span>
              ))}
            </div>
          )}
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
            <div className="card-icon">&#9888;</div>
            <h3>The Problem</h3>
            <p>
              With the rise of AI, many enterprises deploy LLM-powered chatbots for customer inquiries.
              Most are generic and insufficiently tuned for high-stakes financial situations — generating
              shallow, one-size-fits-all responses during crucial decision-making moments.
            </p>
          </div>

          <div className="about-card">
            <div className="card-icon">&#9906;</div>
            <h3>The Gap</h3>
            <p>
              In investment management, wealth planning, and retirement services, customer decisions are
              inherently value-driven and sensitive. Current systems lack the ability to understand a
              customer's emotional state and whether persuasion is even ethical in that context.
            </p>
          </div>

          <div className="about-card">
            <div className="card-icon">&#10022;</div>
            <h3>Our Approach</h3>
            <p>
              TCS' Banking Chatbot assesses each interaction before responding — distinguishing positive, neutral,
              and negative contexts. In sensitive cases like personal loss or financial hardship, the
              system explicitly avoids persuasion and prioritizes empathy.
            </p>
          </div>

          <div className="about-card">
            <div className="card-icon">&#127970;</div>
            <h3>Focus &amp; Scope</h3>
            <p>
              Initially focused on TCS financial domains — investment, wealth management, and retirement —
              the system is designed to be extensible to broader general-purpose applications while
              maintaining its ethical foundation across all contexts.
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
        <div className="footer-logo"><TCSLogo /></div>
        <p>Built for Tata Consultancy Services · Ethical AI Research Project</p>
        <p className="footer-sub">Grounded in FCA Consumer Duty (2023) · Cialdini's Principles of Influence · Motivational Interviewing</p>
      </footer>

    </div>
  );
}

export default App;
