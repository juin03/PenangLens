import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest) {
  const rating = request.nextUrl.searchParams.get('rating'); // 'good' | 'bad' | null
  const status = request.nextUrl.searchParams.get('status') || 'pending'; // 'pending' | 'reviewed' | 'all'
  const page = parseInt(request.nextUrl.searchParams.get('page') || '1');
  const limit = 20;

  // Only show itineraries that have feedback
  const feedbackWhere: any = {};
  if (rating === 'good') feedbackWhere.rating = { gte: 4 };
  else if (rating === 'bad') feedbackWhere.rating = { lte: 2 };
  if (status === 'pending') feedbackWhere.status = 'pending';
  else if (status === 'reviewed') feedbackWhere.status = 'reviewed';

  const where: any = { feedbacks: { some: feedbackWhere } };

  const [itineraries, total] = await Promise.all([
    prisma.itinerary.findMany({
      where,
      include: {
        user: { select: { email: true } },
        stops: { orderBy: { stopOrder: 'asc' }, include: { poi: { select: { name: true } } } },
        feedbacks: { select: { id: true, rating: true, comment: true, status: true, createdAt: true } },
        chatHistory: { select: { role: true, content: true, createdAt: true }, orderBy: { createdAt: 'asc' } },
      },
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * limit,
      take: limit,
    }),
    prisma.itinerary.count({ where }),
  ]);

  return NextResponse.json({ itineraries, total, page, limit });
}
