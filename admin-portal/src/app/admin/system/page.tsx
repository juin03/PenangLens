'use client';

import { useEffect, useState } from 'react';

interface Health { status: string; uptime_seconds: number; }
interface Usage { total_tokens: number; total_requests: number; total_cost_usd: number; }

export default function SystemAdminPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('/api/v1/health').then(r => r.json()).catch(() => null),
      fetch('/api/v1/usage').then(r => r.json()).catch(() => null),
    ]).then(([h, u]) => { setHealth(h); setUsage(u); setLoading(false); });
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">System Admin</h1>
        <p className="page-sub">Service health and AI token usage monitoring.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">Agent Status</div>
          <div className="stat-value" style={{ fontSize: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: health?.status === 'ok' || health?.status === 'healthy' ? '#22c55e' : '#ef4444', display: 'inline-block' }} />
            {loading ? '...' : health?.status === 'ok' || health?.status === 'healthy' ? 'Online' : 'Offline'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Requests</div>
          <div className="stat-value">{loading ? '...' : (usage?.total_requests ?? 0).toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">AI Cost (USD)</div>
          <div className="stat-value">${loading ? '...' : (usage?.total_cost_usd ?? 0).toFixed(4)}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header" style={{ fontWeight: 700 }}>Architecture</div>
        <div className="card-body">
          {[
            { label: 'Next.js BFF URL', value: 'http://localhost:3000', tag: 'bff' },
            { label: 'Agent Backend', value: 'http://127.0.0.1:8000', tag: 'agent' },
            { label: 'VisionML Backend', value: 'http://127.0.0.1:8001', tag: 'vision' },
            { label: 'Database', value: 'Azure PostgreSQL (penanglens-db)', tag: 'db' },
            { label: 'LLM Engine', value: 'Google Gemini 2.5 Flash', tag: 'ai' },
          ].map(row => (
            <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid #f0f0f0' }}>
              <span style={{ fontSize: 13.5, color: '#6b7280', fontWeight: 500 }}>{row.label}</span>
              <span style={{ fontSize: 12.5, fontFamily: 'monospace', background: '#f3f4f6', padding: '4px 10px', borderRadius: 6, color: '#374151' }}>{row.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
