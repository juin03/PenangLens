import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest) {
  const status = request.nextUrl.searchParams.get('status') || 'pending'; // 'pending' | 'reviewed' | 'all'
  const page = parseInt(request.nextUrl.searchParams.get('page') || '1');
  const limit = 20;

  const where: any = {};
  if (status === 'pending') where.status = 'pending';
  else if (status === 'reviewed') where.status = 'reviewed';

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

  // Prefer the conversation transcript stored on the feedback record itself.
  // Fall back to an itinerary thread (for itinerary-chat feedback) if not present.
  const enriched = await Promise.all(items.map(async (item: any) => {
    if (Array.isArray(item.conversation) && item.conversation.length > 0) {
      return { ...item, threadHistory: item.conversation };
    }
    if (item.threadId) {
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
    }
    return { ...item, threadHistory: null };
  }));

  return NextResponse.json({ items: enriched, total, page, limit });
}
