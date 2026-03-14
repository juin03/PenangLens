import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// Public endpoint — no auth required
// Returns all published landmarks + POIs that have GPS coordinates
export async function GET(request: NextRequest) {
  try {
    const includeAll = request.nextUrl.searchParams.get('all') === 'true'; // admin passes ?all=true

    const [landmarks, pois] = await Promise.all([
      prisma.landmark.findMany({
        where: includeAll ? {} : { status: 'published' },
        include: { tags: { include: { tag: true } } },
        orderBy: { name: 'asc' },
      }),
      prisma.pointOfInterest.findMany({
        where: includeAll ? {} : { status: 'published' },
        include: { landmark: { select: { name: true } } },
        orderBy: { name: 'asc' },
      }),
    ]);

    const parseCoords = (location: string | null): { lat: number; lng: number } | null => {
      if (!location) return null;
      const parts = location.replace(/[°NSEW\s]/g, '').split(',');
      if (parts.length !== 2) return null;
      const lat = parseFloat(parts[0]);
      const lng = parseFloat(parts[1]);
      if (isNaN(lat) || isNaN(lng)) return null;
      return { lat, lng };
    };

    const spots = [
      ...landmarks
        .map(l => {
          const coords = parseCoords(l.location);
          if (!coords) return null;
          return {
            id: l.id,
            name: l.name,
            type: 'landmark',
            status: l.status,
            description: l.description,
            tags: l.tags.map(t => t.tag.name),
            ...coords,
          };
        })
        .filter(Boolean),
      ...pois
        .map(p => {
          const coords = parseCoords(p.location);
          if (!coords) return null;
          return {
            id: p.id,
            name: p.name,
            type: 'poi',
            status: p.status,
            description: p.description,
            parentLandmark: p.landmark?.name,
            ...coords,
          };
        })
        .filter(Boolean),
    ];

    return NextResponse.json({ spots });
  } catch (error) {
    console.error('Map spots error:', error);
    return NextResponse.json({ error: 'Failed to fetch map spots' }, { status: 500 });
  }
}
