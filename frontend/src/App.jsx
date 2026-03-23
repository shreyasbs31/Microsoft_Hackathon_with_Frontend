import { useState, useEffect, useRef } from 'react';
import './index.css';

// Generate UUID
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

// Format time
function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// Scammer Scripts Data
const SCAMMER_SCRIPTS = [
  {
    id: 'bank_fraud',
    icon: 'BNK',
    label: 'BANK FRAUD',
    turns: [
      "URGENT: Your SBI account has been compromised. Your account will be blocked in 2 hours. Share your account number and OTP immediately to verify your identity.",
      "I'm sorry we can't provide a public line, but you can reach us securely at +91-9876543210 - please send your account number and OTP immediately.",
      "The issue is being processed by our Mumbai Main Branch - to stop the block, please send your account number 1234567890123456 and the OTP you just received.",
      "Your case reference number is REF-2023-98765; please send your account number and OTP right away to avoid the block.",
      "Kindly email your verification documents to verification@fakebank.com along with your account number and OTP.",
    ]
  },
  {
    id: 'kyc_fraud',
    icon: 'KYC',
    label: 'KYC FRAUD',
    turns: [
      "URGENT: Your Aadhaar eKYC has expired. Your bank account will be BLOCKED in 24 hours. Call us at +91-8876543210 to re-verify.",
      "I am Officer Priya from the UIDAI helpdesk. Your account shows incomplete KYC. Please share your Aadhaar and OTP.",
      "To avoid the freeze, pay KYC updating fee of Rs.500 via UPI: uidai.verify@ybl.",
    ]
  },
  {
    id: 'lottery_fraud',
    icon: 'LTR',
    label: 'LOTTERY FRAUD',
    turns: [
      "CONGRATULATIONS! You have won Rs 50,00,000 in the National Digital India Lottery 2024! Call +91-9988776655 to claim.",
      "I am Mr. Vikram from the National Lottery Board. To transfer your prize, I need your bank account details.",
    ]
  },
];

export default function App() {
  // State
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [sessionData, setSessionData] = useState({
    status: 'NEUTRAL',
    scamType: null,
    turnCount: 0,
    maxTurns: 10,
    confidenceLevel: null,
    intelligence: {
      phoneNumbers: [],
      bankAccounts: [],
      upiIds: [],
      urls: [],
      emailAddresses: [],
      ifscCodes: [],
      caseIds: [],
      policyNumbers: [],
      orderNumbers: [],
      suspiciousKeywords: [],
    },
    agentNotes: '',
  });
  const [logs, setLogs] = useState([]);
  const [showResults, setShowResults] = useState(false);
  const [results, setResults] = useState(null);
  const [activeNav, setActiveNav] = useState('overview');
  const [showChat, setShowChat] = useState(false);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Initialize session
  useEffect(() => {
    initSession();
  }, []);

  // Track mouse
  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const initSession = () => {
    const newSessionId = generateUUID();
    setSessionId(newSessionId);
    setMessages([]);
    setSessionData({
      status: 'NEUTRAL',
      scamType: null,
      turnCount: 0,
      maxTurns: 10,
      confidenceLevel: null,
      intelligence: {
        phoneNumbers: [],
        bankAccounts: [],
        upiIds: [],
        urls: [],
        emailAddresses: [],
        ifscCodes: [],
        caseIds: [],
        policyNumbers: [],
        orderNumbers: [],
        suspiciousKeywords: [],
      },
      agentNotes: '',
    });
    setLogs([{ time: new Date(), type: 'SYSTEM', message: '» System initialized. Awaiting input...' }]);
    setShowResults(false);
    setResults(null);
  };

  const addLog = (type, message) => {
    setLogs(prev => [...prev.slice(-19), { time: new Date(), type, message }]);
  };

  const sendMessage = async (text) => {
    if (!text.trim() || isSending || sessionData.turnCount >= sessionData.maxTurns) return;

    setIsSending(true);
    setInputValue('');

    const scammerMsg = { role: 'scammer', text: text.trim(), time: new Date() };
    setMessages(prev => [...prev, scammerMsg]);
    addLog('INPUT', `» Scammer message received [${text.length} chars]`);

    setIsTyping(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          message: text.trim(),
          conversationHistory: messages.map(m => ({
            sender: m.role === 'scammer' ? 'scammer' : 'user',
            text: m.text
          })),
          language: 'English',
        }),
      });

      const data = await response.json();
      setIsTyping(false);

      if (data.status === 'success') {
        if (data.sessionId) setSessionId(data.sessionId);

        const agentMsg = { role: 'agent', text: data.reply, time: new Date() };
        setMessages(prev => [...prev, agentMsg]);
        addLog('OUTPUT', `» Agent response generated [${data.reply.length} chars]`);

        if (data.session) {
          setSessionData(prev => ({
            ...prev,
            status: data.session.status || prev.status,
            scamType: data.session.scamType || prev.scamType,
            turnCount: data.session.turnCount || prev.turnCount,
            confidenceLevel: data.session.confidenceLevel || prev.confidenceLevel,
            intelligence: data.session.intelligence || prev.intelligence,
            agentNotes: data.session.agentNotes || prev.agentNotes,
          }));

          if (data.session.status === 'HONEYPOT') {
            addLog('ALERT', '» SCAM DETECTED - Intelligence extraction active');
          }
        }
      } else {
        setMessages(prev => [...prev, { role: 'agent', text: 'Error processing message.', time: new Date() }]);
        addLog('ERROR', '» Processing error occurred');
      }
    } catch (err) {
      setIsTyping(false);
      setMessages(prev => [...prev, { role: 'agent', text: 'Connection error. Please try again.', time: new Date() }]);
      addLog('ERROR', '» Connection error');
    }

    setIsSending(false);
    inputRef.current?.focus();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(inputValue);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputValue);
    }
  };

  const viewResults = async () => {
    if (sessionData.turnCount < sessionData.maxTurns) return;

    try {
      const response = await fetch(`/api/session/${sessionId}/results`);
      const data = await response.json();

      if (data.status === 'success' && data.results) {
        setResults(data.results);
        setShowResults(true);
      }
    } catch (err) {
      console.error('Failed to load results');
    }
  };

  const getTotalIntel = () => {
    return Object.values(sessionData.intelligence).reduce((sum, arr) => sum + (arr?.length || 0), 0);
  };

  const getIntelCount = (field) => {
    return sessionData.intelligence[field]?.length || 0;
  };

  // Chart data for traffic analysis
  const chartData = [
    { label: 'T1', value: sessionData.turnCount >= 1 ? 75 : 0 },
    { label: 'T2', value: sessionData.turnCount >= 2 ? 45 : 0 },
    { label: 'T3', value: sessionData.turnCount >= 3 ? 85 : 0 },
    { label: 'T4', value: sessionData.turnCount >= 4 ? 55 : 0 },
    { label: 'T5', value: sessionData.turnCount >= 5 ? 90 : 0 },
    { label: 'T6', value: sessionData.turnCount >= 6 ? 60 : 0 },
    { label: 'T7', value: sessionData.turnCount >= 7 ? 70 : 0 },
    { label: 'T8', value: sessionData.turnCount >= 8 ? 80 : 0 },
  ];

  return (
    <div className="blueprint-app">
      {/* Coordinate Tracker */}
      <div className="coord-tracker">
        <div className="coord-group">
          <span className="coord-label">LAT</span>
          <span className="coord-value">28.6139</span>
        </div>
        <div className="coord-group">
          <span className="coord-label">LNG</span>
          <span className="coord-value">77.2090</span>
        </div>
        <div className="coord-separator" />
        <div className="coord-group">
          <span className="coord-label">X</span>
          <span className="coord-value">{mousePos.x.toString().padStart(4, '0')}</span>
        </div>
        <div className="coord-group">
          <span className="coord-label">Y</span>
          <span className="coord-value">{mousePos.y.toString().padStart(4, '0')}</span>
        </div>
      </div>

      {/* Header */}
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <div className="logo-box">
              <div className="logo-inner">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                  <path d="M2 17l10 5 10-5"/>
                  <path d="M2 12l10 5 10-5"/>
                </svg>
              </div>
              <span className="corner-mark tl">+</span>
              <span className="corner-mark br">+</span>
            </div>
            <div className="logo-text">
              <h1>PROJECT GENESIS</h1>
              <span className="logo-subtitle">// SCAM DETECTION SYSTEM v2.0</span>
            </div>
          </div>
        </div>

        <div className="header-right">
          <div className="status-pill">
            <div className="status-dot" />
            <span>ACTIVE</span>
          </div>
          <div className="session-id">
            <span className="session-label">SESSION //</span>
            <span className="session-value">{sessionId?.substring(0, 8).toUpperCase() || '--------'}</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="main-container">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-header">
            <span className="sidebar-title">// NAVIGATION</span>
          </div>
          <nav className="nav-menu">
            <div
              className={`nav-item ${activeNav === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveNav('overview')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="7" height="7"/>
                <rect x="14" y="3" width="7" height="7"/>
                <rect x="3" y="14" width="7" height="7"/>
                <rect x="14" y="14" width="7" height="7"/>
              </svg>
              <span>Overview</span>
            </div>
            <div
              className={`nav-item ${activeNav === 'analytics' ? 'active' : ''}`}
              onClick={() => setActiveNav('analytics')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M18 20V10M12 20V4M6 20v-6"/>
              </svg>
              <span>Analytics</span>
            </div>
            <div
              className={`nav-item ${activeNav === 'resources' ? 'active' : ''}`}
              onClick={() => setActiveNav('resources')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <ellipse cx="12" cy="5" rx="9" ry="3"/>
                <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
              </svg>
              <span>Resources</span>
            </div>
            <div
              className={`nav-item ${activeNav === 'config' ? 'active' : ''}`}
              onClick={() => setActiveNav('config')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
              </svg>
              <span>Configuration</span>
            </div>
          </nav>
          <div className="sidebar-footer">
            <span>&lt;--- 200px ---&gt;</span>
          </div>
        </aside>

        {/* Dashboard Area */}
        <main className="dashboard">
          {/* Data Cards Row */}
          <div className="cards-row">
            <div className="data-card">
              <div className="card-header">
                <span className="card-id">DAT-01</span>
                <span className="card-icon">◈</span>
              </div>
              <div className="card-body">
                <div className="card-value">{sessionData.turnCount}</div>
                <div className="card-label">Turn Count</div>
              </div>
              <div className="card-footer">
                <span>/{sessionData.maxTurns} MAX</span>
              </div>
              <span className="corner-mark tl">+</span>
              <span className="corner-mark br">+</span>
            </div>

            <div className="data-card">
              <div className="card-header">
                <span className="card-id">DAT-02</span>
                <span className="card-icon">◈</span>
              </div>
              <div className="card-body">
                <div className="card-value">{getTotalIntel()}</div>
                <div className="card-label">Intel Extracted</div>
              </div>
              <div className="card-footer">
                <span>DATA POINTS</span>
              </div>
              <span className="corner-mark tl">+</span>
              <span className="corner-mark br">+</span>
            </div>

            <div className="data-card highlight">
              <div className="card-header">
                <span className="card-id">DAT-03</span>
                <span className="card-icon">⬡</span>
              </div>
              <div className="card-body">
                <div className="card-value">
                  {sessionData.confidenceLevel
                    ? `${(parseFloat(sessionData.confidenceLevel) * 100).toFixed(1)}%`
                    : '---'}
                </div>
                <div className="card-label">Confidence</div>
              </div>
              <div className="card-footer">
                <span>{sessionData.status}</span>
              </div>
              <span className="corner-mark tl">+</span>
              <span className="corner-mark br">+</span>
            </div>
          </div>

          {/* Main Grid */}
          <div className="dashboard-grid">
            {/* Traffic Analysis Chart */}
            <div className="panel chart-panel">
              <div className="panel-header">
                <span className="panel-title">Traffic Analysis</span>
                <span className="panel-badge">LIVE</span>
              </div>
              <div className="chart-container">
                <div className="chart-bars">
                  {chartData.map((bar, i) => (
                    <div key={i} className="bar-wrapper">
                      <div
                        className="bar"
                        style={{ height: `${bar.value}%` }}
                      />
                      <span className="bar-label">{bar.label}</span>
                    </div>
                  ))}
                </div>
                <div className="chart-y-axis">
                  <span>100</span>
                  <span>50</span>
                  <span>0</span>
                </div>
              </div>
              <span className="corner-mark tl">+</span>
              <span className="corner-mark br">+</span>
            </div>

            {/* System Status */}
            <div className="panel status-panel">
              <div className="panel-header">
                <span className="panel-title">System Status</span>
              </div>
              <div className="status-content">
                <div className="status-item">
                  <div className="status-label">
                    <span>CPU Load</span>
                    <span className="status-value">{Math.min(42 + sessionData.turnCount * 5, 95)}%</span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-fill cpu"
                      style={{ width: `${Math.min(42 + sessionData.turnCount * 5, 95)}%` }}
                    />
                  </div>
                </div>
                <div className="status-item">
                  <div className="status-label">
                    <span>Memory</span>
                    <span className="status-value">{Math.min(68 + sessionData.turnCount * 3, 92)}%</span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-fill memory"
                      style={{ width: `${Math.min(68 + sessionData.turnCount * 3, 92)}%` }}
                    />
                  </div>
                </div>
                <div className="status-item">
                  <div className="status-label">
                    <span>Detection Engine</span>
                    <span className="status-value">ONLINE</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill active" style={{ width: '100%' }} />
                  </div>
                </div>
              </div>
              <span className="corner-mark tl">+</span>
              <span className="corner-mark br">+</span>
            </div>

            {/* Intelligence Panel */}
            <div className="panel intel-panel">
              <div className="panel-header">
                <span className="panel-title">Intelligence Data</span>
                <span className="panel-badge accent">{getTotalIntel()} ITEMS</span>
              </div>
              <div className="intel-grid">
                <div className={`intel-item ${getIntelCount('phoneNumbers') > 0 ? 'has-data' : ''}`}>
                  <span className="intel-label">Phone #</span>
                  <span className="intel-count">{getIntelCount('phoneNumbers')}</span>
                </div>
                <div className={`intel-item ${getIntelCount('bankAccounts') > 0 ? 'has-data' : ''}`}>
                  <span className="intel-label">Bank Acc</span>
                  <span className="intel-count">{getIntelCount('bankAccounts')}</span>
                </div>
                <div className={`intel-item ${getIntelCount('upiIds') > 0 ? 'has-data' : ''}`}>
                  <span className="intel-label">UPI IDs</span>
                  <span className="intel-count">{getIntelCount('upiIds')}</span>
                </div>
                <div className={`intel-item ${getIntelCount('urls') > 0 ? 'has-data' : ''}`}>
                  <span className="intel-label">URLs</span>
                  <span className="intel-count">{getIntelCount('urls')}</span>
                </div>
                <div className={`intel-item ${getIntelCount('emailAddresses') > 0 ? 'has-data' : ''}`}>
                  <span className="intel-label">Emails</span>
                  <span className="intel-count">{getIntelCount('emailAddresses')}</span>
                </div>
                <div className={`intel-item ${getIntelCount('ifscCodes') > 0 ? 'has-data' : ''}`}>
                  <span className="intel-label">IFSC</span>
                  <span className="intel-count">{getIntelCount('ifscCodes')}</span>
                </div>
              </div>
              {sessionData.scamType && (
                <div className="scam-type-badge">
                  <span>Detected: {sessionData.scamType}</span>
                </div>
              )}
              <span className="corner-mark tl">+</span>
              <span className="corner-mark br">+</span>
            </div>

            {/* System Logs */}
            <div className="panel logs-panel">
              <div className="panel-header">
                <span className="panel-title">System Logs</span>
                <span className="panel-badge">STREAM</span>
              </div>
              <div className="logs-content">
                {logs.map((log, i) => (
                  <div key={i} className={`log-entry ${log.type.toLowerCase()}`}>
                    <span className="log-time">{formatTime(log.time)}</span>
                    <span className={`log-type ${log.type.toLowerCase()}`}>[{log.type}]</span>
                    <span className="log-msg">{log.message}</span>
                  </div>
                ))}
              </div>
              <span className="corner-mark tl">+</span>
              <span className="corner-mark br">+</span>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="actions-bar">
            <div className="actions-left">
              <button className="action-btn" onClick={() => setShowChat(!showChat)}>
                <span className="btn-icon">◉</span>
                <span>{showChat ? 'HIDE CHAT' : 'OPEN CHAT'}</span>
              </button>
              <button className="action-btn warning" onClick={initSession}>
                <span className="btn-icon">↻</span>
                <span>NEW SESSION</span>
              </button>
              <button
                className="action-btn accent"
                onClick={viewResults}
                disabled={sessionData.turnCount < sessionData.maxTurns}
              >
                <span className="btn-icon">◈</span>
                <span>GENERATE REPORT</span>
              </button>
            </div>
            <div className="actions-right">
              {SCAMMER_SCRIPTS.map((script) => (
                <button
                  key={script.id}
                  className="action-btn script-btn"
                  onClick={() => {
                    setShowChat(true);
                    setTimeout(() => sendMessage(script.turns[0]), 100);
                  }}
                  disabled={isSending}
                >
                  [{script.icon}]
                </button>
              ))}
            </div>
          </div>

          {/* Alert Banner */}
          {sessionData.status === 'HONEYPOT' && (
            <div className="alert-banner">
              <div className="alert-content">
                <span className="alert-icon">⚠</span>
                <span className="alert-text">ANOMALY DETECTED</span>
                <span className="alert-desc">// Scam pattern identified - Intelligence extraction in progress</span>
              </div>
              <span className="corner-mark tl">+</span>
              <span className="corner-mark br">+</span>
            </div>
          )}
        </main>

        {/* Chat Panel (Expandable) */}
        {showChat && (
          <aside className="chat-panel">
            <div className="chat-header">
              <span className="chat-title">// COMMUNICATION</span>
              <div className="turn-indicator">
                <span className="turn-current">{sessionData.turnCount}</span>
                <span className="turn-max">/{sessionData.maxTurns}</span>
              </div>
              <button className="close-btn" onClick={() => setShowChat(false)}>×</button>
            </div>

            <div className="chat-progress">
              <div
                className="chat-progress-fill"
                style={{ width: `${(sessionData.turnCount / sessionData.maxTurns) * 100}%` }}
              />
            </div>

            <div className="chat-messages">
              {messages.length === 0 ? (
                <div className="chat-welcome">
                  <div className="welcome-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                      <path d="M9 12l2 2 4-4"/>
                    </svg>
                  </div>
                  <h3>HONEYPOT READY</h3>
                  <p>Role-play as a <strong>SCAMMER</strong> to test the detection system.</p>
                  <div className="script-buttons">
                    {SCAMMER_SCRIPTS.map((script) => (
                      <button
                        key={script.id}
                        className="script-btn"
                        onClick={() => sendMessage(script.turns[0])}
                      >
                        [{script.icon}]
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg, i) => (
                    <div key={i} className={`chat-message ${msg.role}`}>
                      <div className="message-header">
                        <span className="message-sender">
                          {msg.role === 'scammer' ? 'SCAMMER // YOU' : 'AI AGENT'}
                        </span>
                        <span className="message-time">{formatTime(msg.time)}</span>
                      </div>
                      <div className="message-body">{msg.text}</div>
                    </div>
                  ))}
                  {isTyping && (
                    <div className="typing-indicator">
                      <div className="typing-dots">
                        <span /><span /><span />
                      </div>
                      <span>AI PROCESSING...</span>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            <form className="chat-input-form" onSubmit={handleSubmit}>
              <div className="input-wrapper">
                <span className="input-prefix">MSG //</span>
                <textarea
                  ref={inputRef}
                  className="chat-input"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Enter scammer message..."
                  disabled={isSending || sessionData.turnCount >= sessionData.maxTurns}
                  rows={1}
                />
                <button
                  type="submit"
                  className="send-btn"
                  disabled={isSending || !inputValue.trim() || sessionData.turnCount >= sessionData.maxTurns}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M22 2L11 13"/>
                    <path d="M22 2l-7 20-4-9-9-4 20-7z"/>
                  </svg>
                </button>
              </div>
              <div className="input-meta">
                <span>{inputValue.length}/2000</span>
                <span>ENTER to send</span>
              </div>
            </form>
          </aside>
        )}
      </div>

      {/* Results Modal */}
      {showResults && results && (
        <div className="modal-overlay" onClick={() => setShowResults(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">[REPORT] INTELLIGENCE SUMMARY</span>
              <button className="modal-close" onClick={() => setShowResults(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="report-grid">
                <div className="report-item">
                  <span className="report-label">Status</span>
                  <span className={`report-value ${results.scamDetected ? 'danger' : 'success'}`}>
                    {results.scamDetected ? 'SCAM DETECTED' : 'CLEAN'}
                  </span>
                </div>
                <div className="report-item">
                  <span className="report-label">Type</span>
                  <span className="report-value">{results.scamType || '---'}</span>
                </div>
                <div className="report-item">
                  <span className="report-label">Confidence</span>
                  <span className="report-value">
                    {results.confidenceLevel ? `${(results.confidenceLevel * 100).toFixed(1)}%` : '---'}
                  </span>
                </div>
                <div className="report-item">
                  <span className="report-label">Messages</span>
                  <span className="report-value">{results.totalMessagesExchanged || 0}</span>
                </div>
              </div>
              {results.agentNotes && (
                <div className="report-notes">
                  <span className="notes-label">Agent Analysis:</span>
                  <p>{results.agentNotes}</p>
                </div>
              )}
            </div>
            <span className="corner-mark tl">+</span>
            <span className="corner-mark br">+</span>
          </div>
        </div>
      )}
    </div>
  );
}
