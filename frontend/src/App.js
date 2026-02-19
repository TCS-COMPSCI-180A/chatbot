import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [apiStatus, setApiStatus] = useState('Checking...');
  const [apiMessage, setApiMessage] = useState('');

  useEffect(() => {
    // Check backend API connection
    const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    
    fetch(`${apiUrl}/health`)
      .then(response => response.json())
      .then(data => {
        setApiStatus('✓ Connected');
        setApiMessage(data.message || 'Backend is running');
      })
      .catch(error => {
        setApiStatus('✗ Disconnected');
        setApiMessage('Unable to connect to backend');
        console.error('API connection error:', error);
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <div className="status-card">
          <h2>System Status</h2>
          <div className="status-item">
            <span className="label">Frontend:</span>
            <span className="value status-ok">✓ Running</span>
          </div>
          <div className="status-item">
            <span className="label">Backend API:</span>
            <span className={`value ${apiStatus.includes('✓') ? 'status-ok' : 'status-error'}`}>
              {apiStatus}
            </span>
          </div>
          <div className="status-item">
            <span className="label">Environment:</span>
            <span className="value">{process.env.REACT_APP_ENV || 'development'}</span>
          </div>
        </div>
      </header>
    </div>
  );
}

export default App;
