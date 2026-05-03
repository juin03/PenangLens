import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest) {
  const rating = request.nextUrl.searchParams.get('rating');
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

  // For items with a threadId, fetch the full conversation thread
  const enriched = await Promise.all(items.map(async (item: any) => {
    if (!item.threadId) return { ...item, threadHistory: null };
    const itinerary = await prisma.itinerary.findFirst({
      where: { threadId: item.threadId },
      include: {
        chatHistory: {
          select: { role: true, content: true, createdAt: true },
          orderBy: { createdAt: 'asc' },
        },
      },
    });
    return { ...item, threadHistory: itinerary?.chatHistory ?? null };
  }));

  return NextResponse.json({ items: enriched, total, page, limit });
}
