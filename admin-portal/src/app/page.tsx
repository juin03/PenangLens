'use client';

import { useEffect, useState } from 'react';

interface UsageStats {
  total_requests: number;
  total_sessions: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_thinking_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  uptime_seconds: number;
  avg_tokens_per_request: number;
  avg_cost_per_request_usd: number;
}

export default function Home() {
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
    // Auto-refresh every 10 seconds
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      // Calls our BFF Proxy -> Agent
      const res = await fetch('/api/v1/usage');
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Server returned ${res.status}: ${errText}`);
      }
      const data = await res.json();
      setStats(data);
      setError(null);
    } catch (err) {
      console.error(err);
      setError('Agent offline or unreachable');
    } finally {
      setLoading(false);
    }
  };

  const formatCost = (cost: number) => {
    return '$' + cost.toFixed(4);
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 p-8 font-sans">
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Header */}
        <header className="flex items-center justify-between pb-6 border-b border-gray-200">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-gray-900">PenangLens Admin Portal</h1>
            <p className="mt-2 text-sm text-gray-500">Monitor your AI Agent microservice and token usage.</p>
          </div>
          <div className="flex items-center space-x-3">
            <div className={`h-3 w-3 rounded-full ${error ? 'bg-red-500' : 'bg-green-500 animate-pulse'}`}></div>
            <span className="text-sm font-medium text-gray-700">
              Agent Status: {error ? 'Offline' : 'Online'}
            </span>
          </div>
        </header>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard 
            title="Total Tokens" 
            value={loading ? '...' : stats?.total_tokens.toLocaleString() || '0'} 
          />
          <StatCard 
            title="Total Requests" 
            value={loading ? '...' : stats?.total_requests.toLocaleString() || '0'} 
          />
          <StatCard 
            title="Cost Estimated" 
            value={loading ? '...' : (stats ? formatCost(stats.total_cost_usd) : '$0.0000')} 
            highlight
          />
          <StatCard 
            title="Active Sessions" 
            value={loading ? '...' : stats?.total_sessions.toLocaleString() || '0'} 
          />
        </div>

        {/* Usage Breakdown */}
        {stats && (
          <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold mb-6">Token Breakdown</h2>
            <div className="space-y-4">
              <ProgressBar label="Input Tokens" value={stats.total_input_tokens} total={stats.total_tokens} color="bg-blue-500" />
              <ProgressBar label="Output Tokens" value={stats.total_output_tokens} total={stats.total_tokens} color="bg-indigo-500" />
              <ProgressBar label="Thinking Tokens" value={stats.total_thinking_tokens} total={stats.total_tokens} color="bg-purple-500" />
            </div>
            
            <div className="mt-8 grid grid-cols-2 gap-4 border-t border-gray-100 pt-6">
              <div>
                <p className="text-sm text-gray-500 font-medium">Avg Tokens / Request</p>
                <p className="text-xl font-semibold mt-1">{stats.avg_tokens_per_request.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500 font-medium">Avg Cost / Request</p>
                <p className="text-xl font-semibold mt-1">{formatCost(stats.avg_cost_per_request_usd)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500 font-medium">Server Uptime</p>
                <p className="text-xl font-semibold mt-1">{(stats.uptime_seconds / 3600).toFixed(1)} hrs</p>
              </div>
            </div>
          </div>
        )}

        {/* Configuration */}
        <div className="mt-12 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-semibold mb-4">Architecture Info</h2>
          <div className="space-y-4">
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm font-medium text-gray-600">BFF Proxy URL</span>
              <span className="text-sm font-mono text-gray-900 bg-gray-100 px-3 py-1 rounded">http://localhost:3000/api/v1/*</span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm font-medium text-gray-600">Agent Backend Target</span>
              <span className="text-sm font-mono text-gray-900 bg-gray-100 px-3 py-1 rounded">http://127.0.0.1:8000</span>
            </div>
            <div className="flex justify-between items-center py-3">
              <span className="text-sm font-medium text-gray-600">LLM Engine</span>
              <span className="text-sm font-mono text-blue-600 bg-blue-50 px-3 py-1 rounded border border-blue-100">Google Gemini 2.5 Flash</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

function StatCard({ title, value, highlight = false }: { title: string, value: string, highlight?: boolean }) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border p-6 flex flex-col ${highlight ? 'border-green-200 bg-green-50/10' : 'border-gray-200'}`}>
      <span className="text-sm font-medium text-gray-500 mb-2">{title}</span>
      <span className={`text-3xl font-bold ${highlight ? 'text-green-700' : 'text-gray-900'}`}>{value}</span>
    </div>
  );
}

function ProgressBar({ label, value, total, color }: { label: string, value: number, total: number, color: string }) {
  const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
  
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-gray-500">{value.toLocaleString()} ({percentage}%)</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${percentage}%` }}></div>
      </div>
    </div>
  );
}
