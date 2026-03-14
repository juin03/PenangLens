'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';

const GoogleMap = dynamic(() => import('@/components/GoogleMap'), { ssr: false });

interface MapSpot {
  id: string; name: string; type: string; status: string;
  lat: number; lng: number; tags?: string[]; description?: string;
}

export default function AdminMapPage() {
  const [spots, setSpots] = useState<MapSpot[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'landmark' | 'poi'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'published' | 'draft'>('all');

  useEffect(() => { fetchSpots(); }, []);

  const fetchSpots = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/spots/map?all=true');
      const data = await res.json();
      setSpots(data.spots || []);
    } catch { setSpots([]); }
    setLoading(false);
  };

  const filtered = spots.filter(s => {
    const mt = filter === 'all' || s.type === filter;
    const ms = statusFilter === 'all' || s.status === statusFilter;
    return mt && ms;
  });

  const markerColor = (s: MapSpot) => {
    if (s.status === 'draft') return '#9ca3af';
    return s.type === 'landmark' ? '#2563eb' : '#22c55e';
  };

  const markers = filtered.map(s => ({
    lat: s.lat, lng: s.lng,
    label: s.name,
    color: markerColor(s),
    popupHtml: `
      <div style="min-width:160px;font-family:Inter,sans-serif">
        <div style="font-weight:700;font-size:13px;color:#111827;margin-bottom:3px">${s.name}</div>
        <div style="font-size:11px;color:#6b7280;margin-bottom:6px">${s.type === 'landmark' ? '🏛️ Landmark' : '📍 POI'} · ${s.status}</div>
        ${s.description ? `<div style="font-size:12px;color:#374151;margin-bottom:8px">${s.description.slice(0, 80)}${s.description.length > 80 ? '...' : ''}</div>` : ''}
        <a href="/admin/spots/${s.id}" style="font-size:12px;color:#2563eb;font-weight:600;text-decoration:none">✏️ Edit Spot →</a>
      </div>
    `,
  }));

  const publishedCount = spots.filter(s => s.status === 'published').length;
  const landmarkCount = spots.filter(s => s.type === 'landmark').length;
  const poiCount = spots.filter(s => s.type === 'poi').length;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h1 className="page-title">Penang Heritage Map</h1>
          <p className="page-sub">All landmarks and POIs plotted on the map. Click any pin to see details.</p>
        </div>
        <Link href="/admin/spots" className="btn btn-primary">＋ Add New Spot</Link>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
        {[
          { label: 'Total Spots', value: spots.length, color: '#6b7280' },
          { label: 'Published', value: publishedCount, color: '#15803d' },
          { label: 'Landmarks', value: landmarkCount, color: '#2563eb' },
          { label: 'POIs', value: poiCount, color: '#22c55e' },
        ].map(s => (
          <div key={s.label} className="stat-card" style={{ padding: '14px 18px' }}>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value" style={{ fontSize: 22, color: s.color }}>{loading ? '…' : s.value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ padding: '12px 18px', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Filter:</span>
          {(['all', 'landmark', 'poi'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`btn btn-sm ${filter === f ? 'btn-primary' : 'btn-outline'}`}>
              {f === 'all' ? '🗺️ All' : f === 'landmark' ? '🏛️ Landmarks' : '📍 POIs'}
            </button>
          ))}
          <span style={{ marginLeft: 8, fontSize: 13, fontWeight: 600, color: '#374151' }}>Status:</span>
          {(['all', 'published', 'draft'] as const).map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={`btn btn-sm ${statusFilter === s ? 'btn-primary' : 'btn-outline'}`}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 12, fontSize: 12.5, color: '#6b7280', alignItems: 'center' }}>
        <span>Legend:</span>
        {[
          { color: '#2563eb', label: 'Landmark (Published)' },
          { color: '#22c55e', label: 'POI (Published)' },
          { color: '#9ca3af', label: 'Draft (any type)' },
        ].map(l => (
          <span key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 12, height: 12, borderRadius: '50%', background: l.color, display: 'inline-block' }} />
            {l.label}
          </span>
        ))}
      </div>

      {/* Map */}
      <div className="card" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ height: 560, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 14 }}>
            Loading map...
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ height: 560, position: 'relative' }}>
            <GoogleMap height={560} zoom={12} markers={[]} />
            <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', background: 'rgba(255,255,255,0.95)', borderRadius: 10, padding: '16px 24px', textAlign: 'center', zIndex: 1000, boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }}>
              <p style={{ color: '#6b7280', fontSize: 14, margin: 0 }}>No spots with GPS coordinates yet.<br />Add landmarks and click the map to set pins.</p>
            </div>
          </div>
        ) : (
          <GoogleMap height={560} zoom={12} markers={markers} />
        )}
      </div>

      {/* List below */}
      {filtered.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header" style={{ fontWeight: 700 }}>
            Spots on Map ({filtered.length})
          </div>
          <table className="admin-table">
            <thead>
              <tr>
                <th>NAME</th>
                <th>TYPE</th>
                <th>COORDINATES</th>
                <th>STATUS</th>
                <th style={{ textAlign: 'right' }}>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 600 }}>{s.name}</td>
                  <td><span style={{ fontSize: 13, color: '#6b7280' }}>{s.type === 'landmark' ? '🏛️ Landmark' : '📍 POI'}</span></td>
                  <td><span style={{ fontFamily: 'monospace', fontSize: 12, color: '#6b7280' }}>{s.lat.toFixed(4)}, {s.lng.toFixed(4)}</span></td>
                  <td><span className={`badge badge-${s.status}`}>{s.status}</span></td>
                  <td style={{ textAlign: 'right' }}>
                    <Link href={`/admin/spots/${s.id}`} className="btn btn-outline btn-sm">✏️ Edit</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
