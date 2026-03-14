import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getUserFromRequest } from '@/lib/auth';

export async function GET(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const itineraries = await prisma.itinerary.findMany({
    where: { userId: user.id },
    include: { stops: { orderBy: { stopOrder: 'asc' } } },
    orderBy: { createdAt: 'desc' },
  });

  return NextResponse.json({ itineraries });
}

export async function POST(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  try {
    const body = await request.json();
    const { name, originalPrompt, generatedNarrative, totalDuration, stops } = body;

    const itinerary = await prisma.itinerary.create({
      data: {
        name: name || 'My Penang Trip',
        originalPrompt,
        generatedNarrative,
        totalDuration,
        userId: user.id,
        stops: stops ? {
          create: stops.map((s: any, i: number) => ({
            stopOrder: s.stopOrder ?? i + 1,
            travelTimeMin: s.travelTimeMin,
            poiId: s.poiId || null,
          })),
        } : undefined,
      },
      include: { stops: true },
    });

    return NextResponse.json({ itinerary }, { status: 201 });
  } catch (error) {
    console.error('Create itinerary error:', error);
    return NextResponse.json({ error: 'Failed to save itinerary' }, { status: 500 });
  }
}
