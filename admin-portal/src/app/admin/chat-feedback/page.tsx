'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import s from '../admin.module.css';

interface ChatFeedbackItem {
  id: string; rating: number; aiMessage: string; userMessage?: string; context?: string; threadId?: string; createdAt: string;
  user?: { email: string };
  threadHistory?: { role: string; content: string; createdAt: string }[] | null;
}

export default function ChatFeedbackPage() {
  const [items, setItems] = useState<ChatFeedbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [ratingFilter, setRatingFilter] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [threadExpanded, setThreadExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    const token = localStorage.getItem('admin_token');
    const params = new URLSearchParams({ page: String(page) });
    if (ratingFilter) params.set('rating', ratingFilter);
    fetch(`/api/admin/chat-feedback?${params}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => r.json()).then(d => { setItems(d.items ?? []); setTotal(d.total ?? 0); });
  }, [page, ratingFilter]);

  const toggle = (id: string, set: Set<string>, setter: (s: Set<string>) => void) => {
    const next = new Set(set); next.has(id) ? next.delete(id) : next.add(id); setter(next);
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className={s.page}>
      <h1 className={s.pageTitle}>💬 Chat Feedback Review</h1>
      <p className={s.pageSubtitle}>User thumbs up/down on AI chat responses.</p>

      <div className={s.filterBar}>
        {[{ label: 'All', val: '' }, { label: '👍 Positive', val: '1' }, { label: '👎 Negative', val: '-1' }].map(f => (
          <button key={f.val} className={`${s.filterBtn} ${ratingFilter === f.val ? s.filterBtnActive : ''}`}
            onClick={() => { setRatingFilter(f.val); setPage(1); }}>{f.label}</button>
        ))}
        <span className={s.filterCount}>{total} items</span>
      </div>

      {items.length === 0 ? <p className={s.empty}>No feedback found.</p> : (
        <>
          {items.map(item => {
            const isExpanded = expanded.has(item.id);
            const isThreadOpen = threadExpanded.has(item.id);
            const isLong = item.aiMessage.length > 300;
            return (
              <div key={item.id} className={s.card}>
                <div className={s.cardHeader} onClick={() => toggle(item.id, expanded, setExpanded)}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.aiMessage.slice(0, 120)}{item.aiMessage.length > 120 ? '…' : ''}
                    </div>
                    <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 3 }}>
                      {item.user?.email ?? 'Guest'} · {new Date(item.createdAt).toLocaleDateString()}
                      {item.context && <span> · {item.context}</span>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                    <span className={`${s.badge} ${item.rating === 1 ? s.badgeGood : s.badgeBad}`}>
                      {item.rating === 1 ? '👍' : '👎'}
                    </span>
                    <span style={{ color: '#9ca3af', fontSize: 16 }}>{isExpanded ? '▲' : '▼'}</span>
                  </div>
                </div>

                {isExpanded && (
                  <div className={s.cardBody}>
                    {item.userMessage && (
                      <div className={s.section}>
                        <div className={s.sectionTitle}>👤 User Message</div>
                        <div className={s.promptBox}>{item.userMessage}</div>
                      </div>
                    )}

                    <div className={s.section}>
                      <div className={s.sectionTitle}>🤖 AI Response</div>
                      <div className={s.promptBox} style={{ maxHeight: isLong && !isExpanded ? 120 : undefined, overflow: 'hidden' }}>
                        <ReactMarkdown>{item.aiMessage}</ReactMarkdown>
                      </div>
                    </div>

                    {item.threadId && (
                      <div className={s.section}>
                        <button className={s.filterBtn} onClick={() => toggle(item.id, threadExpanded, setThreadExpanded)}>
                          {isThreadOpen ? '▾ Hide conversation' : '› View full conversation'}
                        </button>
                        {isThreadOpen && item.threadHistory && (
                          <div className={s.chatWrap} style={{ marginTop: 8 }}>
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
