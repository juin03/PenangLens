'use client';

import { useEffect, useState } from 'react';
import s from '../admin.module.css';

interface ChatFeedbackItem {
  id: string;
  rating: number;          // 1–5 stars
  comment?: string | null;
  context?: string | null; // landmark / page the chat was about
  threadId?: string | null;
  messageCount?: number | null;
  status: string;          // 'pending' | 'reviewed'
  createdAt: string;
  user?: { email: string } | null;
  threadHistory?: { role: string; content: string; createdAt: string }[] | null;
}

function Stars({ n }: { n: number }) {
  return <span style={{ color: '#f59e0b', letterSpacing: 1 }}>{'★'.repeat(n)}{'☆'.repeat(Math.max(0, 5 - n))}</span>;
}

export default function ChatFeedbackPage() {
  const [items, setItems] = useState<ChatFeedbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [saving, setSaving] = useState<string | null>(null);
  const [threadExpanded, setThreadExpanded] = useState<Set<string>>(new Set());

  const load = () => {
    const token = localStorage.getItem('admin_token');
    const params = new URLSearchParams({ page: String(page), status: statusFilter });
    fetch(`/api/admin/chat-feedback?${params}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => r.json()).then(d => { setItems(d.items ?? []); setTotal(d.total ?? 0); });
  };

  useEffect(() => { load(); }, [page, statusFilter]);

  const markReviewed = async (id: string) => {
    setSaving(id);
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/chat-feedback/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ status: 'reviewed' }),
    });
    setSaving(null); load();
  };

  const removeFeedback = async (id: string) => {
    if (!confirm('Delete this feedback?')) return;
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/chat-feedback/${id}`, { method: 'DELETE', headers: token ? { Authorization: `Bearer ${token}` } : {} });
    load();
  };

  const toggleThread = (id: string) => {
    const next = new Set(threadExpanded);
    next.has(id) ? next.delete(id) : next.add(id);
    setThreadExpanded(next);
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className={s.page}>
      <h1 className={s.pageTitle}>💬 Chat Feedback Review</h1>
      <p className={s.pageSubtitle}>Per-session star ratings users gave the Penang chat assistant.</p>

      <div className={s.filterBar}>
        {(['pending', 'reviewed', 'all'] as const).map(v => (
          <button key={v} className={`${s.filterBtn} ${statusFilter === v ? s.filterBtnActive : ''}`}
            onClick={() => { setStatusFilter(v); setPage(1); }} style={{ textTransform: 'capitalize' }}>{v}</button>
        ))}
        <span className={s.filterCount}>{total} items</span>
      </div>

      {items.length === 0 ? <p className={s.empty}>No feedback found.</p> : (
        <>
          {items.map(item => {
            const isThreadOpen = threadExpanded.has(item.id);
            return (
              <div key={item.id} className={s.card}>
                <div className={s.cardHeader}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 16 }}><Stars n={item.rating} /></div>
                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 3 }}>
                      {item.user?.email ?? 'Guest'} · {new Date(item.createdAt).toLocaleDateString()}
                      {item.context && <span> · {item.context}</span>}
                      {item.messageCount != null && <span> · {item.messageCount} messages</span>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                    <span className={`${s.badge} ${item.status === 'reviewed' ? s.badgeReviewed : s.badgePending}`}>{item.status}</span>
                    {item.status === 'pending' && (
                      <button className={s.btnPrimary} onClick={() => markReviewed(item.id)} disabled={saving === item.id}>
                        {saving === item.id ? '…' : '✓ Reviewed'}
                      </button>
                    )}
                    <button className={s.btnDanger} onClick={() => removeFeedback(item.id)}>🗑</button>
                  </div>
                </div>

                {(item.comment || (item.threadHistory && item.threadHistory.length > 0)) && (
                  <div className={s.cardBody}>
                    {item.comment && (
                      <div className={s.section}>
                        <div className={s.sectionTitle}>💬 Comment</div>
                        <div className={s.promptBox}>{item.comment}</div>
                      </div>
                    )}

                    {item.threadHistory && item.threadHistory.length > 0 && (
                      <div className={s.section} style={{ marginBottom: 0 }}>
                        <button className={s.filterBtn} onClick={() => toggleThread(item.id)}>
                          {isThreadOpen ? '▾ Hide conversation' : '› View full conversation'}
                        </button>
                        {isThreadOpen && (
                          <div className={s.chatWrap} style={{ marginTop: 10 }}>
                            {item.threadHistory.map((m, i) => (
                              <div key={i} className={`${s.bubble} ${m.role === 'user' ? s.bubbleUser : s.bubbleAI}`}>
                                <span className={s.bubbleLabel}>{m.role === 'user' ? 'User' : 'AI'}:</span>
                                {m.content.length > 400 ? m.content.slice(0, 400) + '…' : m.content}
                              </div>
                            ))}
                          </div>
                        )}
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
