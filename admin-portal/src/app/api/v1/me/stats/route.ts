import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { verifyToken } from '@/lib/auth';

export async function GET(request: NextRequest) {
  let userId: string | null = null;
  try {
    const auth = request.headers.get('authorization');
    if (auth?.startsWith('Bearer ')) {
      const payload = verifyToken(auth.slice(7));
      userId = payload?.sub ?? null;
    }
  } catch { /* no auth */ }

  if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  try {
    const [totalScans, totalItineraries, uniqueSpotsRaw] = await Promise.all([
      prisma.recognitionHistory.count({ where: { userId } }),
      prisma.itinerary.count({ where: { userId } }),
      prisma.recognitionHistory.findMany({
        where: { userId, poiId: { not: null } },
        select: { poiId: true },
        distinct: ['poiId'],
      }),
    ]);

    return NextResponse.json({
      totalScans,
      totalItineraries,
      uniqueSpots: uniqueSpotsRaw.length,
    });
  } catch (error) {
    console.error('User stats error:', error);
    return NextResponse.json({ error: 'Failed to fetch stats' }, { status: 500 });
  }
}
