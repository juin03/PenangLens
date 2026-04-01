import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest) {
  const rating = request.nextUrl.searchParams.get('rating'); // '1' | '-1' | null
  const page = parseInt(request.nextUrl.searchParams.get('page') || '1');
  const limit = 20;

  const where = rating ? { rating: Number(rating) } : {};

  const [items, total] = await Promise.all([
    (prisma as any).chatFeedback.findMany({
      where,
      include: { user: { select: { email: true } } },
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * limit,
      take: limit,
    }),
    (prisma as any).chatFeedback.count({ where }),
  ]);

  return NextResponse.json({ items, total, page, limit });
}
