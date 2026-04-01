'use client';

import { useEffect, useState } from 'react';

interface Stop { stopOrder: number; travelTimeMin?: number; poi?: { name: string } }
interface Feedback { id: string; rating: number; comment?: string; status: string; createdAt: string }
interface ChatMsg { role: string; content: string; createdAt: string }
interface Itinerary {
  id: string; name: string; originalPrompt?: string; generatedNarrative?: string;
  totalDuration?: number; threadId?: string; createdAt: string;
  user?: { email: string }; stops: Stop[]; feedbacks: Feedback[]; chatHistory: ChatMsg[];
}

interface ParsedStop {
  order: number; name: string; description?: string; short_description?: string;
  arrival_time?: string; departure_time?: string; visit_duration_min?: number;
  rating?: number; address?: string; photo_url?: string;
  travel_to_next?: { distance_text?: string; duration_text?: string; mode?: string };
}

const ratingLabel = (r: number) => r >= 4 ? '👍 Good' : r <= 2 ? '👎 Bad' : '😐 Neutral';
const ratingColor = (r: number) => r >= 4 ? '#16a34a' : r <= 2 ? '#dc2626' : '#d97706';
const avgRating = (fb: Feedback[]) => fb.length ? fb.reduce((s, f) => s + f.rating, 0) / fb.length : null;

function parseNarrative(raw?: string): { stops: ParsedStop[]; summary?: string; route_url?: string; travel_mode?: string; total_travel_time_min?: number } | null {
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

function StopCard({ stop, isLast }: { stop: ParsedStop; isLast: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        {/* Timeline */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 32 }}>
          <div style={{ width: 28, height: 28, borderRadius: 14, background: '#1d4ed8', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700 }}>
            {stop.order}
          </div>
          {!isLast && <div style={{ width: 2, height: 40, background: '#d1d5db', marginTop: 4 }} />}
        </div>
        {/* Card */}
        <div style={{ flex: 1, border: '1px solid #e5e7eb', borderRadius: 10, padding: 12, background: '#fff', marginBottom: isLast ? 0 : 8 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            {stop.photo_url && (
              <img src={stop.photo_url} alt={stop.name} style={{ width: 64, height: 64, borderRadius: 8, objectFit: 'cover' }} />
            )}
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{stop.name}</div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                {stop.arrival_time && <span>🕐 {stop.arrival_time} – {stop.departure_time}</span>}
                {stop.visit_duration_min && <span> · {stop.visit_duration_min} min</span>}
                {stop.rating && <span> · ⭐ {stop.rating}</span>}
              </div>
              {stop.short_description && <div style={{ fontSize: 12, color: '#4b5563', marginTop: 4 }}>{stop.short_description}</div>}
              {stop.description && (
                <div style={{ marginTop: 4 }}>
                  <span onClick={() => setOpen(!open)} style={{ fontSize: 11, color: '#1d4ed8', cursor: 'pointer' }}>
                    {open ? '▾ Hide details' : '› Show details'}
                  </span>
                  {open && <div style={{ fontSize: 12, color: '#4b5563', marginTop: 4, lineHeight: 1.5 }}>{stop.description}</div>}
                </div>
              )}
              {stop.address && <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>📍 {stop.address}</div>}
            </div>
          </div>
        </div>
      </div>
      {/* Travel segment */}
      {!isLast && stop.travel_to_next && (
        <div style={{ marginLeft: 40, fontSize: 11, color: '#6b7280', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
          {stop.travel_to_next.mode === 'walking' ? '🚶' : '🚗'} {stop.travel_to_next.duration_text} · {stop.travel_to_next.distance_text}
        </div>
      )}
    </div>
  );
}

export default function ItineraryReviewPage() {
  const [itineraries, setItineraries] = useState<Itinerary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<'all' | 'good' | 'bad'>('all');
  const [statusFilter, setStatusFilter] = useState('pending');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    const token = localStorage.getItem('admin_token');
    const params = new URLSearchParams({ page: String(page), status: statusFilter });
    if (filter !== 'all') params.set('rating', filter);
    fetch(`/api/admin/itineraries?${params}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.json())
      .then(d => { setItineraries(d.itineraries ?? []); setTotal(d.total ?? 0); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page, filter, statusFilter]);

  const markReviewed = async (feedbackId: string) => {
    setSaving(feedbackId);
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/itineraries/${feedbackId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ status: 'reviewed' }),
    });
    setSaving(null);
    load();
  };

  const removeFeedback = async (feedbackId: string) => {
    if (!confirm('Delete this feedback?')) return;
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/itineraries/${feedbackId}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    load();
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div style={{ padding: 32, maxWidth: 1100, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>🗓️ Itinerary Review</h1>
      <p style={{ color: '#6b7280', marginBottom: 24 }}>Review AI-generated itineraries and user feedback.</p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {(['pending', 'reviewed', 'all'] as const).map(s => (
          <button key={s} onClick={() => { setStatusFilter(s); setPage(1); }} style={{
            padding: '6px 16px', borderRadius: 6, border: '1px solid #d1d5db', cursor: 'pointer',
            background: statusFilter === s ? '#1d4ed8' : '#fff',
            color: statusFilter === s ? '#fff' : '#374151', fontWeight: statusFilter === s ? 600 : 400,
            textTransform: 'capitalize',
          }}>{s}</button>
        ))}
        <div style={{ width: 1, background: '#d1d5db', margin: '0 4px' }} />
        {(['all', 'good', 'bad'] as const).map(f => (
          <button key={f} onClick={() => { setFilter(f); setPage(1); }} style={{
            padding: '6px 16px', borderRadius: 6, border: '1px solid #d1d5db', cursor: 'pointer',
            background: filter === f ? '#1d4ed8' : '#fff',
            color: filter === f ? '#fff' : '#374151', fontWeight: filter === f ? 600 : 400,
          }}>{f === 'all' ? 'All Ratings' : f === 'good' ? '👍 Good' : '👎 Bad'}</button>
        ))}
        <span style={{ marginLeft: 'auto', color: '#6b7280', alignSelf: 'center' }}>{total} itineraries</span>
      </div>

      {loading ? <p style={{ color: '#6b7280' }}>Loading...</p> : itineraries.length === 0 ? <p style={{ color: '#6b7280' }}>No itineraries found.</p> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {itineraries.map(it => {
            const avg = avgRating(it.feedbacks);
            const isOpen = expanded === it.id;
            const parsed = parseNarrative(it.generatedNarrative);

            return (
              <div key={it.id} style={{ border: '1px solid #e5e7eb', borderRadius: 10, background: '#fff', overflow: 'hidden' }}>
                {/* Header */}
                <div onClick={() => setExpanded(isOpen ? null : it.id)}
                  style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 20px', cursor: 'pointer', userSelect: 'none' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 15 }}>{it.name}</div>
                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                      {it.user?.email} · {new Date(it.createdAt).toLocaleDateString()} · {parsed?.stops?.length ?? it.stops.length} stops
                      {parsed?.summary && <span> · {parsed.summary}</span>}
                    </div>
                  </div>
                  {avg !== null ? (
                    <span style={{ fontSize: 13, fontWeight: 600, color: ratingColor(avg), background: '#f9fafb', padding: '4px 10px', borderRadius: 6 }}>
                      {ratingLabel(avg)} ({it.feedbacks.length})
                    </span>
                  ) : (
                    <span style={{ fontSize: 12, color: '#9ca3af' }}>No feedback</span>
                  )}
                  <span style={{ color: '#9ca3af', fontSize: 18 }}>{isOpen ? '▲' : '▼'}</span>
                </div>

                {/* Expanded */}
                {isOpen && (
                  <div style={{ borderTop: '1px solid #f3f4f6', padding: '20px', background: '#fafafa' }}>
                    {/* Prompt */}
                    {it.originalPrompt && (
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#374151', marginBottom: 6 }}>💬 User Prompt</div>
                        <div style={{ fontSize: 13, color: '#4b5563', background: '#fff', padding: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}>
                          {it.originalPrompt}
                        </div>
                      </div>
                    )}

                    {/* Route info bar */}
                    {parsed && (
                      <div style={{ display: 'flex', gap: 16, marginBottom: 16, fontSize: 12, color: '#6b7280', flexWrap: 'wrap' }}>
                        {parsed.travel_mode && <span>{parsed.travel_mode === 'walking' ? '🚶 Walking' : '🚗 Driving'}</span>}
                        {parsed.total_travel_time_min && <span>🕐 {parsed.total_travel_time_min} min travel</span>}
                        {parsed.stops?.length && <span>📍 {parsed.stops.length} stops</span>}
                        {parsed.route_url && (
                          <a href={parsed.route_url} target="_blank" rel="noopener" style={{ color: '#1d4ed8', textDecoration: 'none' }}>
                            🗺️ Open in Google Maps
                          </a>
                        )}
                      </div>
                    )}

                    {/* Stops timeline */}
                    {parsed?.stops && parsed.stops.length > 0 ? (
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#374151', marginBottom: 12 }}>📋 Itinerary Stops</div>
                        {parsed.stops.map((s, i) => (
                          <StopCard key={s.order} stop={s} isLast={i === parsed.stops.length - 1} />
                        ))}
                      </div>
                    ) : (
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#374151', marginBottom: 8 }}>📋 Stops</div>
                        {it.stops.map(s => (
                          <div key={s.stopOrder} style={{ fontSize: 13, marginBottom: 4 }}>
                            {s.stopOrder}. {s.poi?.name || '—'} {s.travelTimeMin ? `(+${s.travelTimeMin}m travel)` : ''}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Feedback */}
                    {it.feedbacks.length > 0 && (
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#374151', marginBottom: 6 }}>⭐ User Feedback</div>
                        {it.feedbacks.map((f) => (
                          <div key={f.id} style={{ fontSize: 13, marginBottom: 8, padding: 10, background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <span style={{ color: ratingColor(f.rating), fontWeight: 600 }}>{ratingLabel(f.rating)}</span>
                            <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, background: f.status === 'reviewed' ? '#dbeafe' : '#fef3c7', color: f.status === 'reviewed' ? '#2563eb' : '#d97706', fontWeight: 600 }}>
                              {f.status}
                            </span>
                            {f.comment && <span style={{ color: '#4b5563' }}>— {f.comment}</span>}
                            <span style={{ color: '#9ca3af', fontSize: 11 }}>{new Date(f.createdAt).toLocaleDateString()}</span>
                            <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                              {f.status === 'pending' && (
                                <button onClick={() => markReviewed(f.id)} disabled={saving === f.id} style={{
                                  padding: '3px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 11,
                                  background: '#2563eb', color: '#fff',
                                }}>{saving === f.id ? '...' : '✓ Reviewed'}</button>
                              )}
                              <button onClick={() => removeFeedback(f.id)} style={{
                                padding: '3px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 11,
                                background: '#ef4444', color: '#fff',
                              }}>🗑</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Chat history */}
                    {it.chatHistory?.length > 0 && (
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#374151', marginBottom: 8 }}>💬 Chat History ({it.chatHistory.length})</div>
                        <div style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                          {it.chatHistory.map((m, i) => (
                            <div key={i} style={{
                              fontSize: 12, padding: '8px 12px', borderRadius: 8,
                              background: m.role === 'user' ? '#dbeafe' : '#fff', border: '1px solid #e5e7eb',
                              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '80%',
                            }}>
                              <span style={{ fontWeight: 600, color: m.role === 'user' ? '#1d4ed8' : '#374151' }}>
                                {m.role === 'user' ? 'User' : 'AI'}:
                              </span>{' '}
                              {m.content.length > 300 ? m.content.slice(0, 300) + '…' : m.content}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: 8, marginTop: 24, justifyContent: 'center' }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #d1d5db', cursor: page === 1 ? 'not-allowed' : 'pointer', background: '#fff' }}>← Prev</button>
          <span style={{ alignSelf: 'center', fontSize: 13, color: '#6b7280' }}>Page {page} of {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #d1d5db', cursor: page === totalPages ? 'not-allowed' : 'pointer', background: '#fff' }}>Next →</button>
        </div>
      )}
    </div>
  );
}
