import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest) {
  const days = parseInt(request.nextUrl.searchParams.get('days') || '30');
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

  try {
    const [totalRecognitions, feedbackCount, correctCount, recentFeedback] = await Promise.all([
      prisma.recognitionHistory.count({ where: { createdAt: { gte: since } } }),
      prisma.recognitionFeedback.count({ where: { createdAt: { gte: since } } }),
      prisma.recognitionFeedback.count({ where: { createdAt: { gte: since }, isCorrect: true } }),
      prisma.recognitionFeedback.findMany({
        where: { createdAt: { gte: since } },
        orderBy: { createdAt: 'desc' },
        take: 20,
        include: {
          user: { select: { email: true } },
          recognition: { include: { poi: { select: { name: true } } } },
        },
      }),
    ]);

    // Mock category accuracy (fill with real data when you have enough scans)
    const categories = [
      { label: 'Buildings', accuracy: 87 },
      { label: 'Food', accuracy: 72 },
      { label: 'Nature', accuracy: 91 },
      { label: 'People', accuracy: 65 },
      { label: 'Events', accuracy: 78 },
    ];

    return NextResponse.json({
      totalRecognitions,
      feedbackCount,
      correctCount,
      categories,
      recentFeedback,
    });
  } catch (error) {
    console.error('Analytics error:', error);
    return NextResponse.json({ error: 'Failed to fetch analytics' }, { status: 500 });
  }
}
