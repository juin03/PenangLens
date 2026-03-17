import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

const AGENT_BASE_URL = process.env.AGENT_URL || process.env.AGENT_BASE_URL || 'http://127.0.0.1:8000';
export const dynamic = 'force-dynamic';
export const revalidate = 0;

const INTEREST_TAG_MAP: Record<string, string[]> = {
  'heritage': ['Heritage'],
  'food': ['Food'],
  'nature': ['Nature'],
  'art': ['Art'],
  'religious': ['Religious'],
  'shopping': ['Shopping'],
  'historical': ['Historical'],
  'architecture': ['Architecture'],

  'street art': ['Art', 'Heritage'],
  'history': ['Historical', 'Heritage'],
  'local food': ['Food'],
  'museums': ['Art', 'Historical', 'Heritage'],
  'nightlife': ['Food', 'Shopping'],
  'coffee shops': ['Food'],
  'live music': ['Art', 'Food'],
};

// Public endpoint — no auth required
// Returns all published landmarks + POIs that have GPS coordinates
export async function GET(request: NextRequest) {
  try {
    const includeAll = request.nextUrl.searchParams.get('all') === 'true'; // admin passes ?all=true

    const [landmarks, pois] = await Promise.all([
      prisma.landmark.findMany({
        where: includeAll ? {} : { status: 'published' },
        include: { 
          tags: { include: { tag: true } },
          // Get first image via first POI's images
          pois: {
            take: 1,
            include: { images: { take: 1, orderBy: { createdAt: 'asc' } } },
            orderBy: { createdAt: 'asc' },
          },
        },
        orderBy: { name: 'asc' },
      }),
      prisma.pointOfInterest.findMany({
        where: includeAll ? {} : { status: 'published' },
        include: { 
          landmark: { select: { name: true } },
          images: { take: 1, orderBy: { createdAt: 'asc' } },
        },
        orderBy: { name: 'asc' },
      }),
    ]);

    const parseCoords = (location: string | null): { lat: number; lng: number } | null => {
      if (!location) return null;

      const raw = location.trim();

      const parsePair = (value: string): { lat: number; lng: number } | null => {
        const cleaned = value.replace(/[°NSEW\s]/g, '');
        const parts = cleaned.split(',');
        if (parts.length !== 2) return null;
        const lat = parseFloat(parts[0]);
        const lng = parseFloat(parts[1]);
        if (Number.isNaN(lat) || Number.isNaN(lng)) return null;
        if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
        return { lat, lng };
      };

      const direct = parsePair(raw);
      if (direct) return direct;

      try {
        const url = new URL(raw);
        const qParam = url.searchParams.get('q') || url.searchParams.get('query');
        if (qParam) {
          const fromQuery = parsePair(qParam);
          if (fromQuery) return fromQuery;
        }

        const atMatch = decodeURIComponent(url.pathname).match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
        if (atMatch) {
          const fromAt = parsePair(`${atMatch[1]},${atMatch[2]}`);
          if (fromAt) return fromAt;
        }
      } catch {
      }

      return null;
    };

    const spots = [
      ...landmarks
        .map(l => {
          const coords = parseCoords(l.location);
          if (!coords) return null;
          // Get first image from first POI
          const firstImg = l.pois[0]?.images[0]?.imageUrl ?? null;
          return {
            id: l.id,
            name: l.name,
            type: 'landmark',
            status: l.status,
            description: l.description,
            tags: l.tags.map(t => t.tag.name),
            firstImageUrl: firstImg,
            ...coords,
          };
        })
        .filter(Boolean),
      ...pois
        .map(p => {
          const coords = parseCoords(p.location);
          if (!coords) return null;
          const firstImg = p.images[0]?.imageUrl ?? null;
          return {
            id: p.id,
            name: p.name,
            type: 'poi',
            status: p.status,
            description: p.description,
            parentLandmark: p.landmark?.name,
            firstImageUrl: firstImg,
            ...coords,
          };
        })
        .filter(Boolean),
    ];

    const interestsCsv = request.nextUrl.searchParams.get('interests') || '';
    const interests = interestsCsv
      .split(',')
      .map(i => i.trim())
      .filter(Boolean);

    const normalizedInterests = interests.map(i => i.toLowerCase());
    const mappedTags = normalizedInterests.flatMap(i => INTEREST_TAG_MAP[i] || []);
    const allPriorityTokens = new Set<string>([
      ...normalizedInterests,
      ...mappedTags.map(t => t.toLowerCase()),
    ]);

    const localScoreForSpot = (spot: any): number => {
      if (allPriorityTokens.size === 0) return 0;

      const tags = Array.isArray(spot.tags) ? spot.tags : [];
      const tagTokens = tags.map((t: string) => t.toLowerCase());
      const textBlob = `${spot.name || ''} ${spot.description || ''} ${spot.parentLandmark || ''}`.toLowerCase();

      let score = 0;
      for (const token of allPriorityTokens) {
        if (tagTokens.includes(token)) score += 20;
        if (textBlob.includes(token)) score += 4;
      }
      return score;
    };

    if (interests.length > 0) {
      try {
        const recRes = await fetch(`${AGENT_BASE_URL}/api/v1/personalization/recommendations`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ interests, top_k: 30 }),
        });

        if (recRes.ok) {
          const recData = await recRes.json();
          const recommendations = Array.isArray(recData?.recommendations) ? recData.recommendations : [];
          const scoreBySpotId = new Map<string, number>();

          for (const item of recommendations) {
            const spotId = item?.spot_id;
            const score = Number(item?.score ?? 0);
            if (spotId && !Number.isNaN(score)) {
              const prev = scoreBySpotId.get(spotId) ?? Number.NEGATIVE_INFINITY;
              if (score > prev) scoreBySpotId.set(spotId, score);
            }
          }

          spots.sort((a: any, b: any) => {
            const scoreA = scoreBySpotId.get(a.id) ?? Number.NEGATIVE_INFINITY;
            const scoreB = scoreBySpotId.get(b.id) ?? Number.NEGATIVE_INFINITY;
            if (scoreA !== scoreB) return scoreB - scoreA;
            const localA = localScoreForSpot(a);
            const localB = localScoreForSpot(b);
            if (localA !== localB) return localB - localA;
            return String(a.name).localeCompare(String(b.name));
          });
        } else {
          spots.sort((a: any, b: any) => {
            const localA = localScoreForSpot(a);
            const localB = localScoreForSpot(b);
            if (localA !== localB) return localB - localA;
            return String(a.name).localeCompare(String(b.name));
          });
        }
      } catch (error) {
        console.error('Personalized map ranking failed:', error);
        spots.sort((a: any, b: any) => {
          const localA = localScoreForSpot(a);
          const localB = localScoreForSpot(b);
          if (localA !== localB) return localB - localA;
          return String(a.name).localeCompare(String(b.name));
        });
      }
    }

    return NextResponse.json(
      { spots },
      { headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0' } }
    );
  } catch (error) {
    console.error('Map spots error:', error);
    return NextResponse.json({ error: 'Failed to fetch map spots' }, { status: 500 });
  }
}
