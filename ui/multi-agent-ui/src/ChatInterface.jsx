// ChatInterface.jsx
import { useState } from 'react';
import './ChatInterface.css';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';

// Create configured instance
const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  }
});

export default function ChatInterface() {
  const [inputText, setInputText] = useState('');
  const [basicChat, setBasicChat] = useState([]);
  const [MultiAgentChat, setMultiAgentChat] = useState([]);
  const [loading, setLoading] = useState(false);


  // Handle Basic LLM Call
  const handleBasicLLM = async () => {
    try {
      const response = api.post('/basic-llm', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ prompt: inputText })
      });
     // console.log(await response);
      const data = (await response).data;
      setBasicChat([...basicChat, { query: inputText, response: data.response }]);
    } catch (error) {
      console.error('Basic LLM Error:', error);
    }
  };

  // Handle MultiAgent Workflow
  const handleMultiAgent = async () => {
    setLoading(true);
    try {
      // Init Workflow
      const initRes = api.post('/init', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ problem: inputText })
      });

      const { workflow_id } = (await initRes).data;
        console.log("workflow_id22",workflow_id);
      // Execute Workflow
      const resultRes = await api.post(`/step/${workflow_id}`, {
        method: 'POST'
      });
      const result = (await resultRes).data;
      const solutions = result.state?.solutions || [];
      console.log(solutions);

      console.log("resultplan",solutions);
      
    setMultiAgentChat([...MultiAgentChat, { 
        query: inputText, 
        response: solutions[0]
    }]);
    } catch (error) {
      console.error('MultiAgent Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <div className="input-section">
        <input
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Enter your problem..."
        />
        <div className="button-group" style={{justifyContent:"center"}}>
          <button onClick={handleBasicLLM}>Ask Basic LLM</button>
          <button onClick={handleMultiAgent} disabled={loading}>
            {loading ? 'Processing...' : 'Ask MultiAgent'}
          </button>
        </div>
      </div>

      <div className="chat-container">
        <div className="chat-column">
          <h3>Basic LLM Responses</h3>
          {basicChat.map((entry, idx) => (
            <div key={`basic-${idx}`} className="chat-entry">
              <div className="query">Q: {entry.query}</div>
              <div className="response">A: {entry.response}</div>
            </div>
          ))}
        </div>

        <div className="chat-column">
          <h3>MultiAgent Solutions</h3>
          {MultiAgentChat.map((entry, idx) => (
            <div key={`MultiAgent-${idx}`} className="chat-entry">
              <div className="query">Problem: {entry.query}</div>
                        <div className="response">
                            <ReactMarkdown>
                                {JSON.stringify(entry.response, null, 2)}
                            </ReactMarkdown>
                        </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}