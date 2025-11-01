// src/pages/Health.js
import React, { useState } from 'react';
import TopNav from '../components/TopNav';

const endpointList = [
  { name: 'Visualiser', url: 'http://localhost:8090/health' },
  { name: 'API', url: 'http://localhost:5000/health' },
  { name: 'ThingsBoard', url: 'http://localhost:8082/' },
  { name: 'pgAdmin', url: 'http://localhost:5050/' },
  { name: 'Jena Fuseki', url: 'http://localhost:3030/$/ping' },
  { name: 'GraphDB', url: 'http://localhost:7200/' },
  { name: 'Jupyter', url: 'http://localhost:8888/' },
  { name: 'Adminer', url: 'http://localhost:8282/' },
  { name: 'Microservices', url: 'http://localhost:6001/health' },
  { name: 'Rasa', url: 'http://localhost:5005/version' },
  { name: 'Action Server', url: 'http://localhost:5055/health' },
  { name: 'Duckling', url: 'http://localhost:8000/' },
  { name: 'File Server', url: 'http://localhost:8080/health' },
  { name: 'NL2SPARQL', url: 'http://localhost:6005/health' },
  { name: 'Decider Service', url: 'http://localhost:6009/health' },
  { name: 'Ollama', url: 'http://localhost:11434/api/version' },
];

const cardStyle = {
  borderRadius: 16,
  boxShadow: '0 10px 25px rgba(0,0,0,0.08)',
  backdropFilter: 'blur(6px)',
  border: '1px solid rgba(255,255,255,0.3)'
};

export default function Health() {
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState({});

  const checkOne = async (name, url) => {
    setLoading(prev => ({ ...prev, [name]: true }));
    try {
      // Use no-cors to avoid blocking for endpoints without CORS; status will be opaque.
      const mode = url.startsWith('http://localhost') ? 'no-cors' : 'cors';
      const res = await fetch(url, { method: 'GET', mode });
      // When mode is 'no-cors', res.status is 0. Treat 0 as reachable.
      const ok = res.ok || res.status === 200 || res.status === 204 || res.type === 'opaque' || res.status === 0;
      let text = '';
      try { text = await res.text(); } catch {}
      setResults(prev => ({ ...prev, [name]: { ok, status: res.status || 0, text: text?.slice(0, 200) } }));
    } catch (e) {
      setResults(prev => ({ ...prev, [name]: { ok: false, status: -1, text: String(e) } }));
    } finally {
      setLoading(prev => ({ ...prev, [name]: false }));
    }
  };

  const checkAll = async () => {
    for (const ep of endpointList) {
      // Fire sequentially to avoid spamming
      // eslint-disable-next-line no-await-in-loop
      await checkOne(ep.name, ep.url);
    }
  };

  return (
    <div className="home-body">
      <TopNav />
      <div className="container mt-4" id="content">
        <div className="d-flex align-items-center justify-content-between">
          <h2>Health Check</h2>
          <button className="btn btn-outline-primary" onClick={checkAll}>
            Check All
          </button>
        </div>
        <p className="text-muted">Click the button on any card to probe that service’s health endpoint. Local endpoints without CORS will be fetched in no-cors mode and treated as reachable if they respond.</p>

        <div className="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4">
          {endpointList.map(ep => {
            const r = results[ep.name];
            const busy = loading[ep.name];
            const badge = r ? (r.ok ? 'bg-success' : 'bg-danger') : 'bg-secondary';
            const label = r ? (r.ok ? 'Healthy' : 'Unreachable') : 'Unknown';
            return (
              <div className="col" key={ep.name}>
                <div className="card p-3" style={cardStyle}>
                  <div className="d-flex justify-content-between align-items-center">
                    <div>
                      <h5 className="mb-1">{ep.name}</h5>
                      <a href={ep.url} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>{ep.url}</a>
                    </div>
                    <span className={`badge ${badge}`}>{label}</span>
                  </div>
                  <div className="mt-3">
                    <button
                      className="btn btn-primary"
                      onClick={() => checkOne(ep.name, ep.url)}
                      disabled={busy}
                    >
                      {busy ? 'Checking…' : 'Check Health'}
                    </button>
                  </div>
                  {r && (
                    <pre className="mt-3" style={{ maxHeight: 160, overflow: 'auto', background: '#f8f9fa', padding: 10, borderRadius: 8 }}>
{`status: ${r.status}\n${r.text}`}
                    </pre>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
