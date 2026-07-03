import { NextRequest, NextResponse } from 'next/server';

/**
 * Google Places photo proxy.
 *
 * The Agent returns itinerary photo URLs pointing here instead of directly at
 * places.googleapis.com, so the server API key never appears in client-visible URLs.
 * Responses are cacheable, which also cuts repeat Photos-API billing.
 */

// Places photo resource names look like: places/<placeId>/photos/<photoId>
const PHOTO_REF_PATTERN = /^places\/[A-Za-z0-9_-]+\/photos\/[A-Za-z0-9_-]+$/;

export async function GET(request: NextRequest) {
  const ref = request.nextUrl.searchParams.get('ref') || '';
  if (!PHOTO_REF_PATTERN.test(ref)) {
    return NextResponse.json({ error: 'Invalid photo reference' }, { status: 400 });
  }

  const apiKey = process.env.GOOGLE_MAPS_API_KEY || process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: 'Maps API key not configured' }, { status: 503 });
  }

  const maxHeight = Math.min(Number(request.nextUrl.searchParams.get('h')) || 400, 1600);

  try {
    const upstream = await fetch(
      `https://places.googleapis.com/v1/${ref}/media?maxHeightPx=${maxHeight}&key=${apiKey}`,
    );
    if (!upstream.ok) {
      return NextResponse.json({ error: 'Photo unavailable' }, { status: upstream.status });
    }
    return new NextResponse(upstream.body, {
      status: 200,
      headers: {
        'Content-Type': upstream.headers.get('content-type') || 'image/jpeg',
        // Photos rarely change — cache aggressively on device and CDN
        'Cache-Control': 'public, max-age=86400, s-maxage=604800, immutable',
      },
    });
  } catch (error) {
    console.error('Photo proxy error:', error);
    return NextResponse.json({ error: 'Photo proxy error' }, { status: 502 });
  }
}
