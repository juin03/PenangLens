'use client';

import { useCallback, useEffect, useState } from 'react';

interface ScanFeedback {
  id: string; isCorrect: boolean; status: string; createdAt: string;
  user?: { email: string };
  recognition?: { userImageUrl?: string; aiDetails?: unknown; poi?: { name: string } };
}
interface ChatFeedbackItem {
  id: string; rating: number; aiMessage: string; userMessage?: string; context?: string; createdAt: string;
  user?: { email: string };
}
interface ItineraryFeedbackItem {
  id: string; rating: number; comment?: string; createdAt: string;
  user?: { email: string };
  itinerary?: {
    name: string;
    originalPrompt?: string;
    generatedNarrative?: string;
    stops?: { stopOrder: number; poi?: { name: string } }[];
    chatHistory?: { role: string; content: string; createdAt: string }[];
  };
}
interface AnalyticsData {
  totalRecognitions: number; feedbackCount: number; correctCount: number;
  totalUsers: number; totalPois: number; publishedPois: number; contentCoverage: number; pendingFeedback: number;
  scanTrend: { date: string; count: number }[];
  topSpots: { name: string; scanCount: number }[];
  totalChatFeedback: number; chatPositiveCount: number;
  totalItineraryFeedback: number; avgItineraryRating: number;
  recentFeedback: ScanFeedback[];
  recentChatFeedback: ChatFeedbackItem[];
  recentItineraryFeedback: ItineraryFeedbackItem[];
}

interface StructuredStop {
  name?: string;
  poiName?: string;
  title?: string;
  duration?: string;
  durationText?: string;
  recommendedDuration?: string;
  transport?: string;
  travelMode?: string;
  travelTime?: string;
  eta?: string;
  note?: string;
  poi?: { name?: string };
  travel?: {
    mode?: string;
    duration?: string;
  };
}

interface StructuredItineraryPayload {
  title?: string;
  name?: string;
  itineraryName?: string;
  summary?: string;
  description?: string;
  stops?: StructuredStop[];
  itinerary?: {
    name?: string;
    summary?: string;
    stops?: StructuredStop[];
  };
}

function ScanTrendChart({ data }: { data: { date: string; count: number }[] }) {
  const max = Math.max(...data.map(d => d.count), 1);
  const W = 100, H = 50;
  const pts = data.map((d, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - (d.count / max) * H;
    return `${x},${y}`;
  }).join(' ');
  const area = `0,${H} ` + pts + ` ${W},${H}`;
  const labels = data.filter((_, i) => i % Math.ceil(data.length / 5) === 0);
  return (
    <div style={{ width: '100%' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 120, overflow: 'visible' }}>
        <defs>
          <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={area} fill="url(#grad)" />
        <polyline points={pts} fill="none" stroke="#7c3aed" strokeWidth="2" strokeLinejoin="round" />
        {data.map((d, i) => {
          const x = (i / (data.length - 1)) * W;
          const y = H - (d.count / max) * H;
          return d.count > 0 ? (
            <circle key={i} cx={x} cy={y} r="1.5" fill="#7c3aed" />
          ) : null;
        })}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        {labels.map(d => (
          <span key={d.date} style={{ fontSize: 10, color: '#9ca3af' }}>{d.date.slice(5)}</span>
        ))}
      </div>
    </div>
  );
}

function DonutChart({ correct, incorrect }: { correct: number; incorrect: number }) {
  const total = correct + incorrect || 1;
  const correctPct = correct / total;
  const correctDeg = Math.round(correctPct * 360);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      <div style={{
        width: 120, height: 120, borderRadius: '50%',
        background: `conic-gradient(#22c55e 0deg ${correctDeg}deg, #ef4444 ${correctDeg}deg 360deg)`,
        position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ width: 74, height: 74, borderRadius: '50%', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
          <span style={{ fontSize: 18, fontWeight: 800, color: '#111827' }}>{total}</span>
          <span style={{ fontSize: 10, color: '#6b7280' }}>Feedbacks</span>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '100%' }}>
        {[{ label: 'Correct Recognition', color: '#22c55e', count: correct },
          { label: 'Incorrect Recognition', color: '#ef4444', count: incorrect }].map(item => (
          <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: item.color, flexShrink: 0 }} />
            <span style={{ color: '#374151', flex: 1 }}>{item.label}</span>
            <span style={{ color: '#6b7280', fontWeight: 600 }}>{item.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ExpandableRow({ children, expandContent }: { children: React.ReactNode; expandContent: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr style={{ cursor: 'pointer' }} onClick={() => setOpen(o => !o)}>
        {children}
        <td style={{ textAlign: 'right', paddingRight: 16 }}>
          <span style={{ fontSize: 12, color: '#7c3aed' }}>{open ? '▲ Close' : '▼ Expand'}</span>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={10} style={{ background: '#fafaff', padding: '12px 24px', borderBottom: '1px solid #e5e7eb' }}>
            {expandContent}
          </td>
        </tr>
      )}
    </>
  );
}

function parseNarrativePayload(raw?: string): StructuredItineraryPayload | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed === 'object' && parsed !== null) return parsed;
    return null;
  } catch {
    return null;
  }
}

function renderStructuredItinerary(payload: StructuredItineraryPayload) {
  const stops: StructuredStop[] = Array.isArray(payload.stops)
    ? payload.stops
    : Array.isArray(payload.itinerary?.stops)
      ? payload.itinerary.stops
      : [];

  const title =
    payload.title ||
    payload.name ||
    payload.itinerary?.name ||
    payload.itineraryName;

  const summary =
    payload.summary ||
    payload.description ||
    payload.itinerary?.summary;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {title && <div><b>Title:</b> <span style={{ color: '#374151' }}>{String(title)}</span></div>}
      {summary && <div><b>Summary:</b> <span style={{ color: '#374151' }}>{String(summary)}</span></div>}

      {stops.length > 0 ? (
        <div>
          <b>Stops:</b>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {stops.map((stop, index) => {
              const stopName = stop.name || stop.poiName || stop.poi?.name || stop.title || `Stop ${index + 1}`;
              const duration = stop.duration || stop.durationText || stop.recommendedDuration;
              const transport = stop.transport || stop.travelMode || stop.travel?.mode;
              const travelTime = stop.travelTime || stop.travel?.duration || stop.eta;

              return (
                <div key={`structured-stop-${index}`} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 10, background: '#fff' }}>
                  <div style={{ fontWeight: 700, color: '#111827' }}>{index + 1}. {String(stopName)}</div>
                  {(duration || transport || travelTime) && (
                    <div style={{ marginTop: 4, fontSize: 12, color: '#6b7280' }}>
                      {duration ? `Duration: ${String(duration)}` : ''}
                      {duration && (transport || travelTime) ? ' · ' : ''}
                      {transport ? `Travel: ${String(transport)}` : ''}
                      {transport && travelTime ? ' · ' : ''}
                      {travelTime ? `ETA: ${String(travelTime)}` : ''}
                    </div>
                  )}
                  {stop.note && <div style={{ marginTop: 4, fontSize: 12, color: '#4b5563' }}>{String(stop.note)}</div>}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div style={{ color: '#6b7280' }}>No structured stops found in saved itinerary payload.</div>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState('30');
  const [activeTab, setActiveTab] = useState<'analytics' | 'scan' | 'chat' | 'itinerary'>('analytics');
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const fetchAnalytics = useCallback(async (targetRange: string = range) => {
    try {
      const res = await fetch(`/api/admin/analytics?days=${targetRange}`);
      const json = await res.json();
      setData(json);
    } catch { setData(null); }
    setLoading(false);
  }, [range]);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    void fetchAnalytics(range);
  }, [fetchAnalytics, range]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const updateFeedbackStatus = async (feedbackId: string, status: string) => {
    setUpdatingId(feedbackId);
    setLoading(true);
    await fetch(`/api/admin/feedback/${feedbackId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    setUpdatingId(null);
    fetchAnalytics();
  };

  const accuracy = data ? Math.round((data.correctCount / Math.max(data.feedbackCount, 1)) * 100) : 0;
  const chatPositiveRate = data ? Math.round(((data.chatPositiveCount ?? 0) / Math.max(data.totalChatFeedback ?? 1, 1)) * 100) : 0;

  const getChatActionHint = (feedback: ChatFeedbackItem) => {
    if (feedback.rating === 1) {
      return 'Good response — keep tone and structure as reference';
    }
    if (!feedback.userMessage) {
      return 'Review response quality and grounding against spot content';
    }
    return 'Check relevance to user question; improve facts and specificity';
  };

  const STAT_CARDS = [
    { label: 'Total Scans', value: data?.totalRecognitions ?? 0, color: '#7c3aed' },
    { label: 'Scan Accuracy', value: `${accuracy}%`, color: accuracy >= 80 ? '#22c55e' : accuracy >= 60 ? '#f59e0b' : '#ef4444' },
    { label: 'Total Users', value: data?.totalUsers ?? 0, color: '#2563eb' },
    { label: 'Published Spots', value: `${data?.publishedPois ?? 0} / ${data?.totalPois ?? 0}`, color: '#6b7280' },
    { label: 'Pending Feedback', value: data?.pendingFeedback ?? 0, color: '#f59e0b' },
    { label: 'Chat 👍 Rate', value: `${chatPositiveRate}%`, color: '#22c55e' },
    { label: 'Avg Itinerary ⭐', value: data?.avgItineraryRating ? `${data.avgItineraryRating}/5` : '—', color: '#f59e0b' },
    { label: 'Content Coverage', value: `${data?.contentCoverage ?? 0}%`, color: '#7c3aed' },
  ];

  const maxTopSpot = Math.max(...(data?.topSpots ?? []).map(s => s.scanCount), 1);

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Analytics Dashboard</h1>
          <p className="page-sub">Live data from all 3 feedback types over the selected range.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'inline-flex', border: '1px solid #e5e7eb', borderRadius: 10, overflow: 'hidden', background: '#fff' }}>
            {([
              ['analytics', 'Analytics'],
              ['scan', 'Scan Feedback'],
              ['chat', 'Chat Feedback'],
              ['itinerary', 'Itinerary Feedback'],
            ] as const).map(([tabKey, label]) => (
              <button
                key={tabKey}
                onClick={() => setActiveTab(tabKey)}
                style={{
                  border: 'none',
                  borderRight: tabKey !== 'itinerary' ? '1px solid #e5e7eb' : 'none',
                  background: activeTab === tabKey ? '#7c3aed' : '#fff',
                  color: activeTab === tabKey ? '#fff' : '#4b5563',
                  padding: '8px 12px',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <select className="form-input form-select" style={{ width: 160 }} value={range} onChange={e => {
            const nextRange = e.target.value;
            setLoading(true);
            setRange(nextRange);
            void fetchAnalytics(nextRange);
          }}>
            <option value="7">Last 7 Days</option>
            <option value="30">Last 30 Days</option>
            <option value="90">Last 90 Days</option>
          </select>
        </div>
      </div>

      {activeTab === 'analytics' && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
            {STAT_CARDS.map(card => (
              <div key={card.label} className="stat-card">
                <div className="stat-label">{card.label}</div>
                <div className="stat-value" style={{ color: card.color, fontSize: 22 }}>
                  {loading ? '...' : card.value.toLocaleString?.() ?? card.value}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24, marginBottom: 24 }}>
            <div className="card">
              <div className="card-header">
                <span style={{ fontWeight: 700 }}>Scan Trend</span>
                <span style={{ fontSize: 12, color: '#9ca3af', marginLeft: 8 }}>Daily scans over last {range} days</span>
              </div>
              <div className="card-body">
                {loading ? (
                  <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af' }}>Loading...</div>
                ) : data?.scanTrend?.length ? (
                  <ScanTrendChart data={data.scanTrend} />
                ) : (
                  <div style={{ height: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>No scan data yet</div>
                )}
              </div>
            </div>

            <div className="card">
              <div className="card-header"><span style={{ fontWeight: 700 }}>Scan Feedback Split</span></div>
              <div className="card-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                {loading ? (
                  <div style={{ height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af' }}>Loading…</div>
                ) : (
                  <DonutChart correct={data?.correctCount ?? 0} incorrect={(data?.feedbackCount ?? 0) - (data?.correctCount ?? 0)} />
                )}
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
            <div className="card">
              <div className="card-header"><span style={{ fontWeight: 700 }}>Top 5 Scanned Spots</span></div>
              <div className="card-body">
                {(data?.topSpots ?? []).length === 0 ? (
                  <p style={{ color: '#9ca3af', fontSize: 13 }}>No scan data yet</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {(data?.topSpots ?? []).map((spot, i) => (
                      <div key={spot.name}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 13 }}>
                          <span style={{ fontWeight: 600, color: '#374151' }}>{i + 1}. {spot.name}</span>
                          <span style={{ color: '#7c3aed', fontWeight: 700 }}>{spot.scanCount}</span>
                        </div>
                        <div style={{ background: '#f3f4f6', borderRadius: 4, height: 8 }}>
                          <div style={{ background: '#7c3aed', borderRadius: 4, height: 8, width: `${(spot.scanCount / maxTopSpot) * 100}%`, transition: 'width 0.5s' }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="card">
              <div className="card-header"><span style={{ fontWeight: 700 }}>Other Metrics</span></div>
              <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 13 }}>
                    <span style={{ fontWeight: 600 }}>Content Coverage</span>
                    <span style={{ color: '#7c3aed', fontWeight: 700 }}>{data?.contentCoverage ?? 0}%</span>
                  </div>
                  <div style={{ background: '#f3f4f6', borderRadius: 4, height: 10 }}>
                    <div style={{ background: '#7c3aed', borderRadius: 4, height: 10, width: `${data?.contentCoverage ?? 0}%`, transition: 'width 0.5s' }} />
                  </div>
                </div>
                {[
                  { label: '💬 Chat Feedbacks', val: data?.totalChatFeedback ?? 0, sub: `👍 ${chatPositiveRate}% positive` },
                  { label: '🗺️ Itinerary Feedbacks', val: data?.totalItineraryFeedback ?? 0, sub: `Avg ${data?.avgItineraryRating ?? '—'}/5 stars` },
                ].map(m => (
                  <div key={m.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderTop: '1px solid #f0f0f0', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>{m.label}</div>
                      <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>{m.sub}</div>
                    </div>
                    <span style={{ fontSize: 22, fontWeight: 800, color: '#111827' }}>{m.val}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab !== 'analytics' && (
      <div className="card">

        {/* Scan Feedback Table */}
        {activeTab === 'scan' && (
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th><th>DATE</th><th>USER</th><th>POI</th><th>VERDICT</th><th>STATUS</th><th>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>Loading...</td></tr>
              ) : !data?.recentFeedback?.length ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>No scan feedback yet</td></tr>
              ) : data.recentFeedback.map(fb => (
                <ExpandableRow key={fb.id} expandContent={
                  <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 20, fontSize: 13 }}>
                    {fb.recognition?.userImageUrl && (
                      <img src={fb.recognition.userImageUrl} alt="scan" style={{ width: 200, borderRadius: 8, objectFit: 'cover' }} />
                    )}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div><b>POI Identified:</b> {fb.recognition?.poi?.name ?? '—'}</div>
                      <div><b>User:</b> {fb.user?.email ?? 'Guest'}</div>
                      <div><b>AI Details:</b> <pre style={{ fontSize: 11, background: '#f3f4f6', padding: 8, borderRadius: 4, overflow: 'auto' }}>{JSON.stringify(fb.recognition?.aiDetails, null, 2)}</pre></div>
                    </div>
                  </div>
                }>
                  <td style={{ fontFamily: 'monospace', fontSize: 12, color: '#6b7280' }}>#{fb.id.slice(0, 8).toUpperCase()}</td>
                  <td style={{ fontSize: 12, color: '#6b7280' }}>{new Date(fb.createdAt).toLocaleDateString('en-MY')}</td>
                  <td style={{ fontSize: 12 }}>{fb.user?.email ?? 'Guest'}</td>
                  <td style={{ fontSize: 13 }}>{fb.recognition?.poi?.name ?? '—'}</td>
                  <td>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      fontSize: 12, fontWeight: 700,
                      color: fb.isCorrect ? '#166534' : '#991b1b',
                      background: fb.isCorrect ? '#dcfce7' : '#fee2e2',
                      border: `1px solid ${fb.isCorrect ? '#86efac' : '#fca5a5'}`,
                      padding: '4px 8px', borderRadius: 999,
                    }}>
                      {fb.isCorrect ? '👍 Good' : '👎 Bad'}
                    </span>
                  </td>
                  <td><span className={`badge badge-${fb.status}`}>{fb.status}</span></td>
                  <td style={{ textAlign: 'right' }}>
                    {fb.status === 'pending' && <button className="btn btn-outline btn-sm" disabled={updatingId === fb.id} onClick={() => updateFeedbackStatus(fb.id, 'reviewed')}>Review</button>}
                    {fb.status === 'reviewed' && <button className="btn btn-primary btn-sm" disabled={updatingId === fb.id} onClick={() => updateFeedbackStatus(fb.id, 'actioned')}>Action</button>}
                    {fb.status === 'actioned' && <span style={{ color: '#22c55e', fontSize: 13 }}>✓ Done</span>}
                  </td>
                </ExpandableRow>
              ))}
            </tbody>
          </table>
        )}

        {/* Chat Feedback Table */}
        {activeTab === 'chat' && (
          <table className="admin-table">
            <thead>
              <tr><th>DATE</th><th>USER</th><th>CONTEXT</th><th>REVIEW</th><th>ACTION HINT</th><th>AI MESSAGE (preview)</th><th></th></tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>Loading...</td></tr>
              ) : !data?.recentChatFeedback?.length ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>No chat feedback yet. Add 👍👎 to mobile chat.</td></tr>
              ) : data.recentChatFeedback.map(fb => (
                <ExpandableRow key={fb.id} expandContent={
                  <div style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div><b>Review:</b> <span style={{ color: fb.rating === 1 ? '#16a34a' : '#dc2626', fontWeight: 700 }}>{fb.rating === 1 ? 'Good 👍' : 'Needs Improvement 👎'}</span></div>
                    <div><b>Recommended action:</b> <span style={{ color: '#4b5563' }}>{getChatActionHint(fb)}</span></div>
                    <div><b>User asked:</b> <span style={{ color: '#374151' }}>{fb.userMessage ?? '—'}</span></div>
                    <div><b>AI replied:</b>
                      <div style={{ background: '#f8fafc', border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, marginTop: 6, fontSize: 13, lineHeight: 1.6 }}>{fb.aiMessage}</div>
                    </div>
                  </div>
                }>
                  <td style={{ fontSize: 12, color: '#6b7280' }}>{new Date(fb.createdAt).toLocaleDateString('en-MY')}</td>
                  <td style={{ fontSize: 12 }}>{fb.user?.email ?? 'Guest'}</td>
                  <td style={{ fontSize: 12, color: '#7c3aed' }}>{fb.context ?? '—'}</td>
                  <td>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      fontSize: 12, fontWeight: 700,
                      color: fb.rating === 1 ? '#166534' : '#991b1b',
                      background: fb.rating === 1 ? '#dcfce7' : '#fee2e2',
                      border: `1px solid ${fb.rating === 1 ? '#86efac' : '#fca5a5'}`,
                      padding: '4px 8px', borderRadius: 999,
                    }}>
                      {fb.rating === 1 ? '👍 Good' : '👎 Bad'}
                    </span>
                  </td>
                  <td style={{ maxWidth: 240, fontSize: 12, color: '#4b5563' }}>{getChatActionHint(fb)}</td>
                  <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 13, color: '#374151' }}>{fb.aiMessage}</td>
                </ExpandableRow>
              ))}
            </tbody>
          </table>
        )}

        {/* Itinerary Feedback Table */}
        {activeTab === 'itinerary' && (
          <table className="admin-table">
            <thead>
              <tr><th>DATE</th><th>USER</th><th>ITINERARY</th><th>REVIEW</th><th>COMMENT</th><th></th></tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>Loading...</td></tr>
              ) : !data?.recentItineraryFeedback?.length ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>No itinerary feedback yet.</td></tr>
              ) : data.recentItineraryFeedback.map(fb => (
                <ExpandableRow key={fb.id} expandContent={
                  <div style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div><b>Review:</b> <span style={{ color: fb.rating >= 4 ? '#16a34a' : '#dc2626', fontWeight: 700 }}>{fb.rating >= 4 ? 'Good 👍' : 'Bad 👎'}</span></div>
                    <div><b>Itinerary:</b> {fb.itinerary?.name}</div>
                    <div><b>Original Prompt:</b> <em style={{ color: '#6b7280' }}>{fb.itinerary?.originalPrompt ?? '—'}</em></div>
                    <div>
                      <b>Itinerary Content:</b>
                      <div style={{ background: '#f8fafc', border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, marginTop: 6, fontSize: 13, lineHeight: 1.6 }}>
                        {(() => {
                          const parsed = parseNarrativePayload(fb.itinerary?.generatedNarrative);
                          if (parsed) return renderStructuredItinerary(parsed);
                          return <span>{fb.itinerary?.generatedNarrative ?? '—'}</span>;
                        })()}
                      </div>
                    </div>
                    <div><b>Stops:</b>
                      {fb.itinerary?.stops?.length ? (
                        <ol style={{ margin: '6px 0 0 20px', color: '#374151' }}>
                          {fb.itinerary.stops.map((s, idx) => (
                            <li key={`${fb.id}-${idx}`}>{s.poi?.name ?? `Stop ${s.stopOrder}`}</li>
                          ))}
                        </ol>
                      ) : (
                        <span style={{ color: '#6b7280' }}> — </span>
                      )}
                    </div>
                    <div>
                      <b>Full Chat Thread:</b>
                      {fb.itinerary?.chatHistory?.length ? (
                        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
                          {fb.itinerary.chatHistory.map((msg, index) => {
                            const isUser = msg.role === 'user';
                            return (
                              <div
                                key={`${fb.id}-chat-${index}`}
                                style={{
                                  alignSelf: isUser ? 'flex-end' : 'flex-start',
                                  maxWidth: '85%',
                                  background: isUser ? '#ede9fe' : '#f3f4f6',
                                  border: `1px solid ${isUser ? '#c4b5fd' : '#e5e7eb'}`,
                                  borderRadius: 12,
                                  padding: '8px 10px',
                                }}
                              >
                                <div style={{ fontSize: 11, fontWeight: 700, color: isUser ? '#6d28d9' : '#4b5563', marginBottom: 4 }}>
                                  {isUser ? 'User' : 'Assistant'} · {new Date(msg.createdAt).toLocaleString('en-MY')}
                                </div>
                                <div style={{ color: '#111827', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div style={{ color: '#6b7280', marginTop: 4 }}>No chat history found.</div>
                      )}
                    </div>
                    {fb.comment && <div><b>Comment:</b> {fb.comment}</div>}
                  </div>
                }>
                  <td style={{ fontSize: 12, color: '#6b7280' }}>{new Date(fb.createdAt).toLocaleDateString('en-MY')}</td>
                  <td style={{ fontSize: 12 }}>{fb.user?.email ?? 'Guest'}</td>
                  <td style={{ fontSize: 13, fontWeight: 600 }}>{fb.itinerary?.name ?? '—'}</td>
                  <td>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      fontSize: 12, fontWeight: 700,
                      color: fb.rating >= 4 ? '#166534' : '#991b1b',
                      background: fb.rating >= 4 ? '#dcfce7' : '#fee2e2',
                      border: `1px solid ${fb.rating >= 4 ? '#86efac' : '#fca5a5'}`,
                      padding: '4px 8px', borderRadius: 999,
                    }}>
                      {fb.rating >= 4 ? '👍 Good' : '👎 Bad'}
                    </span>
                  </td>
                  <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 13, color: '#6b7280' }}>{fb.comment ?? '—'}</td>
                </ExpandableRow>
              ))}
            </tbody>
          </table>
        )}
      </div>
      )}
    </div>
  );
}
