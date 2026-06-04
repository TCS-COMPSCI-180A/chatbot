import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';

const STORAGE_KEY = 'tcs_chatbot_v1';

const TCSLogo = () => (
  <img
    src="https://www.tcs.com/content/dam/global-tcs/en/images/home/tcs-logo-1.svg"
    alt="TCS"
    className="tcs-logo"
  />
);

const IconSidebar = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M9 3v18" />
  </svg>
);

const IconPlus = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5v14M5 12h14" />
  </svg>
);

const IconSend = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
  </svg>
);

const IconPaperclip = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
  </svg>
);

const IconTrash = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6L18 20a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    <path d="M10 11v6M14 11v6" />
  </svg>
);

function loadConversations() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

function groupConversations(conversations) {
  const groups = { Today: [], Yesterday: [], 'Previous 7 Days': [], Older: [] };
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today - 86400000);
  const weekAgo = new Date(today - 6 * 86400000);

  conversations.forEach(conv => {
    const d = new Date(conv.createdAt);
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    if (day >= today) groups.Today.push(conv);
    else if (day >= yesterday) groups.Yesterday.push(conv);
    else if (day >= weekAgo) groups['Previous 7 Days'].push(conv);
    else groups.Older.push(conv);
  });

  return groups;
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

const SUGGESTIONS = [
  'What investment options are best for my retirement?',
  'Help me understand my risk tolerance',
  'Explain current market conditions to me',
  'Review my portfolio allocation strategy',
];

function App() {
  const [conversations, setConversations] = useState(loadConversations);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isDragOver, setIsDragOver] = useState(false);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const dragCounter = useRef(0);

  const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  }, [inputValue]);

  const startNewChat = () => {
    setActiveId(null);
    setMessages([]);
    setUploadedFiles([]);
    setInputValue('');
  };

  const selectConversation = (id) => {
    const conv = conversations.find(c => c.id === id);
    setActiveId(id);
    setMessages(conv?.messages || []);
    setUploadedFiles([]);
    setInputValue('');
  };

  const deleteConversation = (e, id) => {
    e.stopPropagation();
    setConversations(prev => prev.filter(c => c.id !== id));
    if (activeId === id) {
      setActiveId(null);
      setMessages([]);
    }
  };

  const handleSend = async () => {
    const message = inputValue.trim();
    if (!message && uploadedFiles.length === 0) return;

    setInputValue('');

    const userMsg = {
      message: message || `Uploaded: ${uploadedFiles.map(f => f.name).join(', ')}`,
      sender: 'user',
      direction: 'outgoing',
      timestamp: new Date().toISOString(),
    };

    const isNewConv = activeId === null;
    const currentId = isNewConv ? Date.now() : activeId;
    const updatedMessages = [...messages, userMsg];

    setMessages(updatedMessages);
    setIsTyping(true);

    if (isNewConv) {
      const newConv = {
        id: currentId,
        title: (message || 'Document upload').substring(0, 60),
        messages: updatedMessages,
        createdAt: new Date().toISOString(),
      };
      setConversations(prev => [newConv, ...prev]);
      setActiveId(currentId);
    } else {
      setConversations(prev =>
        prev.map(c => c.id === currentId ? { ...c, messages: updatedMessages } : c)
      );
    }

    try {
      let response;
      if (uploadedFiles.length > 0) {
        const formData = new FormData();
        formData.append('message', message);
        formData.append('conversation_id', currentId);
        uploadedFiles.forEach(f => formData.append('document', f));
        response = await axios.post(`${apiUrl}/api/v1/chat`, formData);
        setUploadedFiles([]);
      } else {
        response = await axios.post(`${apiUrl}/api/v1/chat`, {
          message,
          conversation_id: currentId,
        });
      }

      const assistantMsg = {
        message: response.data.assistant_message.content,
        sender: 'assistant',
        direction: 'incoming',
        timestamp: new Date().toISOString(),
      };
      const finalMessages = [...updatedMessages, assistantMsg];
      setMessages(finalMessages);
      setConversations(prev =>
        prev.map(c => c.id === currentId ? { ...c, messages: finalMessages } : c)
      );
    } catch {
      const errMsg = {
        message: 'Sorry, there was an error processing your request.',
        sender: 'system',
        direction: 'incoming',
        timestamp: new Date().toISOString(),
      };
      const finalMessages = [...updatedMessages, errMsg];
      setMessages(finalMessages);
      setConversations(prev =>
        prev.map(c => c.id === currentId ? { ...c, messages: finalMessages } : c)
      );
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
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
  const handleDragOver = (e) => e.preventDefault();
  const handleDrop = (e) => {
    e.preventDefault();
    dragCounter.current = 0;
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) setUploadedFiles(prev => [...prev, ...files]);
  };

  const grouped = groupConversations(conversations);

  const inputBox = (
    <div className="input-box">
      <textarea
        ref={textareaRef}
        className="chat-textarea"
        placeholder="Ask a banking question..."
        value={inputValue}
        onChange={e => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
      />
      <div className="input-actions">
        <label className="icon-btn" title="Attach file">
          <IconPaperclip />
          <input
            type="file"
            hidden
            multiple
            onChange={e => setUploadedFiles(prev => [...prev, ...Array.from(e.target.files)])}
          />
        </label>
        <button
          className={`send-btn${inputValue.trim() || uploadedFiles.length > 0 ? ' send-btn-active' : ''}`}
          onClick={handleSend}
          disabled={!inputValue.trim() && uploadedFiles.length === 0}
          title="Send"
        >
          <IconSend />
        </button>
      </div>
    </div>
  );

  const fileChips = uploadedFiles.length > 0 && (
    <div className="file-chips">
      {uploadedFiles.map((f, i) => (
        <span key={i} className="file-chip">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          {f.name}
          <button
            className="chip-remove"
            onClick={() => setUploadedFiles(prev => prev.filter((_, j) => j !== i))}
          >×</button>
        </span>
      ))}
    </div>
  );

  return (
    <div className="app-shell">

      {/* ── Sidebar ── */}
      <aside className={`sidebar${sidebarOpen ? '' : ' sidebar-closed'}`}>
        <div className="sidebar-top">
          <button className="icon-btn" onClick={() => setSidebarOpen(false)} title="Collapse sidebar">
            <IconSidebar />
          </button>
          <button className="icon-btn" onClick={startNewChat} title="New chat">
            <IconPlus />
          </button>
        </div>

        <div className="sidebar-brand">
          <TCSLogo />
          <span className="sidebar-brand-sub">Banking Services · Ethical AI</span>
        </div>

        <nav className="conv-nav">
          {Object.entries(grouped).map(([group, convs]) =>
            convs.length > 0 && (
              <div key={group} className="conv-group">
                <span className="conv-group-label">{group}</span>
                {convs.map(conv => (
                  <button
                    key={conv.id}
                    className={`conv-item${activeId === conv.id ? ' conv-item-active' : ''}`}
                    onClick={() => selectConversation(conv.id)}
                  >
                    <span className="conv-title">{conv.title}</span>
                    <span
                      className="conv-delete"
                      onClick={(e) => deleteConversation(e, conv.id)}
                      title="Delete"
                    >
                      <IconTrash />
                    </span>
                  </button>
                ))}
              </div>
            )
          )}
          {conversations.length === 0 && (
            <p className="conv-empty">No conversations yet.<br />Start chatting below.</p>
          )}
        </nav>

        <div className="sidebar-footer">
          <span className="sidebar-footer-text">FCA Consumer Duty Compliant</span>
        </div>
      </aside>

      {/* ── Main ── */}
      <main
        className="main-area"
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {!sidebarOpen && (
          <div className="topbar">
            <button className="icon-btn" onClick={() => setSidebarOpen(true)} title="Open sidebar">
              <IconSidebar />
            </button>
            <button className="icon-btn" onClick={startNewChat} title="New chat">
              <IconPlus />
            </button>
          </div>
        )}

        {isDragOver && (
          <div className="drag-overlay">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <p className="drag-title">Drop to Upload</p>
            <p className="drag-sub">Attach documents to your conversation</p>
          </div>
        )}

        {activeId === null ? (

          /* ── Landing ── */
          <div className="landing">
            <div className="landing-logo">
              <TCSLogo />
            </div>
            <h1 className="landing-greeting">{getGreeting()}</h1>
            <p className="landing-sub">How can I help with your banking questions today?</p>

            <div className="landing-input-wrap">
              {fileChips}
              {inputBox}
              <p className="input-hint">Enter to send · Shift+Enter for new line</p>
            </div>

            <div className="suggestions">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  className="suggestion-chip"
                  onClick={() => {
                    setInputValue(s);
                    textareaRef.current?.focus();
                  }}
                >
                  {s}
                </button>
              ))}
            </div>

            <div className="landing-badges">
              <span className="badge">FCA Consumer Duty</span>
              <span className="badge">Zero Coercive Language</span>
              <span className="badge">Emotion-Aware</span>
            </div>
          </div>

        ) : (

          /* ── Chat View ── */
          <div className="chat-view">
            <div className="messages-scroll">
              <div className="messages-inner">
                {messages.map((msg, i) => (
                  <div key={i} className={`msg-row msg-${msg.sender}`}>
                    {msg.sender !== 'user' && (
                      <div className="msg-avatar">
                        {msg.sender === 'assistant' ? (
                          <TCSLogo />
                        ) : (
                          <span style={{ fontSize: '0.75rem' }}>!</span>
                        )}
                      </div>
                    )}
                    <div className={`msg-bubble msg-bubble-${msg.sender}`}>
                      {msg.message.split('\n').map((line, j, arr) => (
                        <React.Fragment key={j}>
                          {line}
                          {j < arr.length - 1 && <br />}
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                ))}

                {isTyping && (
                  <div className="msg-row msg-assistant">
                    <div className="msg-avatar">
                      <TCSLogo />
                    </div>
                    <div className="msg-bubble msg-bubble-typing">
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="chat-input-bar">
              <div className="chat-input-inner">
                {fileChips}
                {inputBox}
              </div>
            </div>
          </div>

        )}
      </main>
    </div>
  );
}

export default App;