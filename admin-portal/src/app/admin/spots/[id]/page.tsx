'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';

interface SpotData {
  id: string; name: string; type: string; status: string;
  description?: string; location?: string;
  content?: { overview?: string; history?: string; culture?: string; funFacts?: string };
}

const TABS = ['Overview', 'History', 'Culture', 'Fun Facts'] as const;
const TAB_KEYS = ['overview', 'history', 'culture', 'funFacts'] as const;
type TabKey = typeof TAB_KEYS[number];

export default function SpotDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [spot, setSpot] = useState<SpotData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [content, setContent] = useState<Record<TabKey, string>>({
    overview: '', history: '', culture: '', funFacts: '',
  });
  const [saving, setSaving] = useState(false);
  const [curating, setCurating] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!id) return;
    fetch(`/api/admin/spots/${id}`)
      .then(r => r.json())
      .then(data => {
        setSpot(data.spot);
        const c = data.spot?.content || {};
        setContent({ overview: c.overview || '', history: c.history || '', culture: c.culture || '', funFacts: c.funFacts || '' });
      })
      .finally(() => setLoading(false));
  }, [id]);

  const updateContent = (key: TabKey, value: string) => {
    setContent(prev => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const handleSave = async (status?: string) => {
    setSaving(true);
    const payload = { ...spot, content, type: spot?.type, status: status || spot?.status };
    const res = await fetch(`/api/admin/spots/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      setDirty(false);
      if (status) setSpot(prev => prev ? { ...prev, status } : prev);
    }
    setSaving(false);
  };

  const handleAICurate = async () => {
    setCurating(true);
    try {
      const res = await fetch(`/api/admin/spots/${id}/curate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const data = await res.json();
      if (data.content) {
        setContent({
          overview: data.content.overview || content.overview,
          history: data.content.history || content.history,
          culture: data.content.culture || content.culture,
          funFacts: data.content.funFacts || content.funFacts,
        });
        setDirty(true);
      }
    } catch { alert('AI curation failed. Is the Agent running?'); }
    setCurating(false);
  };

  const handleDelete = async () => {
    if (!confirm('Delete this spot permanently?')) return;
    await fetch(`/api/admin/spots/${id}`, { method: 'DELETE' });
    router.push('/admin/spots');
  };

  if (loading) return <div style={{ padding: 60, textAlign: 'center', color: '#9ca3af' }}>Loading...</div>;
  if (!spot) return <div style={{ padding: 60, textAlign: 'center', color: '#ef4444' }}>Spot not found.</div>;

  return (
    <div>
      {/* Breadcrumb */}
      <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 16 }}>
        <Link href="/admin/spots" style={{ color: '#6b7280', textDecoration: 'none' }}>Dashboard / Spots</Link>
        <span style={{ margin: '0 8px' }}>/</span>
        <span style={{ color: '#374151' }}>{spot.name}</span>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#111827' }}>{spot.name}</h1>
          <span className={`badge badge-${spot.type === 'landmark' ? 'new' : 'reviewed'}`} style={{ fontSize: 12 }}>
            {spot.type === 'landmark' ? 'Landmark' : 'POI'}
          </span>
          <span className={`badge badge-${spot.status}`}>{spot.status}</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-danger" onClick={handleDelete}>🗑 Delete Spot</button>
          <button className="btn btn-ai" onClick={handleAICurate} disabled={curating}>
            {curating ? '⏳ Curating...' : '✨ AI Curate Content'}
          </button>
          <button className="btn btn-primary" onClick={() => handleSave(spot.status === 'draft' ? 'published' : 'draft')} disabled={saving}>
            {spot.status === 'draft' ? '🚀 Publish' : '📋 Unpublish'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24 }}>
        {/* Left: Content */}
        <div>
          {/* Meta section */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <label className="form-label">Name</label>
                  <input className="form-input" value={spot.name}
                    onChange={e => { setSpot(p => p ? { ...p, name: e.target.value } : p); setDirty(true); }} />
                </div>
                <div>
                  <label className="form-label">Type</label>
                  <input className="form-input" value={spot.type === 'landmark' ? 'Landmark' : 'Point of Interest'} disabled style={{ background: '#f9fafb' }} />
                </div>
                <div style={{ gridColumn: '1/-1' }}>
                  <label className="form-label">Location (GPS or Address)</label>
                  <input className="form-input" placeholder="e.g. 5.4215° N, 100.3351° E"
                    value={spot.location || ''} onChange={e => { setSpot(p => p ? { ...p, location: e.target.value } : p); setDirty(true); }} />
                </div>
                <div style={{ gridColumn: '1/-1' }}>
                  <label className="form-label">Short Description</label>
                  <textarea className="form-textarea" rows={3} placeholder="Brief tagline description..."
                    value={spot.description || ''} onChange={e => { setSpot(p => p ? { ...p, description: e.target.value } : p); setDirty(true); }} />
                </div>
              </div>
            </div>
          </div>

          {/* Content Editor */}
          <div className="card">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700, fontSize: 15 }}>Content</span>
              {curating && <span style={{ fontSize: 12, color: '#7c3aed' }}>✨ AI generating content...</span>}
            </div>
            <div className="card-body">
              <div className="tab-bar">
                {TABS.map((tab, i) => (
                  <div key={tab} className={`tab-item ${activeTab === TAB_KEYS[i] ? 'active' : ''}`}
                    onClick={() => setActiveTab(TAB_KEYS[i])}>
                    {tab}
                  </div>
                ))}
              </div>
              <textarea
                className="form-textarea"
                style={{ minHeight: 220 }}
                placeholder={`Write ${TABS[TAB_KEYS.indexOf(activeTab)]} content here...`}
                value={content[activeTab]}
                onChange={e => updateContent(activeTab, e.target.value)}
              />
            </div>
            <div style={{ padding: '14px 24px', borderTop: '1px solid #f0f0f0', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button className="btn btn-outline" onClick={() => { setDirty(false); }} disabled={!dirty}>Discard Changes</button>
              <button className="btn btn-outline" onClick={() => handleSave('draft')} disabled={saving}>Save Draft</button>
              <button className="btn btn-primary" onClick={() => handleSave('published')} disabled={saving}>
                {saving ? 'Publishing...' : 'Publish'}
              </button>
            </div>
          </div>
        </div>

        {/* Right: Metadata sidebar */}
        <div>
          <div className="card">
            <div className="card-header" style={{ fontWeight: 700, fontSize: 14 }}>Details</div>
            <div className="card-body" style={{ fontSize: 13.5 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <span style={{ color: '#9ca3af', fontSize: 12, fontWeight: 600 }}>TYPE</span>
                  <p style={{ marginTop: 3, fontWeight: 600 }}>{spot.type === 'landmark' ? 'Landmark' : 'Point of Interest'}</p>
                </div>
                <div>
                  <span style={{ color: '#9ca3af', fontSize: 12, fontWeight: 600 }}>STATUS</span>
                  <p style={{ marginTop: 3 }}>
                    <span className={`badge badge-${spot.status}`}>{spot.status.charAt(0).toUpperCase() + spot.status.slice(1)}</span>
                  </p>
                </div>
                <div>
                  <span style={{ color: '#9ca3af', fontSize: 12, fontWeight: 600 }}>GPS</span>
                  <p style={{ marginTop: 3, fontFamily: 'monospace', fontSize: 12, color: '#374151' }}>
                    {spot.location || '—'}
                  </p>
                </div>
                <div>
                  <span style={{ color: '#9ca3af', fontSize: 12, fontWeight: 600 }}>CONTENT SECTIONS</span>
                  <p style={{ marginTop: 6, color: '#6b7280', fontSize: 12 }}>
                    {(['overview', 'history', 'culture', 'funFacts'] as TabKey[]).map(k => (
                      <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                        <span style={{ color: content[k] ? '#22c55e' : '#d1d5db' }}>●</span>
                        {k.charAt(0).toUpperCase() + k.slice(1)} {content[k] ? '✓' : '(empty)'}
                      </span>
                    ))}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Map placeholder */}
          <div className="card" style={{ marginTop: 16, overflow: 'hidden' }}>
            <div style={{ height: 160, background: '#e8f0fe', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8, color: '#6b7280', fontSize: 13 }}>
              <span style={{ fontSize: 28 }}>🗺️</span>
              <span>{spot.location ? spot.location : 'No location set'}</span>
              {spot.location && <a href={`https://maps.google.com/?q=${encodeURIComponent(spot.location)}`} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontSize: 12 }}>Open in Maps ↗</a>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
