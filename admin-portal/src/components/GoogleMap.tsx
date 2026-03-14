'use client';

import { useEffect, useRef, useState } from 'react';

interface Marker {
  lat: number;
  lng: number;
  label: string;
  color?: string;
  popupHtml?: string;
}

interface Props {
  center?: { lat: number; lng: number };
  zoom?: number;
  height?: number | string;
  onMapClick?: (lat: number, lng: number) => void;
  markers?: Marker[];
  selectedLat?: number;
  selectedLng?: number;
}

const PENANG = { lat: 5.4164, lng: 100.3327 };
const API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY!;

// Load Google Maps via script tag (most reliable, avoids loader API changes)
let scriptLoaded = false;
let scriptLoading = false;
const loadCallbacks: (() => void)[] = [];

function loadGoogleMapsScript(onLoad: () => void) {
  if (scriptLoaded) { onLoad(); return; }
  loadCallbacks.push(onLoad);
  if (scriptLoading) return;
  scriptLoading = true;

  const script = document.createElement('script');
  script.src = `https://maps.googleapis.com/maps/api/js?key=${API_KEY}&libraries=places&loading=async`;
  script.async = true;
  script.defer = true;
  script.onload = () => {
    scriptLoaded = true;
    loadCallbacks.forEach(cb => cb());
    loadCallbacks.length = 0;
  };
  document.head.appendChild(script);
}

export default function GoogleMap({
  center = PENANG,
  zoom = 13,
  height = 320,
  onMapClick,
  markers = [],
  selectedLat,
  selectedLng,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const clickMarkerRef = useRef<google.maps.Marker | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    loadGoogleMapsScript(() => setLoaded(true));
  }, []);

  useEffect(() => {
    if (!loaded || !containerRef.current) return;

    // Init map
    const map = new google.maps.Map(containerRef.current, {
      center,
      zoom,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
    });
    mapRef.current = map;

    // Helper: colored circle marker icon
    const circleIcon = (color: string): google.maps.Symbol => ({
      path: google.maps.SymbolPath.CIRCLE,
      scale: 11,
      fillColor: color,
      fillOpacity: 1,
      strokeColor: '#ffffff',
      strokeWeight: 2.5,
    });

    // Existing selected pin (red)
    if (selectedLat !== undefined && selectedLng !== undefined) {
      clickMarkerRef.current = new google.maps.Marker({
        position: { lat: selectedLat, lng: selectedLng },
        map,
        icon: circleIcon('#ef4444'),
        title: 'Selected location',
        animation: google.maps.Animation.DROP,
      });
    }

    // Data marker pins (from DB)
    markers.forEach(m => {
      const marker = new google.maps.Marker({
        position: { lat: m.lat, lng: m.lng },
        map,
        title: m.label,
        icon: circleIcon(m.color || '#2563eb'),
      });
      if (m.popupHtml) {
        const infoWindow = new google.maps.InfoWindow({ content: m.popupHtml });
        marker.addListener('click', () => infoWindow.open({ anchor: marker, map }));
      }
    });

    // Click to drop GPS pin
    if (onMapClick) {
      map.addListener('click', (e: google.maps.MapMouseEvent) => {
        const lat = e.latLng!.lat();
        const lng = e.latLng!.lng();
        if (clickMarkerRef.current) clickMarkerRef.current.setMap(null);
        clickMarkerRef.current = new google.maps.Marker({
          position: { lat, lng },
          map,
          icon: circleIcon('#ef4444'),
          animation: google.maps.Animation.DROP,
        });
        onMapClick(lat, lng);
      });
    }

    // Places Autocomplete on search input
    if (onMapClick && searchInputRef.current) {
      const ac = new google.maps.places.Autocomplete(searchInputRef.current, {
        componentRestrictions: { country: 'my' },
        fields: ['geometry', 'name'],
      });
      ac.addListener('place_changed', () => {
        const place = ac.getPlace();
        if (place.geometry?.location) {
          const lat = place.geometry.location.lat();
          const lng = place.geometry.location.lng();

          // Pan map to the selected place
          map.panTo(place.geometry.location);
          map.setZoom(17);

          // Auto-drop pin and fill coordinates — no need to click the map
          if (clickMarkerRef.current) clickMarkerRef.current.setMap(null);
          clickMarkerRef.current = new google.maps.Marker({
            position: { lat, lng },
            map,
            icon: circleIcon('#ef4444'),
            animation: google.maps.Animation.DROP,
          });
          onMapClick(lat, lng);
        }
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);

  return (
    <div>
      {/* Google Places search — only in GPS-picking mode */}
      {onMapClick && (
        <div style={{ marginBottom: 8 }}>
          <input
            ref={searchInputRef}
            type="text"
            placeholder='🔍 Search place (e.g. "Kek Lok Si Temple")...'
            style={{
              width: '100%', padding: '9px 12px', border: '1px solid #d1d5db',
              borderRadius: 8, fontSize: 13.5, outline: 'none', fontFamily: 'inherit',
              color: '#111827', background: '#fff', boxSizing: 'border-box',
            }}
          />
          <p style={{ fontSize: 11.5, color: '#9ca3af', marginTop: 5, marginBottom: 0 }}>
            Select from dropdown → pin drops automatically · Click map to move the pin
          </p>
        </div>
      )}

      {/* Map */}
      <div
        ref={containerRef}
        style={{
          height, width: '100%', borderRadius: 10, overflow: 'hidden',
          border: '1px solid #e8eaed', cursor: onMapClick ? 'crosshair' : 'default',
          background: '#e8f0fe',
        }}
      >
        {!loaded && (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280', fontSize: 13, gap: 8 }}>
            <span>Loading Google Maps...</span>
          </div>
        )}
      </div>
    </div>
  );
}
