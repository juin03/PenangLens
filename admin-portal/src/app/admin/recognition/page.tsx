'use client';

import { useEffect, useState } from 'react';
import s from '../admin.module.css';

interface FeedbackItem {
  id: string; isCorrect: boolean; status: string; adminNotes?: string; createdAt: string;
  user?: { email: string };
  recognition?: { userImageUrl?: string; aiDetails?: { poi_name?: string; name?: string; description?: string }; poi?: { name: string } };
}

export default function RecognitionFeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [saving, setSaving] = useState<string | null>(null);
  const [enlarged, setEnlarged] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const load = () => {
    const token = localStorage.getItem('admin_token');
    fetch(`/api/admin/recognition-feedback?status=${statusFilter}&page=${page}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).then(r => r.json()).then(d => { setItems(d.items ?? []); setTotal(d.total ?? 0); });
  };

  useEffect(() => { load(); }, [page, statusFilter]);

  const markReviewed = async (id: string) => {
    setSaving(id);
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/feedback/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ status: 'reviewed' }),
    });
    setSaving(null); load();
  };

  const remove = async (id: string) => {
    if (!confirm('Delete this feedback?')) return;
    const token = localStorage.getItem('admin_token');
    await fetch(`/api/admin/feedback/${id}`, { method: 'DELETE', headers: token ? { Authorization: `Bearer ${token}` } : {} });
    load();
  };

  const toggle = (id: string) => {
    setExpanded(prev => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next; });
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className={s.page}>
      <h1 className={s.pageTitle}>🔍 Recognition Feedback</h1>
      <p className={s.pageSubtitle}>Review user-reported incorrect landmark scans.</p>

      <div className={s.filterBar}>
        {['pending', 'reviewed', 'all'].map(v => (
          <button key={v} className={`${s.filterBtn} ${statusFilter === v ? s.filterBtnActive : ''}`}
            onClick={() => { setStatusFilter(v); setPage(1); }} style={{ textTransform: 'capitalize' }}>{v}</button>
        ))}
        <span className={s.filterCount}>{total} items</span>
      </div>

      {items.length === 0 ? <p className={s.empty}>No feedback found.</p> : (
        <>
          {items.map(item => {
            const isOpen = expanded.has(item.id);
            const rec = item.recognition;
            return (
              <div key={item.id} className={s.card}>
                <div className={s.cardHeader} onClick={() => toggle(item.id)}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 14, color: '#111827' }}>
                      {rec?.poi?.name ?? rec?.aiDetails?.poi_name ?? rec?.aiDetails?.name ?? 'Unknown landmark'}
                    </div>
                    <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>
                      {item.user?.email ?? 'Guest'} · {new Date(item.createdAt).toLocaleDateString()}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                    <span className={`${s.badge} ${item.isCorrect ? s.badgeGood : s.badgeBad}`}>
                      {item.isCorrect ? '✓ Correct' : '✗ Wrong'}
                    </span>
                    <span className={`${s.badge} ${item.status === 'reviewed' ? s.badgeReviewed : s.badgePending}`}>
                      {item.status}
                    </span>
                    <span style={{ color: '#9ca3af', fontSize: 16 }}>{isOpen ? '▲' : '▼'}</span>
                  </div>
                </div>

                {isOpen && (
                  <div className={s.cardBody}>
                    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                      {rec?.userImageUrl && (
                        <div className={s.section} style={{ flexShrink: 0 }}>
                          <div className={s.sectionTitle}>📷 Scanned Image</div>
                          <img
                            src={rec.userImageUrl} alt="scan"
                            style={{ width: 140, height: 140, objectFit: 'cover', borderRadius: 10, cursor: 'zoom-in', border: '1px solid #e5e7eb' }}
                            onClick={() => setEnlarged(rec.userImageUrl!)}
                          />
                        </div>
                      )}
                      <div style={{ flex: 1 }}>
                        {rec?.aiDetails && (
                          <div className={s.section}>
                            <div className={s.sectionTitle}>🤖 AI Identified As</div>
                            <div className={s.promptBox}>
                              <strong>{rec.aiDetails.poi_name ?? rec.aiDetails.name ?? 'Unknown landmark'}</strong>
                              {rec.aiDetails.description && <div style={{ marginTop: 4, color: '#6b7280' }}>{rec.aiDetails.description}</div>}
                            </div>
                          </div>
                        )}
                        {item.adminNotes && (
                          <div className={s.section}>
                            <div className={s.sectionTitle}>📝 Admin Notes</div>
                            <div className={s.promptBox}>{item.adminNotes}</div>
                          </div>
                        )}
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                      {item.status === 'pending' && (
                        <button className={s.btnPrimary} onClick={() => markReviewed(item.id)} disabled={saving === item.id}>
                          {saving === item.id ? '…' : '✓ Mark Reviewed'}
                        </button>
                      )}
                      <button className={s.btnDanger} onClick={() => remove(item.id)}>🗑 Delete</button>
                    </div>
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

      {/* Enlarged image overlay */}
      {enlarged && (
        <div onClick={() => setEnlarged(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, cursor: 'zoom-out' }}>
          <img src={enlarged} alt="enlarged" style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 12, objectFit: 'contain' }} />
        </div>
      )}
    </div>
  );
}
