'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const GoogleMap = dynamic(() => import('@/components/GoogleMap'), { ssr: false });

const CATEGORY_TAGS = ['Heritage', 'Religious', 'Architecture', 'Nature', 'Food & Culture', 'Historical', 'Waterfront', 'Shopping'];

interface Spot {
  id: string; name: string; type: 'landmark' | 'poi';
  status: 'draft' | 'published'; poiCount?: number;
  updatedAt: string; location?: string; tags?: string[];
  pois?: Spot[];
}

type Step = 'type' | 'landmark' | 'poi' | 'images';

interface UploadedImage {
  file: File;
  preview: string;
  status: 'pending' | 'uploading' | 'indexed' | 'error';
  error?: string;
}

export default function SpotsPage() {
  const [spots, setSpots] = useState<Spot[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [tagFilter, setTagFilter] = useState('all');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [step, setStep] = useState<Step>('type');
  const [saving, setSaving] = useState(false);
  const [createdSpotId, setCreatedSpotId] = useState<string>('');
  const [images, setImages] = useState<UploadedImage[]>([]);
  const [indexingCount, setIndexingCount] = useState(0);

  // Landmark form
  const [lmForm, setLmForm] = useState({
    name: '', description: '', location: '', lat: '', lng: '',
    tags: [] as string[], status: 'draft',
  });

  // POI form
  const [poiForm, setPoiForm] = useState({
    name: '', description: '', landmarkId: '', location: '', lat: '', lng: '',
    searchPrompts: '', status: 'draft',
  });

  useEffect(() => { fetchSpots(); }, []);

  const fetchSpots = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/admin/spots', {
        headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` },
      });
      const data = await res.json();
      setSpots(data.spots || []);
    } catch { setSpots([]); }
    setLoading(false);
  };

  useEffect(() => {
    if (search.length > 0) {
      const newExpanded = new Set(expanded);
      let changed = false;
      const searchLower = search.toLowerCase();
      spots.forEach(s => {
        if (s.pois?.some(p => p.name.toLowerCase().includes(searchLower))) {
          if (!newExpanded.has(s.id)) {
            newExpanded.add(s.id);
            changed = true;
          }
        }
      });
      if (changed) setExpanded(newExpanded);
    }
  }, [search, spots]);

  const toggleExpand = (id: string) => setExpanded(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleSelect = (id: string) => setSelected(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this spot?')) return;
    await fetch(`/api/admin/spots/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` },
    });
    fetchSpots();
  };

  const openModal = () => {
    setStep('type');
    setCreatedSpotId('');
    setImages([]);
    setIndexingCount(0);
    setLmForm({ name: '', description: '', location: '', lat: '', lng: '', tags: [], status: 'draft' });
    setPoiForm({ name: '', description: '', landmarkId: '', location: '', lat: '', lng: '', searchPrompts: '', status: 'draft' });
    setShowModal(true);
  };

  const handleCreateLandmark = async () => {
    if (!lmForm.lat || !lmForm.lng) {
      alert('Please set GPS coordinates (latitude and longitude) before creating this landmark.');
      return;
    }
    setSaving(true);
    const location = `${parseFloat(lmForm.lat).toFixed(6)},${parseFloat(lmForm.lng).toFixed(6)}`;
    try {
      const res = await fetch('/api/admin/spots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('admin_token')}` },
        body: JSON.stringify({ type: 'landmark', name: lmForm.name, description: lmForm.description, location, tags: lmForm.tags, status: lmForm.status }),
      });
      const data = await res.json();
      const newId = data.spot?.id || data.id;
      if (newId) { setCreatedSpotId(newId); setImages([]); setStep('images'); fetchSpots(); }
      else { setShowModal(false); fetchSpots(); }
    } catch { alert('Failed to create landmark.'); }
    setSaving(false);
  };

  const handleCreatePOI = async () => {
    if (!poiForm.lat || !poiForm.lng) {
      alert('Please set GPS coordinates (latitude and longitude) before creating this POI.');
      return;
    }
    setSaving(true);
    const location = `${parseFloat(poiForm.lat).toFixed(6)},${parseFloat(poiForm.lng).toFixed(6)}`;
    try {
      const res = await fetch('/api/admin/spots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('admin_token')}` },
        body: JSON.stringify({ type: 'poi', name: poiForm.name, description: poiForm.description, location, landmarkId: poiForm.landmarkId, searchPrompts: poiForm.searchPrompts.split(',').map(s => s.trim()).filter(Boolean), status: poiForm.status }),
      });
      const data = await res.json();
      const newId = data.spot?.id || data.id;
      if (newId) { setCreatedSpotId(newId); setImages([]); setStep('images'); fetchSpots(); }
      else { setShowModal(false); fetchSpots(); }
    } catch { alert('Failed to create POI.'); }
    setSaving(false);
  };

  const handleImageFiles = (files: FileList | null) => {
    if (!files) return;
    const newImgs: UploadedImage[] = Array.from(files)
      .filter(f => f.type.startsWith('image/'))
      .map(f => ({ file: f, preview: URL.createObjectURL(f), status: 'pending' }));
    setImages(prev => [...prev, ...newImgs]);
  };

  const handleIndexImages = async () => {
    const pending = images.filter(i => i.status === 'pending');
    if (!pending.length || !createdSpotId) return;
    setIndexingCount(0);
    for (let i = 0; i < images.length; i++) {
      if (images[i].status !== 'pending') continue;
      setImages(prev => prev.map((img, idx) => idx === i ? { ...img, status: 'uploading' } : img));
      try {
        const fd = new FormData();
        fd.append('image', images[i].file);
        const res = await fetch(`/api/admin/spots/${createdSpotId}/images`, { method: 'POST', body: fd });
        if (res.ok) {
          setImages(prev => prev.map((img, idx) => idx === i ? { ...img, status: 'indexed' } : img));
          setIndexingCount(c => c + 1);
        } else {
          const { error } = await res.json();
          setImages(prev => prev.map((img, idx) => idx === i ? { ...img, status: 'error', error } : img));
        }
      } catch (e: any) {
        setImages(prev => prev.map((img, idx) => idx === i ? { ...img, status: 'error', error: e.message } : img));
      }
    }
  };

  const landmarks = spots.filter(s => s.type === 'landmark');
  
  const searchLower = search.toLowerCase();
  const filtered = spots.filter(s => {
    const parentMatches = s.name.toLowerCase().includes(searchLower);
    const childMatches = s.pois?.some(p => p.name.toLowerCase().includes(searchLower)) ?? false;
    const ms = searchLower === '' ? true : (parentMatches || childMatches);
    const mf = statusFilter === 'all' || s.status === statusFilter;
    const mt = tagFilter === 'all' || (s.tags && s.tags.includes(tagFilter));
    return ms && mf && mt;
  });

  // Default sort alphabetically if no search is typed
  if (!search) {
    filtered.sort((a, b) => a.name.localeCompare(b.name));
  }

  const fmt = (d: string) => new Date(d).toLocaleString('en-MY', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Spots Management</h1>
          <p className="page-sub">Manage landmarks and points of interest.</p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Link href="/admin/map" className="btn btn-outline">🗺️ View Map</Link>
          <button className="btn btn-primary" onClick={openModal}>＋ Add New Spot</button>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ padding: '14px 20px', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <input className="form-input" placeholder="Search by spot name..." style={{ width: 280 }} value={search} onChange={e => setSearch(e.target.value)} />
          <select className="form-input form-select" style={{ width: 160 }} value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="all">Status: All</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
          </select>
          <select className="form-input form-select" style={{ width: 160 }} value={tagFilter} onChange={e => setTagFilter(e.target.value)}>
            <option value="all">Category: All</option>
            {CATEGORY_TAGS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      {/* Bulk bar */}
      {selected.size > 0 && (
        <div style={{ marginBottom: 12, background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12, fontSize: 13.5 }}>
          <span style={{ color: '#1d4ed8', fontWeight: 600 }}>{selected.size} items selected</span>
          <button className="btn btn-outline btn-sm">✅ Approve</button>
          <button className="btn btn-danger btn-sm">🗑 Delete</button>
        </div>
      )}

      {/* Table */}
      <div className="card">
        <table className="admin-table">
          <thead>
            <tr>
              <th style={{ width: 36 }}><input type="checkbox" className="checkbox" /></th>
              <th>SPOT NAME</th>
              <th>TYPE</th>
              <th># OF POIS</th>
              <th>STATUS</th>
              <th>LAST UPDATED</th>
              <th style={{ textAlign: 'right' }}>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>
                No spots yet. Click <strong>+ Add New Spot</strong> to create your first landmark!
              </td></tr>
            ) : filtered.map(spot => (
              <React.Fragment key={spot.id}>
                <tr key={spot.id}>
                  <td><input type="checkbox" className="checkbox" checked={selected.has(spot.id)} onChange={() => toggleSelect(spot.id)} /></td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {spot.type === 'landmark' && (spot.pois?.length ?? 0) > 0 && (
                        <button onClick={() => toggleExpand(spot.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280', fontSize: 13, width: 18 }}>
                          {expanded.has(spot.id) ? '▾' : '▸'}
                        </button>
                      )}
                      <span style={{ fontWeight: spot.type === 'landmark' ? 700 : 400, color: '#111827' }}>
                        {spot.name}
                      </span>
                      {spot.tags?.slice(0, 2).map(t => (
                        <span key={t} style={{ background: '#eff6ff', color: '#2563eb', fontSize: 11, padding: '2px 7px', borderRadius: 4, fontWeight: 600 }}>{t}</span>
                      ))}
                    </div>
                  </td>
                  <td><span style={{ color: '#6b7280', fontSize: 13 }}>{spot.type === 'landmark' ? 'Landmark' : 'POI'}</span></td>
                  <td style={{ color: '#6b7280' }}>{spot.type === 'landmark' ? (spot.poiCount ?? 0) : '—'}</td>
                  <td><span className={`badge badge-${spot.status}`}>{spot.status.charAt(0).toUpperCase() + spot.status.slice(1)}</span></td>
                  <td style={{ color: '#6b7280', fontSize: 13 }}>{fmt(spot.updatedAt)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <Link href={`/admin/spots/${spot.id}`} className="btn btn-outline btn-sm" style={{ marginRight: 6 }}>✏️ Edit</Link>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(spot.id)}>🗑</button>
                  </td>
                </tr>
                {/* Child POIs */}
                {spot.type === 'landmark' && expanded.has(spot.id) && spot.pois?.map(poi => (
                  <tr key={poi.id} style={{ background: '#fafbff' }}>
                    <td><input type="checkbox" className="checkbox" checked={selected.has(poi.id)} onChange={() => toggleSelect(poi.id)} /></td>
                    <td><span style={{ paddingLeft: 36, color: '#6b7280', fontSize: 13 }}>↳ {poi.name}</span></td>
                    <td><span style={{ color: '#9ca3af', fontSize: 12 }}>POI</span></td>
                    <td style={{ color: '#9ca3af' }}>—</td>
                    <td><span className={`badge badge-${poi.status}`}>{poi.status.charAt(0).toUpperCase() + poi.status.slice(1)}</span></td>
                    <td style={{ color: '#9ca3af', fontSize: 12 }}>{fmt(poi.updatedAt)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <Link href={`/admin/spots/${poi.id}`} className="btn btn-outline btn-sm" style={{ marginRight: 6 }}>✏️ Edit</Link>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(poi.id)}>🗑</button>
                    </td>
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
        <div style={{ padding: '12px 20px', borderTop: '1px solid #f0f0f0', fontSize: 13, color: '#6b7280', display: 'flex', justifyContent: 'space-between' }}>
          <span>Showing 1–{filtered.length} of {filtered.length}</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-outline btn-sm">Previous</button>
            <button className="btn btn-outline btn-sm">Next</button>
          </div>
        </div>
      </div>

      {/* ─── Multi-step Add Spot Modal ─── */}
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <div className="card" style={{ width: '100%', maxWidth: 620, maxHeight: '90vh', overflowY: 'auto', padding: 0 }}>

            {/* STEP 1: Choose type */}
            {step === 'type' && (
              <div style={{ padding: 32 }}>
                <h2 style={{ fontSize: 18, fontWeight: 800, color: '#111827', marginBottom: 6 }}>Add New Spot</h2>
                <p style={{ fontSize: 13.5, color: '#6b7280', marginBottom: 28 }}>What kind of spot are you adding?</p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 28 }}>
                  <button onClick={() => setStep('landmark')} style={{
                    border: '2px solid #e8eaed', borderRadius: 12, padding: '24px 20px', background: '#f9fafb',
                    cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s',
                  }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = '#2563eb'; (e.currentTarget as HTMLElement).style.background = '#eff6ff'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = '#e8eaed'; (e.currentTarget as HTMLElement).style.background = '#f9fafb'; }}>
                    <div style={{ fontSize: 28, marginBottom: 10 }}>🏛️</div>
                    <div style={{ fontWeight: 700, color: '#111827', marginBottom: 4 }}>Landmark</div>
                    <div style={{ fontSize: 12.5, color: '#6b7280' }}>A whole heritage site or area (parent). E.g. Kek Lok Si Temple, Clan Jetties</div>
                  </button>
                  <button onClick={() => setStep('poi')} style={{
                    border: '2px solid #e8eaed', borderRadius: 12, padding: '24px 20px', background: '#f9fafb',
                    cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s',
                  }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = '#22c55e'; (e.currentTarget as HTMLElement).style.background = '#f0fdf4'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = '#e8eaed'; (e.currentTarget as HTMLElement).style.background = '#f9fafb'; }}>
                    <div style={{ fontSize: 28, marginBottom: 10 }}>📍</div>
                    <div style={{ fontWeight: 700, color: '#111827', marginBottom: 4 }}>Point of Interest (POI)</div>
                    <div style={{ fontSize: 12.5, color: '#6b7280' }}>A specific, scannable element inside a landmark. E.g. Pagoda of Rama VI, Guan Yin Statue</div>
                  </button>
                </div>
                <button className="btn btn-outline" style={{ width: '100%' }} onClick={() => setShowModal(false)}>Cancel</button>
              </div>
            )}

            {/* STEP 2a: Landmark Form */}
            {step === 'landmark' && (
              <div style={{ padding: '24px 28px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                  <button onClick={() => setStep('type')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280', fontSize: 13 }}>← Back</button>
                  <h2 style={{ fontSize: 17, fontWeight: 800, color: '#111827', margin: 0 }}>🏛️ New Landmark</h2>
                </div>

                <label className="form-label">Name *</label>
                <input className="form-input" style={{ marginBottom: 14 }} placeholder="e.g. Kek Lok Si Temple" value={lmForm.name} onChange={e => setLmForm(p => ({ ...p, name: e.target.value }))} />

                <label className="form-label">Short Description *</label>
                <textarea className="form-textarea" rows={2} style={{ marginBottom: 14 }} placeholder="One or two sentences shown on mobile cards..." value={lmForm.description} onChange={e => setLmForm(p => ({ ...p, description: e.target.value }))} />

                <label className="form-label">Category Tags * <span style={{ color: '#9ca3af', fontWeight: 400 }}>(select all that apply)</span></label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
                  {CATEGORY_TAGS.map(tag => (
                    <button key={tag} onClick={() => setLmForm(p => ({ ...p, tags: p.tags.includes(tag) ? p.tags.filter(t => t !== tag) : [...p.tags, tag] }))}
                      style={{ padding: '5px 12px', borderRadius: 999, fontSize: 12.5, fontWeight: 600, cursor: 'pointer', border: '1.5px solid', transition: 'all 0.12s', borderColor: lmForm.tags.includes(tag) ? '#2563eb' : '#d1d5db', background: lmForm.tags.includes(tag) ? '#eff6ff' : '#fff', color: lmForm.tags.includes(tag) ? '#2563eb' : '#6b7280' }}>
                      {tag}
                    </button>
                  ))}
                </div>

                <label className="form-label">GPS Location * <span style={{ color: '#9ca3af', fontWeight: 400 }}>— click the map to set coordinates</span></label>
                <div style={{ display: 'flex', gap: 10, marginBottom: 8 }}>
                  <input className="form-input" placeholder="Latitude" style={{ flex: 1 }} value={lmForm.lat} onChange={e => setLmForm(p => ({ ...p, lat: e.target.value }))} />
                  <input className="form-input" placeholder="Longitude" style={{ flex: 1 }} value={lmForm.lng} onChange={e => setLmForm(p => ({ ...p, lng: e.target.value }))} />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <GoogleMap
                    height={240}
                    zoom={13}
                    selectedLat={lmForm.lat ? parseFloat(lmForm.lat) : undefined}
                    selectedLng={lmForm.lng ? parseFloat(lmForm.lng) : undefined}
                    onMapClick={(lat, lng) => setLmForm(p => ({ ...p, lat: lat.toFixed(6), lng: lng.toFixed(6) }))}
                  />
                  <p style={{ fontSize: 11.5, color: '#9ca3af', marginTop: 6 }}>🖱️ Click anywhere on the map above to set the GPS pin</p>
                </div>

                <label className="form-label">Status</label>
                <select className="form-input form-select" style={{ marginBottom: 20 }} value={lmForm.status} onChange={e => setLmForm(p => ({ ...p, status: e.target.value }))}>
                  <option value="draft">Draft (not visible on mobile)</option>
                  <option value="published">Published (visible to all users)</option>
                </select>

                <div style={{ display: 'flex', gap: 10 }}>
                  <button className="btn btn-outline" style={{ flex: 1 }} onClick={() => setShowModal(false)}>Cancel</button>
                  <button className="btn btn-primary" style={{ flex: 2 }} onClick={handleCreateLandmark}
                    disabled={!lmForm.name || !lmForm.description || lmForm.tags.length === 0 || !lmForm.lat || !lmForm.lng || saving}>
                    {saving ? 'Creating...' : '🏛️ Create Landmark'}
                  </button>
                </div>
              </div>
            )}

            {/* STEP 2b: POI Form */}
            {step === 'poi' && (
              <div style={{ padding: '24px 28px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                  <button onClick={() => setStep('type')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280', fontSize: 13 }}>← Back</button>
                  <h2 style={{ fontSize: 17, fontWeight: 800, color: '#111827', margin: 0 }}>📍 New Point of Interest</h2>
                </div>

                <label className="form-label">Parent Landmark * <span style={{ color: '#ef4444', fontSize: 12 }}>— required</span></label>
                <select className="form-input form-select" style={{ marginBottom: 14 }}
                  value={poiForm.landmarkId} onChange={e => setPoiForm(p => ({ ...p, landmarkId: e.target.value }))}>
                  <option value="">— Select which landmark this belongs to —</option>
                  {landmarks.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
                {landmarks.length === 0 && <p style={{ fontSize: 12, color: '#f59e0b', marginBottom: 14, marginTop: -8 }}>⚠️ No landmarks yet — create a Landmark first, then add POIs to it.</p>}

                <label className="form-label">POI Name *</label>
                <input className="form-input" style={{ marginBottom: 14 }} placeholder="e.g. Pagoda of Rama VI" value={poiForm.name} onChange={e => setPoiForm(p => ({ ...p, name: e.target.value }))} />

                <label className="form-label">Short Description *</label>
                <textarea className="form-textarea" rows={2} style={{ marginBottom: 14 }} placeholder="What is this specific element?" value={poiForm.description} onChange={e => setPoiForm(p => ({ ...p, description: e.target.value }))} />

                <label className="form-label">Search Prompts * <span style={{ color: '#9ca3af', fontWeight: 400 }}>(comma-separated keywords for VisionML)</span></label>
                <input className="form-input" style={{ marginBottom: 14 }} placeholder="e.g. red pagoda, seven storey tower, kek lok si pagoda" value={poiForm.searchPrompts} onChange={e => setPoiForm(p => ({ ...p, searchPrompts: e.target.value }))} />
                <p style={{ fontSize: 11.5, color: '#9ca3af', marginTop: -10, marginBottom: 14 }}>💡 These help the AI recognise this specific POI when a user scans it.</p>

                <label className="form-label">GPS Location * <span style={{ color: '#9ca3af', fontWeight: 400 }}>— click the map, or type coordinates</span></label>
                <div style={{ display: 'flex', gap: 10, marginBottom: 8 }}>
                  <input className="form-input" placeholder="Latitude" style={{ flex: 1 }} value={poiForm.lat} onChange={e => setPoiForm(p => ({ ...p, lat: e.target.value }))} />
                  <input className="form-input" placeholder="Longitude" style={{ flex: 1 }} value={poiForm.lng} onChange={e => setPoiForm(p => ({ ...p, lng: e.target.value }))} />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <GoogleMap
                    height={220}
                    zoom={15}
                    selectedLat={poiForm.lat ? parseFloat(poiForm.lat) : undefined}
                    selectedLng={poiForm.lng ? parseFloat(poiForm.lng) : undefined}
                    onMapClick={(lat, lng) => setPoiForm(p => ({ ...p, lat: lat.toFixed(6), lng: lng.toFixed(6) }))}
                  />
                  <p style={{ fontSize: 11.5, color: '#9ca3af', marginTop: 6 }}>🖱️ Click the map to pin the exact location</p>
                </div>

                <label className="form-label">Status</label>
                <select className="form-input form-select" style={{ marginBottom: 20 }} value={poiForm.status} onChange={e => setPoiForm(p => ({ ...p, status: e.target.value }))}>
                  <option value="draft">Draft</option>
                  <option value="published">Published</option>
                </select>

                <div style={{ display: 'flex', gap: 10 }}>
                  <button className="btn btn-outline" style={{ flex: 1 }} onClick={() => setShowModal(false)}>Cancel</button>
                  <button className="btn btn-primary" style={{ flex: 2, background: '#22c55e', borderColor: '#22c55e' }} onClick={handleCreatePOI}
                    disabled={!poiForm.name || !poiForm.landmarkId || !poiForm.description || !poiForm.lat || !poiForm.lng || saving}>
                    {saving ? 'Creating...' : '📍 Create POI'}
                  </button>
                </div>
              </div>
            )}
            {/* STEP 3: Image Upload + DINOv2 Indexing */}
            {step === 'images' && (
              <div style={{ padding: '24px 28px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <h2 style={{ fontSize: 17, fontWeight: 800, color: '#111827', margin: 0 }}>📸 Upload Reference Images</h2>
                </div>
                <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 20 }}>
                  Upload real photos of this spot. Each image will be automatically embedded using <strong>DINOv2</strong> and indexed for scan recognition.
                  The more varied angles you upload, the better the recognition accuracy.
                </p>

                {/* Drop zone */}
                <label style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  border: '2px dashed #d1d5db', borderRadius: 10, padding: '28px 20px',
                  cursor: 'pointer', background: '#f9fafb', marginBottom: 16, gap: 8,
                }}>
                  <span style={{ fontSize: 32 }}>🖼️</span>
                  <span style={{ fontSize: 13.5, fontWeight: 600, color: '#374151' }}>Click to select images</span>
                  <span style={{ fontSize: 12, color: '#9ca3af' }}>JPG, PNG — multiple files allowed</span>
                  <input type="file" accept="image/*" multiple style={{ display: 'none' }}
                    onChange={e => handleImageFiles(e.target.files)} />
                </label>

                {/* Image grid previews */}
                {images.length > 0 && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
                    {images.map((img, i) => (
                      <div key={i} style={{ position: 'relative', borderRadius: 8, overflow: 'hidden', border: '1px solid #e5e7eb' }}>
                        <img src={img.preview} alt="preview" style={{ width: '100%', height: 80, objectFit: 'cover', display: 'block' }} />
                        <div style={{
                          position: 'absolute', bottom: 0, left: 0, right: 0, fontSize: 10.5, fontWeight: 700,
                          textAlign: 'center', padding: '3px 4px',
                          background: img.status === 'indexed' ? '#22c55e' : img.status === 'error' ? '#ef4444' : img.status === 'uploading' ? '#f59e0b' : 'rgba(0,0,0,0.5)',
                          color: '#fff',
                        }}>
                          {img.status === 'pending' ? 'Pending' : img.status === 'uploading' ? '⏳ Indexing...' : img.status === 'indexed' ? '✅ Indexed' : '❌ Error'}
                        </div>
                        {img.status === 'error' && <div title={img.error} style={{ position: 'absolute', top: 4, right: 4, background: '#ef4444', color: '#fff', borderRadius: 999, width: 16, height: 16, fontSize: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'help' }}>!</div>}
                      </div>
                    ))}
                  </div>
                )}

                {images.length > 0 && (
                  <div style={{ fontSize: 12.5, color: '#6b7280', marginBottom: 16 }}>
                    {indexingCount}/{images.length} images indexed into DINOv2 vision search
                  </div>
                )}

                <div style={{ display: 'flex', gap: 10 }}>
                  <button className="btn btn-outline" style={{ flex: 1 }} onClick={() => { setShowModal(false); }}>Done — Skip Images</button>
                  {images.some(i => i.status === 'pending') && (
                    <button className="btn btn-primary" style={{ flex: 2 }}
                      onClick={handleIndexImages}>
                      🧠 Index {images.filter(i => i.status === 'pending').length} Image{images.filter(i => i.status === 'pending').length !== 1 ? 's' : ''}
                    </button>
                  )}
                  {images.length > 0 && images.every(i => i.status === 'indexed') && (
                    <button className="btn btn-primary" style={{ flex: 2, background: '#22c55e', borderColor: '#22c55e' }}
                      onClick={() => { setShowModal(false); }}>
                      ✅ All Indexed — Done
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
