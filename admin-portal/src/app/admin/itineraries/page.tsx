'use client';

import { useEffect, useState } from 'react';
import s from '../admin.module.css';

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
const ratingBadge = (r: number) => r >= 4 ? s.badgeGood : r <= 2 ? s.badgeBad : s.badgeNeutral;
const avgRating = (fb: Feedback[]) => fb.length ? fb.reduce((a, f) => a + f.rating, 0) / fb.length : null;

function parseNarrative(raw?: string) {
  if (!raw) return null;
  try { return JSON.parse(raw) as { stops: ParsedStop[]; summary?: string; route_url?: string; travel_mode?: string; total_travel_time_min?: number; start_time?: string; end_time?: string; interests?: string[] }; }
  catch { return null; }
}

function StopCard({ stop, isLast }: { stop: ParsedStop; isLast: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div className={s.stopRow}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 28 }}>
          <div className={s.stopDot}>{stop.order}</div>
          {!isLast && <div style={{ width: 2, flex: 1, background: '#e5e7eb', minHeight: 32, marginTop: 4 }} />}
        </div>
        <div className={s.stopCard} style={{ marginBottom: isLast ? 0 : 8 }}>
          <div style={{ display: 'flex', gap: 10 }}>
            {stop.photo_url && <img src={stop.photo_url} alt={stop.name} style={{ width: 60, height: 60, borderRadius: 8, objectFit: 'cover', flexShrink: 0 }} />}
            <div style={{ flex: 1 }}>
              <div className={s.stopName}>{stop.name}</div>
              <div className={s.stopMeta}>
                {stop.arrival_time && <span>🕐 {stop.arrival_time} – {stop.departure_time}</span>}
                {stop.visit_duration_min && <span> · {stop.visit_duration_min} min</span>}
                {stop.rating && <span> · ⭐ {stop.rating}</span>}
              </div>
              {stop.short_description && <div style={{ fontSize: 12, color: '#4b5563', marginTop: 4 }}>{stop.short_description}</div>}
              {stop.description && (
                <>
                  <span onClick={() => setOpen(!open)} style={{ fontSize: 11, color: '#1d4ed8', cursor: 'pointer', marginTop: 4, display: 'inline-block' }}>
                    {open ? '▾ Hide' : '› Show details'}
                  </span>
                  {open && <div style={{ fontSize: 12, color: '#4b5563', marginTop: 4, lineHeight: 1.5 }}>{stop.description}</div>}
                </>
              )}
              {stop.address && <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>📍 {stop.address}</div>}
            </div>
          </div>
        </div>
      </div>
      {!isLast && stop.travel_to_next && (
        <div className={s.travelSeg}>
          {stop.travel_to_next.mode === 'walking' ? '🚶' : '🚗'} {stop.travel_to_next.duration_text} · {stop.travel_to_next.distance_text}
        </div>
      )}
    </div>
  );
}

function PlanSnapshot({ label, plan, defaultOpen = false }: { label: string; plan: { stops: ParsedStop[]; summary?: string }; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>{label}</div>
      <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 10, overflow: 'hidden' }}>
        <div onClick={() => setOpen(o => !o)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', cursor: 'pointer' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#15803d' }}>{plan.summary || `${plan.stops?.length} stops`}</span>
          <span style={{ fontSize: 11, color: '#15803d' }}>{open ? '▾ Hide' : '› Show stops'}</span>
        </div>
        {open && (
          <div style={{ padding: '0 14px 14px' }}>
            {plan.stops.map((st, i) => <StopCard key={st.order} stop={st} isLast={i === plan.stops.length - 1} />)}
            <div onClick={() => setOpen(false)} style={{ textAlign: 'center', fontSize: 11, color: '#15803d', cursor: 'pointer', marginTop: 4 }}>▴ Hide stops</div>
          </div>
        )}
      </div>
    </div>
  );
}

function ChatHistory({ history }: { history: ChatMsg[] }) {
  let planVersion = 1;
  return (
    <div className={s.chatWrap}>
      {history.map((m, i) => {
        if (m.role === 'plan') {
          planVersion++;
          const version = planVersion;
          try {
            const p = JSON.parse(m.content) as { stops: ParsedStop[]; summary?: string; travel_mode?: string };
            return <PlanSnapshot key={i} label={`📋 Updated plan (v${version})`} plan={p} />;
          } catch { return null; }
        }
        return (
          <div key={i} className={`${s.bubble} ${m.role === 'user' ? s.bubbleUser : s.bubbleAI}`}>
            <span className={s.bubbleLabel}>{m.role === 'user' ? 'User' : 'AI'}:</span>
            {m.content.length > 300 ? m.content.slice(0, 300) + '…' : m.content}
          </div>
        );
      })}
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
    fetch(`/api/admin/itineraries?${params}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => r.json())
      .then(d => { setItineraries(d.itineraries ?? []); setTotal(d.total ?? 0); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page, filter, statusFilter]);

  const markReviewed = async (id: string) => {
    setSaving(id);
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/itineraries/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ status: 'reviewed' }),
    });
    setSaving(null); load();
  };

  const removeFeedback = async (id: string) => {
    if (!confirm('Delete this feedback?')) return;
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/itineraries/${id}`, { method: 'DELETE', headers: token ? { Authorization: `Bearer ${token}` } : {} });
    load();
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className={s.page}>
      <h1 className={s.pageTitle}>🗓️ Itinerary Review</h1>
      <p className={s.pageSubtitle}>Review AI-generated itineraries and user feedback.</p>

      <div className={s.filterBar}>
        {(['pending', 'reviewed', 'all'] as const).map(v => (
          <button key={v} className={`${s.filterBtn} ${statusFilter === v ? s.filterBtnActive : ''}`}
            onClick={() => { setStatusFilter(v); setPage(1); }} style={{ textTransform: 'capitalize' }}>{v}</button>
        ))}
        <div className={s.filterDivider} />
        {([['all', 'All Ratings'], ['good', '👍 Good'], ['bad', '👎 Bad']] as const).map(([v, label]) => (
          <button key={v} className={`${s.filterBtn} ${filter === v ? s.filterBtnActive : ''}`}
            onClick={() => { setFilter(v as 'all' | 'good' | 'bad'); setPage(1); }}>{label}</button>
        ))}
        <span className={s.filterCount}>{total} itineraries</span>
      </div>

      {loading ? <p className={s.empty}>Loading…</p> : itineraries.length === 0 ? <p className={s.empty}>No itineraries found.</p> : (
        <>
          {itineraries.map(it => {
            const avg = avgRating(it.feedbacks);
            const isOpen = expanded === it.id;
            const parsed = parseNarrative(it.generatedNarrative);
            return (
              <div key={it.id} className={s.card}>
                <div className={s.cardHeader} onClick={() => setExpanded(isOpen ? null : it.id)}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 15, color: '#111827', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{it.name}</div>
                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                      {it.user?.email} · {new Date(it.createdAt).toLocaleDateString()} · {parsed?.stops?.length ?? it.stops.length} stops
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                    {avg !== null
                      ? <span className={`${s.badge} ${ratingBadge(avg)}`}>{ratingLabel(avg)} ({it.feedbacks.length})</span>
                      : <span style={{ fontSize: 12, color: '#9ca3af' }}>No feedback</span>}
                    <span style={{ color: '#9ca3af', fontSize: 16 }}>{isOpen ? '▲' : '▼'}</span>
                  </div>
                </div>

                {isOpen && (
                  <div className={s.cardBody}>
                    {/* Trip metadata */}
                    {parsed && (
                      <div className={s.section}>
                        <div className={s.sectionTitle}>🗺️ Trip Details</div>
                        <div className={s.metaRow}>
                          {parsed.travel_mode && <span>{parsed.travel_mode === 'walking' ? '🚶 Walking' : '🚗 Driving'}</span>}
                          {parsed.start_time && parsed.end_time && <span>🕐 {parsed.start_time} – {parsed.end_time}</span>}
                          {parsed.total_travel_time_min && <span>🚦 {Math.round(parsed.total_travel_time_min)} min travel</span>}
                          {parsed.stops?.length && <span>📍 {parsed.stops.length} stops</span>}
                          {parsed.route_url && <a href={parsed.route_url} target="_blank" rel="noopener">🗺️ Open in Google Maps</a>}
                        </div>
                        {parsed.interests?.length && (
                          <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {parsed.interests.map(int => (
                              <span key={int} className={`${s.badge} ${s.badgeReviewed}`}>{int}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Chronological timeline */}
                    <div className={s.section}>
                      <div className={s.sectionTitle}>📜 Full Session Timeline</div>

                      {it.originalPrompt && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>👤 User request</div>
                          <div className={s.promptBox}>{it.originalPrompt}</div>
                        </div>
                      )}

                      {(() => {
                        const firstPlanMsg = it.chatHistory?.find(m => m.role === 'plan');
                        const v1 = firstPlanMsg ? (() => { try { return JSON.parse(firstPlanMsg.content); } catch { return null; } })() : parsed;
                        return v1?.stops?.length ? <PlanSnapshot label="🤖 Original plan (v1)" plan={v1} /> : null;
                      })()}

                      {it.chatHistory?.filter(m => m.role !== 'plan').length > 0 && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>💬 Conversation & modifications</div>
                          <ChatHistory history={it.chatHistory} />
                        </div>
                      )}

                      {parsed?.stops?.length && !it.chatHistory?.some(m => m.role === 'plan') && (
                        <PlanSnapshot label="🤖 Generated plan" plan={parsed} defaultOpen />
                      )}
                    </div>

                    {/* Feedback */}
                    {it.feedbacks.length > 0 && (
                      <div className={s.section}>
                        <div className={s.sectionTitle}>⭐ User Feedback</div>
                        {it.feedbacks.map(f => (
                          <div key={f.id} className={s.feedbackRow}>
                            <span className={`${s.badge} ${ratingBadge(f.rating)}`}>{ratingLabel(f.rating)}</span>
                            <span className={`${s.badge} ${f.status === 'reviewed' ? s.badgeReviewed : s.badgePending}`}>{f.status}</span>
                            {f.comment && <span style={{ fontSize: 13, color: '#4b5563' }}>— {f.comment}</span>}
                            <span style={{ fontSize: 11, color: '#9ca3af' }}>{new Date(f.createdAt).toLocaleDateString()}</span>
                            <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                              {f.status === 'pending' && (
                                <button className={s.btnPrimary} onClick={() => markReviewed(f.id)} disabled={saving === f.id}>
                                  {saving === f.id ? '…' : '✓ Reviewed'}
                                </button>
                              )}
                              <button className={s.btnDanger} onClick={() => removeFeedback(f.id)}>🗑</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          <div className={s.pagination}>
            <button className={s.pageBtn} disabled={page === 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <span className={s.pageInfo}>Page {page} of {totalPages}</span>
            <button className={s.pageBtn} disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        </>
      )}
    </div>
  );
}
