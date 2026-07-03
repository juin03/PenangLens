import { NextRequest, NextResponse } from 'next/server';
import { getUserFromRequest } from '@/lib/auth';

/**
 * Places Autocomplete proxy.
 *
 * The mobile app used to call Google directly with a key shipped in the bundle —
 * extractable by anyone. This route keeps the key server-side and requires a valid
 * user JWT, so abuse means abusing an account we can rate-limit or ban.
 *
 * Pass the same `sessiontoken` for all keystrokes of one search plus the final
 * details call — Google then bills the whole session as one request instead of
 * billing every keystroke.
 */
export async function GET(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const input = request.nextUrl.searchParams.get('input')?.trim() || '';
  const sessiontoken = request.nextUrl.searchParams.get('sessiontoken') || '';
  if (input.length < 2 || input.length > 120) {
    return NextResponse.json({ predictions: [] });
  }

  const apiKey = process.env.GOOGLE_MAPS_API_KEY || process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  if (!apiKey) return NextResponse.json({ error: 'Maps API key not configured' }, { status: 503 });

  try {
    const params = new URLSearchParams({
      input,
      components: 'country:my',
      key: apiKey,
    });
    if (sessiontoken) params.set('sessiontoken', sessiontoken);

    const res = await fetch(`https://maps.googleapis.com/maps/api/place/autocomplete/json?${params}`);
    const data = await res.json();
    const predictions = (data.predictions ?? []).slice(0, 5).map((p: any) => ({
      description: p.description,
      place_id: p.place_id,
    }));
    return NextResponse.json({ predictions });
  } catch (error) {
    console.error('Autocomplete proxy error:', error);
    return NextResponse.json({ predictions: [] }, { status: 502 });
  }
}
