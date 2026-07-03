import { NextRequest, NextResponse } from 'next/server';
import { getUserFromRequest } from '@/lib/auth';

/**
 * Place Details proxy (geometry only) — companion to the autocomplete proxy.
 * Send the same `sessiontoken` used for the autocomplete keystrokes so Google
 * bills the whole search as a single session.
 */
const PLACE_ID_PATTERN = /^[A-Za-z0-9_-]{10,200}$/;

export async function GET(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const placeId = request.nextUrl.searchParams.get('place_id') || '';
  const sessiontoken = request.nextUrl.searchParams.get('sessiontoken') || '';
  if (!PLACE_ID_PATTERN.test(placeId)) {
    return NextResponse.json({ error: 'Invalid place_id' }, { status: 400 });
  }

  const apiKey = process.env.GOOGLE_MAPS_API_KEY || process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  if (!apiKey) return NextResponse.json({ error: 'Maps API key not configured' }, { status: 503 });

  try {
    const params = new URLSearchParams({
      place_id: placeId,
      fields: 'geometry',
      key: apiKey,
    });
    if (sessiontoken) params.set('sessiontoken', sessiontoken);

    const res = await fetch(`https://maps.googleapis.com/maps/api/place/details/json?${params}`);
    const data = await res.json();
    const location = data.result?.geometry?.location ?? null;
    return NextResponse.json({ location });
  } catch (error) {
    console.error('Place details proxy error:', error);
    return NextResponse.json({ location: null }, { status: 502 });
  }
}
