'use client';

import { useEffect, useState } from 'react';

interface Feedback {
  id: string; recognitionId: string; isCorrect: boolean;
  status: string; createdAt: string; adminNotes?: string;
  user?: { email: string };
  recognition?: { userImageUrl?: string; poi?: { name: string } };
}

interface AnalyticsData {
  totalRecognitions: number;
  feedbackCount: number;
  correctCount: number;
  categories: { label: string; accuracy: number }[];
  feedbackByType: { label: string; count: number; color: string }[];
  recentFeedback: Feedback[];
}

const CATEGORY_COLORS = ['#2563eb', '#22c55e', '#f59e0b', '#a855f7', '#ec4899'];

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState('30');
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  useEffect(() => { fetchAnalytics(); }, [range]);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/analytics?days=${range}`);
      const json = await res.json();
      setData(json);
    } catch { setData(null); }
    setLoading(false);
  };

  const updateFeedbackStatus = async (feedbackId: string, status: string) => {
    setUpdatingId(feedbackId);
    await fetch(`/api/admin/feedback/${feedbackId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    setUpdatingId(null);
    fetchAnalytics();
  };

  const accuracy = data ? Math.round((data.correctCount / Math.max(data.feedbackCount, 1)) * 100) : 0;

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Analytics Dashboard</h1>
          <p className="page-sub">Overview of system performance and user feedback.</p>
        </div>
        <select className="form-input form-select" style={{ width: 160 }} value={range} onChange={e => setRange(e.target.value)}>
          <option value="7">Last 7 Days</option>
          <option value="30">Last 30 Days</option>
          <option value="90">Last 90 Days</option>
        </select>
      </div>

      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">Total Scans</div>
          <div className="stat-value">{loading ? '...' : (data?.totalRecognitions ?? 0).toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">User Feedbacks</div>
          <div className="stat-value">{loading ? '...' : (data?.feedbackCount ?? 0).toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Overall Accuracy</div>
          <div className="stat-value" style={{ color: accuracy >= 80 ? '#22c55e' : accuracy >= 60 ? '#f59e0b' : '#ef4444' }}>
            {loading ? '...' : `${accuracy}%`}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24, marginBottom: 24 }}>
        {/* Bar Chart: Accuracy by Category */}
        <div className="card">
          <div className="card-header">
            <span style={{ fontWeight: 700 }}>AI Recognition Accuracy by Category</span>
            <p style={{ fontSize: 12, color: '#9ca3af', marginTop: 3 }}>Performance breakdown over the last {range} days</p>
          </div>
          <div className="card-body">
            {loading ? (
              <div style={{ height: 180, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af' }}>Loading...</div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 20, height: 180, paddingTop: 20 }}>
                {(data?.categories ?? []).map((cat, i) => (
                  <div key={cat.label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, color: '#374151', fontWeight: 600 }}>{cat.accuracy}%</span>
                    <div style={{
                      width: '100%', background: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
                      height: `${cat.accuracy * 1.4}px`, borderRadius: '4px 4px 0 0', transition: 'height 0.5s',
                    }} />
                    <span style={{ fontSize: 11, color: '#6b7280' }}>{cat.label}</span>
                  </div>
                ))}
                {(!data?.categories?.length) && (
                  <div style={{ width: '100%', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>No recognition data yet</div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Donut: Feedback Type Distribution */}
        <div className="card">
          <div className="card-header">
            <span style={{ fontWeight: 700 }}>Feedback Type Distribution</span>
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
            <div style={{ width: 120, height: 120, borderRadius: '50%', background: `conic-gradient(
              #2563eb 0% 45%, #22c55e 45% 75%, #f59e0b 75% 90%, #6b7280 90% 100%
            )`, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: 72, height: 72, borderRadius: '50%', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
                <span style={{ fontSize: 17, fontWeight: 800 }}>{loading ? '...' : data?.feedbackCount ?? 0}</span>
                <span style={{ fontSize: 10, color: '#6b7280' }}>Total</span>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
              {[
                { label: 'Incorrect Recognition', color: '#2563eb', pct: '45%' },
                { label: 'Incorrect Identification', color: '#22c55e', pct: '30%' },
                { label: 'Incorrect Explanation', color: '#f59e0b', pct: '15%' },
                { label: 'Incorrect Itinerary', color: '#6b7280', pct: '10%' },
              ].map(item => (
                <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5 }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', background: item.color, flexShrink: 0 }} />
                  <span style={{ color: '#374151', flex: 1 }}>{item.label}</span>
                  <span style={{ color: '#6b7280', fontWeight: 600 }}>{item.pct}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Feedback Table */}
      <div className="card">
        <div className="card-header">
          <span style={{ fontWeight: 700 }}>Recent User Feedback</span>
        </div>
        <table className="admin-table">
          <thead>
            <tr>
              <th>FEEDBACK ID</th>
              <th>SUBMITTED ON</th>
              <th>CATEGORY</th>
              <th>DETAILS</th>
              <th>STATUS</th>
              <th style={{ textAlign: 'right' }}>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>Loading...</td></tr>
            ) : !data?.recentFeedback?.length ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>No feedback yet. Users submit feedback from the mobile app after scanning.</td></tr>
            ) : (
              data.recentFeedback.map(fb => (
                <tr key={fb.id}>
                  <td style={{ fontFamily: 'monospace', fontSize: 12, color: '#6b7280' }}>#{fb.id.slice(0, 8).toUpperCase()}</td>
                  <td style={{ color: '#6b7280', fontSize: 13 }}>{new Date(fb.createdAt).toLocaleDateString('en-MY')}</td>
                  <td><span style={{ fontSize: 13 }}>{fb.isCorrect ? '✅ Correct' : '❌ Incorrect Recognition'}</span></td>
                  <td style={{ color: '#374151', fontSize: 13 }}>
                    {fb.recognition?.poi?.name ? `Identified as: ${fb.recognition.poi.name}` : '—'}
                  </td>
                  <td><span className={`badge badge-${fb.status}`}>{fb.status.charAt(0).toUpperCase() + fb.status.slice(1)}</span></td>
                  <td style={{ textAlign: 'right' }}>
                    {fb.status === 'pending' && (
                      <button className="btn btn-outline btn-sm" disabled={updatingId === fb.id}
                        onClick={() => updateFeedbackStatus(fb.id, 'reviewed')}>Review</button>
                    )}
                    {fb.status === 'reviewed' && (
                      <button className="btn btn-primary btn-sm" disabled={updatingId === fb.id}
                        onClick={() => updateFeedbackStatus(fb.id, 'actioned')}>Action</button>
                    )}
                    {fb.status === 'actioned' && <span style={{ color: '#22c55e', fontSize: 13 }}>✓ Done</span>}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {data?.recentFeedback?.length ? (
          <div style={{ padding: '12px 20px', borderTop: '1px solid #f0f0f0', fontSize: 13, color: '#6b7280', display: 'flex', justifyContent: 'space-between' }}>
            <span>Showing 1 to {data.recentFeedback.length} of {data.recentFeedback.length} entries</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-outline btn-sm">Previous</button>
              <button className="btn btn-outline btn-sm">Next</button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
