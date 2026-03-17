import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { verifyToken } from '@/lib/auth';

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { itineraryId, rating, comment } = body;

  if (!itineraryId || !rating) {
    return NextResponse.json({ error: 'itineraryId and rating required' }, { status: 400 });
  }

  let userId: string | undefined;
  try {
    const auth = request.headers.get('authorization');
    if (auth?.startsWith('Bearer ')) {
      const payload = verifyToken(auth.slice(7));
      userId = payload?.sub;
    }
  } catch { /* guest */ }

  try {
    await (prisma as any).itineraryFeedback.create({
      data: { itineraryId, rating: Number(rating), comment, userId },
    });
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Itinerary feedback error:', error);
    return NextResponse.json({ error: 'Failed to save feedback' }, { status: 500 });
  }
}
