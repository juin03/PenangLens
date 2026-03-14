'use client';

import { useEffect, useRef, useState } from 'react';

interface Props {
  center?: [number, number];
  zoom?: number;
  height?: number | string;
  onMapClick?: (lat: number, lng: number) => void;
  markers?: { lat: number; lng: number; label: string; color?: string; popupHtml?: string }[];
  selectedLat?: number;
  selectedLng?: number;
}

export default function LeafletMap({
  center = [5.4164, 100.3327],
  zoom = 12,
  height = 320,
  onMapClick,
  markers = [],
  selectedLat,
  selectedLng,
}: Props) {
  const mapRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const clickMarkerRef = useRef<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');

  // Nominatim geocoding search — free, no API key needed
  const handleSearch = async () => {
    if (!searchQuery.trim() || !mapRef.current) return;
    setSearching(true);
    setSearchError('');
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(searchQuery)}&format=json&countrycodes=my&limit=5`,
        { headers: { 'Accept-Language': 'en' } }
      );
      const results = await res.json();
      if (!results.length) { setSearchError('Place not found. Try a more specific name.'); return; }
      const { lat, lon } = results[0];
      mapRef.current.setView([parseFloat(lat), parseFloat(lon)], 17);
    } catch {
      setSearchError('Search failed. Check your connection.');
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    if (typeof window === 'undefined' || !containerRef.current) return;

    import('leaflet').then(L => {
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      });

      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; }

      const map = L.map(containerRef.current!).setView(center, zoom);
      mapRef.current = map;

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);

      const makeIcon = (color: string) => L.divIcon({
        html: `<div style="width:24px;height:24px;border-radius:50% 50% 50% 0;background:${color};border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.35);transform:rotate(-45deg);"></div>`,
        className: '', iconSize: [24, 24], iconAnchor: [12, 24], popupAnchor: [0, -28],
      });

      markers.forEach(m => {
        const marker = L.marker([m.lat, m.lng], { icon: makeIcon(m.color || '#2563eb') }).addTo(map);
        marker.bindPopup(m.popupHtml || `<b>${m.label}</b>`);
      });

      if (selectedLat !== undefined && selectedLng !== undefined) {
        clickMarkerRef.current = L.marker([selectedLat, selectedLng], { icon: makeIcon('#ef4444') })
          .addTo(map).bindPopup('📍 Selected location').openPopup();
      }

      if (onMapClick) {
        map.on('click', (e: any) => {
          const { lat, lng } = e.latlng;
          if (clickMarkerRef.current) clickMarkerRef.current.remove();
          clickMarkerRef.current = L.marker([lat, lng], { icon: makeIcon('#ef4444') })
            .addTo(map).bindPopup(`📍 ${lat.toFixed(5)}, ${lng.toFixed(5)}`).openPopup();
          onMapClick(lat, lng);
        });
      }
    });

    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    if (!document.querySelector('link[href*="leaflet"]')) document.head.appendChild(link);

    return () => { if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; } };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      {/* Search bar — shown only in GPS-picking mode */}
      {onMapClick && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              style={{
                flex: 1, padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 8,
                fontSize: 13.5, outline: 'none', fontFamily: 'inherit', color: '#111827',
                background: '#fff',
              }}
              placeholder='🔍 Search place (e.g. "Kek Lok Si Temple, Penang")...'
              value={searchQuery}
              onChange={e => { setSearchQuery(e.target.value); setSearchError(''); }}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
            <button
              onClick={handleSearch}
              disabled={searching || !searchQuery.trim()}
              style={{
                padding: '8px 14px', background: '#2563eb', color: '#fff', border: 'none',
                borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: searching ? 'not-allowed' : 'pointer',
                opacity: searching ? 0.7 : 1, whiteSpace: 'nowrap',
              }}
            >
              {searching ? '…' : 'Search'}
            </button>
          </div>
          <p style={{ fontSize: 11.5, color: searchError ? '#ef4444' : '#9ca3af', marginTop: 4, marginBottom: 0 }}>
            {searchError || 'Search to navigate → then click the map to drop the GPS pin'}
          </p>
        </div>
      )}

      <div
        ref={containerRef}
        style={{
          height, width: '100%', borderRadius: 10, overflow: 'hidden',
          border: '1px solid #e8eaed', cursor: onMapClick ? 'crosshair' : 'default',
        }}
      />
    </div>
  );
}
