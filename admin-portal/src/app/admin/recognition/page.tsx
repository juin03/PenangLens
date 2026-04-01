'use client';

import { useEffect, useState } from 'react';

interface FeedbackItem {
  id: string; isCorrect: boolean; status: string; adminNotes?: string; createdAt: string;
  user?: { email: string };
  recognition?: { userImageUrl?: string; aiDetails?: any; poi?: { name: string } };
}

const STATUS_COLORS: Record<string, string> = { pending: '#d97706', reviewed: '#2563eb' };

export default function RecognitionFeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [saving, setSaving] = useState<string | null>(null);
  const [enlargedImage, setEnlargedImage] = useState<string | null>(null);

  const load = () => {
    const token = localStorage.getItem('admin_token');
    fetch(`/api/admin/recognition-feedback?status=${statusFilter}&page=${page}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).then(r => r.json()).then(d => { setItems(d.items ?? []); setTotal(d.total ?? 0); });
  };

  useEffect(() => { load(); }, [page, statusFilter]);

  const update = async (id: string) => {
    setSaving(id);
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/feedback/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ status: 'reviewed' }),
    });
    setSaving(null);
    load();
  };

  const remove = async (id: string) => {
    if (!confirm('Delete this feedback?')) return;
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/feedback/${id}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    load();
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div style={{ padding: 32, maxWidth: 1000, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>🔍 Recognition Feedback Queue</h1>
      <p style={{ color: '#6b7280', marginBottom: 24 }}>Review user-reported incorrect landmark scans.</p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {['pending', 'reviewed', 'all'].map(s => (
          <button key={s} onClick={() => { setStatusFilter(s); setPage(1); }} style={{
            padding: '6px 14px', borderRadius: 6, border: '1px solid #d1d5db', cursor: 'pointer',
            background: statusFilter === s ? '#1d4ed8' : '#fff',
            color: statusFilter === s ? '#fff' : '#374151', fontWeight: statusFilter === s ? 600 : 400,
            textTransform: 'capitalize',
          }}>{s}</button>
        ))}
        <span style={{ marginLeft: 'auto', color: '#6b7280', alignSelf: 'center' }}>{total} items</span>
      </div>

      {items.length === 0 ? <p style={{ color: '#6b7280' }}>No items found.</p> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {items.map(item => (
            <div key={item.id} style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: 16, background: '#fff' }}>
              <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
                {item.recognition?.userImageUrl && (
                  <img
                    src={item.recognition.userImageUrl}
                    alt="scan"
                    onClick={() => setEnlargedImage(item.recognition?.userImageUrl ?? null)}
                    style={{ width: 120, height: 120, objectFit: 'cover', borderRadius: 8, border: '1px solid #e5e7eb', cursor: 'pointer' }}
                  />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontWeight: 600 }}>{item.recognition?.aiDetails?.poi_name ?? item.recognition?.poi?.name ?? 'Unknown POI'}</span>
                    <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, background: item.isCorrect ? '#dcfce7' : '#fee2e2', color: item.isCorrect ? '#16a34a' : '#dc2626' }}>
                      {item.isCorrect ? '✓ Correct' : '✗ Wrong'}
                    </span>
                    <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, background: '#f3f4f6', color: STATUS_COLORS[item.status] ?? '#374151', fontWeight: 600 }}>
                      {item.status}
                    </span>
                  </div>
                  {item.recognition?.aiDetails?.detections?.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4, marginBottom: 4 }}>
                      {item.recognition.aiDetails.detections.map((d: any, i: number) => (
                        <span key={i} style={{ fontSize: 11, padding: '2px 6px', borderRadius: 4, background: '#eff6ff', color: '#1d4ed8' }}>
                          {d.class?.replace(/_/g, ' ')} ({Math.round(d.confidence * 100)}%)
                        </span>
                      ))}
                    </div>
                  )}
                  {item.recognition?.aiDetails?.timing_ms && (
                    <div style={{ fontSize: 11, color: '#9ca3af' }}>⏱️ {item.recognition.aiDetails.timing_ms}ms · {item.recognition.aiDetails.model}</div>
                  )}
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{item.user?.email} · {new Date(item.createdAt).toLocaleDateString()}</div>
                  {item.status === 'pending' && (
                    <button onClick={() => update(item.id)} disabled={saving === item.id} style={{
                      marginTop: 8, padding: '4px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12,
                      background: '#2563eb', color: '#fff',
                    }}>{saving === item.id ? '...' : '✓ Mark Reviewed'}</button>
                  )}
                  <button onClick={() => remove(item.id)} style={{
                    marginTop: 8, marginLeft: 8, padding: '4px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12,
                    background: '#ef4444', color: '#fff',
                  }}>🗑 Delete</button>
                </div>
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

      {/* Enlarged image modal */}
      {enlargedImage && (
        <div
          onClick={() => setEnlargedImage(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', zIndex: 9999, cursor: 'pointer',
          }}
        >
          <img src={enlargedImage} alt="enlarged" style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 12 }} />
        </div>
      )}
    </div>
  );
}
