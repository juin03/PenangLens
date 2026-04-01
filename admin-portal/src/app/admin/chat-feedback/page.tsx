'use client';

import { useEffect, useState } from 'react';

interface ChatFeedbackItem {
  id: string; rating: number; aiMessage: string; userMessage?: string; context?: string; createdAt: string;
  user?: { email: string };
}

export default function ChatFeedbackPage() {
  const [items, setItems] = useState<ChatFeedbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [ratingFilter, setRatingFilter] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('admin_token');
    const params = new URLSearchParams({ page: String(page) });
    if (ratingFilter) params.set('rating', ratingFilter);
    fetch(`/api/admin/chat-feedback?${params}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).then(r => r.json()).then(d => { setItems(d.items ?? []); setTotal(d.total ?? 0); });
  }, [page, ratingFilter]);

  const totalPages = Math.ceil(total / 20);

  return (
    <div style={{ padding: 32, maxWidth: 1000, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>💬 Chat Feedback Review</h1>
      <p style={{ color: '#6b7280', marginBottom: 24 }}>User thumbs up/down on AI chat responses.</p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {[{ label: 'All', val: '' }, { label: '👍 Positive', val: '1' }, { label: '👎 Negative', val: '-1' }].map(f => (
          <button key={f.val} onClick={() => { setRatingFilter(f.val); setPage(1); }} style={{
            padding: '6px 14px', borderRadius: 6, border: '1px solid #d1d5db', cursor: 'pointer',
            background: ratingFilter === f.val ? '#1d4ed8' : '#fff',
            color: ratingFilter === f.val ? '#fff' : '#374151', fontWeight: ratingFilter === f.val ? 600 : 400,
          }}>{f.label}</button>
        ))}
        <span style={{ marginLeft: 'auto', color: '#6b7280', alignSelf: 'center' }}>{total} items</span>
      </div>

      {items.length === 0 ? <p style={{ color: '#6b7280' }}>No feedback found.</p> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map(item => (
            <div key={item.id} style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: 16, background: '#fff' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 20 }}>{item.rating === 1 ? '👍' : '👎'}</span>
                <span style={{ fontSize: 12, color: '#6b7280' }}>{item.user?.email ?? 'Guest'} · {new Date(item.createdAt).toLocaleDateString()}</span>
                {item.context && <span style={{ fontSize: 11, background: '#f3f4f6', padding: '2px 8px', borderRadius: 4, color: '#374151' }}>{item.context}</span>}
              </div>
              {item.userMessage && (
                <div style={{ fontSize: 12, marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, color: '#1d4ed8' }}>User:</span> {item.userMessage}
                </div>
              )}
              <div style={{ fontSize: 12, background: '#f9fafb', padding: 10, borderRadius: 6, color: '#374151' }}>
                <span style={{ fontWeight: 600 }}>AI:</span> {item.aiMessage.length > 300 ? item.aiMessage.slice(0, 300) + '…' : item.aiMessage}
              </div>
            </div>
          ))}
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
