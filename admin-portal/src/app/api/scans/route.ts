import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getUserFromRequest } from '@/lib/auth';

export async function GET(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const scans = await prisma.recognitionHistory.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: 'desc' },
    take: 50,
  });

  return NextResponse.json({ scans });
}

export async function POST(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  try {
    const body = await request.json();
    const { userImageUrl, userLatitude, userLongitude, aiDetails, poiId } = body;

    const scan = await prisma.recognitionHistory.create({
      data: {
        userImageUrl,
        userLatitude,
        userLongitude,
        aiDetails,
        poiId: poiId || null,
        userId: user.id,
      },
    });

    return NextResponse.json({ scan }, { status: 201 });
  } catch (error) {
    console.error('Save scan error:', error);
    return NextResponse.json({ error: 'Failed to save scan' }, { status: 500 });
  }
}
