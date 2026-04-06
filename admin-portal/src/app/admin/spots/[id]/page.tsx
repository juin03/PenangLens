'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const GoogleMap = dynamic(() => import('@/components/GoogleMap'), { ssr: false });

interface SpotData {
  id: string; name: string; type: string; status: string;
  description?: string; location?: string;
  content?: { overview?: string; history?: string; culture?: string; funFacts?: string };
  images?: { id: string; url: string; filename: string }[];
  tags?: string[];
}

const ALL_TAGS = ['Heritage', 'Historical', 'Food', 'Nature', 'Adventure', 'Art', 'Religious', 'Architecture', 'Shopping', 'Culture'];

const TABS = ['Overview', 'History', 'Culture', 'Fun Facts'] as const;
const TAB_KEYS = ['overview', 'history', 'culture', 'funFacts'] as const;
type TabKey = typeof TAB_KEYS[number];

function isValidLatLng(location?: string): boolean {
  const parts = String(location || '').replace(/[°NSEW\s]/g, '').split(',');
  if (parts.length !== 2) return false;
  const lat = Number(parts[0]);
  const lng = Number(parts[1]);
  return !Number.isNaN(lat) && !Number.isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}

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
  const [deletingImages, setDeletingImages] = useState(false);
  const [aiInstructions, setAiInstructions] = useState('');
  const [showCurateModal, setShowCurateModal] = useState(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  // Image Upload state
  const [uploadState, setUploadState] = useState<{file: File, status: string}[]>([]);

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
    if (!spot?.location || !isValidLatLng(spot.location)) {
      alert('Location must be GPS coordinates in lat,lng format (example: 5.416400,100.332700).');
      return;
    }
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
      const res = await fetch(`/api/admin/spots/${id}/curate`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ instructions: aiInstructions }) 
      });
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
    setShowCurateModal(false);
  };

  const handleDelete = async () => {
    if (!confirm('Delete this spot permanently?')) return;
    await fetch(`/api/admin/spots/${id}`, { method: 'DELETE' });
    router.push('/admin/spots');
  };

  const handleImageUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const newFiles = Array.from(files).map(f => ({ file: f, status: 'uploading' }));
    setUploadState(p => [...p, ...newFiles]);

    for (const item of newFiles) {
      const fd = new FormData();
      fd.append('image', item.file);
      try {
        const res = await fetch(`/api/admin/spots/${id}/images`, { method: 'POST', body: fd });
        if (res.ok) {
          setUploadState(p => p.map(u => u.file === item.file ? { ...u, status: 'success' } : u));
        } else {
          setUploadState(p => p.map(u => u.file === item.file ? { ...u, status: 'error' } : u));
        }
      } catch {
        setUploadState(p => p.map(u => u.file === item.file ? { ...u, status: 'error' } : u));
      }
    }
    // Clear success after 3 seconds
    setTimeout(() => {
      setUploadState(p => p.filter(u => u.status !== 'success'));
    }, 3000);
  };

  const handleDeleteImages = async () => {
    if (!confirm('Are you sure you want to delete all indexed images for this spot?')) return;
    setDeletingImages(true);
    try {
      const res = await fetch(`/api/admin/spots/${id}/images`, { method: 'DELETE' });
      if (res.ok) {
        setSpot(prev => prev ? { ...prev, images: [] } : prev);
        alert('All images deleted successfully.');
      } else {
        const err = await res.json();
        alert(`Failed to delete images: ${err.error}`);
      }
    } catch {
      alert('Failed to delete images.');
    }
    setDeletingImages(false);
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
          <button className="btn btn-ai" onClick={() => setShowCurateModal(true)} disabled={curating}>
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
                  <label className="form-label">Location (GPS coordinates only)</label>
                  <input className="form-input" placeholder="e.g. 5.421500,100.335100"
                    value={spot.location || ''} onChange={e => { setSpot(p => p ? { ...p, location: e.target.value } : p); setDirty(true); }} />
                  <div style={{ marginTop: 8 }}>
                    <GoogleMap
                      height={220}
                      center={spot.location && isValidLatLng(spot.location) ? { lat: parseFloat(spot.location.split(',')[0]), lng: parseFloat(spot.location.split(',')[1]) } : undefined}
                      markers={spot.location && isValidLatLng(spot.location) ? [{ lat: parseFloat(spot.location.split(',')[0]), lng: parseFloat(spot.location.split(',')[1]), label: spot.name }] : []}
                      onMapClick={(lat, lng) => { setSpot(p => p ? { ...p, location: `${lat.toFixed(6)},${lng.toFixed(6)}` } : p); setDirty(true); }}
                    />
                  </div>
                </div>
                <div style={{ gridColumn: '1/-1' }}>
                  <label className="form-label">Short Description</label>
                  <textarea className="form-textarea" rows={3} placeholder="Brief tagline description..."
                    value={spot.description || ''} onChange={e => { setSpot(p => p ? { ...p, description: e.target.value } : p); setDirty(true); }} />
                </div>
                <div style={{ gridColumn: '1/-1' }}>
                  <label className="form-label">Tags</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {ALL_TAGS.map(tag => {
                      const active = spot.tags?.includes(tag);
                      return (
                        <button key={tag} type="button" onClick={() => {
                          setSpot(p => {
                            if (!p) return p;
                            const current = p.tags || [];
                            const next = active ? current.filter(t => t !== tag) : [...current, tag];
                            return { ...p, tags: next };
                          });
                          setDirty(true);
                        }} style={{
                          padding: '4px 12px', borderRadius: 16, border: '1px solid', cursor: 'pointer', fontSize: 12, fontWeight: 500,
                          borderColor: active ? '#2563eb' : '#d1d5db',
                          background: active ? '#2563eb' : '#fff',
                          color: active ? '#fff' : '#374151',
                        }}>{tag}</button>
                      );
                    })}
                  </div>
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

          {/* Reference Images Bulk Upload */}
          <div className="card" style={{ marginTop: 16 }}>
            <div className="card-header" style={{ fontWeight: 700, fontSize: 14 }}>Reference Images</div>
            <div className="card-body">
              <p style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
                Upload multiple photos to train the DINOv2 vision model for scanning.
              </p>
              
              <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', border: '2px dashed #d1d5db', borderRadius: 8, padding: '20px', cursor: 'pointer', background: '#f9fafb' }}>
                <span style={{ fontSize: 24, marginBottom: 4 }}>📸</span>
                <span style={{ fontSize: 12.5, fontWeight: 600, color: '#374151', textAlign: 'center' }}>Click to bulk upload</span>
                <input type="file" accept="image/*" multiple style={{ display: 'none' }} onChange={e => handleImageUpload(e.target.files)} />
              </label>

              {uploadState.length > 0 && (
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {uploadState.map((img, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, padding: '6px 10px', background: '#f3f4f6', borderRadius: 4 }}>
                      <span style={{ color: '#374151', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{img.file.name}</span>
                      <span style={{ fontWeight: 600, color: img.status === 'success' ? '#22c55e' : img.status === 'error' ? '#ef4444' : '#f59e0b' }}>
                        {img.status === 'uploading' ? 'Indexing...' : img.status === 'success' ? 'Indexed ✓' : 'Failed ✗'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {spot.images && spot.images.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <p style={{ fontSize: 13, fontWeight: 600, color: '#374151', margin: 0 }}>Indexed Reference Images ({spot.images.length})</p>
                    <button
                      className="btn btn-danger"
                      style={{ padding: '4px 10px', fontSize: 11 }}
                      onClick={handleDeleteImages}
                      disabled={deletingImages}
                    >
                      {deletingImages ? 'Deleting...' : '🗑 Delete All'}
                    </button>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                    {spot.images.map((img: any) => {
                      const imageId = img.imageId || img.url?.split('/').pop()?.replace('.jpg', '') || img.id;
                      const src = img.url?.startsWith('https://') ? img.url : img.url?.startsWith('/') ? img.url : `/uploads/images/${img.url}.jpg`;
                      return (
                        <div key={img.id} style={{ position: 'relative', borderRadius: 6, overflow: 'hidden', border: '1px solid #e5e7eb', height: 75, cursor: 'pointer' }}
                          onClick={() => setSelectedImage(src)}>
                          <img src={src} alt={img.filename} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          <button
                            onClick={async (e) => {
                              e.stopPropagation();
                              if (!confirm('Delete this image and remove from vision index?')) return;
                              const res = await fetch(`/api/admin/spots/${id}/images/${imageId}`, { method: 'DELETE' });
                              if (res.ok) setSpot(prev => prev ? { ...prev, images: prev.images!.filter((i: any) => i.id !== img.id) } : prev);
                              else alert('Failed to delete image.');
                            }}
                            style={{ position: 'absolute', top: 3, right: 3, background: 'rgba(239,68,68,0.9)', border: 'none', borderRadius: 4, color: '#fff', fontSize: 10, fontWeight: 700, padding: '2px 5px', cursor: 'pointer' }}
                          >✕</button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>
      </div>

      {/* Image Lightbox Modal */}
      {selectedImage && (
        <div 
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, cursor: 'pointer' }}
          onClick={() => setSelectedImage(null)}
        >
          <div style={{ position: 'relative', maxWidth: '90vw', maxHeight: '90vh' }}>
            <img 
              src={selectedImage} 
              alt="Full size preview" 
              style={{ maxWidth: '100%', maxHeight: '90vh', objectFit: 'contain', borderRadius: 8, boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }}
              onClick={(e) => e.stopPropagation()}
            />
            <button
              onClick={() => setSelectedImage(null)}
              style={{ position: 'absolute', top: -40, right: 0, background: 'rgba(255,255,255,0.9)', border: 'none', borderRadius: '50%', width: 36, height: 36, cursor: 'pointer', fontSize: 20, fontWeight: 700, color: '#374151', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* AI Curation Modal */}
      {showCurateModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <div className="card" style={{ width: '100%', maxWidth: 500, padding: 0, overflow: 'hidden' }}>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700 }}>✨ AI Content Curation</span>
              <button onClick={() => setShowCurateModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#9ca3af' }}>&times;</button>
            </div>
            <div className="card-body">
              <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 16 }}>
                Provide optional context (like Wikipedia text) or specific instructions to guide the AI in generating content for <strong>{spot.name}</strong>.
              </p>
              <label className="form-label">Instructions / Context</label>
              <textarea 
                className="form-textarea" 
                rows={8} 
                style={{ fontSize: 13 }}
                placeholder="e.g. Paste wikipedia history here, or say 'Refine the fun facts to be more exciting'..." 
                value={aiInstructions}
                onChange={e => setAiInstructions(e.target.value)}
              />
            </div>
            <div style={{ padding: '16px 24px', background: '#f9fafb', borderTop: '1px solid #f0f0f0', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button className="btn btn-outline" onClick={() => setShowCurateModal(false)}>Cancel</button>
              <button className="btn btn-ai" onClick={handleAICurate} disabled={curating}>
                {curating ? '⏳ Generating...' : '✨ Start Curation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
