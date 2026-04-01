import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest) {
  const status = request.nextUrl.searchParams.get('status') || 'pending';
  const page = parseInt(request.nextUrl.searchParams.get('page') || '1');
  const limit = 20;

  const [items, total] = await Promise.all([
    prisma.recognitionFeedback.findMany({
      where: status === 'all' ? {} : { status },
      include: {
        user: { select: { email: true } },
        recognition: { include: { poi: { select: { name: true } } } },
      },
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * limit,
      take: limit,
    }),
    prisma.recognitionFeedback.count({ where: status === 'all' ? {} : { status } }),
  ]);

  return NextResponse.json({ items, total, page, limit });
}
